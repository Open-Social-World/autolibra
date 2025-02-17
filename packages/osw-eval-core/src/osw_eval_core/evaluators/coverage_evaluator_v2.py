import asyncio
from importlib import resources
import pickle
from typing import Any, Literal
import jinja2
from openai import AsyncAzureOpenAI, RateLimitError
import openai
from osw_data.metrics import Metric
from osw_eval_core.configs import OSWEvalSettings
from osw_eval_core.gen_eval.generator import MetricTrainingInstance
from ..gen_eval.feedback_grounding import BehavirorFeedback, feedback_grounding
from pydantic import BaseModel, ValidationError, create_model, Field


def _load_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "aspect_traits_match.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


def sanitize_string(s: str) -> str:
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


def create_aspect_traits_match_json_schema(
    aspects: list[BehavirorFeedback], traits: list[Metric]
) -> dict[str, Any]:
    # First, let's prepare the traits tuple once since it's the same for all trait fields
    trait_options = [
        f"{sanitize_string(trait.name)}: {sanitize_string(trait.explanation)}"
        for trait in traits
    ] + [
        "None of the traits matches the aspect.",
    ]

    # Create fields for aspects and traits
    schema = {}
    schema["properties"] = {}
    for i in range(len(aspects)):
        # Combine behavior and feedback with properly escaped strings
        aspect_text = f"{sanitize_string(aspects[i].feedback)} {sanitize_string(aspects[i].behavior)}"

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
    schema["additionalProperties"] = False

    return schema


async def create_aspect_traits_match_pydantic_model(
    aspects: list[BehavirorFeedback], traits: list[Metric]
) -> BaseModel:
    fields: dict[str, tuple[type[Literal[str]], Field]] = {}
    for i in range(len(aspects)):
        fields[f"aspect_{i}"] = (
            Literal[
                sanitize_string(aspects[i].feedback)
                + ": "
                + sanitize_string(aspects[i].behavior)
            ],
            Field(title=f"Aspect {i}"),
        )

        fields[f"trait_{i}"] = (
            Literal[
                tuple(
                    sanitize_string(trait.name)
                    + ": "
                    + sanitize_string(trait.explanation)
                    for trait in traits
                )
                + ("None of the traits matches the aspect.",)
            ],
            Field(title=f"Trait {i}"),
        )

    return create_model("AspectTraitsMatch", **fields)


async def match_aspects_and_traits(
    client: AsyncAzureOpenAI, aspects: list[BehavirorFeedback], traits: list[Metric]
) -> BaseModel:
    settings = OSWEvalSettings()
    aspect_traits_model = await create_aspect_traits_match_pydantic_model(
        aspects, traits
    )

    template = _load_template()
    prompt = template.render(
        aspects=aspects,
        traits=traits,
    )

    while True:
        wait_time = 1
        try:
            completion = await client.beta.chat.completions.parse(
                model=settings.azure_openai_4o_model,
                messages=[
                    {"role": "system", "content": "Match the aspects with the traits."},
                    {"role": "user", "content": prompt},
                ],
                response_format=aspect_traits_model,
            )
            break
        except ValidationError as e:
            print(e)
            print(aspect_traits_model.model_json_schema())
        except RateLimitError as e:
            print(e)
            wait_time *= 2
            await asyncio.sleep(wait_time)
        except openai.BadRequestError as e:
            print(aspect_traits_model.model_json_schema())
            print(e)
            raise e

    return completion.choices[0].message.parsed


async def run_instance_coverage_eval(
    client: AsyncAzureOpenAI,
    aspects: list[BehavirorFeedback],
    traits: list[Metric],
    ratings: list[int],
) -> tuple[int, int, int, int, list[BehavirorFeedback]]:
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
    unmatch_aspects: list[BehavirorFeedback] = []

    for i in range(len(positive_aspects)):
        if (
            positive_match_results.model_dump()[f"trait_{i}"]
            == "None of the traits matches the aspect."
        ):
            number_of_not_matched_aspects += 1
            unmatch_aspects.append(positive_aspects[i])

    for i in range(len(negative_aspects)):
        if (
            negative_match_results.model_dump()[f"trait_{i}"]
            == "None of the traits matches the aspect."
        ):
            number_of_not_matched_aspects += 1
            unmatch_aspects.append(negative_aspects[i])

    used_traits = set()

    for i in range(len(positive_aspects)):
        if (
            positive_match_results.model_dump()[f"trait_{i}"]
            != "None of the traits matches the aspect."
        ):
            used_traits.add(positive_match_results.model_dump()[f"trait_{i}"])

    for i in range(len(negative_aspects)):
        if (
            negative_match_results.model_dump()[f"trait_{i}"]
            != "None of the traits matches the aspect."
        ):
            used_traits.add(negative_match_results.model_dump()[f"trait_{i}"])

    return (
        number_of_total_aspects - number_of_not_matched_aspects,
        number_of_total_aspects,
        len(traits) - len(used_traits),
        len(traits),
        unmatch_aspects,
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
