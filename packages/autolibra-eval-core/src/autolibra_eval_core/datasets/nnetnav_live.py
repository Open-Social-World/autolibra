import json
from typing import TypedDict


class Message(TypedDict):
    content: str


class NNetNavStepData(TypedDict):
    messages: list[Message]


def _get_objective(data: NNetNavStepData) -> str:
    return data["messages"][1]["content"].split("OBJECTIVE: ")[1].split("\n")[0]


def _get_action(data: NNetNavStepData) -> str:
    try:
        return data["messages"][2]["content"].split("```")[1]
    except IndexError:
        return "none"


def _get_observation(data: NNetNavStepData) -> str:
    return data["messages"][1]["content"].split("OBSERVATION: ")[0]


if __name__ == "__main__":
    objectives: list[str] = []
    with open(".data/raw/nnetnav-live-00/train.jsonl") as f:
        for line in f.readlines():
            data = json.loads(line)
            objectives.append(_get_objective(data))

    unique_objectives: list[str] = []

    instance_starts = [0]

    for line_no, (this_obj, next_obj) in enumerate(zip(objectives, objectives[1:])):
        if this_obj != next_obj:
            instance_starts.append(line_no + 1)

    instance_ends = instance_starts[1:] + [len(objectives)]

    lines: list[str] = []
    with open(".data/raw/nnetnav-live-00/train.jsonl") as f:
        lines = f.readlines()

    for start, end in zip(instance_starts, instance_ends):
        instance_lines = lines[start:end]
        instance_data = [json.loads(line) for line in instance_lines]

        for data in instance_data:
            print(_get_objective(data))
            print(_get_action(data))
            print(_get_observation(data))
            print()

        break
