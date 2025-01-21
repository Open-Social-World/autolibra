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
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_eval_core import MetricTrainingInstance, feedback_grounding


async def main() -> None:
    dataset = MultiAgentDataset(
        name="dataset",
        base_path=".data/webarena",
    )

    annotation_system = AnnotationSystem(
        base_path=".data/annotations/webarena",
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
                        task=instance.metadata["task"],
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


if __name__ == "__main__":
    asyncio.run(main())
