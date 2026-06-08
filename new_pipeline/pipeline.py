# """
# Document extraction pipeline for PDF, JPEG, PNG files.
# Processes files from Data/Raw, classifies, extracts fields, outputs JSON + flagging report.
# """

# import json
# import sys
# from pathlib import Path
# from typing import Dict, Any, List, Optional

# sys.path.insert(0, str(Path(__file__).parent.parent))

# from config import RAW_DIR, FINAL_DIR, HANDWRITTEN_DOC_TYPES
# from logger import logger
# from extractor import extract_pdf, extract_image
# from new_pipeline.field_extractor import get_extractor
# from new_pipeline.classification import classify_document_type
# from new_pipeline.confidence import (
#     compute_field_confidence,
#     compute_overall_confidence,
#     generate_flagging_report,
#     print_flagging_summary,
# )


# def get_raw_text(file_path: Path) -> Optional[str]:
#     """Extract text from PDF or image file."""
#     ext = file_path.suffix.lower()
#     try:
#         if ext == ".pdf":
#             return extract_pdf(str(file_path))
#         elif ext in [".jpg", ".jpeg", ".png"]:
#             return extract_image(str(file_path))
#         else:
#             logger.warning(f"Unsupported file type: {ext} for {file_path} – skipping")
#             return None
#     except Exception as e:
#         logger.error(f"Error extracting text from {file_path}: {e}")
#         return None


# def process_single_file(file_path: Path) -> Optional[Dict[str, Any]]:
#     """Process one file: extract text, classify, extract fields, compute confidence."""
#     logger.info(f"Processing: {file_path.name}")
    
#     raw_text = get_raw_text(file_path)
#     if not raw_text or not raw_text.strip():
#         logger.warning(f"No text extracted from {file_path.name}")
#         return None
    
#     # Classify
#     classification = classify_document_type(raw_text)
#     doc_type = classification["doc_type"]
#     is_handwritten = classification["handwritten"]
#     logger.info(f"  Classified as: {doc_type} (conf: {classification['confidence']}, handwritten: {is_handwritten})")
    
#     if doc_type == "unknown":
#         return {
#             "doc_id": file_path.stem,
#             "source_file": str(file_path),
#             "doc_type": doc_type,
#             "classification_confidence": classification["confidence"],
#             "is_handwritten": is_handwritten,
#             "extracted_fields": {},
#             "overall_confidence": 0,
#             "raw_text_preview": raw_text[:500],
#         }
    
#     # Extract fields
#     extractor_func = get_extractor(doc_type)
#     extracted = extractor_func(raw_text)  # {field: (value, conf)}
    
#     # Refine confidence
#     final_fields = {}
#     for field_name, (value, conf) in extracted.items():
#         if conf == 0 and value:
#             conf = compute_field_confidence(field_name, value, is_handwritten)
#         final_fields[field_name] = (value, conf)
    
#     overall_conf = compute_overall_confidence(final_fields, is_handwritten)
    
#     result = {
#         "doc_id": file_path.stem,
#         "source_file": str(file_path),
#         "doc_type": doc_type,
#         "classification_confidence": classification["confidence"],
#         "is_handwritten": is_handwritten,
#         "extracted_fields": {k: {"value": v[0], "confidence": v[1]} for k, v in final_fields.items()},
#         "overall_confidence": overall_conf,
#         "raw_text_preview": raw_text[:500],
#     }
    
#     logger.info(f"  Extracted {len(final_fields)} fields, overall confidence: {overall_conf}")
#     return result


# def run_pipeline(input_dir: Path = RAW_DIR, output_dir: Path = FINAL_DIR) -> None:
#     """Run pipeline on all PDF/JPEG/PNG files in input_dir."""
#     if not input_dir.exists():
#         logger.error(f"Input directory not found: {input_dir}")
#         return
    
