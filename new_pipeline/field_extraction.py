# """
# Field extractors for 10 document types.
# Supports OpenBharatOCR (primary) with fallback chain:
#   1. OpenBharatOCR
#   2. Tesseract (pytesseract)
#   3. PaddleOCR
#   4. EasyOCR  (final fallback)
# Handwritten forms use regex + heuristics.
# """

# import re
# import logging
# from typing import Dict, Tuple, Any, Optional

# logger = logging.getLogger(__name__)

# # ----------------------------------------------------------------------
# # OCR engine availability flags
# # ----------------------------------------------------------------------
# try:
#     import openbharatocr
#     OPENBHARAT_AVAILABLE = True
# except ImportError:
#     OPENBHARAT_AVAILABLE = False
#     logger.warning("OpenBharatOCR not installed. Falling back to Tesseract → PaddleOCR → EasyOCR.")

# # Tesseract (pytesseract)
# try:
#     import pytesseract
#     from PIL import Image as PILImage
#     TESSERACT_AVAILABLE = True
# except ImportError:
#     TESSERACT_AVAILABLE = False
#     logger.warning("pytesseract / Pillow not installed. Skipping Tesseract in fallback chain.")

# # PaddleOCR
# try:
#     from paddleocr import PaddleOCR as _PaddleOCR
#     PADDLEOCR_AVAILABLE = True
#     _paddle_instance = None
#     def _get_paddle():
#         global _paddle_instance
#         if _paddle_instance is None:
#             # use_angle_cls=True helps with rotated/handwritten text
#             _paddle_instance = _PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
#         return _paddle_instance
# except ImportError:
#     PADDLEOCR_AVAILABLE = False
#     logger.warning("PaddleOCR not installed. Skipping PaddleOCR in fallback chain.")

# # EasyOCR (final fallback)
# try:
#     import easyocr
#     EASYOCR_AVAILABLE = True
#     _easyocr_reader = None
#     def get_easyocr_reader():
#         global _easyocr_reader
#         if _easyocr_reader is None:
#             _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
#         return _easyocr_reader
# except ImportError:
#     EASYOCR_AVAILABLE = False
#     logger.warning("EasyOCR not installed.")

# # ----------------------------------------------------------------------
# # Helper functions for regex extraction & confidence scoring
# # ----------------------------------------------------------------------
# def extract_regex(text: str, pattern: str, default_conf: int = 80) -> Tuple[Optional[str], int]:
#     """Extract first match, return (value, confidence)."""
#     match = re.search(pattern, text, re.IGNORECASE)
#     if match:
#         value = match.group(1) if match.groups() else match.group(0)
#         return value.strip(), default_conf
#     return None, 0

# def extract_date(text: str) -> Tuple[Optional[str], int]:
#     """Extract date in common formats (DD/MM/YYYY, YYYY-MM-DD)."""
#     patterns = [
#         r'(\d{2}[/-]\d{2}[/-]\d{4})',
#         r'(\d{4}[/-]\d{2}[/-]\d{2})',
#         r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})'
#     ]
#     for pat in patterns:
#         match = re.search(pat, text, re.IGNORECASE)
#         if match:
#             return match.group(1).strip(), 85
#     return None, 0

# def extract_name_after_label(text: str, label_pattern: str) -> Tuple[Optional[str], int]:
#     """Extract name following a label (e.g., 'Name:', 'Full Name')."""
#     pat = rf'{label_pattern}\s*:?\s*([A-Za-z\s\.]{3,50})'
#     match = re.search(pat, text, re.IGNORECASE)
#     if match:
#         name = re.sub(r'\s+', ' ', match.group(1).strip())
#         if len(name) > 2:
#             return name, 85
#     return None, 0

# def compute_field_confidence(value: Any, is_handwritten: bool = False, base: int = 80) -> int:
#     """Adjust confidence based on value quality."""
#     if value is None or value == "":
#         return 0
#     val_str = str(value).strip()
#     if len(val_str) < 3:
#         base -= 20
#     alnum_ratio = sum(c.isalnum() for c in val_str) / max(len(val_str), 1)
#     if alnum_ratio < 0.6:
#         base -= 20
#     elif alnum_ratio < 0.8:
#         base -= 10
#     if re.search(r'[lI1O0]{3,}', val_str):
#         base -= 15
#     if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', val_str):     # PAN
#         base = 100
#     elif re.match(r'^\d{4}\s?\d{4}\s?\d{4}$', val_str):   # Aadhaar
#         base = 100
#     elif re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', val_str):    # IFSC
#         base = 95
#     return max(0, min(100, base))

# # ----------------------------------------------------------------------
# # OCR fallback chain: Tesseract → PaddleOCR → EasyOCR
# # Called when OpenBharatOCR is unavailable or fails for a doc type.
# # ----------------------------------------------------------------------
# def _ocr_tesseract(image_path: str) -> str:
#     """Run Tesseract OCR with configs tuned for both printed and handwritten text."""
#     if not TESSERACT_AVAILABLE or not image_path:
#         return ""
#     try:
#         img = PILImage.open(image_path)
#         # --oem 3: LSTM engine; --psm 6: assume a uniform block of text
#         # For handwritten forms, psm 4 (single column) often works better
#         configs = [
#             '--oem 3 --psm 6',   # standard printed docs
#             '--oem 3 --psm 4',   # single-column / handwritten
#             '--oem 3 --psm 11',  # sparse text (forms with gaps)
#         ]
#         best = ""
#         for cfg in configs:
#             try:
#                 out = pytesseract.image_to_string(img, config=cfg, lang='eng')
#                 if len(out.strip()) > len(best.strip()):
#                     best = out
#             except Exception:
#                 continue
#         return best.strip()
#     except Exception as e:
#         logger.debug(f"Tesseract OCR failed: {e}")
#         return ""

# def _ocr_paddle(image_path: str) -> str:
#     """Run PaddleOCR; good for mixed printed/handwritten and degraded images."""
#     if not PADDLEOCR_AVAILABLE or not image_path:
#         return ""
#     try:
#         paddle = _get_paddle()
#         result = paddle.ocr(image_path, cls=True)
#         lines = []
#         # result is list of pages; each page is list of [bbox, (text, score)]
#         if result and result[0]:
#             for line in result[0]:
#                 if line and len(line) >= 2:
#                     text_info = line[1]
#                     if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
#                         lines.append(str(text_info[0]))
#         return " ".join(lines).strip()
#     except Exception as e:
#         logger.debug(f"PaddleOCR failed: {e}")
#         return ""

# def _ocr_easyocr(image_path: str) -> str:
#     """EasyOCR — final fallback."""
#     if not EASYOCR_AVAILABLE or not image_path:
#         return ""
#     try:
#         reader = get_easyocr_reader()
#         result = reader.readtext(image_path, detail=0, paragraph=True)
#         if result:
#             return " ".join(str(x) for x in result)
#     except Exception as e:
#         logger.debug(f"EasyOCR fallback failed: {e}")
#     return ""

