from pathlib import Path
from typing import Any
from pydantic import BaseModel
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


def render_webarena_trajectory(trajectory: SymmetricTrajectory) -> str:
    return "\n".join(
        [
            f"{'Observation' if p.point_type == 'observation' else 'Action'}: {trajectory.get_data_at(i)}"
            for i, p in enumerate(trajectory.points)
        ]
    )


class Metric(BaseModel):
    name: str
    explanation: str
    good_behavior: list[str]
    bad_behavior: list[str]


if __name__ == "__main__":
    template = load_template()

    dataset_path = Path(".data/cogym")
    annotation_path = Path(".data/annotations/cogym")

    dataset = MultiAgentDataset(
        name="dataset",  # This will be loaded from metadata
        base_path=dataset_path,
    )

    annotation_system = AnnotationSystem(
        base_path=annotation_path,
        dataset_path=dataset_path,
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
        any_agent_unannotated = False

        # Check each agent for unannotated trajectories
        for agent_id in instance.agents:
            trajectory_annotations = annotation_system.get_trajectory_annotations(
                instance_id=instance_id, agent_id=agent_id
            )

            for annotation in trajectory_annotations.annotations:
                instances.append(
                    dict(
                        trajectory=render_webarena_trajectory(
                            dataset.get_trajectory(instance_id, agent_id)
                        ),
                        feedback=annotation.content,
                    )
                )

    # Generate the metrics
    prompt = template.render(instances=instances[:50])

    model = VertexAIModel("gemini-2.0-flash-exp")
    agent = Agent(model, result_type=list[Metric])

    result = agent.run_sync(prompt)
    print(result.data)
