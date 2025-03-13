from osw_data import AnnotationSystem
import rich

if __name__ == "__main__":
    dataset_name = "sotopia"

    annotation_system = AnnotationSystem(
        base_path=f".data/annotations/{dataset_name}",
    )

    rich.print(
        f"There are {len(annotation_system.get_all_annotations())} annotations in the dataset."
    )
