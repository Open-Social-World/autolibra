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

from osw_data import Metric, MultiAgentDataset, MetricSet
from osw_data.annotation import AnnotationSystem
from osw_eval_core import MetricTrainingInstance, llm_evaluation


def iterative_metric_creation(
    metric_training_instances: list[MetricTrainingInstance],
) -> list[Metric]:
    # metrics = propose_metrics(metric_training_instances)
    metric_set = MetricSet(
        name="Metrics derived from webarena dataset",
        base_path=".data/metrics_webarena/one-pass-generation-01-19-01",
        induced_from="webarena",
        version="0.1",
    )
    metrics = metric_set.metrics
    while True:
        eval_results = llm_evaluation(metric_training_instances, list(metrics.values()))
        # uncovered_feedbacks, coverage = missing_points_detection(train_trajectories, eval_results)
        # if coverage == 0:
        #     break
        # new_metrics = propose_metrics(train_trajectories, uncovered_feedbacks)
        # metrics += new_metrics
        for eval_result in eval_results:
            print(eval_result)
        # print("Evaluation results: ", eval_results)
        break
    return metrics


def save_metrics(metrics: list[Metric], path: str):
    metric_set = MetricSet(
        name="Metrics derived from webarena dataset",
        base_path=path,
        induced_from="webarena",
        version="0.1",
    )
    metric_set.add_metrics(metrics)


if __name__ == "__main__":
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
                        feedback=annotation.content,
                    )
                )

    iterative_metric_creation(metric_training_instances)
    # save_metrics(
    #     iterative_metric_creation(metric_training_instances),
    #     path=".data/metrics_webarena/" + datetime.now().strftime("%Y%m%d%H%M%S")
    # )
