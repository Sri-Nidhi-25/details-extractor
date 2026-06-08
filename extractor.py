# """
# File extraction module for PDF and images.
# OCR priority: EasyOCR (primary) → PaddleOCR (fallback)
# Scanned PDFs: rendered via PyMuPDF (no poppler needed) → same OCR chain.
# """

# import os
# import logging
# import tempfile
# from typing import Optional
# from PIL import Image, ImageOps

# # PDF text extraction
# try:
#     from PyPDF2 import PdfReader
#     PDF_AVAILABLE = True
# except ImportError:
#     PDF_AVAILABLE = False

# # PyMuPDF — renders PDF pages to images without poppler
# try:
#     import fitz  # pip install pymupdf
#     PYMUPDF_AVAILABLE = True
# except ImportError:
#     PYMUPDF_AVAILABLE = False
#     logging.getLogger(__name__).warning(
#         "PyMuPDF not installed. Scanned PDFs won't be OCR'd. "
#         "Fix: pip install pymupdf"
#     )

# logger = logging.getLogger(__name__)

# # Global OCR readers
# _easyocr_reader = None
# _paddle_ocr = None


# def _get_easyocr():
#     """Lazy load EasyOCR reader."""
#     global _easyocr_reader
#     if _easyocr_reader is not None:
#         return _easyocr_reader if _easyocr_reader is not False else None
#     try:
#         import easyocr
#         _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
#         logger.info("EasyOCR initialized")
#         return _easyocr_reader
#     except ImportError:
#         logger.warning("EasyOCR not installed. Run: pip install easyocr")
#         _easyocr_reader = False
#         return None
#     except Exception as e:
#         logger.error(f"EasyOCR init failed: {e}")
#         _easyocr_reader = False
#         return None


# def _get_paddle_ocr():
#     """Lazy load PaddleOCR as fallback."""
#     global _paddle_ocr
#     if _paddle_ocr is not None:
#         return _paddle_ocr if _paddle_ocr is not False else None
#     try:
#         import warnings
#         warnings.filterwarnings("ignore", category=UserWarning)
#         os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'
#         from paddleocr import PaddleOCR
#         _paddle_ocr = PaddleOCR(lang='en', use_angle_cls=False, device='cpu')
#         logger.info("PaddleOCR initialized (fallback)")
#         return _paddle_ocr
#     except ImportError:
#         logger.debug("PaddleOCR not installed (optional)")
#         _paddle_ocr = False
#         return None
#     except Exception as e:
#         logger.warning(f"PaddleOCR init failed: {e}")
#         _paddle_ocr = False
#         return None


# def _run_ocr_on_image_path(file_path: str) -> Optional[str]:
#     """
#     Run EasyOCR → PaddleOCR on a single image file path.
#     Returns merged text from both engines or None.
#     """
#     texts = []

#     # --- EasyOCR ---
#     easy = _get_easyocr()
#     if easy:
#         try:
#             result = easy.readtext(file_path, detail=0, paragraph=False)
#             if result:
#                 text = " ".join(str(item) for item in result).strip()
#                 if text:
#                     logger.debug(f"EasyOCR got {len(text)} chars")
#                     texts.append(text)
#         except Exception as e:
#             logger.debug(f"EasyOCR failed on {file_path}: {e}")

#     # --- PaddleOCR ---
#     paddle = _get_paddle_ocr()
#     if paddle:
#         try:
#             result = paddle.ocr(file_path)
#             if result and result[0]:
#                 blocks = [line[1][0] for line in result[0] if line and len(line) >= 2]
#                 text = " ".join(blocks).strip()
#                 if text:
#                     logger.debug(f"PaddleOCR got {len(text)} chars")
#                     texts.append(text)
#         except Exception as e:
#             logger.debug(f"PaddleOCR failed on {file_path}: {e}")

#     return "\n".join(texts) if texts else None


# def extract_image(file_path: str) -> Optional[str]:
#     """Extract text from image using EasyOCR first, then PaddleOCR."""
#     text = _run_ocr_on_image_path(file_path)
#     if text:
#         logger.info(f"OCR extracted text from image: {file_path}")
#         return text
#     logger.warning(f"No text extracted from image {file_path}")
#     return None


# def _pdf_render_and_ocr(file_path: str) -> Optional[str]:
#     """
#     Render each PDF page to a PNG via PyMuPDF (no poppler needed),
#     then OCR with EasyOCR + PaddleOCR.
#     """
#     if not PYMUPDF_AVAILABLE:
#         logger.warning(
#             f"PyMuPDF not available — cannot OCR scanned PDF {file_path}. "
#             "Run: pip install pymupdf"
#         )
#         return None

