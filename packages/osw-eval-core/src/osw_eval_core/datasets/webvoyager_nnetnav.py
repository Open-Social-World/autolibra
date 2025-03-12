import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any
import numpy as np
from PIL import Image

# Import our dataset classes
from osw_data import MultiAgentDataset, AgentMetadata, MediaType, PointType
from osw_data.annotation import AnnotationSystem

from .base import BaseConverter, run_converter


class WebVoyagerNNetNavConverter(BaseConverter):
    """Handles downloading and converting WebArena data to our dataset format"""

    def __init__(
        self, output_path: Path, source_path: Path, annotation_path: Path | None = None
    ) -> None:
        super().__init__(output_path, source_path)
        self.screenshots_path = self.source_path / "screenshots"
        self.annotation_path = annotation_path

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
        pass

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

        task_id2instance_id: dict[str, str] = {}

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

                task_id2instance_id[raw_traj["task_id"]] = instance_id

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

        if self.annotation_path:
            annotation_system = AnnotationSystem(
                base_path=self.annotation_path,
                project_name="WebVoyager Annotations",
                description="Free-form text annotations of agent trajectories for WebVoyager",
                annotation_schema={
                    "feedback": {
                        "type": "string",
                        "description": "Free-form text feedback on the trajectory",
                    }
                },
            )

            annotation_system.add_annotator(
                annotator_id="Shikhar",
                name="Shikhar Murty",
            )
            with open(self.source_path / "feedback.json", "r") as f:
                task_id2feedback = json.load(f)
                for task_id in task_id2feedback:
                    instance_id_or_none = task_id2instance_id.get(task_id)
                    if instance_id_or_none:
                        annotation_system.add_annotation(
                            instance_id=instance_id_or_none,
                            agent_id="agent",
                            content={"feedback": task_id2feedback[task_id]},
                            annotator_id="Shikhar",
                        )
        self.logger.info("Dataset conversion complete!")
        dataset.close()


if __name__ == "__main__":
    source_path = Path(".data/raw/webvoyager-nnetnav")
    output_path = Path(".data/webvoyager-nnetnav")
    annotation_path = Path(".data/annotations/webvoyager-nnetnav")

    run_converter(
        WebVoyagerNNetNavConverter,
        output_path,
        source_path,
        annotation_path=annotation_path,
    )
