import json
from .utils import download_github_folder, file_pairs, parse_text_description, visualize_map
import polars as pl

class BaseDatasetLoader():
    def __init__(self):
        pass


class BalrogNLEDatasetLoader(BaseDatasetLoader):
    def __init__(self):
        pass

    def download(self) -> None:
        download_github_folder("balrog-ai", "experiments", "submissions/LLM/20241103_Claude-3.5-Sonnet/nle", ".data/balrog-nle")
    
    def render(self) -> None:
        for csv_file, json_file in file_pairs(".data/balrog-nle/NetHackChallenge-v0"):
            traj = pl.read_csv(csv_file)
            observations = traj.select('Observation')
            actions = traj.select('Action')
            
            for obs, action in zip(observations['Observation'].to_list(), actions['Action'].to_list()):
                print(obs)
                print(action)
                # wait for user input
                input()


class BalrogMiniHackDatasetLoader(BaseDatasetLoader):
    def __init__(self):
        pass

    def download(self) -> None:
        download_github_folder("balrog-ai", "experiments", "submissions/LLM/20241103_Claude-3.5-Sonnet/minihack", ".data/balrog-minihack")
    
    def render(self) -> None:
        summary_json = json.load(open(".data/balrog-minihack/minihack_summary.json"))
        tasks: list[str] = list(summary_json['tasks'].keys())

        for task in tasks:
            for csv_file, json_file in file_pairs(f".data/balrog-minihack/{task}"):
                traj = pl.read_csv(csv_file)
                observations = traj.select('Observation')
                actions = traj.select('Action')
                
                for obs, action in zip(observations['Observation'].to_list(), actions['Action'].to_list()):
                    print(obs)
                    print(action)
                    # wait for user input
                    input()

class BalrogCrafterDatasetLoader(BaseDatasetLoader):
    def __init__(self):
        pass

    def download(self) -> None:
        download_github_folder("balrog-ai", "experiments", "submissions/LLM/20241103_Claude-3.5-Sonnet/crafter", ".data/balrog-crafter")
    
    def render(self) -> None:
        summary_json = json.load(open(".data/balrog-crafter/crafter_summary.json"))
        tasks: list[str] = list(summary_json['tasks'].keys())

        for task in tasks:
            for csv_file, json_file in file_pairs(f".data/balrog-crafter/{task}"):
                traj = pl.read_csv(csv_file)
                observations = traj.select('Observation')
                actions = traj.select('Action')
                
                for obs, action in zip(observations['Observation'].to_list(), actions['Action'].to_list()):
                    print(obs)
                    print(action)
                    # wait for user input
                    input()

class BalrogBabaIsAIDatasetLoader(BaseDatasetLoader):
    def __init__(self):
        pass

    def download(self) -> None:
        download_github_folder("balrog-ai", "experiments", "submissions/LLM/20241103_Claude-3.5-Sonnet/babaisai", ".data/balrog-babaisai")
    
    def render(self) -> None:
        summary_json = json.load(open(".data/balrog-babaisai/babaisai_summary.json"))
        tasks: list[str] = list(summary_json['tasks'].keys())

        for task in tasks:
            for csv_file, json_file in file_pairs(f".data/balrog-babaisai/{task}"):
                traj = pl.read_csv(csv_file)
                observations = traj.select('Observation')
                actions = traj.select('Action')
                
                for obs, action in zip(observations['Observation'].to_list(), actions['Action'].to_list()):
                    # remove text before active rules
                    text_removed_obs = obs.split("Active rules:")[1]
                    active_rules, objects_on_the_map = text_removed_obs.split("Objects on the map:")
                    print(active_rules)
                    visualize_map(parse_text_description(objects_on_the_map))
                    print(action)
                    # wait for user input
                    input()