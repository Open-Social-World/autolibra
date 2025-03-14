import json

# Load llm_eval_results.jsonl

scores = {}
for row in open("llm_eval_results.jsonl"):
    data = json.loads(row)
    for key, value in data.items():
        # Add all new keys to the dictionary
        if key not in scores:
            scores[key] = [0, 0, 0]
        # Increment the corresponding value
        if value == -1:
            scores[key][0] += 1
        elif value == 0:
            scores[key][1] += 1
        elif value == 1:
            scores[key][2] += 1

for key,val in scores.items():
    print(key, val)