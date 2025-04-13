# OSW Eval

## Contributor doc

### Prepare the data

Install git lfs if you haven't already. This is required to download the large files in the dataset.

#### From scratch
For contributors, it is the best to use our shared data repo on huggingface: `open-social-world/osw-eval`. Upload new datasets to this shared repo.

```bash
# Download and preprocess <dataset>
uv run python -m osw_eval_core.datasets.<dataset>
```

#### Download from huggingface

```bash
git clone https://huggingface.co/datasets/open-social-world/osw-eval .data
```

#### Upload your data to huggingface

```bash
# cd into .data
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
### Run experiments
Test environments (BALROG, etc) are included as submodules under .gitmodules. Documentation for using these environments are included within each environment repo.
