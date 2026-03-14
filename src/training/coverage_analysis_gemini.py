import asyncio
import json
from google import genai  # New import format
from osw_data import MultiAgentDataset
from osw_data.annotation import AnnotationSystem
from osw_data.metrics import MetricSet
from autolibra_core.data import MetricTrainingInstance
from autolibra_core.data.primitives import Trait
from autolibra_core.evaluators.llm_evaluator import _make_snake_case
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Add semaphore for rate limiting (similar to llm_evaluator.py)
coverage_analysis_semaphore = asyncio.Semaphore(
    20
)  # Limit to 20 concurrent coverage analysis tasks

# Global token tracking for coverage analysis
TOKEN_USAGE = {
    "coverage_breakdown": defaultdict(int),
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
    """Unified completions interface using native Gemini schema"""

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

    def _convert_pydantic_to_gemini_schema(self, response_format):
        """Convert Pydantic model to Gemini-compatible JSON schema"""
        if hasattr(response_format, "__name__"):
            format_name = response_format.__name__
        else:
            format_name = str(response_format)

        if "FeedbackGroundingOutput" in format_name:
            return {
                "type": "object",
                "properties": {
                    "bullet_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "feedback": {"type": "string"},
                                "behavior": {"type": "string"},
                                "is_positive": {"type": "boolean"},
                            },
                            "required": ["feedback", "behavior", "is_positive"],
                        },
                    }
                },
                "required": ["bullet_points"],
            }
        elif "BehaviorClusteringOutput" in format_name:
            return {
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "explanation": {"type": "string"},
                                "good_behaviors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "bad_behaviors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "name",
                                "explanation",
                                "good_behaviors",
                                "bad_behaviors",
                            ],
                        },
                    }
                },
                "required": ["metrics"],
            }
        elif "AspectTraitsMatch" in format_name:
            # For AspectTraitsMatch: Always use the simple 2-field schema (aspect_0, trait_0)
            # This matches the original OpenAI implementation that processes one aspect at a time
            try:
                fields = response_format.model_fields
                properties = {}
                required = []

                # Extract literal values for aspect_0 and trait_0 specifically
                if "aspect_0" in fields:
                    properties["aspect_0"] = {"type": "string"}
                    required.append("aspect_0")

                if "trait_0" in fields:
                    properties["trait_0"] = {"type": "string"}
                    required.append("trait_0")

                return {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            except Exception:
                # Fallback for unknown dynamic schemas
                return {
                    "type": "object",
                    "properties": {
                        "aspect_0": {"type": "string"},
                        "trait_0": {"type": "string"},
                    },
                    "required": ["aspect_0", "trait_0"],
                }
        else:
            # Generic fallback for other types (like EvaluationResult)
            try:
                fields = response_format.model_fields
                properties = {}
                required = []

                for field_name, field_info in fields.items():
                    if field_name.endswith("_reasoning"):
                        properties[field_info.alias or field_name] = {"type": "string"}
                    else:
                        properties[field_info.alias or field_name] = {
                            "type": "integer",
                            "enum": [-1, 0, 1],
                        }
                    required.append(field_info.alias or field_name)

                return {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            except Exception:
                return {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                }

    async def parse(self, model: str, messages: list, response_format):
        """Replicate OpenAI's structured parsing using native Gemini schema"""

        # Extract system and user content from messages
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

        # Identify what type of call this is
        format_name = getattr(response_format, "__name__", str(response_format))
        print(f"    🔍 API Call Type: {format_name}")

        # For AspectTraitsMatch: Use native schema but with simplified approach
        if "AspectTraitsMatch" in format_name:
            print("    🔄 Using simplified native schema for AspectTraitsMatch")

            # Add format instructions to the prompt to guide the model
            format_instruction = (
                "\n\nPlease respond with valid JSON in this exact format:\n"
            )
            format_instruction += '{"aspect_0": "copy the exact aspect text", "trait_0": "choose the best matching trait or None of the traits matches the aspect."}\n'
            format_instruction += (
                "Important: Use only these exact field names: aspect_0 and trait_0"
            )

            full_prompt = full_prompt + format_instruction

        print(f"    📝 Prompt length: {len(full_prompt)} characters")

        # Add system instruction to prompt
        full_prompt = f"{self.gemini_client.system_instruction}\n\n{full_prompt}"

        # Use native schema approach for all types now
        schema = self._convert_pydantic_to_gemini_schema(response_format)
        print(
            f"    🏗️  Generated schema with {len(schema.get('properties', {}))} fields"
        )
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": schema,
            "temperature": 0.1,
            "max_output_tokens": 65536,
        }

        # Simplified retry logic - much lower retry count since we're using simpler schemas
        max_retries = 10  # Increased for hybrid approach with smart repair

        for attempt in range(max_retries):
            if attempt > 0:
                print(f"    🔄 Retry attempt {attempt}/{max_retries-1}")

            print(
                f"    🌐 Calling Gemini API (native schema, max_tokens: 65536)... [Attempt {attempt + 1}]"
            )

            try:
                # Call Gemini with new API format
                response = self.client.models.generate_content(
                    model=self.gemini_client.model_name,
                    contents=full_prompt,
                    config=generation_config,
                )

                # Log token usage
                self._log_token_usage(
                    response, "coverage_breakdown", attempt, success=True
                )

                # Debug response metadata
                print("    📊 Response metadata:")
                if hasattr(response, "usage_metadata"):
                    usage = response.usage_metadata
                    print(
                        f"      - Usage: prompt={getattr(usage, 'prompt_token_count', 'N/A')}, "
                        f"output={getattr(usage, 'candidates_token_count', 'N/A')}, "
                        f"total={getattr(usage, 'total_token_count', 'N/A')}"
                    )

                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "finish_reason"):
                        print(f"      - Finish reason: {candidate.finish_reason}")

                # Handle response
                if not self._has_valid_text(response):
                    print(f"    ⚠️  Empty response on attempt {attempt + 1}")

                    if attempt < max_retries - 1:
                        print("    ⏳ Waiting 2 seconds before retry...")
                        import time

                        time.sleep(2)
                        continue
                    else:
                        print("    ❌ All retry attempts failed")
                        print(
                            "    🚑 Empty response after all retries, using minimal fallback"
                        )
                        return self._create_minimal_response(response_format)

                response_text = self._get_safe_text(response)
                print(f"    ✅ Got response ({len(response_text):,} chars)")

                # Parse JSON and create Pydantic object
                try:
                    json_data = json.loads(response_text)
                    print("    🔧 Parsed JSON successfully")

                    try:
                        parsed_object = response_format.model_validate(json_data)
                        print(
                            f"    🎯 Successfully parsed response into {type(parsed_object).__name__}"
                        )
                        return GeminiCompletion(parsed_object)
                    except Exception as validation_error:
                        # Handle Pydantic validation errors with smart repair for AspectTraitsMatch
                        if (
                            hasattr(response_format, "__name__")
                            and "AspectTraitsMatch" in response_format.__name__
                            and hasattr(self.gemini_client, "_current_trait_options")
                        ):
                            print(
                                "    🔧 Attempting smart repair for AspectTraitsMatch validation error..."
                            )
                            try:
                                repaired_data = _attempt_smart_repair(
                                    json_data, self.gemini_client._current_trait_options
                                )
                                if repaired_data:
                                    repaired_object = response_format.model_validate(
                                        repaired_data
                                    )
                                    print("    🚑 Smart repair successful!")
                                    return GeminiCompletion(repaired_object)
                                else:
                                    print("    💔 Smart repair could not fix the data")
                            except Exception as repair_error:
                                print(
                                    f"    💔 Smart repair failed: {str(repair_error)[:50]}..."
                                )

                        # If smart repair didn't work or isn't applicable, re-raise the validation error
                        raise validation_error

                except json.JSONDecodeError as e:
                    print(f"    ⚠️  JSON parsing failed on attempt {attempt + 1}: {e}")
                    print(f"    📄 Failed response text: {response_text[:200]}...")

                    if attempt < max_retries - 1:
                        print("    ⏳ Waiting 2 seconds before retry...")
                        import time

                        time.sleep(2)
                        continue
                    else:
                        print("    ❌ JSON parsing failed after all retries")
                        print("    🚑 All retries failed, using minimal fallback")
                        return self._create_minimal_response(response_format)

                except Exception as e:
                    # Handle validation errors and other exceptions
                    print(
                        f"    ⚠️  Validation failed on attempt {attempt + 1}: {str(e)[:100]}..."
                    )

                    if attempt < max_retries - 1:
                        print("    ⏳ Waiting 2 seconds before retry...")
                        import time

                        time.sleep(2)
                        continue
                    else:
                        print("    ❌ Validation failed after all retries")
                        print("    🚑 All retries failed, using minimal fallback")
                        return self._create_minimal_response(response_format)

            except Exception as api_error:
                print(f"    ❌ API call failed on attempt {attempt + 1}: {api_error}")
                print(f"    🔍 Error type: {type(api_error).__name__}")

                # Log failed attempt
                self._log_token_usage(
                    None,
                    "coverage_breakdown",
                    attempt,
                    success=False,
                    error=str(api_error),
                )

                if attempt < max_retries - 1:
                    print("    ⏳ Waiting 2 seconds before retry...")
                    import time

                    time.sleep(2)
                    continue
                else:
                    print("    ❌ API call failed after all retries")
                    print("    🚑 All retries failed, using minimal fallback")
                    return self._create_minimal_response(response_format)

        # Should never reach here, but just in case
        print("    🚑 Unexpected end of retry loop, using minimal fallback")
        return self._create_minimal_response(response_format)

    def _log_token_usage(
        self, response, operation_type, retry_count, success=True, error=None
    ):
        """Log token usage from response with retry tracking"""
        global TOKEN_USAGE

        # Extract token counts from response
        input_tokens = 0
        output_tokens = 0

        if response and hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
            input_tokens = (
                (getattr(usage, "prompt_token_count", 0) or 0)
                + (getattr(usage, "cached_content_token_count", 0) or 0)
                + (getattr(usage, "tool_use_prompt_token_count", 0) or 0)
            )
            output_tokens = (getattr(usage, "candidates_token_count", 0) or 0) + (
                getattr(usage, "thoughts_token_count", 0) or 0
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
            "error": error,
        }

        TOKEN_USAGE["api_calls"].append(api_call_log)

        if success:
            print(
                f"      - Token usage: input={input_tokens:,}, output={output_tokens:,}, total={input_tokens + output_tokens:,}"
            )
        else:
            print(f"      - Failed attempt {retry_count} - {error}")

    def _create_minimal_response(self, response_format):
        """Create a minimal valid response when Gemini fails"""
        class_name = getattr(response_format, "__name__", str(response_format))

        if "AspectTraitsMatch" in class_name:
            # Create minimal aspect-trait match response with actual literal values
            try:
                model_fields = response_format.model_fields
                minimal_data = {}

                for field_name, field_info in model_fields.items():
                    if field_name.startswith("aspect_"):
                        # For aspect fields, get the actual literal from the annotation
                        try:
                            # Extract the literal value from the type annotation
                            if hasattr(field_info.annotation, "__args__"):
                                # This is a Literal type, get the first (and likely only) option
                                minimal_data[field_name] = (
                                    field_info.annotation.__args__[0]
                                )
                            else:
                                # Fallback to a generic message
                                minimal_data[field_name] = (
                                    "Unable to match aspect due to response limit"
                                )
                        except Exception as e:
                            print(
                                f"    ⚠️  Could not extract literal for {field_name}: {e}"
                            )
                            minimal_data[field_name] = (
                                "Unable to match aspect due to response limit"
                            )

                    elif field_name.startswith("trait_"):
                        # For trait fields, always use the standard "none" option
                        minimal_data[field_name] = (
                            "None of the traits matches the aspect."
                        )

                parsed_object = response_format.model_validate(minimal_data)
                print(
                    f"    🚑 Created minimal AspectTraitsMatch response with {len(minimal_data)} fields"
                )
                return GeminiCompletion(parsed_object)

            except Exception as e:
                print(
                    f"    ❌ Failed to create minimal AspectTraitsMatch response: {e}"
                )
                # If all else fails, we need to crash gracefully
                raise ValueError(
                    f"Cannot create minimal AspectTraitsMatch response: {e}"
                )

        elif "FeedbackGroundingOutput" in class_name:
            # Create minimal feedback grounding response
            minimal_data = {
                "bullet_points": [
                    {
                        "feedback": "Unable to ground feedback due to response limit",
                        "behavior": "No behavior identified",
                        "is_positive": False,
                    }
                ]
            }
            parsed_object = response_format.model_validate(minimal_data)
            print("    🚑 Created minimal FeedbackGroundingOutput response")
            return GeminiCompletion(parsed_object)

        elif "BehaviorClusteringOutput" in class_name:
            # Create minimal behavior clustering response
            minimal_data = {
                "metrics": [
                    {
                        "name": "Unable to cluster behaviors",
                        "explanation": "Response limit exceeded during clustering",
                        "good_behaviors": ["No behaviors identified"],
                        "bad_behaviors": ["No behaviors identified"],
                    }
                ]
            }
            parsed_object = response_format.model_validate(minimal_data)
            print("    🚑 Created minimal BehaviorClusteringOutput response")
            return GeminiCompletion(parsed_object)

        else:
            # For other types (like EvaluationResult), create a basic fallback
            try:
                fields = response_format.model_fields
                minimal_data = {}

                for field_name, field_info in fields.items():
                    # Get the alias - this is what goes in the JSON
                    alias = getattr(field_info, "alias", field_name)

                    if field_name.endswith("_reasoning"):
                        minimal_data[alias] = "Unable to evaluate due to response limit"
                    else:
                        minimal_data[alias] = 0  # 0 = not applicable

                try:
                    parsed_object = response_format.model_validate(minimal_data)
                    print(f"    🚑 Created minimal response for {class_name}")
                    return GeminiCompletion(parsed_object)
                except Exception as e:
                    print(f"    ❌ Error creating minimal response: {e}")
                    print(f"    🔍 Minimal data: {minimal_data}")
                    # Try using field names instead of aliases as fallback
                    minimal_data_fallback = {}
                    for field_name, field_info in fields.items():
                        if field_name.endswith("_reasoning"):
                            minimal_data_fallback[field_name] = (
                                "Unable to evaluate due to response limit"
                            )
                        else:
                            minimal_data_fallback[field_name] = 0
                    parsed_object = response_format.model_validate(
                        minimal_data_fallback
                    )
                    print(
                        f"    🚑 Created minimal response for {class_name} using field names as fallback"
                    )
                    return GeminiCompletion(parsed_object)
            except Exception as e:
                raise ValueError(
                    f"Cannot create minimal response for {class_name}: {e}"
                )


