"""Conservative field suggestions with source snippets for buyer review."""

import re

FIELDS = ("supplier", "product", "currency", "unit_price", "price_unit", "pack_size",
          "moq", "lead_days", "transport_cost", "payment_terms", "exceptions",
          "fx_to_zar", "fx_source", "valid_until")


def extract(text):
    fields = {key: "" for key in FIELDS}
    evidence = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    def match(field, patterns, transform=None):
        for line in lines:
            for pattern in patterns:
                found = re.search(pattern, line, re.I)
                if found:
                    value = found.group(1).strip(" .:;")
                    fields[field] = transform(value) if transform else value
                    evidence[field] = line[:240]
                    return

    match("supplier", [r"^(?:supplier|vendor|quoted by|from)\s*[:\-]\s*(.+)$"])
    match("product", [r"^(?:product|item|description|specification)\s*[:\-]\s*(.+)$"])
    match("currency", [r"\b(ZAR|USD|EUR|GBP)\b", r"(R)\s*[\d,]+(?:\.\d+)?"],
          lambda v: "ZAR" if v.upper() == "R" else v.upper())
    match("unit_price", [r"^(?:unit price|price per (?:box|each|pack|100|1000)|price)\s*[:\-]\s*(?:R|ZAR|USD|EUR|GBP|\$|€|£)?\s*([\d,]+(?:\.\d{1,2})?)\b"])
    match("price_unit", [r"^(?:price unit|unit of measure|priced per)\s*[:\-]\s*(each|pack|1000|100)\b",
                         r"^price per\s+(box|each|pack|1000|100)\s*[:\-]"],
          lambda v: "each" if v.lower() == "box" else v.lower())
    match("pack_size", [r"^(?:pack size|boxes per pack)\s*[:\-]\s*(\d+)\b"])
    match("moq", [r"^(?:moq|minimum order(?: quantity)?)\s*[:\-]\s*(\d+)\b"])
    match("lead_days", [r"^(?:lead time|delivery time)\s*[:\-]\s*(\d+)\s*(?:working |business |calendar )?days?\b"])
    match("transport_cost", [r"^(?:transport|delivery|freight|shipping)(?: cost| charge)?\s*[:\-]\s*(?:R|ZAR|USD|EUR|GBP|\$|€|£)?\s*([\d,]+(?:\.\d{1,2})?)\b"])
    match("payment_terms", [r"^(?:payment terms|payment)\s*[:\-]\s*(.+)$"])
    match("exceptions", [r"^(?:exceptions|exclusions|notes)\s*[:\-]\s*(.+)$"])
    match("valid_until", [r"^(?:valid until|quote valid until|validity)\s*[:\-]\s*(.+)$"])
    return fields, evidence
