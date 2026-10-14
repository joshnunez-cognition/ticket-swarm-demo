import json
from wsgiref.simple_server import make_server

from .upload import UploadError, parse_manifest


def app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    if path == "/health":
        return _json(start_response, "200 OK", {"status": "ok"})
    if path == "/upload" and environ["REQUEST_METHOD"] == "POST":
        size = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ["wsgi.input"].read(size)
        try:
            manifest = parse_manifest(raw)
        except UploadError as exc:
            return _json(start_response, "400 Bad Request", {"error": str(exc)})
        return _json(start_response, "202 Accepted", {"accepted": manifest["document_type"]})
    return _json(start_response, "404 Not Found", {"error": "not found"})


def _json(start_response, status, body):
    start_response(status, [("Content-Type", "application/json")])
    return [json.dumps(body).encode()]


if __name__ == "__main__":
    make_server("0.0.0.0", 8081, app).serve_forever()
