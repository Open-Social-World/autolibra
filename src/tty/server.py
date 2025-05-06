from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import sys
from contextlib import asynccontextmanager
import re
import logging
# Add pydantic for request body validation
from pydantic import BaseModel
# Add datetime for timestamps
from datetime import datetime
import os # Import os for sorting agent files numerically
from fastapi.responses import FileResponse
from typing import List, Dict, Optional, Any
import psycopg2
import psycopg2.extras  # For better handling of query results

from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType
from osw_data.metrics import MetricSet
# Import AnnotationSystem
from osw_data.annotation import AnnotationSystem, AnnotationSpan

# TEMPORARY Add the package directory to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent / "packages"))
# TEMPORARY Initialize dataset path
dataset_path = Path(__file__).parent.parent.parent / ".data" / "sotopia"
# Define annotation path
annotation_path = Path(__file__).parent.parent.parent / ".data" / "annotations" / "sotopia"
# --- Add path for WebArena data ---
webarena_dataset_path = Path(__file__).parent.parent.parent / ".data" / "webarena"
# --- Add path for WebArena instances (still useful for direct access if needed, but not for listing via dataset) ---
webarena_instances_path = webarena_dataset_path / "instances"
# --- Add path for Sotopia metrics ---
sotopia_metrics_file = Path(__file__).parent.parent.parent / ".data" / "metrics" / "sotopia" / "8_metrics" / "llm_eval_results.jsonl"
# --- Add path for WebArena metrics ---
webarena_metrics_file = Path(__file__).parent.parent.parent / ".data" / "metrics" / "webarena" / "8_metrics" / "llm_eval_results.jsonl"
# --- Add path for WebArena mock dataset ---
webarena_mock_path = Path(__file__).parent.parent.parent / "inspicio" / ".data" / "extracted" / "nnetnav_openweb_3"
# --- End Add paths ---

# Add at the top of the file
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a Pydantic model for the annotation payload
class AnnotationPayload(BaseModel):
    instance_id: str
    agent_id: str
    annotator_id: str
    comment_text: str
    selection_text: str
    start_offset: int
    end_offset: int

