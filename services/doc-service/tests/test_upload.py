import io
import json

import pytest

from doc_service.app import app
from doc_service.storage import object_key
from doc_service.upload import UploadError, parse_manifest

VALID = b"document_type: eob\nmember_ref: m-100\npages: 2\n"


def test_parse_valid_manifest():
    assert parse_manifest(VALID)["pages"] == 2


def test_missing_fields_rejected():
    with pytest.raises(UploadError):
        parse_manifest(b"document_type: eob\n")


def test_object_key_layout():
    assert object_key("m-100", "eob", "a.pdf") == "members/m-100/eob/a.pdf"


def test_upload_endpoint_accepts_manifest():
    environ = {
        "PATH_INFO": "/upload",
        "REQUEST_METHOD": "POST",
        "CONTENT_LENGTH": str(len(VALID)),
        "wsgi.input": io.BytesIO(VALID),
    }
    status = {}
    body = app(environ, lambda s, h: status.setdefault("s", s))
    assert status["s"].startswith("202")
    assert json.loads(body[0]) == {"accepted": "eob"}
