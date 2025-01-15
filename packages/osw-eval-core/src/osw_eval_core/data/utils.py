# Dataset-specific utils
# In this file, we will include the utility functions to download datasets into files

# balrog
import requests
import os
from urllib.parse import quote

from pathlib import Path
from typing import Tuple, Generator

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


def download_github_folder(
    owner: str, repo: str, path: str, save_path: str, token: str | None = None
) -> None:
    """
    Recursively download a folder from GitHub

    Parameters:
    - owner: repository owner
    - repo: repository name
    - path: path to folder in repository
    - save_path: local path to save files
    - token: GitHub personal access token (optional)
    """
    headers = {}
    if token or (token := os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")):
        headers["Authorization"] = f"token {token}"

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path)}"
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get content: {response.status_code}")

    for item in response.json():
        local_path = Path(save_path) / item["name"]

        if item["type"] == "dir":
            # If it's a directory, create it and recurse
            local_path.mkdir(parents=True, exist_ok=True)

            download_github_folder(owner, repo, item["path"], local_path, token)
            print(f"Processed directory: {item['path']}")

        elif item["type"] == "file":
            # Skip if file already exists and has same size
            if local_path.exists():
                # Get local file size
                local_size = local_path.stat().st_size
                # Get GitHub file size
                github_size = item["size"]

                if local_size == github_size:
                    print(f"Skipping existing file: {item['path']}")
                    continue
                else:
                    print(f"Size mismatch, re-downloading: {item['path']}")

            # Create parent directories if they don't exist
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file content
            download_url = item["download_url"]
            file_response = requests.get(download_url, headers=headers)

            # Save the file
            with open(local_path, "wb") as f:
                f.write(file_response.content)
            print(f"Downloaded file: {item['path']}")


def file_pairs(folder_path: str) -> Generator[Tuple[Path, Path], None, None]:
    """
    Generate pairs of CSV and JSON files with matching names from a folder.

    Args:
        folder_path: Path to the folder to search in

    Yields:
        Tuple of (csv_path, json_path) for matching files
    """
    path = Path(folder_path)

    # Find all CSV files and check for JSON pairs
    for csv_file in path.rglob("*.csv"):
        json_file = csv_file.with_suffix(".json")
        if json_file.exists():
            yield csv_file, json_file


def parse_text_description(text_description: str) -> list[tuple[tuple[int, int], str]]:
    """
    Parse a text description of object positions relative to a reference point
    and convert it back into a list of relative positions and object names.

    Args:
        text_description (str): Multi-line string describing object positions

    Returns:
        list: List of tuples ((x, y), name) where x and y are relative coordinates
              and name is the object name/type
    """
    relative_positions = []

    # Split the description into individual lines
    lines = text_description.strip().split("\n")

    for line in lines:
        if not line.strip():
            continue

        # Initialize position values
        x_offset = 0
        y_offset = 0

        # Split the line into parts
        parts = line.split()

        # Extract the object name (everything before the first number)
        name_parts = []
        i = 0
        while i < len(parts) and not parts[i][0].isdigit():
            name_parts.append(parts[i])
            i += 1
        name = " ".join(name_parts)

        # Process the remaining parts for directions
        while i < len(parts):
            # Get the number of steps
            try:
                steps = int(parts[i])
            except ValueError:
                print(line)
            i += 1

            # Skip 'step' or 'steps'
            i += 1

            # Process direction
            if i < len(parts):
                if parts[i] == "to" and i + 1 < len(parts):
                    i += 1  # skip 'to'
                    if parts[i] == "the":
                        i += 1  # skip 'the'

                    if parts[i] == "right":
                        x_offset = steps
                    elif parts[i] == "left":
                        x_offset = -steps
                    i += 1

                elif parts[i] == "up":
                    y_offset = -steps
                    i += 1
                elif parts[i] == "down":
                    y_offset = steps
                    i += 1

                # Skip 'and' if present
                if i < len(parts) and parts[i] == "and":
                    i += 1

        relative_positions.append(((x_offset, y_offset), name))

    return relative_positions


