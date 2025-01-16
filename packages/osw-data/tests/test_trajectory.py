from pathlib import Path
from osw_data.trajectory import (
    SymmetricTrajectory,
    MediaType,
    PointType,
    render_trajectory,
)

from datetime import datetime
import numpy as np


def test_mixed_trajectory() -> None:
    trajectory = SymmetricTrajectory(
        trajectory_id="robot_1", storage_path=Path("./data/trajectories")
    )

    # Add an observation with image data
    image = np.random.rand(480, 640, 3)
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.OBSERVATION,
        data=image,
        media_type=MediaType.IMAGE,
        metadata={"camera_id": "cam_1"},
    )

    # Add an action with JSON data
    action = {"command": "move", "parameters": {"direction": "forward", "speed": 1.0}}
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.ACTION,
        data=action,
        media_type=MediaType.JSON,
        metadata={"priority": "high"},
    )

    # Add an observation with JSON data
    json_obs = {"position": [1.0, 2.0, 3.0], "orientation": [0.0, 0.0, 1.0]}
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.OBSERVATION,
        data=json_obs,
        media_type=MediaType.JSON,
    )

    # Add an action with audio data
    audio_command = np.random.rand(16000)  # 1 second of audio at 16kHz
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.ACTION,
        data=audio_command,
        media_type=MediaType.AUDIO,
        metadata={"sample_rate": 16000},
    )

    render_trajectory(trajectory)

    trajectory.close()