#     try:
#         doc = fitz.open(file_path)
#     except Exception as e:
#         logger.error(f"PyMuPDF could not open {file_path}: {e}")
#         return None

#     all_text = []
#     # mat=fitz.Matrix(2, 2) → 2× zoom = ~144 dpi, enough for OCR
#     # Use 3× (216 dpi) for better accuracy on small or handwritten text
#     zoom = fitz.Matrix(3, 3)

#     with tempfile.TemporaryDirectory() as tmpdir:
#         for page_num in range(len(doc)):
#             try:
#                 page = doc[page_num]
#                 pix = page.get_pixmap(matrix=zoom, colorspace=fitz.csRGB)
#                 img_path = os.path.join(tmpdir, f"page_{page_num}.png")
#                 pix.save(img_path)
#                 page_text = _run_ocr_on_image_path(img_path)
#                 if page_text and page_text.strip():
#                     all_text.append(page_text.strip())
#                     logger.debug(
#                         f"  PDF page {page_num+1}: OCR got {len(page_text)} chars"
#                     )
#                 else:
#                     logger.debug(f"  PDF page {page_num+1}: no text from OCR")
#             except Exception as e:
#                 logger.warning(f"  PDF page {page_num+1} render/OCR failed: {e}")

#     doc.close()

#     if all_text:
#         combined = "\n".join(all_text)
#         logger.info(
#             f"Scanned PDF OCR complete: {len(doc)} page(s), "
#             f"{len(combined)} chars"
#         )
#         return combined

#     logger.warning(f"Scanned PDF OCR produced no text: {file_path}")
#     return None


# def extract_pdf(file_path: str) -> Optional[str]:
#     """
#     Extract text from PDF.
#     Strategy:
#       1. PyPDF2 native text extraction (instant, zero OCR cost).
#          Works for digitally-created PDFs.
#       2. If no text found → PyMuPDF page render + EasyOCR/PaddleOCR.
#          Works for scanned PDFs and image-only PDFs.
#          No poppler required.
#     """
#     # --- Step 1: native text (digital PDFs) ---
#     if PDF_AVAILABLE:
#         try:
#             reader = PdfReader(file_path)
#             text_parts = []
#             for page in reader.pages:
#                 extracted = page.extract_text()
#                 if extracted and extracted.strip():
#                     text_parts.append(extracted)
#             full_text = "\n".join(text_parts).strip()
#             if full_text:
#                 logger.info(f"PyPDF2 native text extracted from {file_path}")
#                 return full_text
#         except Exception as e:
#             logger.warning(f"PyPDF2 failed on {file_path}: {e}")
#     else:
#         logger.warning("PyPDF2 not installed — skipping native text extraction.")

#     # --- Step 2: scanned PDF → render → OCR ---
#     logger.info(f"No native text found; running scanned-page OCR on {file_path}")
#     return _pdf_render_and_ocr(file_path)


"""
File extraction module for PDF and images.
OCR priority: EasyOCR (primary) → PaddleOCR (fallback)
Scanned PDFs: rendered via PyMuPDF (no poppler needed) → same OCR chain.
"""

import os
import logging
import tempfile
from typing import Optional
from PIL import Image, ImageOps

# PDF text extraction
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# PyMuPDF — renders PDF pages to images without poppler
try:
    import fitz  # pip install pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "PyMuPDF not installed. Scanned PDFs won't be OCR'd. "
        "Fix: pip install pymupdf"
    )

logger = logging.getLogger(__name__)

# Global OCR readers
_easyocr_reader = None
_paddle_ocr = None


def _get_easyocr():
    """Lazy load EasyOCR reader."""
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader if _easyocr_reader is not False else None
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        logger.info("EasyOCR initialized")
        return _easyocr_reader
    except ImportError:
        logger.warning("EasyOCR not installed. Run: pip install easyocr")
        _easyocr_reader = False
        return None
    except Exception as e:
        logger.error(f"EasyOCR init failed: {e}")
        _easyocr_reader = False
        return None


def _get_paddle_ocr():
    """Lazy load PaddleOCR as fallback."""
    global _paddle_ocr
    if _paddle_ocr is not None:
        return _paddle_ocr if _paddle_ocr is not False else None
    try:
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'
        from paddleocr import PaddleOCR
        _paddle_ocr = PaddleOCR(lang='en', use_angle_cls=False, device='cpu')
        logger.info("PaddleOCR initialized (fallback)")
        return _paddle_ocr
    except ImportError:
        logger.debug("PaddleOCR not installed (optional)")
        _paddle_ocr = False
        return None
    except Exception as e:
        logger.warning(f"PaddleOCR init failed: {e}")
        _paddle_ocr = False
        return None


