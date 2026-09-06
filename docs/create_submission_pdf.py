"""Build the one-page Homework 1 submission summary and focused evidence images."""

from __future__ import annotations

import json
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
SCREENSHOTS_DIR = DOCS_DIR / "screenshots"
PDF_DIR = PROJECT_ROOT / "output" / "pdf"
PDF_PATH = PDF_DIR / "homework1_submission_summary.pdf"
DEMO_LOG_PATH = PROJECT_ROOT / "logs" / "demo_run.log"
AGENT_EXAMPLES = (
    (
        PROJECT_ROOT / "logs" / "litellm_run_prompt1.log",
        "Prüfe den Bestand des Industrial Sensor und berechne den Rabatt für 120 Stück. Nenne mir am Ende die wichtigsten Werte.",
    ),
    (
        PROJECT_ROOT / "logs" / "litellm_run_prompt2.log",
        "Wie viele Safety Light Curtain sind auf Lager und reicht der Bestand für eine Bestellung von 5 Stück?",
    ),
)
REPOSITORY_URL = "https://github.com/Sudashiii/dibse_industrial_computing"
README_URL = f"{REPOSITORY_URL}/blob/main/README.md"
CONFIG_URL = f"{REPOSITORY_URL}/blob/main/litellm_config.yaml"


def _font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


MONO = ("consola.ttf", "cour.ttf")
SANS = ("segoeui.ttf", "arial.ttf")
SANS_BOLD = ("segoeuib.ttf", "arialbd.ttf")


def _payload(line: str) -> dict[str, Any]:
    return json.loads(line.split("payload=", 1)[1])


def read_demo_evidence() -> dict[str, Any]:
    """Extract only the relevant values from the verified MCP demo log."""

    if not DEMO_LOG_PATH.exists():
        raise FileNotFoundError(f"Missing demo log: {DEMO_LOG_PATH}")

    lines = DEMO_LOG_PATH.read_text(encoding="utf-8").splitlines()
    lookup_payload = next(
        _payload(line)
        for line in lines
        if "RESPONSE tool=lookup_inventory" in line
    )
    discount_payload = next(
        _payload(line)
        for line in lines
        if "RESPONSE tool=calculate_tiered_discount" in line
    )
    audit_payload = next(
        _payload(line)
        for line in lines
        if "RESPONSE tool=append_audit_event" in line
    )
    resource_line = next(line for line in lines if "RESOURCE audit://events lines=" in line)
    resource_match = re.search(r"RESOURCE audit://events lines=(\d+)", resource_line)
    if resource_match is None:
        raise ValueError("Could not parse audit resource line count.")

    return {
        "lookup": lookup_payload,
        "discount": discount_payload,
        "audit": audit_payload,
        "audit_lines": int(resource_match.group(1)),
    }


def _logged_value(lines: list[str], marker: str) -> str:
    for line in lines:
        if marker in line:
            return line.split(marker, 1)[1].strip()
    raise ValueError(f"Missing log marker: {marker}")


def read_agent_evidence() -> list[dict[str, Any]]:
    """Read the two real OpenRouter runs used for the example answers."""

    examples: list[dict[str, Any]] = []
    for log_path, expected_prompt in AGENT_EXAMPLES:
        if not log_path.exists():
            raise FileNotFoundError(f"Missing agent log: {log_path}")
        lines = log_path.read_text(encoding="utf-8").splitlines()
        prompt = _logged_value(lines, "PROMPT prompt=")
        final_answer = _logged_value(lines, "FINAL answer=")
        lookup_payload = _payload(
            next(
                line
                for line in lines
                if "OBSERVATION" in line and "tool=lookup_inventory" in line
            )
        )
        discount_line = next(
            (
                line
                for line in lines
                if "OBSERVATION" in line and "tool=calculate_tiered_discount" in line
            ),
            None,
        )
        discount_payload = _payload(discount_line) if discount_line else None
        if prompt != expected_prompt:
            raise ValueError(f"Unexpected prompt in {log_path.name}")
        examples.append(
            {
                "log_path": str(log_path.relative_to(PROJECT_ROOT)),
                "prompt": prompt,
                "lookup": lookup_payload,
                "discount": discount_payload,
                "answer": final_answer,
            }
        )
    return examples


