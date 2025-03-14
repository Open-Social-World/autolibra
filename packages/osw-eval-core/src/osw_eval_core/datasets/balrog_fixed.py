import subprocess
import zipfile
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any
import csv
import PIL.Image
import numpy as np
import ast
import pickle as pkl
import shutil

import sys

# Import our dataset classes
from osw_data import MultiAgentDataset, AgentMetadata, PointType, MediaType

from .base import BaseConverter, run_converter
from osw_data.utils import file_pairs, file_pairs_list

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
        """Download Balrog dataset files"""
        self.source_path.mkdir(parents=True, exist_ok=True)

        # This assumes that the trajectory file exists and the repo is in its most recent state,
        # so this shouldn't ever be called

    def convert_to_dataset(self) -> None:
        """Convert Balrog data to osw dataset format"""
        self.logger.info("Creating Balrog dataset...")

        ref_time = datetime.now() # Used for step_id

        # Obtain task from folder name
        turn = self.source_path.name.split("_")[-1]
        task = self.source_path.name.split("_")[0].split("-")[-1]
        summary_path = self.source_path.with_name(self.source_path.name.replace(f"balrog-{task}", "balrog"))
        # Capitalize first letter
        task = task[0].upper() + task[1:]

        # Initialize dataset
        dataset = MultiAgentDataset(
            name=f"{task}-Balrog",
            base_path=self.output_path,
            description=f"{task} trajectories from Balrog dataset",
        )

        summary_json = json.load(open(summary_path / "summary.json"))

        # Get list of all directories within self.source_path
        subtasks: list[str] = [f.name for f in os.scandir(self.source_path) if f.is_dir()]

        # Read trajectories (for given task type, exists n subdirs for task, each subdir has a trajectory file)

        # Iterate over folders in task_dir
        for subtask in subtasks:
            subtask_dir = self.source_path / subtask

            fpl = file_pairs_list(subtask_dir)

            for traj_file, json_file in fpl:
                # Get pair of files in subtask_dir
                episode_number = str(str(json_file).split("_")[-1].split('.')[0])

                # Load json file
                json_file = json.load(open(json_file))

                prompt_data = json_file["prompt"]

                # Create agent metadata (this does not change within a subtask)
                agents_metadata = {
                    "agent": AgentMetadata(
                        agent_id="agent",
                        agent_type="game_agent",
                        capabilities=["navigation", "interaction"]
                    )
                }

                # Create instance metadata (this does not change within a subtask)
                instance_metadata={
                    "task": json_file["task"],
                    "source_model": json_file["client"]["model_id"],
                    "prompt": prompt_data,
                    }

                instance_id = dataset.create_instance(
                    agents_metadata=agents_metadata,
                    instance_metadata=instance_metadata
                )
                print(f"Created instance {instance_id}")


                gif_path = subtask_dir / f"episode_{episode_number}.gif"
                # Copy gif to output path
                gif_out_path = self.output_path / "instances" / instance_id / f"episode_{episode_number}.gif"
                shutil.copy(gif_path, gif_out_path)

                # Update instance_id with gif_path
                add_gif = {'gif_path': gif_out_path}
                dataset.update_instance_metadata(instance_id=instance_id, new_meta=add_gif)

                with open(traj_file, newline="") as f:
                    reader = csv.reader(f, quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    # Skip header
                    next(reader)
                    for line in reader: # Format of Step,Action,Reasoning,Observation,Reward,Done
                        line = [field.replace('\n', ' ').replace('\r', '') for field in line]

                        # Convert to datetime by adding to now
                        step_id = line[0] 
                        step_id = ref_time + timedelta(seconds=int(step_id))
                        actions = line[1]
                        reasoning = line[2]
                        observations = line[3]
                        # Make new glyphs by running self.gm.glyph_id_to_rgb on each element of glyphs_raw in vectorized form
                        # TODO: Figure if reasoning and observations should be added as separate data points
                        
                        # step_id should be the same to allow reconstruction of the trajectory, but if this
                        # causes issues, should be fixed
                        act_obj = {
                            "reasoning": reasoning,
                            "text": actions
                        }

                        obs_obj = {
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
    # source_path = Path(".data/raw/balrog-minihack_turn_0") # Handle all balrog data in one folder
    # output_path = Path(".data/minihack_turn_0") # Handle all balrog data in one folder
    source_path = Path(".data/raw/balrog-babaisai_turn_1") # Handle all balrog data in one folder
    output_path = Path(".data/babaisai_turn_1") # Handle all balrog data in one folder

    run_converter(BalrogConverter, output_path, source_path)
