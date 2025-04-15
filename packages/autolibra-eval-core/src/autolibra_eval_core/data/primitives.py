from typing import Literal
from autolibra_data.trajectory import SymmetricTrajectory
from pydantic import BaseModel, Field
from autolibra_data import Metric


class Aspect(BaseModel):
    feedback: str
    behavior: str
    is_positive: bool = Field(
        description="Whether the feedback is positive or negative."
    )


class Trait(BaseModel):
    metric: Metric
    rating: Literal[-1, 0, 1]


class MetricTrainingInstance:
    def __init__(
        self, task: str, agent_id: str, trajectory: SymmetricTrajectory, feedback: str
    ):
        self.task = task
        self.agent_id = agent_id
        self.trajectory = trajectory
        self.feedback = feedback
