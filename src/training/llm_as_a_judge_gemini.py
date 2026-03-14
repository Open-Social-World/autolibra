import asyncio
from google import genai
import json
from typing import Literal
from osw_data import MultiAgentDataset
from osw_data.metrics import MetricSet
from autolibra_core import (
    run_llm_eval,
)
from autolibra_core.data import MetricTrainingInstance
import os
from pydantic import Field, create_model


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

    def _get_safe_text(self, response):
        """Safely get text from response, return empty string if not available"""
        try:
            # New google.genai API response structure
            if hasattr(response, "text"):
                return response.text if response.text else ""
            elif hasattr(response, "candidates") and response.candidates:
                return (
                    response.candidates[0].content.parts[0].text
                    if response.candidates[0].content.parts
                    else ""
                )
            else:
                return ""
        except (ValueError, AttributeError, IndexError):
            return ""

    def _extract_metrics_from_response_format(self, response_format):
        """Extract metrics from the original response format"""
        fields = response_format.model_fields
        metrics = []

        # Debug: print all fields to see what we have
        print(f"🔍 DEBUG: Total fields in response_format: {len(fields)}")
        for field_name, field_info in fields.items():
            alias = getattr(field_info, "alias", field_name)
            print(f"  - {field_name} -> alias: {alias}")

        # Create mock metrics from the field information
        # First, identify all reasoning fields
        reasoning_fields = set()
        for field_name in fields.keys():
            if field_name.endswith("_reasoning"):
                reasoning_fields.add(field_name)

        # Now identify score fields: fields that have a corresponding reasoning field
        for field_name, field_info in fields.items():
            corresponding_reasoning_field = field_name + "_reasoning"
            is_score_field = corresponding_reasoning_field in reasoning_fields

            print(
                f"  🔍 Checking field: {field_name} -> corresponding reasoning field: {corresponding_reasoning_field} -> is score field: {is_score_field}"
            )

            if is_score_field:  # This is a score field
                print(f"  🔄 Processing score field: {field_name}")
                try:
                    # Extract metric name from alias (the alias is the original metric name)
                    metric_name = field_info.alias or field_name
                    metric_explanation = (
                        field_info.description or f"Evaluation of {metric_name}"
                    )

                    # Create a mock metric object
                    class MockMetric:
                        def __init__(self, name, explanation):
                            self.name = name
                            self.explanation = explanation

                    metrics.append(MockMetric(metric_name, metric_explanation))
                    print(f"  ✅ Extracted metric: {metric_name}")
                except Exception as e:
                    print(f"  ❌ Failed to extract metric from {field_name}: {e}")

        print(f"🎯 Total metrics extracted: {len(metrics)}")
        return metrics

    async def parse(self, model: str, messages: list, response_format):
        """Replicate OpenAI's structured parsing using Gemini's native structured output"""

        # Extract system and user content from messages
        system_content = ""
        user_content = ""

        for message in messages:
            if message["role"] == "system":
                system_content = message["content"]
            elif message["role"] == "user":
                user_content = message["content"]

        # Combine system and user content (no manual JSON formatting needed with native structured output)
        if system_content:
            full_prompt = f"{system_content}\n\n{user_content}"
        else:
            full_prompt = user_content

        # Create Gemini-compatible response format
        metrics = self._extract_metrics_from_response_format(response_format)
        gemini_response_format = self._make_gemini_evaluation_result_class(metrics)

        # Use generous token limit for direct evaluation
        token_limit = 50000

        result = await self._try_with_token_limit(
            full_prompt, token_limit, response_format, gemini_response_format
        )

        if result is not None:
            return result

        return self._create_minimal_response(response_format)

    def _make_snake_case(self, name: str) -> str:
        """Convert name to snake_case"""
        return name.lower().replace(" ", "_")

    def _make_gemini_evaluation_result_class(self, metrics):
        """Create evaluation result class with string enums for Gemini (copy of original but with string literals)"""
        eval_result = create_model(
            "EvaluationResult",
            **{
                self._make_snake_case(metric.name) + "_reasoning": (
                    str,
                    Field(
                        description=metric.explanation, alias=metric.name + " Reasoning"
                    ),
                )
                for metric in metrics
            },
            **{
                self._make_snake_case(metric.name): (
                    Literal["-1", "0", "1"],  # String literals for Gemini compatibility
                    Field(description=metric.explanation, alias=metric.name),
                )
                for metric in metrics
            },
        )
        return eval_result

    def _convert_enum_strings_to_ints(self, json_data, original_format):
        """Convert string enum values back to integers for score fields"""
        if not isinstance(json_data, dict):
            return json_data

        # Get field information to identify score fields
        fields = original_format.model_fields
        converted_data = json_data.copy()

        for field_name, field_info in fields.items():
            alias = getattr(field_info, "alias", field_name)

            # Check if this is a score field (not reasoning) and if it's in the response
            if not field_name.endswith("_reasoning") and alias in converted_data:
                value = converted_data[alias]
                # Convert string enum values to integers
                if isinstance(value, str) and value in ["-1", "0", "1"]:
                    converted_data[alias] = int(value)

        return converted_data

    def _manual_schema_fallback(self, response_format):
        """Fallback manual schema generation"""
        try:
            fields = response_format.model_fields
            properties = {}
            required = []

            # Process reasoning fields FIRST (same order as _make_evaluation_result_class)
            reasoning_fields = [
                (name, info)
                for name, info in fields.items()
                if name.endswith("_reasoning")
            ]
            score_fields = [
                (name, info)
                for name, info in fields.items()
                if not name.endswith("_reasoning")
            ]

            # Add reasoning fields first
            for field_name, field_info in reasoning_fields:
                alias = field_info.alias or field_name
                properties[alias] = {"type": "string"}
                if field_info.description:
                    properties[alias]["description"] = field_info.description
                required.append(alias)

            # Add score fields second
            for field_name, field_info in score_fields:
                alias = field_info.alias or field_name
                properties[alias] = {"type": "integer", "enum": [-1, 0, 1]}
                if field_info.description:
                    properties[alias]["description"] = field_info.description
                required.append(alias)

            return {"type": "object", "properties": properties, "required": required}
        except Exception:
            return {"type": "object", "properties": {}}

    async def _try_with_token_limit(
        self, full_prompt, token_limit, original_response_format, gemini_response_format
    ):
        """Try generation with native structured output using new google.genai API"""

        try:
            # Use new google.genai API with Gemini-compatible schema
            response = self.gemini_client.client.models.generate_content(
                model=self.gemini_client.model_name,
                contents=full_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": gemini_response_format,  # Gemini-compatible model with string enums
                },
            )

            # Get response text
            response_text = self._get_safe_text(response)
        except Exception as e:
            print(f"❌ Gemini generation failed: {e}")
            return None

        # Handle empty response
        if not response_text:
            return None

        # Parse JSON and create Pydantic object
        try:
            # Check if the new API returns parsed objects directly
            if hasattr(response, "parsed") and response.parsed:
                return GeminiCompletion(response.parsed)

            # Otherwise parse JSON manually
            response_text = response_text.strip()

            # With native structured output, response should already be valid JSON
            json_data = json.loads(response_text)

            # Convert string enum values back to integers for score fields
            json_data = self._convert_enum_strings_to_ints(
                json_data, original_response_format
            )

            # Validate against the original response format (not the Gemini-compatible one)
            parsed_object = original_response_format.model_validate(json_data)
            return GeminiCompletion(parsed_object)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ JSON parsing failed even with structured output: {e}")
            return None

    def _create_minimal_response(self, response_format):
        """Create a minimal valid response when Gemini fails"""
        class_name = getattr(response_format, "__name__", str(response_format))

        if "EvaluationResult" in class_name:
            # Create minimal evaluation result with all fields as "not applicable"
            fields = response_format.model_fields
            minimal_data = {}

            for field_name, field_info in fields.items():
                # Get the alias - this is what goes in the JSON
                alias = getattr(field_info, "alias", field_name)

                # Check if this is a reasoning field - must END with " Reasoning"
                if alias and alias.endswith(" Reasoning"):
                    print(f"🔧 DEBUG: {alias} is REASONING field")
                    minimal_data[alias] = (
                        "Unable to evaluate due to response limit - marking as not applicable"
                    )
                elif field_name.endswith("_reasoning"):
                    print(f"🔧 DEBUG: {field_name} is REASONING field (by field name)")
                    minimal_data[alias] = (
                        "Unable to evaluate due to response limit - marking as not applicable"
                    )
                else:
                    print(f"🔧 DEBUG: {alias} is SCORE field")
                    minimal_data[alias] = 0  # 0 = not applicable

            try:
                parsed_object = response_format.model_validate(minimal_data)
                return GeminiCompletion(parsed_object)
            except Exception as e:
                print(f"    ❌ Error creating minimal response: {e}")
                print(f"    🔍 Minimal data: {minimal_data}")
                # Try using field names instead of aliases as fallback
                minimal_data_fallback = {}
                for field_name, field_info in fields.items():
                    # Get the alias - this is the correct key to use
                    alias = getattr(field_info, "alias", field_name)
                    if field_name.endswith("_reasoning"):
                        minimal_data_fallback[alias] = (
                            "Unable to evaluate due to response limit - marking as not applicable"
                        )
                    else:
                        minimal_data_fallback[alias] = 0
                parsed_object = response_format.model_validate(minimal_data_fallback)
                return GeminiCompletion(parsed_object)

        # Fallback for other types
        raise ValueError(
            f"Cannot create minimal response for unknown format: {class_name}"
        )


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
        # Use the new google.genai library
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = "gemini-2.5-flash"

        # Add beta attribute to mimic AsyncAzureOpenAI structure
        self.beta = GeminiBeta(self)


