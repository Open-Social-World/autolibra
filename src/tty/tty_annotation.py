from pathlib import Path
from typing import Any
import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
import json
import streamlit as st

from osw_data.annotation import AnnotationSystem, AnnotationSpan
from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType, MediaType

console = Console()
app = typer.Typer()


class TTYAnnotator:
    """TTY-based annotation interface using Rich"""

    def __init__(self, dataset_path: Path, annotation_path: Path, annotator_id: str):
        self.dataset = MultiAgentDataset(
            name="dataset",  # This will be loaded from metadata
            base_path=dataset_path,
        )

        self.annotation_system = AnnotationSystem(
            base_path=annotation_path,
            project_name="Trajectory Annotation Project",
            description="Free-form text annotations of agent trajectories",
            annotation_schema={
                "feedback": {
                    "type": "string",
                    "description": "Free-form text feedback on the trajectory",
                }
            },
        )

        self.annotator_id = annotator_id

        # Ensure annotator exists
        if annotator_id not in self.annotation_system.project.annotators:
            self.annotation_system.add_annotator(
                annotator_id=annotator_id,
                name=annotator_id,  # Using ID as name for simplicity
            )

    def _select_agent(self, instance_id: str) -> str:
        """Automatically select an unannotated agent for the given instance"""
        instance = self.dataset.get_instance_metadata(instance_id)

        # Get all agents for this instance
        valid_agents = list(instance.agents.keys())

        # Check which agents haven't been annotated by this annotator
        unannotated_agents = []
        for agent_id in valid_agents:
            trajectory_annotations = self.annotation_system.get_trajectory_annotations(
                instance_id=instance_id, agent_id=agent_id
            )

            # Check if any annotations have been made at all
            # Check if this trajectory has any annotations at all
            if not trajectory_annotations.annotations:
                unannotated_agents.append(agent_id)

        if not unannotated_agents:
            raise ValueError(f"No unannotated agents found for instance {instance_id}")

        # Select the first unannotated agent
        selected_agent = unannotated_agents[0]

        # Display the selected agent
        agent_info = instance.agents[selected_agent]
        description = agent_info.model_dump_json()
        console.print(
            f"\n[green]Selected agent for annotation:[/green] {selected_agent}"
        )
        console.print(f"Agent info: {description}\n")

        return selected_agent

    def _format_accessibility_tree(self, html_text: str) -> str:
        """Format accessibility tree for better readability"""
        lines = html_text.strip().split("\\n")
        formatted_lines = []

        for line in lines:
            if not line.strip():
                continue

            # Extract indentation level
            indent_count = 0
            for char in line:
                if char == "\\t":
                    indent_count += 1
                else:
                    break

            # Remove tabs from the start
            line = line.lstrip("\\t")

            # Parse the line
            if line.startswith("["):
                # Extract node ID and content
                node_id = line[1 : line.index("]")]
                content = line[line.index("]") + 1 :].strip()

                # Format based on content type
                if "'" in content:
                    # Extract the quoted text
                    text = content[content.index("'") + 1 : content.rindex("'")]
                    attributes = content[content.rindex("'") + 1 :].strip()

                    # Color coding based on element type
                    if content.startswith("link"):
                        element = f"[blue]link[/blue] '{text}'"
                    elif content.startswith("button"):
                        element = f"[green]button[/green] '{text}'"
                    elif content.startswith("textbox"):
                        element = f"[yellow]textbox[/yellow] '{text}'"
                    elif content.startswith("heading"):
                        element = f"[magenta]heading[/magenta] '{text}'"
                    else:
                        element = f"{content.split(' ')[0]} '{text}'"

                    # Add attributes if present
                    if attributes:
                        element += f" [dim]{attributes}[/dim]"

                    formatted_lines.append(
                        "  " * indent_count + f"[dim]{node_id}:[/dim] {element}"
                    )
                else:
                    # Lines without quoted text
                    formatted_lines.append(
                        "  " * indent_count + f"[dim]{node_id}:[/dim] {content}"
                    )
            else:
                # Tab title or other content
                formatted_lines.append("  " * indent_count + f"[bold]{line}[/bold]")

        return "\n".join(formatted_lines)

    def _display_observation(self, data: Any, media_type: MediaType) -> None:
        """Display an observation based on its media type"""
        if media_type == MediaType.JSON:
            if isinstance(data, dict) and "html" in data and isinstance(data["html"], str):
                # Display URL if present
                if "url" in data:
                    console.print(Panel(f"[bold blue]{data['url']}[/bold blue]", title="URL"))
                    st.markdown("#### 🌐 URL")
                    st.info(data['url'])

                # Format and display the accessibility tree
                formatted_html = self._format_accessibility_tree(data["html"])
                console.print(Panel(formatted_html, title="Page Structure"))
                st.markdown("#### 📄 Page Structure")
                with st.expander("View Page Structure", expanded=True):
                    st.code(formatted_html, language="")
            else:
                json_str = json.dumps(data, indent=2)
                
                def clean_json_obs(json_str: str) -> str:
                    # Remove the outer curly brackets
                    content = json_str.strip("{}")

                    # Remove the "content": part at the beginning
                    if '"content": ' in content:
                        content = content.split('"content": ', 1)[1]

                    # Remove the quotes at the start and end
                    content = content.strip('"')

                    # Replace escaped newlines with actual newlines
                    content = content.replace("\\n", "\n")

                    # Replace escaped quotes with regular quotes
                    content = content.replace("\\'", "'")

                    # Format the content with proper line breaks
                    console_lines = []
                    st_lines = []
                    
                    for line in content.split("\n"):
                        # Skip empty lines and standalone quotes
                        if line.strip() in ["", '"']:
                            continue

                        if ":" in line:
                            label, rest = line.split(":", 1)
                            if label.strip():
                                console_line = f"[bold green]{label}[/bold green]:{rest}"
                                # For Streamlit, wrap in markdown code block
                                st_line = f"**{label}**:{rest}"
                            else:
                                console_line = line
                                st_line = line
                        else:
                            console_line = line
                            st_line = line
                            
                        console_lines.append(console_line)
                        st_lines.append(st_line)

                    return (
                        "\n".join(console_lines),  # Console version
                        "\n\n".join(st_lines)      # Streamlit version with double newlines
                    )

                console_str, st_str = clean_json_obs(json_str)
                width = min(console.width - 2, 120)

                # Console display (with Rich formatting)
                console.print(Panel(console_str, title="Observation (JSON)", width=width))
                
                # Enhanced Streamlit display
                st.markdown("#### 👁️ Observation")
                with st.container():
                    st.info(st_str)

        elif media_type == MediaType.TEXT:
            # Display text data
            console.print(Panel(str(data), title="Observation (Text)"))
            
            # Enhanced Streamlit display
            st.markdown("#### 📝 Observation (Text)")
            st.info(str(data).replace("\n", "\n\n"))

        elif media_type == MediaType.IMAGE:
            # Just indicate image dimensions for TTY interface
            console.print(f"[Image observation with shape {data.shape}]")
            
            # Enhanced Streamlit display
            st.markdown("#### 🖼️ Image Observation")
            st.info(f"Image with shape {data.shape}")

        else:
            console.print(f"[Unsupported media type: {media_type}]")
            st.error(f"Unsupported media type: {media_type}")

    def _display_action(self, data: Any, agent_name: str = "") -> None:
        """Display an action"""
        if isinstance(data, dict):
            json_str = json.dumps(data, indent=2)
            def clean_json_action(json_str: str) -> str:
                # Remove the outer curly brackets
                content = json_str.strip("{}")
                # Remove the "content": part at the beginning
                if '"content": ' in content:
                    content = content.split('"content": ', 1)[1]
                # Remove the quotes at the start and end
                content = content.strip('"')
                # Replace escaped newlines with actual newlines
                content = content.replace("\\n", "\n\n")
                # Replace escaped quotes with regular quotes
                content = content.replace("\\'", "'")
                
                # Add agent name prefix if provided
                if agent_name:
                    content = f"{agent_name} {content}"
                
                # Remove Rich formatting tags
                content = content.replace("[bold green]", "").replace("[/bold green]", "")
                content = content.replace("[bold]", "").replace("[/bold]", "")
                content = content.replace("[dim]", "").replace("[/dim]", "")

                # Ensure proper markdown line breaks
                return content.replace("\n", "\n\n")

            cleaned_json_str = clean_json_action(json_str)
            width = min(console.width - 2, 120)
            
            # Display in console
            panel = Panel(cleaned_json_str, title="Action", width=width)
            console.print(panel)
            
            # Enhanced Streamlit display
            st.markdown("#### 🎯 Action")
            with st.container():
                st.success(cleaned_json_str)
        else:
            # Handle non-dict data
            panel = Panel(str(data), title="Action")
            console.print(panel)
            
            # Enhanced Streamlit display
            st.markdown("#### 🎯 Action")
            st.success(str(data).replace("\n", "\n\n"))

    def annotate_instance(self, instance_id: str) -> bool:
        """Annotate a specific instance"""
        # Keep console output
        console.print(f"\n[bold blue]Annotating Instance:[/bold blue] {instance_id}")
        
        # Enhanced Streamlit display
        st.title(f"🔍 Annotating Instance: {instance_id}")
        
        # Get instance metadata
        instance = self.dataset.get_instance_metadata(instance_id)

        # Display instance info
        console.print(Markdown("### Instance Metadata"))

        metadata_table = Table(show_header=True)
        metadata_table.add_column("Key")
        metadata_table.add_column("Value")

        for key, value in instance.metadata.items():
            metadata_table.add_row(str(key), str(value))

        # Select an unannotated agent for evaluation
        selected_agent = self._select_agent(instance_id)

        console.print(metadata_table)
        console.print("\n")

        # Enhanced Streamlit metadata display
        st.markdown("### 📊 Instance Metadata")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Keys**")
            for key in instance.metadata.keys():
                st.markdown(f"- {key}")
        with col2:
            st.markdown("**Values**")
            for value in instance.metadata.values():
                st.markdown(f"- {value}")

        # Get selected agent's trajectory
        trajectory = self.dataset.get_trajectory(instance_id, selected_agent)
        trajectory_points = [
            (point, trajectory.get_data_at(idx))
            for idx, point in enumerate(trajectory.points)
        ]

        # Sort by timestamp
        trajectory_points.sort(key=lambda x: x[0].timestamp)

        # Display trajectory
        console.print(Markdown(f"### Trajectory for Agent: {selected_agent}"))
        console.print("[dim]You can press 's' at any time to skip this instance[/dim]")
        console.print("Press Enter to step through observations and actions...")

        start_time = None
        for point, data in trajectory_points:
            if start_time is None:
                start_time = point.timestamp

            # Display timestamp
            console.print(f"\n[cyan]Time:[/cyan] {point.timestamp}")

            # Display point data based on type
            if point.point_type == PointType.OBSERVATION:
                self._display_observation(data, point.data_reference.media_type)
            else:
                self._display_action(data, selected_agent)

            console.print(
                "\nPress Enter to continue, 's' to skip this instance, 'q' to quit annotation..."
            )
            if st.button("Continue"):
                pass
            if st.button("Skip"):
                console.print("\n[yellow]Skipping this instance...[/yellow]")
                return False
            if st.button("Quit"):
                console.print("\n[red]Quit Annotation...[/red]")
                raise KeyboardInterrupt()

        # Get annotation
        console.print("\n[bold green]Trajectory complete![/bold green]")
        console.print(
            f"\nPlease provide your feedback on {selected_agent}'s trajectory:"
        )
        feedback = console.input("\n> ")

        # Save annotation
        self.annotation_system.add_annotation(
            instance_id=instance_id,
            agent_id=selected_agent,
            annotator_id=self.annotator_id,
            content={"feedback": feedback},
            span=AnnotationSpan(
                start_time=start_time,
                end_time=point.timestamp,  # Last point's timestamp
            ),
        )

        console.print("\n[bold green]Annotation saved![/bold green]")
        return True

    def run(self) -> None:
        """Run the annotation interface"""
        # Initialize session state if not exists
        if 'current_instance' not in st.session_state:
            st.session_state.current_instance = None
            st.session_state.trajectory_index = 0
            st.session_state.instances = self.dataset.list_instances()
            st.session_state.feedback = ""
            st.session_state.quit = False  # Add quit state

        # Check if user has quit
        if st.session_state.quit:
            st.title("✨ Done annotating for now!")
            st.balloons()  # Add a fun effect
            st.success("Thank you for your annotations! You can close this window.")
            return

        st.title("My Annotations")
        
        # Get all instances
        instances = st.session_state.instances
        
        if not instances:
            st.error("No instances found in dataset!")
            console.print("[red]No instances found in dataset![/red]")
            return

        # Display progress
        total_agent_instances = sum(
            len(self.dataset.get_instance_metadata(instance_id).agents)
            for instance_id in instances
        )
        
        # Calculate unannotated pairs
        unannotated_pairs = []
        for instance_id in instances:
            instance = self.dataset.get_instance_metadata(instance_id)
            for agent_id in instance.agents:
                trajectory_annotations = self.annotation_system.get_trajectory_annotations(
                    instance_id=instance_id, agent_id=agent_id
                )
                if not trajectory_annotations.annotations:
                    unannotated_pairs.append((instance_id, agent_id))
        
        annotated_count = total_agent_instances - len(unannotated_pairs)
        st.progress(annotated_count / total_agent_instances)
        st.write(f"Progress: {annotated_count}/{total_agent_instances} agent trajectories annotated")
        console.print(f"\n[cyan]Progress: {annotated_count}/{total_agent_instances} agent trajectories annotated[/cyan]")

        if not unannotated_pairs:
            st.success("All agent trajectories have been annotated!")
            console.print("\n[green]All agent trajectories have been annotated![/green]")
            return

        # Handle instance selection and annotation
        if st.session_state.current_instance is None:
            import random
            instance_id, agent_id = random.choice(unannotated_pairs)
            st.session_state.current_instance = instance_id
            st.session_state.current_agent = agent_id
            st.session_state.trajectory_index = 0

        # Display current instance
        instance = self.dataset.get_instance_metadata(st.session_state.current_instance)
        trajectory = self.dataset.get_trajectory(st.session_state.current_instance, st.session_state.current_agent)
        trajectory_points = [
            (point, trajectory.get_data_at(idx))
            for idx, point in enumerate(trajectory.points)
        ]
        trajectory_points.sort(key=lambda x: x[0].timestamp)

        # Display metadata
        st.markdown(f"Instance: **{st.session_state.current_instance}**")
        console.print(f"\n[bold blue]Annotating Instance:[/bold blue] {st.session_state.current_instance}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Skip Instance"):
                st.session_state.current_instance = None
                st.rerun()
        with col2:
            if st.button("Quit"):
                st.session_state.quit = True  # Set quit state instead of raising KeyboardInterrupt
                st.rerun()

        # Display current trajectory point
        if st.session_state.trajectory_index < len(trajectory_points):
            point, data = trajectory_points[st.session_state.trajectory_index]
            
            # Add agent name header
            st.markdown(f"### 👤 {st.session_state.current_agent}'s Trajectory")
            
            st.write(f"Time: {point.timestamp}")
            console.print(f"\n[cyan]Time:[/cyan] {point.timestamp}")

            if point.point_type == PointType.OBSERVATION:
                self._display_observation(data, point.data_reference.media_type)
            else:
                self._display_action(data, st.session_state.current_agent)

            if st.button("Next"):
                st.session_state.trajectory_index += 1
                st.rerun()
        else:
            # Trajectory complete, get annotation
            st.success("Trajectory complete!")
            console.print("\n[bold green]Trajectory complete![/bold green]")
            
            feedback = st.text_area("Please provide your feedback on the trajectory:", 
                                  value=st.session_state.feedback)
            
            if st.button("Submit Annotation"):
                # Save annotation
                self.annotation_system.add_annotation(
                    instance_id=st.session_state.current_instance,
                    agent_id=st.session_state.current_agent,
                    annotator_id=self.annotator_id,
                    content={"feedback": feedback},
                    span=AnnotationSpan(
                        start_time=trajectory_points[0][0].timestamp,
                        end_time=trajectory_points[-1][0].timestamp,
                    ),
                )
                
                st.success("Annotation saved!")
                console.print("\n[bold green]Annotation saved![/bold green]")
                
                # Reset for next instance
                st.session_state.current_instance = None
                st.session_state.trajectory_index = 0
                st.session_state.feedback = ""
                st.rerun()


@app.command()
def main(
    dataset_path: Path = typer.Argument(..., help="Path to dataset directory"),
    annotation_path: Path = typer.Argument(..., help="Path to store annotations"),
    annotator_id: str = typer.Option(..., help="Unique identifier for the annotator"),
) -> None:
    """Run the TTY annotation interface"""
    try:
        annotator = TTYAnnotator(
            dataset_path=dataset_path,
            annotation_path=annotation_path,
            annotator_id=annotator_id,
        )
        annotator.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Annotation session terminated.[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise


if __name__ == "__main__":
    app()
