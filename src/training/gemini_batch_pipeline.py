#!/usr/bin/env python3
import subprocess
import os
from pathlib import Path
import argparse
from datetime import datetime
import json


def run_command(cmd, description, cwd=None):
    """Run a command and capture its output"""
    print(f"\n{'='*60}")
    print(f"🚀 Running: {description}")
    print(f"📍 Command: {' '.join(cmd)}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            cmd, check=True, cwd=cwd, capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {description}: {e}")
        if e.stdout:
            print(f"📄 stdout: {e.stdout}")
        if e.stderr:
            print(f"📄 stderr: {e.stderr}")
        return False


def run_command_with_env(cmd, description, env=None, cwd=None):
    """Run a command with custom environment and capture its output"""
    print(f"\n{'='*60}")
    print(f"🚀 Running: {description}")
    print(f"📍 Command: {' '.join(cmd)}")
    if env and "GEMINI_API_KEY" in env:
        print(f"🔑 Using GEMINI_API_KEY: {env['GEMINI_API_KEY'][:8]}...")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            cmd, check=True, cwd=cwd, capture_output=True, text=True, env=env
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {description}: {e}")
        if e.stdout:
            print(f"📄 stdout: {e.stdout}")
        if e.stderr:
            print(f"📄 stderr: {e.stderr}")
        return False


def get_folders_to_process(base_path):
    """Get all folders that need processing, excluding 'storage'"""
    folders = []
    base = Path(base_path)

    for folder in base.iterdir():
        if folder.is_dir() and folder.name != "storage":
            folders.append(folder.name)

    # Sort folders chronologically
    folders.sort()
    return folders


def get_metrics_path_for_folder(folder_name):
    """Determine the correct metrics path based on babaisai level in folder name"""
    if "babaisai_1" in folder_name:
        return "/home/yuxinkai_application/autolibra/.data/metrics/gemini_babaisai/2025-08-04_22-36-07_robust_cot_gemini-2.5-flash-preview-05-20/gemini_3metrics_08_05_18_35_using"
    elif "babaisai_2" in folder_name:
        return "/home/yuxinkai_application/autolibra/.data/metrics/gemini_babaisai/2025-08-07_09-28-06_babaisai_1_gemini-2.5-flash-preview-05-20/gemini_induction_8metrics_08_08_10_42_use"
    elif "babaisai_3" in folder_name:
        return "/home/yuxinkai_application/autolibra/.data/metrics/gemini_babaisai/2025-08-10_23-51-01_babaisai_2_gemini-2.5-flash-preview-05-20/gemini_induction_11metrics_08_11_20_10"
    else:
        print(
            f"⚠️  Warning: Could not determine babaisai level from folder name: {folder_name}"
        )
        return None


