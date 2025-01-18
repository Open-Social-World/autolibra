from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any, Optional, Union
from typing_extensions import Self
from enum import Enum
from pathlib import Path
import numpy as np
import numpy.typing as npt
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
    shape: tuple[int, ...] | None = None  # Optional for JSON data
    dtype: Optional[str] = None  # Optional for JSON data
    metadata: dict[str, Any] | None = None


class MediaStorage:
    """Handles storage and retrieval of both media data and JSON content"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._json_path = self.base_path / "json_data"
        self._json_path.mkdir(exist_ok=True)

    def store_data(
        self,
        data: Union[npt.ArrayLike, dict[str, Any], str],
        media_type: MediaType,
        trajectory_id: str,
        timestamp: str,
        point_type: PointType,
    ) -> MediaReference:
        """Store either media data or JSON content"""
        if media_type == MediaType.JSON:
            assert isinstance(
                data, (dict, str)
            ), "JSON data must be a dictionary or string"
            return self._store_json(data, trajectory_id, timestamp, point_type)
        else:
            assert isinstance(data, np.ndarray), "Media data must be a NumPy"
            return self._store_numpy(
                data, media_type, trajectory_id, timestamp, point_type
            )

    def _store_numpy(
        self,
        data: npt.NDArray[Any],
        media_type: MediaType,
        trajectory_id: str,
        timestamp: str,
        point_type: PointType,
    ) -> MediaReference:
        """Store media data in HDF5"""
        data_path = f"{trajectory_id}/{point_type}/{timestamp}/{uuid4()}.npy"

        Path(self.base_path / data_path).parent.mkdir(parents=True, exist_ok=True)
        np.save(self.base_path / data_path, data)

        return MediaReference(
            media_type=media_type,
            file_path=self.base_path / data_path,
            shape=data.shape,
            dtype=str(data.dtype),
        )

    def _store_json(
        self,
        data: dict[str, Any] | str,
        trajectory_id: str,
        timestamp: str,
        point_type: PointType,
    ) -> MediaReference:
        """Store JSON data"""
        json_file = self._json_path / f"{trajectory_id}_{point_type}_{timestamp}.json"

        with open(json_file, "w") as f:
            json.dump(data, f)

        return MediaReference(
            media_type=MediaType.JSON,
            file_path=json_file,
            metadata={"timestamp": timestamp},
        )

    def load_data(
        self, reference: MediaReference
    ) -> npt.NDArray[Any] | dict[str, Any] | str:
        """Load either media or JSON data from reference"""
        if reference.media_type == MediaType.JSON:
            with open(reference.file_path, "r") as f:
                json_data = json.load(f)
                assert isinstance(json_data, (dict, str)), "Invalid JSON data"
                return json_data
        else:
            data_path = reference.file_path
            data = np.load(data_path)
            assert isinstance(data, np.ndarray), "Invalid NumPy data"
            return data

    def close(self) -> None:
        pass


class TrajectoryPoint(BaseModel):
    """
    Single point in a trajectory that can be either observation or action
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: datetime
    agent_id: str
    point_type: PointType
    data_reference: MediaReference
    metadata: dict[str, Any] = Field(default_factory=dict)


class SymmetricTrajectory:
    """Trajectory with symmetric handling of observations and actions"""

    def __init__(self, trajectory_id: str, storage_path: Path):
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
                with open(self.points_file, "r") as f:
                    points_data = json.load(f)
                    self.points = [
                        TrajectoryPoint(
                            timestamp=datetime.fromisoformat(p["timestamp"]),
                            agent_id=p["agent_id"],
                            point_type=PointType(p["point_type"]),
                            data_reference=MediaReference.model_validate_json(
                                p["data_reference"]
                            ),
                            metadata=p.get("metadata", {}),
                        )
                        for p in points_data
                    ]
            except Exception as e:
                print(f"Error loading points: {e}")

    def _save_points(self) -> None:
        """Save trajectory points to disk"""
        points_data = [
            {
                "timestamp": p.timestamp.isoformat(),
                "agent_id": p.agent_id,
                "point_type": p.point_type.value,
                "data_reference": p.data_reference.model_dump_json(),
                "metadata": p.metadata,
            }
            for p in self.points
        ]

        with open(self.points_file, "w") as f:
            json.dump(points_data, f, indent=2)

    def add_point(
        self,
        timestamp: datetime,
        agent_id: str,
        point_type: PointType,
        data: npt.NDArray[Any] | dict[str, Any] | str,
        media_type: MediaType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add either observation or action point"""
        data_reference = self.media_storage.store_data(
            data=data,
            media_type=media_type,
            trajectory_id=self.trajectory_id,
            timestamp=timestamp.isoformat(),
            point_type=point_type,
        )

        point = TrajectoryPoint(
            timestamp=timestamp,
            agent_id=agent_id,
            point_type=point_type,
            data_reference=data_reference,
            metadata=metadata or {},
        )

        self.points.append(point)
        self._save_points()  # Save after each addition

    def get_data_at(self, index: int) -> npt.NDArray[Any] | dict[str, Any] | str:
        """Load data for a specific trajectory point"""
        point = self.points[index]
        return self.media_storage.load_data(point.data_reference)

    def get_points_by_type(self, point_type: PointType) -> list[TrajectoryPoint]:
        """Get all points of a specific type"""
        return [p for p in self.points if p.point_type == point_type]

    def get_points_by_agent(self, agent_id: str) -> list[TrajectoryPoint]:
        """Get all points for a specific agent"""
        return [p for p in self.points if p.agent_id == agent_id]

    def get_points_in_timerange(
        self, start_time: datetime, end_time: datetime
    ) -> list[TrajectoryPoint]:
        """Get points within a time range"""
        return [p for p in self.points if start_time <= p.timestamp <= end_time]

    def close(self) -> None:
        """Close media storage and ensure points are saved"""
        self._save_points()
        self.media_storage.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


def render_trajectory(trajectory: SymmetricTrajectory) -> list[dict[str, Any]]:
    """Render a trajectory as a list of dictionaries"""
    return [
        {
            "timestamp": p.timestamp.isoformat(),
            "agent_id": p.agent_id,
            "point_type": p.point_type,
            "data": trajectory.get_data_at(i),
            "metadata": p.metadata,
        }
        for i, p in enumerate(trajectory.points)
    ]
