import asyncio
from google import genai  # New import format
import json
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from autolibra_core import (
    run_llm_eval,
)
from autolibra_core.data import MetricTrainingInstance
from autolibra_core.configs import AutoLibraEvalSettings
from autolibra_core.data.primitives import Trait
from autolibra_core.evaluators.coverage_evaluator import run_coverage_eval
from autolibra_core.evaluators.llm_evaluator import _make_snake_case
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Global token tracking for LLM evaluation
TOKEN_USAGE = {
    "evaluation": defaultdict(int),
    "coverage_analysis": defaultdict(int),
    "total": defaultdict(int),
    "api_calls": [],  # Detailed log of each API call
    "retries": defaultdict(int),  # Track retries by operation
}


class GeminiParsedMessage:
    """Mimic OpenAI's parsed message structure"""
    def __init__(self, parsed_content):
        self.parsed = parsed_content


class GeminiChoice:
    """Mimic OpenAI's choice structure"""
    def __init__(self, parsed_content):
        self.message = GeminiParsedMessage(parsed_content)


class GeminiCompletion:
    """Mimic OpenAI's completion structure"""
    def __init__(self, parsed_content):
        self.choices = [GeminiChoice(parsed_content)]


class GeminiCompletions:
    """Minimal completions interface with parse method"""
    def __init__(self, gemini_client):
        self.gemini_client = gemini_client
        self.client = gemini_client.client  # New library client

    def _has_valid_text(self, response):
        """Safely check if response has valid text content"""
        try:
            return response.text and response.text.strip()
        except (ValueError, AttributeError):
            return False

    def _get_safe_text(self, response):
        """Safely get text from response, return empty string if not available"""
        try:
            return response.text if response.text else ""
        except (ValueError, AttributeError):
            return ""

    async def parse(self, model: str, messages: list, response_format):
        """Replicate OpenAI's structured parsing using prompt-based JSON generation"""
        
        # Extract system and user content from messages - these should match original exactly
        system_content = ""
        user_content = ""
        
        for message in messages:
            if message["role"] == "system":
                system_content = message["content"]
            elif message["role"] == "user":
                user_content = message["content"]
        
        # Build JSON format instruction based on response format
        class_name = getattr(response_format, '__name__', str(response_format))
        
        if "EvaluationResult" in class_name:
            # For main evaluations: be more permissive but still constrained
            fields = response_format.model_fields
            reasoning_aliases = []
            score_aliases = []
            
            # Get aliases instead of field names
            for field_name, field_info in fields.items():
                alias = field_info.alias if hasattr(field_info, 'alias') and field_info.alias else field_name
                if field_name.endswith('_reasoning'):
                    reasoning_aliases.append(alias)
                else:
                    score_aliases.append(alias)
            
            json_format = "{\n"
            for alias in reasoning_aliases:
                json_format += f'  "{alias}": "string explaining the reasoning",\n'
            for alias in score_aliases:
                json_format += f'  "{alias}": integer_value_-1_0_or_1,\n'
            json_format = json_format.rstrip(',\n') + "\n}"
            
            format_instruction = f"""

Please respond with valid JSON in this exact format:
{json_format}

Important:
- All reasoning fields should contain clear but concise explanations (aim for 50-100 words each)
- All score fields should be integers: -1 (agent did something wrong), 0 (not applicable), or 1 (agent did perfectly well)
- Ensure the JSON is valid and complete
- Use exactly these field names (case-sensitive)
"""
        elif "FeedbackGroundingOutput" in class_name:
            # Coverage analysis: Apply aggressive constraints here
            conciseness_constraint = """

🚨 CRITICAL CONSTRAINTS FOR COVERAGE ANALYSIS 🚨
- Keep feedback descriptions to MAXIMUM 15 words
- Keep behavior descriptions to MAXIMUM 15 words  
- NO detailed explanations, NO examples
- Be factual and direct only
"""
            
            # Insert constraint into user content for coverage analysis only
            user_content = conciseness_constraint + "\n\n" + user_content
            
            format_instruction = """

Please respond with valid JSON in this exact format:
{
  "bullet_points": [
    {
      "feedback": "string describing the feedback",
      "behavior": "string describing the behavior", 
      "is_positive": boolean
    }
  ]
}

- Use exactly "bullet_points" as the field name (not "feedback_breakdown")
- Keep all descriptions brief and factual
- is_positive should be true or false only
- Ensure the JSON is valid and complete
"""
        elif "BehaviorClusteringOutput" in class_name:
            # Coverage analysis: Apply aggressive constraints here
            conciseness_constraint = """

🚨 CRITICAL CONSTRAINTS FOR BEHAVIOR CLUSTERING 🚨
- Keep metric names to MAXIMUM 10 words
- Keep explanations to MAXIMUM 20 words
- Keep each behavior string to MAXIMUM 15 words
- NO verbose descriptions, NO detailed examples
- Be factual and direct only
"""
            
            # Insert constraint into user content for coverage analysis only
            user_content = conciseness_constraint + "\n\n" + user_content
            
            format_instruction = """

Please respond with valid JSON in this exact format:
{
  "metrics": [
    {
      "name": "string metric name",
      "explanation": "string explanation",
      "good_behaviors": ["list", "of", "strings"],
      "bad_behaviors": ["list", "of", "strings"]
    }
  ]
}

- Keep all descriptions brief and factual
- Ensure the JSON is valid and complete
"""
        elif "AspectTraitsMatch" in class_name:
            # Coverage analysis: Apply constraints here too
            conciseness_constraint = """

🚨 CRITICAL CONSTRAINTS FOR ASPECT-TRAIT MATCHING 🚨
- Use EXACTLY the field names from the schema (like "aspect_0", "trait_0") 
- For aspect fields: copy the exact literal string provided in the schema
- For trait fields: choose ONE of the specific trait options provided, or "None of the traits matches the aspect."
- DO NOT create your own field names
- DO NOT add extra fields
"""
            
            # Insert constraint into user content for coverage analysis only
            user_content = conciseness_constraint + "\n\n" + user_content
            
            format_instruction = """

This is an aspect-trait matching task. You must respond with valid JSON using the EXACT field names provided in the schema.

- Match each aspect to the most relevant trait
- Ensure the JSON is valid and complete

Example format (use actual field names from your schema):
{
  "aspect_0": "exact aspect string from schema",
  "trait_0": "exact trait option from schema or 'None of the traits matches the aspect.'"
}
"""
        else:
            # Fallback for other formats
            format_instruction = """
Please respond with valid JSON matching the expected format.
"""
        
        # Combine all content with format instruction - exactly like original
        if system_content:
            full_prompt = f"{system_content}\n\n{user_content}\n\n{format_instruction}"
        else:
            full_prompt = f"{user_content}\n\n{format_instruction}"
        
        # Use adaptive token limit based on response type
        if "EvaluationResult" in class_name:
            token_limit = 8192  # Give main evaluations more space for reasoning
        elif "FeedbackGroundingOutput" in class_name or "BehaviorClusteringOutput" in class_name or "AspectTraitsMatch" in class_name:
            token_limit = 2048  # Coverage analysis should be much more concise
        else:
            token_limit = 4096  # Default
            
        result = await self._try_with_token_limit(full_prompt, token_limit, response_format, user_content)
        
        if result is not None:
            return result
        
        print(f"    🚑 Token limit failed, using minimal fallback")
        return self._create_minimal_response(response_format)

    async def _try_with_token_limit(self, full_prompt, token_limit, response_format, user_content):
        """Try generation with a specific token limit with token logging"""
        
        print(f"    📝 Prompt length: {len(full_prompt)} characters")
        print(f"    🌐 Calling Gemini API ({self.gemini_client.model_name}, max_tokens: {token_limit})...")
        
        # Determine operation type from response format
        format_name = getattr(response_format, '__name__', str(response_format))
        operation_type = "evaluation"
        if "FeedbackGroundingOutput" in format_name or "AspectTraitsMatch" in format_name:
            operation_type = "coverage_analysis"
        
        # Track retry count
        retry_count = 0
        max_retries = 3
        
        while retry_count <= max_retries:
            try:
                # Call Gemini with new API format
                generation_config = {
                    "temperature": 0.1,
                    "max_output_tokens": token_limit,
                }
                
                response = self.client.models.generate_content(
                    model=self.gemini_client.model_name,
                    contents=full_prompt,
                    config=generation_config,
                )
                
                # Log token usage
                self._log_token_usage(response, operation_type, retry_count, success=True)
                
                # Get response text
                response_text = self._get_safe_text(response)
                print(f"    ✅ Got response text: {len(response_text):,} chars")
                
                # Handle empty response
                if not response_text:
                    print("    ⚠️  Empty response")
                    return None
                
                # Parse JSON and create Pydantic object
                response_text = response_text.strip()
                
                # Try to extract JSON from response if it's wrapped in other text
                if not response_text.startswith('{'):
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(0)
                
                json_data = json.loads(response_text)
                parsed_object = response_format.model_validate(json_data)
                print(f"    🎯 Successfully parsed response")
                return GeminiCompletion(parsed_object)
                
            except Exception as e:
                retry_count += 1
                print(f"    ❌ API call failed (attempt {retry_count}/{max_retries}): {e}")
                
                # Log failed attempt
                self._log_token_usage(None, operation_type, retry_count - 1, success=False, error=str(e))
                
                if retry_count > max_retries:
                    return None
                
                # Wait before retry
                import time
                time.sleep(2 ** retry_count)  # Exponential backoff
    
    def _log_token_usage(self, response, operation_type, retry_count, success=True, error=None):
        """Log token usage from response with retry tracking"""
        global TOKEN_USAGE
        
        # Extract token counts from response
        input_tokens = 0
        output_tokens = 0
        
        if response and hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            input_tokens = (
                (getattr(usage, 'prompt_token_count', 0) or 0) +
                (getattr(usage, 'cached_content_token_count', 0) or 0) +
                (getattr(usage, 'tool_use_prompt_token_count', 0) or 0)
            )
            output_tokens = (
                (getattr(usage, 'candidates_token_count', 0) or 0) +
                (getattr(usage, 'thoughts_token_count', 0) or 0)
            )
        
        # Update token counts
        TOKEN_USAGE[operation_type]["input_tokens"] += input_tokens
        TOKEN_USAGE[operation_type]["output_tokens"] += output_tokens
        TOKEN_USAGE[operation_type]["api_calls"] += 1
        
        TOKEN_USAGE["total"]["input_tokens"] += input_tokens
        TOKEN_USAGE["total"]["output_tokens"] += output_tokens
        TOKEN_USAGE["total"]["api_calls"] += 1
        
        if retry_count > 0:
            TOKEN_USAGE["retries"][operation_type] += retry_count
        
        # Log detailed API call
        api_call_log = {
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            "success": success,
            "retry_count": retry_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "error": error
        }
        
        TOKEN_USAGE["api_calls"].append(api_call_log)

    def _create_minimal_response(self, response_format):
        """Create a minimal valid response when Gemini fails"""
        class_name = getattr(response_format, '__name__', str(response_format))
        
        if "EvaluationResult" in class_name:
            # Create minimal evaluation result with all fields as "not applicable"
            fields = response_format.model_fields
            minimal_data = {}
            
            for field_name, field_info in fields.items():
                # Get the alias - this is what goes in the JSON
                alias = getattr(field_info, 'alias', field_name)
                
                if field_name.endswith('_reasoning'):
                    minimal_data[alias] = "Unable to evaluate due to response limit - marking as not applicable"
                else:
                    minimal_data[alias] = 0  # 0 = not applicable
            
            try:
                parsed_object = response_format.model_validate(minimal_data)
                print(f"    🚑 Created minimal response (fields marked as 'not applicable')")
                return GeminiCompletion(parsed_object)
            except Exception as e:
                print(f"    ❌ Error creating minimal response: {e}")
                print(f"    🔍 Minimal data: {minimal_data}")
                # Try using field names instead of aliases as fallback
                minimal_data_fallback = {}
                for field_name, field_info in fields.items():
                    if field_name.endswith('_reasoning'):
                        minimal_data_fallback[field_name] = "Unable to evaluate due to response limit - marking as not applicable"
                    else:
                        minimal_data_fallback[field_name] = 0
                parsed_object = response_format.model_validate(minimal_data_fallback)
                print(f"    🚑 Created minimal response using field names as fallback")
                return GeminiCompletion(parsed_object)
        
        elif "FeedbackGroundingOutput" in class_name:
            # Create minimal feedback grounding response
            minimal_data = {
                "bullet_points": [
                    {
                        "feedback": "Unable to ground feedback due to response limit",
                        "behavior": "No behavior identified",
                        "is_positive": False
                    }
                ]
            }
            parsed_object = response_format.model_validate(minimal_data)
            print(f"    🚑 Created minimal FeedbackGroundingOutput response")
            return GeminiCompletion(parsed_object)
        
        elif "BehaviorClusteringOutput" in class_name:
            # Create minimal behavior clustering response
            minimal_data = {
                "metrics": [
                    {
                        "name": "Unable to cluster behaviors",
                        "explanation": "Response limit exceeded during clustering",
                        "good_behaviors": ["No behaviors identified"],
                        "bad_behaviors": ["No behaviors identified"]
                    }
                ]
            }
            parsed_object = response_format.model_validate(minimal_data)
            print(f"    🚑 Created minimal BehaviorClusteringOutput response")
            return GeminiCompletion(parsed_object)
        
        elif "AspectTraitsMatch" in class_name:
            # Create minimal aspect-trait match response
            # This model has dynamic fields, so we need to inspect the model to get field names
            try:
                model_fields = response_format.model_fields
                minimal_data = {}
                
                for field_name in model_fields.keys():
                    if field_name.startswith('aspect_'):
                        # For aspect fields, use a generic fallback string
                        minimal_data[field_name] = "Unable to match aspect due to response limit"
                    elif field_name.startswith('trait_'):
                        # For trait fields, use the "none" option
                        minimal_data[field_name] = "None of the traits matches the aspect."
                
                parsed_object = response_format.model_validate(minimal_data)
                print(f"    🚑 Created minimal AspectTraitsMatch response with {len(minimal_data)} fields")
                return GeminiCompletion(parsed_object)
            except Exception as e:
                print(f"    ❌ Failed to create minimal AspectTraitsMatch response: {e}")
                # Create a very basic fallback
                minimal_data = {
                    "aspect_0": "Unable to match aspect due to response limit",
                    "trait_0": "None of the traits matches the aspect."
                }
                try:
                    parsed_object = response_format.model_validate(minimal_data)
                    return GeminiCompletion(parsed_object)
                except:
                    pass
        
        # Fallback for other types
        raise ValueError(f"Cannot create minimal response for unknown format: {class_name}")