def process_single_folder(
    folder_name,
    metrics_path=None,
    skip_convert=False,
    skip_babaisai=False,
    skip_llm_eval=False,
    api_key=None,
):
    """Process a single folder through the entire pipeline"""
    workspace_path = Path("/home/yuxinkai_application/autolibra")

    print(f"\n{'#'*80}")
    print(f"# Processing folder: {folder_name}")
    print(f"{'#'*80}")

    # Track success through pipeline stages
    success = True

    # Step 1: Convert Balrog format
    if not skip_convert:
        source_path = workspace_path / ".data" / "raw" / "gemini_babaisai" / folder_name
        cmd1 = [
            "python",
            "-m",
            "autolibra_core.datasets.convert_balrog_format",
            "--source",
            str(source_path),
        ]
        success = run_command(cmd1, f"Convert Balrog Format - {folder_name}", cwd=None)
        if not success:
            print(
                f"⚠️  Skipping remaining steps for {folder_name} due to conversion error"
            )
            return False

    # Step 2: Process Balrog Babaisai
    if success and not skip_babaisai:
        cmd2 = [
            "python",
            "-m",
            "autolibra_core.datasets.balrog_babaisai",
            "--filename",
            f"gemini_babaisai/{folder_name}",
        ]
        success = run_command(
            cmd2, f"Balrog Babaisai Processing - {folder_name}", cwd=None
        )
        if not success:
            print(
                f"⚠️  Skipping LLM evaluation for {folder_name} due to babaisai processing error"
            )
            return False

    # Step 3: Run LLM as a Judge (Gemini version)
    if success and not skip_llm_eval:
        # Set up environment with API key
        env = os.environ.copy()
        if api_key:
            env["GEMINI_API_KEY"] = api_key

        # Build command with exact format
        cmd3 = [
            "uv",
            "run",
            "python",
            "-m",
            "src.training.llm_as_a_judge_gemini",
            "--filename",
            f"gemini_babaisai/{folder_name}",
        ]

        # Determine metrics path: use provided one or auto-detect based on folder name
        final_metrics_path = metrics_path
        if not final_metrics_path:
            final_metrics_path = get_metrics_path_for_folder(folder_name)
            if final_metrics_path:
                print("📊 Auto-detected metrics path based on babaisai level")

        # Add metric path if available
        if final_metrics_path:
            cmd3.extend(["--metric-path", final_metrics_path])
            print(f"📍 Using metrics: {final_metrics_path}")
        else:
            print(
                "⚠️  No metrics path specified and could not auto-detect from folder name"
            )
            return False

        # Run with modified environment
        success = run_command_with_env(
            cmd3, f"LLM as a Judge (Gemini) - {folder_name}", env=env
        )

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Run the batch processing pipeline for Gemini Balrog data"
    )
    parser.add_argument(
        "--folders",
        nargs="+",
        help="Specific folders to process (if not specified, process all)",
    )
    parser.add_argument(
        "--metric-path",
        help="Path to the metrics directory for LLM evaluation (auto-detected based on babaisai level if not specified)",
    )
    parser.add_argument(
        "--skip-convert",
        action="store_true",
        help="Skip the convert_balrog_format step",
    )
    parser.add_argument(
        "--skip-babaisai", action="store_true", help="Skip the balrog_babaisai step"
    )
    parser.add_argument(
        "--skip-llm-eval", action="store_true", help="Skip the LLM evaluation step"
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing other folders even if one fails",
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API key (required for LLM evaluation unless --skip-llm-eval is used)",
    )

    args = parser.parse_args()

    # Check if API key is required
    if not args.skip_llm_eval and not args.api_key:
        parser.error("--api-key is required unless --skip-llm-eval is specified")

    # Get folders to process
    base_path = "/home/yuxinkai_application/autolibra/.data/raw/gemini_babaisai"

    if args.folders:
        folders_to_process = args.folders
    else:
        folders_to_process = get_folders_to_process(base_path)

    print(f"📁 Found {len(folders_to_process)} folders to process:")
    for i, folder in enumerate(folders_to_process, 1):
        print(f"   {i:2d}. {folder}")

    # Process each folder
    start_time = datetime.now()
    successful = 0
    failed = []

    for i, folder in enumerate(folders_to_process, 1):
        print(f"\n{'='*80}")
        print(f"📊 Progress: {i}/{len(folders_to_process)} folders")
        print(f"{'='*80}")

        try:
            success = process_single_folder(
                folder,
                args.metric_path,
                args.skip_convert,
                args.skip_babaisai,
                args.skip_llm_eval,
                args.api_key,
            )

            if success:
                successful += 1
            else:
                failed.append(folder)
                if not args.continue_on_error:
                    print(f"\n❌ Stopping due to error in {folder}")
                    break

        except Exception as e:
            print(f"❌ Unexpected error processing {folder}: {e}")
            failed.append(folder)
            if not args.continue_on_error:
                break

    # Summary
    elapsed_time = datetime.now() - start_time
    print(f"\n{'='*80}")
    print("🏁 PIPELINE COMPLETE")
    print(f"{'='*80}")
    print(f"⏱️  Total time: {elapsed_time}")
    print(f"✅ Successful: {successful}/{len(folders_to_process)}")

    if failed:
        print(f"❌ Failed: {len(failed)}")
        for folder in failed:
            print(f"   - {folder}")

    # Save summary to file
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_folders": len(folders_to_process),
        "successful": successful,
        "failed": failed,
        "elapsed_time": str(elapsed_time),
        "options": {
            "skip_convert": args.skip_convert,
            "skip_babaisai": args.skip_babaisai,
            "skip_llm_eval": args.skip_llm_eval,
            "metric_path": args.metric_path,
        },
    }

    summary_file = (
        f"gemini_pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n📄 Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
