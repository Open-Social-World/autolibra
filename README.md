# OSW Eval

## Contributor doc

### Prepare the data

#### From scratch
For contributors, it is the best to use our shared data repo on huggingface: `open-social-world/osw-eval`. This is for new dataset that you have created.

```bash
# Download and preprocess <dataset>
uv run python -m osw_eval_core.datasets.<dataset>
```

#### Download from huggingface

```bash
huggingface-cli download --repo-type dataset open-social-world/osw-eval --local-dir .data
```

#### Upload your data to huggingface

```bash
huggingface-cli upload-large-folder --repo-type dataset open-social-world/osw-eval .data
```

### Annotation
```bash
uv run python src/tty/tty_annotation.py .data/webarena .data/annotations/webarena --annotator-id <your name>
```

### To run metric extraction
```bash
uv run python -m osw_eval_core.gen_eval.generator
```
