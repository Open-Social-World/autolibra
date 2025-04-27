import asyncio
from openai import AsyncAzureOpenAI
from osw_data import MultiAgentDataset
from osw_data.metrics import MetricSet
from autolibra_core import (
    run_llm_eval,
)
from autolibra_core.data import MetricTrainingInstance
from autolibra_core.configs import AutoLibraEvalSettings


async def main(dataset_name: str, metric_path: str) -> None:
    dataset = MultiAgentDataset(
        name="dataset",
        base_path=f".data/{dataset_name}",
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
            metric_training_instances.append(
                MetricTrainingInstance(
                    task=instance.metadata["task"]
                    if "task" in instance.metadata
                    else "Task is described in the trajectory observation",
                    agent_id=agent_id,
                    trajectory=dataset.get_trajectory(instances, agent_id),
                    feedback="",
                )
            )

    eval_results = await run_llm_eval(
        metric_training_instances, list(metric_set.metrics.values()), client=client
    )

    with open("llm_eval_results.jsonl", "w") as f:
        for eval_result in eval_results:
            f.write(eval_result.model_dump_json())
            f.write("\n")


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
