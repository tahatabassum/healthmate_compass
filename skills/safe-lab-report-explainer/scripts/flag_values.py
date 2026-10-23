#!/usr/bin/env python3
"""
flag_values.py — Standalone Laboratory Flag Computation Tool
Reuses the exact deterministic validation and flag calculation logic from HealthMate Compass.
No third-party dependencies required (pure standard library).

Usage:
    python flag_values.py input.json [--ranges references/reference-ranges.json] [--gender male|female]
    cat input.json | python flag_values.py -
"""

import sys
import os
import json
import re
import argparse
from typing import Optional, Tuple, Dict, Any, List

def clean_test_name(name: str) -> str:
    if not name:
        return ""
    cleaned = name.lower().strip()
    cleaned = re.sub(r"^(serum|blood|plasma|s\.|b\.)\s+", "", cleaned)
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def build_synonym_map(ref_ranges_data: Dict[str, Any]) -> Dict[str, str]:
    mapping = {}
    tests = ref_ranges_data.get("tests", {})
    for canon_key, info in tests.items():
        mapping[canon_key.lower().strip()] = canon_key
        display = info.get("display", "")
        if display:
            mapping[display.lower().strip()] = canon_key
            mapping[clean_test_name(display)] = canon_key
        for syn in info.get("synonyms", []):
            syn_clean = syn.lower().strip()
            mapping[syn_clean] = canon_key
            mapping[clean_test_name(syn)] = canon_key
            mapping[syn_clean.replace(".", "")] = canon_key

    # Common report truncation abbreviations
    additional = {
        "cholestero": "total_cholesterol",
        "triglyceri": "triglycerides",
        "total bili": "bilirubin_total",
        "total prot": "total_protein",
        "alk phos": "alkaline_phosphatase",
        "got ast": "ast",
        "got": "ast",
        "gpt alt": "alt",
        "gpt": "alt",
        "b/c ratio": "bun_creatinine_ratio",
        "bc ratio": "bun_creatinine_ratio",
        "calc osmo": "osmolality",
        "tco2": "total_co2",
    }
    for k, v in additional.items():
        mapping[k] = v
    return mapping

def resolve_canonical_name(test_name: str, synonym_map: Dict[str, str]) -> Optional[str]:
    if not test_name:
        return None
    raw = test_name.lower().strip()
    if raw in synonym_map:
        return synonym_map[raw]
    cleaned = clean_test_name(test_name)
    if cleaned in synonym_map:
        return synonym_map[cleaned]
    no_dots = raw.replace(".", "").strip()
    if no_dots in synonym_map:
        return synonym_map[no_dots]
    for syn, canon in synonym_map.items():
        if syn == cleaned or syn == no_dots or f" {syn} " in f" {cleaned} ":
            return canon
    return None

