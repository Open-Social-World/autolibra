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
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from osw_eval_core import (
    MetricTrainingInstance,
    feedback_grounding,
    behavior_clustering,
)


async def main(dataset_name: str) -> None:
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

    feedback_grounding_results = await asyncio.gather(
        *[feedback_grounding(instance) for instance in metric_training_instances]
    )

    with open("feedback_grounding_results.jsonl", "w") as f:
        for feedback_grounding_result in feedback_grounding_results:
            f.write(feedback_grounding_result.model_dump_json(indent=2))
            f.write("\n")

    behavior_clustering_results = await behavior_clustering(feedback_grounding_results)

    metric_set = MetricSet(
        name="Derived Metrics",
        base_path=f".data/metrics/{dataset_name}/{datetime.now().strftime('%m_%d_%H_%M')}",
        induced_from=dataset_name,
        version="0.1",
    )

    metric_set.add_metrics(behavior_clustering_results.metrics)


if __name__ == "__main__":
    asyncio.run(main("babaisai_turn_0"))
