"""
CityAssist - stage 1 of the document pipeline.
Reads every PDF in docs/pdfs/, pulls out the text (and any tables), cuts the
text into overlapping pieces, and writes them to data/processed/chunks.json.
"""

import json
import hashlib
import re
from pathlib import Path

import pdfplumber

# --------------------------------------------------------------- settings
PDF_DIR = Path("docs/pdfs")
GUIDE_DIR = Path("docs/guides")
OUT_FILE = Path("data/processed/chunks.json")

TARGET_CHARS = 900      # roughly how big each piece should be
OVERLAP_CHARS = 150     # how much of the previous piece to repeat
MIN_CHARS = 120         # pieces shorter than this are dropped


# --------------------------------------------------------------- helpers
def format_table(table):
    """Turn a table into readable lines so a tariff keeps its label."""
    lines = []
    for row in table:
        cells = [(c or "").strip().replace("\n", " ") for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def page_to_text(page):
    """Text of one page, with any tables appended in readable form."""
    parts = []

    text = page.extract_text() or ""
    if text.strip():
        parts.append(text.strip())

    try:
        tables = page.extract_tables()
    except Exception:
        tables = []

    for table in tables:
        formatted = format_table(table)
        if formatted:
            parts.append("[table]\n" + formatted)

    return "\n\n".join(parts)


def split_text_units(text):
    """Break page text into the smallest sensible units."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    units = []
    for b in blocks:
        if len(b) <= TARGET_CHARS:
            units.append(b)
            continue
        for line in [l.strip() for l in b.split("\n") if l.strip()]:
            if len(line) <= TARGET_CHARS:
                units.append(line)
            else:
                units.extend(s.strip() for s in re.split(r"(?<=[.;:])\s+", line) if s.strip())
    return units


def split_into_chunks(text):
    units = split_text_units(text)
    chunks, current = [], ""
    for u in units:
        if not current:
            current = u
        elif len(current) + len(u) + 1 <= TARGET_CHARS:
            current = current + " " + u
        else:
            chunks.append(current)
            current = current[-OVERLAP_CHARS:] + " " + u
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if len(c.strip()) >= MIN_CHARS]

# --------------------------------------------------------------- main
def guide_chunks():
    """Cut the group's reporting guides (.txt) into pieces, in the same shape as the PDF pieces."""
    chunks = []
    for path in sorted(GUIDE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        for n, piece in enumerate(split_into_chunks(text)):
            chunks.append({
                "chunk_id": f"{path.stem}__p1__{n:03d}",
                "document": path.stem,
                "source_file": path.name,
                "page": 1,
                "text": piece,
                "chars": len(piece),
            })
    print(f"  {len(chunks)} chunks from {len(list(GUIDE_DIR.glob('*.txt')))} guide(s)")
    return chunks

def main():
    if not PDF_DIR.exists():
        raise SystemExit(f"No folder at {PDF_DIR}. Create it and add the PDFs.")

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF files found in {PDF_DIR}.")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_chunks = []
    seen = set()
    empty_pages = []

    print(f"Found {len(pdfs)} PDF file(s) in {PDF_DIR}\n")

    for pdf_path in pdfs:
        doc_name = pdf_path.stem
        doc_chunks = 0
        doc_pages = 0
        doc_empty = 0

        try:
            pdf = pdfplumber.open(pdf_path)
        except Exception as exc:
            print(f"  SKIPPED  {pdf_path.name} - could not open ({exc})")
            continue

        with pdf:
            doc_pages = len(pdf.pages)

            for page_no, page in enumerate(pdf.pages, start=1):
                text = page_to_text(page)

                if len(text.strip()) < MIN_CHARS:
                    doc_empty += 1
                    empty_pages.append(f"{pdf_path.name} p.{page_no}")
                    continue

                for piece in split_into_chunks(text):
                    key = hashlib.md5(piece.encode("utf-8")).hexdigest()
                    if key in seen:
                        continue
                    seen.add(key)

                    all_chunks.append({
                        "chunk_id": f"{doc_name}__p{page_no}__{doc_chunks:03d}",
                        "document": doc_name,
                        "source_file": pdf_path.name,
                        "page": page_no,
                        "text": piece,
                        "chars": len(piece),
                    })
                    doc_chunks += 1

        flag = f"  ({doc_empty} page(s) with no text)" if doc_empty else ""
        print(f"  {pdf_path.name}")
        print(f"      {doc_pages} pages  ->  {doc_chunks} chunks{flag}")

    all_chunks.extend(guide_chunks())

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------ summary
    total_chars = sum(c["chars"] for c in all_chunks)
    print("\n" + "-" * 55)
    print(f"Documents processed : {len(pdfs)}")
    print(f"Chunks written      : {len(all_chunks)}")
    if all_chunks:
        print(f"Average chunk size  : {total_chars // len(all_chunks)} characters")
    print(f"Saved to            : {OUT_FILE}")

    if empty_pages:
        print(f"\nPages with no readable text: {len(empty_pages)}")
        for p in empty_pages[:10]:
            print(f"   {p}")
        if len(empty_pages) > 10:
            print(f"   ...and {len(empty_pages) - 10} more")
        print("These are probably scanned images rather than proper PDFs.")




if __name__ == "__main__":
    main()