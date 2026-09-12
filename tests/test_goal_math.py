import pytest

from app.services import goal_math


def test_project_future_value_no_contributions():
    fv = goal_math.project_future_value(
        current_amount=10000, contribution_per_period=0, annual_return=0.10, years=1, periods_per_year=1
    )
    assert fv == pytest.approx(11000, rel=1e-6)


def test_project_future_value_zero_return():
    fv = goal_math.project_future_value(
        current_amount=1000, contribution_per_period=100, annual_return=0.0, years=2, periods_per_year=12
    )
    assert fv == pytest.approx(1000 + 100 * 24, rel=1e-6)


def test_is_contribution_sufficient_true():
    assert goal_math.is_contribution_sufficient(
        target_amount=10000,
        current_amount=0,
        years=10,
        contribution_per_period=100,
        periods_per_year=12,
        assumed_return=0.07,
    )


def test_is_contribution_sufficient_false():
    assert not goal_math.is_contribution_sufficient(
        target_amount=1_000_000,
        current_amount=0,
        years=1,
        contribution_per_period=10,
        periods_per_year=12,
        assumed_return=0.05,
    )


def test_required_annual_return_matches_projection():
    kwargs = dict(
        target_amount=50000,
        current_amount=5000,
        years=15,
        contribution_per_period=200,
        periods_per_year=12,
    )
    rate = goal_math.required_annual_return(**kwargs)
    projected = goal_math.project_future_value(
        current_amount=kwargs["current_amount"],
        contribution_per_period=kwargs["contribution_per_period"],
        annual_return=rate,
        years=kwargs["years"],
        periods_per_year=kwargs["periods_per_year"],
    )
    assert projected == pytest.approx(kwargs["target_amount"], rel=1e-4)


def test_required_annual_return_already_met():
    rate = goal_math.required_annual_return(
        target_amount=1000,
        current_amount=5000,
        years=5,
        contribution_per_period=0,
        periods_per_year=12,
    )
    assert rate == 0.0