# Database connection parameters
DB_CONFIG = {
    "dbname": "inspiciodb",
    "user": "postgres",
    "password": "Yankayee123",
    "host": "localhost"
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
    
    # Initialize Sotopia dataset
    dataset = MultiAgentDataset(name="sotopia", base_path=dataset_path)
    
    # Initialize WebArena dataset
    try:
        webarena_dataset = MultiAgentDataset(name="webarena", base_path=webarena_dataset_path)
        logger.info(f"WebArena dataset initialized from {webarena_dataset_path}")
    except Exception as e:
        logger.error(f"Failed to initialize WebArena dataset: {e}", exc_info=True)
        webarena_dataset = None # Set to None if initialization fails

    # Load Sotopia labels
    sotopia_labels_path = dataset_path / "instance_labels.json"
    if sotopia_labels_path.exists():
        try:
            with open(sotopia_labels_path, "r") as f:
                instance_labels = json.load(f)
            logger.info(f"Sotopia labels loaded from {sotopia_labels_path}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {sotopia_labels_path}. Initializing as empty.")
            instance_labels = {}
        except Exception as e:
            logger.error(f"Error loading Sotopia labels from {sotopia_labels_path}: {e}. Initializing as empty.")
            instance_labels = {}
    else:
        logger.warning(f"Sotopia labels file not found at {sotopia_labels_path}")
        instance_labels = {} # Initialize as empty dict if not found
    
    # Load WebArena labels
    webarena_labels_path = webarena_dataset_path / "instance_labels.json"
    if webarena_labels_path.exists():
        try:
            with open(webarena_labels_path, "r") as f:
                webarena_instance_labels = json.load(f)
            logger.info(f"WebArena labels loaded from {webarena_labels_path}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {webarena_labels_path}. Initializing as empty.")
            webarena_instance_labels = {}
        except Exception as e:
            logger.error(f"Error loading WebArena labels from {webarena_labels_path}: {e}. Initializing as empty.")
            webarena_instance_labels = {}
    else:
        logger.warning(f"WebArena labels file not found at {webarena_labels_path}")
        webarena_instance_labels = {} # Initialize as empty dict if not found

    # Try to load metrics
    try:
        metric_set = MetricSet(name="sotopia", base_path=dataset_path, induced_from="sotopia")
    except Exception as e:
        logger.warning(f"Could not load metrics: {str(e)}")
        metric_set = None

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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Trajectory Dataset API is running"}

@app.get("/trajectories")
def get_label():
    """Get all Sotopia instance IDs with their labels"""
    if not dataset:
        raise HTTPException(status_code=500, detail="Dataset not initialized")

    instances = dataset.list_instances()
    result = []

    for instance_id in instances:
        try:
            # Get label if available from Sotopia labels
            label = instance_labels.get(instance_id, "Unlabeled")

            result.append({
                "instance_id": instance_id,
                "label": label
            })
        except Exception as e:
            # Log specific error for Sotopia instance loading
            logger.error(f"Error processing Sotopia instance {instance_id}: {str(e)}")

    return result

# --- UPDATED ENDPOINT for WebArena Instances ---
@app.get("/webarena/trajectories")
def get_webarena_label():
    """Get all WebArena instance IDs with their labels"""
    # Use the WebArena dataset object to list instances
    global webarena_dataset # Ensure access to the global dataset object
    if not webarena_dataset:
        logger.error("WebArena dataset not initialized.")
        raise HTTPException(status_code=500, detail="WebArena dataset not initialized")

    try:
        instances = webarena_dataset.list_instances()
        # Sort numerically if possible, otherwise alphabetically (MultiAgentDataset might already sort)
        try:
            instances.sort(key=int)
        except ValueError:
            instances.sort() # Fallback sort
    except Exception as e:
        logger.error(f"Error listing WebArena instances using dataset object: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list WebArena instances")

    result = []

    if not instances:
        logger.info("No WebArena instances found by dataset object.")
        return []

    # Check if webarena_instance_labels were loaded
    if 'webarena_instance_labels' not in globals():
         logger.warning("WebArena instance labels dictionary not found in global scope.")
         # Consider how critical labels are - maybe proceed without them or raise error

    for instance_id in instances:
        try:
            # Get label if available from WebArena labels
            label = globals().get('webarena_instance_labels', {}).get(instance_id, "Unlabeled")

            result.append({
                "instance_id": instance_id,
                "label": label
            })
        except Exception as e:
            # Log specific error for WebArena instance processing
            logger.error(f"Error processing WebArena instance {instance_id} data: {str(e)}")
            # Optionally skip this instance or add a placeholder

    return result
# --- END UPDATED ENDPOINT ---

@app.get("/metrics/instances")
def get_metrics_by_instance():
    """Get a mapping of instance IDs to their available metrics"""
    metrics_file = sotopia_metrics_file
    
    if not metrics_file.exists():
        logger.warning(f"Sotopia metrics file not found at {metrics_file}")
        return {}
    
    # Create a mapping of instance_id -> agent_id -> metrics
    instance_metrics = {}
    
    try:
        with open(metrics_file, "r") as f:
            for line in f:
                try:
                    metric_data = json.loads(line)
                    instance_id = metric_data.get("instance_id")
                    agent_id = metric_data.get("agent_id")
                    
                    if not instance_id or not agent_id:
                        continue
                    
                    # Initialize the instance entry if it doesn't exist
                    if instance_id not in instance_metrics:
                        instance_metrics[instance_id] = {}
                    
                    # Initialize the agent entry if it doesn't exist
                    if agent_id not in instance_metrics[instance_id]:
                        instance_metrics[instance_id][agent_id] = {
                            "metrics": {},
                            "reasoning": {}
                        }
                    
                    # Extract metric scores and reasoning
                    for key, value in metric_data.items():
                        if isinstance(value, int) and key not in ["instance_id", "agent_id"]:
                            instance_metrics[instance_id][agent_id]["metrics"][key] = value
                        elif key.endswith("_reasoning") and isinstance(value, str):
                            metric_name = key.replace("_reasoning", "")
                            instance_metrics[instance_id][agent_id]["reasoning"][metric_name] = value
                            
                except json.JSONDecodeError:
                    logger.error(f"Error parsing JSON from metrics file")
                    continue
    except Exception as e:
        logger.error(f"Error reading metrics file: {str(e)}")
        return {}
    
    return instance_metrics

@app.get("/api/instances/{instance_id}/metrics/{agent_id}")
async def get_instance_agent_metrics(instance_id: str, agent_id: str):
    """Get metrics for a specific agent within a specific instance."""
    logger.info(f"Attempting to get Sotopia metrics for instance='{instance_id}', agent='{agent_id}'")
    metrics_file = sotopia_metrics_file

    if not metrics_file.exists():
        logger.warning(f"Sotopia metrics file not found at {metrics_file} for instance {instance_id}, agent {agent_id}")
        raise HTTPException(status_code=404, detail="Metrics file not found")

    try:
        line_number = 0
        with open(metrics_file, "r") as f:
            for line in f:
                line_number += 1
                try:
                    metric_data = json.loads(line)
                    file_instance_id = metric_data.get("instance_id")
                    file_agent_id = metric_data.get("agent_id")

                    logger.debug(f"Line {line_number}: Comparing Request(instance='{instance_id}', agent='{agent_id}') with File(instance='{file_instance_id}', agent='{file_agent_id}')")
                    ids_match = file_instance_id == instance_id
                    agents_match = file_agent_id == agent_id
                    logger.debug(f"Line {line_number}: Instance match: {ids_match}, Agent match: {agents_match}")

                    if ids_match and agents_match:
                        logger.info(f"Found match on line {line_number} for instance='{instance_id}', agent='{agent_id}'")
                        response_data = {}
                        for key, value in metric_data.items():
                             if isinstance(value, int) or (key.endswith("_reasoning") and isinstance(value, str)):
                                 response_data[key] = value
                        response_data["instance_id"] = instance_id
                        response_data["agent_id"] = agent_id
                        return response_data
                except json.JSONDecodeError:
                    logger.error(f"Error parsing JSON on line {line_number} in metrics file: {line.strip()}")
                    continue

        logger.warning(f"Metrics search completed. No match found for instance {instance_id}, agent {agent_id} after checking {line_number} lines.")
        raise HTTPException(status_code=404, detail="Metrics not found for this instance/agent combination")

    except Exception as e:
        logger.error(f"Error reading metrics file for instance {instance_id}, agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error reading metrics")

@app.get("/trajectories/{instance_id}")
def get_trajectory(instance_id: str):
    """Get full trajectory data for a specific instance"""
    if not dataset:
        raise HTTPException(status_code=500, detail="Dataset not initialized")
    
    try:
        metadata = dataset.get_instance_metadata(instance_id)
        
        # Extract scenario from metadata
        scenario = ""
        if metadata and hasattr(metadata, "metadata") and isinstance(metadata.metadata, dict):
            scenario = metadata.metadata.get("scenario", "")
            
            # Clean the scenario text
            if scenario:
                # Remove HTML tags
                scenario = re.sub(r'<.*?>', '', scenario)
                
                # Remove any text after a period followed by a space if it contains HTML-like content
                match = re.search(r'\.\s+.*?<', scenario)
                if match:
                    scenario = scenario[:match.start() + 1]
                
                # Trim whitespace
                scenario = scenario.strip()
        
        # Extract metrics and agent backgrounds in a single pass
        metrics = {}
        agent_backgrounds = {}
        
        if metadata:
            # Extract agent backgrounds from agent parameters
            if hasattr(metadata, "agents") and metadata.agents:
                for agent_id, agent_data in metadata.agents.items():
                    if hasattr(agent_data, "parameters") and isinstance(agent_data.parameters, dict):
                        if "background" in agent_data.parameters:
                            agent_backgrounds[agent_id] = agent_data.parameters["background"]
        
        
        # Get trajectory data
        conversation = []
        
        for agent_id in metadata.agents:
            trajectory = dataset.get_trajectory(instance_id, agent_id)
            
            # Sort trajectory points by timestamp
            trajectory_points = [
                (point, trajectory.get_data_at(idx))
                for idx, point in enumerate(trajectory.points)
            ]
            trajectory_points.sort(key=lambda x: x[0].timestamp)
            
            # Extract actions (which contain dialogue)
            for point, data in trajectory_points:
                if point.point_type == PointType.ACTION:
                    # Extract the dialogue from the action
                    content = None
                    
                    if isinstance(data, dict) and "content" in data:
                        content = data.get("content", "")
                    elif isinstance(data, str):
                        content = data
                    else:
                        # Try to convert to string if it's not a dict or string
                        try:
                            content = str(data)
                        except:
                            continue
                    
                    if content:
                        # Clean up content if needed
                        if isinstance(content, str):
                            # Remove escaped characters
                            content = content.replace("\\n", "\n").replace('\\"', '"')
                        
                        conversation.append({
                            "agent_id": agent_id,
                            "timestamp": point.timestamp.isoformat(),
                            "content": content
                        })
        
        # Sort all conversation entries by timestamp
        conversation.sort(key=lambda x: x["timestamp"])
        
        return {
            "instance_id": instance_id,
            "conversation": conversation,
            "scenario": scenario,
            "agent_backgrounds": agent_backgrounds
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Instance not found: {str(e)}")

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

@app.get("/webarena/trajectories/{instance_id}")
def get_webarena_trajectory(instance_id: str):
    """Get full trajectory data for a specific WebArena instance"""
    if not webarena_dataset:
        raise HTTPException(status_code=500, detail="WebArena dataset not initialized")
    
    try:
        metadata = webarena_dataset.get_instance_metadata(instance_id)
        
        # Extract scenario from metadata
        scenario = ""
        if metadata and hasattr(metadata, "metadata") and isinstance(metadata.metadata, dict):
            scenario = metadata.metadata.get("scenario", "")
            
            # Clean the scenario text
            if scenario:
                # Remove HTML tags
                scenario = re.sub(r'<.*?>', '', scenario)
                
                # Remove any text after a period followed by a space if it contains HTML-like content
                match = re.search(r'\.\s+.*?<', scenario)
                if match:
                    scenario = scenario[:match.start() + 1]
                
                # Trim whitespace
                scenario = scenario.strip()
        
        # Get trajectory data
        conversation = []
        
        for agent_id in metadata.agents:
            trajectory = webarena_dataset.get_trajectory(instance_id, agent_id)
            
            # Sort trajectory points by timestamp
            trajectory_points = [
                (point, trajectory.get_data_at(idx))
                for idx, point in enumerate(trajectory.points)
            ]
            trajectory_points.sort(key=lambda x: x[0].timestamp)
            
            # Extract actions (which contain dialogue)
            for point, data in trajectory_points:
                if point.point_type == PointType.ACTION:
                    # Extract the dialogue from the action
                    content = None
                    
                    if isinstance(data, dict) and "content" in data:
                        content = data.get("content", "")
                    elif isinstance(data, str):
                        content = data
                    else:
                        # Try to convert to string if it's not a dict or string
                        try:
                            content = str(data)
                        except:
                            continue
                    
                    if content:
                        # Clean up content if needed
                        if isinstance(content, str):
                            # Remove escaped characters
                            content = content.replace("\\n", "\n").replace('\\"', '"')
                        
                        conversation.append({
                            "agent_id": agent_id,
                            "timestamp": point.timestamp.isoformat(),
                            "content": content
                        })
        
        # Sort all conversation entries by timestamp
        conversation.sort(key=lambda x: x["timestamp"])
        
        return {
            "instance_id": instance_id,
            "conversation": conversation,
            "scenario": scenario
        }
    except Exception as e:
        logger.error(f"Error retrieving WebArena trajectory for {instance_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"WebArena instance not found: {str(e)}")


# --- NEW ENDPOINT for Specific WebArena Metrics ---
@app.get("/webarena/instances/{instance_id}/metrics/{agent_id}")
async def get_webarena_instance_agent_metrics(instance_id: str, agent_id: str):
    """Get metrics for a specific WebArena instance (agent_id must be 'agent')."""
    logger.info(f"Attempting to get WebArena metrics for instance='{instance_id}', agent='{agent_id}'")

    # --- Validate requested agent_id ---
    if agent_id != "agent":
        logger.warning(f"Invalid agent_id '{agent_id}' requested for WebArena instance '{instance_id}'. Only 'agent' is supported.")
        raise HTTPException(status_code=400, detail="Invalid agent_id for WebArena. Only 'agent' is supported.")
    # --- End Validation ---

    if not webarena_metrics_file.exists():
        logger.warning(f"WebArena metrics file not found at {webarena_metrics_file} for instance {instance_id}, agent {agent_id}")
        raise HTTPException(status_code=404, detail="WebArena metrics file not found")

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
# --- END NEW ENDPOINT ---

@app.get("/webarena/mock/instances")
def get_webarena_mock_instances():
    """Get all WebArena mock instances from the database"""
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
            WHERE filepath LIKE 'nnetnav_openweb_%/%'
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
        logger.error(f"Error querying WebArena mock instances: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/mock/instances/{instance_id}")
def get_webarena_mock_instance(instance_id: str):
    """Get details for a specific WebArena mock instance"""
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
                    log_path = os.path.join(webarena_mock_path.parent, filepath)
                    
                    if not os.path.exists(log_path):
                        # Try the original path as fallback
                        alt_log_path = os.path.join(webarena_mock_path, file_data['filepath'].lstrip('/'))
                        if os.path.exists(alt_log_path):
                            log_path = alt_log_path
                    
                    if os.path.exists(log_path):
                        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read()
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
        
        cursor.close()
        
        return {
            "instance_id": instance_id,
            "folder_path": folder_path,
            "description": description,
            "files": files,
            "log_content": log_content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying WebArena mock instance {instance_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

@app.get("/webarena/mock/files/{file_id}")
def get_webarena_mock_file(file_id: int):
    """Get a specific file from the WebArena mock dataset"""
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
        file_path = os.path.join(webarena_mock_path.parent, filepath)
        
        if not os.path.exists(file_path):
            # Try an alternative path as fallback
            alt_file_path = os.path.join(webarena_mock_path, file_record['filepath'].lstrip('/'))
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

if __name__ == "__main__":
    import uvicorn
    # Add reload=True for development convenience
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

