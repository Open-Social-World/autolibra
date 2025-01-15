import datetime
from pathlib import Path

from pydantic import BaseModel, Field
from ..data import MultiAgentDataset, AgentMetadata, MediaType, PointType
from .base import BaseConverter, run_converter

from huggingface_hub import hf_hub_download  # type:ignore[import-untyped]


class TwoAgentEpisodeWithScenarioBackgroundGoals(BaseModel):
    episode_id: str = Field()
    environment_id: str = Field()
    agent_ids: list[str] = Field()
    experiment_tag: str = Field()
    experiment_model_name_pairs: list[str] = Field()
    raw_messages: list[list[tuple[str, str, str]]] = Field()
    raw_rewards: list[tuple[float, dict[str, float]] | float] = Field()
    raw_rewards_prompt: str = Field()
    scenario: str = Field()
    codename: str = Field()
    agents_background: dict[str, str] = Field()
    social_goals: dict[str, str] = Field()
    social_interactions: str = Field()
    reasoning: str = Field()
    rewards: list[dict[str, float]] = Field()


class SotopiaConverter(BaseConverter):
    def __init__(self, output_path: Path, source_path: Path):
        super().__init__(output_path, source_path)

    def download_data(self) -> None:
        self.source_path.mkdir(parents=True, exist_ok=True)

        # Download trajectory file
        if not (self.source_path / "sotopia_episodes_v1_hf.jsonl").exists():
            hf_hub_download(
                repo_id="cmu-lti/sotopia",
                filename="sotopia_episodes_v1_hf.jsonl",
                repo_type="dataset",
                local_dir=self.source_path,
            )

    def convert_to_dataset(self) -> None:
        """Convert entire Sotopia dataset"""
        self.logger.info("Converting Sotopia dataset")

        dataset = MultiAgentDataset(
            name="Sotopia Interaction",
            base_path=self.output_path,
            description="Sotopia dialog interactions",
        )

        with open(self.source_path / "sotopia_episodes_v1.jsonl", "r") as f:
            for line in f:
                episode = (
                    TwoAgentEpisodeWithScenarioBackgroundGoals.model_validate_json(line)
                )

                agent_names = episode.agents_background.keys()
                agent_backgrounds = episode.agents_background
                models = episode.experiment_model_name_pairs
                agents_metadata = {}
                for agent_name in agent_names:
                    agents_metadata[agent_name] = AgentMetadata(
                        agent_id=agent_name,
                        agent_type="sotopia_agent",
                        capabilities=[
                            "speek",
                            "non-verbal communication",
                            "physical actions",
                        ],
                        parameters={"background": agent_backgrounds[agent_name]},
                    )
                instance_id = episode.episode_id

                instance_metadata = {
                    "scenario": episode.scenario,
                    "experiment_tag": episode.experiment_tag,
                    "models": models,
                    "rewards": episode.rewards,
                }
                if models != ["gpt-4", "gpt-4", "gpt-4"]:
                    self.logger.info(
                        f"Skipping instance {instance_id} because of model mismatch"
                    )
                    continue

                for rewards in episode.rewards:
                    overall_reward = rewards["overall_score"]
                    if overall_reward < 1.6:
                        self.logger.info(
                            f"Skipping instance {instance_id} because of low reward"
                        )
                        continue

                instance_id = dataset.create_instance(
                    agents_metadata=agents_metadata, instance_metadata=instance_metadata
                )

                for turn in episode.raw_messages:
                    for from_agent, to_agent, message in turn:
                        timestamp = datetime.datetime.now()
                        action_timestamp = datetime.datetime.now()
                        if from_agent == "Environment":
                            dataset.add_data_point(
                                instance_id=instance_id,
                                agent_id=to_agent,
                                point_type=PointType.OBSERVATION,
                                data={"content": message},
                                media_type=MediaType.JSON,
                                timestamp=timestamp,
                            )
                        elif message != "did nothing":
                            dataset.add_data_point(
                                instance_id=instance_id,
                                agent_id=from_agent,
                                point_type=PointType.ACTION,
                                data={"content": message},
                                media_type=MediaType.JSON,
                                timestamp=action_timestamp,
                            )

        dataset.close()


if __name__ == "__main__":
    source_path = Path(".data/raw/sotopia")
    output_path = Path(".data/sotopia")

    run_converter(SotopiaConverter, output_path, source_path)
