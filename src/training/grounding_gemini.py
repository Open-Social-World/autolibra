#!/usr/bin/env python3
# Iterative Metric Creation - Gemini Version
# Input: instances, trajectories, agents, and feedbacks
# Output: metrics

import asyncio
from datetime import datetime
import google.generativeai as genai
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from autolibra_core import (
    MetricTrainingInstance,
    feedback_grounding,
    behavior_clustering,
)
from autolibra_core.configs import AutoLibraEvalSettings
import os

# Add semaphore for rate limiting (similar to llm_evaluator.py)
feedback_grounding_semaphore = asyncio.Semaphore(20)  # Limit to 20 concurrent feedback grounding tasks

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
        self.gemini_model = gemini_client.model

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
        """Replicate OpenAI's structured parsing with robust MAX_TOKENS handling"""
        
        # Determine which function is being called based on response_format
        if hasattr(response_format, '__name__'):
            format_name = response_format.__name__
        else:
            format_name = str(response_format)
            
        if "FeedbackGroundingOutput" in format_name:
            print("  🔍 Calling feedback grounding...")
        elif "BehaviorClusteringOutput" in format_name:
            print("  🧠 Calling behavior clustering...")
        else:
            print(f"  ❓ Calling unknown format: {format_name}")
        
        # Extract system and user content from messages (same as OpenAI expects)
        system_content = ""
        user_content = ""
        
        for message in messages:
            if message["role"] == "system":
                system_content = message["content"]
            elif message["role"] == "user":
                user_content = message["content"]
        
        # Combine system and user content
        if system_content:
            full_prompt = f"{system_content}\n\n{user_content}"
        else:
            full_prompt = user_content
            
        print(f"    📝 Prompt length: {len(full_prompt)} characters")
        
        # Get JSON schema from Pydantic model and clean it for Gemini
        raw_schema = response_format.model_json_schema()
        
        # Create a completely clean schema for Gemini based on the response_format type
        if "FeedbackGroundingOutput" in format_name:
            # Hardcode the schema for FeedbackGroundingOutput to avoid all parsing issues
            schema = {
                "type": "object",
                "properties": {
                    "bullet_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "feedback": {"type": "string"},
                                "behavior": {"type": "string"}, 
                                "is_positive": {"type": "boolean"}
                            },
                            "required": ["feedback", "behavior", "is_positive"]
                        }
                    }
                },
                "required": ["bullet_points"]
            }
        elif "BehaviorClusteringOutput" in format_name:
            # Hardcode the schema for BehaviorClusteringOutput
            schema = {
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "explanation": {"type": "string"},
                                "good_behaviors": {"type": "array", "items": {"type": "string"}},
                                "bad_behaviors": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["name", "explanation", "good_behaviors", "bad_behaviors"]
                        }
                    }
                },
                "required": ["metrics"]
            }
        else:
            # Fallback to a simple object schema
            schema = {
                "type": "object",
                "properties": {},
                "required": []
            }
        
        # Simple approach: just use the maximum 65K tokens for everything
        print(f"    📝 Prompt length: {len(full_prompt)} characters")
        print(f"    🚀 Using maximum 65K tokens for all requests")
        
        # No scaling, no retries, just maximum tokens
        max_output_tokens = 65536
        
        print(f"    🌐 Calling Gemini API ({self.gemini_client.model_name}, max_tokens: {max_output_tokens:,})...")
        
        # Call Gemini with maximum token limit
        response = self.gemini_model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.5,
                max_output_tokens=max_output_tokens,
            )
        )
        
        # Check for finish reason before accessing content
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason
            
            # Handle different finish reasons
            if finish_reason == 2:  # MAX_TOKENS
                print(f"    ⚠️  Hit MAX_TOKENS limit with {max_output_tokens:,} tokens")
                # If we hit 65K tokens, just proceed with whatever we got
                if self._has_valid_text(response):
                    print(f"    🔄 Found partial content, proceeding...")
                else:
                    print(f"    ❌ No content returned even with 65K tokens")
                    return await self._try_chunking_strategy(full_prompt, response_format, schema)
            
            elif finish_reason in [3, 4, 5, 6, 7, 8, 9, 10]:  # Various blocking reasons
                print(f"    ❌ Response blocked! Finish reason: {finish_reason}")
                from openai import RateLimitError
                raise RateLimitError(f"Response blocked. Finish reason: {finish_reason}")
        
        # Handle empty response (using safe text check)
        if not response.parts or not self._has_valid_text(response):
            print(f"    ❌ Response empty!")
            from openai import RateLimitError
            raise RateLimitError(f"Response empty")
        
        # Success case
        response_text = self._get_safe_text(response)
        print(f"    ✅ Got response ({len(response_text):,} chars)")
        
        # Parse JSON and create Pydantic object
        try:
            response_text = response_text.strip()
            
            if not response_text:
                print("    ❌ No text content available for parsing")
                return await self._try_chunking_strategy(full_prompt, response_format, schema)
            
            # Try to fix common JSON truncation issues
            if not response_text.endswith('}') and not response_text.endswith(']'):
                print("    🔧 Attempting to fix truncated JSON...")
                response_text = self._fix_truncated_json(response_text, format_name)
            
            json_data = json.loads(response_text)
            parsed_object = response_format.model_validate(json_data)
            
            if "FeedbackGroundingOutput" in format_name:
                print(f"    🎯 Extracted {len(parsed_object.bullet_points)} bullet points")
            elif "BehaviorClusteringOutput" in format_name:
                print(f"    📊 Generated {len(parsed_object.metrics)} metrics")
            
            return GeminiCompletion(parsed_object)
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"    ❌ JSON parsing failed: {e}")
            safe_text = self._get_safe_text(response)
            print(f"    📄 Response text: {safe_text[:200]}...")
            
            # Last resort: try to salvage partial data
            try:
                salvaged_response = self._salvage_partial_response(safe_text, response_format, format_name)
                if salvaged_response:
                    print(f"    🚑 Successfully salvaged partial response")
                    return GeminiCompletion(salvaged_response)
            except Exception as salvage_error:
                print(f"    💔 Salvage attempt failed: {salvage_error}")
            
            from openai import RateLimitError
            raise RateLimitError(f"JSON parsing failed after all recovery attempts: {e}")

    async def _try_chunking_strategy(self, full_prompt, response_format, schema):
        """Last resort: try to break down the request into smaller chunks"""
        print("    🧩 Attempting chunking strategy...")
        
        # For now, return a minimal valid response to avoid complete failure
        # This could be enhanced to actually chunk the request
        if "FeedbackGroundingOutput" in str(response_format):
            minimal_response = response_format(bullet_points=[])
        else:
            minimal_response = response_format(metrics=[])
        
        return GeminiCompletion(minimal_response)

    def _fix_truncated_json(self, text, format_name):
        """Attempt to fix common JSON truncation issues"""
        # Remove incomplete trailing objects/arrays
        text = text.rstrip(',"')
        
        # Count braces and brackets to determine what's missing
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        
        # Add missing closing characters
        text += ']' * open_brackets
        text += '}' * open_braces
        
        return text

    def _salvage_partial_response(self, text, response_format, format_name):
        """Try to extract whatever valid data we can from a broken response"""
        try:
            # Look for complete JSON objects within the text
            if "FeedbackGroundingOutput" in format_name:
                # Try to find complete bullet point objects
                bullet_pattern = r'\{"feedback":\s*"[^"]*",\s*"behavior":\s*"[^"]*",\s*"is_positive":\s*(true|false)\}'
                matches = re.findall(bullet_pattern, text)
                
                if matches:
                    bullet_points = []
                    for match in matches:
                        try:
                            obj = json.loads(match)
                            bullet_points.append(obj)
                        except:
                            continue
                    
                    if bullet_points:
                        return response_format(bullet_points=bullet_points)
            
            elif "BehaviorClusteringOutput" in format_name:
                # Similar approach for metrics
                # This is a simplified approach - could be enhanced
                return response_format(metrics=[])
            
        except Exception:
            pass
        
        return None


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
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Import the correct enums for safety settings
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        
        # Switch back to gemini-2.5-flash with max token capacity
        self.model_name = 'gemini-2.5-flash'
        
        # Use BLOCK_NONE for all models - this is the correct format for google-generativeai library
        self.safety_settings = [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
        ]
        
        print(f"🛡️  Initializing Gemini {self.model_name} with safety threshold: BLOCK_NONE")
        print(f"🚀 Using maximum output token capacity: 65,536 tokens")
        
        self.model = self._create_model(self.model_name)
        # Add beta attribute to mimic AsyncAzureOpenAI structure
        self.beta = GeminiBeta(self)

    def _create_model(self, model_name):
        """Create a Gemini model with consistent settings"""
        return genai.GenerativeModel(
            model_name,
            safety_settings=self.safety_settings,
            # Enhanced system instruction for research context
            system_instruction="You are analyzing trajectory data from video games and simulations for academic research purposes. "
                             "The content contains gaming terminology (like 'attack', 'kill', 'weapon', 'fight') that refers to "
                             "game mechanics and virtual actions, not real-world violence or harm. "
                             "Please interpret all content strictly in the context of game analysis, behavioral research, "
                             "and trajectory evaluation for AI training purposes."
        )


