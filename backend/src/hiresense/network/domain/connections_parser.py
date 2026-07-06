from __future__ import annotations

import csv
import io
import zipfile

from hiresense.network.domain.contact import Contact

_EXPECTED_COLUMNS = {"First Name", "Last Name", "Company", "Position"}
_ZIP_MAGIC = b"PK\x03\x04"


class ConnectionsParseError(ValueError):
    """Raised when the upload is not a parseable LinkedIn connections export."""


def parse_connections(payload: bytes, *, filename: str) -> list[Contact]:
    """Parse LinkedIn `Connections.csv` content — given directly or inside the
    data-export ZIP. Tolerates LinkedIn's "Notes:" preamble before the header."""
    if payload.startswith(_ZIP_MAGIC):
        payload = _extract_connections_member(payload)
    return _parse_csv(payload)


# Decompressed-size ceiling for the Connections.csv member. The route caps
# the COMPRESSED upload; a crafted ZIP could still expand enormously in
# memory without this gate (zip bomb). Real LinkedIn exports are far smaller.
_MAX_MEMBER_BYTES = 50 * 1024 * 1024


def _extract_connections_member(payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            if name.rsplit("/", 1)[-1].lower() == "connections.csv":
                info = archive.getinfo(name)
                if info.file_size > _MAX_MEMBER_BYTES:
                    raise ConnectionsParseError(
                        "Connections.csv decompresses beyond the allowed size"
                    )
                return archive.read(name)
    raise ConnectionsParseError("ZIP does not contain a Connections.csv")


def _parse_csv(payload: bytes) -> list[Contact]:
    text = payload.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("First Name,")), None)
    if header_index is None:
        raise ConnectionsParseError("No connections header row found")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    if not _EXPECTED_COLUMNS.issubset(set(reader.fieldnames or [])):
        raise ConnectionsParseError("Connections header is missing expected columns")
    contacts: list[Contact] = []
    for row in reader:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        if not first and not last:
            continue  # blank padding rows in real exports
        contacts.append(
            Contact(
                first_name=first,
                last_name=last,
                company=(row.get("Company") or "").strip(),
                position=(row.get("Position") or "").strip(),
                linkedin_url=(row.get("URL") or "").strip() or None,
                email=(row.get("Email Address") or "").strip() or None,
                connected_on=(row.get("Connected On") or "").strip() or None,
            )
        )
    return contacts
