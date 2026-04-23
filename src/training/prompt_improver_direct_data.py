#!/usr/bin/env python3

"""
AutoLibra Prompt Improvement System - DIRECT DATA VERSION

Enhanced to pass metrics, evaluations, and trajectories directly to LLM for metric optimization

KEY FEATURES:
1. 8 Generalizable Prompting Strategies (not game-specific, no coding)
2. Direct passing of raw metrics, evaluations, and trajectories to LLM
3. Metric optimization focus - agent aims to maximize all metric scores
4. Flexible Adaptive Template Structure
5. Manual Rule Input Section (for cross-game generalizability)
6. Agent-Only Evolution (no environment changes)

CORE IMPROVEMENT:
- LLM receives ALL raw data directly instead of pre-processed summaries
- Explicit instruction to optimize for metric performance
- Better utilization of all three data sources
"""

import json
import os
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import google.generativeai as genai
import yaml


class AutoLibraPromptImprover:
    """AutoLibra-style prompt improvement system with direct data passing."""

    def __init__(
        self,
        base_dir: str = "prompt_optimization",
        config_path: str | None = None,
        provider: str = "gemini",
        azure_model: str | None = None,
    ):
        """Initialize the prompt improver."""
        self.workspace_dir = Path.cwd()
        self.config_path = (
            Path(config_path)
            if config_path
            else self.workspace_dir / "prompt_optimization" / "config.yaml"
        )
        self.config = self._load_config(self.config_path)

        paths_cfg = self.config.get("paths", {})
        active_cfg = self.config.get("active", {})
        provider_cfg = self.config.get("provider", {})
        naming_cfg = self.config.get("naming", {})

        self.base_dir = self._resolve_path(paths_cfg.get("base_dir", base_dir))
        self.repo_name = active_cfg.get("repo")
        self.game_name = active_cfg.get("game")
        self.agent_prefix = naming_cfg.get("agent_prefix")
        self.agent_filename_template = naming_cfg.get("agent_filename_template")
        self.provider = provider_cfg.get("name", provider).lower()
        self.azure_model = provider_cfg.get("azure_model", azure_model)

        self._validate_required_config()

        self.turn_info_dir_template = paths_cfg.get(
            "turn_info_dir_template",
            "{base_dir}/repos/{repo}/{game}/turns/turn_{turn}/info",
        )
        self.turn_output_dir_template = paths_cfg.get(
            "turn_output_dir_template",
            "{base_dir}/repos/{repo}/{game}/turns/turn_{turn}/output",
        )
        self.turns_dir = self._resolve_path(
            paths_cfg.get("turns_dir", "{base_dir}/repos/{repo}/{game}/turns")
        )
        self.seed_agent_path = self._resolve_path(
            paths_cfg.get(
                "seed_agent_path", "{base_dir}/repos/{repo}/{game}/prompt_seed/agent.py"
            )
        )
        self.rules_path = self._resolve_path(
            paths_cfg.get("rules_path", "{base_dir}/repos/{repo}/{game}/rules.md")
        )
        self.current_turn = self._detect_current_turn()

        # Set up LLM client (Gemini by default, Azure OpenAI optional)
        self.llm_client = self._setup_llm_client()

        # Load prompting strategies knowledge base
        self.prompting_strategies = self._init_prompting_strategies()

        # Load metrics and evaluation data
        self.metrics = self._load_metrics()
        self.eval_results = self._load_evaluation_results()

        print(
            f"🚀 AutoLibra Prompt Improver initialized with {len(self.prompting_strategies)} generalizable strategies"
        )
        print(f"📍 Current turn: {self.current_turn}")
        print(f"📊 Loaded {len(self.metrics)} metrics")
        print(f"🎯 Loaded {len(self.eval_results)} evaluation results")
        print("🔧 Mode: Agent-only evolution with DIRECT DATA passing")
        print("⚡ Strategy: 8 generalizable prompting techniques + metric optimization")
        print(f"📝 Rule input source: {self.rules_path}")

        # Show the generalizable strategies
        strategy_names = list(self.prompting_strategies.keys())
        print(
            f"🎯 {len(strategy_names)} Generalizable Strategies: {', '.join(strategy_names)}"
        )

        # Verify trajectory linking
        linked_count = sum(
            1 for result in self.eval_results if "trajectory_data" in result
        )
        print(
            f"🔗 Successfully linked {linked_count}/{len(self.eval_results)} trajectories"
        )
        print("📋 Template: Adaptive flexible prompt structure")
        print(f"🎮 Active target: repo={self.repo_name}, game={self.game_name}")
        print("🎯 NEW: Direct data passing for metric optimization")

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load YAML config file for prompt optimization."""
        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}. "
                "Create prompt_optimization/config.yaml before running improver."
            )
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config must be a mapping: {config_path}")
        return loaded

    def _validate_required_config(self) -> None:
        """Validate required config values for generic, non-hardcoded execution."""
        missing = []
        if not self.repo_name:
            missing.append("active.repo")
        if not self.game_name:
            missing.append("active.game")
        if not self.agent_prefix:
            missing.append("naming.agent_prefix")
        if not self.agent_filename_template:
            missing.append("naming.agent_filename_template")
        if not self.provider:
            missing.append("provider.name")

        if missing:
            raise ValueError(
                "Missing required config values in prompt_optimization/config.yaml: "
                + ", ".join(missing)
            )

    def _resolve_path(self, raw_path: str | Path) -> Path:
        """Resolve path with template placeholders against workspace root."""
        raw = str(raw_path)
        context = {
            "workspace": str(getattr(self, "workspace_dir", Path.cwd())),
            "base_dir": str(
                getattr(self, "base_dir", Path.cwd() / "prompt_optimization")
            ),
            "repo": getattr(self, "repo_name", ""),
            "game": getattr(self, "game_name", ""),
            "turn": getattr(self, "current_turn", 0),
            "agent_prefix": getattr(self, "agent_prefix", "Agent"),
            "agent_prefix_lower": getattr(self, "agent_prefix", "Agent").lower(),
        }
        formatted = raw.format(**context)
        path = Path(formatted)
        if path.is_absolute():
            return path
        return getattr(self, "workspace_dir", Path.cwd()) / path

    def _get_turn_info_dir(self, turn: int) -> Path:
        return self._resolve_path(
            self.turn_info_dir_template.format(
                base_dir=str(self.base_dir),
                workspace=str(self.workspace_dir),
                repo=self.repo_name,
                game=self.game_name,
                turn=turn,
                agent_prefix=self.agent_prefix,
                agent_prefix_lower=self.agent_prefix.lower(),
            )
        )

    def _get_turn_output_dir(self, turn: int) -> Path:
        return self._resolve_path(
            self.turn_output_dir_template.format(
                base_dir=str(self.base_dir),
                workspace=str(self.workspace_dir),
                repo=self.repo_name,
                game=self.game_name,
                turn=turn,
                agent_prefix=self.agent_prefix,
                agent_prefix_lower=self.agent_prefix.lower(),
            )
        )

    def _get_agent_filename(self, agent_number: int) -> str:
        return self.agent_filename_template.format(
            agent_prefix=self.agent_prefix,
            agent_prefix_lower=self.agent_prefix.lower(),
            agent_number=agent_number,
        )

    def _load_rule_input_section(self) -> str:
        if self.rules_path.exists():
            return self._load_file(self.rules_path)
        raise FileNotFoundError(
            f"Rule file not found at {self.rules_path}. "
            "Set paths.rules_path in prompt_optimization/config.yaml."
        )

    def show_rule_input_location(self):
        """Show user how the game context system works for optimal prompt generation."""

        print("\n" + "=" * 60)
        print("📝 GAME CONTEXT SYSTEM INFORMATION")
        print("=" * 60)
        print("")
        print(
            "🎮 The improver uses game context to generate optimized, domain-specific"
        )
        print("   agent prompts tailored for maximum performance in the target game.")
        print("")
        print("📍 How it works: The system prompt includes detailed game information")
        print("   that informs the LLM about game mechanics, rules, and strategies.")
        print("")
        print("📋 This game context includes:")
        print("   - Available actions and game mechanics")
        print("   - Winning conditions and objectives")
        print("   - Game-specific rules and constraints")
        print("   - Object types and interactions")
        print("")
        print("✅ Result: The generated agent prompt is highly specific and optimized")
        print("   for this game domain, leading to better performance.")
        print("")
        print("🔧 For different games: Update the rule_input_section in the code")
        print("   with the new game's context information.")
        print("")
        return "Game context system information displayed"

    def _setup_llm_client(self):
        """Setup LLM client based on provider."""
        if self.provider == "gemini":
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
            return {"provider": "gemini", "model": genai.GenerativeModel(model_name)}
        elif self.provider == "azure":
            from openai import AzureOpenAI

            api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
            model_name = (
                self.azure_model
                or os.getenv("AZURE_OPENAI_DEPLOYMENT")
                or os.getenv("AZURE_OPENAI_4O_MODEL")
            )
            if not api_key or not endpoint or not model_name:
                raise ValueError(
                    "Azure provider selected but AZURE_OPENAI_API_KEY/ENDPOINT/DEPLOYMENT not set"
                )
            client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version="2024-12-01-preview",
            )
            return {"provider": "azure", "client": client, "model": model_name}
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_text(self, prompt: str) -> str:
        """Generate text from the configured LLM provider."""
        if self.llm_client["provider"] == "gemini":
            response = self.llm_client["model"].generate_content(prompt)
            return response.text
        elif self.llm_client["provider"] == "azure":
            completion = self.llm_client["client"].chat.completions.create(
                model=self.llm_client["model"],
                messages=[{"role": "user", "content": prompt}],
            )
            return completion.choices[0].message.content
        else:
            raise ValueError(f"Unsupported provider: {self.llm_client['provider']}")

    def _detect_current_turn(self) -> int:
        """Detect which turn we're currently on based on existing files."""
        if not self.turns_dir.exists():
            return 0

        existing_turns = sorted(
            int(d.name.replace("turn_", ""))
            for d in self.turns_dir.iterdir()
            if d.is_dir() and d.name.startswith("turn_")
        )
        if not existing_turns:
            return 0

        # Prefer the first turn that has info but no generated output yet.
        for turn in existing_turns:
            info_dir = self._get_turn_info_dir(turn)
            expected_agent = self._get_agent_filename(turn + 1)
            output_agent_path = self._get_turn_output_dir(turn) / expected_agent

            if info_dir.exists() and not output_agent_path.exists():
                return turn

        # Otherwise continue to the next turn index.
        return max(existing_turns) + 1

    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics definitions with robust directory discovery."""
        metrics = {}

        # Systematically search for metrics directories in the appropriate turn info directory
        turn_info_dir = self._get_turn_info_dir(self.current_turn)

        if not turn_info_dir.exists():
            raise FileNotFoundError(
                f"Could not find {turn_info_dir.name} directory at {turn_info_dir}"
            )

        # Find all metrics directories
        metrics_dirs = []
        for subdir in turn_info_dir.iterdir():
            if subdir.is_dir():
                metrics_dir = subdir / "metrics"
                if metrics_dir.exists():
                    metrics_dirs.append(metrics_dir)

        if not metrics_dirs:
            raise FileNotFoundError(
                f"Could not find any metrics directory in {turn_info_dir.name}"
            )

        # Use the first metrics directory found
        metrics_dir = metrics_dirs[0]
        print(f"📍 Loading metrics from: {metrics_dir.relative_to(self.base_dir)}")

        # Load all metric JSON files
        for metric_file in metrics_dir.glob("*.json"):
            try:
                with open(metric_file, "r") as f:
                    metric_data = json.load(f)
                    metrics[metric_data["name"]] = metric_data
            except Exception as e:
                print(f"⚠️ Error loading metric {metric_file}: {e}")

        print(f"📋 Loaded {len(metrics)} metrics: {list(metrics.keys())}")
        return metrics

    def _load_evaluation_results(self) -> List[Dict]:
        """Load evaluation results with trajectory linking."""
        results = []

        # Find evaluation results files in the appropriate turn info directory
        turn_info_dir = self._get_turn_info_dir(self.current_turn)

        eval_files = []

        for subdir in turn_info_dir.iterdir():
            if subdir.is_dir():
                # Look for evaluation files with various naming patterns
                for pattern in [
                    "llm_eval_results_*metrics.jsonl",
                    "llm_eval_results*.jsonl",
                    "eval_results*.jsonl",
                ]:
                    eval_files.extend(subdir.glob(pattern))

        if not eval_files:
            raise FileNotFoundError(
                f"Could not find evaluation results file in {turn_info_dir.name}"
            )

        # Use the first evaluation file found
        eval_file = eval_files[0]
        print(f"📄 Loading evaluation results from: {eval_file.name}")

        # Load evaluation results and link trajectories
        with open(eval_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        result = json.loads(line)

                        # Link trajectory data using instance_id
                        if "instance_id" in result:
                            trajectory_data = self._load_trajectory_by_instance_id(
                                result["instance_id"]
                            )
                            if trajectory_data:
                                result["trajectory_data"] = trajectory_data

                        results.append(result)

                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON decode error on line {line_num}: {e}")
                    except Exception as e:
                        print(f"⚠️ Error processing line {line_num}: {e}")

        print(f"📊 Loaded {len(results)} evaluation results")
        return results

    def _load_trajectory_by_instance_id(self, instance_id: str) -> Optional[Dict]:
        """Load detailed trajectory data for a specific instance ID using the exact folder structure."""
        try:
            # Use the appropriate turn info directory based on current turn
            turn_info_dir = self._get_turn_info_dir(self.current_turn)

            instances_dir = turn_info_dir / "instances"
            if not instances_dir.exists():
                print(f"⚠️ Instances directory not found at {instances_dir}")
                return None

            instance_path = instances_dir / instance_id
            if not instance_path.exists():
                print(f"⚠️ Instance {instance_id} not found")
                return None

            # Load metadata
            metadata_file = instance_path / "metadata.json"
            if not metadata_file.exists():
                print(f"⚠️ No metadata found for instance {instance_id}")
                return None

            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # Load trajectory data from json_data directory as specified in the long request
            json_data_dir = instance_path / "agent" / "json_data"
            if not json_data_dir.exists():
                print(f"⚠️ No json_data directory found for instance {instance_id}")
                return None

            # Parse trajectory data chronologically
            trajectory_data = {
                "instance_id": instance_id,
                "metadata": metadata,
                "steps": [],
                "task": metadata.get("metadata", {}).get("task", "unknown"),
                "source_model": metadata.get("metadata", {}).get(
                    "source_model", "unknown"
                ),
            }

            # Group observation and action files by timestamp
            obs_files = {}
            action_files = {}

            for file_path in json_data_dir.glob("*.json"):
                file_name = file_path.name

                # Legacy format: "<step>_observation.json" / "<step>_action.json"
                legacy_match = re.match(r"(\d+)_(observation|action)\.json$", file_name)
                if legacy_match:
                    timestamp = int(legacy_match.group(1))
                    file_type = legacy_match.group(2)
                    if file_type == "observation":
                        obs_files[timestamp] = file_path
                    else:
                        action_files[timestamp] = file_path
                    continue

                # Current BALROG-style format:
                # "<instance>_agent_observation_<iso-ts>.json" / "<instance>_agent_action_<iso-ts>.json"
                modern_match = re.match(
                    r".*_agent_(observation|action)_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\.json$",
                    file_name,
                )
                if modern_match:
                    file_type = modern_match.group(1)
                    iso_ts = modern_match.group(2)
                    try:
                        dt = datetime.fromisoformat(iso_ts)
                        # Use microseconds epoch as sortable numeric key.
                        timestamp = int(dt.timestamp() * 1_000_000)
                    except ValueError:
                        # Fallback: keep lexical order if timestamp parsing fails.
                        timestamp = len(obs_files) + len(action_files)

                    if file_type == "observation":
                        obs_files[timestamp] = file_path
                    else:
                        action_files[timestamp] = file_path

            # Process files in chronological order
            for timestamp in sorted(set(obs_files.keys()) | set(action_files.keys())):
                step_data = {"timestamp": timestamp}

                # Load observation
                if timestamp in obs_files:
                    try:
                        with open(obs_files[timestamp], "r") as f:
                            step_data["observation"] = json.load(f)
                    except Exception as e:
                        print(f"⚠️ Error loading observation at {timestamp}: {e}")

                # Load action
                if timestamp in action_files:
                    try:
                        with open(action_files[timestamp], "r") as f:
                            action_data = json.load(f)
                            # Support both old and new action payload keys.
                            step_data["action"] = (
                                action_data.get("completion")
                                or action_data.get("text")
                                or action_data.get("action")
                                or ""
                            )
                            step_data["reasoning"] = action_data.get("reasoning", "")
                    except Exception as e:
                        print(f"⚠️ Error loading action at {timestamp}: {e}")

                # Normalize common observation payload variants to a canonical `obs` field.
                if "observation" in step_data and isinstance(
                    step_data["observation"], dict
                ):
                    observation = step_data["observation"]
                    if "obs" not in observation and "observations" in observation:
                        observation["obs"] = observation.get("observations", "")

                trajectory_data["steps"].append(step_data)

            return trajectory_data

        except Exception as e:
            print(f"⚠️ Error loading trajectory for {instance_id}: {e}")
            return None

    def _init_prompting_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize 8 generalizable prompting strategies for any game domain."""
        return {
            "direct_instruction": {
                "description": "State goals, rules, and objectives explicitly at the start",
                "applicable_failures": [
                    "unclear objectives",
                    "rule confusion",
                    "inaction",
                    "goal confusion",
                ],
                "applicable_successes": [
                    "clear understanding",
                    "focused execution",
                    "rule compliance",
                ],
                "implementation": "Add explicit goal statements and rule explanations in prompt introduction",
                "example": "Your primary goal is [specific objective]. The key rules are: [rule list]. Always focus on achieving this objective.",
            },
            "few_shot": {
                "description": "Provide examples demonstrating successful task completion and reinforce winning patterns",
                "applicable_failures": [
                    "unclear strategies",
                    "no examples",
                    "abstract concepts",
                    "poor understanding",
                    "lack of pattern recognition",
                ],
                "applicable_successes": [
                    "efficient solutions",
                    "correct approaches",
                    "clear reasoning",
                    "systematic execution",
                    "goal achievement",
                ],
                "implementation": "Include 3-5 examples of successful task completion with step-by-step reasoning, emphasizing patterns that led to success",
                "example": "Example 1: [situation] -> Analysis: [reasoning] -> Action: [chosen action] -> Result: [successful outcome]. Key pattern: [what made this successful]",
            },
            "chain_of_thought_enhanced": {
                "description": "Force comprehensive step-by-step reasoning with mandatory analytical components",
                "applicable_failures": [
                    "shallow analysis",
                    "missing key insights",
                    "rushed decisions",
                    "incomplete reasoning",
                ],
                "applicable_successes": [
                    "structured thinking",
                    "complete analysis",
                    "careful evaluation",
                ],
                "implementation": "Create structured reasoning template with required analysis steps: current state, goal identification, option evaluation, consequence prediction, decision validation",
                "example": "REQUIRED ANALYSIS: 1) Current situation assessment 2) Goal identification 3) Available options evaluation 4) Consequence prediction 5) Strategic evaluation 6) Best choice justification",
            },
            "action_forcing": {
                "description": "Prevent inaction and enforce productive decision-making every turn",
                "applicable_failures": [
                    "idle behavior",
                    "no actions",
                    "static agent",
                    "decision avoidance",
                ],
                "applicable_successes": [
                    "consistent progress",
                    "decisive action",
                    "goal-oriented behavior",
                ],
                "implementation": "Strong anti-idle bias with mandatory action requirements and productivity validation",
                "example": "MANDATORY: Take a productive action every turn. Avoid waiting or inaction unless critically necessary for success.",
            },
            "constraint_awareness": {
                "description": "Explicitly identify and respect all system constraints and limitations",
                "applicable_failures": [
                    "constraint violations",
                    "impossible actions",
                    "rule breaking",
                    "invalid moves",
                ],
                "implementation": "Clear constraint identification and mandatory validation before action selection",
                "example": "System constraints: [list all limitations]. Always verify chosen actions respect these constraints before executing.",
            },
            "progressive_hinting": {
                "description": "Provide escalating levels of guidance when agent struggles or gets stuck",
                "applicable_failures": [
                    "persistent confusion",
                    "unable to start",
                    "analysis paralysis",
                    "decision paralysis",
                ],
                "implementation": "Multi-level hint system: general principles -> specific approaches -> direct action suggestions",
                "example": "If stuck: Level 1) General strategy hints, Level 2) Specific approach guidance, Level 3) Direct action recommendations",
            },
            "checklist_validation": {
                "description": "Validate all decisions against comprehensive criteria before committing to actions",
                "applicable_failures": [
                    "invalid moves",
                    "rule violations",
                    "hasty decisions",
                    "action errors",
                ],
                "implementation": "Mandatory pre-action validation checklist with specific pass/fail criteria for decision quality",
                "example": "Before acting, verify: (A) Does this advance the goal? (B) Is this action valid? (C) Are there better alternatives? (D) What are the risks?",
            },
            "negative_prompting": {
                "description": "Explicitly forbid critical errors that guarantee task failure",
                "applicable_failures": [
                    "irreversible mistakes",
                    "task-ending actions",
                    "critical resource destruction",
                    "goal-blocking moves",
                ],
                "implementation": "Identify and prohibit only the most severe failure patterns that make task completion impossible",
                "example": "CRITICAL PROHIBITIONS: Never take actions that permanently prevent task completion. Never destroy essential resources. Never create irreversible blockages.",
            },
        }

    def _load_prompts(self) -> Tuple[str, str]:
        """Load current prompts (env and agent)."""
        if self.current_turn == 0:
            # At turn 0, load vanilla prompts
            env_prompt = None
            agent_prompt = self._load_vanilla_agent_prompt()
        else:
            prev_turn_dir = self._get_turn_output_dir(self.current_turn - 1)
            # No environment evolution, return None for env_prompt
            env_prompt = None
            # Load the agent from previous turn
            prev_agent_filename = self._get_agent_filename(self.current_turn)
            agent_prompt = self._load_file(prev_turn_dir / prev_agent_filename)

        return env_prompt, agent_prompt

    def _load_vanilla_agent_prompt(self) -> str:
        """Load the vanilla agent prompt."""
        return self._load_file(self.seed_agent_path)

    def _load_file(self, filepath: Path) -> str:
        """Load content from a file."""
        with open(filepath, "r") as f:
            return f.read()

    def _analyze_performance(self) -> Dict[str, Any]:
        """Analyze current performance with trajectory-aware insights."""
        # Calculate average scores per metric
        metric_scores = {}
        total_results = len(self.eval_results)

        for metric_name in self.metrics.keys():
            # Convert metric name to evaluation result key format
            metric_key = metric_name.lower().replace(" ", "_").replace("-", "_")

            scores = []
            for result in self.eval_results:
                if metric_key in result:
                    scores.append(result[metric_key])

            if scores:
                metric_scores[metric_name] = {
                    "average": sum(scores) / len(scores),
                    "total_samples": len(scores),
                    "all_negative": all(score < 0 for score in scores),
                    "all_positive": all(score > 0 for score in scores),
                }

        # Enhanced trajectory analysis
        trajectory_insights = self._analyze_trajectory_patterns()

        # Get ALL failure reasoning
        all_failure_reasoning = []
        for result in self.eval_results:
            for key, value in result.items():
                if key.endswith("_reasoning") and isinstance(value, str):
                    all_failure_reasoning.append(value)

        return {
            "metric_scores": metric_scores,
            "all_failure_reasoning": all_failure_reasoning,
            "total_evaluations": total_results,
            "trajectory_insights": trajectory_insights,
        }

    def _analyze_trajectory_patterns(self) -> Dict[str, Any]:
        """Analyze patterns from linked trajectory data."""
        insights = {
            "total_trajectories_analyzed": 0,
            "successful_trajectories": 0,
            "failed_trajectories": 0,
            "action_failure_patterns": [],
            "observation_format_examples": [],
            "reasoning_quality_stats": {},
            "common_failure_modes": [],
            "successful_patterns": [],
        }

        action_failures = 0
        idle_actions = 0
        reasoning_lengths = []

        for result in self.eval_results:
            if "trajectory_data" not in result:
                continue

            trajectory = result["trajectory_data"]
            insights["total_trajectories_analyzed"] += 1

            # Determine success/failure
            metric_scores = []
            for metric in self.metrics.keys():
                metric_key = metric.lower().replace(" ", "_").replace("-", "_")
                score = result.get(metric_key, 0)
                metric_scores.append(score)

            # Classify as successful only if majority of metrics are positive
            positive_scores = sum(1 for score in metric_scores if score > 0)
            total_scores = len(metric_scores)
            is_successful = positive_scores > total_scores / 2  # Majority positive

            if is_successful:
                insights["successful_trajectories"] += 1
                # Analyze successful patterns
                successful_pattern = {
                    "task": trajectory["task"],
                    "total_steps": len(trajectory["steps"]),
                    "successful_metrics": [
                        metric
                        for metric in self.metrics.keys()
                        if result.get(
                            metric.lower().replace(" ", "_").replace("-", "_"), 0
                        )
                        > 0
                    ],
                    "efficiency": "High"
                    if len(trajectory["steps"]) < 50
                    else "Moderate",
                }
                insights["successful_patterns"].append(successful_pattern)
            else:
                insights["failed_trajectories"] += 1
                # Analyze failure modes
                failed_metrics_details = []
                for metric in self.metrics.keys():
                    metric_key = metric.lower().replace(" ", "_").replace("-", "_")
                    score = result.get(metric_key, 0)
                    if score < 0:
                        reasoning_key = f"{metric_key}_reasoning"
                        reasoning = result.get(reasoning_key, "No reasoning provided")
                        failed_metrics_details.append(
                            {"metric": metric, "score": score, "reasoning": reasoning}
                        )

                if failed_metrics_details:
                    failure_mode = {
                        "task": trajectory["task"],
                        "failure_type": "Multiple metric failures"
                        if len(failed_metrics_details) > 1
                        else failed_metrics_details[0]["metric"],
                        "failed_metrics": failed_metrics_details,
                    }
                    insights["common_failure_modes"].append(failure_mode)

            # Analyze observation format
            if trajectory["steps"] and len(insights["observation_format_examples"]) < 3:
                first_obs = trajectory["steps"][0].get("observation", {})
                if isinstance(first_obs, dict):
                    # Reconstruct the observation text format
                    obs_text = first_obs.get("obs", "")
                    if obs_text:
                        insights["observation_format_examples"].append(
                            {
                                "task": trajectory["task"],
                                "observation_sample": obs_text[:500] + "..."
                                if len(obs_text) > 500
                                else obs_text,
                            }
                        )

            # Analyze action patterns
            for step in trajectory["steps"]:
                action = step.get("action", "").strip().lower()
                reasoning = step.get("reasoning", "")

                if action:
                    if action == "failed to obtain a valid action from the reasoning.":
                        action_failures += 1
                        insights["action_failure_patterns"].append(
                            {
                                "instance_id": trajectory["instance_id"],
                                "task": trajectory["task"],
                                "step_number": step["timestamp"],
                                "reasoning_sample": reasoning[:200] + "..."
                                if len(reasoning) > 200
                                else reasoning,
                            }
                        )
                    elif action == "idle":
                        idle_actions += 1

                # Analyze reasoning quality
                if reasoning:
                    reasoning_lengths.append(len(reasoning))

        # Summarize reasoning quality
        if reasoning_lengths:
            insights["reasoning_quality_stats"] = {
                "average_length": sum(reasoning_lengths) / len(reasoning_lengths),
                "min_length": min(reasoning_lengths),
                "max_length": max(reasoning_lengths),
                "total_action_failures": action_failures,
                "total_idle_actions": idle_actions,
            }

        return insights

    def _analyze_failure_patterns(
        self, performance_analysis: Dict[str, Any]
    ) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """Analyze failure patterns from reasoning text."""
        # Define failure pattern keywords (generalizable)
        failure_keywords = {
            "spatial_confusion": [
                "wrong direction",
                "incorrect position",
                "spatial",
                "relative position",
                "confused about location",
                "misidentified position",
                "wrong relative",
            ],
            "rule_confusion": [
                "rule",
                "confused",
                "unclear rule",
                "rule interpretation",
                "misunderstood rule",
            ],
            "goal_confusion": [
                "unclear goal",
                "wrong objective",
                "confused about goal",
                "incorrect target",
            ],
            "action_execution": [
                "failed to obtain",
                "invalid action",
                "parsing",
                "action format",
            ],
            "strategic_planning": [
                "no clear strategy",
                "poor planning",
                "inefficient",
                "indirect path",
            ],
            "inaction": ["idle", "no action", "static", "waiting unnecessarily"],
            "constraint_violation": [
                "invalid move",
                "blocked",
                "boundary",
                "constraint violated",
            ],
            "resource_management": [
                "destroyed",
                "lost critical",
                "trapped essential",
                "isolated important",
            ],
        }

        # Count occurrences
        pattern_counts = {pattern: 0 for pattern in failure_keywords}
        pattern_to_metric_details = {
            pattern: {"count": 0, "metrics": [], "examples": []}
            for pattern in failure_keywords
        }

        # First pass: collect all metric failures and their reasoning
        for result in self.eval_results:
            for metric_name in self.metrics.keys():
                metric_key = metric_name.lower().replace(" ", "_").replace("-", "_")
                reasoning_key = f"{metric_key}_reasoning"

                score = result.get(metric_key, 0)
                reasoning = result.get(reasoning_key, "")

                if score < 0 and reasoning:  # Negative score = failure
                    reasoning_lower = reasoning.lower()

                    # Check each failure pattern
                    for pattern, keywords in failure_keywords.items():
                        if any(keyword in reasoning_lower for keyword in keywords):
                            pattern_counts[pattern] += 1
                            pattern_to_metric_details[pattern]["count"] += 1

                            if (
                                metric_name
                                not in pattern_to_metric_details[pattern]["metrics"]
                            ):
                                pattern_to_metric_details[pattern]["metrics"].append(
                                    metric_name
                                )

                            # Keep up to 3 examples per pattern
                            if len(pattern_to_metric_details[pattern]["examples"]) < 3:
                                pattern_to_metric_details[pattern]["examples"].append(
                                    {
                                        "metric": metric_name,
                                        "reasoning": reasoning[:200] + "..."
                                        if len(reasoning) > 200
                                        else reasoning,
                                        "score": score,
                                    }
                                )

        # Sort by frequency
        sorted_patterns = sorted(
            pattern_counts.items(), key=lambda x: x[1], reverse=True
        )

        # Return patterns that actually occurred
        failure_patterns = [pattern for pattern, count in sorted_patterns if count > 0]

        return failure_patterns, pattern_to_metric_details

    def _select_strategies_with_llm(
        self,
        performance_analysis: Dict[str, Any],
        failure_patterns: List[str],
        pattern_to_metric_details: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[str], str]:
        """Use LLM to intelligently select strategies based on the analysis."""

        # Prepare context for LLM
        metric_summary = []
        for metric, data in performance_analysis["metric_scores"].items():
            status = (
                "🟢 GOOD"
                if data["all_positive"]
                else ("🔴 POOR" if data["all_negative"] else "🟡 MIXED")
            )
            metric_summary.append(f"- {metric}: {data['average']:.2f} avg ({status})")

        failure_summary = []
        for pattern in failure_patterns[:5]:  # Top 5 patterns
            details = pattern_to_metric_details[pattern]
            failure_summary.append(
                f"- {pattern}: {details['count']} occurrences affecting {', '.join(details['metrics'][:3])}"
            )

        # Look for successful patterns to emphasize
        successful_metrics = [
            metric
            for metric, data in performance_analysis["metric_scores"].items()
            if data.get("all_positive", False)
        ]

        strategy_selection_prompt = f"""You are an expert at selecting prompting strategies to improve AI agent performance.



CURRENT PERFORMANCE:

{chr(10).join(metric_summary)}



MAIN FAILURE PATTERNS:

{chr(10).join(failure_summary) if failure_summary else "No significant failure patterns detected"}



SUCCESSFUL AREAS (to maintain/enhance):

{', '.join(successful_metrics) if successful_metrics else "No consistently successful metrics yet"}



AVAILABLE STRATEGIES:

{json.dumps({name: {"description": info["description"], "best_for": info.get("applicable_failures", []) + info.get("applicable_successes", [])}
            for name, info in self.prompting_strategies.items()}, indent=2)}



Based on this analysis:

1. Select 3-5 strategies that would be MOST EFFECTIVE for improving performance
2. Prioritize strategies that address the main failure patterns
3. Include strategies that can enhance already successful areas
4. Consider synergies between strategies



Return a JSON object with:
{
  "selected_strategies": ["strategy1", "strategy2", ...],
  "rationale": "Brief explanation of why these strategies were chosen and how they work together"
}"""

        try:
            print("\n🤖 Using LLM for flexible strategy selection...")
            response_text = self._generate_text(strategy_selection_prompt)
            # Find JSON content between braces
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                selection_data = json.loads(json_text)
            else:
                # Fallback if JSON extraction fails
                raise ValueError("Could not extract JSON from LLM response")

            selected = selection_data.get("selected_strategies", [])
            rationale = selection_data.get("rationale", "")

            # Validate selected strategies
            valid_strategies = [s for s in selected if s in self.prompting_strategies]

            if len(valid_strategies) < 3:
                # Fallback: select top strategies based on failure patterns
                print("⚠️ LLM selection insufficient, using fallback selection...")
                valid_strategies = self._fallback_strategy_selection(failure_patterns)
                rationale = "Fallback selection based on failure pattern frequency"

            return valid_strategies, rationale

        except Exception as e:
            print(f"⚠️ LLM strategy selection failed: {e}, using fallback")
            return self._fallback_strategy_selection(
                failure_patterns
            ), "Fallback selection due to LLM error"

    def _fallback_strategy_selection(self, failure_patterns: List[str]) -> List[str]:
        """Fallback strategy selection based on failure patterns."""
        # Map failure patterns to strategies
        pattern_to_strategies = {
            "spatial_confusion": [
                "direct_instruction",
                "few_shot",
                "chain_of_thought_enhanced",
            ],
            "rule_confusion": [
                "direct_instruction",
                "constraint_awareness",
                "few_shot",
            ],
            "goal_confusion": ["direct_instruction", "progressive_hinting"],
            "action_execution": ["direct_instruction", "checklist_validation"],
            "strategic_planning": ["chain_of_thought_enhanced", "few_shot"],
            "inaction": ["action_forcing", "progressive_hinting"],
            "constraint_violation": ["constraint_awareness", "negative_prompting"],
            "resource_management": ["negative_prompting", "constraint_awareness"],
        }

        # Count strategy recommendations
        strategy_scores = {}
        for pattern in failure_patterns[:3]:  # Top 3 patterns
            if pattern in pattern_to_strategies:
                for strategy in pattern_to_strategies[pattern]:
                    strategy_scores[strategy] = strategy_scores.get(strategy, 0) + 1

        # Sort by score and return top strategies
        sorted_strategies = sorted(
            strategy_scores.items(), key=lambda x: x[1], reverse=True
        )
        selected = [s[0] for s in sorted_strategies[:4]]  # Top 4 strategies

        # Always include these core strategies if not already selected
        core_strategies = ["direct_instruction", "few_shot"]
        for core in core_strategies:
            if core not in selected and len(selected) < 5:
                selected.append(core)

        return selected

    def _format_strategies_for_selection(self, selected_strategies: List[str]) -> str:
        """Format selected strategies for prompt inclusion."""
        formatted = []
        for strategy_name in selected_strategies:
            if strategy_name in self.prompting_strategies:
                strategy = self.prompting_strategies[strategy_name]
                formatted.append(f"""

**{strategy_name}**:
- Description: {strategy['description']}
- Implementation: {strategy['implementation']}
- Example: {strategy['example']}
""")
        return "\n".join(formatted)

    def _generate_trajectory_examples(
        self, performance_analysis: Dict[str, Any]
    ) -> str:
        """Generate rich examples focusing on SUCCESSFUL behaviors from trajectory data."""
        trajectory_insights = performance_analysis.get("trajectory_insights", {})

        examples = []

        # Add detailed observation format examples from real trajectories
        obs_examples = trajectory_insights.get("observation_format_examples", [])
        if obs_examples:
            examples.append("**REAL OBSERVATION FORMAT EXAMPLES:**")
            for i, example in enumerate(obs_examples[:3]):
                examples.append(f"\n**Example {i+1} (Task: {example['task']}):**")
                examples.append("```")
                examples.append(example["observation_sample"])
                examples.append("```")
                examples.append(
                    "Key: Shows active rules first, then object positions with relative coordinates."
                )

        # PRIORITIZE successful trajectory examples
        successful_patterns = trajectory_insights.get("successful_patterns", [])
        if successful_patterns:
            examples.append("\n**SUCCESSFUL BEHAVIORS TO REPLICATE (PRIMARY FOCUS):**")
            for i, pattern in enumerate(
                successful_patterns[:3]
            ):  # Show more successful examples
                examples.append(f"\n**Success Pattern {i+1} - EXCELLENT PERFORMANCE:**")
                examples.append(f"- Task: {pattern['task']}")
                examples.append(
                    f"- Completed in only {pattern['total_steps']} steps (Efficiency: {pattern['efficiency']})"
                )
                examples.append(
                    f"- Successfully achieved: {', '.join(pattern['successful_metrics'])}"
                )
                examples.append("- **KEY SUCCESS FACTORS TO REPLICATE:**")
                examples.append(
                    "  * Clear goal identification and direct path planning"
                )
                examples.append(
                    "  * Efficient spatial reasoning without unnecessary moves"
                )
                examples.append("  * Strategic rule manipulation when needed")
                examples.append("  * Consistent action execution without hesitation")
                examples.append(
                    f"- **EMULATE THIS:** {pattern['efficiency']} efficiency through focused, decisive action"
                )

        # Add brief failure patterns section (secondary focus)
        failure_modes = trajectory_insights.get("common_failure_modes", [])
        if failure_modes:
            examples.append("\n**CHALLENGES TO OVERCOME (SECONDARY FOCUS):**")
            for i, failure in enumerate(
                failure_modes[:2]
            ):  # Show fewer failure examples
                examples.append(f"\n**Challenge {i+1}:**")
                examples.append(f"- Task: {failure['task']}")
                examples.append(f"- Issue: {failure['failure_type']}")
                examples.append(
                    "- **Solution:** Apply successful patterns above to overcome this challenge"
                )

                # Add specific metric failures
                if failure.get("failed_metrics"):
                    examples.append("- **Failed metrics:**")
                    for metric in failure["failed_metrics"]:
                        examples.append(
                            f"  * {metric['metric']}: {metric['score']} - {metric['reasoning'][:100]}..."
                        )

        # Add action failure analysis
        action_failures = trajectory_insights.get("action_failure_patterns", [])
        if action_failures:
            examples.append("\n**ACTION EXECUTION PATTERNS:**")
            examples.append(
                f"- Total action failures detected: {trajectory_insights.get('reasoning_quality_stats', {}).get('total_action_failures', 0)}"
            )
            examples.append(
                "- **Solution:** Ensure clear, decisive action selection with proper format"
            )
            if action_failures:
                sample = action_failures[0]
                examples.append(
                    f"- Example failure: Task '{sample['task']}' at step {sample['step_number']}"
                )

        return "\n".join(examples)

    def _generate_failure_pattern_context(
        self,
        failure_patterns: List[str],
        pattern_to_metric_details: Dict[str, Dict[str, Any]],
    ) -> str:
        """Generate context about failure patterns for the prompt."""
        if not failure_patterns:
            return "No significant failure patterns detected. Focus on maintaining and enhancing current successful behaviors."

        context_lines = []
        for pattern in failure_patterns[:5]:  # Top 5 patterns
            details = pattern_to_metric_details.get(pattern, {})
            if details["count"] > 0:
                context_lines.append(
                    f"\n**{pattern.replace('_', ' ').title()}** ({details['count']} occurrences):"
                )
                context_lines.append(
                    f"- Affects metrics: {', '.join(details['metrics'][:3])}"
                )

                # Add examples
                if details["examples"]:
                    context_lines.append("- Examples:")
                    for ex in details["examples"][:2]:
                        context_lines.append(f"  * {ex['metric']}: {ex['reasoning']}")

                # Add targeted solution hint
                if pattern == "spatial_confusion":
                    context_lines.append(
                        "- **Solution focus:** Enhance spatial reasoning with clear relative position tracking"
                    )
                elif pattern == "rule_confusion":
                    context_lines.append(
                        "- **Solution focus:** Clarify rule explanations and provide concrete examples"
                    )
                elif pattern == "action_execution":
                    context_lines.append(
                        "- **Solution focus:** Ensure clear action format and decisive selection"
                    )
                elif pattern == "strategic_planning":
                    context_lines.append(
                        "- **Solution focus:** Implement structured planning with clear sub-goals"
                    )

                context_lines.append("")

        return "\n".join(context_lines)

    def _generate_agent_improvement(
        self,
        current_agent_code: str,
        performance_analysis: Dict[str, Any],
        failure_patterns: List[str],
        pattern_to_metric_details: Dict[str, Dict[str, Any]],
        selected_strategies: List[str],
        trajectory_examples: str,
    ) -> str:
        """Generate improved agent using ALL raw data directly with focus on metric optimization."""

        agent_number = self.current_turn + 1

        # Prepare raw metrics data
        metrics_data = json.dumps(self.metrics, indent=2)

        # Prepare raw evaluation results (limit to reasonable size)
        eval_results_sample = (
            self.eval_results[:20] if len(self.eval_results) > 20 else self.eval_results
        )
        evaluations_data = json.dumps(eval_results_sample, indent=2)

        # Prepare trajectory data with full details
        trajectory_data = []
        for result in self.eval_results[:18]:  # Limit to 10 for space
            if "trajectory_data" in result:
                traj = result["trajectory_data"]
                trajectory_data.append(
                    {
                        "instance_id": traj["instance_id"],
                        "task": traj["task"],
                        "total_steps": len(traj.get("steps", [])),
                        "first_30_steps": traj.get("steps", [])[
                            :30
                        ],  # Include first 30 steps
                        "evaluation_scores": {
                            k: v
                            for k, v in result.items()
                            if k.endswith("_score") or k in self.metrics
                        },
                    }
                )
        trajectory_data_json = json.dumps(trajectory_data, indent=2)

        # Load game rules/context from config-driven file path.
        rule_input_section = self._load_rule_input_section()

        system_prompt = f"""You are an expert prompt engineer creating a strategically improved {self.agent_prefix}{agent_number}Agent that OPTIMIZES FOR METRIC PERFORMANCE.



CRITICAL OBJECTIVE: Create an agent that maximizes positive scores across ALL metrics below.



=== RAW METRIC DEFINITIONS (IMPORTANT: YOUR FINAL GOAL IS TO OPTIMIZE FOR THESE) ===

{metrics_data}



=== RAW EVALUATION RESULTS (LEARN FROM THESE SCORES) ===

{evaluations_data}



=== RAW TRAJECTORY DATA (EXTRACT PATTERNS AND UNDERSTAND GAME MECHANICS FROM THESE) ===

{trajectory_data_json}



CURRENT AGENT CODE (use as foundation):

```python

{current_agent_code}

```



CONTEXT-ONLY GAME INFORMATION (DO NOT COPY INTO AGENT - FOR YOUR UNDERSTANDING ONLY):

{rule_input_section}



CRITICAL INSTRUCTIONS FOR METRIC OPTIMIZATION:
1. Analyze the METRIC DEFINITIONS carefully - understand what behaviors lead to positive vs negative scores
2. Study the EVALUATION RESULTS - identify which instances scored well/poorly on each metric
3. Extract patterns from TRAJECTORY DATA - find common elements in high-scoring vs low-scoring trajectories
4. Design prompts that DIRECTLY ADDRESS each metric's requirements
5. Include specific examples that demonstrate behaviors leading to POSITIVE metric scores



CRITICAL REQUIREMENTS:
1. The class MUST be named "{self.agent_prefix}{agent_number}Agent" (increment from current)
2. Follow the EXACT same class structure (imports, methods, extraction logic)
3. STRATEGICALLY ENHANCE the cot_instructions string to MAXIMIZE METRIC SCORES
4. For EACH metric, include specific guidance on how to achieve positive scores
5. Use actual trajectory examples that scored well on specific metrics
6. Create a prompt that systematically addresses ALL metrics



PERFORMANCE ANALYSIS (PROCESSED):

{json.dumps(performance_analysis['metric_scores'], indent=2)}



SELECTED STRATEGIES TO IMPLEMENT:

{self._format_strategies_for_selection(selected_strategies)}



ADDITIONAL TRAJECTORY EXAMPLES (PROCESSED):

{trajectory_examples}



ADAPTIVE PROMPT STRUCTURE:
Create a FLEXIBLE prompt structure that best addresses metric optimization. Consider:
- Metric-focused sections that directly target each metric's requirements
- Strategy-based organization leveraging the selected strategies
- Example-rich sections using successful trajectory patterns
- Clear guidance for achieving positive scores on each metric



IMPORTANT:
- Study the metric definitions to understand EXACTLY what behaviors score positively
- Use trajectory data to find CONCRETE EXAMPLES of high-scoring behaviors
- Create prompts that DIRECTLY OPTIMIZE for these positive behaviors
- Ensure each metric is explicitly addressed in the prompt



Generate ONLY the complete Python code for {self.agent_prefix}{agent_number}Agent class. Start with imports and end with the complete class implementation.
"""

        print("\n🤖 Calling LLM with DIRECT DATA for metric optimization...")
        print(f"📊 Passing {len(self.metrics)} raw metric definitions")
        print(f"📈 Passing {len(eval_results_sample)} evaluation results")
        print(f"🎯 Passing {len(trajectory_data)} trajectory examples")

        try:
            response_text = self._generate_text(system_prompt)
            cleaned_code = self._strip_markdown_code_fences(response_text)
            print(f"✅ Generated agent code: {len(cleaned_code)} characters")
            return cleaned_code.strip()

        except Exception as e:
            print(f"❌ Error generating agent improvement: {e}")
            return ""

    def _strip_markdown_code_fences(self, text: str) -> str:
        """Remove markdown code fences if present."""
        # Remove ```python and ``` markers
        text = re.sub(r"^```python\s*\n", "", text.strip())
        text = re.sub(r"\n```\s*$", "", text.strip())
        return text

    def improve_prompts(self) -> bool:
        """Main improvement workflow - AGENT ONLY with trajectory awareness."""
        print(f"\n{'='*60}")
        print(f"Starting Turn {self.current_turn} Improvement (Agent Only)")
        print(f"{'='*60}")

        # PHASE 1: ANALYSIS WITH TRAJECTORY DATA
        env_prompt, agent_prompt = self._load_prompts()

        print("\n" + "=" * 60)
        print("PHASE 1: TRAJECTORY-AWARE PERFORMANCE ANALYSIS")
        print("=" * 60)

        # Comprehensive analysis with trajectory insights
        performance = self._analyze_performance()
        print("\n📊 PERFORMANCE ANALYSIS RESULTS:")
        for metric, data in performance["metric_scores"].items():
            print(
                f"   {metric}: {data['average']:.2f} avg (negative: {data['all_negative']})"
            )

        # Analyze failure patterns with detailed output
        print("\n🔍 FAILURE PATTERN ANALYSIS:")
        failure_patterns, pattern_to_metric_details = self._analyze_failure_patterns(
            performance
        )

        # Select strategies with detailed output
        print("\n🎯 STRATEGY SELECTION:")
        selected_strategies, strategy_rationale = self._select_strategies_with_llm(
            performance, failure_patterns, pattern_to_metric_details
        )

        # Generate trajectory examples
        print("\n📈 TRAJECTORY EXAMPLES GENERATION:")
        trajectory_examples = self._generate_trajectory_examples(performance)
        print(
            f"Generated {len(trajectory_examples.split('Example'))-1} trajectory examples"
        )

        # PHASE 2: CONVERGENCE TO FINAL PROMPT
        print("\n" + "=" * 60)
        print("PHASE 2: PROMPT GENERATION WITH DIRECT DATA")
        print("=" * 60)

        # Generate ONLY agent improvements (no environment evolution)
        agent_number = self.current_turn + 1

        print(
            f"\n🧠 Generating enhanced {self.agent_prefix}{agent_number}Agent with direct data passing..."
        )
        print(f"📋 Using strategies: {', '.join(selected_strategies)}")
        print("🎯 Focus: METRIC OPTIMIZATION")

        improved_agent_code = self._generate_agent_improvement(
            agent_prompt,
            performance,
            failure_patterns,
            pattern_to_metric_details,
            selected_strategies,
            trajectory_examples,
        )

        # Save improvements (agent only)
        success = self._save_improved_prompts(improved_agent_code, performance)

        if success:
            print(
                f"\n✅ Turn {self.current_turn} trajectory-aware AGENT improvements saved!"
            )
            print(f"📁 Check: {self._get_turn_output_dir(self.current_turn)}")
            print(
                f"🎯 Created: {self.agent_prefix}{agent_number}Agent with direct data optimization"
            )
            return True
        else:
            print("❌ Failed to save improvements")
            return False

    def _save_improved_prompts(
        self, agent_code: str, performance: Dict[str, Any]
    ) -> bool:
        """Save improved prompts for the current turn - AGENT ONLY."""
        try:
            # Create turn directory
            turn_dir = self._get_turn_output_dir(self.current_turn)
            turn_dir.mkdir(parents=True, exist_ok=True)

            agent_number = self.current_turn + 1
            agent_filename = self._get_agent_filename(agent_number)

            # Save ONLY improved agent (no environment changes)
            with open(turn_dir / agent_filename, "w") as f:
                f.write(agent_code)

            # Save metadata
            metadata = {
                "turn": self.current_turn,
                "agent_number": agent_number,
                "agent_class": f"{self.agent_prefix}{agent_number}Agent",
                "timestamp": datetime.now().isoformat(),
                "approach": "direct_data_metric_optimization",
                "performance_analysis": performance,
                "key_features": [
                    "Agent-only evolution",
                    "Direct data passing to LLM",
                    "Metric optimization focus",
                    "Raw metrics, evaluations, and trajectories provided",
                    "Strategy-focused improvement",
                    "8 generalizable strategies",
                ],
            }

            with open(turn_dir / "turn_metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # Create evaluation-ready directory structure
            eval_dir = turn_dir / "for_evaluation"
            eval_dir.mkdir(exist_ok=True)

            eval_agent_dir = eval_dir / "agent_code"
            eval_agent_dir.mkdir(exist_ok=True)

            # Copy agent file for evaluation
            shutil.copy(turn_dir / agent_filename, eval_agent_dir / agent_filename)

            return True

        except Exception as e:
            print(f"❌ Error saving improvements: {e}")
            return False

    def run_full_improvement_cycle(self):
        """Run complete trajectory-aware improvement cycle - AGENT ONLY."""
        print("🚀 Starting Direct Data AutoLibra Improvement Cycle")
        print("🎯 Focus: Agent-only evolution with metric optimization")
        print("📝 Strategy: 8 generalizable techniques + direct data passing")
        print("🔧 NEW: LLM receives raw metrics, evaluations, and trajectories")
        print("=" * 60)

        success = self.improve_prompts()

        if success:
            agent_number = self.current_turn + 1
            print("\n✅ DIRECT DATA AGENT IMPROVEMENT COMPLETED")
            print("🎯 Next steps:")
            print(f"   1. Use {self.agent_prefix}{agent_number}Agent for evaluation")
            print("   2. Keep existing environment setup (no environment changes)")
            print("   3. Expect improved performance through metric optimization")
            print("\n📝 IMPORTANT - Key Innovation:")
            print("   - Agent now optimizes directly for metric scores")
            print("   - LLM analyzes raw data instead of pre-processed summaries")
            print("   - Better utilization of all three data sources")
            print("")
            self.show_rule_input_location()
            print(
                "\n🧠 Key improvements: Direct data + Metric optimization + Flexible template"
            )
        else:
            print("\n❌ IMPROVEMENT CYCLE FAILED")


def main():
    """Main entry point for direct data prompt improvement."""
    import argparse

    parser = argparse.ArgumentParser(description="Run direct-data prompt improver")
    parser.add_argument(
        "--config",
        type=str,
        default="prompt_optimization/config.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="prompt_optimization",
        help="Base directory for optimization artifacts (overridden by config)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="gemini",
        choices=["gemini", "azure"],
        help="LLM provider override",
    )
    args = parser.parse_args()

    improver = AutoLibraPromptImprover(
        base_dir=args.base_dir,
        config_path=args.config,
        provider=args.provider,
    )
    improver.run_full_improvement_cycle()


if __name__ == "__main__":
    main()