class GeminiChat:
    """Minimal chat interface"""

    def __init__(self, gemini_client):
        self.completions = GeminiCompletions(gemini_client)


class GeminiBeta:
    """Minimal beta interface"""

    def __init__(self, gemini_client):
        self.chat = GeminiChat(gemini_client)


def save_token_usage_log(dataset_name: str, results_file: str):
    """Save detailed token usage log to the same directory as results"""
    global TOKEN_USAGE

    # Get directory from results file
    output_dir = Path(results_file).parent if results_file else Path(".")

    # Create token log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"gemini_token_usage_coverage_{timestamp}.json"
    log_path = output_dir / log_filename

    # Calculate summary statistics
    summary = {
        "dataset": dataset_name,
        "results_file": results_file,
        "timestamp": timestamp,
        "total_api_calls": TOKEN_USAGE["total"]["api_calls"],
        "total_input_tokens": TOKEN_USAGE["total"]["input_tokens"],
        "total_output_tokens": TOKEN_USAGE["total"]["output_tokens"],
        "total_tokens": TOKEN_USAGE["total"]["input_tokens"]
        + TOKEN_USAGE["total"]["output_tokens"],
        "operations": {
            "coverage_breakdown": dict(TOKEN_USAGE["coverage_breakdown"]),
        },
        "retries": dict(TOKEN_USAGE["retries"]),
        "detailed_calls": TOKEN_USAGE["api_calls"],
    }

    # Save to file
    with open(log_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n💾 Token usage log saved to: {log_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("🔢 GEMINI TOKEN USAGE SUMMARY (Coverage Analysis)")
    print("=" * 60)
    print(f"📊 Total API Calls: {summary['total_api_calls']}")
    print(f"📥 Total Input Tokens: {summary['total_input_tokens']:,}")
    print(f"📤 Total Output Tokens: {summary['total_output_tokens']:,}")
    print(f"💰 Total Tokens: {summary['total_tokens']:,}")

    if TOKEN_USAGE["coverage_breakdown"]["api_calls"] > 0:
        print("\n🌊 Coverage Breakdown:")
        print(f"  • API Calls: {TOKEN_USAGE['coverage_breakdown']['api_calls']}")
        print(
            f"  • Input Tokens: {TOKEN_USAGE['coverage_breakdown']['input_tokens']:,}"
        )
        print(
            f"  • Output Tokens: {TOKEN_USAGE['coverage_breakdown']['output_tokens']:,}"
        )

    if any(TOKEN_USAGE["retries"].values()):
        print("\n🔄 Retries:")
        for op, count in TOKEN_USAGE["retries"].items():
            if count > 0:
                print(f"  • {op}: {count} retries")

    print("=" * 60)

    return str(log_path)


class GeminiClient:
    """Unified Gemini client using native schema for all requests"""

    def __init__(self):
        # New library uses a client instance with API key
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable"
            )

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

        # System instruction for context
        self.system_instruction = (
            "You are analyzing trajectory data from video games and simulations for academic research purposes. "
            "The content contains gaming terminology (like 'attack', 'kill', 'weapon', 'fight') that refers to "
            "game mechanics and virtual actions, not real-world violence or harm. "
            "Please interpret all content strictly in the context of game analysis, behavioral research, "
            "and trajectory evaluation for AI training purposes."
        )

        self.beta = GeminiBeta(self)


def load_evaluation_results(filename="llm_eval_results_gemini.jsonl"):
    """Load the evaluation results from the jsonl file"""
    print(f"📂 Loading evaluation results from: {filename}")

    if not os.path.exists(filename):
        raise FileNotFoundError(f"Evaluation results file not found: {filename}")

    eval_results = []
    with open(filename, "r") as f:
        for line in f:
            if line.strip():
                eval_results.append(json.loads(line.strip()))

    print(f"✅ Loaded {len(eval_results)} evaluation results")
    return eval_results


# Add Gemini-native coverage evaluation functions
def _sanitize_string(s: str) -> str:
    """Sanitize strings for safe processing (copied from autolibra-core)"""
    return (
        s.replace("\\'", "")
        .replace('\\"', "")
        .replace("\\n", " ")
        .replace("'", "")
        .replace('"', "")
        .replace("\n", " ")
        .replace("\\", " ")
        .replace("ℹ", " ")
    )


def _attempt_smart_repair(json_data: dict, trait_options: list[str]) -> dict | None:
    """Attempt to repair common Gemini abbreviation issues for AspectTraitsMatch"""
    try:
        if "trait_0" not in json_data:
            return None

        trait_result = json_data["trait_0"]

        # If it's already a valid trait, no repair needed
        if trait_result in trait_options:
            return json_data

        # Try to find a match by checking if any trait starts with this name
        for full_trait in trait_options[:-1]:  # Exclude "None..." option
            trait_name = full_trait.split(":")[0].strip()

            # Check for various matching patterns
            if (
                trait_name.lower() == trait_result.lower()
                or trait_name.lower() in trait_result.lower()
                or trait_result.lower() in trait_name.lower()
            ):
                print(
                    f"    🔧 Smart repair: '{trait_result[:30]}...' → '{full_trait[:30]}...'"
                )
                repaired_data = json_data.copy()
                repaired_data["trait_0"] = full_trait
                return repaired_data

        # Special case mappings for common abbreviations
        abbreviation_map = {
            "winning rule identification": "Winning Rule Identification",
            "environmental understanding": "Environmental Understanding and Spatial Awareness",
            "environmental understanding and spatial awareness": "Environmental Understanding and Spatial Awareness",
            "goal achievement": "Goal Achievement and Rule Manipulation",
            "goal achievement and rule manipulation": "Goal Achievement and Rule Manipulation",
            "strategic planning": "Strategic Planning and Prioritization",
            "strategic planning and prioritization": "Strategic Planning and Prioritization",
        }

        trait_lower = trait_result.lower()
        for abbrev, full_name in abbreviation_map.items():
            if abbrev in trait_lower:
                # Find the full trait that starts with this name
                for full_trait in trait_options[:-1]:
                    if full_trait.startswith(full_name + ":"):
                        print(
                            f"    🔧 Smart repair (mapping): '{trait_result[:30]}...' → '{full_trait[:30]}...'"
                        )
                        repaired_data = json_data.copy()
                        repaired_data["trait_0"] = full_trait
                        return repaired_data

        # If no match found, suggest using "None..."
        print(
            f"    ⚠️  No repair possible for: '{trait_result[:30]}...', suggesting None"
        )
        repaired_data = json_data.copy()
        repaired_data["trait_0"] = "None of the traits matches the aspect."
        return repaired_data

    except Exception as e:
        print(f"    ❌ Smart repair failed: {e}")
        return None


async def gemini_match_single_aspect_to_traits(client, aspect, traits):
    """Match a single aspect to traits using Gemini - one aspect at a time like original"""

    # Create the simplified schema for just one aspect (aspect_0, trait_0)
    trait_options = [
        _sanitize_string(trait.name) + ": " + _sanitize_string(trait.explanation)
        for trait in traits
    ] + ["None of the traits matches the aspect."]

    # Build prompt content
    aspect_text = (
        _sanitize_string(aspect.feedback) + ": " + _sanitize_string(aspect.behavior)
    )

    prompt = f"""Match this aspect to the most relevant trait.

Aspect: {aspect_text}

Available Trait Options (you MUST choose exactly one of these - copy the COMPLETE text including everything after the colon):
"""
    for i, trait_option in enumerate(trait_options):
        prompt += f"{i+1}. {trait_option}\n"

    prompt += f"""
EXAMPLE:
If the aspect is: "Agent failed: Poor performance"
And the best trait is: "Strategic Planning and Prioritization: This metric evaluates..."
Then respond: {{"aspect_0": "Agent failed: Poor performance", "trait_0": "Strategic Planning and Prioritization: This metric evaluates..."}}

CRITICAL REQUIREMENTS:
- aspect_0: Copy this EXACTLY: "{aspect_text}"
- trait_0: Copy one of the trait options above EXACTLY as written, including the full explanation after the colon
- If no trait matches well, use EXACTLY: "None of the traits matches the aspect."

You must copy the text character-for-character. Do not abbreviate, summarize, or paraphrase."""

    # Create simple dynamic model with strict Literal validation (like original OpenAI)
    from pydantic import Field, create_model
    from typing import Literal

    # Create literal types for validation (exactly like original)
    aspect_literal = Literal[aspect_text]
    trait_literal = Literal[tuple(trait_options)]

    # Create the dynamic model (exactly like original)
    AspectTraitMatch = create_model(
        "AspectTraitsMatch",
        aspect_0=(aspect_literal, Field(title="Aspect 0")),
        trait_0=(trait_literal, Field(title="Trait 0")),
    )

    print(f"    🎯 Matching aspect: {aspect_text[:50]}...")
    print(f"    📋 Against {len(traits)} traits")

    # Store trait_options for smart repair in the client
    client._current_trait_options = trait_options

    try:
        # Use the existing parse method which has its own retry logic
        completion = await client.beta.chat.completions.parse(
            model="gemini-2.5-flash",  # This parameter is ignored but needed for interface
            messages=[
                {
                    "role": "system",
                    "content": "You must copy text exactly as provided. Do not abbreviate or paraphrase. Follow the literal constraints precisely.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=AspectTraitMatch,
        )

        result = completion.choices[0].message.parsed
        return {"aspect_0": result.aspect_0, "trait_0": result.trait_0}
    finally:
        # Clean up
        if hasattr(client, "_current_trait_options"):
            delattr(client, "_current_trait_options")


async def gemini_match_aspects_and_traits(client, aspects, traits):
    """Process multiple aspects one at a time (like original OpenAI implementation)"""
    if not aspects:
        return {}

    print(f"  📊 Processing {len(aspects)} aspects one at a time...")

    # Process each aspect individually (like the original)
    results = []
    for i, aspect in enumerate(aspects):
        print(f"    🔍 Processing aspect {i+1}/{len(aspects)}")
        result = await gemini_match_single_aspect_to_traits(client, aspect, traits)
        results.append(result)

    # Convert to the expected format
    result_dict = {}
    for i, result in enumerate(results):
        result_dict[f"aspect_{i}"] = result["aspect_0"]
        result_dict[f"trait_{i}"] = result["trait_0"]

    return result_dict


async def gemini_run_instance_coverage_eval(client, aspects, traits):
    """Gemini-native instance coverage evaluation"""

    positive_aspects = [aspect for aspect in aspects if aspect.is_positive]
    negative_aspects = [aspect for aspect in aspects if not aspect.is_positive]
    positive_traits = [trait.metric for trait in traits if trait.rating == 1]
    negative_traits = [trait.metric for trait in traits if trait.rating == -1]

    print(
        f"  🟢 Processing {len(positive_aspects)} positive aspects against {len(positive_traits)} positive traits"
    )
    print(
        f"  🔴 Processing {len(negative_aspects)} negative aspects against {len(negative_traits)} negative traits"
    )

    # Coverage on positive aspects
    positive_match_results = await gemini_match_aspects_and_traits(
        client, positive_aspects, positive_traits
    )

    # Coverage on negative aspects
    negative_match_results = await gemini_match_aspects_and_traits(
        client, negative_aspects, negative_traits
    )

    number_of_total_aspects = len(aspects)
    number_of_not_matched_aspects = 0
    unmatch_aspects = []

    for i in range(len(positive_aspects)):
        if (
            positive_match_results[f"trait_{i}"]
            == "None of the traits matches the aspect."
        ):
            number_of_not_matched_aspects += 1
            unmatch_aspects.append(positive_aspects[i])

    for i in range(len(negative_aspects)):
        if (
            negative_match_results[f"trait_{i}"]
            == "None of the traits matches the aspect."
        ):
            number_of_not_matched_aspects += 1
            unmatch_aspects.append(negative_aspects[i])

    used_traits = set()

    for i in range(len(positive_aspects)):
        if (
            positive_match_results[f"trait_{i}"]
            != "None of the traits matches the aspect."
        ):
            used_traits.add(positive_match_results[f"trait_{i}"])

    for i in range(len(negative_aspects)):
        if (
            negative_match_results[f"trait_{i}"]
            != "None of the traits matches the aspect."
        ):
            used_traits.add(negative_match_results[f"trait_{i}"])

    return (
        number_of_total_aspects - number_of_not_matched_aspects,
        number_of_total_aspects,
        len(traits) - len(used_traits),
        len(traits),
        unmatch_aspects,
    )


async def gemini_run_coverage_eval(instance_traits, instances, client):
    """Gemini-native coverage evaluation replacing autolibra-core version"""
    from autolibra_core.operators import feedback_grounding

    print("🌊 Wave 1: Running feedback grounding on all instances...")
    instance_aspects = await asyncio.gather(
        *[feedback_grounding(instance, client) for instance in instances]
    )

    print("💾 Saving feedback grounding results...")
    with open("feedback_grounding_results.jsonl", "w") as f:
        for feedback_grounding_result in instance_aspects:
            for aspect in feedback_grounding_result:
                f.write(aspect.model_dump_json(indent=2))
                f.write("\n")
            f.write("\n")

    print("🌊 Wave 2: Running coverage evaluation on all instances...")
    coverage_results = await asyncio.gather(
        *[
            gemini_run_instance_coverage_eval(client, aspects, traits)
            for aspects, traits in zip(instance_aspects, instance_traits)
        ]
    )

    return coverage_results


async def main(
    dataset_name: str,
    metric_path: str,
    results_file: str = "llm_eval_results_gemini.jsonl",
    test_instance_only: int = None,
) -> None:
    if test_instance_only is not None:
        print(f"🔍 Testing Coverage Analysis on Instance {test_instance_only} Only...")
    else:
        print("🔍 Starting Coverage Analysis with Unified Gemini Client...")

    # Load evaluation results first
    eval_results_raw = load_evaluation_results(results_file)

    # Load dataset and metrics (needed for coverage analysis)
    dataset = MultiAgentDataset(
        name="dataset",
        base_path=f".data/gemini_babaisai/{dataset_name.split('/')[1]}",
    )

    annotation_system = AnnotationSystem(
        base_path=f".data/annotations/gemini_babaisai/{dataset_name.split('/')[1]}",
    )

    metric_set = MetricSet(
        name="",
        base_path=metric_path,
        induced_from=dataset_name,
    )

    # Use unified Gemini client (same as grounding_gemini.py)
    client = GeminiClient()

    print("📊 Reconstructing training instances...")
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

    print(f"📋 Reconstructed {len(metric_training_instances)} training instances")

    # Filter to specific instance if requested
    if test_instance_only is not None:
        if test_instance_only >= len(metric_training_instances):
            print(
                f"❌ Instance {test_instance_only} doesn't exist (only {len(metric_training_instances)} instances)"
            )
            return

        print(f"🎯 Testing ONLY instance {test_instance_only}")
        metric_training_instances = [metric_training_instances[test_instance_only]]
        eval_results_raw = [eval_results_raw[test_instance_only]]

    print(f"🎯 Found {len(metric_set.metrics)} metrics")

    # Verify counts match
    if len(eval_results_raw) != len(metric_training_instances):
        print(
            f"⚠️  Warning: Evaluation results ({len(eval_results_raw)}) don't match training instances ({len(metric_training_instances)})"
        )

    print("📊 Processing evaluation scores...")
    eval_scoring = []

    for result_data in eval_results_raw:
        scores = []
        for metric in metric_set.metrics.values():
            # Get score using snake_case name
            score_field = _make_snake_case(metric.name)
            score = int(result_data.get(score_field, 0))
            scores.append(score)
        eval_scoring.append(scores)

    print("🔍 Debug - Evaluation processing:")
    print(f"   - Raw results loaded: {len(eval_results_raw)}")
    print(f"   - Metrics available: {len(metric_set.metrics)}")
    print(f"   - Metric names: {list(metric_set.metrics.keys())}")
    print(
        f"   - Score matrix size: {len(eval_scoring)}x{len(eval_scoring[0]) if eval_scoring else 0}"
    )
    if eval_scoring:
        print(f"   - Sample scores (first instance): {eval_scoring[0]}")

    print("🔍 Creating traits for coverage analysis...")
    traits = [
        [
            Trait(
                metric=metric,
                rating=score,
            )
            for metric, score in zip(
                metric_set.metrics.values(), eval_scoring_for_instance
            )
        ]
        for eval_scoring_for_instance in eval_scoring
    ]

    print("🔍 Debug - Trait creation:")
    print(f"   - Traits created for {len(traits)} instances")
    if traits:
        print(f"   - Traits per instance: {len(traits[0])}")
        print(
            f"   - Sample trait ratings (first instance): {[t.rating for t in traits[0]]}"
        )

    print("🌐 Running coverage analysis with unified Gemini client...")

    # Add semaphore control for coverage evaluation to prevent overwhelming the API
    async def run_coverage_eval_with_semaphore(instance_traits, instances, client):
        """Wrapper to add semaphore control around coverage evaluation"""
        async with coverage_analysis_semaphore:
            return await gemini_run_coverage_eval(
                instance_traits=instance_traits,
                instances=instances,
                client=client,
            )

    coverage_results = await run_coverage_eval_with_semaphore(
        instance_traits=traits,
        instances=metric_training_instances,
        client=client,
    )

    print("📈 Calculating final statistics...")
    covered, total = 0, 0
    redundant, total_traits = 0, 0

    for coverage_result in coverage_results:
        covered += coverage_result[0]
        total += coverage_result[1]
        redundant += coverage_result[2]
        total_traits += coverage_result[3]

    print("\n🎉 Coverage Analysis Complete!")
    if test_instance_only is not None:
        print(f"📊 Instance {test_instance_only} Results:")

    # Add debugging information
    print("🔍 Debug Info:")
    print(f"   - Total instances processed: {len(coverage_results)}")
    print(f"   - Traits per instance: {[result[3] for result in coverage_results]}")
    print(f"   - Total aspects: {total}")
    print(f"   - Total traits: {total_traits}")

    # Handle division by zero
    if total > 0:
        coverage_percent = covered / total * 100
        print(
            f"📊 Coverage: {covered}/{total} ({coverage_percent:.1f}% of feedback aspects covered)"
        )
    else:
        print(f"📊 Coverage: {covered}/{total} (No aspects found)")

    if total_traits > 0:
        redundancy_percent = redundant / total_traits * 100
        print(
            f"🔄 Redundancy: {redundant}/{total_traits} ({redundancy_percent:.1f}% of metrics unused)"
        )
    else:
        print(
            f"🔄 Redundancy: {redundant}/{total_traits} (No traits found - check evaluation results)"
        )
        print("⚠️  Warning: No traits were created. This suggests an issue with:")
        print("    - LLM evaluation results format")
        print("    - Metric loading/processing")
        print("    - Trait creation logic")

    # Save token usage log
    save_token_usage_log(dataset_name, results_file)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Coverage Analysis with Unified Gemini - Phase 2"
    )
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
        "--results-file",
        type=str,
        default="llm_eval_results_gemini.jsonl",
        help="Path to the evaluation results file (default: llm_eval_results_gemini.jsonl)",
    )
    parser.add_argument(
        "--test-instance",
        type=int,
        default=None,
        help="Test only a specific instance index (0-based). Useful for debugging specific instances.",
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
            dataset_name=f"gemini_babaisai/{filename.split('/')[1]}",
            metric_path=metric_path,
            results_file=args.results_file,
            test_instance_only=args.test_instance,
        ),
    )
