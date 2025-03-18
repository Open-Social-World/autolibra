from importlib import resources
import jinja2
from osw_data.dataset import DataInstance
from osw_data.trajectory import SymmetricTrajectory
from osw_eval_core.data.primitives import MetricTrainingInstance


def load_prompt_template(jinja_file: str) -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(jinja_file).open("r") as f:
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
