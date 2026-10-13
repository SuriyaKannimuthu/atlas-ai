"""Small layout toolkit on top of ReportLab for the Atlas AI design document.

Provides fonts, styles, page decoration, tables, callouts, code blocks, and a tiny
box-and-arrow diagram language. Content lives in `build_design_doc.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

# --- palette -----------------------------------------------------------------------------
NAVY = colors.HexColor("#0b1030")
INK = colors.HexColor("#1f2433")
INK_2 = colors.HexColor("#4a5168")
INK_3 = colors.HexColor("#7c839b")
LINE = colors.HexColor("#d9dce7")
SOFT = colors.HexColor("#f4f6fb")
BLUE = colors.HexColor("#2563eb")
BLUE_SOFT = colors.HexColor("#e8effe")
VIOLET = colors.HexColor("#7c3aed")
VIOLET_SOFT = colors.HexColor("#f1ebfe")
GREEN = colors.HexColor("#15803d")
GREEN_SOFT = colors.HexColor("#e7f6ec")
AMBER = colors.HexColor("#b45309")
AMBER_SOFT = colors.HexColor("#fdf3e3")
RED = colors.HexColor("#b91c1c")
RED_SOFT = colors.HexColor("#fdecec")
CYAN = colors.HexColor("#0e7490")
CYAN_SOFT = colors.HexColor("#e3f5f8")


# --- fonts -------------------------------------------------------------------------------
def _register_fonts() -> tuple[str, str, str, str]:
    """Prefer Segoe UI / Consolas (Windows), then DejaVu, then the PDF base fonts."""
    candidates = [
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf",
         "C:/Windows/Fonts/segoeuii.ttf", "C:/Windows/Fonts/consola.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    for regular, bold, italic, mono in candidates:
        if all(Path(p).exists() for p in (regular, bold, italic, mono)):
            pdfmetrics.registerFont(TTFont("Body", regular))
            pdfmetrics.registerFont(TTFont("Body-Bold", bold))
            pdfmetrics.registerFont(TTFont("Body-Italic", italic))
            pdfmetrics.registerFont(TTFont("Mono", mono))
            pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                                          italic="Body-Italic", boldItalic="Body-Bold")
            return "Body", "Body-Bold", "Body-Italic", "Mono"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


FONT, FONT_BOLD, FONT_ITALIC, FONT_MONO = _register_fonts()

# --- styles ------------------------------------------------------------------------------
BODY = ParagraphStyle("body", fontName=FONT, fontSize=9.6, leading=14.2, textColor=INK,
                      spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.2, leading=11.5, textColor=INK_2,
                       spaceAfter=0)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.3, leading=11.4, spaceAfter=0)
CELL_HEAD = ParagraphStyle("cellhead", parent=CELL, fontName=FONT_BOLD, textColor=NAVY)
CELL_MONO = ParagraphStyle("cellmono", parent=CELL, fontName=FONT_MONO, fontSize=7.6,
                           leading=10.6)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=13, bulletIndent=3, spaceAfter=3)
H1 = ParagraphStyle("h1", fontName=FONT_BOLD, fontSize=19, leading=24, textColor=NAVY,
                    spaceBefore=4, spaceAfter=10, keepWithNext=1)
H2 = ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=13, leading=17, textColor=NAVY,
                    spaceBefore=12, spaceAfter=6, keepWithNext=1)
H3 = ParagraphStyle("h3", fontName=FONT_BOLD, fontSize=10.6, leading=14, textColor=BLUE,
                    spaceBefore=9, spaceAfter=4, keepWithNext=1)
CAPTION = ParagraphStyle("caption", parent=SMALL, alignment=TA_CENTER, textColor=INK_3,
                         spaceBefore=4, spaceAfter=10)
CODE = ParagraphStyle("code", fontName=FONT_MONO, fontSize=7.7, leading=10.4, textColor=INK)
TOC_STYLES = [
    ParagraphStyle("toc1", fontName=FONT_BOLD, fontSize=9.6, leading=14.5, textColor=NAVY,
                   leftIndent=0),
    ParagraphStyle("toc2", fontName=FONT, fontSize=8.4, leading=11.2, textColor=INK_2,
                   leftIndent=14),
]


# --- document ----------------------------------------------------------------------------
class DesignDoc(BaseDocTemplate):
    """Doc template that feeds headings into the TOC and the PDF outline."""

    def __init__(self, path: str, *, title: str, subtitle: str, meta: dict[str, str]):
        super().__init__(path, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                         topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM, title=title,
                         author=meta.get("Author", ""), subject=subtitle)
        self.doc_title, self.subtitle, self.meta = title, subtitle, meta
        frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
                      id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate("cover", frames=[frame], onPage=self._cover),
            PageTemplate("body", frames=[frame], onPage=self._decorate),
        ])
        self._heading_seq = 0

    def beforeDocument(self) -> None:
        # multiBuild renders several passes; keys must be identical in each for the TOC to settle.
        self._heading_seq = 0

    def afterFlowable(self, flowable: Flowable) -> None:
        level = getattr(flowable, "toc_level", None)
        if level is None:
            return
        text = flowable.getPlainText()
        key = f"h{self._heading_seq}"
        self._heading_seq += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, text, self.page, key))

    def _decorate(self, canv, doc) -> None:  # noqa: ANN001
        canv.saveState()
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.6)
        canv.line(MARGIN_X, PAGE_H - 14 * mm, PAGE_W - MARGIN_X, PAGE_H - 14 * mm)
        canv.setFont(FONT_BOLD, 7.8)
        canv.setFillColor(NAVY)
        canv.drawString(MARGIN_X, PAGE_H - 11.5 * mm, "ATLAS AI")
        canv.setFont(FONT, 7.8)
        canv.setFillColor(INK_3)
        canv.drawString(MARGIN_X + 15 * mm, PAGE_H - 11.5 * mm, "Technical Design Document")
        canv.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 11.5 * mm,
                             f"Version {self.meta.get('Version', '')}  |  "
                             f"{self.meta.get('Status', '')}")
        canv.line(MARGIN_X, 13 * mm, PAGE_W - MARGIN_X, 13 * mm)
        canv.drawString(MARGIN_X, 9 * mm, self.meta.get("Date", ""))
        canv.drawRightString(PAGE_W - MARGIN_X, 9 * mm, f"Page {doc.page}")
        canv.restoreState()

    def _cover(self, canv, doc) -> None:  # noqa: ANN001
        canv.saveState()
        # Background band with a soft gradient made of stacked rectangles.
        top = PAGE_H
        band_h = PAGE_H * 0.58
        steps = 60
        start, end = colors.HexColor("#0b1030"), colors.HexColor("#2a1b6e")
        for i in range(steps):
            t = i / (steps - 1)
            canv.setFillColor(colors.Color(
                start.red + (end.red - start.red) * t,
                start.green + (end.green - start.green) * t,
                start.blue + (end.blue - start.blue) * t,
            ))
            canv.rect(0, top - band_h + band_h * i / steps, PAGE_W, band_h / steps + 1,
                      stroke=0, fill=1)
        # Glow circles
        for radius, alpha in ((95 * mm, 0.10), (60 * mm, 0.10), (30 * mm, 0.12)):
            canv.setFillColor(colors.Color(0.36, 0.55, 0.98, alpha=alpha))
            canv.circle(PAGE_W - 30 * mm, PAGE_H - 70 * mm, radius, stroke=0, fill=1)
        _draw_logo(canv, MARGIN_X, PAGE_H - 48 * mm, 16 * mm)
        canv.setFillColor(colors.white)
        canv.setFont(FONT_BOLD, 15)
        canv.drawString(MARGIN_X + 21 * mm, PAGE_H - 41.5 * mm, "Atlas AI")
        canv.setFont(FONT_BOLD, 34)
        canv.drawString(MARGIN_X, PAGE_H - 105 * mm, "Technical Design")
        canv.drawString(MARGIN_X, PAGE_H - 120 * mm, "Document")
        canv.setFont(FONT, 12.5)
        canv.setFillColor(colors.HexColor("#c7cff5"))
        y = PAGE_H - 136 * mm
        for line in self.subtitle.split("\n"):
            canv.drawString(MARGIN_X, y, line)
            y -= 6.5 * mm
        # Metadata block
        canv.setFillColor(INK)
        y = PAGE_H * 0.42 - 16 * mm
        for key, value in self.meta.items():
            canv.setFont(FONT_BOLD, 9.5)
            canv.setFillColor(INK_3)
            canv.drawString(MARGIN_X, y, key.upper())
            canv.setFont(FONT, 11)
            canv.setFillColor(INK)
            canv.drawString(MARGIN_X + 38 * mm, y, value)
            y -= 9 * mm
        canv.setStrokeColor(LINE)
        canv.line(MARGIN_X, 22 * mm, PAGE_W - MARGIN_X, 22 * mm)
        canv.setFont(FONT, 8)
        canv.setFillColor(INK_3)
        canv.drawString(MARGIN_X, 16 * mm,
                        "Describes the system as implemented in this repository. "
                        "Planned work is marked as such.")
        canv.restoreState()


def _draw_logo(canv, x: float, y: float, size: float) -> None:  # noqa: ANN001
    """Hexagon mark matching the console's logo."""
    cx, cy, r = x + size / 2, y + size / 2, size / 2

    def hexagon(radius: float) -> list[tuple[float, float]]:
        return [(cx + radius * math.cos(math.radians(90 + 60 * k)),
                 cy + radius * math.sin(math.radians(90 + 60 * k))) for k in range(6)]

    for radius, fill in ((r, colors.HexColor("#6d6af5")), (r * 0.55, colors.HexColor("#1b1f4d")),
                         (r * 0.3, colors.HexColor("#dbeafe"))):
        path = canv.beginPath()
        points = hexagon(radius)
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        path.close()
        canv.setFillColor(fill)
        canv.drawPath(path, stroke=0, fill=1)


