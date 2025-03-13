# Iterative Metric Creation
# Input: instances, trajectories, agents, and feedbacks
# Output: metrics
# Algorithm:
# metrics = propose_metrics(train_trajectories, train_feedbacks)
# while coverage improves
#     eval_results = llm_evaluator(train_trajectories, metrics)
#     uncovered_feedbacks, coverage = missing_points_detection(train_trajectories, eval_results)
#     new_metrics = propose_metrics(train_trajectories, uncovered_feedbacks)
#     metrics += new_metrics

import asyncio
from datetime import datetime
from openai import AsyncAzureOpenAI
from osw_data import Metric, MultiAgentDataset, MetricSet
from osw_data.annotation import AnnotationSystem
from osw_eval_core import run_llm_eval, behavior_clustering, feedback_grounding
from osw_eval_core.data import MetricTrainingInstance, Trait
from osw_eval_core.configs import OSWEvalSettings
from osw_eval_core.evaluators.coverage_evaluator import run_coverage_eval
from osw_eval_core.evaluators.llm_evaluator import _make_snake_case
import logfire


async def iterative_metric_creation(dataset_name: str) -> list[Metric]:
    settings = OSWEvalSettings()

    dataset = MultiAgentDataset(
        name="dataset",
        base_path=f".data/{dataset_name}",
    )

    annotation_system = AnnotationSystem(
        base_path=f".data/annotations/{dataset_name}",
    )

    metric_training_instances: list[MetricTrainingInstance] = []

    for instances in dataset.list_instances():
        instance = dataset.get_instance_metadata(instances)
        for agent_id in instance.agents:
            trajectory_annotations = annotation_system.get_trajectory_annotations(
                instance_id=instances, agent_id=agent_id
            )
            for annotation in trajectory_annotations.annotations:
                metric_training_instances.append(
                    MetricTrainingInstance(
                        task=instance.metadata["task"]
                        if "task" in instance.metadata
                        else "Task is described in the trajectory observation",
                        agent_id=agent_id,
                        trajectory=dataset.get_trajectory(instances, agent_id),
                        feedback=annotation.content["feedback"],
                    )
                )

    # initial state of metrics
    prev_coverage_rate: float = 0
    curr_coverage_rate: float = 0
    prev_metrics: list[Metric] = []
    curr_metrics: list[Metric] = []

    client = AsyncAzureOpenAI(
        api_key=settings.azure_api_key,
        api_version="2024-12-01-preview",
        azure_endpoint=settings.azure_endpoint,
    )

    logfire.instrument_openai(client)

    # initial aspects
    feedback_grounding_results = await asyncio.gather(
        *[
            feedback_grounding(instance, client)
            for instance in metric_training_instances
        ]
    )

    aspects = sum(
        feedback_grounding_results,
        [],
    )

    while curr_coverage_rate >= prev_coverage_rate:
        logfire.info(f"Current coverage rate: {curr_coverage_rate}")
        logfire.info(f"Previous coverage rate: {prev_coverage_rate}")
        prev_metrics = curr_metrics
        prev_coverage_rate = curr_coverage_rate

        curr_metrics = (
            prev_metrics + (await behavior_clustering(aspects, client)).metrics
        )

        eval_results = await run_llm_eval(
            metric_training_instances, metrics=curr_metrics, client=client
        )

        eval_scoring = [
            [
                int(getattr(eval_result, _make_snake_case(metric.name), 0))
                for metric in curr_metrics
            ]
            for eval_result in eval_results
        ]

        traits = [
            [
                Trait(
                    metric=metric,
                    rating=score,
                )
                for metric, score in zip(curr_metrics, eval_scoring_for_instance)
            ]
            for eval_scoring_for_instance in eval_scoring
        ]

        coverage_eval_results = await run_coverage_eval(
            instance_traits=traits,
            instances=metric_training_instances,
            client=client,
        )

        covered_aspects = sum([result[0] for result in coverage_eval_results])
        total_aspects = sum([result[1] for result in coverage_eval_results])
        _covered_traits = sum([result[2] for result in coverage_eval_results])
        _total_traits = sum([result[3] for result in coverage_eval_results])
        uncovered_aspects = sum([result[4] for result in coverage_eval_results], [])

        curr_coverage_rate = covered_aspects / total_aspects
        aspects = uncovered_aspects

    return prev_metrics


def save_metrics(metrics: list[Metric], path: str) -> None:
    metric_set = MetricSet(
        name="Metrics derived from webarena dataset",
        base_path=path,
        induced_from="webarena",
        version="0.1",
    )
    metric_set.add_metrics(metrics)


async def main() -> None:
    metrics = await iterative_metric_creation("sotopia")

    metric_set = MetricSet(
        name="Metrics derived from sotopia dataset",
        base_path=f".data/metrics/sotopia/{datetime.now().strftime('%m_%d_%H_%M')}",
        induced_from="sotopia",
        version="0.1",
    )

    metric_set.add_metrics(metrics)


if __name__ == "__main__":
    logfire.configure()
    asyncio.run(main())
