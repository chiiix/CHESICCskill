from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "问卷图像识别与数据导出系统V1.0_程序鉴别材料.pdf"
FONT_DIR = Path("C:/Windows/Fonts")

SOURCE_FILES = [
    ROOT / "backend" / "main.py",
    ROOT / "backend" / "requirements.txt",
    ROOT / "src" / "App.jsx",
    ROOT / "src" / "main.jsx",
    ROOT / "src" / "styles.css",
    ROOT / "package.json",
    ROOT / "index.html",
]

PAGE_SIZE = A4
LINES_PER_PAGE = 50
LEFT = 16 * mm
RIGHT = 12 * mm
TOP = 14 * mm
BOTTOM = 14 * mm
HEADER_H = 10 * mm
FOOTER_H = 8 * mm
FONT_SIZE = 8.2
LINE_HEIGHT = 4.75 * mm
LINE_NO_W = 13 * mm


def register_fonts() -> tuple[str, str]:
    pdfmetrics.registerFont(TTFont("SoftSong", str(FONT_DIR / "simsun.ttc")))
    pdfmetrics.registerFont(TTFont("SoftMono", str(FONT_DIR / "consola.ttf")))
    return "SoftSong", "SoftMono"


def read_source_lines() -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows.append((rel, 0, f"// ===== File: {rel} ====="))
        for index, line in enumerate(text, start=1):
            rows.append((rel, index, line.replace("\t", "    ")))
        rows.append((rel, 0, ""))
    return rows


def split_visual_lines(rows: list[tuple[str, int, str]], max_chars: int) -> list[tuple[str, int, str]]:
    visual: list[tuple[str, int, str]] = []
    for file_name, line_no, text in rows:
        if len(text) <= max_chars:
            visual.append((file_name, line_no, text))
            continue
        parts = wrap(text, width=max_chars, replace_whitespace=False, drop_whitespace=False) or [""]
        for part_index, part in enumerate(parts):
            visual.append((file_name, line_no if part_index == 0 else 0, part))
    return visual


def draw_page_header(pdf: canvas.Canvas, page_no: int, total_pages: int, current_file: str, song_font: str) -> None:
    width, height = PAGE_SIZE
    pdf.setStrokeColor(colors.HexColor("#b7c2d0"))
    pdf.setLineWidth(0.5)
    pdf.line(LEFT, height - TOP - HEADER_H + 2 * mm, width - RIGHT, height - TOP - HEADER_H + 2 * mm)
    pdf.setFont(song_font, 9)
    pdf.setFillColor(colors.HexColor("#172033"))
    pdf.drawString(LEFT, height - TOP - 4 * mm, "问卷图像识别与数据导出系统V1.0 - 程序鉴别材料")
    pdf.setFont(song_font, 8)
    pdf.setFillColor(colors.HexColor("#536175"))
    pdf.drawRightString(width - RIGHT, height - TOP - 4 * mm, f"第 {page_no} / {total_pages} 页")
    pdf.drawString(LEFT, height - TOP - 8 * mm, f"当前文件：{current_file}")


def draw_page_footer(pdf: canvas.Canvas, song_font: str) -> None:
    width, _ = PAGE_SIZE
    pdf.setStrokeColor(colors.HexColor("#d7dee8"))
    pdf.setLineWidth(0.4)
    pdf.line(LEFT, BOTTOM + FOOTER_H, width - RIGHT, BOTTOM + FOOTER_H)
    pdf.setFont(song_font, 7.5)
    pdf.setFillColor(colors.HexColor("#687386"))
    pdf.drawString(LEFT, BOTTOM + 2.5 * mm, "交存方式：一般交存；源码不足60页，提交全部源程序。")


def draw_code_line(pdf: canvas.Canvas, y: float, line_no: int, text: str, mono_font: str, song_font: str) -> None:
    pdf.setFont(mono_font, FONT_SIZE)
    pdf.setFillColor(colors.HexColor("#7a8798"))
    line_label = "" if line_no == 0 else str(line_no)
    pdf.drawRightString(LEFT + LINE_NO_W - 2 * mm, y, line_label)
    pdf.setStrokeColor(colors.HexColor("#edf1f6"))
    pdf.line(LEFT + LINE_NO_W, y - 1.2 * mm, LEFT + LINE_NO_W, y + 2.2 * mm)
    pdf.setFont(song_font, FONT_SIZE)
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.drawString(LEFT + LINE_NO_W + 2 * mm, y, text)


def build_pdf() -> Path:
    song_font, mono_font = register_fonts()
    rows = read_source_lines()
    width, height = PAGE_SIZE
    max_chars = 112
    rows = split_visual_lines(rows, max_chars)
    pages = [rows[i : i + LINES_PER_PAGE] for i in range(0, len(rows), LINES_PER_PAGE)]
    total_pages = len(pages)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=PAGE_SIZE)
    pdf.setTitle("问卷图像识别与数据导出系统V1.0_程序鉴别材料")
    pdf.setAuthor("问卷图像识别与数据导出系统V1.0")

    for page_index, page_rows in enumerate(pages, start=1):
        current_file = next((row[0] for row in page_rows if row[0]), "")
        draw_page_header(pdf, page_index, total_pages, current_file, song_font)
        y = height - TOP - HEADER_H - 2 * mm
        for _, line_no, text in page_rows:
            draw_code_line(pdf, y, line_no, text, mono_font, song_font)
            y -= LINE_HEIGHT
        draw_page_footer(pdf, song_font)
        pdf.showPage()

    pdf.save()
    return OUTPUT


if __name__ == "__main__":
    print(build_pdf())
