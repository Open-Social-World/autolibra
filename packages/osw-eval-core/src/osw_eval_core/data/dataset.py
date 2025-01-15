import numpy as np
from pydantic import BaseModel, Field
from typing import Optional, Union, Any
from typing_extensions import Self
from pathlib import Path
import json
import yaml
from datetime import datetime
from uuid import uuid4

# Assume we're importing from the previous trajectory implementation
from .trajectory import SymmetricTrajectory, PointType, MediaType


class AgentMetadata(BaseModel):
    """Metadata for an individual agent"""

    agent_id: str
    agent_type: str
    capabilities: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    additional_info: dict[str, Any] = Field(default_factory=dict)


class DataInstance(BaseModel):
    """
    A single instance in the dataset, containing multiple agent trajectories
    """

    instance_id: str
    timestamp: datetime
    agents: dict[str, AgentMetadata]
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class DatasetMetadata(BaseModel):
    """Metadata for the entire dataset"""

    name: str
    version: str
    description: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    total_instances: int = 0
    agent_types: list[str] = Field(default_factory=list)
    schema_version: str = "1.0"
    additional_info: dict[str, Any] = Field(default_factory=dict)


class MultiAgentDataset:
    """
    Dataset managing multiple instances of multi-agent trajectories
    """

    def __init__(
        self, name: str, base_path: Path, description: str = "", version: str = "1.0"
    ):
        self.base_path = Path(base_path)
        self.instances_path = self.base_path / "instances"
        self.metadata_path = self.base_path / "metadata.yaml"

        # Initialize directory structure
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.instances_path.mkdir(exist_ok=True)

        # Initialize or load dataset metadata
        self.metadata = self._init_metadata(name, description, version)

        # Cache for open trajectories
        self._trajectory_cache: dict[str, dict[str, SymmetricTrajectory]] = {}

    def _init_metadata(
        self, name: str, description: str, version: str
    ) -> DatasetMetadata:
        """Initialize or load dataset metadata"""
        if self.metadata_path.exists():
            with open(self.metadata_path, "r") as f:
                metadata_dict = yaml.safe_load(f)
                return DatasetMetadata(**metadata_dict)
        else:
            metadata = DatasetMetadata(
                name=name, version=version, description=description
            )
            self._save_metadata(metadata)
            return metadata

    def _save_metadata(self, metadata: DatasetMetadata):
        """Save dataset metadata to disk"""
        with open(self.metadata_path, "w") as f:
            yaml.dump(json.loads(metadata.model_dump_json()), f)

    def create_instance(
        self,
        agents_metadata: dict[str, AgentMetadata],
        instance_metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Create a new instance in the dataset

        Args:
            agents_metadata: dictionary mapping agent_id to their metadata
            instance_metadata: Optional metadata for the instance

        Returns:
            instance_id: Unique identifier for the created instance
        """
        instance_id = str(uuid4())
        instance_path = self.instances_path / instance_id
        instance_path.mkdir(exist_ok=True)

        # Create instance metadata
        instance = DataInstance(
            instance_id=instance_id,
            timestamp=datetime.now(),
            agents=agents_metadata,
            metadata=instance_metadata or {},
        )

        # Save instance metadata
        with open(instance_path / "metadata.json", "w") as f:
            f.write(instance.model_dump_json())

        # Initialize trajectories for each agent
        for agent_id in agents_metadata:
            trajectory = SymmetricTrajectory(
                trajectory_id=f"{instance_id}_{agent_id}",
                storage_path=instance_path / agent_id,
            )
            if instance_id not in self._trajectory_cache:
                self._trajectory_cache[instance_id] = {}
            self._trajectory_cache[instance_id][agent_id] = trajectory

        # Update dataset metadata
        self.metadata.total_instances += 1
        self.metadata.agent_types = list(
            set(
                self.metadata.agent_types
                + [am.agent_type for am in agents_metadata.values()]
            )
        )
        self.metadata.updated_at = datetime.now()
        self._save_metadata(self.metadata)

        return instance_id

    def get_trajectory(self, instance_id: str, agent_id: str) -> SymmetricTrajectory:
        """Get trajectory for a specific agent in an instance"""
        if instance_id not in self._trajectory_cache:
            self._trajectory_cache[instance_id] = {}

        if agent_id not in self._trajectory_cache[instance_id]:
            instance_path = self.instances_path / instance_id
            if not instance_path.exists():
                raise ValueError(f"Instance {instance_id} does not exist")

            self._trajectory_cache[instance_id][agent_id] = SymmetricTrajectory(
                trajectory_id=f"{instance_id}_{agent_id}",
                storage_path=instance_path / agent_id,
            )

        return self._trajectory_cache[instance_id][agent_id]

    def get_instance_metadata(self, instance_id: str) -> DataInstance:
        """Get metadata for a specific instance"""
        instance_path = self.instances_path / instance_id
        if not instance_path.exists():
            raise ValueError(f"Instance {instance_id} does not exist")

        with open(instance_path / "metadata.json", "r") as f:
            return DataInstance.model_validate_json(f.read())

    def list_instances(self) -> list[str]:
        """list all instance IDs in the dataset"""
        return [p.name for p in self.instances_path.iterdir() if p.is_dir()]

    def get_instances_by_agent_type(self, agent_type: str) -> list[str]:
        """Get all instances that contain an agent of the specified type"""
        matching_instances = []
        for instance_id in self.list_instances():
            instance = self.get_instance_metadata(instance_id)
            if any(
                agent.agent_type == agent_type for agent in instance.agents.values()
            ):
                matching_instances.append(instance_id)
        return matching_instances

    def add_data_point(
        self,
        instance_id: str,
        agent_id: str,
        timestamp: datetime,
        point_type: PointType,
        data: Union[np.ndarray, dict, str],
        media_type: MediaType,
        metadata: Optional[dict] = None,
    ):
        """Add a data point to a specific agent's trajectory"""
        trajectory = self.get_trajectory(instance_id, agent_id)
        trajectory.add_point(
            timestamp=timestamp,
            agent_id=agent_id,
            point_type=point_type,
            data=data,
            media_type=media_type,
            metadata=metadata,
        )

    def close(self) -> None:
        """Close all open trajectories"""
        for instance_trajectories in self._trajectory_cache.values():
            for trajectory in instance_trajectories.values():
                trajectory.close()
        self._trajectory_cache.clear()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# Example usage
def example_dataset():
    # Create a new dataset
    dataset = MultiAgentDataset(
        name="Robot Interaction Dataset",
        base_path=Path("./data/robot_dataset"),
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