# def _merge_ocr_texts(*texts: str) -> str:
#     """
#     Merge results from multiple OCR engines.
#     Longer output generally means more text was recovered.
#     We concatenate all non-empty results with a separator so
#     regex patterns can match across engine outputs.
#     """
#     parts = [t.strip() for t in texts if t and t.strip()]
#     return "\n".join(parts)

# def _ocr_fallback(image_path: Optional[str]) -> str:
#     """
#     Full fallback chain: Tesseract → PaddleOCR → EasyOCR.
#     Merges all non-empty outputs so regex has the best possible
#     combined text to work with.
#     """
#     if not image_path:
#         return ""
#     tess  = _ocr_tesseract(image_path)
#     paddle = _ocr_paddle(image_path)
#     easy  = _ocr_easyocr(image_path)
#     merged = _merge_ocr_texts(tess, paddle, easy)
#     logger.debug(
#         f"OCR fallback lengths — Tesseract:{len(tess)} "
#         f"Paddle:{len(paddle)} EasyOCR:{len(easy)} Merged:{len(merged)}"
#     )
#     return merged

# # ----------------------------------------------------------------------
# # Government ID extractors (OpenBharatOCR with fallback)
# # ----------------------------------------------------------------------
# def extract_aadhaar(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     if OPENBHARAT_AVAILABLE and image_path:
#         try:
#             front = openbharatocr.front_aadhaar(image_path)
#             try:
#                 back = openbharatocr.back_aadhaar(image_path)
#                 front.update(back)
#             except:
#                 pass
#             mapped = {
#                 "Aadhaar Number": (front.get("aadhaar_number") or front.get("uid"), 100),
#                 "Full Name": (front.get("name"), 90),
#                 "Date of Birth": (front.get("dob"), 85),
#                 "Address": (front.get("address"), 75)
#             }
#             raw = _ocr_fallback(image_path) if not text else text
#             for field, (val, conf) in mapped.items():
#                 if not val:
#                     if field == "Aadhaar Number":
#                         val, conf = extract_regex(raw, r'\b(\d{4}\s?\d{4}\s?\d{4})\b', 95)
#                         if not val:
#                             val, conf = extract_regex(raw, r'\b(\d{12})\b', 90)
#                     elif field == "Full Name":
#                         val, conf = extract_name_after_label(raw, r'(?:Full\s+Name|Name)')
#                     elif field == "Date of Birth":
#                         val, conf = extract_date(raw)
#                     elif field == "Address":
#                         val, conf = extract_regex(raw, r'Address\s*:?\s*([A-Za-z0-9\s,\.\-]{10,100})', 70)
#                     mapped[field] = (val, compute_field_confidence(val, False, conf))
#             return mapped
#         except Exception as e:
#             logger.debug(f"OpenBharatOCR Aadhaar failed: {e}")
#     # Fallback chain
#     raw = _ocr_fallback(image_path) if not text else text
#     result = {}
#     aadhaar, conf = extract_regex(raw, r'\b(\d{4}\s?\d{4}\s?\d{4})\b', 95)
#     if not aadhaar:
#         aadhaar, conf = extract_regex(raw, r'\b(\d{12})\b', 90)
#     result["Aadhaar Number"] = (aadhaar, compute_field_confidence(aadhaar, False, conf))
#     name_match = re.search(r'(?:Full\s+Name|Name)[^\n]*\s+([A-Za-z\.\s]{3,50})', raw, re.IGNORECASE)
#     if name_match:
#         name = re.sub(r'\s+', ' ', name_match.group(1).strip())
#         result["Full Name"] = (name if len(name) > 2 else None, 85 if len(name) > 2 else 0)
#     else:
#         result["Full Name"] = (None, 0)
#     result["Full Name"] = (
#         result["Full Name"][0],
#         compute_field_confidence(result["Full Name"][0], False, result["Full Name"][1])
#     )
#     dob, conf = extract_date(raw)
#     result["Date of Birth"] = (dob, compute_field_confidence(dob, False, conf))
#     addr, conf = extract_regex(raw, r'Address\s*:?\s*([A-Za-z0-9\s,\.\-]{10,100})', 70)
#     result["Address"] = (addr, compute_field_confidence(addr, False, conf))
#     return result

# def extract_pan(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     if OPENBHARAT_AVAILABLE and image_path:
#         try:
#             res = openbharatocr.pan(image_path)
#             mapped = {
#                 "PAN Number": (res.get("pan_number"), 100),
#                 "Full Name": (res.get("name"), 90),
#                 "Father's Name": (res.get("father_name") or res.get("fathers_name"), 85),
#                 "Date of Birth": (res.get("dob"), 85)
#             }
#             raw = _ocr_fallback(image_path) if not text else text
#             for field, (val, conf) in mapped.items():
#                 if not val:
#                     if field == "PAN Number":
#                         val, conf = extract_regex(raw, r'([A-Z]{5}[0-9]{4}[A-Z]{1})', 100)
#                     elif field == "Full Name":
#                         val, conf = extract_name_after_label(raw, r'(?:Name|Full\s+Name)')
#                     elif field == "Father's Name":
#                         val, conf = extract_name_after_label(raw, r"(?:Father'?s?\s+Name|Father)")
#                     elif field == "Date of Birth":
#                         val, conf = extract_date(raw)
#                     mapped[field] = (val, compute_field_confidence(val, False, conf))
#             return mapped
#         except Exception as e:
#             logger.debug(f"OpenBharatOCR PAN failed: {e}")
#     raw = _ocr_fallback(image_path) if not text else text
#     result = {}
#     pan, conf = extract_regex(raw, r'([A-Z]{5}[0-9]{4}[A-Z]{1})', 100)
#     result["PAN Number"] = (pan, compute_field_confidence(pan, False, conf))
#     name, conf = extract_name_after_label(raw, r'(?:Name|Full\s+Name)')
#     result["Full Name"] = (name, compute_field_confidence(name, False, conf))
#     father, conf = extract_name_after_label(raw, r"(?:Father'?s?\s+Name|Father)")
#     result["Father's Name"] = (father, compute_field_confidence(father, False, conf))
#     dob, conf = extract_date(raw)
#     result["Date of Birth"] = (dob, compute_field_confidence(dob, False, conf))
#     return result

