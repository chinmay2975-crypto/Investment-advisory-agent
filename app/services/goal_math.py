"""Deterministic goal-planning math: no LLM, no DB — pure functions over plain numbers."""


def project_future_value(
    current_amount: float,
    contribution_per_period: float,
    annual_return: float,
    years: float,
    periods_per_year: int,
) -> float:
    """Future value of a lump sum plus periodic contributions (ordinary annuity)."""
    n = years * periods_per_year
    r = annual_return / periods_per_year

    if r == 0:
        return current_amount + contribution_per_period * n

    growth = (1 + r) ** n
    return current_amount * growth + contribution_per_period * ((growth - 1) / r)


def is_contribution_sufficient(
    target_amount: float,
    current_amount: float,
    years: float,
    contribution_per_period: float,
    periods_per_year: int,
    assumed_return: float,
) -> bool:
    """Whether the planned contributions reach the target at the assumed rate of return."""
    projected = project_future_value(
        current_amount, contribution_per_period, assumed_return, years, periods_per_year
    )
    return projected >= target_amount


def required_annual_return(
    target_amount: float,
    current_amount: float,
    years: float,
    contribution_per_period: float,
    periods_per_year: int,
    tolerance: float = 1e-6,
    max_iterations: int = 200,
) -> float:
    """The annual return needed so current savings + contributions reach target_amount by years.

    Solved numerically via bisection since the future-value formula isn't
    invertible in closed form once periodic contributions are involved.
    Returns None if the target is unreachable even at extreme high returns
    (e.g. current_amount + total contributions already exceeds the target,
    in which case any non-negative return works — this returns 0.0 instead).
    """
    def fv_at(rate: float) -> float:
        return project_future_value(
            current_amount, contribution_per_period, rate, years, periods_per_year
        )

    if fv_at(0.0) >= target_amount:
        return 0.0

    low, high = 0.0, 1.0
    while fv_at(high) < target_amount:
        high *= 2
        if high > 1000:
            raise ValueError("Target unreachable within a plausible return range")

    for _ in range(max_iterations):
        mid = (low + high) / 2
        if abs(fv_at(mid) - target_amount) < tolerance:
            return mid
        if fv_at(mid) < target_amount:
            low = mid
        else:
            high = mid

    return (low + high) / 2
