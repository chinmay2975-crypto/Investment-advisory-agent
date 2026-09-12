import pytest

from app.services.allocation import get_default_allocation


@pytest.mark.parametrize("cadence", ["Conservative", "Balanced", "Aggressive"])
def test_known_cadences_sum_to_100(cadence):
    allocation = get_default_allocation(cadence)
    assert sum(allocation.values()) == 100


def test_unknown_cadence_raises():
    with pytest.raises(ValueError):
        get_default_allocation("NotARealCadence")
