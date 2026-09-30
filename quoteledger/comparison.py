"""Explicit, auditable packaging quote calculations."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

ALLOWED_UNITS = {"each": 1, "pack": None, "100": 100, "1000": 1000}
CURRENCIES = {"ZAR", "USD", "EUR", "GBP"}


def number(value, label, *, allow_zero=True):
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value).replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise ValueError(f"{label} must be positive" if not allow_zero else f"{label} cannot be negative")
    return result


def validate_fields(fields):
    if not isinstance(fields, dict):
        raise ValueError("Quote fields must be an object")
    clean = {k: str(fields.get(k, "") or "").strip() for k in (
        "supplier", "product", "currency", "unit_price", "price_unit", "pack_size",
        "moq", "lead_days", "transport_cost", "payment_terms", "exceptions",
        "fx_to_zar", "fx_source", "valid_until")}
    if clean["currency"] and clean["currency"] not in CURRENCIES:
        raise ValueError("Currency must be ZAR, USD, EUR or GBP")
    if clean["price_unit"] and clean["price_unit"] not in ALLOWED_UNITS:
        raise ValueError("Price unit must be each, pack, 100 or 1000")
    for key in ("unit_price", "transport_cost", "fx_to_zar"):
        number(clean[key], key, allow_zero=key == "transport_cost")
    for key in ("pack_size", "moq", "lead_days"):
        value = number(clean[key], key, allow_zero=key == "lead_days")
        if value is not None and value != value.to_integral_value():
            raise ValueError(f"{key} must be a whole number")
    return clean


def money(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def evaluate(request, quote):
    f = quote["fields"]
    issues = []
    required = ("supplier", "product", "currency", "unit_price", "price_unit", "moq", "lead_days", "payment_terms")
    issues.extend(f"Missing {key.replace('_', ' ')}" for key in required if not f.get(key))
    if f.get("price_unit") == "pack" and not f.get("pack_size"):
        issues.append("Missing pack size")
    if f.get("currency") and f["currency"] != "ZAR" and (not f.get("fx_to_zar") or not f.get("fx_source")):
        issues.append("Exchange rate and source required")
    if not f.get("transport_cost"):
        issues.append("Transport cost unconfirmed")
    if f.get("exceptions"):
        issues.append("Supplier exceptions noted")
    moq = number(f.get("moq"), "moq")
    quantity = Decimal(request["quantity"])
    order_quantity = max(quantity, moq or quantity)
    if f.get("price_unit") == "pack" and f.get("pack_size"):
        pack_size = Decimal(f["pack_size"])
        order_quantity = (order_quantity / pack_size).to_integral_value(rounding=ROUND_CEILING) * pack_size
        if order_quantity > max(quantity, moq or quantity):
            issues.append("Order rounded up to full packs")
    if moq and moq > quantity:
        issues.append(f"MOQ exceeds request by {int(moq - quantity)} boxes")
    unit = f.get("price_unit")
    divisor = Decimal(f["pack_size"]) if unit == "pack" and f.get("pack_size") else Decimal(ALLOWED_UNITS[unit]) if unit in ALLOWED_UNITS and unit != "pack" else None
    price = number(f.get("unit_price"), "unit_price")
    currency = f.get("currency")
    fx = Decimal("1") if currency == "ZAR" else number(f.get("fx_to_zar"), "fx_to_zar", allow_zero=False)
    transport = number(f.get("transport_cost"), "transport_cost")
    comparable = bool(price is not None and divisor and fx and transport is not None and currency
                      and f.get("moq") and f.get("lead_days") and f.get("payment_terms") and f.get("product")
                      and (currency == "ZAR" or f.get("fx_source")))
    result = {"quote_id": quote["id"], "supplier": f.get("supplier") or "Unnamed supplier",
              "status": quote["status"], "issues": issues, "comparable": comparable,
              "order_quantity": int(order_quantity), "lead_days": f.get("lead_days") or None,
              "payment_terms": f.get("payment_terms") or None, "currency": currency}
    if comparable:
        per_box = price / divisor * fx
        total = per_box * order_quantity + transport * fx
        result.update(unit_price_zar=money(per_box), landed_total_zar=money(total),
                      effective_per_requested_box_zar=money(total / quantity))
    return result


def compare(request, quotes):
    rows = [evaluate(request, q) for q in quotes]
    ranked = sorted((r for r in rows if r["comparable"] and r["status"] == "reviewed"),
                    key=lambda r: Decimal(r["landed_total_zar"]))
    winner = ranked[0]["quote_id"] if ranked else None
    for row in rows:
        row["lowest_reviewed"] = row["quote_id"] == winner
    return rows
