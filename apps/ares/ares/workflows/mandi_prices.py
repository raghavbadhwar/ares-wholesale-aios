"""Local Agmarknet price placeholder."""

from __future__ import annotations


def fetch_agmarknet_prices(*, commodity: str, state: str | None = None) -> dict:
    return {
        "mode": "local_simulation",
        "commodity": commodity,
        "state": state,
        "agmarknet_api_called": False,
        "price_snapshots": [],
        "records_returned": 0,
        "limitation": "Local simulation only; no Agmarknet API key or live call used.",
    }
