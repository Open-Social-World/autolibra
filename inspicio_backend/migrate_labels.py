import os
import json
import logging
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration for the old inspiciodb database
OLD_DB_CONFIG = {
    "dbname": "inspiciodb",
    "user": "postgres",
    "password": "Yankayee123",
    "host": "localhost",
    "port": "5432"
}

# Configuration for the new autolibra database
NEW_DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

class LabelMigration:
    def __init__(self):
        self.old_conn = None
        self.old_cursor = None
        self.new_conn = None
        self.new_cursor = None
        
    def connect_to_old_db(self):
        """Connect to the old inspiciodb database"""
        try:
            self.old_conn = psycopg2.connect(**OLD_DB_CONFIG)
            self.old_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.old_cursor = self.old_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            logger.info("Connected to old inspiciodb database")
        except Exception as e:
            logger.error(f"Failed to connect to old database: {e}")
            raise
    
    def connect_to_new_db(self):
        """Connect to the new autolibra database"""
        try:
            self.new_conn = psycopg2.connect(**NEW_DB_CONFIG)
            self.new_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.new_cursor = self.new_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            logger.info("Connected to new autolibra database")
        except Exception as e:
            logger.error(f"Failed to connect to new database: {e}")
            raise
    
    def close_connections(self):
        """Close all database connections"""
        if self.old_cursor:
            self.old_cursor.close()
        if self.old_conn:
            self.old_conn.close()
        if self.new_cursor:
            self.new_cursor.close()
        if self.new_conn:
            self.new_conn.close()
        logger.info("Database connections closed")
    
    def extract_instance_id_from_filepath(self, filepath: str) -> str:
        """Extract instance ID from filepath in the old database"""
        # Example filepath: "nnetnav_openweb_3/2025-01-01_10-30-31_GenericAgent-meta-llama_Meta-Llama-3.1-70B-Instruct-Turbo_on_openweb_nnetnav_openended_0_0/experiment.log"
        # We want to extract: "2025-01-01_10-30-31_GenericAgent-meta-llama_Meta-Llama-3.1-70B-Instruct-Turbo_on_openweb_nnetnav_openended_0_0"
        
        # Split by '/' and get the second part (index 1)
        parts = filepath.split('/')
        if len(parts) >= 2:
            return parts[1]
        return None
    
    def get_labels_from_old_db(self):
        """Get all labels from the old database"""
        logger.info("Fetching labels from old database...")
        
        try:
            # Query to get unique descriptions (labels) for WebVoyager files
            self.old_cursor.execute("""
                SELECT DISTINCT filepath, description 
                FROM files 
                WHERE filepath LIKE '%nnetnav_openweb_3%' 
                AND description IS NOT NULL 
                AND description != ''
                ORDER BY filepath
            """)
            
            results = self.old_cursor.fetchall()
            logger.info(f"Found {len(results)} labeled files in old database")
            
            # Group by instance_id
            instance_labels = {}
            for row in results:
                filepath = row['filepath']
                description = row['description']
                
                instance_id = self.extract_instance_id_from_filepath(filepath)
                if instance_id:
                    if instance_id not in instance_labels:
                        instance_labels[instance_id] = set()
                    instance_labels[instance_id].add(description)
            
            # Convert sets to lists for easier handling
            for instance_id in instance_labels:
                instance_labels[instance_id] = list(instance_labels[instance_id])
            
            logger.info(f"Found labels for {len(instance_labels)} unique instances")
            return instance_labels
            
        except Exception as e:
            logger.error(f"Error fetching labels from old database: {e}")
            raise
    
    def update_labels_in_new_db(self, instance_labels: dict):
        """Update labels in the new database"""
        logger.info("Updating labels in new database...")
        
        updated_count = 0
        not_found_count = 0
        
        for instance_id, labels in instance_labels.items():
            try:
                # Join multiple labels with semicolon if there are multiple
                label_text = "; ".join(labels) if len(labels) > 1 else labels[0]
                
                # Update the label in webvoyager_instances table
                self.new_cursor.execute("""
                    UPDATE webvoyager_instances 
                    SET label = %s 
                    WHERE instance_id = %s
                """, (label_text, instance_id))
                
                if self.new_cursor.rowcount > 0:
                    updated_count += 1
                    logger.info(f"Updated label for instance {instance_id}: {label_text}")
                else:
                    not_found_count += 1
                    logger.warning(f"Instance {instance_id} not found in new database")
                    
            except Exception as e:
                logger.error(f"Error updating label for instance {instance_id}: {e}")
                continue
        
        logger.info(f"Label migration completed:")
        logger.info(f"  - Updated: {updated_count} instances")
        logger.info(f"  - Not found: {not_found_count} instances")
    
    def verify_migration(self):
        """Verify that labels were migrated correctly"""
        logger.info("Verifying label migration...")
        
        try:
            # Count instances with labels in new database
            self.new_cursor.execute("""
                SELECT COUNT(*) as count 
                FROM webvoyager_instances 
                WHERE label IS NOT NULL AND label != '' AND label != 'WebVoyager Experiment'
            """)
            
            result = self.new_cursor.fetchone()
            labeled_count = result['count']
            
            # Count total instances
            self.new_cursor.execute("SELECT COUNT(*) as count FROM webvoyager_instances")
            result = self.new_cursor.fetchone()
            total_count = result['count']
            
            logger.info(f"Verification results:")
            logger.info(f"  - Total instances: {total_count}")
            logger.info(f"  - Instances with labels: {labeled_count}")
            logger.info(f"  - Label coverage: {labeled_count/total_count*100:.1f}%")
            
            # Show some example labels
            self.new_cursor.execute("""
                SELECT instance_id, label 
                FROM webvoyager_instances 
                WHERE label IS NOT NULL AND label != '' AND label != 'WebVoyager Experiment'
                LIMIT 5
            """)
            
            examples = self.new_cursor.fetchall()
            logger.info("Example labels:")
            for example in examples:
                logger.info(f"  - {example['instance_id']}: {example['label']}")
                
        except Exception as e:
            logger.error(f"Error during verification: {e}")
    
    def run_migration(self):
        """Run the complete label migration"""
        logger.info("Starting label migration from inspiciodb to autolibra...")
        
        try:
            self.connect_to_old_db()
            self.connect_to_new_db()
            
            # Get labels from old database
            instance_labels = self.get_labels_from_old_db()
            
            if not instance_labels:
                logger.warning("No labels found in old database")
                return
            
            # Update labels in new database
            self.update_labels_in_new_db(instance_labels)
            
            # Verify migration
            self.verify_migration()
            
            logger.info("Label migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Label migration failed: {e}")
            raise
        finally:
            self.close_connections()

def main():
    """Main function to run label migration"""
    migration = LabelMigration()
    migration.run_migration()

if __name__ == "__main__":
    main() 