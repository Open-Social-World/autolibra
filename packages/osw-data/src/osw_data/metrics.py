from datetime import datetime
from pathlib import Path
from typing import Annotated
from pydantic import AfterValidator, BaseModel, Field


class MetricSetMetadata(BaseModel):
    created_at: datetime = Field(default_factory=datetime.now)
    name: str
    metric_names: list[str] = Field(default_factory=list)
    induced_from: str | None = Field(default_factory=lambda: None)
    version: str | None = Field(default_factory=lambda: None)


class Metric(BaseModel):
    good_behaviors: list[str] = Field(default_factory=list)
    bad_behaviors: list[str] = Field(default_factory=list)
    explanation: str
    name: Annotated[str, AfterValidator(lambda x: x.replace("/", "_"))]


class MetricSet:
    """
    A set of metrics for evaluating trajectories
    """

    def __init__(
        self,
        name: str,
        base_path: Path | str,
        induced_from: str,
        version: str | None = None,
    ):
        self.base_path = Path(base_path)
        self.metrics_path = self.base_path / "metrics"
        self.metadata_path = self.base_path / "metadata.json"

        # Initialize directory structure
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.metrics_path.mkdir(exist_ok=True)
        self.metrics: dict[str, Metric] = {}

        # Initialize or load dataset metadata
        self.metadata = self._init_metadata(name, induced_from, version)
        self.load_metrics()

    def _init_metadata(
        self, name: str, induced_from: str, version: str | None
    ) -> MetricSetMetadata:
        """Initialize or load dataset metadata"""
        if self.metadata_path.exists():
            with open(self.metadata_path, "r") as f:
                return MetricSetMetadata.model_validate_json(f.read())
        else:
            metadata = MetricSetMetadata(
                name=name, induced_from=induced_from, version=version
            )
            self._save_metadata(metadata)
            return metadata

    def _save_metadata(self, metadata: MetricSetMetadata) -> None:
        with open(self.metadata_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))

    def _save_metrics(
        self,
    ) -> None:
        for name, metric in self.metrics.items():
            metric_path = self.metrics_path / f"{name}.json"
            with open(metric_path, "w") as f:
                f.write(metric.model_dump_json(indent=2))

    def load_metrics(self) -> None:
        for metric in self.metadata.metric_names:
            metric_path = self.metrics_path / f"{metric}.json"
            with open(metric_path, "r") as f:
                self.metrics[metric] = Metric.model_validate_json(f.read())

    def add_metrics(self, metrics: list[Metric]) -> None:
        for metric in metrics:
            if metric.name in self.metrics:
                raise ValueError(f"Metric with name {metric.name} already exists")
            self.metrics[metric.name] = metric
            metric_path = self.metrics_path / f"{metric.name}.json"
            with open(metric_path, "w") as f:
                f.write(metric.model_dump_json(indent=2))

        self.metadata.metric_names = list(self.metrics.keys())
        self._save_metadata(self.metadata)

    def get_metric(self, name: str) -> Metric:
        if name not in self.metrics:
            raise ValueError(f"Metric with name {name} does not exist")
        metric_path = self.metrics_path / f"{name}.json"
        with open(metric_path, "r") as f:
            return Metric.model_validate_json(f.read())
