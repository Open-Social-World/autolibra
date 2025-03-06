# OSW Eval

## Contributor doc

### Prepare the data

#### From scratch
For contributors, it is the best to use our shared data repo on huggingface: `open-social-world/osw-eval`. This is for new dataset that you have created.

```bash
# Download and preprocess <dataset>
uv run python -m osw_eval_core.datasets.<dataset>
```

Or run the following from the root of the repo:

```bash
uv run python -m packages.osw-eval-core.src.osw_eval_core.datasets.balrog_fixed
```

#### Download from huggingface

```bash
git clone https://huggingface.co/datasets/open-social-world/osw-eval .data
```

#### Upload your data to huggingface

```bash
# cd into .datauv run python -m osw_eval_core.datasets.<dataset>
# git add your data
# git commit -m "Add <dataset>"
git push
```

### Annotation
```bash
uv run python src/tty/tty_annotation.py .data/webarena .data/annotations/webarena --annotator-id <your name>
```

### Annotation Web Interface with Streamlit
```bash
uv run streamlit run src/tty/tty_annotation.py .data/sotopia .data/annotations/sotopia -- --annotator-id <your name> --use-streamlit
```

### View Annotations with Streamlit
```bash
streamlit run src/tty/view_annotations.py -- .data/annotations/sotopia/annotations
```

### To run metric extraction
```bash
uv run python -m osw_eval_core.gen_eval.generator
```
