"""Import the Phase 5.8 blind Excel workbook into canonical evaluator CSVs.

The received workbook is treated as immutable research data. This importer
reads the OpenXML package with the Python standard library and writes one CSV
per syllabus in the format consumed by ``aggregate_human_judgment.py``.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

import typer


CRITERIA = tuple(f"C{i}" for i in range(1, 10))
EXPECTED_HEADERS = (
    "Criterio",
    "Nome criterio",
    "Cosa valuta",
    "Guida al punteggio (0 / 1 / 2)",
    "Punteggio",
    "Motivo (solo se NA)",
    "Motivazione (1-3 frasi)",
    "Citazione dal syllabus",
)
CSV_HEADERS = (
    "criterion",
    "name",
    "summary",
    "anchor_0",
    "anchor_1",
    "anchor_2",
    "human_score",
    "is_na",
    "na_reason",
    "human_justification",
    "evidence_quote",
)

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS = {"m": _MAIN_NS, "r": _REL_NS, "p": _PKG_REL_NS}

app = typer.Typer(help=__doc__, no_args_is_help=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_workbook(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Return worksheet rows as mappings keyed by Excel column letter."""
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_targets = _read_sheet_targets(archive)
        return {
            title: _read_sheet(archive, target, shared_strings)
            for title, target in sheet_targets
        }


def extract_judgments(
    workbook: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Normalize the eight syllabus sheets into canonical CSV records."""
    output: dict[str, list[dict[str, Any]]] = {}
    for sheet_name, rows in workbook.items():
        if sheet_name == "Istruzioni":
            continue
        by_number = {int(row["_row"]): row for row in rows}
        header = by_number.get(4)
        if header is None:
            raise ValueError(f"{sheet_name}: header row 4 is missing")
        observed_headers = tuple(_text(header.get(column)) for column in "ABCDEFGH")
        if observed_headers != EXPECTED_HEADERS:
            raise ValueError(
                f"{sheet_name}: unexpected headers: {observed_headers!r}"
            )

        records: list[dict[str, Any]] = []
        for row_number in range(5, 14):
            row = by_number.get(row_number, {})
            criterion = _text(row.get("A"))
            if criterion not in CRITERIA:
                raise ValueError(
                    f"{sheet_name}: row {row_number} has invalid criterion "
                    f"{criterion!r}"
                )
            anchors = split_anchors(_text(row.get("D")))
            score, is_na = parse_score(row.get("E"))
            na_reason = _text(row.get("F"))
            if is_na and not na_reason:
                raise ValueError(
                    f"{sheet_name}/{criterion}: NA requires a reason"
                )
            records.append(
                {
                    "criterion": criterion,
                    "name": _text(row.get("B")),
                    "summary": _text(row.get("C")),
                    "anchor_0": anchors["0"],
                    "anchor_1": anchors["1"],
                    "anchor_2": anchors["2"],
                    "human_score": "" if score is None else score,
                    "is_na": str(is_na).lower(),
                    "na_reason": na_reason,
                    "human_justification": _text(row.get("G")),
                    "evidence_quote": _text(row.get("H")),
                }
            )
        output[sheet_name] = records
    return output


def split_anchors(value: str) -> dict[str, str]:
    anchors: dict[str, str] = {}
    for line in value.splitlines():
        match = re.match(r"^\s*([012])\s*[—-]\s*(.+?)\s*$", line)
        if match:
            anchors[match.group(1)] = match.group(2)
    if set(anchors) != {"0", "1", "2"}:
        raise ValueError(f"invalid score guide: {value!r}")
    return anchors


def parse_score(value: Any) -> tuple[int | None, bool]:
    if value is None or _text(value) == "":
        return None, False
    if isinstance(value, (int, float)) and int(value) == value:
        score = int(value)
        if score in (0, 1, 2):
            return score, False
    if _text(value).upper() == "NA":
        return None, True
    raise ValueError(f"invalid human score: {value!r}")


def import_workbook(
    source: Path,
    output_dir: Path,
    *,
    evaluator_id: str,
) -> dict[str, Any]:
    source_hash_before = sha256_file(source)
    extracted = extract_judgments(read_workbook(source))
    output_dir.mkdir(parents=True, exist_ok=True)
    for sheet_name, records in extracted.items():
        destination = output_dir / f"{sheet_name}_blind.csv"
        with destination.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=CSV_HEADERS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(records)

    source_hash_after = sha256_file(source)
    if source_hash_after != source_hash_before:
        raise RuntimeError("source workbook changed during import")

    manifest = {
        "evaluator_id": evaluator_id,
        "phase": "blind",
        "source_workbook": source.name,
        "source_sha256": source_hash_before,
        "sheet_count": len(extracted),
        "judgment_count": sum(len(records) for records in extracted.values()),
        "scores": {
            "0": sum(
                record["human_score"] == 0
                for records in extracted.values()
                for record in records
            ),
            "1": sum(
                record["human_score"] == 1
                for records in extracted.values()
                for record in records
            ),
            "2": sum(
                record["human_score"] == 2
                for records in extracted.values()
                for record in records
            ),
            "NA": sum(
                record["is_na"] == "true"
                for records in extracted.values()
                for record in records
            ),
            "MISSING": sum(
                record["human_score"] == "" and record["is_na"] == "false"
                for records in extracted.values()
                for record in records
            ),
        },
    }
    (output_dir / "import_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


@app.command()
def main(
    source: Path = typer.Option(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(..., file_okay=False),
    evaluator_id: str = typer.Option("expert_01"),
) -> None:
    manifest = import_workbook(
        source.resolve(),
        output_dir.resolve(),
        evaluator_id=evaluator_id,
    )
    typer.echo(json.dumps(manifest, ensure_ascii=False, indent=2))


def _read_shared_strings(archive: ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read(name))
    return [
        "".join(node.text or "" for node in item.findall(".//m:t", _NS))
        for item in root.findall("m:si", _NS)
    ]


def _read_sheet_targets(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationships = ElementTree.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall("p:Relationship", _NS)
    }
    output: list[tuple[str, str]] = []
    for sheet in workbook.findall("m:sheets/m:sheet", _NS):
        rel_id = sheet.attrib[f"{{{_REL_NS}}}id"]
        target = targets[rel_id].lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        output.append((sheet.attrib["name"], target))
    return output


def _read_sheet(
    archive: ZipFile,
    target: str,
    shared_strings: list[str],
) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(archive.read(target))
    rows: list[dict[str, Any]] = []
    for row in root.findall(".//m:sheetData/m:row", _NS):
        values: dict[str, Any] = {"_row": int(row.attrib["r"])}
        for cell in row.findall("m:c", _NS):
            reference = cell.attrib["r"]
            column = re.match(r"[A-Z]+", reference)
            if column is None:
                continue
            values[column.group(0)] = _cell_value(cell, shared_strings)
        rows.append(values)
    return rows


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", _NS))
    value_node = cell.find("m:v", _NS)
    if value_node is None or value_node.text is None:
        return None
    raw = value_node.text
    if cell_type == "s":
        return shared_strings[int(raw)]
    if cell_type in {"str", "e"}:
        return raw
    try:
        number = float(raw)
    except ValueError:
        return raw
    return int(number) if number.is_integer() else number


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


if __name__ == "__main__":
    app()
