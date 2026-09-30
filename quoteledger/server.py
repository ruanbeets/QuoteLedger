"""Local HTTP interface for QuoteLedger. Run with python3 -m quoteledger.server."""

import base64
import binascii
import csv
import io
import json
import mimetypes
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ai import enrich
from .comparison import compare, validate_fields
from .demo import seed
from .extraction import extract
from .storage import (connect, create_quote, create_request, get_pdf, get_quote,
                      get_request, list_quotes, list_requests, update_quote)

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 10 * 1024 * 1024


def pdf_text(data):
    if not data.startswith(b"%PDF-"):
        raise ValueError("The uploaded file is not a PDF")
    try:
        proc = subprocess.run(["pdftotext", "-layout", "-", "-"], input=data,
                              capture_output=True, timeout=20, check=False)
    except FileNotFoundError as exc:
        raise ValueError("PDF extraction needs the system pdftotext utility") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("PDF extraction timed out") from exc
    if proc.returncode:
        raise ValueError("PDF text could not be extracted")
    text = proc.stdout.decode("utf-8", "replace").strip()
    if not text:
        raise ValueError("No selectable text found in this PDF; run OCR first")
    return text


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def send(self, status, payload, content_type="application/json; charset=utf-8"):
        data = json.dumps(payload).encode() if content_type.startswith("application/json") else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size < 1 or size > MAX_BODY:
            raise ValueError("Request body must be between 1 byte and 10 MB")
        try:
            data = json.loads(self.rfile.read(size))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be an object")
        return data

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/requests":
            with connect() as db:
                self.send(200, {"requests": list_requests(db)})
            return
        matched = re.fullmatch(r"/api/requests/(\d+)", path)
        if matched:
            with connect() as db:
                request = get_request(db, int(matched[1]))
                if request:
                    quotes = list_quotes(db, request["id"])
                    self.send(200, {"request": request, "quotes": quotes,
                                    "comparison": compare(request, quotes)})
                else:
                    self.send(404, {"error": "Request not found"})
            return
        matched = re.fullmatch(r"/api/requests/(\d+)/export.csv", path)
        if matched:
            with connect() as db:
                request = get_request(db, int(matched[1]))
                if not request:
                    self.send(404, {"error": "Request not found"})
                    return
                quotes = list_quotes(db, request["id"])
                rows = {row["quote_id"]: row for row in compare(request, quotes)}
                output = io.StringIO()
                columns = ["request", "specification", "requested_boxes", "supplier", "product",
                           "source_file", "review_status", "currency", "quoted_price", "price_unit",
                           "pack_size", "moq_boxes", "order_boxes", "transport_cost", "fx_to_zar",
                           "fx_source", "unit_price_zar", "landed_total_zar", "effective_per_requested_box_zar",
                           "lead_days", "payment_terms", "valid_until", "exceptions", "buyer_checks"]
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                for quote in quotes:
                    f, row = quote["fields"], rows[quote["id"]]
                    writer.writerow(dict(request=request["name"], specification=request["specification"],
                        requested_boxes=request["quantity"], supplier=f["supplier"], product=f["product"],
                        source_file=quote["filename"], review_status=quote["status"], currency=f["currency"],
                        quoted_price=f["unit_price"], price_unit=f["price_unit"], pack_size=f["pack_size"],
                        moq_boxes=f["moq"], order_boxes=row["order_quantity"], transport_cost=f["transport_cost"],
                        fx_to_zar=f["fx_to_zar"], fx_source=f["fx_source"], unit_price_zar=row.get("unit_price_zar", ""),
                        landed_total_zar=row.get("landed_total_zar", ""),
                        effective_per_requested_box_zar=row.get("effective_per_requested_box_zar", ""),
                        lead_days=f["lead_days"], payment_terms=f["payment_terms"], valid_until=f["valid_until"],
                        exceptions=f["exceptions"], buyer_checks="; ".join(row["issues"])))
                self.send(200, output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")
            return
        matched = re.fullmatch(r"/api/quotes/(\d+)/source.pdf", path)
        if matched:
            with connect() as db:
                data = get_pdf(db, int(matched[1]))
                if data:
                    self.send(200, data, "application/pdf")
                else:
                    self.send(404, {"error": "PDF not found"})
            return
        name = "index.html" if path == "/" else path.removeprefix("/")
        if name in {"index.html", "app.js", "styles.css"}:
            data = (STATIC / name).read_bytes()
            self.send(200, data, mimetypes.guess_type(name)[0] or "application/octet-stream")
        else:
            self.send(404, {"error": "Not found"})

    def do_POST(self):
        try:
            data = self.read_json()
            path = self.path.split("?", 1)[0]
            if path == "/api/requests":
                name = str(data.get("name", "")).strip()
                specification = str(data.get("specification", "")).strip()
                quantity = int(data.get("quantity", 0))
                if not name or quantity < 1 or quantity > 10_000_000:
                    raise ValueError("Enter a request name and quantity between 1 and 10,000,000")
                with connect() as db:
                    self.send(201, create_request(db, name, specification, quantity))
                return
            matched = re.fullmatch(r"/api/requests/(\d+)/quotes", path)
            if not matched:
                self.send(404, {"error": "Not found"})
                return
            request_id = int(matched[1])
            filename = str(data.get("filename", "")).strip()[:200]
            source = str(data.get("text", "")).strip()
            pdf = None
            if data.get("pdf_base64"):
                try:
                    pdf = base64.b64decode(data["pdf_base64"], validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ValueError("Invalid PDF upload") from exc
                if len(pdf) > 7 * 1024 * 1024:
                    raise ValueError("PDF must be 7 MB or smaller")
                source = pdf_text(pdf)
                filename = filename or "quote.pdf"
            if not source or len(source) > 150_000:
                raise ValueError("Quote text must be between 1 and 150,000 characters")
            fields, evidence = extract(source)
            fields, evidence = enrich(source, fields, evidence)
            with connect() as db:
                if not get_request(db, request_id):
                    self.send(404, {"error": "Request not found"})
                else:
                    self.send(201, create_quote(db, request_id, filename, source, pdf, fields, evidence))
        except (ValueError, TypeError) as exc:
            self.send(400, {"error": str(exc)})

    def do_PUT(self):
        try:
            data = self.read_json()
            matched = re.fullmatch(r"/api/quotes/(\d+)", self.path.split("?", 1)[0])
            if not matched:
                self.send(404, {"error": "Not found"})
                return
            fields = validate_fields(data.get("fields"))
            status = data.get("status", "needs_review")
            if status not in {"needs_review", "reviewed"}:
                raise ValueError("Invalid review status")
            if status == "reviewed" and not fields["supplier"]:
                raise ValueError("Supplier is required before marking reviewed")
            with connect() as db:
                if not get_quote(db, int(matched[1])):
                    self.send(404, {"error": "Quote not found"})
                else:
                    self.send(200, update_quote(db, int(matched[1]), fields, status))
        except (ValueError, TypeError) as exc:
            self.send(400, {"error": str(exc)})


def main():
    with connect() as db:
        seed(db)
    host = os.environ.get("QUOTELEDGER_HOST", "127.0.0.1")
    port = int(os.environ.get("QUOTELEDGER_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"QuoteLedger running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
