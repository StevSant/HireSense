import io
import zipfile

import pytest

from hiresense.network.domain import ConnectionsParseError, parse_connections

_HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"
_ROWS = (
    'Jordan,Lee,https://www.linkedin.com/in/jlee,,Acme Inc.,Engineering Manager,01 Feb 2025\n'
    'Sam,Diaz,,sam@x.dev,Globant S.A.,Recruiter,15 Mar 2024\n'
    ',,,,,,\n'  # fully empty row is skipped
)
_PREAMBLE = (
    '"Notes:\nWhen exporting your connection data, you may notice missing emails."\n\n'
)


def _csv_bytes(*, preamble: bool) -> bytes:
    return ((_PREAMBLE if preamble else "") + _HEADER + "\n" + _ROWS).encode("utf-8")


def test_parses_plain_csv_with_preamble() -> None:
    contacts = parse_connections(_csv_bytes(preamble=True), filename="Connections.csv")
    assert len(contacts) == 2
    assert contacts[0].first_name == "Jordan"
    assert contacts[0].company_normalized == "acme"
    assert contacts[1].email == "sam@x.dev"
    assert contacts[1].connected_on == "15 Mar 2024"


def test_parses_csv_without_preamble() -> None:
    assert len(parse_connections(_csv_bytes(preamble=False), filename="x.csv")) == 2


def test_parses_zip_export() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Basic_LinkedInDataExport/Connections.csv", _csv_bytes(preamble=True))
        archive.writestr("Basic_LinkedInDataExport/Skills.csv", "Name\nPython\n")
    contacts = parse_connections(buffer.getvalue(), filename="export.zip")
    assert len(contacts) == 2


def test_zip_without_connections_raises() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Skills.csv", "Name\nPython\n")
    with pytest.raises(ConnectionsParseError, match="Connections.csv"):
        parse_connections(buffer.getvalue(), filename="export.zip")


def test_csv_without_header_raises() -> None:
    with pytest.raises(ConnectionsParseError, match="header"):
        parse_connections(b"not,a,connections,file\n1,2,3,4\n", filename="x.csv")


def test_zip_member_decompression_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hiresense.network.domain.connections_parser._MAX_MEMBER_BYTES", 64
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Connections.csv", _HEADER + "\n" + "a,b,,,c,d,e\n" * 100)
    with pytest.raises(ConnectionsParseError, match="decompresses beyond"):
        parse_connections(buffer.getvalue(), filename="export.zip")