#     # Find supported files
#     supported_ext = {".pdf", ".jpg", ".jpeg", ".png"}
#     files = [f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() in supported_ext]
#     if not files:
#         logger.warning(f"No PDF/JPG/PNG files found in {input_dir}")
#         return
    
#     logger.info(f"Found {len(files)} files to process")
    
#     results = []
#     for file_path in files:
#         res = process_single_file(file_path)
#         if res:
#             results.append(res)
    
#     # Save JSON output
#     output_dir.mkdir(parents=True, exist_ok=True)
#     json_output = output_dir / "extraction_output.json"
#     with open(json_output, "w", encoding="utf-8") as f:
#         json.dump(results, f, indent=2, ensure_ascii=False)
#     logger.info(f"Saved extraction results to {json_output}")
    
#     # Generate flagging report
#     flagging_input = []
#     for res in results:
#         extracted_fields = {k: (v["value"], v["confidence"]) for k, v in res.get("extracted_fields", {}).items()}
#         flagging_input.append({
#             "doc_id": res["doc_id"],
#             "doc_type": res["doc_type"],
#             "extracted_fields": extracted_fields,
#             "is_handwritten": res["is_handwritten"],
#         })
#     report_path = output_dir / "flagging_report.csv"
#     generate_flagging_report(flagging_input, report_path)
#     logger.info(f"Saved flagging report to {report_path}")
    
#     # Print flagged summary
#     all_flags = []
#     for inp in flagging_input:
#         from new_pipeline.confidence import flag_low_confidence_fields
#         flags = flag_low_confidence_fields(inp["doc_id"], inp["doc_type"], inp["extracted_fields"], inp["is_handwritten"])
#         all_flags.extend(flags)
#     print_flagging_summary(all_flags)
    
#     logger.info("Pipeline completed.")


# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(description="Document extraction pipeline (PDF, JPEG, PNG)")
#     parser.add_argument("--input", type=Path, default=RAW_DIR, help="Input directory with documents")
#     parser.add_argument("--output", type=Path, default=FINAL_DIR, help="Output directory for JSON and CSV")
#     args = parser.parse_args()
#     run_pipeline(args.input, args.output)

"""
Document extraction pipeline for PDF, JPEG, PNG files.
Processes files from Data/Raw, classifies, extracts fields, outputs JSON + flagging report.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RAW_DIR, FINAL_DIR, HANDWRITTEN_DOC_TYPES
from logger import logger
from extractor import extract_pdf, extract_image
from new_pipeline.field_extraction import get_extractor
from new_pipeline.classification import classify_document_type
from new_pipeline.confidence import (
    compute_field_confidence,
    compute_overall_confidence,
    generate_flagging_report,
    print_flagging_summary,
)

# Image types that can be passed directly as image_path to field extractors
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def get_raw_text(file_path: Path) -> Optional[str]:
    """Extract text from PDF or image file."""
    ext = file_path.suffix.lower()
    try:
        if ext == ".pdf":
            return extract_pdf(str(file_path))
        elif ext in _IMAGE_EXTENSIONS:
            return extract_image(str(file_path))
        else:
            logger.warning(f"Unsupported file type: {ext} for {file_path} – skipping")
            return None
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        return None


def process_single_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Process one file: extract text, classify, extract fields, compute confidence."""
    logger.info(f"Processing: {file_path.name}")

    ext = file_path.suffix.lower()
    raw_text = get_raw_text(file_path)

    # For image files, always pass image_path to extractors so they can run
    # their own multi-engine OCR (Tesseract/Paddle/EasyOCR) directly on the
    # image — gives better results than passing pre-extracted text alone.
    image_path: Optional[str] = (
        str(file_path) if ext in _IMAGE_EXTENSIONS else None
    )

    # For scanned PDFs: no image_path (pages were already OCR'd inside extract_pdf)
    # raw_text will contain the merged OCR output from all pages.

    if not raw_text or not raw_text.strip():
        logger.warning(f"No text extracted from {file_path.name}")
        return None

    # --- Classify ---
    classification = classify_document_type(raw_text)
    doc_type = classification["doc_type"]
    is_handwritten = classification["handwritten"]
    logger.info(
        f"  Classified as: {doc_type} "
        f"(conf: {classification['confidence']}, handwritten: {is_handwritten})"
    )

    if doc_type == "unknown":
        return {
            "doc_id": file_path.stem,
            "source_file": str(file_path),
            "doc_type": doc_type,
            "classification_confidence": classification["confidence"],
            "is_handwritten": is_handwritten,
            "extracted_fields": {},
            "overall_confidence": 0,
            "raw_text_preview": raw_text[:500],
        }

    # --- Extract fields ---
    # Pass both raw_text AND image_path so the extractor can use whichever
    # OCR engine gives the best result for each field.
    extractor_func = get_extractor(doc_type)
    extracted = extractor_func(raw_text, image_path=image_path)

    # Refine confidence
    final_fields = {}
    for field_name, (value, conf) in extracted.items():
        if conf == 0 and value:
            conf = compute_field_confidence(field_name, value, is_handwritten)
        final_fields[field_name] = (value, conf)

    overall_conf = compute_overall_confidence(final_fields, is_handwritten)

    result = {
        "doc_id": file_path.stem,
        "source_file": str(file_path),
        "doc_type": doc_type,
        "classification_confidence": classification["confidence"],
        "is_handwritten": is_handwritten,
        "extracted_fields": {
            k: {"value": v[0], "confidence": v[1]} for k, v in final_fields.items()
        },
        "overall_confidence": overall_conf,
        "raw_text_preview": raw_text[:500],
    }

    logger.info(f"  Extracted {len(final_fields)} fields, overall confidence: {overall_conf}")
    return result


