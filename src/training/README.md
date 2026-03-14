# Training Scripts

This document explains key scripts in `src/training` and how they fit into the AutoLibra pipeline.

## Scripts

- `grounding_gemini.py`
  - Runs metric grounding using Gemini.
  - Produces a metric set from annotation/feedback-derived signals.

- `grounding_gemini_induction.py`
  - Inductive grounding pass that starts from an existing metric set.
  - Focuses on adding/refining uncovered behavior aspects while reducing duplication.

- `llm_eval_gemini.py`
  - Scores trajectory instances against a provided metric set using Gemini.
  - Produces per-instance metric score outputs (typically JSONL in `eval_results` style paths).

- `coverage_analysis_gemini.py`
  - Reads metric definitions and Gemini eval outputs to compute coverage/redundancy reports.
  - Use this after `llm_eval_gemini.py` when you want explicit coverage diagnostics.

- `llm_as_a_judge_gemini.py`
  - Alternate Gemini judging path for direct LLM judging workflows.
  - Can be used when running a judge-style evaluation setup rather than the standard eval flow.

- `gemini_batch_pipeline.py` (`src/training`)
  - Convenience orchestrator for batch execution across folders.
  - Wraps conversion/processing/evaluation commands into one multi-folder run.

- `analyze_eval_results_matrix.py` (`src/training`)
  - Aggregates multiple eval JSONL files and writes a metric-by-run summary CSV.
  - Provider-agnostic post-run analysis utility.

## Order

1. `grounding_gemini.py` (or `grounding_gemini_induction.py` for iterative rounds)
2. `llm_eval_gemini.py`
3. `coverage_analysis_gemini.py` (optional but recommended for diagnostics)
4. `prompt_improver_direct_data.py` (uses metrics/eval outputs/trajectories)

## Prompt Improver (`prompt_improver_direct_data.py`)

### What it does

- Reads turn input data (metrics, eval results, trajectories) and generates the next agent prompt/code.
- Uses a config-driven path layout so game/repo details are not hardcoded.
- Supports provider selection (Gemini/Azure) via config/CLI options.

### Required config

- Default config path: `prompt_optimization/config.yaml`
- Required sections:
  - `active` (`repo`, `game`)
  - `provider` (`name`, optional `azure_model`)
  - `naming` (`agent_prefix`, `agent_filename_template`)
  - `paths` (`base_dir`, `turn_info_dir_template`, `turn_output_dir_template`, `turns_dir`, `seed_agent_path`, `rules_path`)

### Expected folder structure

- Turn input: `prompt_optimization/repos/{repo}/{game}/turns/turn_k/info/`
- Turn output: `prompt_optimization/repos/{repo}/{game}/turns/turn_k/output/`
- Seed prompt: `prompt_optimization/repos/{repo}/{game}/prompt_seed/agent.py`
- Rules: `prompt_optimization/repos/{repo}/{game}/rules.md`

The improver picks the first turn where `info/` exists but the expected output agent file does not exist yet.

### Run examples

- Default config:
  - `python -m src.training.prompt_improver_direct_data`
- Explicit config/provider:
  - `python -m src.training.prompt_improver_direct_data --config prompt_optimization/config.yaml --provider gemini`
