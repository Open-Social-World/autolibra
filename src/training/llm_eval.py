import asyncio
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from osw_eval_core import (
    MetricTrainingInstance,
    run_llm_eval,
)
from osw_eval_core.evaluators.coverage_evaluator_v2 import run_coverage_eval
from osw_eval_core.evaluators.llm_evaluator import _make_snake_case


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
                        feedback=annotation.content,
                    )
                )

    eval_results = await run_llm_eval(
        metric_training_instances, list(metric_set.metrics.values())
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

    coverage_results = await run_coverage_eval(
        metric_set.metrics.values(), eval_scoring, metric_training_instances
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
    asyncio.run(
        main(
            dataset_name="babaisai_turn_0",
            metric_path=".data/metrics/babaisai_turn_0/03_06_23_26",
        ),
    )
