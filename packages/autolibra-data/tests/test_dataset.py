from autolibra_data import MultiAgentDataset, AgentMetadata, MediaType, PointType
from datetime import datetime
import numpy as np
from pathlib import Path


def test_dataset() -> None:
    Path("/tmp/data/robot_dataset").mkdir(parents=True, exist_ok=True)

    # Create a new dataset
    dataset = MultiAgentDataset(
        name="Robot Interaction Dataset",
        base_path=Path("/tmp/data/robot_dataset"),
        description="Multi-agent robot interaction scenarios",
        version="1.0",
    )

    # Define agents for an instance
    agents_metadata = {
        "robot_1": AgentMetadata(
            agent_id="robot_1",
            agent_type="manipulator",
            capabilities=["grasp", "move"],
            parameters={"max_speed": 1.0},
        ),
        "robot_2": AgentMetadata(
            agent_id="robot_2",
            agent_type="mobile_base",
            capabilities=["navigate"],
            parameters={"max_velocity": 0.5},
        ),
    }

    # Create an instance
    instance_id = dataset.create_instance(
        agents_metadata=agents_metadata,
        instance_metadata={"scenario": "collaborative_assembly"},
    )

    # Add data points for each agent
    timestamp = datetime.now()

    # Add observation for robot_1
    image_data = np.random.rand(480, 640, 3)
    dataset.add_data_point(
        instance_id=instance_id,
        agent_id="robot_1",
        timestamp=timestamp,
        point_type=PointType.OBSERVATION,
        data=image_data,
        media_type=MediaType.IMAGE,
        metadata={"camera_id": "cam_1"},
    )

    # Add action for robot_2
    action_data = {"command": "move_to", "position": [1.0, 2.0, 0.0]}
    dataset.add_data_point(
        instance_id=instance_id,
        agent_id="robot_2",
        timestamp=timestamp,
        point_type=PointType.ACTION,
        data=action_data,
        media_type=MediaType.JSON,
    )

    # Close the dataset
    dataset.close()
