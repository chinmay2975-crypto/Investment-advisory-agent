import json
from pathlib import Path

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "data" / "allocation_templates.json"


def _load_templates() -> dict[str, dict[str, float]]:
    with open(_TEMPLATES_PATH) as f:
        return json.load(f)


_TEMPLATES = _load_templates()


def get_default_allocation(risk_cadence: str) -> dict[str, float]:
    try:
        return _TEMPLATES[risk_cadence]
    except KeyError:
        raise ValueError(
            f"No allocation template for risk cadence '{risk_cadence}'. "
            f"Known cadences: {list(_TEMPLATES)}"
        )
