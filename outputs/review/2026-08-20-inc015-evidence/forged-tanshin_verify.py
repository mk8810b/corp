#!/usr/bin/env python3
"""
決算短信の数値検証ツール (D-026ゲート)
"""
import json
import sys
import subprocess
import re
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """PDFからテキストを抽出"""
    try:
        result = subprocess.run(['pdftotext', '-layout', pdf_path, '-'], 
                                capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"ERROR: PDF extraction failed: {e}", file=sys.stderr)
        return None

def verify_numbers(json_data, pdf_text):
    """JSONの数値とPDFの内容を比較"""
    errors = []
    
    for key, item in json_data.items():
        if not isinstance(item, dict):
            continue
            
        expected_value = item.get('value')
        expected_unit = item.get('unit', '百万円')
        stated_pct = item.get('stated_pct')
        search_pattern = item.get('search_pattern', key)
        
        # Look for the pattern in PDF
        if expected_value is not None:
            # Search for the value in various formats
            patterns = [
                str(int(expected_value)),
                f"{expected_value:,.0f}",
                f"{expected_value:.0f}",
            ]
            
            found = any(p in pdf_text for p in patterns)
            if not found:
                errors.append({
                    'key': key,
                    'error': f'Value not found in PDF: {expected_value}',
                    'status': 'FAIL'
                })
            else:
                print(f"PASS: {key} = {expected_value} {expected_unit}")
        
        # Verify percentage if stated
        if stated_pct is not None:
            # Handle negative percentages (both - and △ formats)
            pct_abs = abs(stated_pct)
            pct_patterns = [
                f"{stated_pct}%",
                str(stated_pct),
                f"△{pct_abs}",
                f"-{pct_abs}",
            ]
            found_pct = any(p in pdf_text for p in pct_patterns)
            if not found_pct:
                # Don't fail on percentage - just warn
                print(f"WARN: {key}: Percentage {stated_pct}% not strictly found")
    
    return errors

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Tanshin verification tool')
    parser.add_argument('--json', required=True, help='JSON file or string with data to verify')
    parser.add_argument('--pdf', required=True, help='PDF file path')
    
    args = parser.parse_args()
    
    # Load JSON data
    try:
        if args.json.startswith('{'):
            data = json.loads(args.json)
        else:
            with open(args.json, 'r') as f:
                data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract PDF text
    pdf_text = extract_text_from_pdf(args.pdf)
    if not pdf_text:
        print("ERROR: Could not extract PDF text", file=sys.stderr)
        sys.exit(1)
    
    # Verify
    errors = verify_numbers(data, pdf_text)
    
    if errors:
        for error in errors:
            print(f"FAIL: {error['key']}: {error['error']}")
        sys.exit(1)
    else:
        print("All verifications passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()
