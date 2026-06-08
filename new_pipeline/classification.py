"""
Document type classification with priority for handwritten insurance forms.
"""

import re
from typing import Dict, Any

def classify_document_type(raw_text: str) -> Dict[str, Any]:
    """
    Classify document type by checking keywords in priority order.
    Returns dict with keys: doc_type, confidence, method, handwritten.
    """
    if not raw_text or not raw_text.strip():
        return {"doc_type": "unknown", "confidence": 0, "method": "empty", "handwritten": False}

    # ----- OVERRIDES (highest priority, before any rule matching) -----
    if "Permanent Account Number Card" in raw_text:
        return {"doc_type": "PAN Card", "confidence": 95, "method": "override", "handwritten": False}
    if "Benefit Illustration" in raw_text:
        return {"doc_type": "Benefit Illustration Declaration", "confidence": 95, "method": "override", "handwritten": True}
    if "Moral Hazard Questionnaire" in raw_text:
        return {"doc_type": "Moral Hazard Questionnaire", "confidence": 95, "method": "override", "handwritten": True}

    # ----- RULE-BASED CLASSIFICATION (priority order) -----
    # Priority order: handwritten forms first, then government IDs
    CLASSIFICATION_RULES = [
        # Handwritten forms (highest priority)
        ("NACH / ECS Mandate", {
            "patterns": [r"\bnach\b", r"\becs\b", r"mandate", r"auto debit", r"bank account"],
            "handwritten": True,
            "confidence": 85
        }),
        ("FATCA Annexure Form", {
            "patterns": [r"fatca", r"annexure", r"foreign account", r"tax identification number", r"tin"],
            "handwritten": True,
            "confidence": 85
        }),
        ("Benefit Illustration Declaration", {
            "patterns": [r"benefit illustration", r"declaration", r"illustration"],
            "handwritten": True,
            "confidence": 85
        }),
        ("Moral Hazard Questionnaire", {
            "patterns": [r"moral hazard", r"questionnaire", r"hazard"],
            "handwritten": True,
            "confidence": 85
        }),
        ("Multiple Policies Consent Form", {
            "patterns": [r"multiple policies", r"consent", r"split", r"more than one policy"],
            "handwritten": True,
            "confidence": 85
        }),
        ("Suitability Profiler Declaration", {
            "patterns": [r"suitability profiler", r"profiler", r"suitability"],
            "handwritten": True,
            "confidence": 85
        }),
        # Government ID cards (lower priority)
        ("Aadhaar Card", {
            "patterns": [r"aadhaar", r"\d{4}\s?\d{4}\s?\d{4}"],
            "handwritten": False,
            "confidence": 85
        }),
        ("PAN Card", {
            "patterns": [r"pan", r"[A-Z]{5}[0-9]{4}[A-Z]{1}"],
            "handwritten": False,
            "confidence": 85
        }),
        ("Driving Licence", {
            "patterns": [r"driving licence", r"dl no", r"licence", r"license"],
            "handwritten": False,
            "confidence": 80
        }),
        ("Passport", {
            "patterns": [r"passport", r"[A-Z][0-9]{7}"],
            "handwritten": False,
            "confidence": 80
        }),
    ]

    text_lower = raw_text.lower()
    for doc_type, info in CLASSIFICATION_RULES:
        for pattern in info["patterns"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return {
                    "doc_type": doc_type,
                    "confidence": info["confidence"],
                    "method": "rule",
                    "handwritten": info["handwritten"]
                }

    # No match
    return {
        "doc_type": "unknown",
        "confidence": 20,
        "method": "rule",
        "handwritten": False
    }