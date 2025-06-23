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
from fastapi.responses import FileResponse
from typing import List, Dict, Optional, Any
import psycopg2
import psycopg2.extras 
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()
from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType
from osw_data.annotation import AnnotationSystem, AnnotationSpan

annotation_path = Path(__file__).parent.parent.parent / ".data" / "annotations" / "sotopia"
webvoyager_path = Path(__file__).parent.parent.parent / ".data" / "nnetnav_openweb_3"
webvoyager_metrics_file = Path(__file__).parent.parent.parent / ".data" / "metrics" / "webvoyager_nnetnav" / "8_metrics" / "llm_eval_results.jsonl"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnnotationPayload(BaseModel):
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize dataset, load labels, and initialize annotation system
    global dataset, instance_labels, metric_set, annotation_system, webarena_instance_labels, webarena_dataset, db_conn
    
    # Initialize database connection
    try:
        db_conn = get_db_connection()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}", exc_info=True)
        db_conn = None
    
    # Initialize Annotation System
    try:
        # Ensure the annotation directory exists
        annotation_path.mkdir(parents=True, exist_ok=True)
        
        annotation_system = AnnotationSystem(
            base_path=annotation_path,
            project_name="Sotopia Web Annotation", # Give it a relevant name
            description="Annotations added via the web interface.",
            annotation_schema={
                "comment": {
                    "type": "object",
                    "properties": {
                        "comment_text": {"type": "string"},
                        "selection_text": {"type": "string"},
                        "start_offset": {"type": "integer"},
                        "end_offset": {"type": "integer"},
                    },
                    "required": ["comment_text", "selection_text", "start_offset", "end_offset"],
                    "description": "A comment linked to a text selection.",
                }
            },
        )
        logger.info(f"Annotation system initialized at {annotation_path}")
    except Exception as e:
        logger.error(f"Failed to initialize AnnotationSystem: {str(e)}", exc_info=True)
        annotation_system = None # Set to None if initialization fails

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
    """Receive and save a new annotation."""
    logger.info(f"Received annotation payload: {payload.dict()}")

    if not annotation_system:
        logger.error("Annotation system not initialized.")
        raise HTTPException(status_code=500, detail="Annotation system not available")

    # Ensure annotator exists in the system
    if payload.annotator_id not in annotation_system.project.annotators:
        try:
            annotation_system.add_annotator(
                annotator_id=payload.annotator_id,
                name=payload.annotator_id, # Use ID as name for simplicity
            )
            logger.info(f"Added new annotator: {payload.annotator_id}")
        except Exception as e:
            logger.error(f"Failed to add annotator {payload.annotator_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to add annotator: {str(e)}")

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

        # Add the annotation
        # We don't have a precise time span from the frontend comment system,
        # so we'll use the current time as a point annotation (start=end).
        # Alternatively, omit the span if your workflow allows.
        current_time = datetime.now()
        annotation_system.add_annotation(
            instance_id=payload.instance_id,
            agent_id=payload.agent_id,
            annotator_id=payload.annotator_id,
            content=annotation_content,
            span=AnnotationSpan(start_time=current_time, end_time=current_time), # Point-in-time span
            # span=None # Or omit span if not strictly needed here
        )

        logger.info(f"Annotation saved successfully for instance {payload.instance_id}, agent {payload.agent_id}")
        return {"message": "Annotation saved successfully"}

    except Exception as e:
        logger.error(f"Failed to save annotation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save annotation: {str(e)}")