def _run_ocr_on_image_path(file_path: str) -> Optional[str]:
    """
    Run EasyOCR → PaddleOCR on a single image file path.
    Returns merged text from both engines or None.
    """
    texts = []

    # --- EasyOCR ---
    easy = _get_easyocr()
    if easy:
        try:
            result = easy.readtext(file_path, detail=0, paragraph=False)
            if result:
                text = " ".join(str(item) for item in result).strip()
                if text:
                    logger.debug(f"EasyOCR got {len(text)} chars")
                    texts.append(text)
        except Exception as e:
            logger.debug(f"EasyOCR failed on {file_path}: {e}")

    # --- PaddleOCR ---
    paddle = _get_paddle_ocr()
    if paddle:
        try:
            result = paddle.ocr(file_path)
            if result and result[0]:
                blocks = [line[1][0] for line in result[0] if line and len(line) >= 2]
                text = " ".join(blocks).strip()
                if text:
                    logger.debug(f"PaddleOCR got {len(text)} chars")
                    texts.append(text)
        except Exception as e:
            logger.debug(f"PaddleOCR failed on {file_path}: {e}")

    return "\n".join(texts) if texts else None


def extract_image(file_path: str) -> Optional[str]:
    """Extract text from image using EasyOCR first, then PaddleOCR."""
    text = _run_ocr_on_image_path(file_path)
    if text:
        logger.info(f"OCR extracted text from image: {file_path}")
        return text
    logger.warning(f"No text extracted from image {file_path}")
    return None


def _pdf_render_and_ocr(file_path: str) -> Optional[str]:
    """
    Render each PDF page to a PNG via PyMuPDF (no poppler needed),
    then OCR with EasyOCR + PaddleOCR.
    """
    if not PYMUPDF_AVAILABLE:
        logger.warning(
            f"PyMuPDF not available — cannot OCR scanned PDF {file_path}. "
            "Run: pip install pymupdf"
        )
        return None

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        logger.error(f"PyMuPDF could not open {file_path}: {e}")
        return None

    all_text = []
    # mat=fitz.Matrix(2, 2) → 2× zoom = ~144 dpi, enough for OCR
    # Use 3× (216 dpi) for better accuracy on small or handwritten text
    zoom = fitz.Matrix(3, 3)

    with tempfile.TemporaryDirectory() as tmpdir:
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                pix = page.get_pixmap(matrix=zoom, colorspace=fitz.csRGB)
                img_path = os.path.join(tmpdir, f"page_{page_num}.png")
                pix.save(img_path)
                page_text = _run_ocr_on_image_path(img_path)
                if page_text and page_text.strip():
                    all_text.append(page_text.strip())
                    logger.debug(
                        f"  PDF page {page_num+1}: OCR got {len(page_text)} chars"
                    )
                else:
                    logger.debug(f"  PDF page {page_num+1}: no text from OCR")
            except Exception as e:
                logger.warning(f"  PDF page {page_num+1} render/OCR failed: {e}")

    page_count = len(doc)  # capture before close
    doc.close()

    if all_text:
        combined = "\n".join(all_text)
        logger.info(
            f"Scanned PDF OCR complete: {page_count} page(s), "
            f"{len(combined)} chars"
        )
        return combined

    logger.warning(f"Scanned PDF OCR produced no text: {file_path}")
    return None


def extract_pdf(file_path: str) -> Optional[str]:
    """
    Extract text from PDF.
    Strategy:
      1. PyPDF2 native text extraction (instant, zero OCR cost).
         Works for digitally-created PDFs.
      2. If no text found → PyMuPDF page render + EasyOCR/PaddleOCR.
         Works for scanned PDFs and image-only PDFs.
         No poppler required.
    """
    # --- Step 1: native text (digital PDFs) ---
    if PDF_AVAILABLE:
        try:
            reader = PdfReader(file_path)
            text_parts = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    text_parts.append(extracted)
            full_text = "\n".join(text_parts).strip()
            if full_text:
                logger.info(f"PyPDF2 native text extracted from {file_path}")
                return full_text
        except Exception as e:
            logger.warning(f"PyPDF2 failed on {file_path}: {e}")
    else:
        logger.warning("PyPDF2 not installed — skipping native text extraction.")

    # --- Step 2: scanned PDF → render → OCR ---
    logger.info(f"No native text found; running scanned-page OCR on {file_path}")
    return _pdf_render_and_ocr(file_path)