import datetime
from pathlib import Path
from pydantic import BaseModel, Field
from osw_data import MultiAgentDataset, AgentMetadata, MediaType, PointType, AnnotationSystem
from .base import BaseConverter, run_converter

class MiniHackAction(BaseModel):
    role: str
    action: str
    action_status: str
    timestamp: str

class MiniHackTrajectory(BaseModel):
    trajectory: list[MiniHackAction]
    task: str
    human_eval: dict | None = Field(default=None)

class MiniHackConverter(BaseConverter):
    def __init__(self, output_path: Path, source_path: Path, annotation_path: Path | None = None) -> None:
        super().__init__(output_path, source_path)
        self.annotation_path = annotation_path

    def download_data(self) -> None:
        trajectory_path = self.source_path / "trajectory"
        if not trajectory_path.exists():
            raise FileNotFoundError(f"Trajectory path {trajectory_path} does not exist")

    def convert_to_dataset(self) -> None:
        self.logger.info("Converting MiniHack dataset")
        dataset = MultiAgentDataset(name="MiniHack Interaction", base_path=self.output_path, description="MiniHack dialog interactions")

        trajectory_path = self.source_path / "trajectory"
        for trajectory_file in trajectory_path.glob("*.json"):
            trajectory = MiniHackTrajectory.model_validate_json(trajectory_file.read_text())
            roles = list(set([action.role for action in trajectory.trajectory]))
            if len(roles) < 2:
                self.logger.warning(f"Skipping trajectory with insufficient roles: {trajectory_file}")
                continue

            agents_metadata = {role: AgentMetadata(agent_id=role, agent_type="agent", capabilities=["dialog"]) for role in roles}
            instance_id = dataset.create_instance(agents_metadata=agents_metadata, instance_metadata={"task": trajectory.task})

            for action in trajectory.trajectory:
                dataset.add_data_point(instance_id=instance_id, agent_id=action.role, point_type=PointType.ACTION, media_type=MediaType.JSON, data=action.action, timestamp=datetime.datetime.fromisoformat(action.timestamp))

        dataset.close()

if __name__ == "__main__":
    source_path = Path("/Users/anantsinha/.data/raw/balrog-minihack")
    output_path = Path("/Users/anantsinha/.data")
    

    run_converter(MiniHackConverter, output_path, source_path)