import asyncio
from importlib import resources
import jinja2
from openai import AsyncAzureOpenAI, RateLimitError
from autolibra_data.metrics import Metric
from autolibra_eval_core.configs import AutoLibraEvalSettings
from ..data import MetricTrainingInstance
from ..utils import render_training_instance
from pydantic import BaseModel, ValidationError, create_model, Field
from typing import Literal


def _make_snake_case(name: str) -> str:
    return name.lower().replace(" ", "_")


def _make_evaluation_result_class(metrics: list[Metric]) -> type[BaseModel]:
    eval_result = create_model(  # type: ignore[call-overload]
        "EvaluationResult",
        **{
            _make_snake_case(metric.name) + "_reasoning": (
                str,
                Field(description=metric.explanation, alias=metric.name + " Reasoning"),
            )
            for metric in metrics
        },
        **{
            _make_snake_case(metric.name): (
                Literal[-1, 0, 1],
                Field(description=metric.explanation, alias=metric.name),
            )
            for metric in metrics
        },
    )
    return eval_result  # type: ignore[no-any-return]


def _load_llm_eval_template() -> jinja2.Template:
    with resources.files("autolibra_eval_core.templates").joinpath(
        "llm_as_a_judge_evaluator_v3.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


semaphore = asyncio.Semaphore(20)  # Limit to 3 concurrent tasks


async def eval_instance(
    instance: MetricTrainingInstance, metrics: list[Metric], client: AsyncAzureOpenAI
) -> BaseModel:
    settings = AutoLibraEvalSettings()
    template = _load_llm_eval_template()

    prompt = template.render(
        trajectory=render_training_instance(instance),
        metrics=metrics,
    )

    model = settings.azure_openai_o3_model
    assert model

    async with semaphore:
        while True:
            wait_time = 1
            try:
                completion = await client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": "Evaluate the trajectory."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format=_make_evaluation_result_class(metrics),
                    reasoning_effort="medium",
                )

                if not completion.choices[0].message.parsed:
                    print("Failed to parse the response. Retrying.")
                    await asyncio.sleep(wait_time)
                    continue
                break
            except (ValidationError, RateLimitError) as e:
                print(e)
                await asyncio.sleep(wait_time)
                wait_time *= 2

        if not completion.choices[0].message.parsed:
            raise ValueError("Failed to parse the response.")
        else:
            return completion.choices[0].message.parsed


async def run_llm_eval(
    instances: list[MetricTrainingInstance],
    metrics: list[Metric],
    client: AsyncAzureOpenAI,
) -> list[BaseModel]:
    eval_results = await asyncio.gather(
        *[eval_instance(instance, metrics, client) for instance in instances]
    )

    return eval_results
