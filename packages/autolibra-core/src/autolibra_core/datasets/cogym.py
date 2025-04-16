import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from osw_data import (
    MultiAgentDataset,
    AgentMetadata,
    MediaType,
    PointType,
    AnnotationSystem,
)
from .base import BaseConverter, run_converter


class HumanEvalFinal(BaseModel):
    env_id: str
    user_id: str
    agent_rating: int
    outcome_preference: str
    outcome_rating: int
    feedback: str


class HumanEval(BaseModel):
    final: HumanEvalFinal | None = Field(default=None)


class Action(BaseModel):
    role: str
    action: str
    action_status: str
    timestamp: str


class CoGymTrajectory(BaseModel):
    trajectory: list[Action]
    task: str
    human_eval: HumanEval


class CoGymConverter(BaseConverter):
    def __init__(
        self, output_path: Path, source_path: Path, annotation_path: Path | None = None
    ) -> None:
        super().__init__(output_path, source_path)
        self.annotation_path = annotation_path

    def download_data(self) -> None:
        trajectory_path = self.source_path / "trajectory"

        if not trajectory_path.exists():
            raise FileNotFoundError(f"Trajectory path {trajectory_path} does not exist")

    def convert_to_dataset(self) -> None:
        """Convert entire Sotopia dataset"""
        self.logger.info("Converting CoGym dataset")

        dataset = MultiAgentDataset(
            name="CoGym Interaction",
            base_path=self.output_path,
            description="CoGym dialog interactions",
        )

        if self.annotation_path is not None:
            annotation_system = AnnotationSystem(
                base_path=self.annotation_path,
                project_name="CoGym Annotations",
                annotation_schema={
                    "feedback": {
                        "type": "string",
                        "description": "Free-form text feedback on the trajectory",
                    }
                },
            )

            annotator_id = "Original CoGym Annotators"

            if annotator_id not in annotation_system.project.annotators:
                annotation_system.add_annotator(
                    annotator_id=annotator_id,
                    name=annotator_id,  # Using ID as name for simplicity
                )

        trajectory_path = self.source_path / "trajectory"

        for trajectory_file in trajectory_path.glob("*.json"):
            trajectory = CoGymTrajectory.model_validate_json(
                trajectory_file.read_text()
            )

            roles = list(set([action.role for action in trajectory.trajectory]))
            if len(roles) == 1:
                self.logger.warning(
                    f"Skipping trajectory with only one role: {trajectory_file}"
                )
                continue

            assert len(roles) == 2, f"Expected 2 roles, got {roles}"
            the_other_role = {
                roles[0]: roles[1],
                roles[1]: roles[0],
            }
            agent_role: str | None = None

            agents_metadata = {}
            for role in roles:
                if "user" in role:
                    agents_metadata[role] = AgentMetadata(
                        agent_id=role,
                        agent_type="human",
                        capabilities=["dialog"],
                    )
                    agent_role = the_other_role[role]
                else:
                    agents_metadata[role] = AgentMetadata(
                        agent_id=role,
                        agent_type="agent",
                        capabilities=["dialog", "code_generation"],
                    )

            assert agent_role

            instance_metadata = {
                "task": trajectory.task,
            }

            instance_id = dataset.create_instance(
                agents_metadata=agents_metadata, instance_metadata=instance_metadata
            )

            for action in trajectory.trajectory:
                dataset.add_data_point(
                    instance_id=instance_id,
                    agent_id=action.role,
                    point_type=PointType.ACTION,
                    media_type=MediaType.JSON,
                    data=action.action,
                    timestamp=datetime.datetime.fromisoformat(action.timestamp),
                )
                dataset.add_data_point(
                    instance_id=instance_id,
                    agent_id=the_other_role[action.role],
                    point_type=PointType.OBSERVATION,
                    media_type=MediaType.JSON,
                    data=action.action_status,
                    timestamp=datetime.datetime.fromisoformat(action.timestamp),
                )

            if (
                self.annotation_path is not None
                and trajectory.human_eval.final is not None
            ):
                annotation_system.add_annotation(
                    instance_id=instance_id,
                    agent_id=agent_role,
                    annotator_id=annotator_id,
                    content={"feedback": trajectory.human_eval.final.feedback},
                )

        dataset.close()


if __name__ == "__main__":
    source_path = Path(".data/raw/cogym")
    output_path = Path(".data/cogym")
    annotation_path = Path(".data/annotations/cogym")

    run_converter(
        CoGymConverter, output_path, source_path, annotation_path=annotation_path
    )
