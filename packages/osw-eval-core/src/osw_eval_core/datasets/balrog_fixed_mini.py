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
from osw_data.utils import file_pairs

class BalrogConverter(BaseConverter):
    """Handles downloading and converting Balrog data to our dataset format"""

    def __init__(self, output_path: Path, source_path: Path):
        super().__init__(output_path, source_path)

    @staticmethod
    def clean_csv_file(file_path: Path) -> None:
        """Remove NUL characters from a CSV file."""
        with open(file_path, "rb") as f:
            content = f.read()
        
        # Remove NUL characters
        content = content.replace(b'\x00', b'')
        
        with open(file_path, "wb") as f:
            f.write(content)

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

        ref_time = datetime.now()  # Used for step_id

        # Obtain task from folder name
        turn = self.source_path.name.split("_")[-1]
        task = self.source_path.name.split("_")[0].split("-")[-1]
        summary_path = self.source_path.with_name(self.source_path.name.replace(f"balrog-{task}", "balrog"))
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

        # Iterate over folders in task_dir
        for subtask in subtasks:
            subtask_dir = self.source_path / subtask

            # Find all files with matching suffixes (00, 01, 02)
            for suffix in ["00", "01", "02"]:
                # Construct file paths for the current group
                gif_path = subtask_dir / f"episode_{suffix}.gif"
                csv_path = subtask_dir / f"{subtask}_run_{suffix}.csv"  # Use subtask name + _run_ + suffix
                json_path = subtask_dir / f"{subtask}_run_{suffix}.json"  # Use subtask name + _run_ + suffix
                pkl_path = subtask_dir / f"{subtask}_run_{suffix}.pkl"  # Use subtask name + _run_ + suffix

                # Check if all required files exist for this group
                if not (gif_path.exists() and csv_path.exists() and json_path.exists() and pkl_path.exists()):
                    self.logger.warning(f"Missing files for suffix {suffix} in {subtask_dir}")
                    continue

                # Clean the CSV file before processing
                self.clean_csv_file(csv_path)  # Call the clean_csv_file method

                # Load json file
                json_file = json.load(open(json_path))

                # Create agent metadata (this does not change within a subtask)
                agents_metadata = {
                    "agent": AgentMetadata(
                        agent_id="agent",
                        agent_type="game_agent",
                        capabilities=["navigation", "interaction"]
                    )
                }

                # Create instance metadata (this does not change within a subtask)
                instance_metadata = {
                    "task": json_file["task"],
                    "source_model": json_file["client"]["model_id"],
                }

                # Create a unique instance ID for this group
                instance_id = dataset.create_instance(
                    agents_metadata=agents_metadata,
                    instance_metadata=instance_metadata
                )
                self.logger.info(f"Created instance {instance_id} for suffix {suffix}")

                # Copy GIF to output path
                gif_out_path = self.output_path / "instances" / instance_id / f"episode_{suffix}.gif"
                shutil.copy(gif_path, gif_out_path)

                # Update instance metadata with GIF path
                add_gif = {'gif_path': gif_out_path}
                dataset.update_instance_metadata(instance_id=instance_id, new_meta=add_gif)

                # Process the CSV file
                with open(csv_path, newline="") as f:
                    reader = csv.reader(f, quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    next(reader)  # Skip header
                    for line in reader:
                        line = [field.replace('\n', ' ').replace('\r', '') for field in line]

                        step_id = line[0]
                        step_id = ref_time + timedelta(seconds=int(step_id))
                        actions = line[1]
                        reasoning = line[2]
                        observations = line[3]

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
                            timestamp=step_id,
                            point_type=PointType.ACTION,
                            data=act_obj,
                            media_type=MediaType.JSON,
                        )

        self.logger.info(f"Dataset conversion complete for {task}")
        dataset.close()


if __name__ == "__main__":
    # source_path = Path(".data/raw/balrog-minihack_turn_0") # Handle all balrog data in one folder
    # output_path = Path(".data/minihack_turn_0") # Handle all balrog data in one folder
    source_path = Path(".data/raw/balrog-minihack_turn_1") # Handle all balrog data in one folder
    output_path = Path(".data/minihack_turn_1") # Handle all balrog data in one folder

    run_converter(BalrogConverter, output_path, source_path)
