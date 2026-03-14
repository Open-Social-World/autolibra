#!/usr/bin/env python3

import argparse
import csv
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import List, Optional


def extract_level(filename: str) -> int:
    """Extract task level suffix like *_N where N is an integer."""
    match = re.search(r"_(\d+)", filename)
    if match:
        return int(match.group(1))
    return 999


def extract_run_name(filepath: str) -> str:
    """Extract a readable run name from a result filepath."""
    filename = Path(filepath).name
    if filename.endswith(".jsonl"):
        filename = filename[: -len(".jsonl")]

    # Normalize common prefixes while staying provider-agnostic.
    for prefix in ("llm_eval_results_", "eval_results_"):
        if filename.startswith(prefix):
            return filename[len(prefix) :]
    return filename


def calculate_success_rate(scores: List[int]) -> Optional[float]:
    """Calculate success rate = 1 / (1 + -1), excluding 0."""
    successes = sum(1 for score in scores if score == 1)
    failures = sum(1 for score in scores if score == -1)
    applicable = successes + failures
    if applicable == 0:
        return None
    return (successes / applicable) * 100


def analyze_all_results(file_paths: List[str], output_csv: str) -> None:
    """Analyze multiple evaluation files and generate a matrix CSV."""
    print(f"Analyzing {len(file_paths)} evaluation result files")
    print("=" * 80)

    all_file_results = OrderedDict()
    all_metrics = set()

    sorted_paths = sorted(
        file_paths,
        key=lambda p: (extract_level(extract_run_name(p)), extract_run_name(p)),
    )

    for filepath in sorted_paths:
        path = Path(filepath)
        if not path.exists():
            print(f"Warning: missing file {filepath}, skipping")
            continue

        run_name = extract_run_name(filepath)
        print(f"\nProcessing: {run_name}")
        file_metrics = defaultdict(list)

        with open(path, "r", encoding="utf-8") as file_obj:
            for line_num, line in enumerate(file_obj, 1):
                try:
                    result = json.loads(line.strip())
                    for field_name, field_value in result.items():
                        if isinstance(field_value, int) and not field_name.endswith(
                            "_reasoning"
                        ):
                            file_metrics[field_name].append(field_value)
                            all_metrics.add(field_name)
                except json.JSONDecodeError as exc:
                    print(f"  Parse warning on line {line_num}: {exc}")

        file_success_rates = {}
        for metric, scores in file_metrics.items():
            success_rate = calculate_success_rate(scores)
            file_success_rates[metric] = success_rate
            if success_rate is not None:
                print(f"  {metric}: {success_rate:.1f}%")
            else:
                print(f"  {metric}: N/A")

        all_file_results[run_name] = file_success_rates

    sorted_metrics = sorted(all_metrics)
    print(f"\nTotal unique metrics found: {len(sorted_metrics)}")
    print(f"Writing matrix CSV to: {output_csv}")

    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Metric"] + list(all_file_results.keys()))
        for metric in sorted_metrics:
            row = [metric]
            for run_name in all_file_results.keys():
                success_rate = all_file_results[run_name].get(metric)
                row.append(f"{success_rate:.1f}" if success_rate is not None else "")
            writer.writerow(row)

    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze multiple LLM eval JSONL files and generate a metric success matrix CSV."
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="llm_eval_results_*.jsonl",
        help="Glob pattern for result files (default: llm_eval_results_*.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="eval_results_summary.csv",
        help="Output CSV filename (default: eval_results_summary.csv)",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Directory to search (default: current directory)",
    )

    args = parser.parse_args()
    search_path = Path(args.dir)

    file_paths = list(search_path.glob(args.pattern))
    eval_results_dir = search_path / "eval_results"
    if eval_results_dir.exists():
        file_paths.extend(eval_results_dir.glob(args.pattern))

    file_paths = sorted(set(str(path) for path in file_paths))
    if not file_paths:
        print(f"No files found for pattern: {args.pattern}")
        print(f"Searched: {search_path} and {eval_results_dir}")
        return

    analyze_all_results(file_paths, args.output)


if __name__ == "__main__":
    main()
