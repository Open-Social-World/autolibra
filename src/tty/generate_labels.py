from pathlib import Path
import sys
import json

# Add the package directory to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent / "packages"))

from osw_data.dataset import MultiAgentDataset, DataInstance
from osw_data.trajectory import PointType
from datetime import datetime
import openai
from pydantic import BaseModel
import os
import re

class DialogueSummary(BaseModel):
    summary: str

def generate_labels(dataset_path: str):
    print(f"Looking for dataset at: {dataset_path}")
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset path {dataset_path} does not exist!")
        return []
    
    try:
        dataset = MultiAgentDataset(name="sotopia", base_path=dataset_path)
        instance_ids = dataset.list_instances()
        print(f"Found {len(instance_ids)} instances in the dataset")
        
        labels = []
        # Create a dictionary to store instance_id -> label mapping
        labels_dict = {}

        for instance_id in instance_ids:
            try:
                print(f"Processing instance {instance_id}...")
                instance_metadata = dataset.get_instance_metadata(instance_id)
                agents = list(instance_metadata.agents.values())

                if len(agents) < 2:
                    print(f"Instance {instance_id} has less than two agents, skipping.")
                    continue

                # Extract first names
                agent1_first_name = agents[0].agent_id.split()[0]
                agent2_first_name = agents[1].agent_id.split()[0]

                # Extract dialogue content from trajectories
                dialogue_content = extract_dialogue_from_trajectories(dataset, instance_id, instance_metadata)

                # Format date
                date_str = instance_metadata.timestamp.strftime("%Y-%m-%d")

                # Generate label with new format: "Ava & Noah | Alcohol Concern | 2025-01-14"
                label = f"{agent1_first_name} & {agent2_first_name} | {dialogue_content} | {date_str}"
                labels.append(label)
                # Add to dictionary
                labels_dict[instance_id] = label
                print(f"Generated label: {label}")
            except Exception as e:
                print(f"Error processing instance {instance_id}: {str(e)}")
        
        # Save labels to a JSON file
        labels_file = Path(dataset_path) / "instance_labels.json"
        with open(labels_file, "w") as f:
            json.dump(labels_dict, f, indent=2)
        print(f"Saved labels to {labels_file}")
                
        return labels
    except Exception as e:
        print(f"Error loading dataset: {str(e)}")
        return []

def extract_dialogue_from_trajectories(dataset, instance_id, instance_metadata):
    """Extract dialogue content from agent trajectories"""
    try:
        # Get all agent IDs
        agent_ids = list(instance_metadata.agents.keys())
        
        # Collect all dialogue from all agents' trajectories
        all_dialogue = []
        
        for agent_id in agent_ids:
            try:
                # Get the agent's trajectory
                trajectory = dataset.get_trajectory(instance_id, agent_id)
                
                # Sort trajectory points by timestamp
                trajectory_points = [
                    (point, trajectory.get_data_at(idx))
                    for idx, point in enumerate(trajectory.points)
                ]
                trajectory_points.sort(key=lambda x: x[0].timestamp)
                
                # Extract actions (which contain dialogue)
                for point, data in trajectory_points:
                    if point.point_type == PointType.ACTION:
                        # Extract the dialogue from the action
                        if isinstance(data, dict) and "content" in data:
                            dialogue = data.get("content", "")
                            if dialogue:
                                all_dialogue.append(f"{agent_id}: {dialogue}")
                        elif isinstance(data, str):
                            all_dialogue.append(f"{agent_id}: {data}")
                        else:
                            # Try to convert to string if it's not a dict or string
                            try:
                                all_dialogue.append(f"{agent_id}: {str(data)}")
                            except:
                                pass
            except Exception as e:
                print(f"Error extracting trajectory for agent {agent_id}: {str(e)}")
        
        # Join all dialogue parts
        dialogue_text = "\n".join(all_dialogue)
        print(f"Extracted dialogue (length: {len(dialogue_text)} chars)")
        if len(dialogue_text) < 100:
            print(f"Full dialogue: {dialogue_text}")
        else:
            print(f"Dialogue preview: {dialogue_text[:100]}...")
        
        # If no dialogue was found, return a placeholder
        if not dialogue_text.strip():
            return "NoDialogue"
        
        # Generate a summary 
        client = openai.OpenAI()
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": """
                    You are a specialized labeling expert who creates concise, descriptive labels for conversations.
                    
                    Your task is to analyze the conversation and create a specific, meaningful label that captures its 
                    main topic or theme in maximum 2 words.
                    
                    Focus on:
                    - The specific subject matter discussed (e.g., "ClimatePolicy", "JobInterview", "FamilyConflict")
                    - Unique aspects that distinguish this conversation from others
                    - Concrete topics rather than generic terms
                    
                    Your label should be immediately informative about what the conversation contains.
                """},
                {"role": "user", "content": dialogue_text},
            ],
            response_format=DialogueSummary,
        )

        # Extract the summary from the structured response
        summary = completion.choices[0].message.parsed.summary
        # Keep spaces and formatting for readability
        summary = summary.replace("|", "-")

        # Add spaces between words
        summary = re.sub(r'([a-z])([A-Z])', r'\1 \2', summary)

        print(f"Generated summary: {summary}")
        return summary
    except Exception as e:
        print(f"Error in extract_dialogue_from_trajectories: {str(e)}")
        return "ExtractionError"

if __name__ == "__main__":
    dataset_path = Path(__file__).parent.parent.parent / ".data" / "sotopia"
    print(f"Starting label generation from {dataset_path}")
    
    labels = generate_labels(str(dataset_path))
    
    print(f"\nGenerated {len(labels)} labels:")
    for label in labels:
        print(label)