class GeminiChat:
    """Minimal chat interface"""
    def __init__(self, gemini_client):
        self.completions = GeminiCompletions(gemini_client)


class GeminiBeta:
    """Minimal beta interface"""
    def __init__(self, gemini_client):
        self.chat = GeminiChat(gemini_client)


class GeminiClient:
    """Simple wrapper to make Gemini work with autolibra_core functions"""
    def __init__(self):
        # New library uses a client instance with API key
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.5-flash'
        
        # System instruction for context
        self.system_instruction = ("You are analyzing trajectory data from video games and simulations for academic research purposes. "
                                 "The content contains gaming terminology (like 'attack', 'kill', 'weapon', 'fight') that refers to "
                                 "game mechanics and virtual actions, not real-world violence or harm. "
                                 "Please interpret all content strictly in the context of game analysis, behavioral research, "
                                 "and trajectory evaluation for AI training purposes.")
        
        # Add beta attribute to mimic AsyncAzureOpenAI structure
        self.beta = GeminiBeta(self)


def save_token_usage_log(output_file: str, dataset_name: str, metric_path: str):
    """Save detailed token usage log to the same directory as results"""
    global TOKEN_USAGE
    
    # Get directory from output file
    output_dir = Path(output_file).parent
    
    # Create token log filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"gemini_token_usage_llm_eval_{timestamp}.json"
    log_path = output_dir / log_filename
    
    # Calculate summary statistics
    summary = {
        "dataset": dataset_name,
        "metric_path": metric_path,
        "output_file": output_file,
        "timestamp": timestamp,
        "total_api_calls": TOKEN_USAGE["total"]["api_calls"],
        "total_input_tokens": TOKEN_USAGE["total"]["input_tokens"],
        "total_output_tokens": TOKEN_USAGE["total"]["output_tokens"],
        "total_tokens": TOKEN_USAGE["total"]["input_tokens"] + TOKEN_USAGE["total"]["output_tokens"],
        "operations": {
            "evaluation": dict(TOKEN_USAGE["evaluation"]),
            "coverage_analysis": dict(TOKEN_USAGE["coverage_analysis"]),
        },
        "retries": dict(TOKEN_USAGE["retries"]),
        "detailed_calls": TOKEN_USAGE["api_calls"]
    }
    
    # Save to file
    with open(log_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n💾 Token usage log saved to: {log_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("🔢 GEMINI TOKEN USAGE SUMMARY (LLM Evaluation)")
    print("="*60)
    print(f"📊 Total API Calls: {summary['total_api_calls']}")
    print(f"📥 Total Input Tokens: {summary['total_input_tokens']:,}")
    print(f"📤 Total Output Tokens: {summary['total_output_tokens']:,}")
    print(f"💰 Total Tokens: {summary['total_tokens']:,}")
    print()
    
    if TOKEN_USAGE["evaluation"]["api_calls"] > 0:
        print("📝 Evaluation:")
        print(f"  • API Calls: {TOKEN_USAGE['evaluation']['api_calls']}")
        print(f"  • Input Tokens: {TOKEN_USAGE['evaluation']['input_tokens']:,}")
        print(f"  • Output Tokens: {TOKEN_USAGE['evaluation']['output_tokens']:,}")
    
    if TOKEN_USAGE["coverage_analysis"]["api_calls"] > 0:
        print("🌊 Coverage Analysis:")
        print(f"  • API Calls: {TOKEN_USAGE['coverage_analysis']['api_calls']}")
        print(f"  • Input Tokens: {TOKEN_USAGE['coverage_analysis']['input_tokens']:,}")
        print(f"  • Output Tokens: {TOKEN_USAGE['coverage_analysis']['output_tokens']:,}")
    
    if any(TOKEN_USAGE["retries"].values()):
        print("\n🔄 Retries:")
        for op, count in TOKEN_USAGE["retries"].items():
            if count > 0:
                print(f"  • {op}: {count} retries")
    
    print("="*60)
    
    return str(log_path)


async def main(filename: str, metric_path: str, output_file: str = "llm_eval_results_gemini.jsonl") -> None:
    print("🚀 Starting LLM Evaluation with Gemini...")
    print(f"📁 Output file: {output_file}")
    
    dataset = MultiAgentDataset(
        name="dataset",
        base_path=f".data/gemini_babaisai/{filename.split('/')[1]}",
    )

    annotation_system = AnnotationSystem(
        base_path=f".data/annotations/gemini_babaisai/{filename.split('/')[1]}",
        project_name="gemini_eval_project",
    )

    metric_set = MetricSet(
        name="",
        base_path=metric_path,
        induced_from=f"gemini_babaisai/{filename.split('/')[1]}",
    )

    settings = AutoLibraEvalSettings()

    # Use Gemini client instead of Azure OpenAI
    client = GeminiClient()

    print("📊 Loading training instances...")
    metric_training_instances: list[MetricTrainingInstance] = []

    for instances in dataset.list_instances():
        instance = dataset.get_instance_metadata(instances)
        for agent_id in instance.agents:
            trajectory_annotations = annotation_system.get_trajectory_annotations(
                instance_id=instances, agent_id=agent_id
            )
            for annotation in trajectory_annotations.annotations:
                metric_training_instances.append(
                    MetricTrainingInstance(
                        task=instance.metadata["task"]
                        if "task" in instance.metadata
                        else "Task is described in the trajectory observation",
                        agent_id=agent_id,
                        trajectory=dataset.get_trajectory(instances, agent_id),
                        feedback=str(annotation.content),
                    )
                )

    print(f"📋 Found {len(metric_training_instances)} training instances")
    print(f"🎯 Found {len(metric_set.metrics)} metrics to evaluate")
    print("🤖 Starting LLM evaluations...")
    print("")  # Add blank line for readability

    # Track evaluation progress
    total_instances = len(metric_training_instances)
    
    async def eval_with_progress_and_retry(instance, idx):
        print(f"  🔍 Evaluating instance {idx + 1}/{total_instances}...")
        
        # Retry logic for failed evaluations
        max_retries = 5
        
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"    🔄 Retry attempt {attempt}/{max_retries-1} for instance {idx + 1}")
            
            try:
                from autolibra_core.evaluators.llm_evaluator import eval_instance
                eval_result = await eval_instance(instance, list(metric_set.metrics.values()), client)
                
                # Check if evaluation was successful (has actual evaluation data)
                # A minimal fallback response would have all fields as 0 or "not applicable"
                is_minimal_response = True
                for metric in metric_set.metrics.values():
                    score_field = _make_snake_case(metric.name)
                    reasoning_field = f"{score_field}_reasoning"
                    
                    # Check if we got a real evaluation (non-zero score or non-fallback reasoning)
                    score = getattr(eval_result, score_field, 0)
                    reasoning = getattr(eval_result, reasoning_field, "")
                    
                    if score != 0 or ("not applicable" not in reasoning.lower() and "unable to evaluate" not in reasoning.lower()):
                        is_minimal_response = False
                        break
                
                if is_minimal_response and attempt < max_retries - 1:
                    print(f"    ⚠️  Got minimal fallback response on attempt {attempt + 1}, retrying...")
                    print(f"    ⏳ Waiting 2 seconds before retry...")
                    import time
                    time.sleep(2)
                    continue
                else:
                    if is_minimal_response:
                        print(f"    🚑 Instance {idx + 1}: Using minimal fallback after {max_retries} attempts")
                    else:
                        print(f"    ✅ Instance {idx + 1}: Successfully evaluated" + (f" (attempt {attempt + 1})" if attempt > 0 else ""))
                    
                    return eval_result
                    
            except Exception as e:
                print(f"    ❌ Evaluation failed on attempt {attempt + 1} for instance {idx + 1}: {e}")
                print(f"    🔍 Error type: {type(e).__name__}")
                
                if attempt < max_retries - 1:
                    print(f"    ⏳ Waiting 2 seconds before retry...")
                    import time
                    time.sleep(2)
                    continue
                else:
                    print(f"    ❌ All retry attempts failed for instance {idx + 1}")
                    # Create a minimal response as final fallback
                    try:
                        from autolibra_core.evaluators.llm_evaluator import _create_eval_result_class
                        EvaluationResult = _create_eval_result_class(list(metric_set.metrics.values()))
                        
                        minimal_data = {}
                        for metric in metric_set.metrics.values():
                            score_field = _make_snake_case(metric.name)
                            reasoning_field = f"{score_field}_reasoning"
                            minimal_data[score_field] = 0  # 0 = not applicable
                            minimal_data[reasoning_field] = f"Unable to evaluate due to persistent errors - marking as not applicable"
                        
                        return EvaluationResult.model_validate(minimal_data)
                    except Exception as fallback_error:
                        print(f"    💔 Even minimal fallback failed: {fallback_error}")
                        raise e  # Re-raise original error
        
        # Should never reach here, but just in case
        print(f"    🚑 Unexpected end of retry loop for instance {idx + 1}")
        raise Exception(f"Retry logic failed for instance {idx + 1}")
    
    # Run full evaluation on all instances with retry logic
    eval_results = await asyncio.gather(
        *[eval_with_progress_and_retry(instance, idx) for idx, instance in enumerate(metric_training_instances)]
    )

    print("")  # Add blank line after evaluations
    print("✅ LLM evaluations completed!")
    print("📊 Processing evaluation scores...")

    eval_scoring = [
        [
            int(getattr(eval_result, _make_snake_case(metric.name), 0))
            for metric in metric_set.metrics.values()
        ]
        for eval_result in eval_results
    ]

    print("💾 Saving evaluation results...")
    with open(output_file, "w") as f:
        for eval_result in eval_results:
            f.write(eval_result.model_dump_json())
            f.write("\n")

    print("\n🎉 LLM Evaluation Complete!")
    print(f"📁 Results saved to: {output_file}")
    print(f"📊 Evaluated {len(eval_results)} instances across {len(metric_set.metrics)} metrics")
    
    # Save token usage log
    dataset_name = filename  # Using filename as dataset name
    save_token_usage_log(output_file, dataset_name, metric_path)
    
    print(f"\n🔄 To run coverage analysis, use: uv run python -m src.training.coverage_analysis_gemini --filename {{your_filename}} --results-file {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM Evaluation with Gemini - Phase 1")
    parser.add_argument(
        "--filename",
        type=str,
        required=True,
        help="The name of the folder containing the data for the given run, including the date subfolder",
    )
    parser.add_argument(
        "--metric-path",
        type=str,
        default=None,
        help="Path to the metrics directory (if not specified, will be derived from filename)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="llm_eval_results_gemini.jsonl",
        help="Path to save the evaluation results (default: llm_eval_results_gemini.jsonl)",
    )

    args = parser.parse_args()
    filename = args.filename
    filename_no_date = filename.split("/")[0]

    # Use provided metric path or derive from filename
    if args.metric_path:
        metric_path = args.metric_path
    else:
        metric_path = f".data/metrics/{filename}"

    asyncio.run(
        main(
            filename=filename,
            metric_path=metric_path,
            output_file=args.output_file,
        ),
    ) 