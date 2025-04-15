from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import sys
from contextlib import asynccontextmanager
import re
import logging

from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType
from osw_data.metrics import MetricSet

# TEMPORARY Add the package directory to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent / "packages"))
# TEMPORARY Initialize dataset path
dataset_path = Path(__file__).parent.parent.parent / ".data" / "sotopia"

# Add at the top of the file
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize dataset and load labels
    global dataset, instance_labels, metric_set
    
    # Initialize dataset
    dataset = MultiAgentDataset(name="sotopia", base_path=dataset_path)
    
    # Load labels
    labels_path = dataset_path / "instance_labels.json"
    if labels_path.exists():
        with open(labels_path, "r") as f:
            instance_labels = json.load(f)
    else:
        print(f"Warning: Labels file not found at {labels_path}")
    
    # Try to load metrics
    try:
        metric_set = MetricSet(name="sotopia", base_path=dataset_path, induced_from="sotopia")
    except Exception as e:
        print(f"Warning: Could not load metrics: {str(e)}")
        metric_set = None
    
    yield
    
    # Shutdown: Clean up resources if needed
    # (No cleanup needed in this case)

app = FastAPI(title="Conversation Dataset API", lifespan=lifespan)

# Configure CORS to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # REPLACE with FRONTEND URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Trajectory Dataset API is running"}

@app.get("/trajectories")
def get_label():
    """Get all instance IDs with their labels"""
    if not dataset:
        raise HTTPException(status_code=500, detail="Dataset not initialized")
    
    instances = dataset.list_instances()
    result = []
    
    for instance_id in instances:
        try:
            # Get label if available
            label = instance_labels.get(instance_id, "Unlabeled")
            
            result.append({
                "instance_id": instance_id,
                "label": label
            })
        except Exception as e:
            print(f"Error loading instance {instance_id}: {str(e)}")
    
    return result

@app.get("/metrics/instances")
def get_metrics_by_instance():
    """Get a mapping of instance IDs to their available metrics"""
    metrics_file = Path(__file__).parent.parent.parent / ".data" / "metrics" / "sotopia" / "8_metrics" / "llm_eval_results.jsonl"
    
    if not metrics_file.exists():
        logger.warning(f"Metrics file not found at {metrics_file}")
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
    logger.info(f"Attempting to get metrics for instance='{instance_id}', agent='{agent_id}'")
    metrics_file = Path(__file__).parent.parent.parent / ".data" / "metrics" / "sotopia" / "8_metrics" / "llm_eval_results.jsonl"

    if not metrics_file.exists():
        logger.warning(f"Metrics file not found at {metrics_file} for instance {instance_id}, agent {agent_id}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

