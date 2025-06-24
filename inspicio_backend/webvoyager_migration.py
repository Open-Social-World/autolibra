import os
import json
import sys
import logging
import re
import gzip
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

class WebVoyagerMigration:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.dataset_path = Path(__file__).parent.parent / ".data" / "nnetnav_openweb_3"
        self.metrics_path = Path(__file__).parent.parent / ".data" / "metrics" / "webvoyager-nnetnav"
        
    def validate_db_config(self):
        """Validate that all required database environment variables are set"""
        required_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.warning(f"Missing database environment variables: {', '.join(missing_vars)}")
            logger.info("Using default values for database connection")
        
        logger.info("Database configuration validation passed")
        
    def connect_to_db(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.conn.cursor()
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
    
    def create_tables(self):
        """Create WebVoyager-specific database tables"""
        logger.info("Creating WebVoyager database tables...")
        
        # Table for instances
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS webvoyager_instances (
                instance_id VARCHAR(255) PRIMARY KEY,
                timestamp TIMESTAMP,
                scenario TEXT,
                experiment_tag VARCHAR(255),
                source_model VARCHAR(255),
                models JSONB,
                rewards JSONB,
                label VARCHAR(500),
                metadata JSONB,
                summary_info JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table for agents
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS webvoyager_agents (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES webvoyager_instances(instance_id) ON DELETE CASCADE,
                agent_id VARCHAR(255) NOT NULL,
                agent_type VARCHAR(100),
                capabilities JSONB,
                parameters JSONB,
                background TEXT,
                additional_info JSONB,
                UNIQUE(instance_id, agent_id)
            )
        """)
        
        # Table for trajectory points (experiment steps)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS webvoyager_trajectory_points (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES webvoyager_instances(instance_id) ON DELETE CASCADE,
                agent_id VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                point_type VARCHAR(50) NOT NULL,
                media_type VARCHAR(50),
                data_content JSONB,
                data_text TEXT,
                metadata JSONB,
                point_index INTEGER,
                step_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id, agent_id, step_number, point_type)
            )
        """)
        
        # Drop and recreate experiment logs table to ensure unique constraint
        self.cursor.execute("DROP TABLE IF EXISTS webvoyager_experiment_logs CASCADE")
        self.cursor.execute("""
            CREATE TABLE webvoyager_experiment_logs (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES webvoyager_instances(instance_id) ON DELETE CASCADE,
                log_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id)
            )
        """)
        
        # Drop and recreate step files table to ensure BYTEA column type
        self.cursor.execute("DROP TABLE IF EXISTS webvoyager_step_files CASCADE")
        self.cursor.execute("""
            CREATE TABLE webvoyager_step_files (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES webvoyager_instances(instance_id) ON DELETE CASCADE,
                step_number INTEGER,
                step_data BYTEA,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id, step_number)
            )
        """)
        
        # Table for screenshots
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS webvoyager_screenshots (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES webvoyager_instances(instance_id) ON DELETE CASCADE,
                step_number INTEGER,
                screenshot_data BYTEA,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id, step_number)
            )
        """)
        
        # Table for metrics
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS webvoyager_metrics (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES webvoyager_instances(instance_id) ON DELETE CASCADE,
                agent_id VARCHAR(255) NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value FLOAT,
                reasoning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id, agent_id, metric_name)
            )
        """)
        
        # Create indexes for better performance
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_agents_instance ON webvoyager_agents(instance_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_trajectory_instance ON webvoyager_trajectory_points(instance_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_trajectory_agent ON webvoyager_trajectory_points(agent_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_trajectory_step ON webvoyager_trajectory_points(step_number)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_logs_instance ON webvoyager_experiment_logs(instance_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_screenshots_instance ON webvoyager_screenshots(instance_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_screenshots_step ON webvoyager_screenshots(step_number)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_step_files_instance ON webvoyager_step_files(instance_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_step_files_step ON webvoyager_step_files(step_number)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_metrics_instance ON webvoyager_metrics(instance_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_webvoyager_metrics_agent ON webvoyager_metrics(agent_id)")
        
        logger.info("WebVoyager tables created successfully")
    
    def parse_instance_id_from_path(self, folder_path: Path) -> str:
        """Extract instance ID from folder path"""
        # Example: 2025-01-01_10-30-31_GenericAgent-meta-llama_Meta-Llama-3.1-70B-Instruct-Turbo_on_openweb_nnetnav_openended_0_0
        folder_name = folder_path.name
        return folder_name
    
    def extract_metadata_from_path(self, folder_path: Path) -> Dict[str, Any]:
        """Extract metadata from folder path"""
        folder_name = folder_path.name
        
        # Parse the folder name to extract metadata
        # Format: timestamp_agent_type_model_dataset_task_id
        parts = folder_name.split('_')
        
        metadata = {
            "folder_name": folder_name,
            "timestamp": None,
            "agent_type": None,
            "model": None,
            "dataset": None,
            "task_id": None
        }
        
        if len(parts) >= 6:
            # Extract timestamp
            if len(parts[0]) == 10 and parts[0].count('-') == 2:  # YYYY-MM-DD
                metadata["timestamp"] = f"{parts[0]}_{parts[1]}_{parts[2]}"
                remaining_parts = parts[3:]
            else:
                remaining_parts = parts
            
            # Extract task ID (last part)
            if remaining_parts:
                metadata["task_id"] = remaining_parts[-1]
                remaining_parts = remaining_parts[:-1]
            
            # Extract dataset (second to last part)
            if len(remaining_parts) >= 2:
                metadata["dataset"] = remaining_parts[-2]
                remaining_parts = remaining_parts[:-2]
            
            # Extract model (remaining parts)
            if remaining_parts:
                metadata["model"] = "_".join(remaining_parts)
        
        return metadata
    
    def migrate_instances(self):
        """Migrate WebVoyager instances from file system"""
        logger.info("Starting WebVoyager instance migration...")
        
        if not self.dataset_path.exists():
            logger.error(f"WebVoyager dataset path does not exist: {self.dataset_path}")
            return
        
        # Get all experiment folders
        experiment_folders = [f for f in self.dataset_path.iterdir() if f.is_dir() and f.name.startswith('2025-')]
        logger.info(f"Found {len(experiment_folders)} WebVoyager experiment folders")
        
        migrated_count = 0
        
        for folder_path in experiment_folders:
            try:
                instance_id = self.parse_instance_id_from_path(folder_path)
                metadata = self.extract_metadata_from_path(folder_path)
                
                # Read summary_info.json if it exists
                summary_info = None
                summary_file = folder_path / "summary_info.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r') as f:
                            summary_info = json.load(f)
                    except Exception as e:
                        logger.warning(f"Error reading summary_info.json for {instance_id}: {e}")
                
                # Parse timestamp from folder name
                timestamp = None
                if metadata["timestamp"]:
                    try:
                        timestamp = datetime.strptime(metadata["timestamp"], "%Y-%m-%d_%H-%M-%S")
                    except:
                        pass
                
                # Insert instance
                self.cursor.execute("""
                    INSERT INTO webvoyager_instances 
                    (instance_id, timestamp, scenario, experiment_tag, source_model, models, rewards, label, metadata, summary_info)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (instance_id) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    scenario = EXCLUDED.scenario,
                    experiment_tag = EXCLUDED.experiment_tag,
                    source_model = EXCLUDED.source_model,
                    models = EXCLUDED.models,
                    rewards = EXCLUDED.rewards,
                    label = EXCLUDED.label,
                    metadata = EXCLUDED.metadata,
                    summary_info = EXCLUDED.summary_info
                """, (
                    instance_id,
                    timestamp,
                    metadata.get("dataset", ""),
                    metadata.get("task_id"),
                    metadata.get("model"),
                    None,  # models
                    None,  # rewards
                    "WebVoyager Experiment",
                    json.dumps(metadata),
                    json.dumps(summary_info) if summary_info else None
                ))
                
                # Insert default agent (WebVoyager typically has one agent per experiment)
                self.cursor.execute("""
                    INSERT INTO webvoyager_agents 
                    (instance_id, agent_id, agent_type, capabilities, parameters, background, additional_info)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (instance_id, agent_id) DO UPDATE SET
                    agent_type = EXCLUDED.agent_type,
                    capabilities = EXCLUDED.capabilities,
                    parameters = EXCLUDED.parameters,
                    background = EXCLUDED.background,
                    additional_info = EXCLUDED.additional_info
                """, (
                    instance_id,
                    "agent",
                    metadata.get("agent_type", "GenericAgent"),
                    json.dumps({}),
                    json.dumps({}),
                    "",
                    None
                ))
                
                migrated_count += 1
                if migrated_count % 10 == 0:
                    logger.info(f"Migrated {migrated_count} WebVoyager instances...")
                    
            except Exception as e:
                logger.error(f"Error migrating WebVoyager instance {folder_path.name}: {e}")
                continue
        
        logger.info(f"Completed WebVoyager instance migration. Migrated {migrated_count} instances.")
    
    def migrate_experiment_logs(self):
        """Migrate experiment logs"""
        logger.info("Starting WebVoyager experiment log migration...")
        
        experiment_folders = [f for f in self.dataset_path.iterdir() if f.is_dir() and f.name.startswith('2025-')]
        migrated_logs = 0
        
        for folder_path in experiment_folders:
            try:
                instance_id = self.parse_instance_id_from_path(folder_path)
                log_file = folder_path / "experiment.log"
                
                if log_file.exists():
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read()
                        
                        self.cursor.execute("""
                            INSERT INTO webvoyager_experiment_logs 
                            (instance_id, log_content)
                            VALUES (%s, %s)
                            ON CONFLICT (instance_id) DO UPDATE SET
                            log_content = EXCLUDED.log_content
                        """, (
                            instance_id,
                            log_content
                        ))
                        
                        migrated_logs += 1
                        
                    except Exception as e:
                        logger.error(f"Error reading log file for {instance_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing experiment log for {folder_path.name}: {e}")
                continue
        
        logger.info(f"Completed WebVoyager experiment log migration. Migrated {migrated_logs} logs.")
    
    def migrate_screenshots(self):
        """Migrate screenshots"""
        logger.info("Starting WebVoyager screenshot migration...")
        
        experiment_folders = [f for f in self.dataset_path.iterdir() if f.is_dir() and f.name.startswith('2025-')]
        migrated_screenshots = 0
        
        for folder_path in experiment_folders:
            try:
                instance_id = self.parse_instance_id_from_path(folder_path)
                
                # Find all screenshot files
                screenshot_files = list(folder_path.glob("screenshot_step_*.png"))
                
                for screenshot_file in screenshot_files:
                    try:
                        # Extract step number from filename
                        step_match = re.search(r'screenshot_step_(\d+)\.png', screenshot_file.name)
                        if not step_match:
                            continue
                        
                        step_number = int(step_match.group(1))
                        
                        # Read screenshot data
                        with open(screenshot_file, 'rb') as f:
                            screenshot_data = f.read()
                        
                        self.cursor.execute("""
                            INSERT INTO webvoyager_screenshots 
                            (instance_id, step_number, screenshot_data, file_size)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (instance_id, step_number) DO UPDATE SET
                            screenshot_data = EXCLUDED.screenshot_data,
                            file_size = EXCLUDED.file_size
                        """, (
                            instance_id,
                            step_number,
                            screenshot_data,
                            len(screenshot_data)
                        ))
                        
                        migrated_screenshots += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing screenshot {screenshot_file} for {instance_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing screenshots for {folder_path.name}: {e}")
                continue
        
        logger.info(f"Completed WebVoyager screenshot migration. Migrated {migrated_screenshots} screenshots.")
    
    def migrate_step_files(self):
        """Migrate step files (pickle data)"""
        logger.info("Starting WebVoyager step file migration...")
        
        experiment_folders = [f for f in self.dataset_path.iterdir() if f.is_dir() and f.name.startswith('2025-')]
        migrated_steps = 0
        
        for folder_path in experiment_folders:
            try:
                instance_id = self.parse_instance_id_from_path(folder_path)
                
                # Find all step files
                step_files = list(folder_path.glob("step_*.pkl.gz"))
                
                for step_file in step_files:
                    try:
                        # Extract step number from filename
                        step_match = re.search(r'step_(\d+)\.pkl\.gz', step_file.name)
                        if not step_match:
                            continue
                        
                        step_number = int(step_match.group(1))
                        
                        # Read and parse pickle data
                        try:
                            with gzip.open(step_file, 'rb') as f:
                                step_data = f.read()  # Read raw compressed data
                            
                        except Exception as e:
                            logger.warning(f"Error reading pickle file {step_file} for {instance_id}: {e}")
                            step_data = b""  # Empty bytes if failed
                        
                        self.cursor.execute("""
                            INSERT INTO webvoyager_step_files 
                            (instance_id, step_number, step_data, file_size)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (instance_id, step_number) DO UPDATE SET
                            step_data = EXCLUDED.step_data,
                            file_size = EXCLUDED.file_size
                        """, (
                            instance_id,
                            step_number,
                            step_data,  # Store raw bytes
                            step_file.stat().st_size
                        ))
                        
                        migrated_steps += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing step file {step_file} for {instance_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing step files for {folder_path.name}: {e}")
                continue
        
        logger.info(f"Completed WebVoyager step file migration. Migrated {migrated_steps} step files.")
    
    def migrate_trajectory_points(self):
        """Migrate trajectory points from experiment logs"""
        logger.info("Starting WebVoyager trajectory point migration...")
        
        # Get all experiment logs
        self.cursor.execute("SELECT instance_id, log_content FROM webvoyager_experiment_logs")
        logs = self.cursor.fetchall()
        
        migrated_points = 0
        
        for instance_id, log_content in logs:
            try:
                # Parse log content to extract actions
                actions = self.parse_actions_from_log(log_content)
                
                for i, action in enumerate(actions):
                    try:
                        self.cursor.execute("""
                            INSERT INTO webvoyager_trajectory_points 
                            (instance_id, agent_id, timestamp, point_type, media_type, data_content, data_text, point_index, step_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (instance_id, agent_id, step_number, point_type) DO UPDATE SET
                            timestamp = EXCLUDED.timestamp,
                            data_content = EXCLUDED.data_content,
                            data_text = EXCLUDED.data_text,
                            point_index = EXCLUDED.point_index
                        """, (
                            instance_id,
                            "agent",
                            datetime.now(),  # Use current time as approximation
                            "action",
                            "text/plain",
                            json.dumps({"action": action}),
                            action,
                            i,
                            i + 1  # step_number
                        ))
                        
                        migrated_points += 1
                        
                    except Exception as e:
                        logger.error(f"Error inserting trajectory point for {instance_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing trajectory for {instance_id}: {e}")
                continue
        
        logger.info(f"Completed WebVoyager trajectory point migration. Migrated {migrated_points} points.")
    
    def parse_actions_from_log(self, log_content: str) -> List[str]:
        """Parse actions from experiment log content"""
        actions = []
        lines = log_content.split('\n')
        
        for line in lines:
            if 'action:' in line:
                # Extract action after "action:"
                action_match = re.search(r'action:\s*(.+)', line)
                if action_match:
                    action = action_match.group(1).strip()
                    actions.append(action)
        
        return actions
    
    def migrate_metrics(self):
        """Migrate metrics from metrics files"""
        logger.info("Starting WebVoyager metrics migration...")
        
        if not self.metrics_path.exists():
            logger.warning(f"WebVoyager metrics path does not exist: {self.metrics_path}")
            return
        
        # Find metrics directories
        metrics_dirs = [d for d in self.metrics_path.iterdir() if d.is_dir()]
        
        migrated_metrics = 0
        
        for metrics_dir in metrics_dirs:
            try:
                # Look for individual metric files
                metric_files = list(metrics_dir.glob("*.json"))
                
                for metric_file in metric_files:
                    try:
                        with open(metric_file, 'r') as f:
                            metric_data = json.load(f)
                        
                        # Extract instance_id from metric data
                        instance_id = metric_data.get("instance_id")
                        if not instance_id:
                            continue
                        
                        # Extract metric name from filename
                        metric_name = metric_file.stem
                        
                        # Extract metric value and reasoning
                        metric_value = metric_data.get("score", 0.0)
                        reasoning = metric_data.get("reasoning", "")
                        
                        self.cursor.execute("""
                            INSERT INTO webvoyager_metrics 
                            (instance_id, agent_id, metric_name, metric_value, reasoning)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (instance_id, agent_id, metric_name) DO UPDATE SET
                            metric_value = EXCLUDED.metric_value,
                            reasoning = EXCLUDED.reasoning
                        """, (
                            instance_id,
                            "agent",
                            metric_name,
                            float(metric_value),
                            reasoning
                        ))
                        
                        migrated_metrics += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing metric file {metric_file}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing metrics directory {metrics_dir}: {e}")
                continue
        
        logger.info(f"Completed WebVoyager metrics migration. Migrated {migrated_metrics} metrics.")
    
    def run_migration(self):
        """Run the complete WebVoyager migration"""
        logger.info("Starting WebVoyager data migration to autolibra database...")
        
        try:
            self.validate_db_config()
            self.connect_to_db()
            self.create_tables()
            self.migrate_instances()
            self.migrate_experiment_logs()
            self.migrate_screenshots()
            self.migrate_step_files()
            self.migrate_trajectory_points()
            self.migrate_metrics()
            logger.info("WebVoyager migration completed successfully!")
            
        except Exception as e:
            logger.error(f"WebVoyager migration failed: {e}")
            raise
        finally:
            self.close_db()

def main():
    """Main function to run WebVoyager migration"""
    migration = WebVoyagerMigration()
    migration.run_migration()

if __name__ == "__main__":
    main() 