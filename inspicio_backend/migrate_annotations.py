import os
import json
import logging
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
load_dotenv()

from osw_data.annotation import AnnotationSystem

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration for the new autolibra database
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

class AnnotationMigration:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.base_annotation_path = Path(__file__).parent.parent / ".data" / "annotations"
        
    def connect_to_db(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def close_db(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def create_annotation_tables(self):
        """Create annotation tables for each dataset"""
        logger.info("Creating annotation tables...")
        
        # Create annotation tables for each dataset
        datasets = ["sotopia", "webarena", "webvoyager"]
        
        for dataset in datasets:
            table_name = f"{dataset}_annotations"
            
            self.cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    annotation_id VARCHAR(255) UNIQUE NOT NULL,
                    instance_id VARCHAR(255) NOT NULL,
                    agent_id VARCHAR(255) NOT NULL,
                    annotator_id VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    content JSONB NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    confidence FLOAT,
                    metadata JSONB,
                    created_at_db TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_instance ON {table_name}(instance_id)")
            self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_agent ON {table_name}(agent_id)")
            self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_annotator ON {table_name}(annotator_id)")
            self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_annotation_id ON {table_name}(annotation_id)")
            
            logger.info(f"Created annotation table for {dataset}")
    
    def migrate_dataset_annotations(self, dataset_name: str):
        """Migrate annotations for a specific dataset using AnnotationSystem"""
        logger.info(f"Starting annotation migration for {dataset_name}...")

        annotation_dir = self.base_annotation_path / dataset_name
        
        if not annotation_dir.exists():
            logger.warning(f"Annotation directory not found for {dataset_name}: {annotation_dir}")
            return
        
        # Initialize AnnotationSystem for this dataset
        try:
            annotation_system = AnnotationSystem(base_path=annotation_dir)
            logger.info(f"Initialized AnnotationSystem for {dataset_name}")
        except Exception as e:
            logger.error(f"Failed to initialize AnnotationSystem for {dataset_name}: {e}")
            return
        
        # Get all trajectory annotations from the AnnotationSystem
        migrated_count = 0
        skipped_count = 0
        
        try:
            # Get all annotation files from the AnnotationSystem
            annotation_files = list(annotation_dir.glob("annotations/*.json"))
            logger.info(f"Found {len(annotation_files)} annotation files for {dataset_name}")
            
            for annotation_file in annotation_files:
                try:
                    # Extract instance_id and agent_id from filename
                    # Format: {instance_id}_{agent_id}.json
                    filename = annotation_file.stem
                    if '_' in filename:
                        parts = filename.split('_', 1)
                        if len(parts) == 2:
                            instance_id = parts[0]
                            agent_id = parts[1]
                        else:
                            logger.warning(f"Invalid filename format: {filename}")
                            skipped_count += 1
                            continue
                    else:
                        logger.warning(f"Invalid filename format: {filename}")
                        skipped_count += 1
                        continue
                    
                    # Get trajectory annotations using AnnotationSystem
                    trajectory_annotations = annotation_system.get_trajectory_annotations(
                        instance_id=instance_id,
                        agent_id=agent_id
                    )
                    
                    # Insert each annotation into the database
                    for annotation in trajectory_annotations.annotations:
                        try:
                            # Extract annotation details from the AnnotationSystem object
                            annotation_id = annotation.annotation_id
                            annotator_id = annotation.annotator_id
                            created_at = annotation.created_at
                            updated_at = annotation.updated_at
                            content = annotation.content
                            span = annotation.span
                            confidence = annotation.confidence
                            metadata = annotation.metadata
                            
                            # Parse timestamps
                            start_time = None
                            end_time = None
                            if span:
                                start_time = span.start_time
                                end_time = span.end_time
                            
                            # Insert into database
                            table_name = f"{dataset_name}_annotations"
                            
                            self.cursor.execute(f"""
                                INSERT INTO {table_name} 
                                (annotation_id, instance_id, agent_id, annotator_id, created_at, updated_at, 
                                 content, start_time, end_time, confidence, metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (annotation_id) DO UPDATE SET
                                instance_id = EXCLUDED.instance_id,
                                agent_id = EXCLUDED.agent_id,
                                annotator_id = EXCLUDED.annotator_id,
                                created_at = EXCLUDED.created_at,
                                updated_at = EXCLUDED.updated_at,
                                content = EXCLUDED.content,
                                start_time = EXCLUDED.start_time,
                                end_time = EXCLUDED.end_time,
                                confidence = EXCLUDED.confidence,
                                metadata = EXCLUDED.metadata
                            """, (
                                annotation_id,
                                instance_id,
                                agent_id,
                                annotator_id,
                                created_at,
                                updated_at,
                                json.dumps(content) if content else '{}',
                                start_time,
                                end_time,
                                confidence,
                                json.dumps(metadata) if metadata else '{}'
                            ))
                            
                            migrated_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error inserting annotation {annotation.annotation_id} for {dataset_name}: {e}")
                            skipped_count += 1
                            continue
                
                except Exception as e:
                    logger.error(f"Error processing annotation file {annotation_file}: {e}")
                    skipped_count += 1
                    continue
                    
        except Exception as e:
            logger.error(f"Error accessing AnnotationSystem for {dataset_name}: {e}")
            return
        
        logger.info(f"Completed annotation migration for {dataset_name}:")
        logger.info(f"  - Migrated: {migrated_count} annotations")
        logger.info(f"  - Skipped: {skipped_count} annotations")
    
    def verify_migration(self):
        """Verify that annotations were migrated correctly"""
        logger.info("Verifying annotation migration...")
        
        datasets = ["sotopia", "webarena", "webvoyager"]
        
        for dataset in datasets:
            try:
                table_name = f"{dataset}_annotations"
                
                # Count annotations in database
                self.cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                result = self.cursor.fetchone()
                db_count = result['count']
                
                file_count = 0
                annotation_dir = self.base_annotation_path / dataset
                if annotation_dir.exists():
                    annotations_dir = annotation_dir / "annotations"
                    if annotations_dir.exists():
                        annotation_files = list(annotations_dir.glob("*.json"))
                        file_count = len(annotation_files)
                
                logger.info(f"{dataset.title()} annotations:")
                logger.info(f"  - Files: {file_count}")
                logger.info(f"  - Database records: {db_count}")
                
                # Show some example annotations
                self.cursor.execute(f"""
                    SELECT annotation_id, instance_id, agent_id, annotator_id, created_at
                    FROM {table_name} 
                    LIMIT 3
                """)
                
                examples = self.cursor.fetchall()
                if examples:
                    logger.info(f"  - Example annotations:")
                    for example in examples:
                        logger.info(f"    * {example['annotation_id']} - {example['instance_id']} - {example['agent_id']} - {example['annotator_id']}")
                
            except Exception as e:
                logger.error(f"Error verifying {dataset} annotations: {e}")
    
    def run_migration(self):
        """Run the complete annotation migration"""
        logger.info("Starting annotation migration to autolibra database...")
        
        try:
            self.connect_to_db()
            self.create_annotation_tables()
            
            # Migrate annotations for each dataset
            datasets = ["sotopia", "webarena", "webvoyager"]
            
            for dataset in datasets:
                self.migrate_dataset_annotations(dataset)
            
            # Verify migration
            self.verify_migration()
            
            logger.info("Annotation migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Annotation migration failed: {e}")
            raise
        finally:
            self.close_db()

def main():
    """Main function to run annotation migration"""
    migration = AnnotationMigration()
    migration.run_migration()

if __name__ == "__main__":
    main() 