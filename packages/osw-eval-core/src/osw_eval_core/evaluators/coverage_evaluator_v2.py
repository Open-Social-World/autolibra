import asyncio
from importlib import resources
import pickle
from typing import Any
import jinja2
from openai import AsyncAzureOpenAI, RateLimitError
import openai
from osw_data.metrics import Metric
from osw_eval_core.configs import OSWEvalSettings
from osw_eval_core.gen_eval.generator import MetricTrainingInstance
from ..gen_eval.feedback_grounding import BehavirorFeedback, feedback_grounding
from pydantic import BaseModel


def _load_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "aspect_traits_match.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def create_aspect_traits_match_json_schema(
    aspects: list[BehavirorFeedback], traits: list[Metric]
) -> dict[str, Any]:
    # First, let's prepare the traits tuple once since it's the same for all trait fields
    trait_options = tuple(f"{trait.name}: {trait.explanation}" for trait in traits) + (
        "None of the traits matches the aspect.",
    )

    # Create fields for aspects and traits
    schema = {}
    schema["properties"] = {}
    for i in range(len(aspects)):
        # Combine behavior and feedback with properly escaped strings
        aspect_text = f"{aspects[i].feedback} {aspects[i].behavior}"

        schema["properties"][f"aspect_{i}"] = {
            "type": "string",
            "const": aspect_text,
            "title": f"Aspect {i}",
        }

        schema["properties"][f"trait_{i}"] = {
            "type": "string",
            "enum": trait_options,
            "title": f"Trait {i}",
        }

    schema["required"] = [f"trait_{i}" for i in range(len(aspects))] + [
        f"aspect_{i}" for i in range(len(aspects))
    ]
    schema["title"] = "AspectTraitsMatch"
    schema["type"] = "object"

    return schema


async def match_aspects_and_traits(
    client: AsyncAzureOpenAI, aspects: list[BehavirorFeedback], traits: list[Metric]
) -> BaseModel:
    aspect_traits_match_schema = create_aspect_traits_match_json_schema(aspects, traits)

    template = _load_template()
    prompt = template.render(
        aspects=aspects,
        traits=traits,
    )

    while True:
        wait_time = 1
        try:
            completion = await client.chat.completions.parse(
                model="gpt-4o-241120",
                messages=[
                    {"role": "system", "content": "Match the aspects with the traits."},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "AspectTraitsMatch",
                        "schema": aspect_traits_match_schema,
                        "strict": True,
                    },
                },
            )
            break
        except RateLimitError as e:
            print(e)
            wait_time *= 2
            await asyncio.sleep(wait_time)
        except openai.BadRequestError as e:
            print(e)
            raise e

    if not completion.choices[0].message.parsed:
        raise ValueError("Failed to parse the completion.")
    else:
        return completion.choices[0].message.parsed


async def run_instance_coverage_eval(
    client: AsyncAzureOpenAI,
    aspects: list[BehavirorFeedback],
    traits: list[Metric],
    ratings: list[int],
) -> tuple[int, int]:
    positive_aspects = [aspect for aspect in aspects if aspect.is_positive]
    negative_aspects = [aspect for aspect in aspects if not aspect.is_positive]
    positive_traits = [trait for (trait, rating) in zip(traits, ratings) if rating == 1]
    negative_traits = [
        trait for (trait, rating) in zip(traits, ratings) if rating == -1
    ]

    # Coverage on positive aspects
    try:
        positive_match_results = await match_aspects_and_traits(
            client, positive_aspects, positive_traits
        )
    except openai.BadRequestError as e:
        pickle.dump(
            (positive_aspects, positive_traits),
            open("positive_aspects_traits.pkl", "wb"),
        )
        raise e

    # Coverage on negative aspects
    negative_match_results = await match_aspects_and_traits(
        client, negative_aspects, negative_traits
    )

    number_of_total_aspects = len(aspects)
    number_of_not_matched_aspects = 0

    for i in range(len(positive_aspects)):
        if (
            positive_match_results.model_dump()[f"trait_{i}"]
            == "None of the traits matches the aspect."
        ):
            number_of_not_matched_aspects += 1

    for i in range(len(negative_aspects)):
        if (
            negative_match_results.model_dump()[f"trait_{i}"]
            == "None of the traits matches the aspect."
        ):
            number_of_not_matched_aspects += 1

    return (
        number_of_total_aspects - number_of_not_matched_aspects,
        number_of_total_aspects,
    )


async def run_coverage_eval(
    metrics: list[Metric],
    metric_scoring: list[list[int]],
    instances: list[MetricTrainingInstance],
):
    settings = OSWEvalSettings()

    client = AsyncAzureOpenAI(
        api_key=settings.azure_api_key,
        api_version="2024-10-21",
        azure_endpoint=settings.azure_endpoint,
    )

    feedback_grounding_results = await asyncio.gather(
        *[feedback_grounding(instance) for instance in instances]
    )

    coverage_results = await asyncio.gather(
        *[
            run_instance_coverage_eval(
                client, feedback_grounding_result.bullet_points, metrics, ratings
            )
            for feedback_grounding_result, ratings in zip(
                feedback_grounding_results, metric_scoring
            )
        ]
    )

    return coverage_results
