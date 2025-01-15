from pathlib import Path
import logging


class BaseConverter(object):
    def __init__(self, output_path: Path, source_path: Path) -> None:
        self.output_path = output_path
        self.source_path = source_path

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(type(self).__name__)

        self._setup_constants()

    def _setup_constants(self) -> None:
        pass

    def download_data(self) -> None:
        raise NotImplementedError()

    def convert_to_dataset(self) -> None:
        raise NotImplementedError()


def run_converter(
    converter_class: type[BaseConverter], output_path: Path, source_path: Path
) -> None:
    converter = converter_class(output_path=output_path, source_path=source_path)
    converter.download_data()
    converter.convert_to_dataset()