def visualize_map(
    relative_positions: list[tuple[tuple[int, int], str]], reference_char: str = "@"
) -> None:
    """
    Visualize the game map using rich library for prettier output.

    Args:
        relative_positions: List of ((x, y), name) tuples
        reference_char: Character to represent the reference point (player)
    """
    console = Console()

    # Find the dimensions of the map
    min_x = min(x for (x, y), _ in relative_positions)
    max_x = max(x for (x, y), _ in relative_positions)
    min_y = min(y for (x, y), _ in relative_positions)
    max_y = max(y for (x, y), _ in relative_positions)

    # Add padding and account for reference point at (0,0)
    min_x = min(min_x, 0) - 1
    max_x = max(max_x, 0) + 1
    min_y = min(min_y, 0) - 1
    max_y = max(max_y, 0) + 1

    # Create a rich Table for the game grid
    table = Table(
        box=box.SQUARE,
        padding=0,
        show_header=True,
        header_style="bold cyan",
        show_edge=True,
    )

    # Add columns with X-coordinates as headers
    COLUMN_WIDTH = 10  # Fixed width for all columns

    # Add Y-coordinates column with the same width
    table.add_column(" ", style="bold cyan", width=COLUMN_WIDTH, justify="center")

    # Add other columns with consistent width
    for x in range(min_x, max_x + 1):
        table.add_column(
            str(x),
            justify="center",
            width=COLUMN_WIDTH,
            min_width=COLUMN_WIDTH,
            max_width=COLUMN_WIDTH,
        )

    # Helper function to get styled symbol for object
    def get_styled_symbol(name: str) -> Text:
        name = name.lower()
        if name.startswith("rule"):
            if "`" in name:
                rule_text = name.split("`")[1].split("`")[0]
                return Text(f"[{rule_text}]", style="bold yellow")
            return Text("[rule]", style="yellow")
        elif "wall" in name:
            return Text("#", style="red")
        elif "ball" in name:
            return Text("o", style="green")
        elif "key" in name:
            return Text("k", style="blue")
        else:
            return Text("*", style="white")

    # Create the grid with objects
    for y in range(min_y, max_y + 1):
        row: list[str | Text] = [str(y)]  # Y-coordinate
        for x in range(min_x, max_x + 1):
            cell_content = Text(" ")  # Empty cell by default

            # Check if this is the reference point (0,0)
            if x == 0 and y == 0:
                # Center the reference character
                padding = (COLUMN_WIDTH - 1) // 2  # -1 for single character
                cell_content = Text(
                    " " * padding + reference_char, style="bold magenta"
                )

            # Check if there's an object at this position
            for (obj_x, obj_y), name in relative_positions:
                if obj_x == x and obj_y == y:
                    symbol = get_styled_symbol(name)
                    # Center the symbol in the column width
                    padding = (COLUMN_WIDTH - len(str(symbol))) // 2
                    cell_content = Text(" " * padding) + symbol
                    break

            row.append(cell_content)
        table.add_row(*row)

    # Create legend panel
    legend_text = [
        Text("Legend:", style="bold"),
        Text(f"\n{reference_char} ", style="bold magenta")
        + Text("- Player (reference point)"),
        Text("\n# ", style="red") + Text("- Wall"),
        Text("\no ", style="green") + Text("- Ball"),
        Text("\nk ", style="blue") + Text("- Key"),
        Text("\n[text] ", style="bold yellow") + Text("- Rule"),
        Text("\n* ", style="white") + Text("- Other objects"),
    ]
    legend = Text.assemble(*legend_text)

    # Create coordinates panel
    coord_text = Text.assemble(
        Text("Grid coordinates:", style="bold"),
        Text(f"\nX: {min_x} to {max_x}"),
        Text(f"\nY: {min_y} to {max_y}"),
    )

    # Print everything
    console.print(Panel(table, title="Game Map", border_style="cyan"))
    console.print(Panel(legend, title="Legend", border_style="green"))
    console.print(Panel(coord_text, title="Coordinates", border_style="blue"))
