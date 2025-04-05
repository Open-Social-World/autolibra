import json
import os


file_path = ".data/raw/balrog-babaisai_turn_3"

# Walk over all subdirs in the given dir using os.walk

scoresteps = {}

for root, dirs, files in os.walk(file_path):
    json_files = [f for f in files if f.endswith(".json") and "summary" not in f]

    for ind_file in json_files:

        with open(os.path.join(root, ind_file), "r") as f:
            data = json.load(f)
            task = data['task']

            if task not in scoresteps:
                scoresteps[task] = [data['num_steps'], data['episode_return'], 1]
            else:
                scoresteps[task][0] += data['num_steps']
                scoresteps[task][1] += data['episode_return']
                scoresteps[task][2] += 1

net_avg_steps = 0
net_avg_return = 0

for key, val in scoresteps.items():
    avg_steps = val[0] / val[2]
    avg_return = val[1] / val[2]

    print(key, avg_steps, avg_return)
    net_avg_steps += avg_steps
    net_avg_return += avg_return

print("Net average steps:", net_avg_steps / len(scoresteps))
print("Net average return:", net_avg_return / len(scoresteps))
