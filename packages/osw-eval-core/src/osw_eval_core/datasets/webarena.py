import subprocess
import zipfile
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any
import numpy as np
from PIL import Image

# Import our dataset classes
from osw_data import MultiAgentDataset, AgentMetadata, MediaType, PointType

from .base import BaseConverter, run_converter


class WebArenaConverter(BaseConverter):
    """Handles downloading and converting WebArena data to our dataset format"""

    def __init__(self, output_path: Path, source_path: Path):
        super().__init__(output_path, source_path)
        self.screenshots_path = self.source_path / "screenshots"

    def _setup_constants(self) -> None:
        """Setup WebArena-specific constants"""
        self.SPECIAL_KEYS = [
            "Enter",
            "Tab",
            "Control",
            "Shift",
            "Meta",
            "Backspace",
            "Delete",
            "Escape",
            "ArrowUp",
            "ArrowDown",
            "ArrowLeft",
            "ArrowRight",
            "PageDown",
            "PageUp",
            "Meta+a",
        ]
        self.ASCII_CHARSET = "".join(chr(x) for x in range(32, 128))
        self.FREQ_UNICODE_CHARSET = "".join(chr(x) for x in range(129, 1000))
        self._id2key = (
            self.SPECIAL_KEYS
            + list(self.ASCII_CHARSET)
            + list(self.FREQ_UNICODE_CHARSET)
            + ["\n"]
        )

    def download_data(self) -> None:
        """Download WebArena dataset files"""
        self.source_path.mkdir(parents=True, exist_ok=True)

        # Download trajectory file
        if not (self.source_path / "trajectories.jsonl").exists():
            self.logger.info("Downloading trajectory file...")
            traj_id = "1tvnaklsdSLx4Sp9Uc1spopcFpLktStO8"
            subprocess.run(
                ["gdown", traj_id, "-O", str(self.source_path / "trajectories.jsonl")],
                check=True,
            )

        # Download and extract screenshots
        if not self.screenshots_path.exists():
            self.logger.info("Downloading screenshots...")
            screenshots_id = "1TNfhApmiEIxiOcUqi4duvVWBaH5_m3By"
            zip_path = self.source_path / "screenshots.zip"

            subprocess.run(["gdown", screenshots_id, "-O", str(zip_path)], check=True)

            self.logger.info("Extracting screenshots...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(self.source_path)

            # Rename images directory to screenshots
            images_path = self.source_path / "images"
            if images_path.exists():
                images_path.rename(self.screenshots_path)

            # Cleanup zip file
            zip_path.unlink()

    def _convert_action(
        self, action: dict[str, Any], metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert WebArena action to our format"""
        function = action["action_name"]
        kwargs = {}

        if function == "stop":
            kwargs["answer"] = action.get("answer", "")
        elif function == "type":
            # text_indices = action["text"]
            # kwargs["text"] = ''.join([
            #     self._id2key[i]
            #     for i in text_indices
            #     if isinstance(i, int) and i < len(self._id2key) and i >= len(self.SPECIAL_KEYS)
            # ])
            kwargs["text"] = action["text"]
            kwargs["element_id"] = action["element_id"]
        elif function in ["hover", "click"]:
            kwargs["element_id"] = action["element_id"]
        elif function == "scroll":
            kwargs["dx"] = 0
            kwargs["dy"] = 100 if action["direction"].lower() == "down" else -100
        elif function in ["key_press", "press"]:
            kwargs["key_comb"] = action["key_comb"]
            function = "press"
        elif function in ["new_tab", "goto", "goto_url"]:
            kwargs["url"] = action["url"]
            function = "goto" if function == "goto_url" else function
        elif function in ["tab_focus", "page_focus"]:
            kwargs["page_number"] = action["page_number"]
            function = "tab_focus"
        elif function in ["go_back", "page_close", "go_forward"]:
            function = "tab_close" if function == "page_close" else function
        else:
            raise ValueError(f"Unknown function: {function}")

        return {
            "function": function,
            "kwargs": kwargs,
            "description": metadata.get("cot", ""),
        }

    def convert_to_dataset(self) -> None:
        """Convert WebArena data to our dataset format"""
        self.logger.info("Creating dataset...")

        # Initialize dataset
        dataset = MultiAgentDataset(
            name="WebArena Interactions",
            base_path=self.output_path,
            description="Web interaction trajectories from WebArena dataset",
        )

        # Read trajectories
        with open(self.source_path / "trajectories.jsonl", "r") as f:
            for line in f:
                raw_traj = json.loads(line)

                # Skip blacklisted sources
                if raw_traj["source"] in ["SteP"]:
                    continue

                # Create agent metadata
                agents_metadata = {
                    "agent": AgentMetadata(
                        agent_id="agent",
                        agent_type="web_agent",
                        capabilities=["navigation", "interaction"],
                        parameters={"viewport_size": (1280, 720)},
                    ),
                    "user": AgentMetadata(
                        agent_id="user",
                        agent_type="human",
                        capabilities=["instruction"],
                    ),
                }

                # Create instance
                instance_id = str(raw_traj["task_id"])
                instance_metadata = {
                    "task": raw_traj["intent"],
                    "source_model": raw_traj["source"],
                }

                instance_id = dataset.create_instance(
                    agents_metadata=agents_metadata, instance_metadata=instance_metadata
                )

                # Add initial task observation
                dataset.add_data_point(
                    instance_id=instance_id,
                    agent_id="user",
                    timestamp=datetime.now(),  # Using current time as original times not available
                    point_type=PointType.ACTION,
                    data={"text": raw_traj["intent"]},
                    media_type=MediaType.JSON,
                )

                # Process trajectory elements
                for element in raw_traj["trajectory"]:
                    timestamp = (
                        datetime.now()
                    )  # Using current time as original times not available

                    if "action" in element:
                        # Convert action
                        action_data = self._convert_action(
                            element["action"], element.get("metadata", {})
                        )

                        dataset.add_data_point(
                            instance_id=instance_id,
                            agent_id="agent",
                            timestamp=timestamp,
                            point_type=PointType.ACTION,
                            data=action_data,
                            media_type=MediaType.JSON,
                        )

                    elif "url" in element:
                        # Add URL and HTML observation
                        web_data = {"url": element["url"], "html": element["axtree"]}
                        dataset.add_data_point(
                            instance_id=instance_id,
                            agent_id="agent",
                            timestamp=timestamp,
                            point_type=PointType.OBSERVATION,
                            data=web_data,
                            media_type=MediaType.JSON,
                        )

                        # Add screenshot observation
                        screenshot_path = element["screenshot_path"].replace(
                            "demo_trajs/images/", str(self.screenshots_path)
                        )
                        if os.path.exists(screenshot_path):
                            # Load and convert image to numpy array
                            image = Image.open(screenshot_path)
                            image_array = np.array(image)

                            dataset.add_data_point(
                                instance_id=instance_id,
                                agent_id="agent",
                                timestamp=timestamp,
                                point_type=PointType.OBSERVATION,
                                data=image_array,
                                media_type=MediaType.IMAGE,
                                metadata={"original_path": screenshot_path},
                            )
                    else:
                        self.logger.warning(
                            f"Unknown element type in trajectory: {element}"
                        )

        self.logger.info("Dataset conversion complete!")
        dataset.close()


if __name__ == "__main__":
    source_path = Path(".data/raw/webarena")
    output_path = Path(".data/webarena")

    run_converter(WebArenaConverter, output_path, source_path)
