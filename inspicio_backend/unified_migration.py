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
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None
        
    def validate_db_config(self) -> None:
        """Validate that all required database environment variables are set"""
        required_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required database environment variables: {', '.join(missing_vars)}")
        
        logger.info("Database configuration validation passed")
        
    def connect_to_db(self) -> None:
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            if self.conn is not None:
                self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                self.cursor = self.conn.cursor()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def close_db(self) -> None:
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def create_tables(self) -> None:
        """Create tables for the dataset"""
        table_prefix = self.config["table_prefix"]
        logger.info(f"Creating {self.dataset_name} database tables...")
        
        if self.cursor is None:
            raise RuntimeError("Database cursor is not initialized")
        
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
    
    def migrate_instances_and_agents(self) -> None:
        """Migrate instance metadata and agent information"""
        logger.info(f"Starting {self.dataset_name} instance and agent migration...")
        
        dataset_path = self.config["dataset_path"]
        if not dataset_path.exists():
            logger.error(f"Dataset path {dataset_path} does not exist")
            return
        
        # Implementation of migrate_instances_and_agents method
        # This method should be implemented to migrate instance metadata and agent information
        # from the dataset to the database
        # ...