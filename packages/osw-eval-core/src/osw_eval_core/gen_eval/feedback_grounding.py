import asyncio
from importlib import resources
import jinja2
from openai import AsyncAzureOpenAI, RateLimitError
from osw_eval_core.configs import OSWEvalSettings
from pydantic import BaseModel
from .generator import render_training_instance, MetricTrainingInstance


class BehavirorFeedback(BaseModel):
    feedback: str
    behavior: str


class FeedbackGroundingOutput(BaseModel):
    bullet_points: list[BehavirorFeedback]


def _load_feedback_grounding_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "feedback_grounding.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


async def feedback_grounding(
    instance: MetricTrainingInstance,
) -> FeedbackGroundingOutput:
    settings = OSWEvalSettings()

    client = AsyncAzureOpenAI(
        api_key=settings.azure_api_key,
        api_version="2024-10-21",
        azure_endpoint=settings.azure_endpoint,
    )

    template = _load_feedback_grounding_template()

    prompt = template.render(
        instance=dict(
            trajectory=render_training_instance(instance), feedback=instance.feedback
        )
    )

    wait_time = 1
    while True:
        try:
            completion = await client.beta.chat.completions.parse(
                model="gpt-4o-241120",
                messages=[
                    {
                        "role": "system",
                        "content": "Ground the feedback in the behavior.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=FeedbackGroundingOutput,
            )
            break
        except RateLimitError as e:
            print(f"Rate limit error: {e}")
            await asyncio.sleep(wait_time)
            wait_time *= 2

    if not completion.choices[0].message.parsed:
        raise ValueError("Failed to parse the response.")
    else:
        return completion.choices[0].message.parsed
