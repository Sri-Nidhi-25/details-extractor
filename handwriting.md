# Handwritten Text Handling Notes

## Approach
- Rule-based regex patterns first (tuned for common handwritten variations)
- OCR correction mapping (O→0, S→5, etc.) in `correct_ocr_digits()`
- For checkbox detection: used image analysis with fill ratio >5% indicating checked
- Low-confidence fields (<70) trigger LLM verification (Ollama with llama3.2)
- For handwritten forms specifically, threshold lowered to 60 and LLM is always invoked

## Observed Failure Cases
- Extremely cursive handwriting where characters merge (e.g., "SBI" looks like "581")
- IFSC codes with ambiguous characters (0/O, 1/I/l)
- Date formats mixing DD/MM/YYYY and MM/DD/YYYY – rule-based extraction may swap
- Checkbox detection fails if image is skewed or lighting is poor

## Mitigation
- All flagged fields go to human review (flagging report)
- LLM re-prompt (OLLAMA_RECHECK_ATTEMPTS=2) improves extraction by 15-20% on average