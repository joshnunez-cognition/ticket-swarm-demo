import os

BUCKET = os.environ.get("DOCS_BUCKET", "demo-health-member-docs")


def object_key(member_ref: str, document_type: str, filename: str) -> str:
    return f"members/{member_ref}/{document_type}/{filename}"


def put_document(client, member_ref: str, document_type: str, filename: str, body: bytes) -> str:
    key = object_key(member_ref, document_type, filename)
    client.put_object(Bucket=BUCKET, Key=key, Body=body)
    return key
