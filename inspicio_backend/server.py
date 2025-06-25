from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import sys
from contextlib import asynccontextmanager
import re
import logging
from pydantic import BaseModel
from datetime import datetime
import os
from typing import List, Dict, Optional, Any
import psycopg2
import psycopg2.extras 
import uvicorn
import os
from dotenv import load_dotenv
load_dotenv()

from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnnotationPayload(BaseModel):
    dataset: str  
    instance_id: str
    agent_id: str
    annotator_id: str
    comment_text: str
    selection_text: str
    start_offset: int
    end_offset: int

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Function to get database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def save_annotation_to_db(dataset: str, annotation_id: str, instance_id: str, agent_id: str, 
                         annotator_id: str, content: dict, created_at: datetime, 
                         updated_at: datetime, start_time: datetime = None, 
                         end_time: datetime = None, confidence: float = None, 
                         metadata: dict = None):
    """Save annotation to the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise Exception("Database connection not available")
    
    # Validate dataset
    supported_datasets = ["sotopia", "webarena", "webvoyager"]
    if dataset not in supported_datasets:
        raise Exception(f"Unsupported dataset: {dataset}. Supported datasets: {supported_datasets}")
    
    try:
        cursor = db_conn.cursor()
        table_name = f"{dataset}_annotations"
        
        # Ensure the annotation table exists
        cursor.execute(f"""
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
        
        # Create indexes if they don't exist
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_instance ON {table_name}(instance_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_agent ON {table_name}(agent_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_annotator ON {table_name}(annotator_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{dataset}_annotations_annotation_id ON {table_name}(annotation_id)")
        
        # Insert the annotation
        cursor.execute(f"""
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
        
        db_conn.commit()
        cursor.close()
        logger.info(f"Annotation {annotation_id} saved to database for dataset {dataset}")
        
    except Exception as e:
        logger.error(f"Error saving annotation to database: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise Exception(f"Failed to save annotation to database: {str(e)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database connection
    global db_conn
    
    # Initialize database connection
    try:
        db_conn = get_db_connection()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}", exc_info=True)
        db_conn = None

    yield
    
    # Shutdown: Clean up resources
    if db_conn:
        db_conn.close()
        logger.info("Database connection closed")

app = FastAPI(title="Conversation Dataset API", lifespan=lifespan)

# Configure CORS to allow requests from frontend
# Make sure your frontend URL is allowed, or use "*" for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "https://*.railway.app",  # Allow Railway domains
        "*"  # Allow all origins for development - remove in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Trajectory Dataset API is running"}


# --- NEW ANNOTATION ENDPOINT ---
@app.post("/annotations")
async def create_annotation(payload: AnnotationPayload):
    """Receive and save a new annotation to the database."""
    logger.info(f"Received annotation payload: {payload.dict()}")

    # Validate dataset
    supported_datasets = ["sotopia", "webarena", "webvoyager"]
    if payload.dataset not in supported_datasets:
        logger.error(f"Unsupported dataset: {payload.dataset}")
        raise HTTPException(status_code=400, detail=f"Unsupported dataset: {payload.dataset}. Supported datasets: {supported_datasets}")

    try:
        # Prepare the content based on the schema
        annotation_content = {
            "comment": {
                "comment_text": payload.comment_text,
                "selection_text": payload.selection_text,
                "start_offset": payload.start_offset,
                "end_offset": payload.end_offset,
            }
        }

        # Generate a unique annotation ID
        current_time = datetime.now()
        annotation_id = f"{payload.dataset}_{payload.instance_id}_{payload.agent_id}_{payload.annotator_id}_{current_time.strftime('%Y%m%d_%H%M%S_%f')}"

        # Save the annotation to the database
        save_annotation_to_db(
            dataset=payload.dataset,
            annotation_id=annotation_id,
            instance_id=payload.instance_id,
            agent_id=payload.agent_id,
            annotator_id=payload.annotator_id,
            content=annotation_content,
            created_at=current_time,
            updated_at=current_time,
            start_time=current_time,  # Use current time as point annotation
            end_time=current_time,    # Use current time as point annotation
            confidence=None,
            metadata={"source": "web_interface"}
        )

        logger.info(f"Annotation saved successfully to database for dataset {payload.dataset}, instance {payload.instance_id}, agent {payload.agent_id}")
        return {"message": "Annotation saved successfully", "annotation_id": annotation_id}

    except Exception as e:
        logger.error(f"Failed to save annotation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save annotation: {str(e)}")
# --- END NEW ANNOTATION ENDPOINT ---

# --- NEW ANNOTATION RETRIEVAL ENDPOINTS ---
@app.get("/annotations/{dataset}/{instance_id}/{agent_id}")
async def get_annotations(dataset: str, instance_id: str, agent_id: str):
    """Get annotations for a specific dataset, instance, and agent from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        table_name = f"{dataset}_annotations"
        
        cursor.execute(f"""
            SELECT annotation_id, annotator_id, created_at, updated_at, 
                   content, start_time, end_time, confidence, metadata
            FROM {table_name} 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY created_at DESC
        """, (instance_id, agent_id))
        
        results = cursor.fetchall()
        cursor.close()
        
        annotations = []
        for row in results:
            annotation_data = {
                'annotation_id': row['annotation_id'],
                'annotator_id': row['annotator_id'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                'content': row['content'] if isinstance(row['content'], dict) else {},
                'start_time': row['start_time'].isoformat() if row['start_time'] else None,
                'end_time': row['end_time'].isoformat() if row['end_time'] else None,
                'confidence': row['confidence'],
                'metadata': row['metadata'] if isinstance(row['metadata'], dict) else {}
            }
            annotations.append(annotation_data)
        
        return {
            "dataset": dataset,
            "instance_id": instance_id,
            "agent_id": agent_id,
            "annotations": annotations
        }
        
    except Exception as e:
        logger.error(f"Error querying annotations for dataset {dataset}, instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/annotations/{dataset}")
async def get_dataset_annotations(dataset: str):
    """Get all annotations for a specific dataset from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    # Validate dataset
    supported_datasets = ["sotopia", "webarena", "webvoyager"]
    if dataset not in supported_datasets:
        raise HTTPException(status_code=400, detail=f"Unsupported dataset: {dataset}. Supported datasets: {supported_datasets}")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        table_name = f"{dataset}_annotations"
        
        cursor.execute(f"""
            SELECT annotation_id, instance_id, agent_id, annotator_id, created_at, updated_at, 
                   content, start_time, end_time, confidence, metadata
            FROM {table_name} 
            ORDER BY created_at DESC
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        annotations = []
        for row in results:
            annotation_data = {
                'annotation_id': row['annotation_id'],
                'instance_id': row['instance_id'],
                'agent_id': row['agent_id'],
                'annotator_id': row['annotator_id'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                'content': row['content'] if isinstance(row['content'], dict) else {},
                'start_time': row['start_time'].isoformat() if row['start_time'] else None,
                'end_time': row['end_time'].isoformat() if row['end_time'] else None,
                'confidence': row['confidence'],
                'metadata': row['metadata'] if isinstance(row['metadata'], dict) else {}
            }
            annotations.append(annotation_data)
        
        return {
            "dataset": dataset,
            "annotations": annotations,
            "count": len(annotations)
        }
        
    except Exception as e:
        logger.error(f"Error querying annotations for dataset {dataset}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

# --- END NEW ANNOTATION RETRIEVAL ENDPOINTS ---

# --- NEW DATABASE-BACKED WEBARENA ENDPOINTS ---

@app.get("/webarena/instances")
def get_webarena_instances():
    """Get all WebArena instances from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT instance_id, timestamp, scenario, source_model, label, metadata, created_at
            FROM webarena_instances 
            ORDER BY timestamp DESC
        """)
        
        results = cursor.fetchall()
        instances = []
        
        for row in results:
            try:
                # Create a clean dictionary from the row data
                instance_data = {
                    'instance_id': row['instance_id'],
                    'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
                    'scenario': row['scenario'] or '',
                    'source_model': row['source_model'] or '',
                    'label': row['label'] or 'Unlabeled',
                    'metadata': row['metadata'] if isinstance(row['metadata'], dict) else {},
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                }
                
                instances.append(instance_data)
                
            except Exception as row_error:
                logger.error(f"Error processing row {row}: {row_error}")
                continue
        
        cursor.close()
        return instances
        
    except Exception as e:
        logger.error(f"Error querying WebArena instances: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/instances/{instance_id}")
def get_webarena_instance(instance_id: str):
    """Get details for a specific WebArena instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get instance data
        cursor.execute("""
            SELECT instance_id, timestamp, scenario, source_model, label, metadata, created_at
            FROM webarena_instances 
            WHERE instance_id = %s
        """, (instance_id,))
        
        instance_row = cursor.fetchone()
        if not instance_row:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        instance_data = dict(instance_row)
        
        # Convert datetime to string for JSON serialization
        if instance_data['timestamp']:
            instance_data['timestamp'] = instance_data['timestamp'].isoformat()
        if instance_data['created_at']:
            instance_data['created_at'] = instance_data['created_at'].isoformat()
        
        # Parse JSONB fields
        if instance_data['metadata'] is not None:
            # JSONB fields are already parsed as Python objects by psycopg2
            if not isinstance(instance_data['metadata'], dict):
                instance_data['metadata'] = {}
        else:
            instance_data['metadata'] = {}
        
        # Get agents for this instance
        cursor.execute("""
            SELECT agent_id, agent_type, capabilities, parameters, additional_info
            FROM webarena_agents 
            WHERE instance_id = %s
            ORDER BY agent_id
        """, (instance_id,))
        
        agents = []
        for agent_row in cursor.fetchall():
            agent_data = dict(agent_row)
            
            # Parse JSONB fields
            if agent_data['capabilities'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['capabilities'], dict):
                    agent_data['capabilities'] = {}
            else:
                agent_data['capabilities'] = {}
            
            if agent_data['parameters'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['parameters'], dict):
                    agent_data['parameters'] = {}
            else:
                agent_data['parameters'] = {}
            
            if agent_data['additional_info'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['additional_info'], dict):
                    agent_data['additional_info'] = {}
            else:
                agent_data['additional_info'] = {}
            
            agents.append(agent_data)
        
        instance_data['agents'] = agents
        cursor.close()
        
        return instance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebArena instance {instance_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/instances/{instance_id}/trajectory/{agent_id}")
def get_webarena_trajectory_db(instance_id: str, agent_id: str):
    """Get trajectory data for a specific agent in a WebArena instance from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get trajectory points
        cursor.execute("""
            SELECT timestamp, point_type, media_type, data_content, data_text, metadata, point_index
            FROM webarena_trajectory_points 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY timestamp, point_index
        """, (instance_id, agent_id))
        
        trajectory_points = []
        for row in cursor.fetchall():
            point_data = dict(row)
            
            # Convert datetime to string for JSON serialization
            if point_data['timestamp']:
                point_data['timestamp'] = point_data['timestamp'].isoformat()
            
            # Parse JSONB fields
            if point_data['data_content'] and isinstance(point_data['data_content'], str):
                try:
                    point_data['data_content'] = json.loads(point_data['data_content'])
                except:
                    pass
            
            if point_data['metadata'] and isinstance(point_data['metadata'], str):
                try:
                    point_data['metadata'] = json.loads(point_data['metadata'])
                except:
                    pass
            
            trajectory_points.append(point_data)
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "agent_id": agent_id,
            "trajectory_points": trajectory_points
        }
        
    except Exception as e:
        logger.error(f"Error querying WebArena trajectory for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/instances/{instance_id}/conversation")
def get_webarena_conversation(instance_id: str):
    """Get conversation data for a WebArena instance from the database (similar to the original /webarena/trajectories/{instance_id} endpoint)"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get instance data
        cursor.execute("""
            SELECT scenario FROM webarena_instances WHERE instance_id = %s
        """, (instance_id,))
        
        instance_row = cursor.fetchone()
        if not instance_row:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        scenario = instance_row['scenario'] or ""
        
        # Get conversation (trajectory points that are actions)
        cursor.execute("""
            SELECT agent_id, timestamp, data_content, data_text
            FROM webarena_trajectory_points 
            WHERE instance_id = %s AND point_type = 'action'
            ORDER BY timestamp
        """, (instance_id,))
        
        conversation = []
        for row in cursor.fetchall():
            content = ""
            
            # Try to get content from data_text first, then data_content
            if row['data_text']:
                content = row['data_text']
            elif row['data_content']:
                if isinstance(row['data_content'], str):
                    try:
                        data_content = json.loads(row['data_content'])
                        if isinstance(data_content, dict) and 'content' in data_content:
                            content = str(data_content['content'])
                        else:
                            content = str(data_content)
                    except:
                        content = str(row['data_content'])
                else:
                    if isinstance(row['data_content'], dict) and 'content' in row['data_content']:
                        content = str(row['data_content']['content'])
                    else:
                        content = str(row['data_content'])
            
            if content:
                conversation.append({
                    "agent_id": row['agent_id'],
                    "timestamp": row['timestamp'].isoformat(),
                    "content": content
                })
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "conversation": conversation,
            "scenario": scenario  
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebArena conversation for instance {instance_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/instances/{instance_id}/metrics/{agent_id}")
async def get_webarena_instance_agent_metrics_db(instance_id: str, agent_id: str):
    """Get metrics for a specific WebArena instance and agent from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT metric_name, metric_value, reasoning
            FROM webarena_metrics 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY metric_name
        """, (instance_id, agent_id))
        
        results = cursor.fetchall()
        cursor.close()
        
        if not results:
            raise HTTPException(status_code=404, detail="Metrics not found for this instance/agent combination")
        
        # Format the response to match the original API
        response_data = {
            "instance_id": instance_id,
            "agent_id": agent_id
        }
        
        for row in results:
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            reasoning = row['reasoning']
            
            response_data[metric_name] = metric_value
            if reasoning:
                response_data[f"{metric_name}_reasoning"] = reasoning
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebArena metrics for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/metrics/instances")
def get_webarena_metrics_by_instance():
    """Get a mapping of instance IDs to their available metrics from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT instance_id, agent_id, metric_name, metric_value, reasoning
            FROM webarena_metrics 
            ORDER BY instance_id, agent_id, metric_name
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        # Create a mapping of instance_id -> agent_id -> metrics
        instance_metrics = {}
        
        for row in results:
            instance_id = row['instance_id']
            agent_id = row['agent_id']
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            reasoning = row['reasoning']
            
            # Initialize the instance entry if it doesn't exist
            if instance_id not in instance_metrics:
                instance_metrics[instance_id] = {}
            
            # Initialize the agent entry if it doesn't exist
            if agent_id not in instance_metrics[instance_id]:
                instance_metrics[instance_id][agent_id] = {
                    "metrics": {},
                    "reasoning": {}
                }
            
            # Add metric and reasoning
            instance_metrics[instance_id][agent_id]["metrics"][metric_name] = metric_value
            if reasoning:
                instance_metrics[instance_id][agent_id]["reasoning"][metric_name] = reasoning
        
        return instance_metrics
        
    except Exception as e:
        logger.error(f"Error querying WebArena metrics by instance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

# --- END NEW DATABASE-BACKED WEBARENA ENDPOINTS ---

@app.get("/webvoyager/instances")
def get_webvoyager_instances():
    """Get all WebVoyager instances from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT instance_id, timestamp, scenario, experiment_tag, source_model, 
                   label, metadata, summary_info, created_at
            FROM webvoyager_instances 
            ORDER BY timestamp DESC
        """)
        
        results = cursor.fetchall()
        instances = []
        
        for row in results:
            try:
                # Create a clean dictionary from the row data
                instance_data = {
                    'instance_id': row['instance_id'],
                    'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
                    'scenario': row['scenario'] or '',
                    'experiment_tag': row['experiment_tag'] or '',
                    'source_model': row['source_model'] or '',
                    'label': row['label'] or 'Unlabeled',
                    'metadata': row['metadata'] if isinstance(row['metadata'], dict) else {},
                    'summary_info': row['summary_info'] if isinstance(row['summary_info'], dict) else {},
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                }
                
                instances.append(instance_data)
                
            except Exception as row_error:
                logger.error(f"Error processing row {row}: {row_error}")
                continue
        
        cursor.close()
        logger.info(f"Successfully retrieved {len(instances)} WebVoyager instances")
        return instances
        
    except Exception as e:
        logger.error(f"Error querying WebVoyager instances: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/instances/{instance_id}")
def get_webvoyager_instance(instance_id: str):
    """Get details for a specific WebVoyager instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get instance data
        cursor.execute("""
            SELECT instance_id, timestamp, scenario, experiment_tag, source_model, 
                   label, metadata, summary_info, created_at
            FROM webvoyager_instances 
            WHERE instance_id = %s
        """, (instance_id,))
        
        instance_row = cursor.fetchone()
        if not instance_row:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        # Create a clean dictionary from the row data
        instance_data = {
            'instance_id': instance_row['instance_id'],
            'timestamp': instance_row['timestamp'].isoformat() if instance_row['timestamp'] else None,
            'scenario': instance_row['scenario'] or '',
            'experiment_tag': instance_row['experiment_tag'] or '',
            'source_model': instance_row['source_model'] or '',
            'label': instance_row['label'] or 'Unlabeled',
            'metadata': instance_row['metadata'] if isinstance(instance_row['metadata'], dict) else {},
            'summary_info': instance_row['summary_info'] if isinstance(instance_row['summary_info'], dict) else {},
            'created_at': instance_row['created_at'].isoformat() if instance_row['created_at'] else None
        }
        
        # Get agents for this instance
        cursor.execute("""
            SELECT agent_id, agent_type, capabilities, parameters, background, additional_info
            FROM webvoyager_agents 
            WHERE instance_id = %s
            ORDER BY agent_id
        """, (instance_id,))
        
        agents = []
        for agent_row in cursor.fetchall():
            agent_data = dict(agent_row)
            
            # Parse JSONB fields
            if agent_data['capabilities'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['capabilities'], dict):
                    agent_data['capabilities'] = {}
            else:
                agent_data['capabilities'] = {}
            
            if agent_data['parameters'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['parameters'], dict):
                    agent_data['parameters'] = {}
            else:
                agent_data['parameters'] = {}
            
            if agent_data['additional_info'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['additional_info'], dict):
                    agent_data['additional_info'] = {}
            else:
                agent_data['additional_info'] = {}
            
            agents.append(agent_data)
        
        instance_data['agents'] = agents
        
        # Get experiment log
        cursor.execute("""
            SELECT log_content FROM webvoyager_experiment_logs 
            WHERE instance_id = %s
        """, (instance_id,))
        
        log_row = cursor.fetchone()
        log_content = log_row['log_content'] if log_row else None
        
        # Get screenshots
        cursor.execute("""
            SELECT step_number, screenshot_data, file_size, created_at
            FROM webvoyager_screenshots 
            WHERE instance_id = %s
            ORDER BY step_number
        """, (instance_id,))
        
        screenshots = []
        for screenshot_row in cursor.fetchall():
            # Create a clean dictionary from the screenshot row data (exclude binary data)
            screenshot_data = {
                'step_number': screenshot_row['step_number'],
                'file_size': screenshot_row['file_size'],
                'created_at': screenshot_row['created_at'].isoformat() if screenshot_row['created_at'] else None
            }
            screenshots.append(screenshot_data)
        
        # Get step files
        cursor.execute("""
            SELECT step_number, step_data, file_size, created_at
            FROM webvoyager_step_files 
            WHERE instance_id = %s
            ORDER BY step_number
        """, (instance_id,))
        
        step_files = []
        for step_row in cursor.fetchall():
            # Create a clean dictionary from the step row data (exclude binary data)
            step_data = {
                'step_number': step_row['step_number'],
                'file_size': step_row['file_size'],
                'created_at': step_row['created_at'].isoformat() if step_row['created_at'] else None
            }
            step_files.append(step_data)
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "instance_data": instance_data,
            "agents": agents,
            "log_content": log_content,
            "screenshots": screenshots,
            "step_files": step_files
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebVoyager instance {instance_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/instances/{instance_id}/trajectory/{agent_id}")
def get_webvoyager_trajectory(instance_id: str, agent_id: str):
    """Get trajectory data for a specific agent in a WebVoyager instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get trajectory points
        cursor.execute("""
            SELECT timestamp, point_type, media_type, data_content, data_text, metadata, point_index, step_number
            FROM webvoyager_trajectory_points 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY timestamp, point_index
        """, (instance_id, agent_id))
        
        trajectory_points = []
        for row in cursor.fetchall():
            point_data = dict(row)
            
            # Convert datetime to string for JSON serialization
            if point_data['timestamp']:
                point_data['timestamp'] = point_data['timestamp'].isoformat()
            
            # Parse JSONB fields
            if point_data['data_content'] and isinstance(point_data['data_content'], str):
                try:
                    point_data['data_content'] = json.loads(point_data['data_content'])
                except:
                    pass
            
            if point_data['metadata'] and isinstance(point_data['metadata'], str):
                try:
                    point_data['metadata'] = json.loads(point_data['metadata'])
                except:
                    pass
            
            trajectory_points.append(point_data)
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "agent_id": agent_id,
            "trajectory_points": trajectory_points
        }
        
    except Exception as e:
        logger.error(f"Error querying WebVoyager trajectory for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/instances/{instance_id}/conversation")
def get_webvoyager_conversation(instance_id: str):
    """Get conversation data for a WebVoyager instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get instance data
        cursor.execute("""
            SELECT scenario FROM webvoyager_instances WHERE instance_id = %s
        """, (instance_id,))
        
        instance_row = cursor.fetchone()
        if not instance_row:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        scenario = instance_row['scenario'] or ""
        
        # Get conversation (trajectory points that are actions)
        cursor.execute("""
            SELECT agent_id, timestamp, data_content, data_text, step_number
            FROM webvoyager_trajectory_points 
            WHERE instance_id = %s AND point_type = 'action'
            ORDER BY timestamp
        """, (instance_id,))
        
        conversation = []
        for row in cursor.fetchall():
            content = ""
            
            # Try to get content from data_text first, then data_content
            if row['data_text']:
                content = row['data_text']
            elif row['data_content']:
                if isinstance(row['data_content'], str):
                    try:
                        data_content = json.loads(row['data_content'])
                        if isinstance(data_content, dict) and 'content' in data_content:
                            content = str(data_content['content'])
                        else:
                            content = str(data_content)
                    except:
                        content = str(row['data_content'])
                else:
                    if isinstance(row['data_content'], dict) and 'content' in row['data_content']:
                        content = str(row['data_content']['content'])
                    else:
                        content = str(row['data_content'])
            
            if content:
                conversation.append({
                    "agent_id": row['agent_id'],
                    "timestamp": row['timestamp'].isoformat(),
                    "content": content,
                    "step_number": row['step_number']
                })
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "conversation": conversation,
            "scenario": scenario
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebVoyager conversation for instance {instance_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/screenshots/{instance_id}/{step_number}")
def get_webvoyager_screenshot(instance_id: str, step_number: int):
    """Get a specific screenshot for a WebVoyager instance and step"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT screenshot_data, file_size FROM webvoyager_screenshots 
            WHERE instance_id = %s AND step_number = %s
        """, (instance_id, step_number))
        
        screenshot_row = cursor.fetchone()
        cursor.close()
        
        if not screenshot_row:
            raise HTTPException(status_code=404, detail=f"Screenshot not found for instance {instance_id}, step {step_number}")
        
        # Return the screenshot as a file response
        return Response(
            content=screenshot_row['screenshot_data'],
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=screenshot_step_{step_number}.png"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving screenshot for instance {instance_id}, step {step_number}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving screenshot: {str(e)}")

@app.get("/webvoyager/step_files/{instance_id}/{step_number}")
def get_webvoyager_step_file(instance_id: str, step_number: int):
    """Get a specific step file for a WebVoyager instance and step"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT step_data, file_size FROM webvoyager_step_files 
            WHERE instance_id = %s AND step_number = %s
        """, (instance_id, step_number))
        
        step_row = cursor.fetchone()
        cursor.close()
        
        if not step_row:
            raise HTTPException(status_code=404, detail=f"Step file not found for instance {instance_id}, step {step_number}")
        
        # Return the step file as a file response
        return Response(
            content=step_row['step_data'],
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=step_{step_number}.pkl.gz"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving step file for instance {instance_id}, step {step_number}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving step file: {str(e)}")

@app.get("/webvoyager/instances/{instance_id}/metrics/{agent_id}")
async def get_webvoyager_instance_agent_metrics(instance_id: str, agent_id: str):
    """Get metrics for a specific WebVoyager instance and agent from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT metric_name, metric_value, reasoning
            FROM webvoyager_metrics 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY metric_name
        """, (instance_id, agent_id))
        
        results = cursor.fetchall()
        cursor.close()
        
        if not results:
            raise HTTPException(status_code=404, detail="Metrics not found for this instance/agent combination")
        
        # Format the response to match the original API
        response_data = {
            "instance_id": instance_id,
            "agent_id": agent_id
        }
        
        for row in results:
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            reasoning = row['reasoning']
            
            response_data[metric_name] = metric_value
            if reasoning:
                response_data[f"{metric_name}_reasoning"] = reasoning
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebVoyager metrics for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/metrics/instances")
def get_webvoyager_metrics_by_instance():
    """Get a mapping of instance IDs to their available metrics from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT instance_id, agent_id, metric_name, metric_value, reasoning
            FROM webvoyager_metrics 
            ORDER BY instance_id, agent_id, metric_name
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        # Create a mapping of instance_id -> agent_id -> metrics
        instance_metrics = {}
        
        for row in results:
            instance_id = row['instance_id']
            agent_id = row['agent_id']
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            reasoning = row['reasoning']
            
            # Initialize the instance entry if it doesn't exist
            if instance_id not in instance_metrics:
                instance_metrics[instance_id] = {}
            
            # Initialize the agent entry if it doesn't exist
            if agent_id not in instance_metrics[instance_id]:
                instance_metrics[instance_id][agent_id] = {
                    "metrics": {},
                    "reasoning": {}
                }
            
            # Add metric and reasoning
            instance_metrics[instance_id][agent_id]["metrics"][metric_name] = metric_value
            if reasoning:
                instance_metrics[instance_id][agent_id]["reasoning"][metric_name] = reasoning
        
        return instance_metrics
        
    except Exception as e:
        logger.error(f"Error querying WebVoyager metrics by instance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

# --- NEW DATABASE-BACKED SOTOPIA ENDPOINTS ---

@app.get("/sotopia/instances")
def get_sotopia_instances():
    """Get all Sotopia instances from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT instance_id, timestamp, scenario, experiment_tag, 
                   models, rewards, label, metadata, created_at
            FROM sotopia_instances 
            ORDER BY timestamp DESC
        """)
        
        results = cursor.fetchall()
        instances = []
        
        for row in results:
            instance_data = dict(row)
            
            # Convert datetime to string for JSON serialization
            if instance_data['timestamp']:
                instance_data['timestamp'] = instance_data['timestamp'].isoformat()
            if instance_data['created_at']:
                instance_data['created_at'] = instance_data['created_at'].isoformat()
            
            # Parse JSONB fields
            if instance_data['models'] and isinstance(instance_data['models'], str):
                try:
                    instance_data['models'] = json.loads(instance_data['models'])
                except:
                    pass
            
            if instance_data['rewards'] and isinstance(instance_data['rewards'], str):
                try:
                    instance_data['rewards'] = json.loads(instance_data['rewards'])
                except:
                    pass
            
            if instance_data['metadata'] and isinstance(instance_data['metadata'], str):
                try:
                    instance_data['metadata'] = json.loads(instance_data['metadata'])
                except:
                    pass
            
            instances.append(instance_data)
        
        cursor.close()
        return instances
        
    except Exception as e:
        logger.error(f"Error querying Sotopia instances: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/sotopia/instances/{instance_id}")
def get_sotopia_instance(instance_id: str):
    """Get details for a specific Sotopia instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get instance data
        cursor.execute("""
            SELECT instance_id, timestamp, scenario, experiment_tag, 
                   models, rewards, label, metadata, created_at
            FROM sotopia_instances 
            WHERE instance_id = %s
        """, (instance_id,))
        
        instance_row = cursor.fetchone()
        if not instance_row:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        instance_data = dict(instance_row)
        
        # Convert datetime to string for JSON serialization
        if instance_data['timestamp']:
            instance_data['timestamp'] = instance_data['timestamp'].isoformat()
        if instance_data['created_at']:
            instance_data['created_at'] = instance_data['created_at'].isoformat()
        
        # Parse JSONB fields
        if instance_data['models'] and isinstance(instance_data['models'], str):
            try:
                instance_data['models'] = json.loads(instance_data['models'])
            except:
                pass
        
        if instance_data['rewards'] and isinstance(instance_data['rewards'], str):
            try:
                instance_data['rewards'] = json.loads(instance_data['rewards'])
            except:
                pass
        
        if instance_data['metadata'] and isinstance(instance_data['metadata'], str):
            try:
                instance_data['metadata'] = json.loads(instance_data['metadata'])
            except:
                pass
        
        # Get agents for this instance
        cursor.execute("""
            SELECT agent_id, agent_type, capabilities, parameters, background
            FROM sotopia_agents 
            WHERE instance_id = %s
            ORDER BY agent_id
        """, (instance_id,))
        
        agents = []
        for agent_row in cursor.fetchall():
            agent_data = dict(agent_row)
            
            # Parse JSONB fields
            if agent_data['capabilities'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['capabilities'], dict):
                    agent_data['capabilities'] = {}
            else:
                agent_data['capabilities'] = {}
            
            if agent_data['parameters'] is not None:
                # JSONB fields are already parsed as Python objects by psycopg2
                if not isinstance(agent_data['parameters'], dict):
                    agent_data['parameters'] = {}
            else:
                agent_data['parameters'] = {}
            
            agents.append(agent_data)
        
        instance_data['agents'] = agents
        cursor.close()
        
        return instance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying Sotopia instance {instance_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/sotopia/instances/{instance_id}/trajectory/{agent_id}")
def get_sotopia_trajectory(instance_id: str, agent_id: str):
    """Get trajectory data for a specific agent in a Sotopia instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get trajectory points
        cursor.execute("""
            SELECT timestamp, point_type, media_type, data_content, data_text, metadata, point_index
            FROM sotopia_trajectory_points 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY timestamp, point_index
        """, (instance_id, agent_id))
        
        trajectory_points = []
        for row in cursor.fetchall():
            point_data = dict(row)
            
            # Convert datetime to string for JSON serialization
            if point_data['timestamp']:
                point_data['timestamp'] = point_data['timestamp'].isoformat()
            
            # Parse JSONB fields
            if point_data['data_content'] and isinstance(point_data['data_content'], str):
                try:
                    point_data['data_content'] = json.loads(point_data['data_content'])
                except:
                    pass
            
            if point_data['metadata'] and isinstance(point_data['metadata'], str):
                try:
                    point_data['metadata'] = json.loads(point_data['metadata'])
                except:
                    pass
            
            trajectory_points.append(point_data)
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "agent_id": agent_id,
            "trajectory_points": trajectory_points
        }
        
    except Exception as e:
        logger.error(f"Error querying Sotopia trajectory for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/sotopia/instances/{instance_id}/conversation")
def get_sotopia_conversation(instance_id: str):
    """Get conversation data for a Sotopia instance (similar to the original /trajectories/{instance_id} endpoint)"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get instance data
        cursor.execute("""
            SELECT scenario FROM sotopia_instances WHERE instance_id = %s
        """, (instance_id,))
        
        instance_row = cursor.fetchone()
        if not instance_row:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        scenario = instance_row['scenario'] or ""
        
        # Get agent backgrounds
        cursor.execute("""
            SELECT agent_id, background FROM sotopia_agents 
            WHERE instance_id = %s AND background IS NOT NULL AND background != ''
        """, (instance_id,))
        
        agent_backgrounds = {}
        for row in cursor.fetchall():
            agent_backgrounds[row['agent_id']] = row['background']
        
        # Get conversation (trajectory points that are actions)
        cursor.execute("""
            SELECT agent_id, timestamp, data_content, data_text
            FROM sotopia_trajectory_points 
            WHERE instance_id = %s AND point_type = 'action'
            ORDER BY timestamp
        """, (instance_id,))
        
        conversation = []
        for row in cursor.fetchall():
            content = ""
            
            # Try to get content from data_text first, then data_content
            if row['data_text']:
                content = row['data_text']
            elif row['data_content']:
                if isinstance(row['data_content'], str):
                    try:
                        data_content = json.loads(row['data_content'])
                        if isinstance(data_content, dict) and 'content' in data_content:
                            content = str(data_content['content'])
                        else:
                            content = str(data_content)
                    except:
                        content = str(row['data_content'])
                else:
                    if isinstance(row['data_content'], dict) and 'content' in row['data_content']:
                        content = str(row['data_content']['content'])
                    else:
                        content = str(row['data_content'])
            
            if content:
                conversation.append({
                    "agent_id": row['agent_id'],
                    "timestamp": row['timestamp'].isoformat(),
                    "content": content
                })
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "conversation": conversation,
            "scenario": scenario,
            "agent_backgrounds": agent_backgrounds
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying Sotopia conversation for instance {instance_id}: {str(e)}", exc_info=True)
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/sotopia/instances/{instance_id}/metrics/{agent_id}")
async def get_sotopia_instance_agent_metrics(instance_id: str, agent_id: str):
    """Get metrics for a specific Sotopia instance and agent from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT metric_name, metric_value, reasoning
            FROM sotopia_metrics 
            WHERE instance_id = %s AND agent_id = %s
            ORDER BY metric_name
        """, (instance_id, agent_id))
        
        results = cursor.fetchall()
        cursor.close()
        
        if not results:
            raise HTTPException(status_code=404, detail="Metrics not found for this instance/agent combination")
        
        # Format the response to match the original API
        response_data = {
            "instance_id": instance_id,
            "agent_id": agent_id
        }
        
        for row in results:
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            reasoning = row['reasoning']
            
            response_data[metric_name] = metric_value
            if reasoning:
                response_data[f"{metric_name}_reasoning"] = reasoning
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying Sotopia metrics for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/sotopia/metrics/instances")
def get_sotopia_metrics_by_instance():
    """Get a mapping of instance IDs to their available metrics from the database"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT instance_id, agent_id, metric_name, metric_value, reasoning
            FROM sotopia_metrics 
            ORDER BY instance_id, agent_id, metric_name
        """)
        
        results = cursor.fetchall()
        cursor.close()
        
        # Create a mapping of instance_id -> agent_id -> metrics
        instance_metrics = {}
        
        for row in results:
            instance_id = row['instance_id']
            agent_id = row['agent_id']
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            reasoning = row['reasoning']
            
            # Initialize the instance entry if it doesn't exist
            if instance_id not in instance_metrics:
                instance_metrics[instance_id] = {}
            
            # Initialize the agent entry if it doesn't exist
            if agent_id not in instance_metrics[instance_id]:
                instance_metrics[instance_id][agent_id] = {
                    "metrics": {},
                    "reasoning": {}
                }
            
            # Add metric and reasoning
            instance_metrics[instance_id][agent_id]["metrics"][metric_name] = metric_value
            if reasoning:
                instance_metrics[instance_id][agent_id]["reasoning"][metric_name] = reasoning
        
        return instance_metrics
        
    except Exception as e:
        logger.error(f"Error querying Sotopia metrics by instance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

# --- END NEW DATABASE-BACKED SOTOPIA ENDPOINTS ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

