from importlib import resources
import time
from typing import Literal
import jinja2
from osw_data.annotation import AnnotationSystem
from osw_data.dataset import MultiAgentDataset
from pydantic import BaseModel
from pydantic_ai import Agent
import pydantic_ai
import pydantic_core
from .generator import MetricTrainingInstance, render_webarena_trajectory
from pathlib import Path
from osw_data import DataInstance, SymmetricTrajectory, Metric
from abc import abstractmethod

from pydantic_ai.models import Model
from pydantic_ai.models.vertexai import VertexAIModel
from openai import AzureOpenAI

from ..configs import OSWEvalSettings


class CoverageEvaluationResult(BaseModel):
    reasoning: str
    rating: int


class EvaluationResult(BaseModel):
    evaluation_metric_name: str
    reasoning: str
    rating: Literal["positive", "negative", "N/A"]


class EvaluationResultArray(BaseModel):
    results: list[EvaluationResult]


class Evaluator(object):
    def __init__(self, metric: Metric):
        self.metric = metric

    @abstractmethod
    def __call__(
        self,
        data_instance: DataInstance,
        agent_id: str,
        trajectory: SymmetricTrajectory,
    ) -> EvaluationResult:
        raise NotImplementedError


def _load_llm_as_a_judge_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "llm_as_a_judge_evaluator.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def _load_llm_as_a_judge_v2_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "llm_as_a_judge_evaluator_v2.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def _load_coverage_evaluation_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "coverage_evaluation.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def _load_metrics_from_file(file: Path) -> list[Metric]:
    with file.open("r") as f:
        return [Metric.model_validate_json(line) for line in f.readlines()]


class LLMasaJudgeEvaluator(Evaluator):
    def __init__(self, metric: Metric, model: Model):
        super().__init__(metric)
        self.model = model
        self.template = _load_llm_as_a_judge_template()
        self.agent = Agent(
            model=model,
            result_type=EvaluationResult,
        )

    def __call__(
        self,
        data_instance: DataInstance,
        agent_id: str,
        trajectory: SymmetricTrajectory,
    ) -> EvaluationResult:
        instance = dict(
            task_metadata=data_instance.metadata,
            agent_metadata=data_instance.agents[agent_id],
            trajectory=render_webarena_trajectory(trajectory=trajectory),
            metric=self.metric.model_dump_json(),
        )
        prompt = self.template.render(
            instance=instance,
        )

        wait_time = 1
        for i in range(10):
            try:
                result = self.agent.run_sync(user_prompt=prompt)
                break
            except pydantic_ai.exceptions.UnexpectedModelBehavior as e:
                print(f"Model error: {e}")
                time.sleep(wait_time)
                wait_time *= 2
            except pydantic_core._pydantic_core.ValidationError as e:
                print(f"Validation error: {e}")

        return result.data


def llm_evaluation(
    instances: list[MetricTrainingInstance], metrics: list[Metric]
) -> list[list[EvaluationResult]]:
    template = _load_llm_as_a_judge_v2_template()

    eval_results: list[list[EvaluationResult]] = []

    for instance in instances:
        prompt = template.render(
            instance=dict(
                task_metadata=instance.task,
                agent_metadata=instance.agent_id,
                trajectory=render_webarena_trajectory(instance.trajectory),
                feedback=instance.feedback,
                metrics=[metric.model_dump() for metric in metrics],
            )
        )

        settings = OSWEvalSettings()

        client = AzureOpenAI(
            api_key=settings.azure_api_key,
            api_version="2024-10-21",
            azure_endpoint=settings.azure_endpoint,
        )

        # wait_time = 1
        while True:
            # try:
            result = client.beta.chat.completions.parse(
                model="gpt-4o-241120",  # replace with the model deployment name of your gpt-4o 2024-08-06 deployment
                messages=[
                    {"role": "system", "content": "Following the user instruction."},
                    {"role": "user", "content": prompt},
                ],
                response_format=EvaluationResultArray,
            )

            #     print(f"Model error: {e}")
            #     time.sleep(wait_time)
            #     wait_time *= 2
            #     continue

            # if len(result.data) == len(metrics):
            break

        if not result.choices[0].message.parsed:
            raise ValueError("Failed to parse the response.")
        else:
            eval_results.append(result.choices[0].message.parsed.results)

    return eval_results


def evaluate_dataset_with_metrics(
    dataset_path: Path, annotation_path: Path, metrics: list[Metric]
) -> None:
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

    coverage_list: list[CoverageEvaluationResult] = []

    for instance_id in dataset.list_instances():
        instance = dataset.get_instance_metadata(instance_id)

        # Check each agent for unannotated trajectories
        for agent_id in instance.agents:
            trajectory_annotations = annotation_system.get_trajectory_annotations(
                instance_id, agent_id
            )

            for annotation in trajectory_annotations.annotations:
                quantative_evaluation = ""
                for metric in metrics:
                    evaluator = LLMasaJudgeEvaluator(
                        metric=metric, model=VertexAIModel("gemini-1.5-pro")
                    )
                    result = evaluator(
                        data_instance=instance,
                        agent_id=agent_id,
                        trajectory=dataset.get_trajectory(instance_id, agent_id),
                    )
                    print(result)
                    quantative_evaluation += (
                        f"{metric.name}, {metric.explanation}: {result.rating}\n"
                    )

                coverage_prompt = _load_coverage_evaluation_template().render(
                    instance=dict(
                        task_metadata=instance.metadata,
                        agent_metadata=instance.agents[agent_id],
                        feedback=annotation.content,
                        metrics=quantative_evaluation,
                    )
                )

                wait_time = 1
                for i in range(10):
                    try:
                        coverage = Agent(
                            model=VertexAIModel("gemini-1.5-pro"),
                            result_type=CoverageEvaluationResult,
                        ).run_sync(user_prompt=coverage_prompt)
                        break
                    except pydantic_ai.exceptions.UnexpectedModelBehavior as e:
                        print(f"Model error: {e}")
                        time.sleep(wait_time)
                        wait_time *= 2
                    except pydantic_core._pydantic_core.ValidationError as e:
                        print(f"Validation error: {e}")

                coverage_list.append(coverage.data)
    print(sum([coverage.rating for coverage in coverage_list]) / len(coverage_list))


if __name__ == "__main__":
    metrics = _load_metrics_from_file(
        Path(".data/metrics/metrics-cogym-2025-01-17-13-04-07.jsonl")
    )
    evaluate_dataset_with_metrics(
        dataset_path=Path(".data/webarena"),
        annotation_path=Path(".data/annotations/webarena"),
        metrics=metrics,
    )
