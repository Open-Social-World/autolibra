import os
import json
import sys
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

sys.path.append(str(Path(__file__).parent.parent.parent / "packages"))

from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType, MediaType
from osw_data.annotation import AnnotationSystem

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Dataset configurations
DATASET_CONFIGS = {
    "sotopia": {
        "dataset_path": Path(__file__).parent.parent / ".data" / "sotopia",
        "annotation_path": Path(__file__).parent.parent / ".data" / "annotations" / "sotopia",
        "metrics_file": Path(__file__).parent.parent / ".data" / "metrics" / "sotopia" / "8_metrics" / "llm_eval_results.jsonl",
        "table_prefix": "sotopia",
        "metadata_fields": {
            "scenario_field": "scenario",
            "experiment_tag_field": "experiment_tag",
            "models_field": "models",
            "rewards_field": "rewards",
            "source_model_field": None
        }
    },
    "webarena": {
        "dataset_path": Path(__file__).parent.parent / ".data" / "webarena",
        "annotation_path": Path(__file__).parent.parent / ".data" / "annotations" / "webarena",
        "metrics_file": Path(__file__).parent.parent / ".data" / "metrics" / "webarena" / "8_metrics" / "llm_eval_results.jsonl",
        "table_prefix": "webarena",
        "metadata_fields": {
            "scenario_field": "task",
            "experiment_tag_field": None,
            "models_field": None,
            "rewards_field": None,
            "source_model_field": "source_model"
        }
    }
}

