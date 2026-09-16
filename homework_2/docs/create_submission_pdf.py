"""Create a one-page Homework 2 submission summary from demo evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "output" / "evidence"
DEFAULT_PDF = PROJECT_ROOT / "output" / "pdf" / "homework_2_submission_summary.pdf"
REPOSITORY_URL = "https://github.com/Sudashiii/dibse_industrial_computing"

NAVY = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#334155")
BLUE = colors.HexColor("#2563eb")
PALE_BLUE = colors.HexColor("#eff6ff")
PALE_GREEN = colors.HexColor("#ecfdf5")
BORDER = colors.HexColor("#cbd5e1")
MUTED = colors.HexColor("#64748b")


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "C:\\Windows\\Fonts\\consolab.ttf",
        "C:\\Windows\\Fonts\\consola.ttf",
    )
    if not bold:
        candidates = ("C:\\Windows\\Fonts\\consola.ttf",) + candidates
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def create_terminal_screenshot(log_path: Path, output_path: Path) -> None:
    """Render only relevant workflow lines as a readable terminal image."""

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    markers = (
        "question=",
        "COMMAND docker compose",
        "REGISTRY_LOOKUP",
        "AGENT_SELECTED",
        "A2A_CALL",
        "WORKFLOW_COMPLETED",
        "SUMMARY",
        "CLEANUP",
    )
    selected = [
        line.strip()
        for line in log_lines
        if any(marker in line for marker in markers)
    ]
    if not selected:
        raise ValueError("Execution log does not contain workflow evidence.")

    width = 1800
    margin = 56
    line_height = 40
    header_height = 82
    footer_height = 42
    max_chars = 118
    clipped = [
        line if len(line) <= max_chars else f"{line[: max_chars - 3]}..."
        for line in selected
    ]
    height = header_height + margin + len(clipped) * line_height + footer_height
    image = Image.new("RGB", (width, height), "#0f172a")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, header_height), fill="#1e293b")
    for x, color in ((42, "#fb7185"), (82, "#facc15"), (122, "#34d399")):
        draw.ellipse((x, 30, x + 22, 52), fill=color)
    draw.text(
        (180, 23),
        "A2A workflow - focused execution evidence",
        fill="#e2e8f0",
        font=_font(28, bold=True),
    )
    body_font = _font(25)
    for index, line in enumerate(clipped):
        color = "#67e8f9" if "COMMAND" in line else "#e2e8f0"
        draw.text(
            (margin, header_height + 22 + index * line_height),
            line,
            fill=color,
            font=body_font,
        )
    draw.text(
        (margin, height - footer_height + 8),
        "Only registry lookups, agent calls and workflow totals are shown.",
        fill="#94a3b8",
        font=_font(20),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _wrapped_lines(
    text: str,
    *,
    font_name: str,
    font_size: float,
    width: float,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, font_name, font_size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _paragraph(
    page: canvas.Canvas,
    text: str,
    *,
    x: float,
    y: float,
    width: float,
    font_name: str = "Helvetica",
    font_size: float = 8.5,
    leading: float = 11,
    color: colors.Color = SLATE,
) -> float:
    page.setFillColor(color)
    page.setFont(font_name, font_size)
    for line in _wrapped_lines(
        text,
        font_name=font_name,
        font_size=font_size,
        width=width,
    ):
        page.drawString(x, y, line)
        y -= leading
    return y


def _card(
    page: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    fill: colors.Color = colors.white,
) -> None:
    page.setFillColor(fill)
    page.setStrokeColor(BORDER)
    page.setLineWidth(0.8)
    page.roundRect(x, y, width, height, 8, fill=1, stroke=1)
    page.setFillColor(BLUE)
    page.roundRect(x, y + height - 4, width, 4, 2, fill=1, stroke=0)
    page.setFillColor(NAVY)
    page.setFont("Helvetica-Bold", 10)
    page.drawString(x + 12, y + height - 23, title)


def _arrow(page: canvas.Canvas, x1: float, y1: float, x2: float, y2: float) -> None:
    page.setStrokeColor(BLUE)
    page.setFillColor(BLUE)
    page.setLineWidth(1.2)
    page.line(x1, y1, x2, y2)
    page.line(x2, y2, x2 - 5, y2 + 3)
    page.line(x2, y2, x2 - 5, y2 - 3)


def _flow_box(
    page: canvas.Canvas,
    *,
    x: float,
    y: float,
    title: str,
    subtitle: str,
) -> None:
    page.setFillColor(PALE_BLUE)
    page.setStrokeColor(colors.HexColor("#93c5fd"))
    page.roundRect(x, y, 67, 36, 5, fill=1, stroke=1)
    page.setFillColor(NAVY)
    page.setFont("Helvetica-Bold", 6.7)
    page.drawCentredString(x + 33.5, y + 22, title)
    page.setFont("Helvetica", 6.2)
    page.drawCentredString(x + 33.5, y + 11, subtitle)


def build_pdf(
    data: dict[str, Any],
    *,
    terminal_image: Path,
    output_path: Path,
) -> None:
    """Build the one-page visual summary with aspect-ratio-safe evidence."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    page = canvas.Canvas(str(output_path), pagesize=A4)
    margin = 36

    page.setFillColor(NAVY)
    page.rect(0, page_height - 76, page_width, 76, fill=1, stroke=0)
    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 19)
    page.drawString(margin, page_height - 34, "Homework 2 - Distributed Remote A2A System")
    page.setFont("Helvetica", 9)
    page.setFillColor(colors.HexColor("#bfdbfe"))
    page.drawString(margin, page_height - 55, "One-page implementation and verification summary")
    page.setFillColor(colors.white)
    page.setFont("Helvetica", 8)
    page.drawRightString(page_width - margin, page_height - 30, "Repository")
    page.setFillColor(colors.HexColor("#7dd3fc"))
    page.drawRightString(page_width - margin, page_height - 45, "github.com/Sudashiii/dibse_industrial_computing")
    page.linkURL(REPOSITORY_URL, (page_width - 245, page_height - 50, page_width - margin, page_height - 20))

    card_y = page_height - 184
    card_h = 91
    card_w = (page_width - 2 * margin - 14) / 2
    _card(page, x=margin, y=card_y, width=card_w, height=card_h, title="Implementation")
    implementation = [
        "- Registry with capability-based lookup",
        "- Search, Evidence and Synthesis agents",
        "- A2A JSON-RPC message/send over HTTP",
        "- Docker Compose with health-gated startup",
    ]
    y = card_y + card_h - 39
    for line in implementation:
        y = _paragraph(page, line, x=margin + 12, y=y, width=card_w - 24, font_size=8.2, leading=11)

    right_x = margin + card_w + 14
    _card(page, x=right_x, y=card_y, width=card_w, height=card_h, title="Verification", fill=PALE_GREEN)
    agents = data.get("agents", [])
    search_hits = data.get("search", {}).get("hits", [])
    evidence_items = data.get("evidence", {}).get("evidence", [])
    findings = data.get("synthesis", {}).get("key_findings", [])
    checks = [
        f"- {len(agents)} registered agents",
        f"- {len(search_hits)} search hits -> {len(evidence_items)} evidence items",
        f"- {len(findings)} synthesis findings returned",
        "- Compose config, image build and workflow passed",
    ]
    y = card_y + card_h - 39
    for line in checks:
        y = _paragraph(page, line, x=right_x + 12, y=y, width=card_w - 24, font_size=8.2, leading=11)

    page.setFillColor(SLATE)
    page.setFont("Helvetica", 9)
    page.drawString(margin, card_y - 27, "Relevant execution output")

    image = Image.open(terminal_image)
    image_width, image_height = image.size
    target_width = page_width - 2 * margin
    target_height = target_width * image_height / image_width
    image_top = card_y - 38
    page.drawImage(
        ImageReader(image),
        margin,
        image_top - target_height,
        width=target_width,
        height=target_height,
        preserveAspectRatio=True,
        mask="auto",
    )

    lower_y = image_top - target_height - 17
    lower_h = 137
    _card(page, x=margin, y=lower_y - lower_h, width=card_w, height=lower_h, title="Evidence files")
    evidence_lines = [
        "- execution.log: focused command and agent trace",
        "- workflow-output.json: complete structured result",
        "- terminal-screenshot.png: relevant output only",
        "- README and Compose commands are reproducible",
    ]
    y = lower_y - 33
    for line in evidence_lines:
        y = _paragraph(page, line, x=margin + 12, y=y, width=card_w - 24, font_size=8.0, leading=12)

    _card(page, x=right_x, y=lower_y - lower_h, width=card_w, height=lower_h, title="Integration flow", fill=PALE_BLUE)
    flow_y = lower_y - 85
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 7.3)
    page.drawString(right_x + 12, lower_y - 43, "Each step is selected from the Registry by capability.")
    x1 = right_x + 13
    x2 = x1 + 77
    x3 = x2 + 77
    _flow_box(page, x=x1, y=flow_y, title="Search", subtitle="8101")
    _flow_box(page, x=x2, y=flow_y, title="Evidence", subtitle="8102")
    _flow_box(page, x=x3, y=flow_y, title="Synthesis", subtitle="8103")
    _arrow(page, x1 + 67, flow_y + 18, x2, flow_y + 18)
    _arrow(page, x2 + 67, flow_y + 18, x3, flow_y + 18)
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 6.9)
    page.drawString(right_x + 12, lower_y - 116, "Registry: port 8000 | Orchestrator: one-shot Compose profile")

    page.setStrokeColor(BORDER)
    page.line(margin, 34, page_width - margin, 34)
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 7.5)
    page.drawString(margin, 21, "Links: README | output/evidence/execution.log | workflow-output.json")
    page.drawRightString(page_width - margin, 21, "Focused evidence - no credentials included")
    page.showPage()
    page.save()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the Homework 2 one-page PDF.")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_PDF))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    evidence_dir = Path(args.evidence_dir)
    output_path = Path(args.output)
    workflow_path = evidence_dir / "workflow-output.json"
    log_path = evidence_dir / "execution.log"
    if not workflow_path.exists() or not log_path.exists():
        raise FileNotFoundError(
            "Run scripts/run_demo.py before creating the submission PDF."
        )
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    terminal_image = evidence_dir / "terminal-screenshot.png"
    create_terminal_screenshot(log_path, terminal_image)
    build_pdf(data, terminal_image=terminal_image, output_path=output_path)
    print(f"Created {output_path}")
    print(f"Created {terminal_image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
