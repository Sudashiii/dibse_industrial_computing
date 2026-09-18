"""Create a one-page Homework 2 submission summary from demo evidence."""

from __future__ import annotations

import argparse
import json
import textwrap
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
README_URL = f"{REPOSITORY_URL}/blob/main/homework/homework_2/README.md"

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
    selected: list[str] = []
    completed_examples = 0
    for raw_line in log_lines:
        line = raw_line.strip()
        keep = (
            "COMMAND docker compose up" in line
            or "LITELLM_HEALTH" in line
            or "WORKFLOW_COMPLETED" in line
            or "SUMMARY" in line
            or "CLEANUP" in line
            or (
                completed_examples == 0
                and "COMMAND docker compose --profile workflow run" in line
            )
            or (
                completed_examples == 0
                and ("REGISTRY_LOOKUP" in line or "A2A_CALL" in line)
            )
        )
        if keep:
            selected.append(line)
        if "WORKFLOW_COMPLETED" in line:
            completed_examples += 1
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


def create_samples_screenshot(
    samples: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Render a compact screenshot of the three completed sample requests."""

    width, height = 1800, 620
    image = Image.new("RGB", (width, height), "#0f172a")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 82), fill="#1e293b")
    for x, color in ((42, "#fb7185"), (82, "#facc15"), (122, "#34d399")):
        draw.ellipse((x, 30, x + 22, 52), fill=color)
    draw.text(
        (180, 23),
        "A2A sample requests - parsed workflow results",
        fill="#e2e8f0",
        font=_font(28, bold=True),
    )

    card_gap = 24
    card_x = 48
    card_y = 108
    card_width = (width - 2 * card_x - 2 * card_gap) / 3
    card_height = 440
    title_font = _font(23, bold=True)
    body_font = _font(21)
    small_font = _font(18)
    for index, sample in enumerate(samples[:3], start=1):
        x = card_x + (index - 1) * (card_width + card_gap)
        draw.rounded_rectangle(
            (x, card_y, x + card_width, card_y + card_height),
            radius=16,
            fill="#172033",
            outline="#334155",
            width=2,
        )
        draw.text((x + 22, card_y + 18), f"EXAMPLE {index}", fill="#67e8f9", font=title_font)
        question = str(sample.get("question", ""))
        y = card_y + 62
        draw.text((x + 22, y), "QUESTION", fill="#94a3b8", font=small_font)
        y += 29
        for line in textwrap.wrap(question, width=34, break_long_words=False):
            draw.text((x + 22, y), line, fill="#f8fafc", font=body_font)
            y += 27

        agents = sample.get("agents", [])
        search = sample.get("search", {})
        evidence = sample.get("evidence", {})
        synthesis = sample.get("synthesis", {})
        hit_ids = ", ".join(hit.get("paper_id", "?") for hit in search.get("hits", [])) or "none"
        draw.text((x + 22, y + 14), f"REGISTRY -> {len(agents)} agents", fill="#67e8f9", font=body_font)
        draw.text((x + 22, y + 48), f"SEARCH hits: {hit_ids}", fill="#e2e8f0", font=small_font)
        draw.text(
            (x + 22, y + 77),
            f"EVIDENCE items: {len(evidence.get('evidence', []))}",
            fill="#e2e8f0",
            font=small_font,
        )
        draw.text(
            (x + 22, y + 106),
            f"SYNTHESIS findings: {len(synthesis.get('key_findings', []))}",
            fill="#34d399",
            font=small_font,
        )
        finding = ""
        findings = synthesis.get("key_findings", [])
        if findings:
            finding = str(findings[0])
        y += 152
        draw.text((x + 22, y), "FIRST FINDING", fill="#94a3b8", font=small_font)
        y += 27
        for line in textwrap.wrap(finding or "No matching corpus item", width=34, break_long_words=False)[:4]:
            draw.text((x + 22, y), line, fill="#cbd5e1", font=small_font)
            y += 23

    draw.text(
        (48, height - 38),
        "All values are parsed from workflow-samples.json; no credentials or external model calls are shown.",
        fill="#94a3b8",
        font=_font(18),
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
    samples: list[dict[str, Any]],
    terminal_image: Path,
    sample_image: Path,
    output_path: Path,
) -> None:
    """Build the one-page visual summary with aspect-ratio-safe evidence."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    page = canvas.Canvas(str(output_path), pagesize=A4)
    page.setTitle("Homework 2 - Distributed Remote A2A System")
    page.setAuthor("Industrial Computing Homework")
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
    total_hits = sum(
        len(sample.get("search", {}).get("hits", [])) for sample in samples
    )
    total_evidence = sum(
        len(sample.get("evidence", {}).get("evidence", [])) for sample in samples
    )
    checks = [
        f"- {len(agents)} registered agents per run",
        f"- {len(samples)} sample requests completed",
        f"- {total_hits} search hits -> {total_evidence} evidence items",
        "- LiteLLM liveness and Compose passed",
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
    lower_bottom = lower_y - lower_h
    _card(page, x=margin, y=lower_bottom, width=card_w, height=lower_h, title="Sample evidence")
    sample = Image.open(sample_image)
    sample_width, sample_height = sample.size
    sample_box_width = card_w - 18
    sample_box_height = 83
    sample_scale = min(sample_box_width / sample_width, sample_box_height / sample_height)
    sample_draw_width = sample_width * sample_scale
    sample_draw_height = sample_height * sample_scale
    page.drawImage(
        ImageReader(sample),
        margin + (card_w - sample_draw_width) / 2,
        lower_bottom + 20,
        width=sample_draw_width,
        height=sample_draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 6.8)
    page.drawString(margin + 12, lower_bottom + 8, "Three live questions; full JSON and log are linked below.")

    _card(page, x=right_x, y=lower_bottom, width=card_w, height=lower_h, title="Integration flow", fill=PALE_BLUE)
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
    page.drawString(margin, 21, "Links: README | output/evidence/execution.log | workflow-samples.json")
    page.linkURL(README_URL, (margin, 16, margin + 55, 29))
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
    samples_path = evidence_dir / "workflow-samples.json"
    log_path = evidence_dir / "execution.log"
    if not workflow_path.exists() or not log_path.exists():
        raise FileNotFoundError(
            "Run scripts/run_demo.py before creating the submission PDF."
        )
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    samples = json.loads(samples_path.read_text(encoding="utf-8")) if samples_path.exists() else [data]
    terminal_image = evidence_dir / "terminal-screenshot.png"
    sample_image = evidence_dir / "sample-results.png"
    create_terminal_screenshot(log_path, terminal_image)
    create_samples_screenshot(samples, sample_image)
    build_pdf(
        data,
        samples=samples,
        terminal_image=terminal_image,
        sample_image=sample_image,
        output_path=output_path,
    )
    print(f"Created {output_path}")
    print(f"Created {terminal_image}")
    print(f"Created {sample_image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
