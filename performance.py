"""
Generate overall performance report for document extraction.
Usage: python performance_report.py
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

EXTRACTED_JSON = Path("Data/final/extraction_output.json")
GROUND_TRUTH_DIR = Path("Data/ground_truth")  # optional
OUTPUT_REPORT = Path("Data/final/performance_report.json")

def load_ground_truth(doc_id: str) -> Dict[str, str]:
    """Load ground truth for a single document (JSON per doc)."""
    gt_path = GROUND_TRUTH_DIR / f"{doc_id}.json"
    if not gt_path.exists():
        return {}
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_str(s: Any) -> str:
    return str(s).strip().lower() if s else ""

def compare_with_ground_truth(extracted_value: Any, expected_value: Any) -> bool:
    """Exact match after normalisation."""
    return normalize_str(extracted_value) == normalize_str(expected_value)

def generate_report():
    with open(EXTRACTED_JSON, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Overall counters
    total_docs = len(results)
    total_fields = 0
    fields_extracted = 0  # non-null values
    fields_flagged = 0
    confidence_sum = 0
    confidence_count = 0

    # Per‑document stats
    doc_stats = []
    # Per‑field type stats
    field_type_stats = defaultdict(lambda: {"total": 0, "extracted": 0, "flagged": 0, "confidence_sum": 0})
    # Accuracy (if ground truth exists)
    accuracy_total = 0
    accuracy_correct = 0
    ground_truth_available = GROUND_TRUTH_DIR.exists()

    for doc in results:
        doc_id = doc["doc_id"]
        doc_type = doc["doc_type"]
        is_handwritten = doc["is_handwritten"]
        extracted_fields = doc.get("extracted_fields", {})
        overall_conf = doc.get("overall_confidence", 0)

        # Count fields for this document
        num_fields = len(extracted_fields)
        total_fields += num_fields
        extracted_count = sum(1 for v in extracted_fields.values() if v["value"] is not None)
        fields_extracted += extracted_count
        flagged_count = sum(1 for v in extracted_fields.values() if v["confidence"] < (60 if is_handwritten else 70))
        fields_flagged += flagged_count
        doc_confidence_sum = sum(v["confidence"] for v in extracted_fields.values())
        confidence_sum += doc_confidence_sum
        confidence_count += num_fields

        # Load ground truth if available
        if ground_truth_available:
            gt = load_ground_truth(doc_id)
            for field, expected in gt.items():
                extracted_value = extracted_fields.get(field, {}).get("value")
                if compare_with_ground_truth(extracted_value, expected):
                    accuracy_correct += 1
                accuracy_total += 1

        # Per‑field type stats
        for field, data in extracted_fields.items():
            field_type_stats[field]["total"] += 1
            if data["value"] is not None:
                field_type_stats[field]["extracted"] += 1
            if data["confidence"] < (60 if is_handwritten else 70):
                field_type_stats[field]["flagged"] += 1
            field_type_stats[field]["confidence_sum"] += data["confidence"]

        doc_stats.append({
            "doc_id": doc_id,
            "doc_type": doc_type,
            "handwritten": is_handwritten,
            "extracted_fields": extracted_count,
            "total_fields": num_fields,
            "flagged_fields": flagged_count,
            "overall_confidence": overall_conf
        })

    # Compute averages
    avg_confidence = confidence_sum / confidence_count if confidence_count else 0
    extraction_rate = fields_extracted / total_fields if total_fields else 0
    flag_rate = fields_flagged / total_fields if total_fields else 0
    accuracy = accuracy_correct / accuracy_total if accuracy_total > 0 else None

    # Build report
    report = {
        "summary": {
            "total_documents": total_docs,
            "total_fields_expected": total_fields,
            "fields_extracted_non_null": fields_extracted,
            "extraction_rate": round(extraction_rate, 3),
            "fields_flagged_below_threshold": fields_flagged,
            "flag_rate": round(flag_rate, 3),
            "average_confidence_across_fields": round(avg_confidence, 2),
        },
        "per_field_accuracy": {}
    }

    if accuracy is not None:
        report["summary"]["ground_truth_accuracy"] = round(accuracy, 3)
        report["summary"]["correct_fields"] = accuracy_correct
        report["summary"]["total_compared_fields"] = accuracy_total

    # Per‑field performance
    for field, stats in sorted(field_type_stats.items()):
        report["per_field_accuracy"][field] = {
            "total_occurrences": stats["total"],
            "times_extracted": stats["extracted"],
            "times_flagged": stats["flagged"],
            "average_confidence": round(stats["confidence_sum"] / stats["total"], 2) if stats["total"] else 0
        }

    # Optional: per‑document details (can be large, maybe omit for final)
    report["per_document_summary"] = doc_stats

    # Save report
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Performance report saved to {OUTPUT_REPORT}")
    print("\n=== QUICK SUMMARY ===")
    print(f"Total documents: {total_docs}")
    print(f"Fields extracted: {fields_extracted}/{total_fields} ({extraction_rate:.1%})")
    print(f"Fields flagged for review: {fields_flagged} ({flag_rate:.1%})")
    print(f"Average confidence: {avg_confidence:.1f}")
    if accuracy is not None:
        print(f"Ground truth accuracy: {accuracy:.1%} ({accuracy_correct}/{accuracy_total})")
    else:
        print("No ground truth found – accuracy not computed.")

if __name__ == "__main__":
    generate_report()