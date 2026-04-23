<p align="center">
  <img src="https://autolibra.org/static/images/scale.png" width="80" alt="AutoLibra" />
</p>

<h1 align="center">AutoLibra</h1>

<p align="center">
  <b>Agent Metric Induction from Open-Ended Human Feedback</b><br>
  <i>ICLR 2026</i>
</p>

<p align="center">
  <a href="https://arxiv.org/abs/2505.02820"><img src="https://img.shields.io/badge/paper-arXiv-b31b1b" alt="arXiv"></a>
  <a href="https://autolibra.org/"><img src="https://img.shields.io/badge/website-autolibra.org-175E54" alt="website"></a>
  <a href="https://openreview.net/forum?id=4BjGVZ7Bxn"><img src="https://img.shields.io/badge/OpenReview-ICLR%202026-8c1b13" alt="OpenReview"></a>
  <a href="https://huggingface.co/datasets/open-social-world/autolibra"><img src="https://img.shields.io/badge/🤗%20dataset-open--social--world%2Fautolibra-yellow" alt="dataset"></a>
</p>

---

AutoLibra turns **open-ended natural-language feedback** on agent
trajectories into **fine-grained, interpretable evaluation metrics**. Give it
sentences like *"the agent did not choose iPhone 14/15"* or *"this agent has
too much autonomy"*, and it gives back metrics with definitions and concrete
examples — ready to drive an LLM-as-a-Judge, diagnose failure modes, or serve
as optimization targets for prompt engineering.

The pipeline has three LLM-driven operators:

1. **Feedback grounding** — break feedback into `(behavior, feedback, sign)` aspects tied to a specific part of the trajectory.
2. **Behavior clustering** — group similar aspects into metrics with definitions + positive/negative examples.
3. **LLM-as-a-Judge** — score trajectories on the induced metrics, producing positive and negative *traits*.

`coverage` and `redundancy` meta-metrics then measure how well the induced
metric set covers unseen human feedback.

## Install

[uv](https://docs.astral.sh/uv/) is the supported package manager.

```bash
git clone https://github.com/Open-Social-World/autolibra
cd autolibra
uv sync
```

AutoLibra talks to Azure OpenAI. Create a `.env` in the repo root:

```env
AZURE_API_KEY=...
AZURE_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_4O_MODEL=gpt-4o
AZURE_OPENAI_O3_MODEL=o3-mini
GITHUB_PERSONAL_ACCESS_TOKEN=...   # optional, for some GitHub-backed dataset loaders
```

## Quickstart (Python API)

```python
import asyncio
from openai import AsyncAzureOpenAI
from autolibra_core import (
    feedback_grounding,
    behavior_clustering,
    run_llm_eval,
    MetricTrainingInstance,
)

async def main():
    client = AsyncAzureOpenAI(azure_endpoint=..., api_key=..., api_version=...)

    # 1. Build MetricTrainingInstance objects from your trajectories + feedback.
    #    See `autolibra_core.datasets.*` for loaders; each yields instances like:
    #    MetricTrainingInstance(task=..., agent_id=..., trajectory=..., feedback=...)
    instances: list[MetricTrainingInstance] = load_my_data()

    # 2. Ground feedback into aspects per instance.
    aspects = []
    for inst in instances:
        aspects.extend(await feedback_grounding(inst, client))

    # 3. Cluster aspects into metrics with definitions + behavior examples.
    induced = await behavior_clustering(aspects, client)
    metrics = induced.metrics

    # 4. Run LLM-as-a-Judge on the trajectories with the induced metrics.
    results = await run_llm_eval(instances, metrics, client)
    print(metrics)
    print(results)

asyncio.run(main())
```

## Datasets

Shared trajectories + feedback live on Hugging Face at
[`open-social-world/autolibra`](https://huggingface.co/datasets/open-social-world/autolibra).
Install [git-lfs](https://git-lfs.com/) first, then:

```bash
git clone https://huggingface.co/datasets/open-social-world/autolibra .data
```

Preprocess or convert from the original sources with the dataset loaders in
`autolibra_core.datasets` (one module per dataset):

```bash
uv run python -m autolibra_core.datasets.webarena
uv run python -m autolibra_core.datasets.sotopia
uv run python -m autolibra_core.datasets.cogym
uv run python -m autolibra_core.datasets.balrog_babaisai
# ...
```

To contribute a new dataset, add a loader under
`packages/autolibra-core/src/autolibra_core/datasets/` that emits
`MetricTrainingInstance` objects, then push the converted artifacts to the
shared HF repo.

## Collecting feedback

Two annotation frontends ship in `src/tty/`:

```bash
# Terminal UI
uv run python src/tty/tty_annotation.py \
    .data/webarena .data/annotations/webarena \
    --annotator-id <your-name>

# Streamlit UI (browser)
uv run streamlit run src/tty/tty_annotation.py \
    .data/sotopia .data/annotations/sotopia \
    -- --annotator-id <your-name> --use-streamlit

# Review annotations
uv run streamlit run src/tty/view_annotations.py \
    -- .data/annotations/sotopia/annotations
```

Annotators are shown each trajectory step by step and write a single piece of
natural-language feedback per trajectory. See §2.1 of the paper for
annotation guidelines.

## Training / iterative metric induction

`src/training/` contains the end-to-end scripts used in the paper, including
the Gemini-based iterative induction pipeline from §4 ("AutoLibra as a
Ladder"). See [`src/training/README.md`](src/training/README.md) for the per-script breakdown.

The prompt-optimization harness used on Baba-Is-AI (Fig. 4 in the paper) is in
[`prompt_optimization/`](prompt_optimization/); environment submodules
(BALROG, etc.) are declared in `.gitmodules`.

## Repository layout

```
autolibra/
├── packages/
│   ├── autolibra-core/        # Core operators, evaluators, dataset loaders
│   └── osw-data/              # Trajectory / metric primitives
├── src/
│   ├── tty/                   # Annotation UIs (terminal + Streamlit)
│   ├── training/              # Iterative induction / eval pipelines
│   ├── tools/                 # Analysis utilities
│   └── plot/                  # Figure generation
├── prompt_optimization/       # Agent prompt-optimization harness
└── pyproject.toml
```

## Contributing

Issues and PRs welcome. Before opening a PR:

```bash
uv run pre-commit run --all-files
uv run pytest
```

## Citation

```bibtex
@inproceedings{zhu2026autolibra,
  title     = {AutoLibra: Agent Metric Induction from Open-Ended Human Feedback},
  author    = {Hao Zhu and Phil Cuvin and Xinkai Yu and
               Charlotte Ka Yee Yan and Jason Zhang and Diyi Yang},
  booktitle = {The Fourteenth International Conference on Learning Representations},
  year      = {2026},
  url       = {https://openreview.net/forum?id=4BjGVZ7Bxn}
}
```

## Acknowledgments

Supported by ONR N000142412532, NSF IIS-2247357, and DARPA *Friction for
Accountability in Conversational Transactions*. Compute credits from Google
Cloud Platform and Modal. Thanks to the Stanford SALT Lab for feedback.
