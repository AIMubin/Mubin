"""Produce a local, reviewable evidence package for a tafsir printed-edition scan.

This tool DOES NOT validate publisher/edition identity, the printed page number,
passage boundaries, authenticity, or redistribution rights. Human review gates
remain mandatory. It never uploads PDF images or long excerpts to GitHub.
Requires optional PyMuPDF (pip install pymupdf) for local inspection only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

SCOPED_VERSES = {"4:43": 2, "17:4": 5, "18:10": 5, "33:9": 6}


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def capture(pdf, verse_id, volume, page_indices, output_dir, edition_metadata, dpi=120):
    if verse_id not in SCOPED_VERSES:
        raise ValueError("Only four Q0.3 Baghawi cases are in scope")
    if type(volume) is not int or volume != SCOPED_VERSES[verse_id]:
        raise ValueError("Volume disagrees with first-pass bibliographic mapping")
    if not isinstance(page_indices, list) or not page_indices or any(
        type(i) is not int or i < 1 for i in page_indices
    ) or len(set(page_indices)) != len(page_indices):
        raise ValueError("PDF page indices must be unique, 1-based positive integers")
    if not 96 <= dpi <= 220:
        raise ValueError("DPI outside bounded review range")
    for key in ("work", "publisher", "publication_year", "edition", "scan_url"):
        if not isinstance(edition_metadata.get(key), str) or not edition_metadata[key].strip():
            raise ValueError(f"Missing edition/scan candidate metadata: {key}")
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install PyMuPDF locally: python -m pip install pymupdf") from exc
    pdf = Path(pdf).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError("Evidence destination must not exist (immutable packages)")
    if not pdf.is_file():
        raise FileNotFoundError(pdf)
    with pdf.open("rb") as source:
        header = source.read(5)
    if header != b"%PDF-":
        raise ValueError("No valid PDF header")
    with fitz.open(pdf) as document:
        if document.needs_pass:
            raise ValueError("Password-locked PDF cannot be verified")
        if any(i > len(document) for i in page_indices):
            raise ValueError("PDF page index out of bounds")
        pages = []
        parent = output_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".mubin-print-", dir=parent))
        try:
            for i in page_indices:
                page = document[i - 1]
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                name = f"pdf-page-{i:04d}.png"
                outfile = stage / name
                pix.save(outfile)
                text = page.get_text("text")
                pages.append({
                    "pdf_page_index_1based": i,
                    "printed_page_number": None,
                    "printed_page_number_verified": False,
                    "page_image_sha256": sha256_file(outfile),
                    "rendered_width_pixels": pix.width,
                    "rendered_height_pixels": pix.height,
                    "searchable_text_detected": bool(text.strip()),
                    "page_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text.strip() else None,
                    "image_local_path": name,
                })
            report = {
                "schema_version": "0.1.0",
                "status": "PRINT_SCAN_PAGES_CAPTURED_EDITORIAL_VERIFICATION_PENDING",
                "work": "معالم التنزيل",
                "verse_id": verse_id,
                "volume": volume,
                "edition_candidate": edition_metadata,
                "pdf_file_sha256": sha256_file(pdf),
                "pdf_page_count": len(document),
                "render_engine": "PyMuPDF " + fitz.VersionBind,
                "render_dpi": dpi,
                "pages": pages,
                "printed_edition_identity_verified": False,
                "printed_pagination_verified": False,
                "verse_passage_boundaries_verified": False,
                "original_tafsir_modified": False,
                "scholarly_verified": False,
                "rights_for_redistribution_verified": False,
                "note": "Review page images locally; record visible printed page, verse range and reviewer attestation separately. Never commit scans or edited-text extracts.",
            }
            (stage / "attestation.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stage.rename(output_dir)
            return report
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--verse-id", choices=sorted(SCOPED_VERSES), required=True)
    p.add_argument("--volume", type=int, required=True)
    p.add_argument("--pages", required=True, help="comma-separated 1-based PDF page indices")
    p.add_argument("--edition-metadata", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--dpi", type=int, default=120)
    a = p.parse_args()
    page_indices = [int(v) for v in a.pages.split(",")]
    result = capture(a.pdf, a.verse_id, a.volume, page_indices, a.out_dir,
                     json.loads(a.edition_metadata.read_text(encoding="utf-8")), a.dpi)
    print(json.dumps({k: v for k, v in result.items() if k != "pages"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
