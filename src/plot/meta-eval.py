import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

# Example data for all four datasets
# You should replace these with your actual data for each dataset
cogym_data = [
    [0.47, 0.50, 2],
    [0.59, 0.63, 3],
    [0.76, 0.83, 4],
    [0.74, 0.80, 4],
    [0.70, 0.67, 4],
    [0.77, 0.85, 5],
    [0.74, 0.77, 6],
    [0.75, 0.83, 7],
    [0.72, 0.85, 8],
    [0.73, 0.85, 9],
    [0.70, 0.87, 10],
    [0.68, 0.88, 11],
    [0.70, 0.88, 12],
]

# Example data for the other datasets - replace with your actual data
sotopia_data = [
    [0.31, 0.40, 2],
    [0.41, 0.62, 3],
    [0.47, 0.66, 4],
    [0.50, 0.70, 5],
    [0.57, 0.79, 6],
    [0.57, 0.80, 7],
    [0.58, 0.81, 8],
    [0.60, 0.85, 9],
    [0.60, 0.92, 10],
    [0.58, 0.91, 11],
    [0.54, 0.86, 12],
]

webarena_data = [
    [0.45, 0.48, 2],
    [0.58, 0.60, 3],
    [0.67, 0.72, 4],
    [0.85, 0.66, 5],
    [0.90, 0.70, 6],
    [0.93, 0.74, 6],
    [0.91, 0.73, 7],
    [0.88, 0.77, 8],
    [0.87, 0.75, 9],
    [0.84, 0.72, 10],
    [0.89, 0.80, 11],
    [0.86, 0.82, 12],
]

webvoyager_data = [
    [0.32, 0.30, 2],
    [0.51, 0.47, 3],
    [0.60, 0.50, 4],
    [0.76, 0.78, 5],
    [0.88, 0.72, 6],
    [0.91, 0.72, 7],
    [0.92, 0.77, 8],
    [0.91, 0.78, 9],
    [0.92, 0.80, 10],
    [0.93, 0.83, 11],
    [0.93, 0.85, 12],
]

# Convert to numpy arrays
datasets = {
    "CoGym": np.array(cogym_data),
    "Sotopia": np.array(sotopia_data),
    "WebArena": np.array(webarena_data),
    "WebVoyager": np.array(webvoyager_data),
}

# Create the figure and grid
fig = plt.figure(figsize=(6, 5))
gs = GridSpec(2, 2, figure=fig, wspace=0.3, hspace=0.3)

# Determine global min and max values for consistent axes across all plots
all_coverage = np.concatenate([d[:, 0] for d in datasets.values()])
all_redundancy = np.concatenate([d[:, 1] for d in datasets.values()])
all_n_metrics = np.concatenate([d[:, 2] for d in datasets.values()])

min_coverage, max_coverage = np.min(all_coverage) - 0.05, np.max(all_coverage) + 0.05
min_redundancy, max_redundancy = (
    np.min(all_redundancy) - 0.05,
    np.max(all_redundancy) + 0.05,
)
min_n_metrics, max_n_metrics = np.min(all_n_metrics), np.max(all_n_metrics)

# Create a scatter plot for each dataset
axes = []
scatters = []

stars = {
    "CoGym": [0.75, 0.72],
    "Sotopia": [0.58, 0.85],
    "WebArena": [0.82, 0.8],
    "WebVoyager": [0.83, 0.76],
}

square = {
    "CoGym": [0.47, 0.84],
    "Sotopia": [0.53, 0.79],
    "WebArena": [0.75, 0.88],
    "WebVoyager": [0.76, 0.91],
}

positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
for i, (dataset_name, dataset) in enumerate(datasets.items()):
    row, col = positions[i]
    ax = fig.add_subplot(gs[row, col])
    axes.append(ax)

    coverage = dataset[:, 0]
    redundancy = dataset[:, 1]
    n_metrics = dataset[:, 2]

    scatter = ax.scatter(
        redundancy,
        coverage,
        c=n_metrics,
        cmap="PiYG",
        s=100,
        alpha=0.8,
        edgecolors="k",
        vmin=min_n_metrics,
        vmax=max_n_metrics,
    )

    star_y, star_x = stars[dataset_name]
    ax.plot(
        star_x,
        star_y,
        "*",
        color="yellow",
        markersize=15,
        markeredgecolor="black",
        markeredgewidth=1.0,
    )
    scatters.append(scatter)

    square_y, square_x = square[dataset_name]
    ax.plot(
        square_x,
        square_y,
        "s",
        color="blue",
        markersize=10,
        markeredgecolor="black",
        markeredgewidth=1.0,
    )

    # Set consistent axis limits for all plots
    ax.set_xlim(min_redundancy, max_redundancy)
    ax.set_ylim(min_coverage, max_coverage)

    # Add labels and title, but remove redundancy label from first row
    # and coverage label from second column
    if row == 1:  # Only add x-axis label for bottom row
        ax.set_xlabel("Redundancy", fontsize=12)
    if col == 0:  # Only add y-axis label for left column
        ax.set_ylabel("Coverage", fontsize=12)
    ax.set_title(dataset_name, fontsize=14)

    # Add grid
    ax.grid(True, linestyle="--", alpha=0.7)

# Adjust layout before adding colorbar
plt.tight_layout(rect=(0, 0, 0.9, 1))  # Make room for the colorbar

# Add a common colorbar to the figure
cbar_ax = fig.add_axes((0.92, 0.15, 0.02, 0.7))  # [left, bottom, width, height]
cbar = fig.colorbar(scatters[0], cax=cbar_ax)

# Position N label under the colorbar
cbar.ax.set_xlabel("$N$", labelpad=5)
cbar.ax.xaxis.set_label_position("bottom")

# Save the figure
plt.savefig("four_datasets_grid.pdf", bbox_inches="tight")
plt.savefig("four_datasets_grid.png", dpi=300, bbox_inches="tight")
