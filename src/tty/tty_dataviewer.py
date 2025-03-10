from pathlib import Path
from typing import Any
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.table import Table
import json

from osw_data.dataset import MultiAgentDataset
from osw_data.trajectory import PointType, MediaType

console = Console()
app = typer.Typer()


class TTYDataviewer:
    """TTY-based annotation interface using Rich"""

    def __init__(self, dataset_path: Path):
        self.dataset = MultiAgentDataset(
            name="dataset",  # This will be loaded from metadata
            base_path=dataset_path,
        )

    def _select_agent(self, instance_id: str) -> str:
        """Display agent selection menu and return selected agent ID using arrow keys"""
        import sys
        import termios
        import tty

        def get_key() -> str | bool:
            """Get a single keypress from stdin"""
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return True if ch == "\x03" else ch

        instance = self.dataset.get_instance_metadata(instance_id)
        valid_agents = list(instance.agents.keys())
        current_idx = 0

        def render_menu() -> None:
            """Render the agent selection menu"""
            console.clear()
            console.print(
                "\n[bold]Available Agents:[/bold] (Use ↑↓ arrows to select, Enter to confirm)\n"
            )

            for idx, agent_id in enumerate(valid_agents):
                agent_info = instance.agents[agent_id]
                description = agent_info.model_dump_json()

                if idx == current_idx:
                    console.print(
                        f"[bold white on blue] > {agent_id}: {description}[/bold white on blue]"
                    )
                else:
                    console.print(f"   {agent_id}: {description}")

        while True:
            render_menu()
            key = get_key()

            if key == "\x1b":  # Arrow key prefix
                get_key()  # Skip the [
                arrow = get_key()

                if arrow == "A":  # Up arrow
                    current_idx = (current_idx - 1) % len(valid_agents)
                elif arrow == "B":  # Down arrow
                    current_idx = (current_idx + 1) % len(valid_agents)

            elif key == "\r":  # Enter key
                console.print(
                    f"\n[green]Selected agent:[/green] {valid_agents[current_idx]}"
                )
                return valid_agents[current_idx]

            elif key in ("q", "\x03"):  # q or Ctrl+C
                raise KeyboardInterrupt()

    def view_instance(self, instance_id: str) -> bool:
        """Annotate a specific instance"""
        console.clear()

        # Get instance metadata
        instance = self.dataset.get_instance_metadata(instance_id)

        # Display instance info
        console.print(f"\n[bold blue]Annotating Instance:[/bold blue] {instance_id}")
        console.print(Markdown("### Instance Metadata"))

        metadata_table = Table(show_header=True)
        metadata_table.add_column("Key")
        metadata_table.add_column("Value")

        for key, value in instance.metadata.items():
            metadata_table.add_row(str(key), str(value))

        # Let user select which agent to annotate
        selected_agent = self._select_agent(instance_id)

        console.print(metadata_table)
        console.print("\n")

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
                self._display_action(data)

            console.print(
                "\nPress Enter to continue, 's' to skip this instance, 'q' to quit annotation..."
            )
            user_input = input().lower()
            if user_input == "s":
                console.print("\n[yellow]Skipping this instance...[/yellow]")
                return False  # Return False to indicate skip
            elif user_input == "q":
                console.print("\n[red]Quit Annotation...[/red]")
                raise KeyboardInterrupt()

        return True

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
            # Handle HTML-like accessibility tree specially
            if (
                isinstance(data, dict)
                and "html" in data
                and isinstance(data["html"], str)
            ):
                # Display URL if present
                if "url" in data:
                    console.print(
                        Panel(f"[bold blue]{data['url']}[/bold blue]", title="URL")
                    )

                # Format and display the accessibility tree
                formatted_html = self._format_accessibility_tree(data["html"])
                console.print(Panel(formatted_html, title="Page Structure"))
            else:
                # Pretty print other JSON data
                json_str = json.dumps(data, indent=2)
                syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
                # Get console width and adjust panel width
                width = min(
                    console.width - 2, 120
                )  # Max width of 120 or console width - 2
                console.print(Panel(syntax, title="Observation (JSON)", width=width))

        elif media_type == MediaType.TEXT:
            # Display text data
            console.print(Panel(str(data), title="Observation (Text)"))

        elif media_type == MediaType.IMAGE:
            # Just indicate image dimensions for TTY interface
            console.print(f"[Image observation with shape {data.shape}]")

        else:
            console.print(f"[Unsupported media type: {media_type}]")

    def _display_action(self, data: Any) -> None:
        """Display an action"""
        if isinstance(data, dict):
            # Pretty print action data
            json_str = json.dumps(data, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
            # Get console width and adjust panel width
            width = min(console.width - 2, 120)  # Max width of 120 or console width - 2
            console.print(Panel(syntax, title="Action", width=width))
        else:
            console.print(Panel(str(data), title="Action"))

    def run(self) -> None:
        """Run the annotation interface"""
        console.clear()
        console.print("[bold]TTY Annotation Interface[/bold]\n")

        # Get all instances
        instances = self.dataset.list_instances()

        if not instances:
            console.print("[red]No instances found in dataset![/red]")
            return

        for instance_id in instances:
            console.clear()
            console.print("[bold]TTY Annotation Interface[/bold]\n")

            instance = self.dataset.get_instance_metadata(instance_id)
            console.print(f"\n[yellow]Selected instance:[/yellow] {instance_id}")
            console.print("[cyan]Instance metadata:[/cyan]")
            for key, value in instance.metadata.items():
                console.print(f"  {key}: {value}")

            self.view_instance(instance_id)

            # Annotate instance
            console.print("\nPress Enter to start annotation, or 'q' to quit...")
            if input().lower() == "q":
                break

            console.print("\nPress 'Enter' for next random instance, or 'q' to quit...")
            if input().lower() == "q":
                break


@app.command()
def main(
    dataset_path: Path = typer.Argument(..., help="Path to dataset directory"),
) -> None:
    """Run the TTY annotation interface"""
    try:
        annotator = TTYDataviewer(
            dataset_path=dataset_path,
        )
        annotator.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Annotation session terminated.[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise


if __name__ == "__main__":
    app()