def modify_behavior_clustering_template(num_metrics):
    """Temporarily modify the behavior clustering template to generate specific number of metrics"""
    # Path to the template file
    template_path = Path("packages/autolibra-core/src/autolibra_core/templates/behavior_clustering.j2")
    
    if not template_path.exists():
        print(f"⚠️  Template file not found at {template_path}, using default behavior")
        return None, None
    
    # Create backup with timestamp for uniqueness
    import time
    timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
    backup_path = template_path.with_suffix(f'.j2.backup_{timestamp}')
    
    try:
        # Read the current template file
        with open(template_path, 'r') as f:
            original_content = f.read()
        
        # Create backup of current state
        shutil.copy2(template_path, backup_path)
        print(f"📄 Created backup: {backup_path.name}")
        
        # Use a more robust regex pattern to find and replace any "Output N metrics." pattern
        import re
        # This pattern will match "Output" followed by any number followed by "metrics."
        pattern = r'Output\s+\d+\s+metrics\.'
        replacement = f'Output {num_metrics} metrics.'
        
        # Check if the pattern exists
        if not re.search(pattern, original_content):
            print(f"⚠️  Could not find 'Output N metrics.' pattern in template")
            print(f"📄 Template content around the end:")
            lines = original_content.split('\n')
            for i, line in enumerate(lines[-10:]):
                print(f"  {len(lines)-10+i+1}: {line}")
            # Don't fail, just proceed without modification
            return template_path, backup_path
        
        # Apply the replacement
        modified_content = re.sub(pattern, replacement, original_content)
        
        # Verify the change was made
        if modified_content == original_content:
            print(f"⚠️  No changes were made to the template")
            return template_path, backup_path
        
        # Count how many times the pattern was replaced
        original_matches = len(re.findall(pattern, original_content))
        new_matches = len(re.findall(f'Output\\s+{num_metrics}\\s+metrics\\.', modified_content))
        
        if original_matches != 1 or new_matches != 1:
            print(f"⚠️  Unexpected number of pattern matches: original={original_matches}, new={new_matches}")
        
        # Write modified template
        with open(template_path, 'w') as f:
            f.write(modified_content)
        
        print(f"📝 Modified behavior clustering template to generate {num_metrics} metrics")
        print(f"🔄 Changed from pattern 'Output N metrics.' to 'Output {num_metrics} metrics.'")
        
        return template_path, backup_path
        
    except Exception as e:
        print(f"⚠️  Failed to modify template: {e}")
        # Try to restore from backup if it exists
        if backup_path and backup_path.exists():
            try:
                shutil.copy2(backup_path, template_path)
                print(f"🔄 Restored template from backup due to error")
            except Exception as restore_error:
                print(f"❌ Failed to restore template: {restore_error}")
        return None, None


