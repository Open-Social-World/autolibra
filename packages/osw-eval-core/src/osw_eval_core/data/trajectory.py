from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Union
from enum import Enum
from pathlib import Path
import numpy as np
import h5py
import json

class MediaType(str, Enum):
    """Types of media data supported"""
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    NUMPY = "numpy"
    JSON = "json"

class PointType(str, Enum):
    """Type of trajectory point"""
    OBSERVATION = "observation"
    ACTION = "action"

class MediaReference(BaseModel):
    """Reference to media data stored on disk"""
    media_type: MediaType
    file_path: Path
    shape: Optional[tuple] = None  # Optional for JSON data
    dtype: Optional[str] = None    # Optional for JSON data
    metadata: dict | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class MediaStorage:
    """Handles storage and retrieval of both media data and JSON content"""
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._h5_file = None
        self._json_path = self.base_path / "json_data"
        self._json_path.mkdir(exist_ok=True)

    @property
    def h5_file(self):
        if self._h5_file is None:
            self._h5_file = h5py.File(self.base_path / "media_data.h5", "a")
        return self._h5_file

    def store_data(self, 
                  data: Union[np.ndarray, dict, str],
                  media_type: MediaType,
                  trajectory_id: str,
                  timestamp: str,
                  point_type: PointType) -> MediaReference:
        """Store either media data or JSON content"""
        if media_type == MediaType.JSON:
            assert isinstance(data, (dict, str)), "JSON data must be a dictionary or string"
            return self._store_json(data, trajectory_id, timestamp, point_type)
        else:
            assert isinstance(data, np.ndarray), "Media data must be a NumPy"
            return self._store_media(data, media_type, trajectory_id, timestamp, point_type)

    def _store_media(self, 
                    data: np.ndarray,
                    media_type: MediaType,
                    trajectory_id: str,
                    timestamp: str,
                    point_type: PointType) -> MediaReference:
        """Store media data in HDF5"""
        dataset_path = f"{trajectory_id}/{point_type}/{timestamp}"
        
        if dataset_path in self.h5_file:
            del self.h5_file[dataset_path]
        
        _ = self.h5_file.create_dataset(
            dataset_path,
            data=data,
            compression="gzip",
            compression_opts=4
        )
        
        return MediaReference(
            media_type=media_type,
            file_path=self.base_path / "media_data.h5",
            shape=data.shape,
            dtype=str(data.dtype),
            metadata={
                "dataset_path": dataset_path,
                "compression": "gzip",
                "compression_level": 4
            }
        )

    def _store_json(self,
                   data: Union[dict, str],
                   trajectory_id: str,
                   timestamp: str,
                   point_type: PointType) -> MediaReference:
        """Store JSON data"""
        json_file = self._json_path / f"{trajectory_id}_{point_type}_{timestamp}.json"
        
        with open(json_file, 'w') as f:
            json.dump(data, f)
        
        return MediaReference(
            media_type=MediaType.JSON,
            file_path=json_file,
            metadata={"timestamp": timestamp}
        )

    def load_data(self, reference: MediaReference) -> Union[np.ndarray, dict]:
        """Load either media or JSON data from reference"""
        if reference.media_type == MediaType.JSON:
            with open(reference.file_path, 'r') as f:
                return json.load(f)
        else:
            dataset_path = reference.metadata["dataset_path"]
            return self.h5_file[dataset_path][:]

    def close(self):
        if self._h5_file is not None:
            self._h5_file.close()
            self._h5_file = None

class TrajectoryPoint(BaseModel):
    """
    Single point in a trajectory that can be either observation or action
    """
    timestamp: datetime
    agent_id: str
    point_type: PointType
    data_reference: MediaReference
    metadata: dict = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

