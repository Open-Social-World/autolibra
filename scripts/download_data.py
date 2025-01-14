from osw_eval.data import BalrogNLEDatasetLoader, BalrogMiniHackDatasetLoader, BalrogCrafterDatasetLoader, BalrogBabaIsAIDatasetLoader

def download_nle_dataset() -> None:
    BalrogNLEDatasetLoader().download()

def download_minihack_dataset() -> None:
    BalrogMiniHackDatasetLoader().download()

def download_crafter_dataset() -> None:
    BalrogCrafterDatasetLoader().download()

def download_babaisai_dataset() -> None:
    # BalrogBabaIsAIDatasetLoader().download()
    BalrogBabaIsAIDatasetLoader().render()

if __name__ == "__main__":
    download_babaisai_dataset()