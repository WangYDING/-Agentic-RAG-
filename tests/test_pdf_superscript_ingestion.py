import tempfile
from pathlib import Path

import fitz
import pytest

from src.loader import load_pdf_pages


def _make_superscript_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()

    page.insert_text((72, 100), "resistance >= 10", fontsize=10.45)
    page.insert_text((146, 96.5), "8", fontsize=6.85)
    page.insert_text((149.5, 100), " ohm", fontsize=10.45)

    page.insert_text((72, 125), "area = 10", fontsize=10.45)
    page.insert_text((115, 121.5), "2", fontsize=6.85)
    page.insert_text((118.5, 125), " m2", fontsize=10.45)

    page.insert_text((72, 150), "ordinary integers: 108 and 2026", fontsize=10.45)
    document.save(path)
    document.close()


def test_load_pdf_pages_preserves_superscript_digits_without_rewriting_integers():
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "superscript.pdf"
        _make_superscript_pdf(pdf_path)

        _, pages = load_pdf_pages(pdf_path)

    text = pages[0].text
    assert "10⁸ ohm" in text
    assert "10² m2" in text
    assert "ordinary integers: 108 and 2026" in text
    assert "ordinary integers: 10⁸" not in text


@pytest.mark.integration
def test_real_pdf_preserves_insulation_resistance_exponent():
    pdf_path = Path("data/raw/城市轨道交通工程设计标准.pdf")
    if not pdf_path.exists():
        pytest.skip("真实规范 PDF 不可用")

    _, pages = load_pdf_pages(pdf_path)
    page_text = pages[50].text

    assert "10⁸Ω" in page_text
    assert "不应小于108Ω" not in page_text