# def extract_driving_licence(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     if OPENBHARAT_AVAILABLE and image_path:
#         try:
#             res = openbharatocr.driving_licence(image_path)
#             mapped = {
#                 "DL Number": (res.get("dl_number"), 90),
#                 "Name": (res.get("name"), 90),
#                 "Date of Issue": (res.get("date_of_issue"), 85),
#                 "Valid Till date": (res.get("valid_till"), 85)
#             }
#             raw = _ocr_fallback(image_path) if not text else text
#             for field, (val, conf) in mapped.items():
#                 if not val:
#                     if field == "DL Number":
#                         val, conf = extract_regex(raw, r'\b([A-Z]{2}[0-9]{2,15})\b', 85)
#                     elif field == "Name":
#                         val, conf = extract_name_after_label(raw, r'(?:Name|Holder\'?s?\s+Name)')
#                     elif field == "Date of Issue":
#                         val, conf = extract_date(raw)
#                     elif field == "Valid Till date":
#                         val, conf = extract_regex(raw, r'(?:Valid\s+till|Expiry|Valid\s+upto)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 85)
#                         if not val:
#                             val, conf = extract_date(raw)
#                     mapped[field] = (val, compute_field_confidence(val, False, conf))
#             return mapped
#         except Exception as e:
#             logger.debug(f"OpenBharatOCR DL failed: {e}")
#     raw = _ocr_fallback(image_path) if not text else text
#     result = {}
#     dl, conf = extract_regex(raw, r'\b([A-Z]{2}[0-9]{2,15})\b', 85)
#     result["DL Number"] = (dl, compute_field_confidence(dl, False, conf))
#     name, conf = extract_name_after_label(raw, r'(?:Name|Holder\'?s?\s+Name)')
#     result["Name"] = (name, compute_field_confidence(name, False, conf))
#     issue, conf = extract_date(raw)
#     result["Date of Issue"] = (issue, compute_field_confidence(issue, False, conf))
#     valid, conf = extract_regex(raw, r'(?:Valid\s+till|Expiry|Valid\s+upto)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 85)
#     if not valid:
#         valid, conf = extract_date(raw)
#     result["Valid Till date"] = (valid, compute_field_confidence(valid, False, conf))
#     return result

# def extract_passport(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     if OPENBHARAT_AVAILABLE and image_path:
#         try:
#             res = openbharatocr.passport(image_path)
#             mapped = {
#                 "Passport Number": (res.get("passport_number"), 95),
#                 "Date of Birth": (res.get("dob"), 90),
#                 "Date of Expiry": (res.get("date_of_expiry"), 90),
#                 "MRZ Line 2": (res.get("mrz_line2"), 85)
#             }
#             raw = _ocr_fallback(image_path) if not text else text
#             for field, (val, conf) in mapped.items():
#                 if not val:
#                     if field == "Passport Number":
#                         val, conf = extract_regex(raw, r'\b([A-Z][0-9]{7})\b', 95)
#                     elif field == "Date of Birth":
#                         val, conf = extract_date(raw)
#                     elif field == "Date of Expiry":
#                         val, conf = extract_regex(raw, r'(?:Date\s+of\s+Expiry|Expiry\s+Date)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 90)
#                         if not val:
#                             val, conf = extract_date(raw)
#                     elif field == "MRZ Line 2":
#                         val, conf = extract_regex(raw, r'([A-Z0-9<]{44})', 80)
#                     mapped[field] = (val, compute_field_confidence(val, False, conf))
#             return mapped
#         except Exception as e:
#             logger.debug(f"OpenBharatOCR Passport failed: {e}")
#     raw = _ocr_fallback(image_path) if not text else text
#     result = {}
#     pnum, conf = extract_regex(raw, r'\b([A-Z][0-9]{7})\b', 95)
#     result["Passport Number"] = (pnum, compute_field_confidence(pnum, False, conf))
#     dob, conf = extract_date(raw)
#     result["Date of Birth"] = (dob, compute_field_confidence(dob, False, conf))
#     expiry, conf = extract_regex(raw, r'(?:Date\s+of\s+Expiry|Expiry\s+Date)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 90)
#     if not expiry:
#         expiry, conf = extract_date(raw)
#     result["Date of Expiry"] = (expiry, compute_field_confidence(expiry, False, conf))
#     mrz, conf = extract_regex(raw, r'([A-Z0-9<]{44})', 80)
#     result["MRZ Line 2"] = (mrz, compute_field_confidence(mrz, False, conf))
#     return result

# # ----------------------------------------------------------------------
# # Handwritten forms — regex & heuristics on merged OCR output
# # All four engines run; merged text passed to regex extractors.
# # ----------------------------------------------------------------------
# def extract_nach(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     # Always run full fallback chain for handwritten NACH forms
#     ocr_raw = _ocr_fallback(image_path) if image_path else ""
#     raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
#     result = {}
#     # Bank Account Number — 9-18 digits; avoid matching IFSC or dates
#     acc_match = re.search(r'(?:A/?c\.?\s*(?:No\.?|Number)?|Account\s*(?:No\.?|Number)?)\s*[:\-]?\s*(\d{9,18})', raw, re.IGNORECASE)
#     if not acc_match:
#         acc_match = re.search(r'\b(\d{9,18})\b', raw)
#     val = acc_match.group(1) if acc_match else None
#     result["Bank Account Number"] = (val, compute_field_confidence(val, True, 75))
#     # IFSC Code — strict format XXXX0XXXXXX
#     ifsc_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', raw, re.IGNORECASE)
#     val = ifsc_match.group(1).upper() if ifsc_match else None
#     result["IFSC Code"] = (val, compute_field_confidence(val, True, 85))
#     # Bank Name — extended list for insurance/NACH context
#     banks = [
#         "SBI", "STATE BANK", "HDFC", "ICICI", "AXIS", "KOTAK",
#         "PNB", "PUNJAB NATIONAL", "CANARA", "UNION", "BANK OF BARODA",
#         "BOB", "INDUSIND", "YES BANK", "IDFC", "FEDERAL", "SOUTH INDIAN",
#         "KARNATAKA", "UCO", "CENTRAL BANK", "INDIAN BANK", "IOB",
#         "INDIAN OVERSEAS", "VIJAYA", "SYNDICATE", "CORPORATION"
#     ]
#     bank = next((b for b in banks if re.search(rf'\b{re.escape(b)}\b', raw, re.IGNORECASE)), None)
#     result["Bank Name"] = (bank, compute_field_confidence(bank, True, 70))
#     # Amount — handle ₹, Rs, commas, decimals
#     amt_match = re.search(r'(?:Amount|Rs\.?|₹)\s*[:\-]?\s*([0-9]{1,3}(?:,\s*[0-9]{3})*(?:\.[0-9]{1,2})?)', raw, re.IGNORECASE)
#     if not amt_match:
#         amt_match = re.search(r'[₹Rs\.]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', raw)
#     val = amt_match.group(1).replace(' ', '') if amt_match else None
#     result["Amount (figures)"] = (val, compute_field_confidence(val, True, 75))
#     # Frequency
#     freq_map = {
#         "monthly": "Monthly", "quarterly": "Quarterly",
#         "half.?yearly": "Half-Yearly", "half.?year": "Half-Yearly",
#         "yearly": "Yearly", "annual": "Yearly", "as and when": "As and When"
#     }
#     freq = None
#     for pattern, label in freq_map.items():
#         if re.search(rf'\b{pattern}\b', raw, re.IGNORECASE):
#             freq = label
#             break
#     result["Frequency"] = (freq, compute_field_confidence(freq, True, 80))
#     return result

