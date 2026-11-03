from app.countries.base import CountryConfig
from app.countries.india import INDIA
from app.countries.united_kingdom import UNITED_KINGDOM
from app.countries.united_states import UNITED_STATES

# The single place a new country gets registered.
_COUNTRIES: dict[str, CountryConfig] = {c.code: c for c in (INDIA, UNITED_STATES, UNITED_KINGDOM)}
_ALIASES: dict[str, str] = {alias: c.code for c in _COUNTRIES.values() for alias in c.aliases}


class UnknownCountryError(ValueError):
    pass


def list_countries() -> list[CountryConfig]:
    return list(_COUNTRIES.values())


def normalize_country_code(code: str) -> str:
    upper = code.strip().upper()
    resolved = _ALIASES.get(upper, upper)
    if resolved not in _COUNTRIES:
        raise UnknownCountryError(
            f"Unsupported country '{code}'. Supported: {sorted(_COUNTRIES)} (alias: UK -> GB)"
        )
    return resolved


def get_country(code: str) -> CountryConfig:
    return _COUNTRIES[normalize_country_code(code)]