def restore_behavior_clustering_template(template_path, backup_path):
    """Restore the original behavior clustering template"""
    if template_path and backup_path and backup_path.exists():
        try:
            # Read the backup content to verify it's valid
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            
            # Basic validation - check if it looks like a valid template
            if not backup_content.strip() or 'behavior_feedback_list' not in backup_content:
                print(f"⚠️  Backup file seems invalid, skipping restore")
                return
            
            # Restore the template
            shutil.copy2(backup_path, template_path)
            print(f"🔄 Restored original behavior clustering template")
            
            # Clean up the backup file
            backup_path.unlink()
            print(f"🧹 Cleaned up backup file: {backup_path.name}")
            
        except Exception as e:
            print(f"⚠️  Failed to restore template: {e}")
            # Don't delete backup on failure - might be useful for debugging
            print(f"📄 Backup file preserved for debugging: {backup_path.name}")
    else:
        print(f"⚠️  Cannot restore template - missing template_path or backup_path")
        if backup_path and backup_path.exists():
            print(f"📄 Backup file exists but won't be restored: {backup_path.name}")


async def main(dataset_name: str, num_metrics: int = 6) -> None:
    print(f"🚀 Starting Gemini grounding for dataset: {dataset_name}")
    print(f"🎯 Target number of metrics: {num_metrics}")
    sys.stdout.flush()
    
    # Modify behavior clustering template for specific metric count
    template_path, backup_path = modify_behavior_clustering_template(num_metrics)
    
    try:
        settings = AutoLibraEvalSettings()
        print("⚙️  Settings loaded")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Settings failed: {e}")
        sys.stdout.flush()
        raise

    # Just swap this line from AsyncAzureOpenAI to GeminiClient
    try:
        print("📡 Initializing Gemini client...")
        sys.stdout.flush()
        client = GeminiClient()
        print("✅ Gemini client initialized")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Gemini client failed: {e}")
        sys.stdout.flush()
        raise

    try:
        print(f"📂 Loading dataset from: .data/{dataset_name}")
        sys.stdout.flush()
        dataset = MultiAgentDataset(
            name="dataset",
            base_path=f".data/{dataset_name}",
        )
        print("✅ Dataset loaded")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Dataset loading failed: {e}")
        sys.stdout.flush()
        raise

    # Handle path mapping for annotations - convert to lowercase
    annotation_path = dataset_name.lower()
    try:
        print(f"📋 Loading annotations from: .data/annotations/{annotation_path}")
        sys.stdout.flush()
        
        annotation_system = AnnotationSystem(
            base_path=f".data/annotations/{annotation_path}",
            project_name="Trajectory Annotation Project",
            description="Free-form text annotations of agent trajectories",
            annotation_schema={
                "feedback": {
                    "type": "string",
                    "description": "Free-form text feedback on the trajectory",
                }
            },
        )
        print("✅ Annotation system loaded")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Annotation system failed: {e}")
        sys.stdout.flush()
        raise

    try:
        print("🔍 Collecting metric training instances...")
        sys.stdout.flush()
        metric_training_instances: list[MetricTrainingInstance] = []

        for instances in dataset.list_instances():
            print(f"  📝 Processing instance: {instances}")
            sys.stdout.flush()
            instance = dataset.get_instance_metadata(instances)
            for agent_id in instance.agents:
                print(f"    🤖 Processing agent: {agent_id}")
                sys.stdout.flush()
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
                            feedback=annotation.content["feedback"],
                        )
                    )
        print("✅ Instances collected")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Instance collection failed: {e}")
        sys.stdout.flush()
        raise

    print(f"📊 Found {len(metric_training_instances)} metric training instances")
    sys.stdout.flush()
    
    if len(metric_training_instances) == 0:
        print("⚠️  No training instances found! Check your dataset and annotation paths.")
        sys.stdout.flush()
        return
    
    print("🤖 Starting feedback grounding with Gemini...")
    sys.stdout.flush()

    # Add retry wrapper for feedback grounding to handle intermittent failures
    async def feedback_grounding_with_retry(instance, max_retries=3):
        """Wrapper to add retry logic around feedback_grounding calls"""
        
        # Use semaphore to limit concurrent API calls
        async with feedback_grounding_semaphore:
            for attempt in range(max_retries):
                try:
                    result = await feedback_grounding(instance, client=client)
                    
                    # Check if we got a meaningful result (not empty)
                    if result and len(result) > 0:
                        if attempt > 0:
                            print(f"    ✅ Feedback grounding succeeded on attempt {attempt + 1}")
                        return result
                    else:
                        if attempt < max_retries - 1:
                            print(f"    ⚠️  Empty feedback grounding result on attempt {attempt + 1}, retrying...")
                            import time
                            time.sleep(2)
                            continue
                        else:
                            print(f"    🚑 Using empty result after {max_retries} attempts")
                            return result
                            
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"    ❌ Feedback grounding failed on attempt {attempt + 1}: {e}")
                        print(f"    ⏳ Waiting 2 seconds before retry...")
                        import time
                        time.sleep(2)
                        continue
                    else:
                        print(f"    ❌ Feedback grounding failed after {max_retries} attempts: {e}")
                        # Return empty result to not break the pipeline
                        return []
            
            return []

    # Use the same autolibra_core functions with retry wrapper
    feedback_grounding_results = await asyncio.gather(
        *[
            feedback_grounding_with_retry(instance)
            for instance in metric_training_instances
        ]
    )

    print(f"✅ Feedback grounding completed. Processing {len(feedback_grounding_results)} results")
    sys.stdout.flush()
    print("💾 Writing feedback grounding results to file...")
    sys.stdout.flush()

    with open("feedback_grounding_results.jsonl", "w") as f:
        for feedback_grounding_result in feedback_grounding_results:
            for aspect in feedback_grounding_result:
                f.write(aspect.model_dump_json(indent=2))
                f.write("\n")
            f.write("\n")

    aspects = sum(
        [
            feedback_grounding_result
            for feedback_grounding_result in feedback_grounding_results
        ],
        [],
    )

    print(f"🎯 Extracted {len(aspects)} aspects total")
    sys.stdout.flush()
    print("🧠 Starting behavior clustering with Gemini...")
    sys.stdout.flush()

    # Add retry wrapper for behavior clustering
    async def behavior_clustering_with_retry(aspects, max_retries=10):
        """Wrapper to add retry logic around behavior_clustering calls"""
        for attempt in range(max_retries):
            try:
                result = await behavior_clustering(aspects=aspects, client=client)
                
                # Check if we got meaningful metrics
                if result and hasattr(result, 'metrics') and len(result.metrics) > 0:
                    if attempt > 0:
                        print(f"    ✅ Behavior clustering succeeded on attempt {attempt + 1}")
                    return result
                else:
                    if attempt < max_retries - 1:
                        print(f"    ⚠️  Empty behavior clustering result on attempt {attempt + 1}, retrying...")
                        import time
                        time.sleep(2)
                        continue
                    else:
                        print(f"    🚑 Using empty clustering result after {max_retries} attempts")
                        return result
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"    ❌ Behavior clustering failed on attempt {attempt + 1}: {e}")
                    print(f"    ⏳ Waiting 2 seconds before retry...")
                    import time
                    time.sleep(2)
                    continue
                else:
                    print(f"    ❌ Behavior clustering failed after {max_retries} attempts: {e}")
                    # Re-raise the exception since behavior clustering is critical
                    raise e
        
        # Should not reach here
        raise Exception("Unexpected end of retry loop")

    try:
        behavior_clustering_results = await behavior_clustering_with_retry(aspects)

        print(f"📈 Generated {len(behavior_clustering_results.metrics)} metrics")
        sys.stdout.flush()
        
        metrics_path = f".data/metrics/{dataset_name}/gemini_{num_metrics}metrics_{datetime.now().strftime('%m_%d_%H_%M')}"
        print(f"💾 Saving metrics to: {metrics_path}")
        sys.stdout.flush()

        metric_set = MetricSet(
            name=f"Derived Metrics (Gemini) - {num_metrics} metrics",
            base_path=metrics_path,
            induced_from=dataset_name,
            version="0.1",
        )

        metric_set.add_metrics(behavior_clustering_results.metrics)
        
        print("🎉 Gemini grounding completed successfully!")
        print(f"📍 Results saved to: {metrics_path}")
        print(f"📋 Feedback results: feedback_grounding_results.jsonl")
        print(f"🎯 Generated {len(behavior_clustering_results.metrics)} metrics")
        sys.stdout.flush()
        
    finally:
        # Always restore the original template
        restore_behavior_clustering_template(template_path, backup_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Balrog Converter (Gemini Version)")
    parser.add_argument(
        "--filename",
        type=str,
        required=True,
        help="The name of the folder containing the data for the given run",
    )
    parser.add_argument(
        "--num-metrics",
        type=int,
        default=6,
        help="Number of metrics to generate (default: 6)",
    )

    args = parser.parse_args()

    asyncio.run(main(args.filename, args.num_metrics)) 