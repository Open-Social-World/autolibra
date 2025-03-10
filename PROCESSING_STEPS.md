Assumptions:
1. BALROG and osw-eval are using the custom versions from GitHub.
2. BALROG and osw-eval are in the same parent directory.

For BALROG-osw-eval, an entire pipeline (turn) proceeds as follows:

1. Perform evaluation on task/dataset split as defined by config.yaml in BALROG.
    a. In config.yaml, update episodes for all tasks to 0 except for the task to be evaluated, which should be set to 1.
    b. In config.yaml, comment out all sub-tasks except the half-split to be evaluated.
    c. Run BALROG eval with the following line, replacing [turn] with the name of the previous turn file (arbitrary if turn 0) and [user] with the user's name:
    `python3 eval.py   agent.type=robust_cot   agent.max_image_history=0   agent.max_history=16   eval.num_workers=5   client.client_name=azure   client.model_id="gpt-4o-241120"  eval.next_turn="[turn]" eval.metrics_file="/home/[user]/osw-eval/.data/metrics/babaisai_turn_0/03_06_23_2/metrics"`


    d. Once run complete, run `python3 z_postprocess_results.py` to generate the final results file in `./raw`.
    e. Copy `./raw` to the `raw` folder in the `osw-eval` repo (by hand).

2. Convert and perform annotation on the new file using the annotation tty.
    a. Run the following line, ensuring that the correct input and output paths are used in the `balrog_fixed.py` file:
    `uv run python -m packages.osw-eval-core.src.osw_eval_core.datasets.balrog_fixed`
    b. Perform annotation with the following line, ensuring that the correct input and output paths are used in the `tty_annotation.py` file,
    "Enter" will not kick you to the next trajectory. Click the links to open the gifs in the VSCode browser.
    `uv run python src/tty/tty_annotation.py .data/balrog_fixed .data/annotations/balrog_fixed --annotator-id <your name>`
        i. To increase number of previous steps that can be seen, CTRL+SHIFT+P --> Preferences: Open Settings (JSON), add the following line:
        `"terminal.integrated.scrollback": 5000`

3. Run the metric extraction and conversion script.
    a. Run the following line, ensuring the target file is set correctly (changes every turn):
    `uv run python -m src.training.grounding`

4. Run LLM Eval to get coverage.
    a. Run the following line, ensuring that the dataset name and metric path are used in the `llm_eval.py` file:
    `uv run python -m osw_eval_core.gen_eval.llm_eval`

5. Convert the results into parsable json and
    