# --- flowable helpers --------------------------------------------------------------------
def heading(text: str, level: int) -> Paragraph:
    style = {0: H1, 1: H2, 2: H3}[level]
    paragraph = Paragraph(text, style)
    if level < 2:
        paragraph.toc_level = level  # type: ignore[attr-defined]
    return paragraph


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def bullets(items: list[str], style: ParagraphStyle = BULLET) -> list[Paragraph]:
    return [Paragraph(item, style, bulletText="\u2022") for item in items]


def numbered(items: list[str]) -> list[Paragraph]:
    return [Paragraph(item, BULLET, bulletText=f"{i}.") for i, item in enumerate(items, 1)]


def table(rows: list[list[str]], widths: list[float], *, header: bool = True,
          mono_cols: tuple[int, ...] = (), zebra: bool = True) -> Table:
    """Wrapping table. `widths` are fractions of the content width."""
    data = []
    for r, row in enumerate(rows):
        cells = []
        for c, cell in enumerate(row):
            if r == 0 and header:
                style = CELL_HEAD
            elif c in mono_cols:
                style = CELL_MONO
            else:
                style = CELL
            cells.append(Paragraph(str(cell), style))
        data.append(cells)
    t = Table(data, colWidths=[w * CONTENT_W for w in widths], repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), BLUE_SOFT),
                     ("LINEBELOW", (0, 0), (-1, 0), 0.9, BLUE)]
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if r % 2 == 0:
                commands.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    t.setStyle(TableStyle(commands))
    t.spaceBefore, t.spaceAfter = 4, 10
    return t


