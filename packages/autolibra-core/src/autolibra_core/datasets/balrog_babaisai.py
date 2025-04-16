import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import csv
import shutil

# Import our dataset classes
from osw_data import MultiAgentDataset, AgentMetadata, PointType, MediaType

from .base import BaseConverter, run_converter
from osw_data.utils import file_pairs_list


class BalrogConverter(BaseConverter):
    """Handles downloading and converting Balrog data to our dataset format"""

    def __init__(self, output_path: Path, source_path: Path):
        super().__init__(output_path, source_path)

    def download_data(self) -> None:
        """Download Balrog dataset files"""
        self.source_path.mkdir(parents=True, exist_ok=True)

        # This only exists to satisfy the BaseConverter class

    @staticmethod
    def clean_csv_file(file_path: Path) -> None:
        """Remove NUL characters from a CSV file."""
        with open(file_path, "rb") as f:
            content = f.read()

        # Remove NUL characters
        content = content.replace(b"\x00", b"")

        with open(file_path, "wb") as f:
            f.write(content)

    def convert_to_dataset(self) -> None:
        """Convert Balrog data to autolibra dataset format"""
        self.logger.info("Creating Balrog dataset...")

        ref_time = datetime.now()  # Used for step_id

        # Obtain task from folder name
        task = self.source_path.name.split("_")[0].split("-")[-1]
        task = task[0].upper() + task[1:]

        # Initialize dataset
        dataset = MultiAgentDataset(
            name=f"{task}-Balrog",
            base_path=self.output_path,
            description=f"{task} trajectories from Balrog dataset",
        )

        # Get list of all directories within self.source_path
        subtasks: list[str] = [
            f.name for f in os.scandir(self.source_path) if f.is_dir()
        ]

        # Read trajectories (for given task type, exists n subdirs for task, each subdir has a trajectory file)

        # Iterate over folders in task_dir
        for subtask in subtasks:
            subtask_dir = self.source_path / subtask

            fpl = file_pairs_list(subtask_dir)

            for traj_file, jf in fpl:
                # Get pair of files in subtask_dir
                episode_number = str(str(jf).split("_")[-1].split(".")[0])
                # Clean the CSV file before processing
                csv_path = subtask_dir / f"{subtask}_run_{episode_number}.csv"
                self.clean_csv_file(csv_path)  # Call the clean_csv_file method
                # Load json file
                json_file = json.load(open(jf))

                prompt_data = json_file["prompt"]

                # Create agent metadata (this does not change within a subtask)
                agents_metadata = {
                    "agent": AgentMetadata(
                        agent_id="agent",
                        agent_type="game_agent",
                        capabilities=["navigation", "interaction"],
                    )
                }

                # Create instance metadata (this does not change within a subtask)
                instance_metadata = {
                    "task": json_file["task"],
                    "source_model": json_file["client"]["model_id"],
                    "prompt": prompt_data,
                }

                instance_id = dataset.create_instance(
                    agents_metadata=agents_metadata, instance_metadata=instance_metadata
                )
                self.logger.info(
                    f"Created instance {instance_id} for episode number {episode_number}"
                )

                gif_path = subtask_dir / f"episode_{episode_number}.gif"
                # Copy gif to output path
                gif_out_path = (
                    self.output_path
                    / "instances"
                    / instance_id
                    / f"episode_{episode_number}.gif"
                )
                shutil.copy(gif_path, gif_out_path)

                # Update instance_id with gif_path
                add_gif = {"gif_path": gif_out_path}
                dataset.update_instance_metadata(
                    instance_id=instance_id, new_meta=add_gif
                )

                with open(traj_file, newline="") as f:
                    reader = csv.reader(f, quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    # Skip header
                    next(reader)
                    for line in (
                        reader
                    ):  # Format of Step,Action,Reasoning,Observation,Reward,Done
                        line = [
                            field.replace("\n", " ").replace("\r", "") for field in line
                        ]

                        # Convert to datetime by adding to now
                        step_id = ref_time + timedelta(seconds=int(line[0]))
                        actions = line[1]
                        reasoning = line[2]
                        observations = line[3]
                        # Make new glyphs by running self.gm.glyph_id_to_rgb on each element of glyphs_raw in vectorized form

                        # step_id should be the same to allow reconstruction of the trajectory, but if this
                        # causes issues, should be fixed
                        act_obj = {"reasoning": reasoning, "text": actions}

                        obs_obj = {"observations": observations}

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
                            timestamp=step_id,  # Using step_id as timestamp
                            point_type=PointType.ACTION,
                            data=act_obj,
                            media_type=MediaType.JSON,
                        )

            self.logger.info(f"Dataset conversion complete for {task}")
            dataset.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Balrog Converter")
    parser.add_argument(
        "--filename",
        type=str,
        required=True,
        help="The name of the folder containing the Balrog-babaisai data for the given run",
    )

    filename = parser.parse_args().filename

    source_path = Path(f".data/raw/{filename}")  # Handle all balrog data in one folder
    output_path = Path(
        f".data/{filename.split('-')[-1]}"
    )  # Handle all balrog data in one folder

    run_converter(BalrogConverter, output_path, source_path)
