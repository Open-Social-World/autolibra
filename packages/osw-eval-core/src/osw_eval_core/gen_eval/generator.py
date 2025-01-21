from datetime import datetime
from pathlib import Path
from typing import Any
from osw_data.dataset import DataInstance
from osw_data.metrics import Metric
from pydantic_ai import Agent
from pydantic_ai.models.vertexai import VertexAIModel
from importlib import resources

from osw_data import MultiAgentDataset, AnnotationSystem, SymmetricTrajectory

import jinja2


def load_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "generate_metrics_v2.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def load_renaming_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "rename_proposed_metrics.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def render_webarena_trajectory(
    trajectory: SymmetricTrajectory, metadata: DataInstance | None = None
) -> str:
    return "\n".join(
        [
            metadata.model_dump_json(),
        ]
        if metadata
        else []
        + [
            f"{'Observation' if p.point_type == 'observation' else 'Action'}: {trajectory.get_data_at(i)}"
            for i, p in enumerate(trajectory.points)
        ]
    )


def get_metrics(dataset_path: Path, annotation_path: Path) -> list[Metric]:
    template = load_template()

    dataset = MultiAgentDataset(
        name="dataset",  # This will be loaded from metadata
        base_path=dataset_path,
    )

    annotation_system = AnnotationSystem(
        base_path=annotation_path,
        project_name="Trajectory Annotation Project",
        description="Free-form text annotations of agent trajectories",
        annotation_schema={
            "feedback": {
                "type": "string",
                "description": "Free-form text feedback on the trajectory",
            }
        },
    )

    instances: list[dict[str, Any]] = []

    for instance_id in dataset.list_instances():
        instance = dataset.get_instance_metadata(instance_id)

        # Check each agent for unannotated trajectories
        for agent_id in instance.agents:
            trajectory_annotations = annotation_system.get_trajectory_annotations(
                instance_id=instance_id, agent_id=agent_id
            )

            for annotation in trajectory_annotations.annotations:
                instances.append(
                    dict(
                        trajectory=render_webarena_trajectory(
                            metadata=instance,
                            trajectory=dataset.get_trajectory(instance_id, agent_id),
                        ),
                        feedback=annotation.content,
                    )
                )

    # Generate the metrics
    prompt = template.render(instances=instances)

    model = VertexAIModel("gemini-2.0-flash-exp")
    agent = Agent(model, result_type=list[Metric])

    result = agent.run_sync(prompt)
    return result.data


class MetricTrainingInstance:
    def __init__(
        self, task: str, agent_id: str, trajectory: SymmetricTrajectory, feedback: str
    ):
        self.task = task
        self.agent_id = agent_id
        self.trajectory = trajectory
        self.feedback = feedback


def render_training_instance(training_instance: MetricTrainingInstance) -> str:
    return "\n".join(
        [
            f"The task is {training_instance.task}",
        ]
        + [
            f"{'Observation' if p.point_type == 'observation' else 'Action'}: {training_instance.trajectory.get_data_at(i)}"
            for i, p in enumerate(training_instance.trajectory.points)
        ]
    )


def propose_metrics(instances: list[MetricTrainingInstance]) -> list[Metric]:
    template = load_template()
    prompt = template.render(
        instances=[
            dict(
                trajectory=render_training_instance(training_instance),
                feedback=training_instance.feedback,
            )
            for training_instance in instances
        ]
    )

    with open("prompt.txt", "w") as f:
        f.write(prompt)

    model = VertexAIModel("gemini-2.0-flash-exp")
    agent = Agent(model, result_type=list[Metric])

    result = agent.run_sync(prompt)
    return result.data


if __name__ == "__main__":
    result = get_metrics(Path(".data/sotopia"), Path(".data/annotations/sotopia"))
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    # Save the metrics to a file
    with open(f".data/metrics/metrics-{timestamp}.jsonl", "w") as f:
        for metric in result:
            f.write(metric.model_dump_json() + "\n")
