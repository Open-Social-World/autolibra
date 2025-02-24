import subprocess
import zipfile
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

import sys

# Import our dataset classes
from osw_data import MultiAgentDataset, AgentMetadata, PointType, MediaType

from .base import BaseConverter, run_converter
from ..data.utils import download_github_folder, file_pairs

class BalrogConverter(BaseConverter):
    """Handles downloading and converting Balrog data to our dataset format"""

    def __init__(self, output_path: Path, source_path: Path):
        super().__init__(output_path, source_path)

    def _setup_constants(self) -> None:
        """Setup Balrog-specific constants, i.e. action space"""

        #TODO: Currently unused, do we need explicit conversion if format already correct?

        # ACTIONS = {
        #     "north": "move north",
        #     "east": "move east",
        #     "south": "move south",
        #     "west": "move west",
        #     "northeast": "move northeast",
        #     "southeast": "move southeast",
        #     "southwest": "move southwest",
        #     "northwest": "move northwest",
        #     "far north": "move far north",
        #     "far east": "move far east",
        #     "far south": "move far south",
        #     "far west": "move far west",
        #     "far northeast": "move far northeast",
        #     "far southeast": "move far southeast",
        #     "far southwest": "move far southwest",
        #     "far northwest": "move far northwest",
        #     "up": "go up the stairs",
        #     "down": "go down the stairs",
        #     "wait": "rest one move while doing nothing",
        #     "more": "display more of the message",
        #     "apply": "apply (use) a tool",
        #     "close": "close an adjacent door",
        #     "open": "open an adjacent door",
        #     "eat": "eat something",
        #     "force": "force a lock",
        #     "kick": "kick an enemy or a locked door or chest",
        #     "loot": "loot a box on the floor",
        #     "pickup": "pick up things at the current location if there are any",
        #     "pray": "pray to the gods for help",
        #     "puton": "put on an accessory",
        #     "quaff": "quaff (drink) something",
        #     "search": "search for hidden doors and passages",
        #     "zap": "zap a wand",
        # }
        # self.SPECIAL_KEYS = list(ACTIONS.keys())
        # self._id2key = (
        #     self.SPECIAL_KEYS
        # )

    def download_data(self) -> None:
        """Download MiniHack-Balrog dataset files"""
        self.source_path.mkdir(parents=True, exist_ok=True)

        # Download trajectory file
        if not (self.source_path / "minihack").exists():
            self.logger.info("Downloading trajectory file for MiniHack-Balrog...")
            raise NotImplementedError("Download not yet implemented")

    def convert_to_dataset(self) -> None:
        """Convert Balrog data to osw dataset format"""
        self.logger.info("Creating Balrog dataset...")

        ref_time = datetime.now() # Used for step_id

        # Iterate over task folders in source_path
        for task in os.listdir(self.source_path):
            if task == "minihack":
                self.source_path = self.source_path / task
            elif task == "babaisai":
                self.source_path = self.source_path / task / 'env'
            else:
                raise NotImplementedError(f"Task type {task} not currently supported")

            # Initialize dataset
            dataset = MultiAgentDataset(
                name=f"{task}-Balrog",
                base_path=self.output_path,
                description=f"{task} trajectories from Balrog dataset",
            )

            summary_json = json.load(open(self.source_path / "summary.json"))
            subtasks: list[str] = list(summary_json["tasks"].keys())

            # Read trajectories (for given task type, exists n subdirs for task, each subdir has a trajectory file)

            # Iterate over folders in task_dir
            for subtask in subtasks:
                subtask_dir = self.source_path / subtask

                traj_file, json_file = file_pairs(subtask_dir)

                # Load json file
                json_file = json.load(open(subtask_dir / json_file))

                # Create agent metadata (this does not change within a subtask)
                agents_metadata = {
                    "agent": AgentMetadata(
                        agent_id="agent",
                        agent_type="game_agent",
                        capabilities=["navigation", "interaction"]
                    ),
                    "user": AgentMetadata(
                        agent_id="user",
                        agent_type="human",
                        capabilities=["instruction"],
                    ),
                }

                # Create instance metadata (this does not change within a subtask)
                instance_metadata={
                    "task": json_file["task"],
                    "source_model": json_file["client"]["model_id"],
                    }

                instance_id = dataset.create_instance(
                    agents_metadata=agents_metadata,
                    instance_metadata=instance_metadata
                )
                with open(traj_file) as f:
                    for line in f: # Format of Step,Action,Reasoning,Observation,Reward,Done

                        # Convert to datetime by adding to now
                        step_id = line.split(",")[0] 
                        step_id = ref_time + datetime.timedelta(seconds=int(step_id))
                        actions = line.split(",")[1]
                        reasoning = line.split(",")[2]
                        observations = line.split(",")[3]

                        # TODO: Figure if reasoning and observations should be added as separate data points
                        # step_id should be the same to allow reconstruction of the trajectory, but if this
                        # causes issues, should be fixed
                        act_obj = {
                            "text": actions
                        }

                        obs_obj = {
                            "reasoning": reasoning,
                            "observations": observations
                        }

                        dataset.add_data_point(
                                instance_id=instance_id,
                                agent_id="agent",
                                timestamp=step_id,
                                point_type=PointType.OBSERVATION,
                                data=obs_obj,
                                media_type=MediaType.JSON,
                            )

                        dataset.add_data_point(
                            instance_id=instance_id,
                            agent_id="agent",
                            timestamp=step_id, # Using step_id as timestamp
                            point_type=PointType.ACTION,
                            data=act_obj,
                            media_type=MediaType.JSON,
                        )

                self.logger.info(f"Dataset conversion complete for {task}")
                dataset.close()


if __name__ == "__main__":
    source_path = Path(".data/raw/balrog") # Handle all balrog data in one folder
    output_path = Path(".data/balrog") # Handle all balrog data in one folder

    run_converter(BalrogConverter, output_path, source_path)
