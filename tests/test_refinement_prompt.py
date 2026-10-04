from datetime import datetime, timezone

from app.services.recommendation_engine import build_refinement_prompt


def _base_args():
    profile = {"risk_cadence": "Balanced", "horizon_years": 15, "preferences": {}, "restrictions": {}}
    goal = {
        "category": "Retirement",
        "target_amount": 50000,
        "current_amount": 5000,
        "target_date": datetime(2041, 1, 1, tzinfo=timezone.utc),
        "contribution_cadence": "monthly",
        "contribution_amount": 200,
    }
    prior_recommendation = {
        "what": "Shift to a 70/30 stock/bond split using VTI and BND",
        "target_allocation": {"stocks": 70, "bonds": 30},
        "suggested_instruments": ["VTI", "BND", "NVDA"],
    }
    return profile, goal, prior_recommendation


def test_build_refinement_prompt_includes_prior_recommendation_and_message():
    profile, goal, prior_recommendation = _base_args()

    prompt = build_refinement_prompt(
        profile=profile,
        goal=goal,
        goal_analysis=None,
        context_docs=[],
        default_allocation={"stocks": 60, "bonds": 40},
        prior_recommendation=prior_recommendation,
        active_constraints={"exclusions": [], "tilts": [], "other": []},
        user_message="remove NVIDIA",
        turn_number=1,
    )

    assert "VTI" in prompt
    assert "NVDA" in prompt
    assert "remove NVIDIA" in prompt
    assert "Balanced" in prompt
    assert "Retirement" in prompt


def test_build_refinement_prompt_carries_prior_active_constraints():
    profile, goal, prior_recommendation = _base_args()

    prompt = build_refinement_prompt(
        profile=profile,
        goal=goal,
        goal_analysis=None,
        context_docs=[],
        default_allocation={"stocks": 60, "bonds": 40},
        prior_recommendation=prior_recommendation,
        active_constraints={"exclusions": ["remove NVIDIA"], "tilts": ["more bonds"], "other": []},
        user_message="also add some international exposure",
        turn_number=2,
    )

    assert "remove NVIDIA" in prompt
    assert "more bonds" in prompt
    assert "also add some international exposure" in prompt
