# OSW Eval

## Contributor doc

### WebArena

```bash 
# Download and preprocess webarena
uv run python -m osw_eval_core.datasets.webarena
```

### Annotation 
```bash
uv run python src/tty/tty_annotation.py .data/webarena .data/annotations/webarena --annotator-id <your name>
```