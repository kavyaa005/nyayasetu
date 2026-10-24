"""Print the raw extracted text of one PDF page, so we can see what the parser faces.

Run:  python scripts/inspect_pdf.py data/raw/bns.pdf 3
"""
import sys

import pdfplumber

path = sys.argv[1]
page_no = int(sys.argv[2]) if len(sys.argv) > 2 else 1

with pdfplumber.open(path) as pdf:
    total = len(pdf.pages)
    print(f"{path}: {total} pages. Showing page {page_no}.")
    print("=" * 70)
    text = pdf.pages[page_no - 1].extract_text() or "(no text found on this page)"
    print(text)
    print("=" * 70)
