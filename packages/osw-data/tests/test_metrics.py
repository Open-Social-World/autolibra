import pytest
from pathlib import Path
import json
from typing import Generator

# Import the classes to test
from osw_data.metrics import MetricSet, Metric, MetricSetMetadata


@pytest.fixture
def sample_metric() -> Metric:
    """Fixture that returns a sample metric"""
    return Metric(
        name="test_metric",
        explanation="A test metric",
        good_behaviors=["good1", "good2"],
        bad_behaviors=["bad1", "bad2"],
    )


@pytest.fixture
def sample_metrics() -> list[Metric]:
    """Fixture that returns a list of sample metrics"""
    return [
        Metric(
            name="metric1",
            explanation="First test metric",
            good_behaviors=["good1"],
            bad_behaviors=["bad1"],
        ),
        Metric(
            name="metric2",
            explanation="Second test metric",
            good_behaviors=["good2"],
            bad_behaviors=["bad2"],
        ),
    ]


@pytest.fixture
def metric_set(tmp_path: Path) -> Generator[MetricSet, None, None]:
    """Fixture that creates a MetricSet instance with a temporary directory"""
    ms = MetricSet(
        name="test_set", base_path=tmp_path, induced_from="test_source", version="1.0.0"
    )
    yield ms


class TestMetricSetInitialization:
    def test_basic_initialization(self, tmp_path: Path) -> None:
        """Test basic initialization of MetricSet"""
        ms = MetricSet(name="test", base_path=tmp_path, induced_from="source")

        assert ms.base_path == tmp_path
        assert ms.metrics_path == tmp_path / "metrics"
        assert ms.metadata_path == tmp_path / "metadata.json"
        assert ms.metrics_path.exists()
        assert ms.base_path.exists()

    def test_initialization_with_existing_metadata(self, tmp_path: Path) -> None:
        """Test initialization when metadata file already exists"""
        # Create existing metadata
        metadata = MetricSetMetadata(
            name="existing",
            metric_names=["metric1"],
            induced_from="source",
            version="1.0",
        )
        metadata_path = tmp_path / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))

        metric1 = Metric(
            name="metric1",
            explanation="First test metric",
            good_behaviors=["good1"],
            bad_behaviors=["bad1"],
        )

        # Create existing metric file
        metric_path = tmp_path / "metrics" / "metric1.yaml"
        metric_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metric_path, "w") as f:
            f.write(metric1.model_dump_json(indent=2))

        # Initialize MetricSet with existing metadata
        ms = MetricSet(name="new_name", base_path=tmp_path, induced_from="new_source")

        # Should load existing metadata instead of creating new
        assert ms.metadata.name == "existing"
        assert ms.metadata.metric_names == ["metric1"]

    def test_initialization_with_invalid_metadata(self, tmp_path: Path) -> None:
        """Test initialization with corrupted metadata file"""
        metadata_path = tmp_path / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w") as f:
            f.write("invalid json")

        with pytest.raises(Exception):
            MetricSet(name="test", base_path=tmp_path, induced_from="source")


class TestMetricOperations:
    def test_add_single_metric(
        self, metric_set: MetricSet, sample_metric: Metric
    ) -> None:
        """Test adding a single metric"""
        metric_set.add_metrics([sample_metric])

        # Check if metric was added to internal dict
        assert sample_metric.name in metric_set.metrics
        assert metric_set.metrics[sample_metric.name] == sample_metric

        # Check if metric file was created
        metric_path = metric_set.metrics_path / f"{sample_metric.name}.yaml"
        assert metric_path.exists()

    def test_add_multiple_metrics(
        self, metric_set: MetricSet, sample_metrics: list[Metric]
    ) -> None:
        """Test adding multiple metrics at once"""
        metric_set.add_metrics(sample_metrics)

        for metric in sample_metrics:
            assert metric.name in metric_set.metrics
            metric_path = metric_set.metrics_path / f"{metric.name}.yaml"
            assert metric_path.exists()

    def test_add_duplicate_metric(
        self, metric_set: MetricSet, sample_metric: Metric
    ) -> None:
        """Test adding a metric with a name that already exists"""
        metric_set.add_metrics([sample_metric])

        with pytest.raises(
            ValueError, match=f"Metric with name {sample_metric.name} already exists"
        ):
            metric_set.add_metrics([sample_metric])

    def test_get_existing_metric(
        self, metric_set: MetricSet, sample_metric: Metric
    ) -> None:
        """Test retrieving an existing metric"""
        metric_set.add_metrics([sample_metric])

        retrieved_metric = metric_set.get_metric(sample_metric.name)
        assert retrieved_metric.model_dump() == sample_metric.model_dump()

    def test_get_nonexistent_metric(self, metric_set: MetricSet) -> None:
        """Test attempting to retrieve a metric that doesn't exist"""
        with pytest.raises(
            ValueError, match="Metric with name nonexistent does not exist"
        ):
            metric_set.get_metric("nonexistent")

    def test_get_metric_with_corrupted_file(
        self, metric_set: MetricSet, sample_metric: Metric
    ) -> None:
        """Test getting a metric when its file is corrupted"""
        metric_set.add_metrics([sample_metric])

        # Corrupt the metric file
        metric_path = metric_set.metrics_path / f"{sample_metric.name}.yaml"
        with open(metric_path, "w") as f:
            f.write("invalid json")

        with pytest.raises(Exception):
            metric_set.get_metric(sample_metric.name)


class TestMetadataOperations:
    def test_save_metadata(self, metric_set: MetricSet) -> None:
        """Test saving metadata to file"""
        new_metadata = MetricSetMetadata(
            name="new_name",
            metric_names=["metric1", "metric2"],
            induced_from="new_source",
            version="2.0.0",
        )

        metric_set._save_metadata(new_metadata)

        # Verify file contents
        with open(metric_set.metadata_path, "r") as f:
            saved_data = json.loads(f.read())
            assert saved_data["name"] == "new_name"
            assert saved_data["metric_names"] == ["metric1", "metric2"]

    def test_save_metrics(
        self, metric_set: MetricSet, sample_metrics: list[Metric]
    ) -> None:
        """Test saving all metrics to files"""
        metric_set.metrics = {metric.name: metric for metric in sample_metrics}
        metric_set._save_metrics()

        for metric in sample_metrics:
            metric_path = metric_set.metrics_path / f"{metric.name}.yaml"
            assert metric_path.exists()

            with open(metric_path, "r") as f:
                saved_data = json.loads(f.read())
                assert saved_data["name"] == metric.name
                assert saved_data["explanation"] == metric.explanation

    def test_initialization_with_none_path(self) -> None:
        """Test initialization with None as path"""
        with pytest.raises(TypeError):
            MetricSet(name="test", base_path=None, induced_from="source")  # type: ignore[arg-type]

    def test_file_permission_errors(self, tmp_path: Path) -> None:
        """Test handling of file permission errors"""
        # Create directory with no write permissions
        no_write_dir = tmp_path / "no_write"
        no_write_dir.mkdir()
        no_write_dir.chmod(0o444)  # Read-only

        with pytest.raises(Exception):
            MetricSet(name="test", base_path=no_write_dir, induced_from="source")
