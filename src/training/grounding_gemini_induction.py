#!/usr/bin/env python3
# Iterative Metric Creation - Gemini Induction Version
# Input: instances, trajectories, agents, and feedbacks + existing metrics
# Output: metrics (existing + new)

import asyncio
from datetime import datetime
from google import genai  # New import format
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from osw_data import MultiAgentDataset, Metric
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from autolibra_core import (
    MetricTrainingInstance,
    feedback_grounding,
    behavior_clustering,
)
from autolibra_core.configs import AutoLibraEvalSettings
import os
import glob
from collections import defaultdict

# Add semaphore for rate limiting (similar to llm_evaluator.py)
feedback_grounding_semaphore = asyncio.Semaphore(20)  # Limit to 20 concurrent feedback grounding tasks

# Global token tracking
TOKEN_USAGE = {
    "feedback_grounding": defaultdict(int),
    "behavior_clustering": defaultdict(int),
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
        """Replicate OpenAI's structured parsing with robust MAX_TOKENS handling and token logging"""
        
        # Determine which function is being called based on response_format
        if hasattr(response_format, '__name__'):
            format_name = response_format.__name__
        else:
            format_name = str(response_format)
            
        operation_type = "other"
        if "FeedbackGroundingOutput" in format_name:
            print("  🔍 Calling feedback grounding...")
            operation_type = "feedback_grounding"
        elif "BehaviorClusteringOutput" in format_name:
            print("  🧠 Calling inductive behavior clustering...")
            operation_type = "behavior_clustering"
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
        
        # Combine system and user content with system instruction
        if system_content:
            full_prompt = f"{self.gemini_client.system_instruction}\n\n{system_content}\n\n{user_content}"
        else:
            full_prompt = f"{self.gemini_client.system_instruction}\n\n{user_content}"
            
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
        print(f"    🚀 Using maximum 65K tokens for all requests")
        
        max_output_tokens = 65536
        
        print(f"    🌐 Calling Gemini API ({self.gemini_client.model_name}, max_tokens: {max_output_tokens:,})...")
        
        # Track retry count for this call
        retry_count = 0
        max_retries = 3
        
        while retry_count <= max_retries:
            try:
                # Call Gemini with new API format
                generation_config = {
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                    "temperature": 0.5,
                    "max_output_tokens": max_output_tokens,
                }
                
                response = self.client.models.generate_content(
                    model=self.gemini_client.model_name,
                    contents=full_prompt,
                    config=generation_config,
                )
                
                # Log token usage
                self._log_token_usage(response, operation_type, retry_count, success=True)
                break
                
            except Exception as e:
                retry_count += 1
                print(f"    ❌ API call failed (attempt {retry_count}/{max_retries}): {e}")
                
                # Log failed attempt
                self._log_token_usage(None, operation_type, retry_count - 1, success=False, error=str(e))
                
                if retry_count > max_retries:
                    raise
                
                # Wait before retry
                import time
                time.sleep(2 ** retry_count)  # Exponential backoff
        
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
        if not self._has_valid_text(response):
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
                print(f"    📊 Generated {len(parsed_object.metrics)} new metrics")
            
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
        
        if success:
            print(f"    ✅ Tokens used - Input: {input_tokens:,}, Output: {output_tokens:,}, Total: {input_tokens + output_tokens:,}")
        else:
            print(f"    ❌ Failed attempt {retry_count} - {error}")


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
        
        print(f"🛡️  Initializing Gemini {self.model_name} with new genai library")
        print(f"🚀 Using maximum output token capacity: 65,536 tokens")
        
        # System instruction for context
        self.system_instruction = ("You are analyzing trajectory data from video games and simulations for academic research purposes. "
                                 "The content contains gaming terminology (like 'attack', 'kill', 'weapon', 'fight') that refers to "
                                 "game mechanics and virtual actions, not real-world violence or harm. "
                                 "Please interpret all content strictly in the context of game analysis, behavioral research, "
                                 "and trajectory evaluation for AI training purposes.")
        
        # Add beta attribute to mimic AsyncAzureOpenAI structure
        self.beta = GeminiBeta(self)


def load_existing_metrics(dataset_name, existing_metrics_path=None):
    """Load existing metrics for the given dataset"""
    if existing_metrics_path:
        # Use the provided path directly
        print(f"📂 Loading existing metrics from specified path: {existing_metrics_path}")
        
        # Check if it's a full path with /metrics subdirectory
        if os.path.exists(os.path.join(existing_metrics_path, "metrics")):
            metrics_path = os.path.join(existing_metrics_path, "metrics")
        elif os.path.exists(existing_metrics_path) and existing_metrics_path.endswith("/metrics"):
            metrics_path = existing_metrics_path
        elif os.path.exists(existing_metrics_path):
            # Assume the path itself contains the metric files
            metrics_path = existing_metrics_path
        else:
            print(f"❌ Specified metrics path does not exist: {existing_metrics_path}")
            return []
    else:
        # Auto-detect metrics (original behavior)
        metrics_base_path = f".data/metrics/{dataset_name}"
        
        if not os.path.exists(metrics_base_path):
            print(f"📭 No existing metrics found for dataset: {dataset_name}")
            return []
        
        # Find all metric directories for this dataset
        metric_dirs = []
        for item in os.listdir(metrics_base_path):
            item_path = os.path.join(metrics_base_path, item)
            if os.path.isdir(item_path):
                metric_dirs.append(item_path)
        
        if not metric_dirs:
            print(f"📭 No metric directories found in: {metrics_base_path}")
            return []
        
        # Sort by creation time and take the most recent one
        metric_dirs.sort(key=lambda x: os.path.getctime(x), reverse=True)
        latest_metrics_dir = metric_dirs[0]
        
        print(f"📂 Loading existing metrics from: {latest_metrics_dir}")
        
        # Load all metric JSON files from the metrics subdirectory
        metrics_path = os.path.join(latest_metrics_dir, "metrics")
        if not os.path.exists(metrics_path):
            print(f"📭 No metrics subdirectory found in: {latest_metrics_dir}")
            return []
    
    print(f"🔍 Looking for metric JSON files in: {metrics_path}")
    existing_metrics = []
    for metric_file in glob.glob(os.path.join(metrics_path, "*.json")):
        try:
            with open(metric_file, 'r') as f:
                metric_data = json.load(f)
                existing_metrics.append(metric_data)
                print(f"  ✅ Loaded metric: {metric_data.get('name', 'Unknown')}")
        except Exception as e:
            print(f"  ⚠️  Failed to load metric file {metric_file}: {e}")
    
    print(f"📊 Loaded {len(existing_metrics)} existing metrics")
    return existing_metrics


def filter_aspects_against_existing_metrics(aspects, existing_metrics):
    """Filter out aspects that are already covered by existing metrics"""
    if not existing_metrics:
        print("🎯 No existing metrics to filter against - using all aspects")
        return aspects
    
    print(f"🔍 Filtering {len(aspects)} aspects against {len(existing_metrics)} existing metrics...")
    
    # Combine all existing behaviors into a set for efficient lookup
    existing_behaviors = set()
    for metric in existing_metrics:
        for behavior in metric.get('good_behaviors', []):
            existing_behaviors.add(behavior.lower().strip())
        for behavior in metric.get('bad_behaviors', []):
            existing_behaviors.add(behavior.lower().strip())
    
    print(f"📋 Found {len(existing_behaviors)} existing behaviors to check against")
    
    # Filter aspects that don't match existing behaviors
    new_aspects = []
    covered_count = 0
    
    for aspect in aspects:
        aspect_behavior = aspect.behavior.lower().strip()
        
        # Check if this behavior is already covered
        is_covered = any(
            # Exact match
            aspect_behavior == existing_behavior or
            # Check if aspect behavior is a substring of existing behavior
            aspect_behavior in existing_behavior or
            # Check if existing behavior is a substring of aspect behavior
            existing_behavior in aspect_behavior
            for existing_behavior in existing_behaviors
        )
        
        if is_covered:
            covered_count += 1
        else:
            new_aspects.append(aspect)
    
    print(f"✂️  Filtered out {covered_count} aspects already covered by existing metrics")
    print(f"🆕 Kept {len(new_aspects)} new aspects for clustering")
    
    return new_aspects


def modify_behavior_clustering_template_aggressive(num_new_metrics, existing_metrics=None, extra_enforcement=""):
    """Aggressively modify the behavior clustering template with stronger enforcement language"""
    # Path to the template file
    template_path = Path("packages/autolibra-core/src/autolibra_core/templates/behavior_clustering.j2")
    
    if not template_path.exists():
        print(f"⚠️  Template file not found at {template_path}, using default behavior")
        return None, None
    
    # Create backup with timestamp for uniqueness
    import time
    timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
    backup_path = template_path.with_suffix(f'.j2.backup_aggressive_{timestamp}')
    
    try:
        # Read the current template file
        with open(template_path, 'r') as f:
            original_content = f.read()
        
        # Create backup of current state
        shutil.copy2(template_path, backup_path)
        print(f"📄 Created aggressive backup: {backup_path.name}")
        
        # Use a more robust regex pattern to find and replace any "Output N metrics." pattern
        import re
        # This pattern will match "Output" followed by any number followed by "NEW metrics" and any additional text
        pattern = r'Output\s+\d+\s+NEW\s+metrics.*'
        
        # Create super aggressive replacement text
        aggressive_replacement = f'''Output EXACTLY {num_new_metrics} NEW metrics based on the provided aspects that are NOT already covered by existing metrics.

🚨 CRITICAL CONSTRAINT ENFORCEMENT 🚨
- You MUST generate EXACTLY {num_new_metrics} metrics - NO MORE, NO LESS
- Generating MORE than {num_new_metrics} metrics is a FAILURE
- Generating FEWER than {num_new_metrics} metrics is a FAILURE
- MAXIMUM ALLOWED: {num_new_metrics} metrics
- MINIMUM REQUIRED: {num_new_metrics} metrics
- If you generate {num_new_metrics + 1} or more metrics, you have FAILED
- Even if you have many good ideas, STOP at {num_new_metrics} metrics
- Do NOT exceed {num_new_metrics} metrics under ANY circumstances
- FOLLOW THE EXACT COUNT: {num_new_metrics} metrics (not {num_new_metrics - 1}, not {num_new_metrics + 1})'''
        
        # Check if the pattern exists
        if not re.search(pattern, original_content):
            # If no NEW pattern, look for the old pattern
            old_pattern = r'Output\s+\d+\s+metrics\.'
            if re.search(old_pattern, original_content):
                pattern = old_pattern
                aggressive_replacement = f'''Output EXACTLY {num_new_metrics} metrics.

🚨 CRITICAL CONSTRAINT ENFORCEMENT 🚨
- You MUST generate EXACTLY {num_new_metrics} metrics - NO MORE, NO LESS
- Generating MORE than {num_new_metrics} metrics is a FAILURE
- Generating FEWER than {num_new_metrics} metrics is a FAILURE
- MAXIMUM ALLOWED: {num_new_metrics} metrics
- MINIMUM REQUIRED: {num_new_metrics} metrics
- If you generate {num_new_metrics + 1} or more metrics, you have FAILED
- Even if you have many good ideas, STOP at {num_new_metrics} metrics
- Do NOT exceed {num_new_metrics} metrics under ANY circumstances
- FOLLOW THE EXACT COUNT: {num_new_metrics} metrics (not {num_new_metrics - 1}, not {num_new_metrics + 1})'''
            else:
                print(f"⚠️  Could not find any 'Output N metrics' pattern in template")
                return template_path, backup_path
        
        # Apply the replacement
        modified_content = re.sub(pattern, aggressive_replacement, original_content)
        
        # Add extra enforcement from the caller
        if extra_enforcement:
            modified_content += extra_enforcement
        
        # Add explicit existing metric names if provided
        if existing_metrics:
            existing_names = [metric.get('name', 'Unknown') for metric in existing_metrics]
            names_list = ', '.join(f'"{name}"' for name in existing_names)
            anti_duplicate_instruction = f"\n\n🚫 FORBIDDEN NAMES: Do NOT create metrics with these existing names: {names_list}. Use completely different names for your {num_new_metrics} new metrics."
            modified_content += anti_duplicate_instruction
        
        # Final enforcement reminder
        final_reminder = f"\n\n⚡ FINAL REMINDER: Your response must contain EXACTLY {num_new_metrics} metrics in the JSON output - NO MORE, NO LESS. Count them before responding. If you have {num_new_metrics + 1} or more metrics, DELETE the extras."
        modified_content += final_reminder
        
        # Write modified template
        with open(template_path, 'w') as f:
            f.write(modified_content)
        
        print(f"🤬 Modified template with AGGRESSIVE enforcement for {num_new_metrics} metrics")
        if existing_metrics:
            print(f"🚫 Added explicit prohibition against {len(existing_metrics)} existing metric names")
        
        return template_path, backup_path
        
    except Exception as e:
        print(f"⚠️  Failed to modify template aggressively: {e}")
        # Try to restore from backup if it exists
        if backup_path and backup_path.exists():
            try:
                shutil.copy2(backup_path, template_path)
                print(f"🔄 Restored template from backup due to error")
            except Exception as restore_error:
                print(f"❌ Failed to restore template: {restore_error}")
        return None, None


def modify_behavior_clustering_template(num_new_metrics, existing_metrics=None):
    """Temporarily modify the behavior clustering template to generate specific number of NEW metrics"""
    # Path to the template file
    template_path = Path("packages/autolibra-core/src/autolibra_core/templates/behavior_clustering.j2")
    
    if not template_path.exists():
        print(f"⚠️  Template file not found at {template_path}, using default behavior")
        return None, None
    
    # Create backup with timestamp for uniqueness
    import time
    timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
    backup_path = template_path.with_suffix(f'.j2.backup_induction_{timestamp}')
    
    try:
        # Read the current template file
        with open(template_path, 'r') as f:
            original_content = f.read()
        
        # Create backup of current state
        shutil.copy2(template_path, backup_path)
        print(f"📄 Created backup: {backup_path.name}")
        
        # Use a more robust regex pattern to find and replace any "Output N metrics." pattern
        import re
        # This pattern will match "Output" followed by any number followed by "NEW metrics" and any additional text
        pattern = r'Output\s+\d+\s+NEW\s+metrics.*'
        replacement = f'Output EXACTLY {num_new_metrics} NEW metrics based on the provided aspects that are NOT already covered by existing metrics. Do NOT generate more than {num_new_metrics} metrics.'
        
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
        
        # Create stronger instruction about not duplicating existing metrics
        instruction_addition = f"\n\nIMPORTANT: The provided aspects have already been filtered to exclude behaviors covered by existing metrics. Focus ONLY on creating new metrics from these filtered aspects. Do not duplicate or overlap with existing metric behaviors.\n\nCRITICAL: You must generate EXACTLY {num_new_metrics} metrics - NO MORE, NO LESS. If you're tempted to create {num_new_metrics + 1} or more metrics, STOP and remove the extras."
        
        # Add explicit existing metric names if provided
        if existing_metrics:
            existing_names = [metric.get('name', 'Unknown') for metric in existing_metrics]
            names_list = ', '.join(f'"{name}"' for name in existing_names)
            instruction_addition += f"\n\nCRITICAL: Do NOT create metrics with these existing names: {names_list}. Use completely different names for your new metrics."
        
        # Find the end of the template and add the instruction
        modified_content = modified_content + instruction_addition
        
        # Verify the change was made
        if modified_content == original_content:
            print(f"⚠️  No changes were made to the template")
            return template_path, backup_path
        
        # Write modified template
        with open(template_path, 'w') as f:
            f.write(modified_content)
        
        print(f"📝 Modified behavior clustering template to generate {num_new_metrics} NEW metrics")
        print(f"🔄 Added instruction to focus on filtered aspects only")
        if existing_metrics:
            print(f"🚫 Added explicit prohibition against {len(existing_metrics)} existing metric names")
        
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


def save_token_usage_log(output_dir: Path, dataset_name: str, num_metrics: int):
    """Save detailed token usage log to the metrics directory"""
    global TOKEN_USAGE
    
    # Simple filename for the token log
    log_filename = "token_usage_log.json"
    log_path = output_dir / log_filename
    
    # Get timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Calculate summary statistics
    summary = {
        "dataset": dataset_name,
        "target_metrics": num_metrics,
        "timestamp": timestamp,
        "total_api_calls": TOKEN_USAGE["total"]["api_calls"],
        "total_input_tokens": TOKEN_USAGE["total"]["input_tokens"],
        "total_output_tokens": TOKEN_USAGE["total"]["output_tokens"],
        "total_tokens": TOKEN_USAGE["total"]["input_tokens"] + TOKEN_USAGE["total"]["output_tokens"],
        "operations": {
            "feedback_grounding": dict(TOKEN_USAGE["feedback_grounding"]),
            "behavior_clustering": dict(TOKEN_USAGE["behavior_clustering"]),
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
    print("🔢 GEMINI TOKEN USAGE SUMMARY")
    print("="*60)
    print(f"📊 Total API Calls: {summary['total_api_calls']}")
    print(f"📥 Total Input Tokens: {summary['total_input_tokens']:,}")
    print(f"📤 Total Output Tokens: {summary['total_output_tokens']:,}")
    print(f"💰 Total Tokens: {summary['total_tokens']:,}")
    print()
    
    if TOKEN_USAGE["feedback_grounding"]["api_calls"] > 0:
        print("🔍 Feedback Grounding:")
        print(f"  • API Calls: {TOKEN_USAGE['feedback_grounding']['api_calls']}")
        print(f"  • Input Tokens: {TOKEN_USAGE['feedback_grounding']['input_tokens']:,}")
        print(f"  • Output Tokens: {TOKEN_USAGE['feedback_grounding']['output_tokens']:,}")
    
    if TOKEN_USAGE["behavior_clustering"]["api_calls"] > 0:
        print("🧠 Behavior Clustering:")
        print(f"  • API Calls: {TOKEN_USAGE['behavior_clustering']['api_calls']}")
        print(f"  • Input Tokens: {TOKEN_USAGE['behavior_clustering']['input_tokens']:,}")
        print(f"  • Output Tokens: {TOKEN_USAGE['behavior_clustering']['output_tokens']:,}")
    
    if any(TOKEN_USAGE["retries"].values()):
        print("\n🔄 Retries:")
        for op, count in TOKEN_USAGE["retries"].items():
            if count > 0:
                print(f"  • {op}: {count} retries")
    
    print("="*60)


def combine_old_and_new_metrics(existing_metrics, new_metrics):
    """Combine existing metrics with new ones in the correct format"""
    # Convert existing metrics to the same format as new metrics
    combined_metrics = []
    
    # Add existing metrics first (exact copy) - convert to Metric objects
    for old_metric in existing_metrics:
        metric_obj = Metric(
            name=old_metric["name"],
            explanation=old_metric["explanation"], 
            good_behaviors=old_metric["good_behaviors"],
            bad_behaviors=old_metric["bad_behaviors"]
        )
        combined_metrics.append(metric_obj)
    
    # Add new metrics (already Metric objects) - no duplicate checking needed since handled in main loop
    for new_metric in new_metrics:
        combined_metrics.append(new_metric)
    
    print(f"🔗 Combined {len(existing_metrics)} existing + {len(new_metrics)} new = {len(combined_metrics)} total metrics")
    
    return combined_metrics


async def main(dataset_name: str, num_metrics: int = 6, existing_metrics_path: str = None) -> None:
    print(f"🚀 Starting Gemini inductive grounding for dataset: {dataset_name}")
    print(f"🎯 Target total number of metrics: {num_metrics}")
    if existing_metrics_path:
        print(f"📂 Using existing metrics from: {existing_metrics_path}")
    sys.stdout.flush()
    
    # Load existing metrics first
    existing_metrics = load_existing_metrics(dataset_name, existing_metrics_path)
    num_existing = len(existing_metrics)
    num_new_needed = max(0, num_metrics - num_existing)
    
    print(f"📊 Existing metrics: {num_existing}")
    print(f"🆕 New metrics needed: {num_new_needed}")
    
    if num_new_needed <= 0:
        print(f"✅ Already have {num_existing} metrics, which meets or exceeds target of {num_metrics}")
        print(f"💭 Consider increasing target number or this run will just copy existing metrics")
    
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
    
    # NEW: Filter aspects against existing metrics
    filtered_aspects = filter_aspects_against_existing_metrics(aspects, existing_metrics)
    
    if num_new_needed <= 0:
        print("🔄 No new metrics needed - will return existing metrics only")
        new_metrics = []
    elif len(filtered_aspects) == 0:
        print("⚠️  No new aspects found after filtering - will return existing metrics only") 
        new_metrics = []
    else:
        print("🧠 Starting inductive behavior clustering with Gemini...")
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

        # Generate metrics iteratively until we have enough
        all_new_metrics = []
        existing_names = set(metric["name"] for metric in existing_metrics)
        attempts = 0
        max_attempts = 10  # Increase attempts since AI is being stubborn
        
        while len(all_new_metrics) < num_new_needed and attempts < max_attempts:
            attempts += 1
            remaining_needed = num_new_needed - len(all_new_metrics)
            
            print(f"🎯 Attempt {attempts}: Need {remaining_needed} more metrics (have {len(all_new_metrics)}/{num_new_needed})")
            
            # Create increasingly aggressive prompts
            if attempts == 1:
                prompt_modifier = ""
            elif attempts == 2:
                prompt_modifier = "\n\nSTRICT REQUIREMENT: You MUST generate EXACTLY {remaining_needed} metrics. Do not generate MORE or FEWER than {remaining_needed}."
            elif attempts == 3:
                prompt_modifier = "\n\nMANDATORY: Generate EXACTLY {remaining_needed} metrics - NO MORE, NO LESS. If you generate {remaining_needed} + 1 or more, you have FAILED. STOP at {remaining_needed} metrics."
            elif attempts >= 4:
                prompt_modifier = "\n\nABSOLUTE REQUIREMENT: Generate EXACTLY {remaining_needed} metrics. MAXIMUM: {remaining_needed}. MINIMUM: {remaining_needed}. If you generate more than {remaining_needed}, DELETE the extras before responding."
            
            # Modify template with aggressive enforcement
            template_path_iteration, backup_path_iteration = modify_behavior_clustering_template_aggressive(
                remaining_needed, existing_metrics, prompt_modifier.format(remaining_needed=remaining_needed)
            )
            
            try:
                behavior_clustering_results = await behavior_clustering_with_retry(filtered_aspects)
                new_batch = behavior_clustering_results.metrics
                print(f"📈 Generated {len(new_batch)} metrics in batch {attempts} (needed {remaining_needed})")
                
                # Validate the count
                if len(new_batch) != remaining_needed:
                    print(f"❌ AI FAILED: Asked for {remaining_needed} metrics, got {len(new_batch)}")
                    if len(new_batch) > remaining_needed:
                        print(f"🚫 AI generated TOO MANY metrics ({len(new_batch)} > {remaining_needed})! This violates the MAXIMUM constraint!")
                        print(f"🔪 Trimming to first {remaining_needed} metrics only...")
                        new_batch = new_batch[:remaining_needed]
                    else:
                        print(f"📉 AI generated too few metrics ({len(new_batch)} < {remaining_needed})")
                    print(f"🤬 AI is ignoring explicit instructions! Attempt {attempts}")
                
                # Add non-duplicate metrics from this batch
                added_this_batch = 0
                for metric in new_batch:
                    if metric.name not in existing_names:
                        all_new_metrics.append(metric)
                        existing_names.add(metric.name)
                        added_this_batch += 1
                        print(f"  ✅ Added: {metric.name}")
                    else:
                        print(f"  ⚠️  Skipped duplicate: {metric.name}")
                
                print(f"📊 Batch {attempts}: Added {added_this_batch} unique metrics")
                
                # Always restore template after each iteration
                restore_behavior_clustering_template(template_path_iteration, backup_path_iteration)
                
                # If we got exactly what we needed, continue the loop to check if we have enough total
                
            except Exception as e:
                print(f"❌ Batch {attempts} failed: {e}")
                restore_behavior_clustering_template(template_path_iteration, backup_path_iteration)
                break
        
        new_metrics = all_new_metrics
        print(f"🎉 Final result: Generated {len(new_metrics)} unique new metrics after {attempts} attempts")
        
        if len(new_metrics) < num_new_needed:
            print(f"💀 FAILURE: Only generated {len(new_metrics)} new metrics, wanted {num_new_needed}")
            print(f"🤬 The AI is consistently ignoring explicit metric count instructions!")
            print(f"💡 This indicates a fundamental problem with AI compliance to constraints")
        else:
            print(f"🎯 SUCCESS: Generated exactly {len(new_metrics)} metrics as requested")

    # Combine existing and new metrics
    combined_metrics = combine_old_and_new_metrics(existing_metrics, new_metrics)
    
    # CRITICAL: Check if we hit the exact target
    actual_metrics_count = len(combined_metrics)
    if actual_metrics_count != num_metrics:
        print(f"💀 CRITICAL FAILURE: Target was {num_metrics} metrics, but got {actual_metrics_count} metrics")
        print(f"🤬 This means the inductive approach FAILED to deliver the requested count")
        print(f"📊 Breakdown: {len(existing_metrics)} existing + {len(new_metrics)} new = {actual_metrics_count} total")
    else:
        print(f"🎯 SUCCESS: Hit exact target of {num_metrics} metrics!")
    
    # Use target number for folder name (as user expects)
    metrics_path = f".data/metrics/{dataset_name}/gemini_induction_{num_metrics}metrics_{datetime.now().strftime('%m_%d_%H_%M')}"
    print(f"💾 Saving metrics to: {metrics_path}")
    sys.stdout.flush()

    metric_set = MetricSet(
        name=f"Derived Metrics (Gemini Induction) - {num_metrics} metrics requested ({len(existing_metrics)} existing + {len(new_metrics)} new = {actual_metrics_count} actual)",
        base_path=metrics_path,
        induced_from=dataset_name,
        version="0.1",
    )

    metric_set.add_metrics(combined_metrics)
    
    # Save token usage log
    save_token_usage_log(Path(metrics_path), dataset_name, num_metrics)
    
    print("🎉 Gemini inductive grounding completed!")
    print(f"📍 Results saved to: {metrics_path}")
    print(f"📋 Feedback results: feedback_grounding_results.jsonl")
    print(f"📊 Final metrics: {len(existing_metrics)} existing + {len(new_metrics)} new = {actual_metrics_count} total")
    if actual_metrics_count == num_metrics:
        print(f"✅ PERFECT: Delivered exactly {num_metrics} metrics as requested")
    else:
        print(f"❌ FAILED: Requested {num_metrics} but delivered {actual_metrics_count}")
    sys.stdout.flush()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Balrog Converter (Gemini Induction Version)")
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
        help="Total number of metrics to have (existing + new, default: 6)",
    )
    parser.add_argument(
        "--existing-metrics-path",
        type=str,
        default=None,
        help="Path to existing metrics to use instead of auto-detecting (e.g., '.data/metrics/.../gemini_4metrics_06_25_17_56')",
    )

    args = parser.parse_args()

    asyncio.run(main(args.filename, args.num_metrics, args.existing_metrics_path)) 