# --- END NEW ANNOTATION ENDPOINT ---

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
            instance_data = dict(row)
            
            # Convert datetime to string for JSON serialization
            if instance_data['timestamp']:
                instance_data['timestamp'] = instance_data['timestamp'].isoformat()
            if instance_data['created_at']:
                instance_data['created_at'] = instance_data['created_at'].isoformat()
            
            # Parse JSONB fields
            if instance_data['metadata'] and isinstance(instance_data['metadata'], str):
                try:
                    instance_data['metadata'] = json.loads(instance_data['metadata'])
                except:
                    pass
            
            instances.append(instance_data)
        
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
        if instance_data['metadata'] and isinstance(instance_data['metadata'], str):
            try:
                instance_data['metadata'] = json.loads(instance_data['metadata'])
            except:
                pass
        
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
            if agent_data['capabilities'] and isinstance(agent_data['capabilities'], str):
                try:
                    agent_data['capabilities'] = json.loads(agent_data['capabilities'])
                except:
                    pass
            
            if agent_data['parameters'] and isinstance(agent_data['parameters'], str):
                try:
                    agent_data['parameters'] = json.loads(agent_data['parameters'])
                except:
                    pass
            
            if agent_data['additional_info'] and isinstance(agent_data['additional_info'], str):
                try:
                    agent_data['additional_info'] = json.loads(agent_data['additional_info'])
                except:
                    pass
            
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
        # Create a new cursor for this request
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Query to get distinct experiment folders and their descriptions
        cursor.execute("""
            SELECT DISTINCT 
                regexp_replace(filepath, '/[^/]*$', '') as folder_path,
                description
            FROM files 
            WHERE filepath LIKE 'nnetnav_openweb_3/%'
            AND description IS NOT NULL
            ORDER BY folder_path
        """)
        
        results = cursor.fetchall()
        
        # Format the results
        instances = []
        for row in results:
            folder_path = row['folder_path']
            description = row['description']
            
            # Extract instance_id from the folder path
            # Assuming format like 'nnetnav_openweb_3/experiment_123'
            parts = folder_path.split('/')
            if len(parts) >= 2:
                instance_id = parts[1]  # Get the experiment_XXX part
            else:
                instance_id = folder_path
            
            instances.append({
                "instance_id": instance_id,
                "label": description or "Unlabeled",
                "folder_path": folder_path
            })
        
        cursor.close()
        return instances
        
    except Exception as e:
        logger.error(f"Error querying WebVoyagerinstances: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/instances/{instance_id}")
