import asyncio
from importlib import resources
import jinja2
from openai import AsyncAzureOpenAI, RateLimitError
from osw_eval_core.configs import OSWEvalSettings
from pydantic import BaseModel, Field
from .generator import render_training_instance, MetricTrainingInstance


class Aspect(BaseModel):
    feedback: str
    behavior: str
    is_positive: bool = Field(
        description="Whether the feedback is positive or negative."
    )


class FeedbackGroundingOutput(BaseModel):
    bullet_points: list[Aspect]


def _load_feedback_grounding_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "feedback_grounding.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


async def feedback_grounding(
    instance: MetricTrainingInstance,
    client: AsyncAzureOpenAI,
) -> FeedbackGroundingOutput:
    settings = OSWEvalSettings()

    template = _load_feedback_grounding_template()

    prompt = template.render(
        instance=dict(
            trajectory=render_training_instance(instance), feedback=instance.feedback
        )
    )

    model = settings.azure_openai_4o_model
    assert model

    wait_time = 1
    while True:
        try:
            completion = await client.beta.chat.completions.parse(
                model=model,
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
