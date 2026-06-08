"""Configuration settings for the entire pipeline."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "Raw"
PROCESSED_DIR = DATA_DIR / "ingested"
OUTPUT_DIR = DATA_DIR / "processed"

# Files
RAW_JSONL = PROCESSED_DIR / "jobs_raw.jsonl"
EXTRACTED_JSONL = OUTPUT_DIR / "extracted_jobs.jsonl"

# final
FINAL_DIR = DATA_DIR / "final"
INPUT_JSONL = OUTPUT_DIR / "extracted_jobs.jsonl"
OUTPUT_JSON = FINAL_DIR / "searchable_jobs.json"
OUTPUT_CSV = FINAL_DIR / "searchable_jobs.csv"

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_FALLBACK_MODELS = ["llama3.2:latest", "qwen2.5-coder:7b"]
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
OLLAMA_RETRIES = int(os.getenv("OLLAMA_RETRIES", "5"))
OLLAMA_RETRY_DELAY = float(os.getenv("OLLAMA_RETRY_DELAY", "1.0"))
HEURISTIC_CONFIDENCE_THRESHOLD = int(os.getenv("HEURISTIC_CONFIDENCE_THRESHOLD", "95"))
OLLAMA_PARALLELISM = int(os.getenv("OLLAMA_PARALLELISM", "4"))
LLM_VERIFY_THRESHOLD = int(os.getenv("LLM_VERIFY_THRESHOLD", "85"))
FORCE_LLM_VERIFY = os.getenv("FORCE_LLM_VERIFY", "false").lower() in ("1", "true", "yes")
OLLAMA_RECHECK_ATTEMPTS = int(os.getenv("OLLAMA_RECHECK_ATTEMPTS", "2"))

# --- Document extraction thresholds (add these) ---
DOCUMENT_CONFIDENCE_THRESHOLD = int(os.getenv("DOCUMENT_CONFIDENCE_THRESHOLD", "70"))
HANDWRITTEN_CONFIDENCE_THRESHOLD = int(os.getenv("HANDWRITTEN_CONFIDENCE_THRESHOLD", "60"))

HANDWRITTEN_DOC_TYPES = [
    "NACH / ECS Mandate",
    "FATCA Annexure Form",
    "Benefit Illustration Declaration",
    "Moral Hazard Questionnaire",
    "Multiple Policies Consent Form",
    "Suitability Profiler Declaration"
]

DATE_PATTERNS = [
    r'(\d{2}[/-]\d{2}[/-]\d{4})',
    r'(\d{4}[/-]\d{2}[/-]\d{2})',
    r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})'
]