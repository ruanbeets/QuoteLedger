# QuoteLedger

QuoteLedger is a working procurement quote comparison prototype for buyers of corrugated packaging. It turns supplier PDFs or pasted quote text into a reviewable comparison, normalizes pack prices to a price per box, and records the inputs behind each decision.

## Run

Requires Python 3.11+ and `pdftotext` (Poppler) for PDF uploads. No Python packages are required.

```bash
python3 -m quoteledger.server
```

Open <http://127.0.0.1:8000>. The first launch creates a sample request with three quotes. Data is stored in `instance/quoteledger.sqlite3` (ignored by Git).

Or use Docker Compose:

```bash
docker compose up --build -d
```

The app is available at <http://127.0.0.1:8000>. SQLite data persists in the `quoteledger_data` Docker volume. `docker compose down` stops the service without deleting the volume.

## Workflow

1. Create a packaging purchase request with a required number of boxes.
2. Add a supplier quote by uploading a text-based PDF/TXT or pasting its text.
3. Review and correct the extracted fields. Keep the source document/text attached for audit.
4. Enter an explicit ZAR exchange rate for any non-ZAR quote. Rates are never assumed or fetched silently.
5. Compare landed cost at the requested quantity and export the comparison as CSV. The comparison highlights missing terms, MOQs, lead times and exceptions.

The parser is deliberately conservative: it suggests fields from common quote wording and leaves ambiguous terms blank. A scanned PDF needs OCR before upload. No purchase order is issued and no supplier is contacted.

### Optional local AI extraction

Set `QUOTELEDGER_OLLAMA_URL` to an Ollama server URL to enable a second extraction pass. It fills only fields missed by the rule parser and only when the model supplies an exact source line. The model result still needs buyer review. For example:

```bash
QUOTELEDGER_OLLAMA_URL=http://127.0.0.1:11434 QUOTELEDGER_OLLAMA_MODEL=qwen3:4b python3 -m quoteledger.server
```

For Docker, set `QUOTELEDGER_OLLAMA_URL` and `QUOTELEDGER_OLLAMA_MODEL` in `compose.yaml` under `environment`, using a URL reachable from the container. The default container runs without an Ollama dependency. Quote text is sent to the configured Ollama endpoint; choose a local endpoint if the documents must stay on your machine. This adapter uses Ollama's [generate API](https://docs.ollama.com/api/generate) with [structured JSON output](https://docs.ollama.com/capabilities/structured-outputs).

## Scope and growth path

The prototype serves one buyer on a local machine. Its data and calculation layers are separate from the HTTP interface (`quoteledger/storage.py`, `quoteledger/comparison.py`, `quoteledger/extraction.py`). The next production steps are organization accounts and permissions, object storage for original documents, asynchronous OCR and model assisted extraction with evidence spans, approved exchange rate sources, supplier email ingestion, and audit event storage. Keep a human review gate before comparisons are treated as purchase decisions.

`legacy/` contains the previous DataCo supply chain analysis. It is unrelated to QuoteLedger and is retained only as historical work.

## Check

```bash
python3 -m unittest discover -s tests -v
```
