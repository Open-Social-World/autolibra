from importlib import resources
import jinja2
from openai import AsyncAzureOpenAI
from autolibra_eval_core.configs import AutoLibraEvalSettings
from pydantic import BaseModel, ValidationError
from ..data import Aspect
from autolibra_data import Metric


def _load_behavior_clustering_template() -> jinja2.Template:
    with resources.files("autolibra_eval_core.templates").joinpath(
        "behavior_clustering.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


class BehaviorClusteringOutput(BaseModel):
    metrics: list[Metric]


async def behavior_clustering(
    aspects: list[Aspect],
    client: AsyncAzureOpenAI,
) -> BehaviorClusteringOutput:
    prompt = _load_behavior_clustering_template().render(
        behavior_feedback_list=aspects,
    )

    settings = AutoLibraEvalSettings()

    model = settings.azure_openai_o3_model
    assert model is not None

    while True:
        try:
            completion = await client.beta.chat.completions.parse(
                model=model,
                messages=[
                    # {"role": "system", "content": "Cluster the behaviors."},
                    {"role": "user", "content": prompt},
                ],
                response_format=BehaviorClusteringOutput,
                reasoning_effort="high",
            )
            break
        except ValidationError as e:
            # In rare cases, the response may not be parsed correctly.
            # Retry the request.
            print(f"Validation error: {e}")

    if not completion.choices[0].message.parsed:
        raise ValueError("Failed to parse the response.")
    else:
        return completion.choices[0].message.parsed