class SymmetricTrajectory:
    """Trajectory with symmetric handling of observations and actions"""
    def __init__(self, 
                 trajectory_id: str,
                 storage_path: Path):
        self.trajectory_id = trajectory_id
        self.media_storage = MediaStorage(storage_path)
        self.points: list[TrajectoryPoint] = []
        self.points_file = storage_path / "points.json"
        
        # Load points if they exist
        self._load_points()

    def _load_points(self) -> None:
        """Load trajectory points from disk"""
        if self.points_file.exists():
            try:
                with open(self.points_file, 'r') as f:
                    points_data = json.load(f)
                    self.points = [
                        TrajectoryPoint(
                            timestamp=datetime.fromisoformat(p['timestamp']),
                            agent_id=p['agent_id'],
                            point_type=PointType(p['point_type']),
                            data_reference=MediaReference.model_validate_json(p['data_reference']),
                            metadata=p.get('metadata', {})
                        )
                        for p in points_data
                    ]
            except Exception as e:
                print(f"Error loading points: {e}")

    def _save_points(self) -> None:
        """Save trajectory points to disk"""
        points_data = [
            {
                'timestamp': p.timestamp.isoformat(),
                'agent_id': p.agent_id,
                'point_type': p.point_type.value,
                'data_reference': p.data_reference.model_dump_json(),
                'metadata': p.metadata
            }
            for p in self.points
        ]
        
        with open(self.points_file, 'w') as f:
            json.dump(points_data, f, indent=2)

    def add_point(self,
                 timestamp: datetime,
                 agent_id: str,
                 point_type: PointType,
                 data: Union[np.ndarray, dict, str],
                 media_type: MediaType,
                 metadata: Optional[dict] = None) -> None:
        """Add either observation or action point"""
        data_reference = self.media_storage.store_data(
            data=data,
            media_type=media_type,
            trajectory_id=self.trajectory_id,
            timestamp=timestamp.isoformat(),
            point_type=point_type
        )
        
        point = TrajectoryPoint(
            timestamp=timestamp,
            agent_id=agent_id,
            point_type=point_type,
            data_reference=data_reference,
            metadata=metadata or {}
        )
        
        self.points.append(point)
        self._save_points()  # Save after each addition

    def get_data_at(self, index: int) -> Union[np.ndarray, dict]:
        """Load data for a specific trajectory point"""
        point = self.points[index]
        return self.media_storage.load_data(point.data_reference)

    def get_points_by_type(self, point_type: PointType) -> list[TrajectoryPoint]:
        """Get all points of a specific type"""
        return [p for p in self.points if p.point_type == point_type]

    def get_points_by_agent(self, agent_id: str) -> list[TrajectoryPoint]:
        """Get all points for a specific agent"""
        return [p for p in self.points if p.agent_id == agent_id]

    def get_points_in_timerange(self, 
                              start_time: datetime, 
                              end_time: datetime) -> list[TrajectoryPoint]:
        """Get points within a time range"""
        return [
            p for p in self.points 
            if start_time <= p.timestamp <= end_time
        ]

    def close(self):
        """Close media storage and ensure points are saved"""
        self._save_points()
        self.media_storage.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Example usage
def example_mixed_trajectory():
    trajectory = SymmetricTrajectory(
        trajectory_id="robot_1",
        storage_path=Path("./data/trajectories")
    )

    # Add an observation with image data
    image = np.random.rand(480, 640, 3)
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.OBSERVATION,
        data=image,
        media_type=MediaType.IMAGE,
        metadata={"camera_id": "cam_1"}
    )

    # Add an action with JSON data
    action = {
        "command": "move",
        "parameters": {"direction": "forward", "speed": 1.0}
    }
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.ACTION,
        data=action,
        media_type=MediaType.JSON,
        metadata={"priority": "high"}
    )

    # Add an observation with JSON data
    json_obs = {
        "position": [1.0, 2.0, 3.0],
        "orientation": [0.0, 0.0, 1.0]
    }
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.OBSERVATION,
        data=json_obs,
        media_type=MediaType.JSON
    )

    # Add an action with audio data
    audio_command = np.random.rand(16000)  # 1 second of audio at 16kHz
    trajectory.add_point(
        timestamp=datetime.now(),
        agent_id="robot_1",
        point_type=PointType.ACTION,
        data=audio_command,
        media_type=MediaType.AUDIO,
        metadata={"sample_rate": 16000}
    )

    trajectory.close()