# def extract_fatca(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     ocr_raw = _ocr_fallback(image_path) if image_path else ""
#     raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
#     result = {}
#     # TIN / PAN
#     pan, _ = extract_regex(raw, r'([A-Z]{5}[0-9]{4}[A-Z]{1})', 90)
#     if not pan:
#         pan, _ = extract_regex(raw, r'\b(\d{9,12})\b', 70)
#     result["TIN / PAN"] = (pan, compute_field_confidence(pan, True, 80))
#     # Father's Name
#     father, _ = extract_name_after_label(raw, r"(?:Father'?s?\s+Name|Father)")
#     result["Father's Name"] = (father, compute_field_confidence(father, True, 75))
#     # Place of Birth
#     pob = re.search(r'Place\s+of\s+Birth\s*:?\s*([A-Za-z\s,]{3,50})', raw, re.IGNORECASE)
#     val = pob.group(1).strip() if pob else None
#     result["Place of Birth"] = (val, compute_field_confidence(val, True, 70))
#     # Nationality
#     nat = re.search(r'Nationality\s*:?\s*([A-Za-z]{3,20})', raw, re.IGNORECASE)
#     val = nat.group(1).strip() if nat else None
#     result["Nationality"] = (val, compute_field_confidence(val, True, 80))
#     # Policy Number
#     policy = re.search(r'Policy\s+(?:No\.?|Number)\s*:?\s*([A-Z0-9]{6,20})', raw, re.IGNORECASE)
#     if not policy:
#         policy = re.search(r'\b([A-Z]{2,4}[0-9]{6,14})\b', raw)
#     val = policy.group(1) if policy else None
#     result["Policy Number"] = (val, compute_field_confidence(val, True, 75))
#     return result

# def extract_benefit_illustration(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     ocr_raw = _ocr_fallback(image_path) if image_path else ""
#     raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
#     result = {}
#     app, _ = extract_regex(raw, r'(?:Application\s+No|App\s+No)[\s:]*([A-Z0-9]{8,20})', 80)
#     if not app:
#         app, _ = extract_regex(raw, r'\b(\d{8,12})\b', 65)
#     result["Application Number"] = (app, compute_field_confidence(app, True, 75))
#     name, _ = extract_name_after_label(raw, r"(?:Policyholder\s+Name|Name of Policyholder)")
#     result["Policyholder Name"] = (name, compute_field_confidence(name, True, 80))
#     date, _ = extract_date(raw)
#     result["Date"] = (date, compute_field_confidence(date, True, 85))
#     place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
#     val = place.group(1).strip() if place else None
#     result["Place"] = (val, compute_field_confidence(val, True, 65))
#     return result

# def extract_moral_hazard(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     ocr_raw = _ocr_fallback(image_path) if image_path else ""
#     raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
#     result = {}
#     app, _ = extract_regex(raw, r'(?:Application\s+No|App\s+No)[\s:]*([A-Z0-9]{8,20})', 80)
#     if not app:
#         app, _ = extract_regex(raw, r'\b(\d{8,12})\b', 65)
#     result["Application Number"] = (app, compute_field_confidence(app, True, 75))
#     name, _ = extract_name_after_label(raw, r"(?:Name of Life Assured|Life Assured)")
#     result["Name of Life Assured"] = (name, compute_field_confidence(name, True, 80))
#     nr = re.search(r'Nominee\s+Relationship\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
#     val = nr.group(1).strip() if nr else None
#     result["Nominee Relationship"] = (val, compute_field_confidence(val, True, 75))
#     date, _ = extract_date(raw)
#     result["Date"] = (date, compute_field_confidence(date, True, 85))
#     place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
#     val = place.group(1).strip() if place else None
#     result["Place"] = (val, compute_field_confidence(val, True, 65))
#     return result

# def extract_multiple_policies(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     ocr_raw = _ocr_fallback(image_path) if image_path else ""
#     raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
#     result = {}
#     name, _ = extract_name_after_label(raw, r"(?:Proposer\s+Name|Name of Proposer)")
#     result["Proposer Name"] = (name, compute_field_confidence(name, True, 80))
#     reasons = [
#         "Higher sum assured", "Additional coverage",
#         "Family floater", "Other"
#     ]
#     reason = next((r for r in reasons if re.search(rf'\b{re.escape(r)}\b', raw, re.IGNORECASE)), None)
#     result["Reason for Multiple Policies (selected checkbox)"] = (reason, compute_field_confidence(reason, True, 70))
#     date, _ = extract_date(raw)
#     result["Date"] = (date, compute_field_confidence(date, True, 85))
#     place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
#     val = place.group(1).strip() if place else None
#     result["Place"] = (val, compute_field_confidence(val, True, 65))
#     return result

# def extract_suitability(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
#     ocr_raw = _ocr_fallback(image_path) if image_path else ""
#     raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
#     result = {}
#     app, _ = extract_regex(raw, r'(?:Application\s+No|App\s+No)[\s:]*([A-Z0-9]{8,20})', 80)
#     if not app:
#         app, _ = extract_regex(raw, r'\b(\d{8,12})\b', 65)
#     result["Application Number"] = (app, compute_field_confidence(app, True, 75))
#     name, _ = extract_name_after_label(raw, r"(?:Name of Life Assured|Life Assured)")
#     result["Name of Life Assured"] = (name, compute_field_confidence(name, True, 80))
#     agent, _ = extract_name_after_label(raw, r"(?:Name of Agent|Agent/SP\s+Name|Agent)")
#     result["Name of Agent/SP"] = (agent, compute_field_confidence(agent, True, 80))
#     date, _ = extract_date(raw)
#     result["Date"] = (date, compute_field_confidence(date, True, 85))
#     place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
#     val = place.group(1).strip() if place else None
#     result["Place"] = (val, compute_field_confidence(val, True, 65))
#     return result

# # ----------------------------------------------------------------------
# # Dispatcher
# # ----------------------------------------------------------------------
# EXTRACTOR_MAP = {
#     "Aadhaar Card": extract_aadhaar,
#     "PAN Card": extract_pan,
#     "Driving Licence": extract_driving_licence,
#     "Passport": extract_passport,
#     "NACH / ECS Mandate": extract_nach,
#     "FATCA Annexure Form": extract_fatca,
#     "Benefit Illustration Declaration": extract_benefit_illustration,
#     "Moral Hazard Questionnaire": extract_moral_hazard,
#     "Multiple Policies Consent Form": extract_multiple_policies,
#     "Suitability Profiler Declaration": extract_suitability,
# }

