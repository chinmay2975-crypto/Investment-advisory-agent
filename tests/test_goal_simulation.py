from datetime import datetime, timedelta

import pytest

from app.services.goal_simulation import apply_goal_simulation, classify_asset, simulate_goal


def goal(years=15, target=5_000_000, current=500_000, monthly=15_000):
    return {
        "target_amount": target,
        "current_amount": current,
        "target_date": datetime.now() + timedelta(days=round(365.25 * years)),
        "contribution_cadence": "monthly",
        "contribution_amount": monthly,
    }


@pytest.mark.parametrize(
    "name, asset",
    [
        ("Indian equity", "equity"), ("stocks", "equity"), ("Nifty 50 index fund", "equity"),
        ("Gilt funds", "bonds"), ("Debt", "bonds"), ("Gold ETF", "gold"), ("Cash", "cash"),
        ("REITs", "real_estate"), ("crypto", "other"),
    ],
)
def test_classify_asset(name, asset):
    assert classify_asset(name) == asset


def test_simulation_is_deterministic():
    alloc = {"stocks": 60, "bonds": 40}
    assert simulate_goal(alloc, goal()) == simulate_goal(alloc, goal())


def test_percent_and_fraction_weights_are_equivalent():
    assert simulate_goal({"stocks": 60, "bonds": 40}, goal()) == simulate_goal({"stocks": 0.6, "bonds": 0.4}, goal())


def test_risk_levels_give_different_probabilities_and_spreads():
    conservative = simulate_goal({"stocks": 30, "bonds": 70}, goal())
    aggressive = simulate_goal({"stocks": 90, "bonds": 10}, goal())
    assert conservative["probability"] != aggressive["probability"]
    assert aggressive["volatility"] > conservative["volatility"]
    assert aggressive["p90_final"] - aggressive["p10_final"] > conservative["p90_final"] - conservative["p10_final"]


def test_cash_only_matches_compound_growth_closely():
    # near-zero volatility: the median should be close to deterministic compounding of 3.5% + contributions
    result = simulate_goal({"cash": 100}, goal(years=10, target=1, current=100_000, monthly=0))
    assert result["probability"] == 1.0
    assert result["median_final"] == pytest.approx(100_000 * 1.035**10, rel=0.02)


def test_easy_and_impossible_goals():
    assert simulate_goal({"stocks": 60, "bonds": 40}, goal(target=1))["probability"] == 1.0
    assert simulate_goal({"stocks": 60, "bonds": 40}, goal(target=10**12))["probability"] == 0.0


def test_country_assumptions_change_the_result():
    alloc = {"equity": 70, "bonds": 30}
    assert simulate_goal(alloc, goal(), "IN")["expected_return"] > simulate_goal(alloc, goal(), "US")["expected_return"]


def test_unsimulatable_inputs_leave_payload_unchanged():
    payload = {"goal_probability": 0.7, "target_allocation": {"stocks": 60, "bonds": 40}}
    assert apply_goal_simulation(payload, None) == payload
    past = goal()
    past["target_date"] = datetime.now() - timedelta(days=10)
    assert apply_goal_simulation(payload, past) == payload
    assert apply_goal_simulation({**payload, "target_allocation": {}}, goal())["goal_probability"] == 0.7


def test_apply_keeps_llm_guess_for_reference():
    out = apply_goal_simulation({"goal_probability": 0.78, "target_allocation": {"stocks": 60, "bonds": 40}}, goal())
    assert out["goal_probability_method"] == "monte_carlo"
    assert out["llm_goal_probability"] == 0.78
    assert out["goal_probability"] == out["simulation"]["probability"]


def test_memory_stays_flat_for_long_horizons():
    import tracemalloc
    from datetime import datetime, timedelta

    goal = {"target_amount": 1e7, "current_amount": 1e5, "target_date": datetime.now() + timedelta(days=99 * 365),
            "contribution_cadence": "monthly", "contribution_amount": 1e4}
    tracemalloc.start()
    result = simulate_goal({"equity": 60, "bonds": 40}, goal, "IN")
    peak_mb = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()
    assert result["months"] > 1000
    assert peak_mb < 5  # a (months x paths) block would be ~48 MB


def test_absurd_horizon_is_not_simulated():
    from datetime import datetime

    assert simulate_goal({"equity": 100}, {"target_amount": 1, "target_date": datetime(9999, 1, 1)}) is None
