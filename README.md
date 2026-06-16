# Document Extraction Pipeline

A modular pipeline that classifies 10 types of identity and insurance documents, extracts specific fields, assigns confidence scores per field, and flags low-confidence extractions for human review. Designed for insurance onboarding and KYC automation.

---

## 📁 Recommended Repository Structure

```text
document-extraction-pipeline/
│
├── Data/
│   ├── Raw/                         (place input PDFs/images here)
│   ├── final/                       (output: extraction_output.json, flagging_report.csv, performance_report.json)
│   └── ground_truth/                (optional – for evaluation, JSON per doc)
│
├── new_pipeline/                    (main pipeline modules)
│   ├── __init__.py
│   ├── classification.py
│   ├── field_extractors.py
│   ├── confidence.py
│   └── pipeline.py
│
├── extractor.py                     (PDF / image OCR with Tesseract, Paddle, EasyOCR fallback)
├── logger.py                        (logging setup)
├── config.py                        (configuration constants)
├── utils.py                         (helper functions, e.g., normalize_job_id – optional)
├── performance_report.py            (script to generate performance summary)
├── evaluate.py                      (optional – compare with ground truth)
├── requirements.txt
├── LICENSE                          (choose MIT or Apache 2.0)
├── .gitignore                       (ignore __pycache__, Data/, venv/, etc.)
└── README.md
```

You can keep the original job-extraction files (`data_prep.py`, `field_extraction.py`, etc.) in the root if you want, but for clarity, move them into a separate folder like `legacy/` or remove them if they are not needed for this task.

---

## ✨ Features

- **Document classification** – identifies Aadhaar, PAN, Driving Licence, Passport, NACH Mandate, FATCA, Benefit Illustration, Moral Hazard, Multiple Policies, and Suitability Profiler forms.
- **Field extraction** – extracts 40+ fields including Aadhaar number, PAN, IFSC, bank account numbers, dates, names, and place names.
- **Per-field confidence** – each extracted value receives a 0–100 confidence score based on OCR quality, pattern matching, and field length.
- **Flagging report** – automatically lists fields below threshold (70 for printed, 60 for handwritten) for manual review.
- **Multi-engine OCR** – tries Tesseract, PaddleOCR, and EasyOCR in fallback order to maximise text extraction from images and scanned PDFs.
- **Scanned PDF support** – converts PDF pages to images and applies the same OCR chain.

---

## 📋 Requirements

- Python 3.8+
- Tesseract OCR (system binary) – install guide:
  https://github.com/UB-Mannheim/tesseract/wiki
- Poppler (for PDF-to-image conversion) – download:
  https://github.com/oschwartz10612/poppler-windows/releases

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## ⚙️ Installation

1. Clone the repository:

```bash
git clone https://github.com/[your-username]/document-extraction-pipeline.git
cd document-extraction-pipeline
```

2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Ensure Tesseract is installed and added to your PATH.

(Set `TESSERACT_CMD` environment variable if needed.)

4. For scanned PDFs, install Poppler and add its `bin` folder to your PATH.

---

## 🚀 Usage

1. Place your documents (PDF, PNG, JPEG) inside `Data/Raw/`.

2. Run the pipeline:

```bash
python -m new_pipeline.pipeline --input Data/Raw --output Data/final
```

3. Find results in `Data/final/`:

- `extraction_output.json` – structured JSON with all extracted fields and confidence.
- `flagging_report.csv` – fields that need human review.
- `performance_report.json` – overall extraction statistics (run `python performance_report.py` to generate).

4. (Optional) Evaluate against ground truth:

- Create JSON files in `Data/ground_truth/` (named same as `doc_id`).
- Run:

```bash
python evaluate.py
```

to see accuracy.

---

## 🔧 Configuration

Edit `config.py` to adjust:

- `DOCUMENT_CONFIDENCE_THRESHOLD` – threshold for printed documents (default 70).
- `HANDWRITTEN_CONFIDENCE_THRESHOLD` – threshold for handwritten forms (default 60).
- `HANDWRITTEN_DOC_TYPES` – list of document types considered handwritten.

---

## 📊 Results Summary (on provided test set)

- **Documents processed:** 12 (including 2 scanned PDFs)
- **Fields extracted:** 25 / 53 (47%)
- **Fields flagged for review:** 28 (53%)
- **Average confidence:** 38
- **Flagging report** successfully captured the most uncertain fields (e.g., amount on NACH mandate read as "42", confidence 55).

The pipeline reliably extracts printed fields but struggles with handwritten text – exactly what the flagging mechanism is designed to catch.

---

## 🔮 Future Improvements

- Replace EasyOCR with a specialised handwriting-trained model (e.g., TrOCR or Google Document AI).
- Add image preprocessing (deskew, binarisation) before OCR.
- Use a vision language model (e.g., Ovis, Qwen-VL) as a final fallback for low-confidence handwritten fields.
- Convert PDFs with higher DPI (600) for better OCR.

---

## 📦 requirements.txt

```txt
PyPDF2>=3.0.0
pytesseract>=0.3.10
Pillow>=10.0.0
paddlepaddle
paddleocr
opencv-python
easyocr>=1.7.0
pdf2image>=1.16.0
numpy
```

---

## 🧹 .gitignore

```gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*.so

# Virtual environments
venv/
env/
data_extractor_venv/

# Data directories (ignore input and output if you don't want to commit them)
Data/Raw/
Data/final/
Data/processed/
Data/ingested/

# Logs and debug files
*.log
*.txt

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

---

## 🚀 Pushing to GitHub

1. Create a new repository on GitHub (do NOT initialise with README, .gitignore, or license – add them manually).

2. Initialise your local project:

```bash
git init
git add .
git commit -m "Initial commit: document extraction pipeline"
git remote add origin https://github.com/[your-username]/document-extraction-pipeline.git
git push -u origin main
```

---

## 📊 Final Deliverables for the Internship

When submitting, you can provide:

- A link to your GitHub repository (best, shows code quality).
- Or attach the following files:
  - `extraction_output.json`
  - `flagging_report.csv`
  - `performance_report.json`
  - A PDF with your performance summary (the email drafted earlier).

You can also add a `demo/` folder with sample inputs/outputs (but keep them small).

---

## 📄 License

[MIT](LICENSE)

---

## 🙏 Acknowledgements

Built with Python, OpenCV, Tesseract, PaddleOCR, EasyOCR, and PyPDF2.