# def get_extractor(doc_type: str):
#     """Return the extractor function for the given document type."""
#     return EXTRACTOR_MAP.get(doc_type, lambda text, image_path=None: {})

"""
Field extractors for 10 document types.
Supports OpenBharatOCR (primary) with fallback chain:
  1. OpenBharatOCR
  2. Tesseract (pytesseract)
  3. PaddleOCR
  4. EasyOCR  (final fallback)
Handwritten forms use regex + heuristics.
"""

import re
import logging
from typing import Dict, Tuple, Any, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# OCR engine availability flags
# ----------------------------------------------------------------------
try:
    import openbharatocr
    OPENBHARAT_AVAILABLE = True
except ImportError:
    OPENBHARAT_AVAILABLE = False
    logger.warning("OpenBharatOCR not installed. Falling back to Tesseract → PaddleOCR → EasyOCR.")

# Tesseract (pytesseract)
try:
    import pytesseract
    from PIL import Image as PILImage
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract / Pillow not installed. Skipping Tesseract in fallback chain.")

# PaddleOCR
try:
    from paddleocr import PaddleOCR as _PaddleOCR
    PADDLEOCR_AVAILABLE = True
    _paddle_instance = None
    def _get_paddle():
        global _paddle_instance
        if _paddle_instance is None:
            # use_angle_cls=True helps with rotated/handwritten text
            _paddle_instance = _PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        return _paddle_instance
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logger.warning("PaddleOCR not installed. Skipping PaddleOCR in fallback chain.")

# EasyOCR (final fallback)
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    _easyocr_reader = None
    def get_easyocr_reader():
        global _easyocr_reader
        if _easyocr_reader is None:
            _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        return _easyocr_reader
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not installed.")