async def main(dataset_name: str, metric_path: str) -> None:
    print("🚀 Starting evaluation...")
    print(f"📁 Dataset: {dataset_name}")
    print(f"📊 Metrics: {metric_path}")

    dataset = MultiAgentDataset(
        name="dataset",
        base_path=f".data/{dataset_name}",
    )

    metric_set = MetricSet(
        name="",
        base_path=metric_path,
        induced_from=dataset_name,
    )

    client = GeminiClient()

    print("📋 Loading training instances...")
    metric_training_instances: list[MetricTrainingInstance] = []

    instances_list = list(dataset.list_instances())
    print(f"🔍 Dataset found {len(instances_list)} instances")

    for instances in instances_list:
        print(f"  Processing instance: {instances}")
        instance = dataset.get_instance_metadata(instances)
        print(f"    Agents: {list(instance.agents)}")
        for agent_id in instance.agents:
            print(f"    Creating training instance for agent: {agent_id}")
            metric_training_instances.append(
                MetricTrainingInstance(
                    task=instance.metadata["task"]
                    if "task" in instance.metadata
                    else "Task is described in the trajectory observation",
                    agent_id=agent_id,
                    trajectory=dataset.get_trajectory(instances, agent_id),
                    feedback="",
                )
            )
            print(f"    ✅ Created training instance for {agent_id}")

    print(f"✅ Found {len(metric_training_instances)} training instances")
    print(f"🎯 Found {len(metric_set.metrics)} metrics")
    print("🤖 Starting evaluation...")

    eval_results = await run_llm_eval(
        metric_training_instances, list(metric_set.metrics.values()), client=client
    )

    print(f"💾 Saving {len(eval_results)} results...")
    output_filename = f"llm_eval_results_{dataset_name.replace('/', '_')}.jsonl"
    with open(output_filename, "w") as f:
        for i, eval_result in enumerate(eval_results):
            # Extract instance ID and agent ID from the training instance
            training_instance = metric_training_instances[i]

            # The trajectory_id is in format "{instance_id}_{agent_id}"
            trajectory_id = training_instance.trajectory.trajectory_id
            instance_id, agent_id = trajectory_id.rsplit("_", 1)

            # Convert evaluation result to dict and add metadata
            result_dict = eval_result.model_dump()
            result_dict["instance_id"] = instance_id
            result_dict["agent_id"] = agent_id

            # Convert string scores to integers for metric fields
            for key, value in result_dict.items():
                if (
                    not key.endswith("_reasoning")
                    and isinstance(value, str)
                    and value in ["-1", "0", "1"]
                ):
                    result_dict[key] = int(value)

            f.write(json.dumps(result_dict))
            f.write("\n")

    print(f"🎉 Done! Results saved to {output_filename}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Balrog Converter")
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
            dataset_name=filename,
            metric_path=metric_path,
        ),
    )
