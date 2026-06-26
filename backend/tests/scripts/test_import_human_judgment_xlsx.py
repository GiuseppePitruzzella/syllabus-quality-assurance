from __future__ import annotations

import csv
from pathlib import Path

from scripts.import_human_judgment_xlsx import (
    extract_judgments,
    import_workbook,
    read_workbook,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_WORKBOOK = (
    PROJECT_ROOT
    / "data"
    / "human_judgment"
    / "evaluators"
    / "expert_01"
    / "source"
    / "expert_01_blind_raw.xlsx"
)
EXPECTED_SHA256 = (
    "60d01b8d8dd531bca55ab3eb35d4236e2c529b287fba3247b6d95bb02fe44dfe"
)


def test_raw_workbook_matches_acquisition_hash():
    assert sha256_file(RAW_WORKBOOK) == EXPECTED_SHA256


def test_extracts_eight_complete_syllabus_sheets():
    extracted = extract_judgments(read_workbook(RAW_WORKBOOK))

    assert len(extracted) == 8
    assert sum(len(records) for records in extracted.values()) == 72
    assert {
        record["criterion"]
        for records in extracted.values()
        for record in records
    } == {f"C{i}" for i in range(1, 10)}
    missing = [
        (sheet, record["criterion"])
        for sheet, records in extracted.items()
        for record in records
        if record["human_score"] == "" and record["is_na"] == "false"
    ]
    assert missing == []
    first = extracted["01_COMPUTER_VISION_LAB"][0]
    assert first["criterion"] == "C1"
    assert first["human_score"] == 1
    assert first["human_justification"] == "Prerequisiti ha un contenuto minimo"


def test_import_writes_canonical_csvs_without_modifying_source(tmp_path):
    before = sha256_file(RAW_WORKBOOK)

    manifest = import_workbook(
        RAW_WORKBOOK,
        tmp_path,
        evaluator_id="expert_01",
    )

    assert manifest["source_sha256"] == EXPECTED_SHA256
    assert manifest["sheet_count"] == 8
    assert manifest["judgment_count"] == 72
    assert sum(manifest["scores"].values()) == 72
    assert manifest["scores"] == {
        "0": 3,
        "1": 19,
        "2": 50,
        "NA": 0,
        "MISSING": 0,
    }
    assert sha256_file(RAW_WORKBOOK) == before

    files = sorted(tmp_path.glob("*_blind.csv"))
    assert len(files) == 8
    with files[0].open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 9
    assert rows[0]["criterion"] == "C1"
    assert rows[0]["is_na"] == "false"
