import pickle
from openai import AsyncAzureOpenAI
from osw_data.metrics import Metric
from osw_eval_core.configs import OSWEvalSettings
from osw_eval_core.evaluators.coverage_evaluator_v2 import (
    match_aspects_and_traits,
    create_aspect_traits_match_model,
)
from osw_eval_core.gen_eval.feedback_grounding import BehavirorFeedback
import pytest

"""
{"feedback":"\"The agent initially tried to find the contributors through the Commit history or Graph tab which are reasonable guesses, but the Contributor tab is the most straightforward choice.","behavior":"\"The agent went step by step through different sections (Commits, Graph) before navigating to the Contributors tab.\"","is_positive":true}
{"feedback":"\"Anyway, the agent made the right choice in the end which is good although wasting a few more steps.\"","behavior":"\"The agent ultimately navigated to the Contributors tab and successfully identified the top contributor.\"","is_positive":true}
"""

"""
{"good_behaviors":["Behavior #3: The agent typed 'white desk' into the correct search box (ID 172) and pressed Search.","Behavior #4: The agent clicked the 'Add to Wish List' button (ID 5919) for the correct item.","Behavior #39: The agent typed 'white desk' into the correct search bar (ID 1585).","Behavior #40: The agent clicked the 'Add to Wish List' button (ID 6684) for the correct product."],"bad_behaviors":["Behavior #1: The agent clicked on a nonexistent element (ID 1488).","Behavior #6: The agent tried typing into the wrong text areas (IDs 2169 and 3421) instead of the actual textbox.","Behavior #8: The agent clicked on a nonexistent element (ID 1605)."],"explanation":"Measures whether the agent targets valid page elements for its actions. Good behaviors involve using the correct element ID or selector for the intended action, whereas bad behaviors show the agent clicking or typing into the wrong or nonexistent elements.","name":"Element Interaction Correctness"}
{"good_behaviors":["Behavior #20: The agent found the website URL of the Carnegie Museum of Art successfully.","Behavior #22: The agent identified the correct zip code (06516) confirming the Yale University location.","Behavior #24: The agent began searching for the Carnegie Museum of Art in Pittsburgh and proceeded correctly.","Behavior #25: The final action where the agent indeed outputs the museum’s website at the end of the trajectory.","Behavior #37: The agent identified the top contributor’s email address accurately."],"bad_behaviors":["Behavior #14: The agent mistakenly reported the rating of the wrong product (iPhone Cable) instead of 'Lightning to 3.5mm Adapter.'","Behavior #15: The agent did not succeed in locating the intended 'Canon Photo Printer' listing."],"explanation":"Covers how precisely the agent retrieves or pinpoints the correct item or piece of data requested. Positive instances yield exactly the needed information, whereas negative ones incorrectly match or fail to locate the target.","name":"Information Discovery Accuracy"}
"""

_aspects = [
    BehavirorFeedback(
        feedback="The agent initially tried to find the contributors through the Commit history or Graph tab which are reasonable guesses, but the Contributor tab is the most straightforward choice.",
        behavior="The agent went step by step through different sections (Commits, Graph) before navigating to the Contributors tab.",
        is_positive=True,
    ),
    BehavirorFeedback(
        feedback="Anyway, the agent made the right choice in the end which is good although wasting a few more steps.",
        behavior="The agent ultimately navigated to the Contributors tab and successfully identified the top contributor.",
        is_positive=True,
    ),
]

_traits = [
    Metric(
        name="Element Interaction Correctness",
        explanation="Measures whether the agent targets valid page elements for its actions. Good behaviors involve using the correct element ID or selector for the intended action, whereas bad behaviors show the agent clicking or typing into the wrong or nonexistent elements.",
    ),
    Metric(
        name="Information Discovery Accuracy",
        explanation="Covers how precisely the agent retrieves or pinpoints the correct item or piece of data requested. Positive instances yield exactly the needed information, whereas negative ones incorrectly match or fail to locate the target.",
    ),
]


@pytest.mark.asyncio
async def test_match_aspects_and_traits():
    settings = OSWEvalSettings()

    (_aspects, _traits) = pickle.load(
        open(
            "/Users/hao/osw-eval/packages/osw-eval-core/tests/positive_aspects_traits.pkl",
            "rb",
        )
    )

    client = AsyncAzureOpenAI(
        api_key=settings.azure_api_key,
        api_version="2024-10-21",
        azure_endpoint=settings.azure_endpoint,
    )

    result_model = create_aspect_traits_match_model(aspects=_aspects, traits=_traits)

    print(result_model.model_json_schema())

    _ = await match_aspects_and_traits(
        client=client,
        aspects=_aspects[:1],
        traits=_traits,
    )
