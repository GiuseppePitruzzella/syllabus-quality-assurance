"""Official self-consistency default sample = the 8 human-validation syllabi.

Kept identical to ``backend/scripts/setup_human_judgment.py``'s
``SHORTLIST`` (slot 08 = VULN_ASSESSMENT_PT after the 2026-06-18 swap).
A parity test guards against divergence; we duplicate the literal here
(rather than importing the script) to avoid importing a CLI module at
runtime.
"""
from __future__ import annotations

OFFICIAL_HUMAN_SAMPLE: list[tuple[str, str]] = [
    ("88B7C1CE-B595-46A5-A37A-C5414AD807B5", "01_COMPUTER_VISION_LAB"),
    ("0B53E8E2-4B90-426F-A25C-3AA31FA4B649", "02_INTERNET_OF_THINGS"),
    ("F4AF1512-9D7A-4256-B57D-E103E05B009B", "03_PEER_TO_PEER_LAB"),
    ("9A90BBCE-99E3-4FB0-BF91-CCAAA5C51791", "04_MULTIMEDIA_LAB"),
    ("89E21813-A17C-4C85-AF65-C295EE11ED59", "05_COMPUTER_VISION"),
    ("E2446DF6-59A1-46FD-B8D8-635EB937C1B3", "06_OTTIMIZZAZIONE"),
    ("3540D939-DA16-4C1D-983C-E6B85C403F2F", "07_DEEP_LEARNING"),
    ("46D62804-0FCD-4478-A51D-A752B64A7DCB", "08_VULN_ASSESSMENT_PT"),
]
