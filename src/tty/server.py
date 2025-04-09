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

@app.get("/metrics")
def get_metrics():
    """Get all available metrics with their descriptions"""
    if not metric_set:
        return []
    
    result = []
    for metric_name, metric in metric_set.metrics.items():
        result.append({
            "name": metric_name,
            "explanation": metric.explanation,
            "good_behaviors": metric.good_behaviors,
            "bad_behaviors": metric.bad_behaviors
        })
    
    return result

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
        
        # Extract metrics from metadata
        metrics = {}
        metric_details = {}
        
        if metric_set and metadata and hasattr(metadata, "metadata") and isinstance(metadata.metadata, dict):
            if "rewards" in metadata.metadata and isinstance(metadata.metadata["rewards"], list):
                for i, reward in enumerate(metadata.metadata["rewards"]):
                    agent_id = list(metadata.agents.keys())[i] if i < len(metadata.agents) else f"Agent {i+1}"
                    metrics[agent_id] = reward
                    
                    # Process each metric to get its details
                    for metric_name in reward.keys():
                        normalized_name = metric_name.replace("/", "_")  # Match the normalization in Metric class
                        if normalized_name in metric_set.metrics:
                            metric = metric_set.metrics[normalized_name]
                            metric_details[metric_name] = {
                                "explanation": metric.explanation,
                                "good_behaviors": metric.good_behaviors,
                                "bad_behaviors": metric.bad_behaviors
                            }
        
        # Add debug logging
        logger.info(f"Available metrics in metric_set: {list(metric_set.metrics.keys()) if metric_set else 'None'}")
        logger.info(f"Metrics in reward: {list(reward.keys())}")
        logger.info(f"Extracted metric details: {metric_details}")
        
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
            "metrics": metrics,
            "metric_details": metric_details
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Instance not found: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

