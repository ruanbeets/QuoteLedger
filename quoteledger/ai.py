"""Optional Ollama extraction adapter. Suggestions always require buyer review."""

import json
import os
import urllib.error
import urllib.request

from .comparison import validate_fields
from .extraction import FIELDS


def enrich(text, fields, evidence):
    base_url = os.environ.get("QUOTELEDGER_OLLAMA_URL", "").rstrip("/")
    if not base_url:
        evidence["_engine"] = "rules"
        return fields, evidence

    model = os.environ.get("QUOTELEDGER_OLLAMA_MODEL", "qwen3:4b")
    schema = {"type": "object", "properties": {
        "fields": {"type": "object", "properties": {key: {"type": "string"} for key in FIELDS},
                   "required": list(FIELDS), "additionalProperties": False},
        "evidence": {"type": "object", "properties": {key: {"type": "string"} for key in FIELDS},
                     "required": list(FIELDS), "additionalProperties": False}},
              "required": ["fields", "evidence"], "additionalProperties": False}
    prompt = ("Extract packaging supplier quote fields. Return empty strings for absent or unclear values. "
              "For every nonempty value, give the exact source line in evidence. "
              "Use ZAR, USD, EUR or GBP for currency. price_unit is each, pack, 100 or 1000. "
              "All quantities and days must be plain numbers. MOQ is in boxes, not packs. "
              "Do not invent transport, exchange rates, dates or terms.\n\nQUOTE:\n" + text[:12000])
    payload = {"model": model, "prompt": prompt, "format": schema, "stream": False,
               "options": {"temperature": 0}}
    request = urllib.request.Request(base_url + "/api/generate", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(json.loads(response.read())["response"])
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        evidence["_engine"] = "rules; model unavailable"
        return fields, evidence

    suggestions = result.get("fields", {})
    source_lines = result.get("evidence", {})
    if not isinstance(suggestions, dict) or not isinstance(source_lines, dict):
        evidence["_engine"] = "rules; invalid model result"
        return fields, evidence
    lines = {line.strip().casefold() for line in text.splitlines() if line.strip()}
    for key in FIELDS:
        if fields[key]:
            continue
        value = suggestions.get(key, "")
        source = source_lines.get(key, "")
        if not isinstance(value, str) or not isinstance(source, str) or not value.strip():
            continue
        if source.strip().casefold() not in lines:
            continue
        candidate = {**fields, key: value.strip()}
        try:
            validate_fields(candidate)
        except ValueError:
            continue
        fields[key] = value.strip()
        evidence[key] = source.strip()[:240]
    evidence["_engine"] = f"rules + Ollama {model}"
    return fields, evidence
