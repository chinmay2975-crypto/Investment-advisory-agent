from datetime import datetime, timezone

from app.services.recommendation_engine import build_prompt


def test_build_prompt_includes_profile_goal_and_context():
    profile = {
        "risk_cadence": "Balanced",
        "horizon_years": 15,
        "preferences": {},
        "restrictions": {},
    }
    goal = {
        "category": "Retirement",
        "target_amount": 50000,
        "current_amount": 5000,
        "target_date": datetime(2041, 1, 1, tzinfo=timezone.utc),
        "contribution_cadence": "monthly",
        "contribution_amount": 200,
    }
    goal_analysis = {
        "required_annual_return": 0.0289,
        "is_sufficient": True,
        "projected_value": 72319.18,
        "assumed_annual_return": 0.07,
    }
    context_docs = [
        {
            "text": "Consumer Price Index was 334.13 as of 2026-08-01.",
            "metadata": {"category": "inflation", "source": "FRED", "as_of": "2026-08-01T00:00:00+00:00"},
        }
    ]
    default_allocation = {"stocks": 60, "bonds": 40}

    prompt = build_prompt(profile, goal, goal_analysis, context_docs, default_allocation)

    assert "Balanced" in prompt
    assert "Retirement" in prompt
    assert "50000" in prompt
    assert "0.0289" in prompt
    assert "Consumer Price Index" in prompt
    assert "FRED" in prompt
    assert "stocks" in prompt


def test_build_prompt_handles_missing_goal_analysis_and_context():
    profile = {"risk_cadence": "Conservative", "horizon_years": 5, "preferences": {}, "restrictions": {}}
    goal = {
        "category": "Home",
        "target_amount": 20000,
        "current_amount": 1000,
        "target_date": datetime(2031, 1, 1, tzinfo=timezone.utc),
        "contribution_cadence": None,
        "contribution_amount": None,
    }

    prompt = build_prompt(profile, goal, None, [], {"stocks": 40, "bonds": 60})

    assert "No contribution plan set" in prompt
    assert "No market context retrieved" in prompt