def get_webvoyager_instance(instance_id: str):
    """Get details for a specific WebVoyager instance"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        # Create a new cursor for this request
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # First, find the folder path for this instance_id
        cursor.execute("""
            SELECT DISTINCT regexp_replace(filepath, '/[^/]*$', '') as folder_path
            FROM files 
            WHERE filepath LIKE %s
            LIMIT 1
        """, (f'%/{instance_id}/%',))
        
        folder_result = cursor.fetchone()
        if not folder_result:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        folder_path = folder_result['folder_path']
        
        # Get all files for this instance
        cursor.execute("""
            SELECT id, filename, filepath, filetype, filesize, 
                   created_at, description, metadata
            FROM files 
            WHERE filepath LIKE %s
            ORDER BY filepath, filename
        """, (f'{folder_path}/%',))
        
        files = []
        log_content = None
        log_segments = []
        
        # First pass to collect all files and find the log file
        for row in cursor.fetchall():
            file_data = dict(row)
            
            # Convert datetime to string for JSON serialization
            if file_data['created_at']:
                file_data['created_at'] = file_data['created_at'].isoformat()
            
            # Parse metadata JSON if it exists
            if file_data['metadata'] and isinstance(file_data['metadata'], str):
                try:
                    file_data['metadata'] = json.loads(file_data['metadata'])
                except:
                    pass
            
            files.append(file_data)
            
            # If this is the experiment.log file, read its content
            if file_data['filename'] == 'experiment.log':
                try:
                    # Fix the filepath by removing duplicate nnetnav_openweb_3 if present
                    filepath = file_data['filepath'].lstrip('/')
                    if filepath.startswith('nnetnav_openweb_3/nnetnav_openweb_3/'):
                        filepath = filepath.replace('nnetnav_openweb_3/nnetnav_openweb_3/', 'nnetnav_openweb_3/', 1)
                    
                    # Try the corrected path first
                    log_path = os.path.join(webvoyager_path.parent, filepath)
                    
                    if not os.path.exists(log_path):
                        # Try the original path as fallback
                        alt_log_path = os.path.join(webvoyager_path, file_data['filepath'].lstrip('/'))
                        if os.path.exists(alt_log_path):
                            log_path = alt_log_path
                    
                    if os.path.exists(log_path):
                        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read()
                            
                            # Split log into segments based on actions
                            segments = []
                            current_segment = ""
                            
                            for line in log_content.splitlines():
                                current_segment += line + "\n"
                                
                                # If line contains "action:" it's the end of a segment
                                if "action:" in line:
                                    segments.append(current_segment.strip())
                                    current_segment = ""
                            
                            # Add the last segment if it's not empty
                            if current_segment.strip():
                                segments.append(current_segment.strip())
                                
                            log_segments = segments
                    else:
                        logger.error(f"Log file not found at: {log_path}")
                except Exception as e:
                    logger.error(f"Error reading log file: {str(e)}")
        
        # Get the description (task) for this instance
        cursor.execute("""
            SELECT description 
            FROM files 
            WHERE filepath LIKE %s 
            AND description IS NOT NULL 
            LIMIT 1
        """, (f'{folder_path}/%',))
        
        description_row = cursor.fetchone()
        description = description_row['description'] if description_row else "Unknown Task"
        
        # Get screenshot files and sort them
        screenshot_files = [f for f in files if f['filetype'] in ('image/png', 'image/jpeg')]
        screenshot_files.sort(key=lambda x: x['filepath'])
        
        # Match log segments to screenshots if possible
        screenshot_log_pairs = []
        
        # If we have both screenshots and log segments, try to pair them
        if screenshot_files and log_segments:
            # If we have more screenshots than log segments, use the available segments
            if len(screenshot_files) > len(log_segments):
                for i, screenshot in enumerate(screenshot_files):
                    if i < len(log_segments):
                        screenshot_log_pairs.append({
                            "screenshot_id": screenshot['id'],
                            "log_segment": log_segments[i]
                        })
                    else:
                        screenshot_log_pairs.append({
                            "screenshot_id": screenshot['id'],
                            "log_segment": "No corresponding log segment available"
                        })
            # If we have more log segments than screenshots, use the first segments
            else:
                for i, screenshot in enumerate(screenshot_files):
                    screenshot_log_pairs.append({
                        "screenshot_id": screenshot['id'],
                        "log_segment": log_segments[i]
                    })
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "folder_path": folder_path,
            "description": description,
            "files": files,
            "log_content": log_content,
            "screenshot_log_pairs": screenshot_log_pairs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebVoyager instance {instance_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webvoyager/files/{file_id}")
def get_webvoyager_file(file_id: int):
    """Get a specific file from the WebVoyager dataset"""
    if not db_conn:
        logger.error("Database connection not available")
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        # Create a new cursor for this request
        cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get the file record
        cursor.execute("""
            SELECT id, filename, filepath, filetype 
            FROM files 
            WHERE id = %s
        """, (file_id,))
        
        file_record = cursor.fetchone()
        cursor.close()
        
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File with ID {file_id} not found")
        
        # Fix the filepath by removing duplicate nnetnav_openweb_3 if present
        filepath = file_record['filepath'].lstrip('/')
        if filepath.startswith('nnetnav_openweb_3/nnetnav_openweb_3/'):
            filepath = filepath.replace('nnetnav_openweb_3/nnetnav_openweb_3/', 'nnetnav_openweb_3/', 1)
        
        # Construct the full path to the file
        file_path = os.path.join(webvoyager_path.parent, filepath)
        
        if not os.path.exists(file_path):
            # Try an alternative path as fallback
            alt_file_path = os.path.join(webvoyager_path, file_record['filepath'].lstrip('/'))
            if not os.path.exists(alt_file_path):
                logger.error(f"File not found on disk: {file_path} or {alt_file_path}")
                raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path}")
            file_path = alt_file_path
        
        # Return the file
        return FileResponse(
            path=file_path,
            filename=file_record['filename'],
            media_type=file_record['filetype']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file {file_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")
    
@app.get("/webvoyager/instances/{instance_id}/metrics/{agent_id}")
async def get_webvoyager_instance_agent_metrics(instance_id: str, agent_id: str):
    """Get metrics for a specific WebVoyager instance (agent_id must be 'agent')."""
    logger.info(f"Attempting to get WebVoyager metrics for instance='{instance_id}', agent='{agent_id}'")

    # --- Validate requested agent_id ---
    if agent_id != "agent":
        logger.warning(f"Invalid agent_id '{agent_id}' requested for WebVoyager instance '{instance_id}'. Only 'agent' is supported.")
        raise HTTPException(status_code=400, detail="Invalid agent_id for WebVoyager. Only 'agent' is supported.")
    # --- End Validation ---

    if not webvoyager_metrics_file.exists():
        logger.warning(f"WebVoyager metrics file not found at {webvoyager_metrics_file} for instance {instance_id}, agent {agent_id}")
        raise HTTPException(status_code=404, detail="WebVoyager metrics file not found")

    try:
        line_number = 0
        with open(webarena_metrics_file, "r") as f:
            for line in f:
                line_number += 1
                try:
                    metric_data = json.loads(line)
                    file_instance_id = metric_data.get("instance_id")
                    # --- Check agent_id in file ---
                    file_agent_id = metric_data.get("agent_id")
                    if file_agent_id != "agent":
                        # Silently skip lines with incorrect agent_id in the file
                        continue
                    # --- End Check ---

                    logger.debug(f"Line {line_number}: Comparing Request(instance='{instance_id}') with File(instance='{file_instance_id}', agent='{file_agent_id}')")
                    ids_match = file_instance_id == instance_id
                    # agents_match is implicitly true if we reach here, as both request and file agent_id must be 'agent'
                    logger.debug(f"Line {line_number}: Instance match: {ids_match}")

                    if ids_match: # Only need to check instance ID now
                        logger.info(f"Found WebArena match on line {line_number} for instance='{instance_id}', agent='agent'")
                        response_data = {}
                        for key, value in metric_data.items():
                             if isinstance(value, (int, float)) or (key.endswith("_reasoning") and isinstance(value, str)):
                                 response_data[key] = value
                        # Return the validated agent_id from the request
                        response_data["instance_id"] = instance_id
                        response_data["agent_id"] = agent_id # Should always be 'agent'
                        return response_data
                except json.JSONDecodeError:
                    logger.error(f"Error parsing JSON on line {line_number} in WebArena metrics file: {line.strip()}")
                    continue
                except Exception as e: # Catch other potential errors per line
                    logger.error(f"Error processing line {line_number} in WebArena metrics file: {line.strip()} - {e}")
                    continue

        # If loop finishes without finding a match for the instance_id with agent_id='agent'
        logger.warning(f"WebArena metrics search completed. No match found for instance {instance_id} (with agent_id='agent') after checking {line_number} lines.")
        raise HTTPException(status_code=404, detail="Metrics not found for this WebArena instance with agent_id='agent'")

    except Exception as e:
        logger.error(f"Error reading WebArena metrics file for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error reading WebArena metrics")

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
            if agent_data['capabilities'] and isinstance(agent_data['capabilities'], str):
                try:
                    agent_data['capabilities'] = json.loads(agent_data['capabilities'])
                except:
                    pass
            
            if agent_data['parameters'] and isinstance(agent_data['parameters'], str):
                try:
                    agent_data['parameters'] = json.loads(agent_data['parameters'])
                except:
                    pass
            
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