def validate_and_sanitize_range(
    ref_low: Optional[float],
    ref_high: Optional[float],
    ref_range_text: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    warning = None
    txt = (ref_range_text or "").strip()

    if txt:
        lt_match = re.match(r"^<\s*(\d+(?:\.\d+)?)$", txt)
        if lt_match:
            return None, float(lt_match.group(1)), None
        gt_match = re.match(r"^>\s*(\d+(?:\.\d+)?)$", txt)
        if gt_match:
            return float(gt_match.group(1)), None, None
        hyphen_match = re.match(r"^(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)$", txt)
        if hyphen_match:
            p_low = float(hyphen_match.group(1))
            p_high = float(hyphen_match.group(2))
            if p_low <= p_high:
                return p_low, p_high, None
            else:
                return p_high, p_low, f"Inverted range in printed text '{txt}' corrected."

    if ref_low is not None and ref_high is not None:
        if ref_low > ref_high:
            return ref_high, ref_low, f"Inverted reference bounds ({ref_low} - {ref_high}) automatically swapped."

    return ref_low, ref_high, warning

def compute_flag(
    value: Optional[float],
    canonical_name: Optional[str],
    report_low: Optional[float],
    report_high: Optional[float],
    ref_range_text: Optional[str],
    ref_ranges_data: Dict[str, Any],
    gender: Optional[str] = None,
) -> Tuple[str, Optional[float], Optional[float]]:
    if value is None:
        return "unverified", None, None

    eff_low, eff_high, _ = validate_and_sanitize_range(report_low, report_high, ref_range_text)

    crit_low: Optional[float] = None
    crit_high: Optional[float] = None

    tests = ref_ranges_data.get("tests", {})
    if canonical_name and canonical_name in tests:
        tinfo = tests[canonical_name]
        ranges = tinfo.get("ranges", {})
        gen_key = (gender or "default").lower()
        active = ranges.get(gen_key) or ranges.get("default") or {}

        if eff_low is None and active.get("low") is not None:
            eff_low = active.get("low")
        if eff_high is None and active.get("high") is not None:
            eff_high = active.get("high")

        crit_low = active.get("critical_low")
        crit_high = active.get("critical_high")

    if eff_low is not None and eff_high is not None and eff_low > eff_high:
        eff_low, eff_high = eff_high, eff_low

    if crit_low is not None and value <= crit_low:
        return "critical", eff_low, eff_high
    if crit_high is not None and value >= crit_high:
        return "critical", eff_low, eff_high

    if eff_low is not None and value < eff_low:
        return "low", eff_low, eff_high
    if eff_high is not None and value > eff_high:
        return "high", eff_low, eff_high

    return "normal", eff_low, eff_high

def process_items(
    items: List[Dict[str, Any]],
    ref_ranges_data: Dict[str, Any],
    gender: Optional[str] = None,
) -> List[Dict[str, Any]]:
    synonym_map = build_synonym_map(ref_ranges_data)
    processed = []

    for item in items:
        tname = item.get("test_name", "")
        val = item.get("value")
        unit = item.get("unit", "")
        r_low = item.get("ref_low")
        r_high = item.get("ref_high")
        r_txt = item.get("ref_range_text")

        canon = item.get("canonical_name") or resolve_canonical_name(tname, synonym_map)

        # Negative value check
        if val is not None and val < 0:
            item_out = dict(item)
            item_out["canonical_name"] = canon
            item_out["value"] = None
            item_out["flag"] = "unverified"
            item_out["error"] = f"Suppressed invalid negative reading ({val})"
            processed.append(item_out)
            continue

        flag, eff_low, eff_high = compute_flag(
            value=val,
            canonical_name=canon,
            report_low=r_low,
            report_high=r_high,
            ref_range_text=r_txt,
            ref_ranges_data=ref_ranges_data,
            gender=gender,
        )

        item_out = dict(item)
        item_out["canonical_name"] = canon
        item_out["flag"] = flag
        item_out["effective_ref_low"] = eff_low
        item_out["effective_ref_high"] = eff_high
        processed.append(item_out)

    return processed

def main():
    parser = argparse.ArgumentParser(description="Deterministic clinical lab value flagging script.")
    parser.add_argument("input_file", help="Path to JSON file with test values, or '-' for stdin")
    parser.add_argument("--ranges", default=None, help="Path to reference-ranges.json")
    parser.add_argument("--gender", choices=["male", "female", "default"], default=None, help="Patient biological sex")
    args = parser.parse_args()

    # Locate default reference-ranges.json if not passed
    ranges_path = args.ranges
    if not ranges_path:
        local_ref = os.path.join(os.path.dirname(__file__), "..", "references", "reference-ranges.json")
        if os.path.exists(local_ref):
            ranges_path = local_ref
        else:
            ranges_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app", "data", "reference_ranges.json")

    if not os.path.exists(ranges_path):
        sys.stderr.write(f"Error: reference ranges file not found at {ranges_path}\n")
        sys.exit(1)

    with open(ranges_path, "r", encoding="utf-8") as f:
        ref_data = json.load(f)

    if args.input_file == "-":
        input_data = json.load(sys.stdin)
    else:
        with open(args.input_file, "r", encoding="utf-8") as f:
            input_data = json.load(f)

    if isinstance(input_data, dict) and "values" in input_data:
        items = input_data["values"]
    elif isinstance(input_data, list):
        items = input_data
    else:
        sys.stderr.write("Input JSON must be an array of test objects or an object with 'values': [...]\n")
        sys.exit(1)

    flagged = process_items(items, ref_data, gender=args.gender)
    print(json.dumps(flagged, indent=2))

if __name__ == "__main__":
    main()
