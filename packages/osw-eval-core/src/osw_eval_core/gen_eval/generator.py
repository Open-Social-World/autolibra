from osw_data.dataset import DataInstance
from importlib import resources

from osw_data import SymmetricTrajectory

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
            f"{'Observation' if p.point_type == 'observation' else 'Action'}: {str(training_instance.trajectory.get_data_at(i))[:8000]}"
            for i, p in enumerate(training_instance.trajectory.points)
        ]
    )
