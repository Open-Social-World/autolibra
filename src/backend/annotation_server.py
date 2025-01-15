from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from osw_eval_core.data.trajectory import TrajectoryPoint
from pydantic import BaseModel
from typing import Any
from pathlib import Path
import random
from datetime import datetime

from osw_eval_core.data import MultiAgentDataset

from osw_eval_core.data import AnnotationSystem, AnnotationSpan

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize dataset and annotation system
DATASET_PATH = Path(".data/webarena")
ANNOTATION_PATH = Path(".data/annotations/webarena")

dataset = MultiAgentDataset(name="WebArena Interactions", base_path=DATASET_PATH)

annotation_system = AnnotationSystem(
    base_path=ANNOTATION_PATH,
    dataset_path=DATASET_PATH,
    project_name="WebArena User Feedback",
    description="Human feedback on web interaction trajectories",
    schema={"feedback_text": "string"},
)


class FeedbackSubmission(BaseModel):
    """Schema for feedback submission"""

    feedback_text: str


class AnnotationRequest(BaseModel):
    """Schema for annotation submission"""

    instanceId: str
    feedback: FeedbackSubmission


def format_trajectory_step(step: TrajectoryPoint) -> dict[str, Any]:
    """Format a trajectory step for frontend display"""
    if step.point_type == "OBSERVATION":
        if step.data_reference.media_type == "IMAGE":
            return {
                "type": "observation",
                "content": "Screenshot",
                "screenshot": step.data_reference.file_path,
            }
        else:
            return {
                "type": "observation",
                "content": step.data_reference.get("text", "")
                if isinstance(step.data, dict)
                else str(step.data),
            }
    else:
        return {
            "type": "action",
            "content": f"{step.data['function']}: {str(step.data['kwargs'])}",
        }


@app.get("/api/random-instance")
async def get_random_instance():
    """Get a random instance from the dataset"""
    try:
        # Get list of all instances
        instances = dataset.list_instances()
        if not instances:
            raise HTTPException(status_code=404, detail="No instances found")

        # Select random instance
        instance_id = random.choice(instances)
        instance_metadata = dataset.get_instance_metadata(instance_id)

        # Format trajectory data
        trajectory_steps = []
        for agent_id in instance_metadata.agents:
            trajectory = dataset.get_trajectory(instance_id, agent_id)
            for point in trajectory.points:
                trajectory_steps.append(format_trajectory_step(point))

        return {
            "id": instance_id,
            "task": instance_metadata.metadata["task"],
            "source_model": instance_metadata.metadata["source_model"],
            "trajectory": sorted(trajectory_steps, key=lambda x: x.get("timestamp", 0)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit-annotation")
async def submit_annotation(request: AnnotationRequest):
    """Submit annotation for an instance"""
    try:
        # Get annotator (create default if doesn't exist)
        annotator_id = "default_annotator"
        if annotator_id not in annotation_system.project.annotators:
            annotation_system.add_annotator(
                annotator_id=annotator_id, name="Default Annotator"
            )

        # Create annotation
        annotation_system.add_annotation(
            instance_id=request.instanceId,
            agent_id="web_browser",  # Main agent for web interactions
            annotator_id=annotator_id,
            content={"feedback_text": request.feedback.feedback_text},
            span=AnnotationSpan(start_time=datetime.now(), end_time=datetime.now()),
        )

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
