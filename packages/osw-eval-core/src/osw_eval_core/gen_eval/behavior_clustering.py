from importlib import resources
import jinja2
from openai import AsyncAzureOpenAI
from osw_eval_core.configs import OSWEvalSettings
from pydantic import BaseModel
from .feedback_grounding import FeedbackGroundingOutput
from osw_data import Metric


def _load_behavior_clustering_template() -> jinja2.Template:
    with resources.files("osw_eval_core.templates").joinpath(
        "behavior_clustering.j2"
    ).open("r") as f:
        return jinja2.Template(f.read())


class BehaviorClusteringOutput(BaseModel):
    metrics: list[Metric]


async def behavior_clustering(
    feedback_grounding_results: list[FeedbackGroundingOutput],
) -> BehaviorClusteringOutput:
    behavior_feedback_list = sum(
        (output.bullet_points for output in feedback_grounding_results), []
    )

    prompt = _load_behavior_clustering_template().render(
        behavior_feedback_list=behavior_feedback_list,
    )

    settings = OSWEvalSettings()

    client = AsyncAzureOpenAI(
        api_key=settings.azure_api_key,
        api_version="2024-12-01-preview",
        azure_endpoint=settings.azure_endpoint,
    )

    completion = await client.beta.chat.completions.parse(
        model="o1-241217",
        messages=[
            # {"role": "system", "content": "Cluster the behaviors."},
            {"role": "user", "content": prompt},
        ],
        response_format=BehaviorClusteringOutput,
    )

    if not completion.choices[0].message.parsed:
        raise ValueError("Failed to parse the response.")
    else:
        return completion.choices[0].message.parsed