class UnifiedMigration:
    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.config = DATASET_CONFIGS[dataset_name]
        self.conn = None
        self.cursor = None
        
    def validate_db_config(self):
        """Validate that all required database environment variables are set"""
        required_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required database environment variables: {', '.join(missing_vars)}")
        
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
        """Create tables for the dataset"""
        table_prefix = self.config["table_prefix"]
        logger.info(f"Creating {self.dataset_name} database tables...")
        
        # Table for instances
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_prefix}_instances (
                instance_id VARCHAR(255) PRIMARY KEY,
                timestamp TIMESTAMP,
                scenario TEXT,
                experiment_tag VARCHAR(255),
                source_model VARCHAR(255),
                models JSONB,
                rewards JSONB,
                label VARCHAR(500),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table for agents
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_prefix}_agents (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES {table_prefix}_instances(instance_id) ON DELETE CASCADE,
                agent_id VARCHAR(255) NOT NULL,
                agent_type VARCHAR(100),
                capabilities JSONB,
                parameters JSONB,
                background TEXT,
                additional_info JSONB,
                UNIQUE(instance_id, agent_id)
            )
        """)
        
        # Table for trajectory points
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_prefix}_trajectory_points (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES {table_prefix}_instances(instance_id) ON DELETE CASCADE,
                agent_id VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                point_type VARCHAR(50) NOT NULL,
                media_type VARCHAR(50),
                data_content JSONB,
                data_text TEXT,
                metadata JSONB,
                point_index INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id, agent_id, timestamp, point_type, point_index, data_text)
            )
        """)
        
        # Table for annotations
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_prefix}_annotations (
                id SERIAL PRIMARY KEY,
                annotation_id VARCHAR(255) UNIQUE NOT NULL,
                instance_id VARCHAR(255) REFERENCES {table_prefix}_instances(instance_id) ON DELETE CASCADE,
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
        
        # Table for metrics
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_prefix}_metrics (
                id SERIAL PRIMARY KEY,
                instance_id VARCHAR(255) REFERENCES {table_prefix}_instances(instance_id) ON DELETE CASCADE,
                agent_id VARCHAR(255) NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value FLOAT,
                reasoning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instance_id, agent_id, metric_name)
            )
        """)
        
        # Create indexes for better performance
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_agents_instance ON {table_prefix}_agents(instance_id)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_trajectory_instance ON {table_prefix}_trajectory_points(instance_id)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_trajectory_agent ON {table_prefix}_trajectory_points(agent_id)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_trajectory_timestamp ON {table_prefix}_trajectory_points(timestamp)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_annotations_instance ON {table_prefix}_annotations(instance_id)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_annotations_agent ON {table_prefix}_annotations(agent_id)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_metrics_instance ON {table_prefix}_metrics(instance_id)")
        self.cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_prefix}_metrics_agent ON {table_prefix}_metrics(agent_id)")
        
        logger.info(f"{self.dataset_name} tables created successfully")
    
    def migrate_instances_and_agents(self):
        """Migrate instance metadata and agent information"""
        logger.info(f"Starting {self.dataset_name} instance and agent migration...")
        
        dataset_path = self.config["dataset_path"]
        if not dataset_path.exists():
            logger.error(f"{self.dataset_name} dataset path does not exist: {dataset_path}")
            return
        
        labels = {}
        labels_path = dataset_path / "instance_labels.json"
        if labels_path.exists():
            try:
                with open(labels_path, "r") as f:
                    labels = json.load(f)
                logger.info(f"Loaded {len(labels)} {self.dataset_name} instance labels")
            except Exception as e:
                logger.error(f"Error loading labels: {e}")
        
        try:
            dataset = MultiAgentDataset(name=self.dataset_name, base_path=dataset_path)
            instances = dataset.list_instances()
            logger.info(f"Found {len(instances)} {self.dataset_name} instances to migrate")
        except Exception as e:
            logger.error(f"Error initializing {self.dataset_name} dataset: {e}")
            return
        
        migrated_count = 0
        table_prefix = self.config["table_prefix"]
        metadata_fields = self.config["metadata_fields"]
        
        for instance_id in instances:
            try:
                # Get instance metadata
                metadata = dataset.get_instance_metadata(instance_id)
                
                # Extract fields based on dataset configuration
                scenario = ""
                experiment_tag = None
                source_model = None
                models = None
                rewards = None
                
                if metadata.metadata and isinstance(metadata.metadata, dict):
                    if metadata_fields["scenario_field"]:
                        scenario = metadata.metadata.get(metadata_fields["scenario_field"], "")
                        scenario = re.sub(r'<.*?>', '', scenario)
                        scenario = scenario.strip()
                    
                    if metadata_fields["experiment_tag_field"]:
                        experiment_tag = metadata.metadata.get(metadata_fields["experiment_tag_field"])
                    
                    if metadata_fields["source_model_field"]:
                        source_model = metadata.metadata.get(metadata_fields["source_model_field"])
                    
                    if metadata_fields["models_field"]:
                        models = metadata.metadata.get(metadata_fields["models_field"])
                    
                    if metadata_fields["rewards_field"]:
                        rewards = metadata.metadata.get(metadata_fields["rewards_field"])

                label = labels.get(instance_id, "Unlabeled")
                
                self.cursor.execute(f"""
                    INSERT INTO {table_prefix}_instances 
                    (instance_id, timestamp, scenario, experiment_tag, source_model, models, rewards, label, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (instance_id) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    scenario = EXCLUDED.scenario,
                    experiment_tag = EXCLUDED.experiment_tag,
                    source_model = EXCLUDED.source_model,
                    models = EXCLUDED.models,
                    rewards = EXCLUDED.rewards,
                    label = EXCLUDED.label,
                    metadata = EXCLUDED.metadata
                """, (
                    instance_id,
                    metadata.timestamp,
                    scenario,
                    experiment_tag,
                    source_model,
                    json.dumps(models) if models else None,
                    json.dumps(rewards) if rewards else None,
                    label,
                    json.dumps(metadata.metadata) if metadata.metadata else None
                ))
                
                # Insert agents
                for agent_id, agent_data in metadata.agents.items():
                    background = ""
                    additional_info = None
                    
                    if hasattr(agent_data, "parameters") and isinstance(agent_data.parameters, dict):
                        background = agent_data.parameters.get("background", "")
                    
                    if hasattr(agent_data, "additional_info") and agent_data.additional_info:
                        additional_info = agent_data.additional_info
                    
                    self.cursor.execute(f"""
                        INSERT INTO {table_prefix}_agents 
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
                        agent_id,
                        agent_data.agent_type,
                        json.dumps(agent_data.capabilities),
                        json.dumps(agent_data.parameters) if agent_data.parameters else None,
                        background,
                        json.dumps(additional_info) if additional_info else None
                    ))
                
                migrated_count += 1
                if migrated_count % 100 == 0:
                    logger.info(f"Migrated {migrated_count} {self.dataset_name} instances...")
                    
            except Exception as e:
                logger.error(f"Error migrating {self.dataset_name} instance {instance_id}: {e}")
                continue
        
        logger.info(f"Completed {self.dataset_name} instance and agent migration. Migrated {migrated_count} instances.")
    
    def migrate_trajectories(self):
        """Migrate trajectory data"""
        logger.info(f"Starting {self.dataset_name} trajectory migration...")
        
        dataset_path = self.config["dataset_path"]
        table_prefix = self.config["table_prefix"]
        
        try:
            dataset = MultiAgentDataset(name=self.dataset_name, base_path=dataset_path)
            instances = dataset.list_instances()
        except Exception as e:
            logger.error(f"Error initializing {self.dataset_name} dataset for trajectory migration: {e}")
            return
        
        migrated_points = 0
        for instance_id in instances:
            try:
                metadata = dataset.get_instance_metadata(instance_id)
                
                for agent_id in metadata.agents:
                    try:
                        trajectory = dataset.get_trajectory(instance_id, agent_id)
                        
                        # Sort trajectory points by timestamp
                        trajectory_points = [
                            (idx, point, trajectory.get_data_at(idx))
                            for idx, point in enumerate(trajectory.points)
                        ]
                        trajectory_points.sort(key=lambda x: x[1].timestamp)
                        
                        for point_index, point, data in trajectory_points:
                            try:
                                # Extract data content
                                data_content = None
                                data_text = None
                                
                                if isinstance(data, dict):
                                    data_content = data
                                    # Extract text content if available
                                    if "content" in data:
                                        data_text = str(data["content"])
                                elif isinstance(data, str):
                                    data_text = data
                                else:
                                    # Try to convert to string
                                    data_text = str(data)
                                
                                # Insert trajectory point
                                self.cursor.execute(f"""
                                    INSERT INTO {table_prefix}_trajectory_points 
                                    (instance_id, agent_id, timestamp, point_type, media_type, 
                                     data_content, data_text, metadata, point_index)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (instance_id, agent_id, timestamp, point_type, point_index, data_text) 
                                    DO UPDATE SET
                                    media_type = EXCLUDED.media_type,
                                    data_content = EXCLUDED.data_content,
                                    metadata = EXCLUDED.metadata
                                """, (
                                    instance_id,
                                    agent_id,
                                    point.timestamp,
                                    point.point_type.value,
                                    point.data_reference.media_type.value if point.data_reference else None,
                                    json.dumps(data_content) if data_content else None,
                                    data_text,
                                    json.dumps(point.metadata) if point.metadata else None,
                                    point_index
                                ))
                                
                                migrated_points += 1
                                
                            except Exception as e:
                                logger.error(f"Error migrating trajectory point {point_index} for {self.dataset_name} instance {instance_id}, agent {agent_id}: {e}")
                                continue
                                
                    except Exception as e:
                        logger.error(f"Error migrating trajectory for {self.dataset_name} instance {instance_id}, agent {agent_id}: {e}")
                        continue
                
                if migrated_points % 1000 == 0:
                    logger.info(f"Migrated {migrated_points} {self.dataset_name} trajectory points...")
                    
            except Exception as e:
                logger.error(f"Error processing {self.dataset_name} instance {instance_id} for trajectory migration: {e}")
                continue
        
        logger.info(f"Completed {self.dataset_name} trajectory migration. Migrated {migrated_points} trajectory points.")
    
    def migrate_annotations(self):
        """Migrate annotation data"""
        logger.info(f"Starting {self.dataset_name} annotation migration...")
        
        annotation_path = self.config["annotation_path"]
        table_prefix = self.config["table_prefix"]
        
        if not annotation_path.exists():
            logger.warning(f"{self.dataset_name} annotation path does not exist: {annotation_path}")
            return
        
        try:
            annotation_system = AnnotationSystem(base_path=annotation_path)
        except Exception as e:
            logger.error(f"Error initializing {self.dataset_name} annotation system: {e}")
            return
        
        migrated_annotations = 0
        
        # Get all annotation files
        annotation_files = list(annotation_path.glob("annotations/*.json"))
        logger.info(f"Found {len(annotation_files)} {self.dataset_name} annotation files")
        
        for annotation_file in annotation_files:
            try:
                # Parse instance_id and agent_id from filename
                filename = annotation_file.stem  # Remove .json extension
                if "_" in filename:
                    parts = filename.split("_", 1)
                    if len(parts) == 2:
                        instance_id, agent_id = parts
                    else:
                        logger.warning(f"Unexpected {self.dataset_name} annotation filename format: {filename}")
                        continue
                else:
                    logger.warning(f"Unexpected {self.dataset_name} annotation filename format: {filename}")
                    continue
                
                # Load annotations
                with open(annotation_file, "r") as f:
                    trajectory_annotations = json.load(f)
                
                # Insert annotations
                for annotation_data in trajectory_annotations.get("annotations", []):
                    try:
                        # Handle span data
                        span_data = annotation_data.get("span")
                        start_time = None
                        end_time = None
                        
                        if span_data:
                            start_time = datetime.fromisoformat(span_data["start_time"])
                            if span_data.get("end_time"):
                                end_time = datetime.fromisoformat(span_data["end_time"])
                        
                        self.cursor.execute(f"""
                            INSERT INTO {table_prefix}_annotations 
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
                            annotation_data["annotation_id"],
                            instance_id,
                            agent_id,
                            annotation_data["annotator_id"],
                            datetime.fromisoformat(annotation_data["created_at"]),
                            datetime.fromisoformat(annotation_data["updated_at"]),
                            json.dumps(annotation_data["content"]),
                            start_time,
                            end_time,
                            annotation_data.get("confidence"),
                            json.dumps(annotation_data.get("metadata", {}))
                        ))
                        
                        migrated_annotations += 1
                        
                    except Exception as e:
                        logger.error(f"Error migrating {self.dataset_name} annotation {annotation_data.get('annotation_id', 'unknown')}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing {self.dataset_name} annotation file {annotation_file}: {e}")
                continue
        
        logger.info(f"Completed {self.dataset_name} annotation migration. Migrated {migrated_annotations} annotations.")
    
    def migrate_metrics(self):
        """Migrate metrics data"""
        logger.info(f"Starting {self.dataset_name} metrics migration...")
        
        metrics_file = self.config["metrics_file"]
        table_prefix = self.config["table_prefix"]
        
        if not metrics_file.exists():
            logger.warning(f"{self.dataset_name} metrics file does not exist: {metrics_file}")
            return
        
        migrated_metrics = 0
        
        try:
            with open(metrics_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        metric_data = json.loads(line)
                        instance_id = metric_data.get("instance_id")
                        agent_id = metric_data.get("agent_id")
                        
                        if not instance_id or not agent_id:
                            logger.warning(f"Skipping line {line_num}: missing instance_id or agent_id")
                            continue
                        
                        # Extract metrics and reasoning
                        for key, value in metric_data.items():
                            if key in ["instance_id", "agent_id"]:
                                continue
                            
                            if isinstance(value, (int, float)):
                                # This is a metric value
                                reasoning = metric_data.get(f"{key}_reasoning")
                                
                                self.cursor.execute(f"""
                                    INSERT INTO {table_prefix}_metrics 
                                    (instance_id, agent_id, metric_name, metric_value, reasoning)
                                    VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (instance_id, agent_id, metric_name) DO UPDATE SET
                                    metric_value = EXCLUDED.metric_value,
                                    reasoning = EXCLUDED.reasoning
                                """, (
                                    instance_id,
                                    agent_id,
                                    key,
                                    float(value),
                                    reasoning
                                ))
                                
                                migrated_metrics += 1
                        
                        if migrated_metrics % 1000 == 0:
                            logger.info(f"Migrated {migrated_metrics} {self.dataset_name} metrics...")
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON on line {line_num}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing {self.dataset_name} metrics on line {line_num}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error reading {self.dataset_name} metrics file: {e}")
            return
        
        logger.info(f"Completed {self.dataset_name} metrics migration. Migrated {migrated_metrics} metrics.")
    
    def run_migration(self):
        """Run the complete migration for the dataset"""
        logger.info(f"Starting {self.dataset_name} data migration to PostgreSQL...")
        
        try:
            self.validate_db_config()
            self.connect_to_db()
            self.create_tables()
            self.migrate_instances_and_agents()
            self.migrate_trajectories()
            self.migrate_annotations()
            self.migrate_metrics()
            logger.info(f"{self.dataset_name} migration completed successfully!")
            
        except Exception as e:
            logger.error(f"{self.dataset_name} migration failed: {e}")
            raise
        finally:
            self.close_db()

def main():
    """Main function to run migrations"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified migration script for Sotopia and WebArena datasets")
    parser.add_argument("dataset", choices=["sotopia", "webarena"], help="Dataset to migrate")
    parser.add_argument("--all", action="store_true", help="Migrate all datasets")
    
    args = parser.parse_args()
    
    if args.all:
        datasets = ["sotopia", "webarena"]
    else:
        datasets = [args.dataset]
    
    for dataset_name in datasets:
        logger.info(f"Starting migration for {dataset_name}...")
        migration = UnifiedMigration(dataset_name)
        migration.run_migration()
        logger.info(f"Completed migration for {dataset_name}")

if __name__ == "__main__":
    main() 