from __future__ import annotations

from pathlib import Path

import pytest

from apps.ares.ares.data.models import Customer, Order, OrderItem
from apps.ares.ares.profiles import ClientProfile, load_client_profile, write_client_profile


def test_business_models_json_serialize() -> None:
    order = Order(
        id="ord_1",
        customer_id="cust_1",
        items=[OrderItem(sku_id="surf", name="Surf", quantity=20, unit="carton")],
    )

    payload = order.model_dump_json()

    assert "ord_1" in payload
    assert "Surf" in payload


def test_all_required_customer_fields_are_explicit() -> None:
    customer = Customer(id="cust_1", name="Raj Traders")

    assert customer.status == "active"
    assert customer.aliases == []


def test_client_profile_round_trip_isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    profile = ClientProfile(
        client_slug="demo-wholesale",
        business_name="Demo Wholesale",
        owner_name="Owner",
    )

    path = write_client_profile(profile)
    loaded = load_client_profile("demo-wholesale")

    assert path == tmp_path / ".ares" / "clients" / "demo-wholesale" / "profile.yaml"
    assert loaded.business_name == "Demo Wholesale"
    assert (path.parent / "memory").is_dir()
    assert (path.parent / "approvals").is_dir()


def test_invalid_profile_reports_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    profile_dir = tmp_path / ".ares" / "clients" / "bad-client"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.yaml").write_text("client_slug: bad-client\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Ares client profile"):
        load_client_profile("bad-client")