def callout(title: str, body: str, tone: str = "info") -> Table:
    accent, soft = {
        "info": (BLUE, BLUE_SOFT), "warn": (AMBER, AMBER_SOFT), "risk": (RED, RED_SOFT),
        "ok": (GREEN, GREEN_SOFT), "note": (VIOLET, VIOLET_SOFT),
    }[tone]
    title_style = ParagraphStyle("ct", parent=CELL, fontName=FONT_BOLD, textColor=accent)
    content = [Paragraph(title, title_style), Spacer(1, 2), Paragraph(body, CELL)]
    t = Table([[content]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), soft),
        ("LINEBEFORE", (0, 0), (0, -1), 2.6, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    t.spaceBefore, t.spaceAfter = 4, 10
    return t


def code(text: str, caption: str | None = None) -> list[Flowable]:
    block = Preformatted(text.strip("\n"), CODE)
    t = Table([[block]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f7fb")),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    t.spaceBefore, t.spaceAfter = 3, 4 if caption else 10
    out: list[Flowable] = [t]
    if caption:
        out.append(Paragraph(caption, CAPTION))
    return out


def figure(diagram: Flowable, caption: str, lead: list[Flowable] | None = None) -> KeepTogether:
    """Figure with caption; `lead` (e.g. a heading) is kept on the same page."""
    return KeepTogether([*(lead or []), Spacer(1, 4), diagram, Paragraph(caption, CAPTION)])


def toc() -> TableOfContents:
    t = TableOfContents()
    t.levelStyles = TOC_STYLES
    t.dotsMinLevel = 0
    return t


# --- diagram language --------------------------------------------------------------------
STYLES = {
    "default": (colors.white, NAVY, INK),
    "blue": (BLUE_SOFT, BLUE, NAVY),
    "violet": (VIOLET_SOFT, VIOLET, NAVY),
    "green": (GREEN_SOFT, GREEN, NAVY),
    "amber": (AMBER_SOFT, AMBER, NAVY),
    "red": (RED_SOFT, RED, NAVY),
    "cyan": (CYAN_SOFT, CYAN, NAVY),
    "grey": (SOFT, INK_3, INK_2),
    "dark": (NAVY, NAVY, colors.white),
}


@dataclass
class Box:
    key: str
    x: float  # mm from left of the diagram
    y: float  # mm from top of the diagram
    w: float
    h: float
    label: str
    style: str = "default"
    sub: str = ""
    shape: str = "rect"  # rect | diamond | db | round


@dataclass
class Arrow:
    src: str
    dst: str
    label: str = ""
    via: list[tuple[float, float]] = field(default_factory=list)  # mm, top-left origin
    dashed: bool = False
    src_side: str | None = None  # n e s w
    dst_side: str | None = None
    label_at: float = 0.5
    label_dx: float = 0.0
    label_dy: float = 0.0
    start: tuple[float, float] | None = None  # explicit endpoints override anchors
    end: tuple[float, float] | None = None


@dataclass
class Group:
    x: float
    y: float
    w: float
    h: float
    label: str
    tone: str = "grey"


class Diagram(Flowable):
    """Box-and-arrow diagram described in millimetres with a top-left origin."""

    def __init__(self, width_mm: float, height_mm: float, boxes: list[Box],
                 arrows: list[Arrow], groups: list[Group] | None = None,
                 texts: list[tuple[float, float, str, int]] | None = None) -> None:
        super().__init__()
        self.wmm, self.hmm = width_mm, height_mm
        self.width, self.height = width_mm * mm, height_mm * mm
        self.boxes = {b.key: b for b in boxes}
        self.arrows = arrows
        self.groups = groups or []
        self.texts = texts or []

    def wrap(self, avail_w: float, avail_h: float) -> tuple[float, float]:
        return self.width, self.height

    # coordinate helpers (mm, top-left) -> points (bottom-left)
    def _pt(self, x: float, y: float) -> tuple[float, float]:
        return x * mm, (self.hmm - y) * mm

    def _anchor(self, box: Box, side: str) -> tuple[float, float]:
        return {
            "n": (box.x + box.w / 2, box.y),
            "s": (box.x + box.w / 2, box.y + box.h),
            "e": (box.x + box.w, box.y + box.h / 2),
            "w": (box.x, box.y + box.h / 2),
        }[side]

    def _auto_side(self, box: Box, toward: tuple[float, float]) -> str:
        cx, cy = box.x + box.w / 2, box.y + box.h / 2
        dx, dy = toward[0] - cx, toward[1] - cy
        if abs(dx) * box.h > abs(dy) * box.w:
            return "e" if dx > 0 else "w"
        return "s" if dy > 0 else "n"

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        for g in self.groups:
            fill, stroke, text = STYLES[g.tone]
            x, y = self._pt(g.x, g.y + g.h)
            c.setFillColor(fill)
            c.setStrokeColor(stroke)
            c.setDash(3, 2)
            c.setLineWidth(0.6)
            c.roundRect(x, y, g.w * mm, g.h * mm, 6, stroke=1, fill=1)
            c.setDash()
            c.setFont(FONT_BOLD, 7)
            c.setFillColor(stroke)
            tx, ty = self._pt(g.x + 2.5, g.y + 4)
            c.drawString(tx, ty, g.label.upper())
        for a in self.arrows:
            self._draw_arrow(a)
        for b in self.boxes.values():
            self._draw_box(b)
        for x, y, text, size in self.texts:
            c.setFont(FONT, size)
            c.setFillColor(INK_3)
            px, py = self._pt(x, y)
            c.drawCentredString(px, py, text)
        c.restoreState()

    def _draw_box(self, b: Box) -> None:
        c = self.canv
        fill, stroke, text = STYLES[b.style]
        x, y = self._pt(b.x, b.y + b.h)
        w, h = b.w * mm, b.h * mm
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(0.9)
        if b.shape == "diamond":
            path = c.beginPath()
            path.moveTo(x + w / 2, y + h)
            path.lineTo(x + w, y + h / 2)
            path.lineTo(x + w / 2, y)
            path.lineTo(x, y + h / 2)
            path.close()
            c.drawPath(path, stroke=1, fill=1)
        elif b.shape == "db":
            e = min(3.2 * mm, h * 0.22)
            c.rect(x, y + e / 2, w, h - e, stroke=0, fill=1)
            c.ellipse(x, y, x + w, y + e, stroke=1, fill=1)
            c.line(x, y + e / 2, x, y + h - e / 2)
            c.line(x + w, y + e / 2, x + w, y + h - e / 2)
            c.ellipse(x, y + h - e, x + w, y + h, stroke=1, fill=1)
        elif b.shape == "round":
            c.roundRect(x, y, w, h, h / 2, stroke=1, fill=1)
        else:
            c.roundRect(x, y, w, h, 3.2, stroke=1, fill=1)
        lines = b.label.split("\n")
        sub_lines = b.sub.split("\n") if b.sub else []
        size, sub_size = 7.6, 6.2
        total = len(lines) * (size + 1.6) + len(sub_lines) * (sub_size + 1.4)
        ty = y + h / 2 + total / 2 - size
        if b.shape == "db":
            ty -= 1.2
        c.setFillColor(text)
        c.setFont(FONT_BOLD, size)
        for line in lines:
            c.drawCentredString(x + w / 2, ty, line)
            ty -= size + 1.6
        c.setFont(FONT, sub_size)
        c.setFillColor(INK_2 if b.style != "dark" else colors.HexColor("#c7cff5"))
        for line in sub_lines:
            c.drawCentredString(x + w / 2, ty + 0.6, line)
            ty -= sub_size + 1.4

    def _draw_arrow(self, a: Arrow) -> None:
        c = self.canv
        src, dst = self.boxes[a.src], self.boxes[a.dst]
        first_target = a.via[0] if a.via else (dst.x + dst.w / 2, dst.y + dst.h / 2)
        last_source = a.via[-1] if a.via else (src.x + src.w / 2, src.y + src.h / 2)
        start = a.start or self._anchor(src, a.src_side or self._auto_side(src, first_target))
        end = a.end or self._anchor(dst, a.dst_side or self._auto_side(dst, last_source))
        points = [start, *a.via, end]
        c.setStrokeColor(INK_3)
        c.setFillColor(INK_3)
        c.setLineWidth(0.8)
        if a.dashed:
            c.setDash(2.5, 2)
        path = c.beginPath()
        path.moveTo(*self._pt(*points[0]))
        for pt in points[1:]:
            path.lineTo(*self._pt(*pt))
        c.drawPath(path, stroke=1, fill=0)
        c.setDash()
        # arrow head
        (x1, y1), (x2, y2) = self._pt(*points[-2]), self._pt(*points[-1])
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 4.2
        head = c.beginPath()
        head.moveTo(x2, y2)
        head.lineTo(x2 - size * math.cos(angle - 0.42), y2 - size * math.sin(angle - 0.42))
        head.lineTo(x2 - size * math.cos(angle + 0.42), y2 - size * math.sin(angle + 0.42))
        head.close()
        c.drawPath(head, stroke=0, fill=1)
        if a.label:
            # place label along the longest segment's midpoint (or at label_at of total path)
            seg = max(range(len(points) - 1),
                      key=lambda i: math.dist(points[i], points[i + 1]))
            (sx, sy), (ex, ey) = points[seg], points[seg + 1]
            mx = sx + (ex - sx) * a.label_at + a.label_dx
            my = sy + (ey - sy) * a.label_at + a.label_dy
            px, py = self._pt(mx, my)
            c.setFont(FONT, 6.3)
            tw = pdfmetrics.stringWidth(a.label, FONT, 6.3)
            c.setFillColor(colors.white)
            c.rect(px - tw / 2 - 1.6, py - 2.2, tw + 3.2, 8, stroke=0, fill=1)
            c.setFillColor(INK_2)
            c.drawCentredString(px, py, a.label)


class Sequence(Flowable):
    """Minimal sequence diagram: participants as lifelines, messages as arrows."""

    def __init__(self, participants: list[str], messages: list[tuple[int, int, str, bool]],
                 width_mm: float = 170, step_mm: float = 7.2) -> None:
        super().__init__()
        self.participants = participants
        self.messages = messages
        self.wmm = width_mm
        self.step = step_mm
        self.hmm = 16 + step_mm * (len(messages) + 1)
        self.width, self.height = self.wmm * mm, self.hmm * mm

    def wrap(self, avail_w: float, avail_h: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        n = len(self.participants)
        gap = self.wmm / n
        xs = [gap * (i + 0.5) * mm for i in range(n)]
        top = self.height
        c.saveState()
        for x, name in zip(xs, self.participants, strict=True):
            w = min(gap - 4, 30) * mm
            c.setFillColor(NAVY)
            c.roundRect(x - w / 2, top - 10 * mm, w, 8 * mm, 3, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont(FONT_BOLD, 7.2)
            c.drawCentredString(x, top - 6.9 * mm, name)
            c.setStrokeColor(LINE)
            c.setDash(2, 2)
            c.line(x, top - 10 * mm, x, 2 * mm)
            c.setDash()
        y = top - 16 * mm
        for src, dst, label, dashed in self.messages:
            x1, x2 = xs[src], xs[dst]
            c.setStrokeColor(BLUE if not dashed else INK_3)
            c.setFillColor(BLUE if not dashed else INK_3)
            c.setLineWidth(0.8)
            if dashed:
                c.setDash(2.5, 2)
            if src == dst:
                c.line(x1, y + 1.5 * mm, x1 + 8 * mm, y + 1.5 * mm)
                c.line(x1 + 8 * mm, y + 1.5 * mm, x1 + 8 * mm, y - 1.5 * mm)
                c.line(x1 + 8 * mm, y - 1.5 * mm, x1, y - 1.5 * mm)
                tip, direction = (x1, y - 1.5 * mm), -1
            else:
                c.line(x1, y, x2, y)
                tip, direction = (x2, y), (1 if x2 > x1 else -1)
            c.setDash()
            head = c.beginPath()
            head.moveTo(*tip)
            head.lineTo(tip[0] - direction * 4, tip[1] + 2.2)
            head.lineTo(tip[0] - direction * 4, tip[1] - 2.2)
            head.close()
            c.drawPath(head, stroke=0, fill=1)
            c.setFont(FONT, 6.6)
            c.setFillColor(INK)
            if src == dst:
                c.drawString(x1 + 10 * mm, y - 1, label)
            else:
                c.drawCentredString((x1 + x2) / 2, y + 1.8, label)
            y -= self.step * mm
        c.restoreState()


__all__ = [
    "AMBER", "BLUE", "BODY", "CAPTION", "CONTENT_W", "Arrow", "Box", "DesignDoc", "Diagram",
    "Group", "Sequence", "SMALL", "bullets", "callout", "code", "figure", "heading",
    "numbered", "p", "table", "toc", "TA_LEFT", "H1",
]
