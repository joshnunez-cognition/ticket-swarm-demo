import yaml

REQUIRED_FIELDS = ("document_type", "member_ref", "pages")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class UploadError(ValueError):
    pass


def parse_manifest(raw: bytes) -> dict:
    """Parse the YAML manifest that accompanies every document upload."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise UploadError("manifest too large")
    try:
        manifest = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise UploadError("invalid manifest") from exc
    if not isinstance(manifest, dict):
        raise UploadError("manifest must be a mapping")
    missing = [f for f in REQUIRED_FIELDS if f not in manifest]
    if missing:
        raise UploadError(f"missing fields: {', '.join(missing)}")
    return manifest
