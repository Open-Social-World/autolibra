import asyncio
from openai import AsyncAzureOpenAI
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from autolibra_core import (
    run_llm_eval,
)
from autolibra_core.data import MetricTrainingInstance
from autolibra_core.configs import AutoLibraEvalSettings
from autolibra_core.data.primitives import Trait
from autolibra_core.evaluators.coverage_evaluator import run_coverage_eval
from autolibra_core.evaluators.llm_evaluator import _make_snake_case


async def main(dataset_name: str, metric_path: str) -> None:
    dataset = MultiAgentDataset(
        name="dataset",
        base_path=f".data/{dataset_name}",
    )

    annotation_system = AnnotationSystem(
        base_path=f".data/annotations/{dataset_name}",
    )

    metric_set = MetricSet(
        name="",
        base_path=metric_path,
        induced_from=dataset_name,
    )

    settings = AutoLibraEvalSettings()

    client = AsyncAzureOpenAI(
        api_key=settings.azure_api_key,
        api_version="2024-12-01-preview",
        azure_endpoint=settings.azure_endpoint,
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
                        feedback=str(annotation.content),
                    )
                )

    eval_results = await run_llm_eval(
        metric_training_instances, list(metric_set.metrics.values()), client=client
    )

    eval_scoring = [
        [
            int(getattr(eval_result, _make_snake_case(metric.name), 0))
            for metric in metric_set.metrics.values()
        ]
        for eval_result in eval_results
    ]

    with open("llm_eval_results.jsonl", "w") as f:
        for eval_result in eval_results:
            f.write(eval_result.model_dump_json())
            f.write("\n")

    traits = [
        [
            Trait(
                metric=metric,
                rating=score,
            )
            for metric, score in zip(
                metric_set.metrics.values(), eval_scoring_for_instance
            )
        ]
        for eval_scoring_for_instance in eval_scoring
    ]

    coverage_results = await run_coverage_eval(
        instance_traits=traits,
        instances=metric_training_instances,
        client=client,
    )

    covered, total = 0, 0
    redundant, total_traits = 0, 0

    for coverage_result in coverage_results:
        covered += coverage_result[0]
        total += coverage_result[1]
        redundant += coverage_result[2]
        total_traits += coverage_result[3]

    print(f"Coverage: {covered}/{total}")
    print(f"Redundancy: {redundant}/{total_traits}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Balrog Converter")
    parser.add_argument(
        "--filename",
        type=str,
        required=True,
        help="The name of the folder containing the data for the given run, including the date subfolder",
    )

    filename = parser.parse_args().filename
    filename_no_date = filename.split("/")[0]

    asyncio.run(
        main(
            dataset_name=filename_no_date,
            metric_path=f".data/metrics/{filename}",
        ),
    )