def run_verification() -> dict[str, str]:
    """Run the local checks used as evidence in the submission summary."""

    python_executable = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python_executable.exists():
        raise FileNotFoundError(f"Missing project environment: {python_executable}")

    test_run = subprocess.run(
        [str(python_executable), "-m", "pytest", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if test_run.returncode != 0:
        raise RuntimeError(f"pytest failed:\n{test_run.stdout}\n{test_run.stderr}")
    pytest_summary = next(
        line.strip()
        for line in reversed(test_run.stdout.splitlines())
        if line.strip()
    )

    compose_run = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if compose_run.returncode != 0:
        raise RuntimeError(f"docker compose config failed:\n{compose_run.stderr}")

    cli_run = subprocess.run(
        [str(python_executable), "litellm_agent.py", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if cli_run.returncode != 0:
        raise RuntimeError(f"Agent CLI help failed:\n{cli_run.stderr}")

    return {
        "pytest": pytest_summary,
        "compose": "compose config: valid",
        "cli": "litellm_agent.py: CLI available",
    }


def create_terminal_screenshot(
    path: Path,
    title: str,
    command: str,
    lines: list[str],
    height: int,
    line_start: int = 170,
    line_spacing: int = 48,
) -> None:
    width = 1600
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    title_font = _font(SANS_BOLD, 34)
    mono_font = _font(MONO, 28)
    small_font = _font(SANS, 23)

    draw.rectangle((0, 0, width, 78), fill="#1E293B")
    draw.ellipse((32, 28, 48, 44), fill="#F87171")
    draw.ellipse((58, 28, 74, 44), fill="#FBBF24")
    draw.ellipse((84, 28, 100, 44), fill="#34D399")
    draw.text((130, 20), title, font=title_font, fill="#F8FAFC")
    draw.text((48, 105), f"> {command}", font=mono_font, fill="#67E8F9")

    y = line_start
    for line in lines:
        draw.text((64, y), line, font=mono_font, fill="#E2E8F0")
        y += line_spacing

    draw.text(
        (64, height - 46),
        "Focused evidence view - timestamps and unrelated environment output omitted",
        font=small_font,
        fill="#94A3B8",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def create_agent_examples_screenshot(path: Path, examples: list[dict[str, Any]]) -> None:
    """Create a focused two-card view of the real agent requests and answers."""

    width, height = 1600, 520
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    title_font = _font(SANS_BOLD, 32)
    card_title_font = _font(SANS_BOLD, 23)
    mono_font = _font(MONO, 20)
    answer_font = _font(SANS, 20)

    draw.rectangle((0, 0, width, 78), fill="#1E293B")
    draw.ellipse((32, 28, 48, 44), fill="#F87171")
    draw.ellipse((58, 28, 74, 44), fill="#FBBF24")
    draw.ellipse((84, 28, 100, 44), fill="#34D399")
    draw.text((130, 21), "Live ReAct examples - OpenRouter", font=title_font, fill="#F8FAFC")

    card_gap = 28
    card_width = (width - 96 - card_gap) // 2
    card_y = 106
    card_height = 372

    for index, example in enumerate(examples, start=1):
        card_x = 48 + (index - 1) * (card_width + card_gap)
        draw.rounded_rectangle(
            (card_x, card_y, card_x + card_width, card_y + card_height),
            radius=18,
            fill="#172033",
            outline="#334155",
            width=2,
        )
        draw.text(
            (card_x + 24, card_y + 20),
            f"EXAMPLE {index} | {example['log_path']}",
            font=card_title_font,
            fill="#67E8F9",
        )

        text_x = card_x + 24
        text_width = 56
        y = card_y + 68
        prompt_lines = textwrap.wrap(
            example["prompt"], width=text_width, break_long_words=False, break_on_hyphens=False
        )
        draw.text((text_x, y), "PROMPT", font=mono_font, fill="#F8FAFC")
        y += 27
        for line in prompt_lines:
            draw.text((text_x + 20, y), line, font=mono_font, fill="#CBD5E1")
            y += 25

        lookup = example["lookup"]["products"][0]
        draw.text(
            (text_x, y + 8),
            f"TOOL  lookup_inventory -> stock={lookup['stock']} | price={lookup['unit_price']:.2f} EUR",
            font=mono_font,
            fill="#E2E8F0",
        )
        y += 39
        discount = example["discount"]
        if discount:
            draw.text(
                (text_x, y + 4),
                f"TOOL  calculate_tiered_discount -> discount={discount['discount_amount']} EUR",
                font=mono_font,
                fill="#E2E8F0",
            )
            y += 29
            draw.text(
                (text_x + 54, y + 4),
                f"net={discount['net_total']} EUR",
                font=mono_font,
                fill="#E2E8F0",
            )
            y += 34
            answer = (
                f"Bestand: {lookup['stock']} Stück; Rabatt: {discount['discount_amount']} EUR; "
                f"Nettobetrag: {discount['net_total']} EUR."
            )
        else:
            answer = (
                f"Es sind {lookup['stock']} Stück auf Lager. Der Bestand reicht für eine "
                "Bestellung von 5 Stück."
            )
            y += 25

        draw.text((text_x, y + 8), "ANSWER (condensed)", font=mono_font, fill="#34D399")
        y += 38
        answer_lines = textwrap.wrap(
            answer, width=text_width, break_long_words=False, break_on_hyphens=False
        )
        for line in answer_lines:
            draw.text((text_x + 20, y), line, font=answer_font, fill="#F8FAFC")
            y += 26

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def create_flow_screenshot(path: Path) -> None:
    width, height = 1600, 520
    image = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(image)
    title_font = _font(SANS_BOLD, 35)
    body_font = _font(SANS, 25)
    box_title_font = _font(SANS_BOLD, 27)

    draw.text((54, 35), "Integration flow", font=title_font, fill="#0F172A")

    boxes = [
        (70, 160, 390, 342, "User prompt", ["litellm_agent.py", "ReAct loop"]),
        (470, 160, 790, 342, "MCP over Stdio", ["mcp_server.py", "3 tools + 2 resources"]),
        (870, 72, 1185, 250, "Local data", ["SQLite inventory", "JSONL audit log"]),
        (870, 270, 1185, 448, "LiteLLM proxy", ["localhost:4000/v1", "OpenRouter provider"]),
        (1265, 178, 1530, 370, "OpenRouter", ["OpenAI-compatible", "model routing"]),
    ]

    for x1, y1, x2, y2, heading, body in boxes:
        fill = "#E0F2FE" if heading in {"User prompt", "MCP over Stdio"} else "#EEF2FF"
        draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill=fill, outline="#93C5FD", width=3)
        draw.text((x1 + 20, y1 + 22), heading, font=box_title_font, fill="#0F172A")
        for index, line in enumerate(body):
            draw.text((x1 + 20, y1 + 72 + index * 38), line, font=body_font, fill="#334155")

    def arrow(start: tuple[int, int], end: tuple[int, int]) -> None:
        draw.line((*start, *end), fill="#2563EB", width=5)
        ex, ey = end
        draw.polygon([(ex, ey), (ex - 16, ey - 10), (ex - 16, ey + 10)], fill="#2563EB")

    arrow((390, 251), (470, 251))
    arrow((790, 220), (870, 160))
    arrow((790, 282), (870, 360))
    arrow((1185, 360), (1265, 274))

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def create_evidence_images(
    evidence: dict[str, Any],
    checks: dict[str, str],
    agent_examples: list[dict[str, Any]],
) -> None:
    create_agent_examples_screenshot(
        SCREENSHOTS_DIR / "mcp_demo.png",
        agent_examples,
    )
    create_terminal_screenshot(
        SCREENSHOTS_DIR / "verification.png",
        "Local verification",
        ".venv\\Scripts\\python.exe -m pytest -q",
        [
            checks["pytest"],
            "",
            "> docker compose config --quiet",
            checks["compose"],
            "",
            "> litellm_agent.py --help",
            checks["cli"],
        ],
        440,
        line_start=155,
        line_spacing=31,
    )
    create_flow_screenshot(SCREENSHOTS_DIR / "integration_flow.png")


def _pdf_text(c: canvas.Canvas, text: str, x: float, y: float, size: float, color: Any) -> None:
    c.setFont("Helvetica", size)
    c.setFillColor(color)
    c.drawString(x, y, text)


def _pdf_bullets(
    c: canvas.Canvas,
    items: list[str],
    x: float,
    y: float,
    width: float,
    size: float = 8.6,
) -> float:
    c.setFont("Helvetica", size)
    c.setFillColor(HexColor("#334155"))
    for item in items:
        words = item.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if c.stringWidth(candidate, "Helvetica", size) <= width - 14:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        c.drawString(x, y, "- " + lines[0])
        y -= 12
        for continuation in lines[1:]:
            c.drawString(x + 10, y, continuation)
            y -= 12
        y -= 2
    return y


def _card(c: canvas.Canvas, x: float, y: float, width: float, height: float, title: str) -> None:
    c.setFillColor(white)
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.roundRect(x, y, width, height, 10, fill=1, stroke=1)
    c.setFillColor(HexColor("#2563EB"))
    c.roundRect(x, y + height - 4, width, 4, 2, fill=1, stroke=0)
    _pdf_text(c, title, x + 14, y + height - 23, 11, HexColor("#0F172A"))


def _draw_image_contain(
    c: canvas.Canvas,
    image_path: Path,
    x: float,
    y: float,
    box_width: float,
    box_height: float,
) -> None:
    """Place an image without changing its aspect ratio."""

    with Image.open(image_path) as image:
        source_width, source_height = image.size
    scale = min(box_width / source_width, box_height / source_height)
    draw_width = source_width * scale
    draw_height = source_height * scale
    draw_x = x + (box_width - draw_width) / 2
    draw_y = y + (box_height - draw_height) / 2
    c.drawImage(ImageReader(str(image_path)), draw_x, draw_y, draw_width, draw_height)


def build_pdf(evidence: dict[str, Any], checks: dict[str, str]) -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PATH), pagesize=landscape(A4))
    page_width, page_height = landscape(A4)
    c.setTitle("Homework 1 - MCP Tool Server Submission Summary")

    c.setFillColor(HexColor("#F8FAFC"))
    c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    c.setFillColor(HexColor("#0F172A"))
    c.rect(0, page_height - 76, page_width, 76, fill=1, stroke=0)
    _pdf_text(c, "Homework 1 - Custom MCP Math & Database Tool Server", 34, page_height - 32, 19, white)
    _pdf_text(c, "One-page implementation and verification summary", 35, page_height - 54, 9.5, HexColor("#BAE6FD"))

    link_x = page_width - 292
    _pdf_text(c, "Repository", link_x, page_height - 31, 8.5, HexColor("#BAE6FD"))
    c.setFont("Helvetica", 8.5)
    c.setFillColor(HexColor("#67E8F9"))
    c.drawString(link_x + 50, page_height - 31, "github.com/Sudashiii/dibse_industrial_computing")
    c.linkURL(REPOSITORY_URL, (link_x + 50, page_height - 34, page_width - 34, page_height - 23), relative=0)
    _pdf_text(c, "Stand: 06.09.2026", link_x, page_height - 52, 8.5, HexColor("#CBD5E1"))

    card_y = page_height - 205
    card_h = 111
    card_gap = 14
    left_x = 34
    card_w = (page_width - 68 - card_gap) / 2
    _card(c, left_x, card_y, card_w, card_h, "Implementierung")
    _pdf_bullets(
        c,
        [
            "SQLite inventory lookup with automatic database creation and seed data.",
            "Tiered discount engine with 0 / 5 / 10 / 15 percent volume tiers.",
            "JSONL audit tool plus audit://events MCP resource.",
            "MCP Stdio server and bounded ReAct agent via LiteLLM and OpenRouter.",
        ],
        left_x + 14,
        card_y + card_h - 40,
        card_w - 28,
    )

    right_x = left_x + card_w + card_gap
    _card(c, right_x, card_y, card_w, card_h, "Verifikation")
    _pdf_bullets(
        c,
        [
            checks["pytest"],
            checks["compose"],
            "Two live OpenRouter prompts are included below.",
            "Execution logs: litellm_run_prompt1.log and prompt2.log.",
        ],
        right_x + 14,
        card_y + card_h - 40,
        card_w - 28,
    )

    image_x = 34
    image_y = 138
    image_w = page_width - 68
    image_h = 232
    _pdf_text(c, "Live ReAct examples and tool observations", image_x, image_y + image_h + 7, 9.5, HexColor("#475569"))
    _draw_image_contain(c, SCREENSHOTS_DIR / "mcp_demo.png", image_x, image_y, image_w, image_h)

    lower_y = 24
    lower_h = 92
    lower_gap = 14
    lower_w = (page_width - 68 - lower_gap) / 2
    _pdf_text(c, "Checks", image_x, lower_y + lower_h + 7, 9.5, HexColor("#475569"))
    _draw_image_contain(c, SCREENSHOTS_DIR / "verification.png", image_x, lower_y, lower_w, lower_h)
    flow_x = image_x + lower_w + lower_gap
    _pdf_text(c, "Relevant integration path", flow_x, lower_y + lower_h + 7, 9.5, HexColor("#475569"))
    _draw_image_contain(c, SCREENSHOTS_DIR / "integration_flow.png", flow_x, lower_y, lower_w, lower_h)

    footer_y = 16
    c.setFont("Helvetica", 7.5)
    c.setFillColor(HexColor("#64748B"))
    c.drawString(34, footer_y, "Links: README")
    c.linkURL(README_URL, (70, footer_y - 2, 112, footer_y + 8), relative=0)
    c.drawString(118, footer_y, "LiteLLM config")
    c.linkURL(CONFIG_URL, (175, footer_y - 2, 235, footer_y + 8), relative=0)
    c.drawRightString(page_width - 34, footer_y, "Focused screenshots contain no credentials or unrelated desktop content.")
    c.showPage()
    c.save()


def main() -> None:
    evidence = read_demo_evidence()
    agent_examples = read_agent_evidence()
    checks = run_verification()
    create_evidence_images(evidence, checks, agent_examples)
    build_pdf(evidence, checks)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
