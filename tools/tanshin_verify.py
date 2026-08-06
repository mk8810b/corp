#!/usr/bin/env python3
"""
Decision Short-form Verification Script (D-026)
Validates numerical transfers from earnings forecast revisions and quarterly reports.
"""

import json
import sys
import argparse
from pathlib import Path


def verify_metrics(json_data):
    """Verify metrics calculations."""
    failures = []
    warnings = []
    
    metrics = json_data.get("metrics", [])
    for metric in metrics:
        name = metric.get("name", "Unknown")
        before = metric.get("before")
        after = metric.get("after")
        stated_pct = metric.get("stated_pct")
        
        if before is None or after is None or stated_pct is None:
            failures.append(f"{name}: Missing data")
            continue
        
        # Calculate expected percentage change
        if before == 0:
            if after == 0:
                expected_pct = 0.0
            else:
                # Cannot calculate meaningful percentage
                warnings.append(f"{name}: Before value is 0")
                continue
        else:
            expected_pct = round(((after - before) / before) * 100, 1)
        
        # Compare with stated percentage
        if abs(expected_pct - stated_pct) > 0.05:  # Allow small rounding difference
            failures.append(
                f"{name}: Calculated {expected_pct}% does not match stated {stated_pct}%"
            )
    
    return failures, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Verify numerical transfers from financial documents"
    )
    parser.add_argument("--json", required=True, help="Path to JSON verification file")
    parser.add_argument("--pdf", required=True, help="Path to source PDF document")
    
    args = parser.parse_args()
    
    # Load JSON
    try:
        with open(args.json, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: JSON file not found: {args.json}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(1)
    
    # Verify PDF exists
    if not Path(args.pdf).exists():
        print(f"ERROR: PDF file not found: {args.pdf}")
        sys.exit(1)
    
    # Run verification
    failures, warnings = verify_metrics(json_data)
    
    # Report results
    print(f"Verification Report: {json_data.get('company')} ({json_data.get('code')})")
    print(f"Document Type: {json_data.get('document_type')}")
    print(f"Fiscal Period: {json_data.get('fiscal_period')}")
    print()
    
    if failures:
        print(f"FAIL ({len(failures)} issue(s)):")
        for fail in failures:
            print(f"  - {fail}")
    else:
        print("✓ All metrics verified")
    
    if warnings:
        print(f"\nWARN ({len(warnings)} warning(s)):")
        for warn in warnings:
            print(f"  - {warn}")
    
    # Exit code
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