def run_pipeline(input_dir: Path = RAW_DIR, output_dir: Path = FINAL_DIR) -> None:
    """Run pipeline on all PDF/JPEG/PNG files in input_dir."""
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return

    supported_ext = {".pdf", ".jpg", ".jpeg", ".png"}
    files = [
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in supported_ext
    ]
    if not files:
        logger.warning(f"No PDF/JPG/PNG files found in {input_dir}")
        return

    logger.info(f"Found {len(files)} files to process")

    results = []
    for file_path in sorted(files):
        res = process_single_file(file_path)
        if res:
            results.append(res)

    # --- Save JSON output ---
    output_dir.mkdir(parents=True, exist_ok=True)
    json_output = output_dir / "extraction_output.json"
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved extraction results to {json_output}")

    # --- Generate flagging report ---
    flagging_input = []
    for res in results:
        extracted_fields = {
            k: (v["value"], v["confidence"])
            for k, v in res.get("extracted_fields", {}).items()
        }
        flagging_input.append({
            "doc_id": res["doc_id"],
            "doc_type": res["doc_type"],
            "extracted_fields": extracted_fields,
            "is_handwritten": res["is_handwritten"],
        })

    report_path = output_dir / "flagging_report.csv"
    generate_flagging_report(flagging_input, report_path)
    logger.info(f"Saved flagging report to {report_path}")

    # --- Print flagged summary ---
    all_flags = []
    for inp in flagging_input:
        from new_pipeline.confidence import flag_low_confidence_fields
        flags = flag_low_confidence_fields(
            inp["doc_id"],
            inp["doc_type"],
            inp["extracted_fields"],
            inp["is_handwritten"],
        )
        all_flags.extend(flags)
    print_flagging_summary(all_flags)

    logger.info("Pipeline completed.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Document extraction pipeline (PDF, JPEG, PNG)"
    )
    parser.add_argument(
        "--input", type=Path, default=RAW_DIR,
        help="Input directory with documents"
    )
    parser.add_argument(
        "--output", type=Path, default=FINAL_DIR,
        help="Output directory for JSON and CSV"
    )
    args = parser.parse_args()
    run_pipeline(args.input, args.output)