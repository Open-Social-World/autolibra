import streamlit as st
from pathlib import Path
import json
import pandas as pd
from datetime import datetime
import typer

app = typer.Typer()

def sanitize_text(text: str) -> str:
    """Clean text to avoid display issues and escape markdown characters."""
    # Replace problematic unicode characters with their closest ASCII equivalents
    replacements = {
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '–': '-',
        '—': '-',
        '…': '...'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Escape markdown special characters
    markdown_chars = ['*', '_', '`', '#', '~', '>', '<', '[', ']', '(', ')', '|', '$']
    for char in markdown_chars:
        text = text.replace(char, '\\' + char)
    
    return text

def load_annotations(annotations_dir: Path) -> list:
    """Load all annotation files from the directory."""
    annotations = []
    
    # Get all json files in the annotations directory - use the passed in path
    annotation_files = list(annotations_dir.glob("*.json"))
    
    for file_path in annotation_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Extract instance_id and agent_id from filename
            # Filename format: instance_id_agent_id.json
            filename = file_path.stem  # Get filename without extension
            instance_id, agent_id = filename.rsplit('_', 1)
            
            # Process each annotation in the file
            for annotation in data['annotations']:
                # Parse the ISO format timestamp string into a datetime object
                created_dt = datetime.fromisoformat(annotation['created_at'].replace('Z', '+00:00'))
                
                annotations.append({
                    'instance_id': instance_id,
                    'agent_id': agent_id,
                    'annotator_id': annotation['annotator_id'],
                    'feedback': sanitize_text(annotation['content']['feedback']),
                    'start_time': annotation['span']['start_time'],
                    'end_time': annotation['span']['end_time'],
                    'created_at': created_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'created_dt': created_dt  # Keep datetime object for sorting
                })
    
    return annotations

@app.command()
def main(
    annotations_dir: Path = typer.Argument(
        ...,
        help="Path to the annotations directory (e.g., .data/annotations/sotopia/annotations)",
        exists=True,
        dir_okay=True,
        file_okay=False,
    )
):
    """View annotations from the specified directory."""
    st.title("🔍 Annotation Viewer")
    
    # Convert to absolute path and resolve any relative path components
    annotations_dir = annotations_dir.absolute().resolve()
    
    if not annotations_dir.exists():
        st.error(f"Annotations directory not found: {annotations_dir}")
        st.info("Please provide the full path to the annotations directory. For example:\n\n"
                "```bash\n"
                "streamlit run src/tty/view_annotations.py -- .data/annotations/sotopia/annotations\n"
                "```")
        return
    
    # Load annotations
    annotations = load_annotations(annotations_dir)
    
    if not annotations:
        st.warning("No annotations found.")
        return
    
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(annotations)
    
    # Remove duplicate annotations, keeping only the most recent one
    df = df.sort_values('created_dt', ascending=False).drop_duplicates(
        subset=['instance_id', 'agent_id', 'annotator_id', 'feedback'],
        keep='first'
    )
    
    # Display summary statistics
    st.header("📊 Summary Statistics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Annotations", len(df))
    with col2:
        st.metric("Unique Instances", df['instance_id'].nunique())
    with col3:
        st.metric("Unique Annotators", df['annotator_id'].nunique())
    
    # Filters
    st.header("🔎 Filters")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_annotator = st.selectbox(
            "Select Annotator",
            options=["All"] + sorted(df['annotator_id'].unique().tolist())
        )
    
    # Filter instance options based on selected annotator
    instance_options = df['instance_id'].unique().tolist()
    if selected_annotator != "All":
        instance_options = df[df['annotator_id'] == selected_annotator]['instance_id'].unique().tolist()
    
    with col2:
        selected_instance = st.selectbox(
            "Select Instance",
            options=["All"] + sorted(instance_options)
        )
    
    # Apply filters
    filtered_df = df.copy()
    if selected_annotator != "All":
        filtered_df = filtered_df[filtered_df['annotator_id'] == selected_annotator]
    if selected_instance != "All":
        filtered_df = filtered_df[filtered_df['instance_id'] == selected_instance]
    
    # Display annotations
    st.header("📝 Annotations")
    
    # Sort by timestamp in descending order
    filtered_df = filtered_df.sort_values('created_dt', ascending=False)
    
    for _, row in filtered_df.iterrows():
        with st.expander(f"Instance: {row['instance_id']} | Agent: {row['agent_id']} | {row['created_at']}", expanded=False):
            st.markdown(f"**Annotator:** {row['annotator_id']}")
            st.markdown(f"**Feedback:**")
            st.info(row['feedback'])
            st.markdown(f"**Time Range:** {row['start_time']} to {row['end_time']}")

if __name__ == "__main__":
    app() 