# ----------------------------------------------------------------------
# Helper functions for regex extraction & confidence scoring
# ----------------------------------------------------------------------
def extract_regex(text: str, pattern: str, default_conf: int = 80) -> Tuple[Optional[str], int]:
    """Extract first match, return (value, confidence)."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        value = match.group(1) if match.groups() else match.group(0)
        return value.strip(), default_conf
    return None, 0

def extract_date(text: str) -> Tuple[Optional[str], int]:
    """Extract date in common formats (DD/MM/YYYY, YYYY-MM-DD)."""
    patterns = [
        r'(\d{2}[/-]\d{2}[/-]\d{4})',
        r'(\d{4}[/-]\d{2}[/-]\d{2})',
        r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})'
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), 85
    return None, 0

def extract_name_after_label(text: str, label_pattern: str) -> Tuple[Optional[str], int]:
    """Extract name following a label (e.g., 'Name:', 'Full Name')."""
    pat = rf'{label_pattern}\s*:?\s*([A-Za-z\s\.]{3,50})'
    match = re.search(pat, text, re.IGNORECASE)
    if match:
        name = re.sub(r'\s+', ' ', match.group(1).strip())
        if len(name) > 2:
            return name, 85
    return None, 0

def compute_field_confidence(value: Any, is_handwritten: bool = False, base: int = 80) -> int:
    """Adjust confidence based on value quality."""
    if value is None or value == "":
        return 0
    val_str = str(value).strip()
    if len(val_str) < 3:
        base -= 20
    alnum_ratio = sum(c.isalnum() for c in val_str) / max(len(val_str), 1)
    if alnum_ratio < 0.6:
        base -= 20
    elif alnum_ratio < 0.8:
        base -= 10
    if re.search(r'[lI1O0]{3,}', val_str):
        base -= 15
    if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', val_str):     # PAN
        base = 100
    elif re.match(r'^\d{4}\s?\d{4}\s?\d{4}$', val_str):   # Aadhaar
        base = 100
    elif re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', val_str):    # IFSC
        base = 95
    return max(0, min(100, base))

# ----------------------------------------------------------------------
# OCR fallback chain: Tesseract → PaddleOCR → EasyOCR
# Called when OpenBharatOCR is unavailable or fails for a doc type.
# ----------------------------------------------------------------------
def _ocr_tesseract(image_path: str) -> str:
    """Run Tesseract OCR with configs tuned for both printed and handwritten text."""
    if not TESSERACT_AVAILABLE or not image_path:
        return ""
    try:
        img = PILImage.open(image_path)
        # --oem 3: LSTM engine; --psm 6: assume a uniform block of text
        # For handwritten forms, psm 4 (single column) often works better
        configs = [
            '--oem 3 --psm 6',   # standard printed docs
            '--oem 3 --psm 4',   # single-column / handwritten
            '--oem 3 --psm 11',  # sparse text (forms with gaps)
        ]
        best = ""
        for cfg in configs:
            try:
                out = pytesseract.image_to_string(img, config=cfg, lang='eng')
                if len(out.strip()) > len(best.strip()):
                    best = out
            except Exception:
                continue
        return best.strip()
    except Exception as e:
        logger.debug(f"Tesseract OCR failed: {e}")
        return ""

def _ocr_paddle(image_path: str) -> str:
    """Run PaddleOCR; good for mixed printed/handwritten and degraded images."""
    if not PADDLEOCR_AVAILABLE or not image_path:
        return ""
    try:
        paddle = _get_paddle()
        result = paddle.ocr(image_path, cls=True)
        lines = []
        # result is list of pages; each page is list of [bbox, (text, score)]
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                        lines.append(str(text_info[0]))
        return " ".join(lines).strip()
    except Exception as e:
        logger.debug(f"PaddleOCR failed: {e}")
        return ""

def _ocr_easyocr(image_path: str) -> str:
    """EasyOCR — final fallback."""
    if not EASYOCR_AVAILABLE or not image_path:
        return ""
    try:
        reader = get_easyocr_reader()
        result = reader.readtext(image_path, detail=0, paragraph=True)
        if result:
            return " ".join(str(x) for x in result)
    except Exception as e:
        logger.debug(f"EasyOCR fallback failed: {e}")
    return ""

def _merge_ocr_texts(*texts: str) -> str:
    """
    Merge results from multiple OCR engines.
    Longer output generally means more text was recovered.
    We concatenate all non-empty results with a separator so
    regex patterns can match across engine outputs.
    """
    parts = [t.strip() for t in texts if t and t.strip()]
    return "\n".join(parts)

def _ocr_fallback(image_path: Optional[str]) -> str:
    """
    Full fallback chain: Tesseract → PaddleOCR → EasyOCR.
    Merges all non-empty outputs so regex has the best possible
    combined text to work with.
    """
    if not image_path:
        return ""
    tess  = _ocr_tesseract(image_path)
    paddle = _ocr_paddle(image_path)
    easy  = _ocr_easyocr(image_path)
    merged = _merge_ocr_texts(tess, paddle, easy)
    logger.debug(
        f"OCR fallback lengths — Tesseract:{len(tess)} "
        f"Paddle:{len(paddle)} EasyOCR:{len(easy)} Merged:{len(merged)}"
    )
    return merged

# ----------------------------------------------------------------------
# Government ID extractors (OpenBharatOCR with fallback)
# ----------------------------------------------------------------------
def extract_aadhaar(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    if OPENBHARAT_AVAILABLE and image_path:
        try:
            front = openbharatocr.front_aadhaar(image_path)
            try:
                back = openbharatocr.back_aadhaar(image_path)
                front.update(back)
            except:
                pass
            mapped = {
                "Aadhaar Number": (front.get("aadhaar_number") or front.get("uid"), 100),
                "Full Name": (front.get("name"), 90),
                "Date of Birth": (front.get("dob"), 85),
                "Address": (front.get("address"), 75)
            }
            raw = _ocr_fallback(image_path) if not text else text
            for field, (val, conf) in mapped.items():
                if not val:
                    if field == "Aadhaar Number":
                        val, conf = extract_regex(raw, r'\b(\d{4}\s?\d{4}\s?\d{4})\b', 95)
                        if not val:
                            val, conf = extract_regex(raw, r'\b(\d{12})\b', 90)
                    elif field == "Full Name":
                        val, conf = extract_name_after_label(raw, r'(?:Full\s+Name|Name)')
                    elif field == "Date of Birth":
                        val, conf = extract_date(raw)
                    elif field == "Address":
                        val, conf = extract_regex(raw, r'Address\s*:?\s*([A-Za-z0-9\s,\.\-]{10,100})', 70)
                    mapped[field] = (val, compute_field_confidence(val, False, conf))
            return mapped
        except Exception as e:
            logger.debug(f"OpenBharatOCR Aadhaar failed: {e}")
    # Fallback chain
    raw = _ocr_fallback(image_path) if not text else text
    result = {}
    aadhaar, conf = extract_regex(raw, r'\b(\d{4}\s?\d{4}\s?\d{4})\b', 95)
    if not aadhaar:
        aadhaar, conf = extract_regex(raw, r'\b(\d{12})\b', 90)
    result["Aadhaar Number"] = (aadhaar, compute_field_confidence(aadhaar, False, conf))
    name_match = re.search(r'(?:Full\s+Name|Name)[^\n]*\s+([A-Za-z\.\s]{3,50})', raw, re.IGNORECASE)
    if name_match:
        name = re.sub(r'\s+', ' ', name_match.group(1).strip())
        result["Full Name"] = (name if len(name) > 2 else None, 85 if len(name) > 2 else 0)
    else:
        result["Full Name"] = (None, 0)
    result["Full Name"] = (
        result["Full Name"][0],
        compute_field_confidence(result["Full Name"][0], False, result["Full Name"][1])
    )
    dob, conf = extract_date(raw)
    result["Date of Birth"] = (dob, compute_field_confidence(dob, False, conf))
    addr, conf = extract_regex(raw, r'Address\s*:?\s*([A-Za-z0-9\s,\.\-]{10,100})', 70)
    result["Address"] = (addr, compute_field_confidence(addr, False, conf))
    return result

def extract_pan(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    if OPENBHARAT_AVAILABLE and image_path:
        try:
            res = openbharatocr.pan(image_path)
            mapped = {
                "PAN Number": (res.get("pan_number"), 100),
                "Full Name": (res.get("name"), 90),
                "Father's Name": (res.get("father_name") or res.get("fathers_name"), 85),
                "Date of Birth": (res.get("dob"), 85)
            }
            raw = _ocr_fallback(image_path) if not text else text
            for field, (val, conf) in mapped.items():
                if not val:
                    if field == "PAN Number":
                        val, conf = extract_regex(raw, r'([A-Z]{5}[0-9]{4}[A-Z]{1})', 100)
                    elif field == "Full Name":
                        val, conf = extract_name_after_label(raw, r'(?:Name|Full\s+Name)')
                    elif field == "Father's Name":
                        val, conf = extract_name_after_label(raw, r"(?:Father'?s?\s+Name|Father)")
                    elif field == "Date of Birth":
                        val, conf = extract_date(raw)
                    mapped[field] = (val, compute_field_confidence(val, False, conf))
            return mapped
        except Exception as e:
            logger.debug(f"OpenBharatOCR PAN failed: {e}")
    raw = _ocr_fallback(image_path) if not text else text
    result = {}
    pan, conf = extract_regex(raw, r'([A-Z]{5}[0-9]{4}[A-Z]{1})', 100)
    result["PAN Number"] = (pan, compute_field_confidence(pan, False, conf))
    name, conf = extract_name_after_label(raw, r'(?:Name|Full\s+Name)')
    result["Full Name"] = (name, compute_field_confidence(name, False, conf))
    father, conf = extract_name_after_label(raw, r"(?:Father'?s?\s+Name|Father)")
    result["Father's Name"] = (father, compute_field_confidence(father, False, conf))
    dob, conf = extract_date(raw)
    result["Date of Birth"] = (dob, compute_field_confidence(dob, False, conf))
    return result

def extract_driving_licence(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    if OPENBHARAT_AVAILABLE and image_path:
        try:
            res = openbharatocr.driving_licence(image_path)
            mapped = {
                "DL Number": (res.get("dl_number"), 90),
                "Name": (res.get("name"), 90),
                "Date of Issue": (res.get("date_of_issue"), 85),
                "Valid Till date": (res.get("valid_till"), 85)
            }
            raw = _ocr_fallback(image_path) if not text else text
            for field, (val, conf) in mapped.items():
                if not val:
                    if field == "DL Number":
                        val, conf = extract_regex(raw, r'\b([A-Z]{2}[0-9]{2,15})\b', 85)
                    elif field == "Name":
                        val, conf = extract_name_after_label(raw, r'(?:Name|Holder\'?s?\s+Name)')
                    elif field == "Date of Issue":
                        val, conf = extract_date(raw)
                    elif field == "Valid Till date":
                        val, conf = extract_regex(raw, r'(?:Valid\s+till|Expiry|Valid\s+upto)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 85)
                        if not val:
                            val, conf = extract_date(raw)
                    mapped[field] = (val, compute_field_confidence(val, False, conf))
            return mapped
        except Exception as e:
            logger.debug(f"OpenBharatOCR DL failed: {e}")
    raw = _ocr_fallback(image_path) if not text else text
    result = {}
    dl, conf = extract_regex(raw, r'\b([A-Z]{2}[0-9]{2,15})\b', 85)
    result["DL Number"] = (dl, compute_field_confidence(dl, False, conf))
    name, conf = extract_name_after_label(raw, r'(?:Name|Holder\'?s?\s+Name)')
    result["Name"] = (name, compute_field_confidence(name, False, conf))
    issue, conf = extract_date(raw)
    result["Date of Issue"] = (issue, compute_field_confidence(issue, False, conf))
    valid, conf = extract_regex(raw, r'(?:Valid\s+till|Expiry|Valid\s+upto)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 85)
    if not valid:
        valid, conf = extract_date(raw)
    result["Valid Till date"] = (valid, compute_field_confidence(valid, False, conf))
    return result

def extract_passport(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    if OPENBHARAT_AVAILABLE and image_path:
        try:
            res = openbharatocr.passport(image_path)
            mapped = {
                "Passport Number": (res.get("passport_number"), 95),
                "Date of Birth": (res.get("dob"), 90),
                "Date of Expiry": (res.get("date_of_expiry"), 90),
                "MRZ Line 2": (res.get("mrz_line2"), 85)
            }
            raw = _ocr_fallback(image_path) if not text else text
            for field, (val, conf) in mapped.items():
                if not val:
                    if field == "Passport Number":
                        val, conf = extract_regex(raw, r'\b([A-Z][0-9]{7})\b', 95)
                    elif field == "Date of Birth":
                        val, conf = extract_date(raw)
                    elif field == "Date of Expiry":
                        val, conf = extract_regex(raw, r'(?:Date\s+of\s+Expiry|Expiry\s+Date)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 90)
                        if not val:
                            val, conf = extract_date(raw)
                    elif field == "MRZ Line 2":
                        val, conf = extract_regex(raw, r'([A-Z0-9<]{44})', 80)
                    mapped[field] = (val, compute_field_confidence(val, False, conf))
            return mapped
        except Exception as e:
            logger.debug(f"OpenBharatOCR Passport failed: {e}")
    raw = _ocr_fallback(image_path) if not text else text
    result = {}
    pnum, conf = extract_regex(raw, r'\b([A-Z][0-9]{7})\b', 95)
    result["Passport Number"] = (pnum, compute_field_confidence(pnum, False, conf))
    dob, conf = extract_date(raw)
    result["Date of Birth"] = (dob, compute_field_confidence(dob, False, conf))
    expiry, conf = extract_regex(raw, r'(?:Date\s+of\s+Expiry|Expiry\s+Date)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})', 90)
    if not expiry:
        expiry, conf = extract_date(raw)
    result["Date of Expiry"] = (expiry, compute_field_confidence(expiry, False, conf))
    mrz, conf = extract_regex(raw, r'([A-Z0-9<]{44})', 80)
    result["MRZ Line 2"] = (mrz, compute_field_confidence(mrz, False, conf))
    return result

# ----------------------------------------------------------------------
# Handwritten forms — regex & heuristics on merged OCR output
# All four engines run; merged text passed to regex extractors.
# ----------------------------------------------------------------------
def extract_nach(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    # Always run full fallback chain for handwritten NACH forms
    ocr_raw = _ocr_fallback(image_path) if image_path else ""
    raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
    result = {}
    # Bank Account Number — 9-18 digits; avoid matching IFSC or dates
    acc_match = re.search(r'(?:A/?c\.?\s*(?:No\.?|Number)?|Account\s*(?:No\.?|Number)?)\s*[:\-]?\s*(\d{9,18})', raw, re.IGNORECASE)
    if not acc_match:
        acc_match = re.search(r'\b(\d{9,18})\b', raw)
    val = acc_match.group(1) if acc_match else None
    result["Bank Account Number"] = (val, compute_field_confidence(val, True, 75))
    # IFSC Code — strict format XXXX0XXXXXX
    ifsc_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', raw, re.IGNORECASE)
    val = ifsc_match.group(1).upper() if ifsc_match else None
    result["IFSC Code"] = (val, compute_field_confidence(val, True, 85))
    # Bank Name — extended list for insurance/NACH context
    banks = [
        "SBI", "STATE BANK", "HDFC", "ICICI", "AXIS", "KOTAK",
        "PNB", "PUNJAB NATIONAL", "CANARA", "UNION", "BANK OF BARODA",
        "BOB", "INDUSIND", "YES BANK", "IDFC", "FEDERAL", "SOUTH INDIAN",
        "KARNATAKA", "UCO", "CENTRAL BANK", "INDIAN BANK", "IOB",
        "INDIAN OVERSEAS", "VIJAYA", "SYNDICATE", "CORPORATION"
    ]
    bank = next((b for b in banks if re.search(rf'\b{re.escape(b)}\b', raw, re.IGNORECASE)), None)
    result["Bank Name"] = (bank, compute_field_confidence(bank, True, 70))
    # Amount — multi-pattern extraction with false-positive rejection
    # Patterns ordered from most to least specific
    _AMT_PATTERNS = [
        # Explicit label + Indian comma-formatted number (5,000 / 1,50,000)
        r'(?:Amount|Rs\.?|₹)\s*(?:in\s+figures?)?\s*[:\-]?\s*([1-9][0-9]{0,2}(?:,[0-9]{2,3})+(?:\.[0-9]{2})?)',
        # Explicit label + plain number >= 3 digits
        r'(?:Amount|Rs\.?|₹)\s*(?:in\s+figures?)?\s*[:\-]?\s*([1-9][0-9]{2,}(?:\.[0-9]{2})?)',
        # Comma-formatted Indian number anywhere (1,50,000 or 5,000)
        r'\b([1-9][0-9]{0,2}(?:,[0-9]{2,3})+(?:\.[0-9]{2})?)\b',
        # Plain number 1000–9999999 (avoids account-number collisions)
        r'\b([1-9][0-9]{3,6})\b',
    ]
    # Tokens that look like amounts but are IDs (IFSC, account numbers)
    _AMT_REJECT = [
        r'^[A-Z]{4}[0-9]',   # IFSC code
        r'^\d{9,}$',          # account number (>= 9 bare digits)
    ]
    val = None
    for _pat in _AMT_PATTERNS:
        for _m in re.finditer(_pat, raw, re.IGNORECASE):
            _raw_val = _m.group(1).replace(' ', '')
            if any(re.match(_r, _raw_val) for _r in _AMT_REJECT):
                continue
            try:
                _numeric = float(_raw_val.replace(',', ''))
                if 100 <= _numeric <= 10_000_000:
                    val = _raw_val
                    break
            except ValueError:
                continue
        if val:
            break
    result["Amount (figures)"] = (val, compute_field_confidence(val, True, 75))
    # Frequency
    freq_map = {
        "monthly": "Monthly", "quarterly": "Quarterly",
        "half.?yearly": "Half-Yearly", "half.?year": "Half-Yearly",
        "yearly": "Yearly", "annual": "Yearly", "as and when": "As and When"
    }
    freq = None
    for pattern, label in freq_map.items():
        if re.search(rf'\b{pattern}\b', raw, re.IGNORECASE):
            freq = label
            break
    result["Frequency"] = (freq, compute_field_confidence(freq, True, 80))
    return result

def extract_fatca(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    ocr_raw = _ocr_fallback(image_path) if image_path else ""
    raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
    result = {}
    # TIN / PAN
    pan, _ = extract_regex(raw, r'([A-Z]{5}[0-9]{4}[A-Z]{1})', 90)
    if not pan:
        pan, _ = extract_regex(raw, r'\b(\d{9,12})\b', 70)
    result["TIN / PAN"] = (pan, compute_field_confidence(pan, True, 80))
    # Father's Name
    father, _ = extract_name_after_label(raw, r"(?:Father'?s?\s+Name|Father)")
    result["Father's Name"] = (father, compute_field_confidence(father, True, 75))
    # Place of Birth
    pob = re.search(r'Place\s+of\s+Birth\s*:?\s*([A-Za-z\s,]{3,50})', raw, re.IGNORECASE)
    val = pob.group(1).strip() if pob else None
    result["Place of Birth"] = (val, compute_field_confidence(val, True, 70))
    # Nationality
    nat = re.search(r'Nationality\s*:?\s*([A-Za-z]{3,20})', raw, re.IGNORECASE)
    val = nat.group(1).strip() if nat else None
    result["Nationality"] = (val, compute_field_confidence(val, True, 80))
    # Policy Number
    policy = re.search(r'Policy\s+(?:No\.?|Number)\s*:?\s*([A-Z0-9]{6,20})', raw, re.IGNORECASE)
    if not policy:
        policy = re.search(r'\b([A-Z]{2,4}[0-9]{6,14})\b', raw)
    val = policy.group(1) if policy else None
    result["Policy Number"] = (val, compute_field_confidence(val, True, 75))
    return result

def extract_benefit_illustration(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    ocr_raw = _ocr_fallback(image_path) if image_path else ""
    raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
    result = {}
    app, _ = extract_regex(raw, r'(?:Application\s+No|App\s+No)[\s:]*([A-Z0-9]{8,20})', 80)
    if not app:
        app, _ = extract_regex(raw, r'\b(\d{8,12})\b', 65)
    result["Application Number"] = (app, compute_field_confidence(app, True, 75))
    name, _ = extract_name_after_label(raw, r"(?:Policyholder\s+Name|Name of Policyholder)")
    result["Policyholder Name"] = (name, compute_field_confidence(name, True, 80))
    date, _ = extract_date(raw)
    result["Date"] = (date, compute_field_confidence(date, True, 85))
    place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
    val = place.group(1).strip() if place else None
    result["Place"] = (val, compute_field_confidence(val, True, 65))
    return result

def extract_moral_hazard(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    ocr_raw = _ocr_fallback(image_path) if image_path else ""
    raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
    result = {}
    app, _ = extract_regex(raw, r'(?:Application\s+No|App\s+No)[\s:]*([A-Z0-9]{8,20})', 80)
    if not app:
        app, _ = extract_regex(raw, r'\b(\d{8,12})\b', 65)
    result["Application Number"] = (app, compute_field_confidence(app, True, 75))
    name, _ = extract_name_after_label(raw, r"(?:Name of Life Assured|Life Assured)")
    result["Name of Life Assured"] = (name, compute_field_confidence(name, True, 80))
    nr = re.search(r'Nominee\s+Relationship\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
    val = nr.group(1).strip() if nr else None
    result["Nominee Relationship"] = (val, compute_field_confidence(val, True, 75))
    date, _ = extract_date(raw)
    result["Date"] = (date, compute_field_confidence(date, True, 85))
    place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
    val = place.group(1).strip() if place else None
    result["Place"] = (val, compute_field_confidence(val, True, 65))
    return result

def extract_multiple_policies(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    ocr_raw = _ocr_fallback(image_path) if image_path else ""
    raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
    result = {}
    name, _ = extract_name_after_label(raw, r"(?:Proposer\s+Name|Name of Proposer)")
    result["Proposer Name"] = (name, compute_field_confidence(name, True, 80))
    reasons = [
        "Higher sum assured", "Additional coverage",
        "Family floater", "Other"
    ]
    reason = next((r for r in reasons if re.search(rf'\b{re.escape(r)}\b', raw, re.IGNORECASE)), None)
    result["Reason for Multiple Policies (selected checkbox)"] = (reason, compute_field_confidence(reason, True, 70))
    date, _ = extract_date(raw)
    result["Date"] = (date, compute_field_confidence(date, True, 85))
    place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
    val = place.group(1).strip() if place else None
    result["Place"] = (val, compute_field_confidence(val, True, 65))
    return result

def extract_suitability(text: str, image_path: Optional[str] = None) -> Dict[str, Tuple[Any, int]]:
    ocr_raw = _ocr_fallback(image_path) if image_path else ""
    raw = _merge_ocr_texts(text, ocr_raw) if text else ocr_raw
    result = {}
    app, _ = extract_regex(raw, r'(?:Application\s+No|App\s+No)[\s:]*([A-Z0-9]{8,20})', 80)
    if not app:
        app, _ = extract_regex(raw, r'\b(\d{8,12})\b', 65)
    result["Application Number"] = (app, compute_field_confidence(app, True, 75))
    name, _ = extract_name_after_label(raw, r"(?:Name of Life Assured|Life Assured)")
    result["Name of Life Assured"] = (name, compute_field_confidence(name, True, 80))
    agent, _ = extract_name_after_label(raw, r"(?:Name of Agent|Agent/SP\s+Name|Agent)")
    result["Name of Agent/SP"] = (agent, compute_field_confidence(agent, True, 80))
    date, _ = extract_date(raw)
    result["Date"] = (date, compute_field_confidence(date, True, 85))
    place = re.search(r'Place\s*:?\s*([A-Za-z\s]{3,30})', raw, re.IGNORECASE)
    val = place.group(1).strip() if place else None
    result["Place"] = (val, compute_field_confidence(val, True, 65))
    return result

# ----------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------
EXTRACTOR_MAP = {
    "Aadhaar Card": extract_aadhaar,
    "PAN Card": extract_pan,
    "Driving Licence": extract_driving_licence,
    "Passport": extract_passport,
    "NACH / ECS Mandate": extract_nach,
    "FATCA Annexure Form": extract_fatca,
    "Benefit Illustration Declaration": extract_benefit_illustration,
    "Moral Hazard Questionnaire": extract_moral_hazard,
    "Multiple Policies Consent Form": extract_multiple_policies,
    "Suitability Profiler Declaration": extract_suitability,
}

def get_extractor(doc_type: str):
    """Return the extractor function for the given document type."""
    return EXTRACTOR_MAP.get(doc_type, lambda text, image_path=None: {})