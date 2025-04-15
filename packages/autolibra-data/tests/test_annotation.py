from datetime import datetime
from autolibra_data.annotation import AnnotationSpan, AnnotationSystem
from pathlib import Path


def test_annotation_system() -> None:
    # Initialize annotation system
    annotation_system = AnnotationSystem(
        base_path=Path("/tmp/data/annotations"),
        project_name="Robot Behavior Analysis",
        description="Annotating robot behaviors and interactions",
        annotation_schema={
            "behavior_type": ["cooperative", "competitive", "neutral"],
            "success_rating": {"type": "float", "min": 0, "max": 1},
            "comments": "string",
        },
    )

    # Add annotators
    annotation_system.add_annotator(
        annotator_id="expert1",
        name="Dr. Smith",
        role="robotics_expert",
        expertise_level="expert",
    )

    annotation_system.add_annotator(
        annotator_id="expert2",
        name="Dr. Jones",
        role="hri_researcher",
        expertise_level="expert",
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
            "comments": "Robot showed good adaptation to human partner",
        },
        span=AnnotationSpan(start_time=datetime.now(), end_time=datetime.now()),
        confidence=0.9,
    )

    # Expert 2's annotation
    annotation_system.add_annotation(
        instance_id=instance_id,
        agent_id=agent_id,
        annotator_id="expert2",
        content={
            "behavior_type": "cooperative",
            "success_rating": 0.78,
            "comments": "Good cooperation but some delays in responses",
        },
        span=AnnotationSpan(start_time=datetime.now(), end_time=datetime.now()),
        confidence=0.85,
    )
