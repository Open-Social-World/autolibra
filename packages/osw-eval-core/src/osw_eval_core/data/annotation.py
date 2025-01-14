from pydantic import BaseModel, Field
from typing import Optional, Any
from pathlib import Path
from datetime import datetime
import json
import yaml
from uuid import uuid4

class Annotator(BaseModel):
    """Information about an annotator"""
    annotator_id: str
    name: str
    role: Optional[str] = None
    expertise_level: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class AnnotationSpan(BaseModel):
    """Represents a span of trajectory points being annotated"""
    start_time: datetime
    end_time: Optional[datetime] = None
    point_indices: Optional[list[int]] = None
    
    class Config:
        arbitrary_types_allowed = True

class Annotation(BaseModel):
    """Single annotation entry"""
    annotation_id: str = Field(default_factory=lambda: str(uuid4()))
    annotator_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    content: dict[str, Any]  # Flexible annotation content
    span: Optional[AnnotationSpan] = None
    confidence: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class TrajectoryAnnotations(BaseModel):
    """Collection of annotations for a specific trajectory"""
    instance_id: str
    agent_id: str
    annotations: list[Annotation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

class AnnotationProject(BaseModel):
    """Metadata for an annotation project"""
    project_id: str
    name: str
    description: str
    dataset_path: Path
    schema: dict[str, Any]  # Defines the expected annotation structure
    guidelines: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    annotators: dict[str, Annotator] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

class AnnotationSystem:
    """
    System for managing annotations separate from but linked to the dataset
    """
    def __init__(
        self,
        base_path: Path,
        dataset_path: Path,
        project_name: str,
        description: str = "",
        schema: Optional[dict[str, Any]] = None
    ):
        self.base_path = Path(base_path)
        self.annotations_path = self.base_path / "annotations"
        self.project_path = self.base_path / "project.yaml"
        
        # Initialize directory structure
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.annotations_path.mkdir(exist_ok=True)
        
        # Initialize or load project metadata
        self.project = self._init_project(
            project_name,
            description,
            dataset_path,
            schema or {}
        )

    def _init_project(
        self,
        name: str,
        description: str,
        dataset_path: Path,
        schema: dict[str, Any]
    ) -> AnnotationProject:
        """Initialize or load project metadata"""
        if self.project_path.exists():
            with open(self.project_path, 'r') as f:
                project_dict = yaml.safe_load(f)
                return AnnotationProject(**project_dict)
        else:
            project = AnnotationProject(
                project_id=str(uuid4()),
                name=name,
                description=description,
                dataset_path=dataset_path,
                schema=schema
            )
            self._save_project(project)
            return project

    def _save_project(self, project: AnnotationProject):
        """Save project metadata to disk"""
        with open(self.project_path, 'w') as f:
            yaml.dump(json.loads(project.json()), f)

    def add_annotator(
        self,
        annotator_id: str,
        name: str,
        role: Optional[str] = None,
        expertise_level: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None
    ):
        """Register a new annotator"""
        annotator = Annotator(
            annotator_id=annotator_id,
            name=name,
            role=role,
            expertise_level=expertise_level,
            metadata=metadata or {}
        )
        self.project.annotators[annotator_id] = annotator
        self._save_project(self.project)

    def _get_trajectory_annotation_path(
        self,
        instance_id: str,
        agent_id: str
    ) -> Path:
        """Get path for trajectory annotations"""
        return self.annotations_path / f"{instance_id}_{agent_id}.json"

    def get_trajectory_annotations(
        self,
        instance_id: str,
        agent_id: str
    ) -> TrajectoryAnnotations:
        """Get all annotations for a specific trajectory"""
        annotation_path = self._get_trajectory_annotation_path(instance_id, agent_id)
        if annotation_path.exists():
            with open(annotation_path, 'r') as f:
                return TrajectoryAnnotations.parse_raw(f.read())
        return TrajectoryAnnotations(
            instance_id=instance_id,
            agent_id=agent_id
        )

    def add_annotation(
        self,
        instance_id: str,
        agent_id: str,
        annotator_id: str,
        content: dict[str, Any],
        span: Optional[AnnotationSpan] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Add a new annotation to a trajectory
        
        Args:
            instance_id: ID of the dataset instance
            agent_id: ID of the agent
            annotator_id: ID of the annotator
            content: The annotation content
            span: Optional time span or point indices being annotated
            confidence: Optional confidence score
            metadata: Optional additional metadata
            
        Returns:
            annotation_id: ID of the created annotation
        """
        if annotator_id not in self.project.annotators:
            raise ValueError(f"Unknown annotator: {annotator_id}")
        
        # Create new annotation
        annotation = Annotation(
            annotator_id=annotator_id,
            content=content,
            span=span,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        # Add to trajectory annotations
        trajectory_annotations = self.get_trajectory_annotations(instance_id, agent_id)
        trajectory_annotations.annotations.append(annotation)
        
        # Save to disk
        annotation_path = self._get_trajectory_annotation_path(instance_id, agent_id)
        with open(annotation_path, 'w') as f:
            f.write(trajectory_annotations.json())
        
        return annotation.annotation_id

    def get_annotator_annotations(
        self,
        annotator_id: str
    ) -> dict[str, list[Annotation]]:
        """Get all annotations by a specific annotator"""
        annotations = {}
        for annotation_file in self.annotations_path.glob("*.json"):
            with open(annotation_file, 'r') as f:
                trajectory_annotations = TrajectoryAnnotations.parse_raw(f.read())
                
                # Filter annotations by annotator
                annotator_anns = [
                    ann for ann in trajectory_annotations.annotations
                    if ann.annotator_id == annotator_id
                ]
                
                if annotator_anns:
                    key = f"{trajectory_annotations.instance_id}_{trajectory_annotations.agent_id}"
                    annotations[key] = annotator_anns
        
        return annotations

    def get_annotations_by_time(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> dict[str, list[Annotation]]:
        """Get annotations within a time range"""
        annotations = {}
        for annotation_file in self.annotations_path.glob("*.json"):
            with open(annotation_file, 'r') as f:
                trajectory_annotations = TrajectoryAnnotations.parse_raw(f.read())
                
                # Filter annotations by time
                time_anns = [
                    ann for ann in trajectory_annotations.annotations
                    if ann.span and ann.span.start_time >= start_time and
                    (not end_time or ann.span.end_time <= end_time)
                ]
                
                if time_anns:
                    key = f"{trajectory_annotations.instance_id}_{trajectory_annotations.agent_id}"
                    annotations[key] = time_anns
        
        return annotations

# Example usage
def example_annotation_system():
    # Initialize annotation system
    annotation_system = AnnotationSystem(
        base_path=Path("./data/annotations"),
        dataset_path=Path("./data/robot_dataset"),
        project_name="Robot Behavior Analysis",
        description="Annotating robot behaviors and interactions",
        schema={
            "behavior_type": ["cooperative", "competitive", "neutral"],
            "success_rating": {"type": "float", "min": 0, "max": 1},
            "comments": "string"
        }
    )

    # Add annotators
    annotation_system.add_annotator(
        annotator_id="expert1",
        name="Dr. Smith",
        role="robotics_expert",
        expertise_level="expert"
    )

    annotation_system.add_annotator(
        annotator_id="expert2",
        name="Dr. Jones",
        role="hri_researcher",
        expertise_level="expert"
    )

    # Add annotations
    instance_id = "instance_001"
    agent_id = "robot_1"
    
    # Expert 1's annotation
    annotation_system.add_annotation(
        instance_id=instance_id,
        agent_id=agent_id,
        annotator_id="expert1",
        content={
            "behavior_type": "cooperative",
            "success_rating": 0.85,
            "comments": "Robot showed good adaptation to human partner"
        },
        span=AnnotationSpan(
            start_time=datetime.now(),
            end_time=datetime.now()
        ),
        confidence=0.9
    )

    # Expert 2's annotation
    annotation_system.add_annotation(
        instance_id=instance_id,
        agent_id=agent_id,
        annotator_id="expert2",
        content={
            "behavior_type": "cooperative",
            "success_rating": 0.78,
            "comments": "Good cooperation but some delays in responses"
        },
        span=AnnotationSpan(
            start_time=datetime.now(),
            end_time=datetime.now()
        ),
        confidence=0.85
    )

    # Query annotations
    trajectory_annotations = annotation_system.get_trajectory_annotations(
        instance_id=instance_id,
        agent_id=agent_id
    )

    # Get all annotations by expert1
    expert1_annotations = annotation_system.get_annotator_annotations("expert1")