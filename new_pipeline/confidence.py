"""
Confidence scoring and flagging for document field extraction.
Provides per-field confidence scores and generates a flagging report
for fields below threshold.
"""

from typing import Dict, Any, List, Tuple, Optional
import csv
from pathlib import Path

from config import DOCUMENT_CONFIDENCE_THRESHOLD, HANDWRITTEN_CONFIDENCE_THRESHOLD, HANDWRITTEN_DOC_TYPES


def compute_field_confidence(field_name: str, value: Any, is_handwritten: bool = False) -> int:
    """
    Compute confidence for a single field based on value characteristics.
    Returns integer 0-100.
    """
    if value is None or value == "":
        return 0
    
    # Start with base confidence
    base = 70 if is_handwritten else 85
    
    # Adjust based on value quality
    value_str = str(value).strip()
    
    # Penalize very short values (likely incomplete)
    if len(value_str) < 3:
        base -= 20
    elif len(value_str) < 5:
        base -= 10
    
    # Penalize if contains too many non-alphanumeric characters (possible OCR garbage)
    alnum_ratio = sum(c.isalnum() for c in value_str) / max(len(value_str), 1)
    if alnum_ratio < 0.6:
        base -= 20
    elif alnum_ratio < 0.8:
        base -= 10
    
    # Penalize if contains repeated ambiguous OCR characters
    if re.search(r'[lI1O0]{3,}', value_str):
        base -= 15
    
    # Boost for specific high-value field patterns
    if field_name in ["PAN Number", "Aadhaar Number", "Passport Number", "DL Number"]:
        # Already validated by regex, so trust is high
        base = min(base + 10, 100)
    elif field_name in ["IFSC Code"]:
        if re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value_str):
            base = min(base + 10, 100)
    elif field_name in ["Date of Birth", "Date of Issue", "Valid Till date", "Date of Expiry"]:
        # Validate date format
        if re.match(r'\d{2}[/-]\d{2}[/-]\d{4}', value_str) or re.match(r'\d{4}[/-]\d{2}[/-]\d{2}', value_str):
            base = min(base + 5, 100)
    
    return max(0, min(100, base))


def compute_overall_confidence(extracted_fields: Dict[str, Tuple[Any, int]], is_handwritten: bool = False) -> int:
    """
    Compute overall document confidence as average of non-zero field confidences.
    """
    confidences = [conf for (_, conf) in extracted_fields.values() if conf > 0]
    if not confidences:
        return 0
    return int(sum(confidences) / len(confidences))


def get_field_confidence_threshold(is_handwritten: bool) -> int:
    """
    Return the confidence threshold to use for flagging.
    """
    return HANDWRITTEN_CONFIDENCE_THRESHOLD if is_handwritten else DOCUMENT_CONFIDENCE_THRESHOLD


def flag_low_confidence_fields(
    doc_id: str,
    doc_type: str,
    extracted_fields: Dict[str, Tuple[Any, int]],
    is_handwritten: bool = False
) -> List[Dict[str, Any]]:
    """
    Identify fields with confidence below threshold.
    Returns list of flag records.
    """
    threshold = get_field_confidence_threshold(is_handwritten)
    flags = []
    
    for field_name, (value, conf) in extracted_fields.items():
        if conf < threshold and value is not None and value != "":
            flags.append({
                "document_id": doc_id,
                "document_type": doc_type,
                "field": field_name,
                "extracted_value": str(value)[:100],  # truncate long values
                "confidence": conf,
                "threshold": threshold,
                "review_needed": "YES"
            })
    return flags


def generate_flagging_report(
    extraction_results: List[Dict[str, Any]],
    output_path: Path
) -> Path:
    """
    Generate a CSV report of all flagged fields.
    
    Args:
        extraction_results: List of records, each containing:
            - doc_id: str
            - doc_type: str
            - extracted_fields: Dict[str, Tuple[Any, int]]
            - is_handwritten: bool (optional, will be inferred from doc_type if missing)
        output_path: Path to save the CSV report.
    
    Returns:
        Path to the created report file.
    """
    all_flags = []
    
    for result in extraction_results:
        doc_id = result.get("doc_id", "unknown")
        doc_type = result.get("doc_type", "unknown")
        extracted_fields = result.get("extracted_fields", {})
        
        # Determine if handwritten based on doc_type or explicit flag
        if "is_handwritten" in result:
            is_handwritten = result["is_handwritten"]
        else:
            is_handwritten = doc_type in HANDWRITTEN_DOC_TYPES
        
        flags = flag_low_confidence_fields(doc_id, doc_type, extracted_fields, is_handwritten)
        all_flags.extend(flags)
    
    # Write to CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["document_id", "document_type", "field", "extracted_value", "confidence", "threshold", "review_needed"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_flags)
    
    return output_path


def print_flagging_summary(flags: List[Dict[str, Any]]) -> None:
    """
    Print a summary of flagged fields to console.
    """
    if not flags:
        print("\n✅ No fields flagged below confidence threshold.")
        return
    
    print(f"\n⚠️  Flagged {len(flags)} fields below confidence threshold:")
    # Group by document
    by_doc = {}
    for flag in flags:
        doc_id = flag["document_id"]
        if doc_id not in by_doc:
            by_doc[doc_id] = []
        by_doc[doc_id].append(flag)
    
    for doc_id, doc_flags in by_doc.items():
        print(f"\n  Document: {doc_id}")
        for f in doc_flags:
            print(f"    - {f['field']}: '{f['extracted_value']}' (confidence: {f['confidence']} < {f['threshold']})")


# Import re for use in compute_field_confidence (lazy import at top)
import re