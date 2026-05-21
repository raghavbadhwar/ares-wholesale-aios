"""GST invoice draft generation for approved Ares orders."""

from __future__ import annotations

from apps.ares.ares.data.models import Customer, Order, ProductSKU
from apps.ares.ares.data.repository import BusinessRepository

DEFAULT_GST_RATE = 0.18


def _find_customer(repository: BusinessRepository, customer_id: str | None) -> Customer | None:
    if not customer_id:
        return None
    for customer in repository.get_customers():
        if customer.id == customer_id:
            return customer
    return None


def _find_product(repository: BusinessRepository, sku_id: str | None, item_name: str) -> ProductSKU | None:
    normalized_name = item_name.strip().lower()
    for product in repository.get_products():
        if sku_id and product.id == sku_id:
            return product
        names = [product.name, *product.aliases]
        if any(name.strip().lower() == normalized_name for name in names if name):
            return product
    return None


def _state_code_from_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    gstin = gstin.strip()
    return gstin[:2] if len(gstin) >= 2 else None


def draft_gst_invoice(order: Order, repository: BusinessRepository, *, seller_gstin: str, seller_state_code: str) -> dict:
    customer = _find_customer(repository, order.customer_id)
    errors: list[str] = []
    lines: list[dict] = []

    if not seller_gstin:
        errors.append("seller_gstin_missing")
    customer_gstin = customer.gstin if customer else None
    if not customer_gstin:
        errors.append("customer_gstin_missing")

    taxable_value = 0.0
    for item in order.items:
        product = _find_product(repository, item.sku_id, item.name)
        if product is None or product.selling_price is None:
            identifier = item.sku_id or item.name
            errors.append(f"missing_selling_price:{identifier}")
            continue
        unit_price = float(product.selling_price)
        line_total = round(item.quantity * unit_price, 2)
        taxable_value += line_total
        lines.append(
            {
                "sku_id": product.id,
                "name": product.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": unit_price,
                "line_total": line_total,
                "gst_rate": DEFAULT_GST_RATE,
            }
        )

    customer_state_code = _state_code_from_gstin(customer_gstin)
    tax_mode = "intra_state" if customer_state_code == seller_state_code else "inter_state"
    tax_amount = round(taxable_value * DEFAULT_GST_RATE, 2)
    if tax_mode == "intra_state":
        cgst = round(tax_amount / 2, 2)
        sgst = round(tax_amount / 2, 2)
        igst = 0.0
    else:
        cgst = 0.0
        sgst = 0.0
        igst = tax_amount

    grand_total = round(taxable_value + tax_amount, 2)
    return {
        "ok": len(errors) == 0,
        "order_id": order.id,
        "customer_id": order.customer_id,
        "customer_gstin": customer_gstin,
        "seller_gstin": seller_gstin,
        "seller_state_code": seller_state_code,
        "tax_mode": tax_mode,
        "validation_errors": errors,
        "lines": lines,
        "totals": {
            "taxable_value": round(taxable_value, 2),
            "tax_amount": tax_amount,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "grand_total": grand_total,
        },
    }
