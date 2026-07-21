from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw, ImageFont


CANVAS = (3200, 1800)

COPY = {
    "title": "状态驱动的三阶段程序设计引导方法",
    "subtitle": "智能体依据本次会话状态调整支架，学习任务始终由学生完成",
    "state_layer": "会话状态层",
    "role_layer": "角色协作层",
    "activity_layer": "学习活动层",
    "evidence_layer": "证据边界层",
    "state": "当前会话状态",
    "teacher": "教师型智能体",
    "teacher_reads": "读取：回答、提示次数、进度、验证结果",
    "teacher_outputs": "输出：提示、诊断、支架",
    "student": "真实学生",
    "student_actions": "表达思路 · 判断结构 · 讲解与修正",
    "virtual_student": "虚拟学生",
    "virtual_actions": "连续追问 · 呈现错误代码",
    "stage1": "1 思路外化",
    "stage1_action": "说明算法步骤与边界",
    "stage2": "2 程序构建",
    "stage2_action": "识别结构并验证修正",
    "stage3": "3 讲解纠错",
    "stage3_action": "向虚拟学生讲解并修正错误",
    "observable": "日志可观察：进入、提示、验证、对话、修正、完成与退出",
    "boundary": "日志不能直接证明：认知质量、学习增益与因果效果",
}

COLORS = {
    "ink": "#172033",
    "muted": "#66758C",
    "canvas": "#F6F8FC",
    "white": "#FFFFFF",
    "blue": "#2563EB",
    "blue_dark": "#1D4ED8",
    "blue_pale": "#EAF2FF",
    "green": "#059669",
    "green_pale": "#E9F9F3",
    "orange": "#D97706",
    "orange_pale": "#FFF3E5",
    "purple": "#7C3AED",
    "purple_pale": "#F3EEFF",
    "line": "#D5DDEA",
    "boundary": "#718096",
}


def layout_boxes() -> dict[str, tuple[int, int, int, int]]:
    return {
        "state": (120, 205, 3080, 350),
        "roles": (120, 385, 3080, 1075),
        "stage1": (120, 1135, 1040, 1460),
        "stage2": (1140, 1135, 2060, 1460),
        "stage3": (2160, 1135, 3080, 1460),
        "observable": (120, 1520, 1960, 1725),
        "boundary": (2040, 1520, 3080, 1725),
    }


def _font_path(bold: bool = False) -> Path:
    candidates = (
        [
            Path(r"C:\Windows\Fonts\msyhbd.ttc"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
        ]
        if bold
        else [
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\simsun.ttc"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No supported Chinese font found in C:\\Windows\\Fonts")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_font_path(bold)), size=size)


def _rounded_panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str,
    radius: int = 34,
    width: int = 4,
    shadow: bool = True,
    dashed: bool = False,
) -> None:
    draw = ImageDraw.Draw(image)
    if shadow:
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(
            (x1 + 8, y1 + 10, x2 + 8, y2 + 10),
            radius=radius,
            fill="#E4E9F2",
        )
    if not dashed:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
        return

    draw.rounded_rectangle(box, radius=radius, fill=fill)
    x1, y1, x2, y2 = box
    dash = 30
    gap = 18
    for start in range(x1 + radius, x2 - radius, dash + gap):
        draw.line((start, y1, min(start + dash, x2 - radius), y1), fill=outline, width=width)
        draw.line((start, y2, min(start + dash, x2 - radius), y2), fill=outline, width=width)
    for start in range(y1 + radius, y2 - radius, dash + gap):
        draw.line((x1, start, x1, min(start + dash, y2 - radius)), fill=outline, width=width)
        draw.line((x2, start, x2, min(start + dash, y2 - radius)), fill=outline, width=width)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and _text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    *,
    fill: str,
    line_gap: int = 10,
    max_width: int | None = None,
) -> None:
    x1, y1, x2, y2 = box
    width = max_width or (x2 - x1)
    lines = _wrap_text(draw, text, font, width)
    bbox = draw.textbbox((0, 0), "国Ag", font=font)
    line_height = bbox[3] - bbox[1]
    total_height = len(lines) * line_height + max(0, len(lines) - 1) * line_gap
    y = y1 + (y2 - y1 - total_height) / 2
    for line in lines:
        line_width = _text_width(draw, line, font)
        x = x1 + (x2 - x1 - line_width) / 2
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height + line_gap


def _draw_layer_tag(draw: ImageDraw.ImageDraw, text: str, y: int) -> None:
    box = (120, y, 350, y + 64)
    draw.rounded_rectangle(box, radius=22, fill=COLORS["ink"])
    _draw_centered_lines(draw, box, text, _font(31, True), fill=COLORS["white"])


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str,
    width: int = 12,
    head: int = 24,
) -> None:
    draw.line((*start, *end), fill=color, width=width)
    x2, y2 = end
    x1, y1 = start
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 > x1 else -1
        points = [(x2, y2), (x2 - direction * head, y2 - head // 2), (x2 - direction * head, y2 + head // 2)]
    else:
        direction = 1 if y2 > y1 else -1
        points = [(x2, y2), (x2 - head // 2, y2 - direction * head), (x2 + head // 2, y2 - direction * head)]
    draw.polygon(points, fill=color)


def _trim_white(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, "white")
    difference = ImageChops.difference(rgb, background).convert("L")
    mask = difference.point(lambda value: 255 if value > 10 else 0)
    bbox = mask.getbbox()
    return rgb.crop(bbox) if bbox else rgb


def _fit(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    result = image.copy()
    result.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return result


def _paste_center(
    canvas: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    x = x1 + (x2 - x1 - image.width) // 2
    y = y1 + (y2 - y1 - image.height) // 2
    canvas.paste(image, (x, y))


def _role_crops(asset: Image.Image) -> Iterable[Image.Image]:
    width, height = asset.size
    boundaries = (
        (0, int(width * 0.37)),
        (int(width * 0.405), int(width * 0.75)),
        (int(width * 0.75), width),
    )
    for left, right in boundaries:
        yield _trim_white(asset.crop((left, 0, right, height)))


def compose_figure(asset_path: Path, output_path: Path) -> None:
    canvas = Image.new("RGBA", CANVAS, COLORS["canvas"])
    draw = ImageDraw.Draw(canvas)
    boxes = layout_boxes()

    title_font = _font(72, True)
    subtitle_font = _font(36)
    _draw_centered_lines(draw, (180, 36, 3020, 115), COPY["title"], title_font, fill=COLORS["ink"])
    _draw_centered_lines(draw, (260, 125, 2940, 180), COPY["subtitle"], subtitle_font, fill=COLORS["muted"])

    _rounded_panel(canvas, boxes["state"], fill=COLORS["purple_pale"], outline=COLORS["purple"], radius=30)
    _draw_layer_tag(draw, COPY["state_layer"], 225)
    state_label = (395, 235, 830, 320)
    draw.rounded_rectangle(state_label, radius=25, fill=COLORS["purple"])
    _draw_centered_lines(draw, state_label, COPY["state"], _font(40, True), fill=COLORS["white"])
    chips = ["回答", "提示次数", "阶段进度", "错误/未答", "验证结果", "最近对话"]
    chip_x = 880
    for chip in chips:
        chip_width = max(210, _text_width(draw, chip, _font(32, True)) + 70)
        chip_box = (chip_x, 240, chip_x + chip_width, 315)
        draw.rounded_rectangle(chip_box, radius=24, fill=COLORS["white"], outline=COLORS["line"], width=3)
        _draw_centered_lines(draw, chip_box, chip, _font(32, True), fill=COLORS["ink"])
        chip_x += chip_width + 28

    _rounded_panel(canvas, boxes["roles"], fill=COLORS["white"], outline=COLORS["line"], radius=42)
    _draw_layer_tag(draw, COPY["role_layer"], 405)

    role_columns = {
        "teacher": (210, 455, 1050, 1045),
        "student": (1180, 455, 2020, 1045),
        "virtual": (2150, 455, 2990, 1045),
    }
    role_badges = {
        "teacher": (360, 430, 900, 510),
        "student": (1330, 430, 1870, 510),
        "virtual": (2300, 430, 2840, 510),
    }
    role_colors = {
        "teacher": (COLORS["blue"], COLORS["blue_pale"]),
        "student": (COLORS["green"], COLORS["green_pale"]),
        "virtual": (COLORS["orange"], COLORS["orange_pale"]),
    }
    role_titles = {
        "teacher": COPY["teacher"],
        "student": COPY["student"],
        "virtual": COPY["virtual_student"],
    }
    for role, badge in role_badges.items():
        primary, pale = role_colors[role]
        draw.rounded_rectangle(badge, radius=28, fill=pale, outline=primary, width=4)
        _draw_centered_lines(draw, badge, role_titles[role], _font(42, True), fill=primary)

    _draw_arrow(draw, (1020, 585), (1185, 585), color=COLORS["blue"], width=11)
    _draw_centered_lines(draw, (970, 515, 1235, 565), "提示·诊断", _font(28, True), fill=COLORS["blue_dark"])
    _draw_arrow(draw, (2020, 575), (2160, 575), color=COLORS["orange"], width=11)
    _draw_centered_lines(draw, (1990, 510, 2190, 555), "讲解", _font(28, True), fill=COLORS["orange"])
    _draw_arrow(draw, (2160, 635), (2020, 635), color=COLORS["orange"], width=8)
    _draw_centered_lines(draw, (1980, 645, 2200, 690), "追问·纠错", _font(26, True), fill=COLORS["orange"])

    asset = Image.open(asset_path).convert("RGB")
    crops = list(_role_crops(asset))
    image_boxes = ((220, 525, 1040, 910), (1190, 525, 2010, 910), (2160, 525, 2980, 910))
    for crop, image_box in zip(crops, image_boxes, strict=True):
        fitted = _fit(crop, image_box[2] - image_box[0], image_box[3] - image_box[1])
        _paste_center(canvas, fitted, image_box)

    detail_boxes = {
        "teacher": (230, 900, 1030, 1040),
        "student": (1200, 920, 2000, 1035),
        "virtual": (2170, 920, 2970, 1035),
    }
    _draw_centered_lines(draw, (250, 900, 1010, 965), COPY["teacher_reads"], _font(28), fill=COLORS["ink"], max_width=740)
    _draw_centered_lines(draw, (250, 968, 1010, 1030), COPY["teacher_outputs"], _font(30, True), fill=COLORS["blue_dark"], max_width=740)
    _draw_centered_lines(draw, detail_boxes["student"], COPY["student_actions"], _font(31, True), fill=COLORS["green"], max_width=740)
    _draw_centered_lines(draw, detail_boxes["virtual"], COPY["virtual_actions"], _font(31, True), fill=COLORS["orange"], max_width=740)

    _draw_layer_tag(draw, COPY["activity_layer"], 1065)
    stage_specs = (
        ("stage1", COPY["stage1"], COPY["stage1_action"], COLORS["blue"], COLORS["blue_pale"]),
        ("stage2", COPY["stage2"], COPY["stage2_action"], COLORS["green"], COLORS["green_pale"]),
        ("stage3", COPY["stage3"], COPY["stage3_action"], COLORS["orange"], COLORS["orange_pale"]),
    )
    for key, heading, action, primary, pale in stage_specs:
        box = boxes[key]
        _rounded_panel(canvas, box, fill=pale, outline=primary, radius=38)
        number = heading.split()[0]
        circle = (box[0] + 54, box[1] + 48, box[0] + 150, box[1] + 144)
        draw.ellipse(circle, fill=primary)
        _draw_centered_lines(draw, circle, number, _font(46, True), fill=COLORS["white"])
        heading_text = heading.split(" ", 1)[1]
        _draw_centered_lines(draw, (box[0] + 170, box[1] + 42, box[2] - 45, box[1] + 150), heading_text, _font(49, True), fill=primary)
        _draw_centered_lines(draw, (box[0] + 70, box[1] + 165, box[2] - 70, box[3] - 30), action, _font(38), fill=COLORS["ink"], max_width=760)

    _draw_arrow(draw, (1050, 1298), (1130, 1298), color=COLORS["muted"], width=10)
    _draw_arrow(draw, (2070, 1298), (2150, 1298), color=COLORS["muted"], width=10)
    _draw_centered_lines(draw, (1130, 1076, 2070, 1130), "支架随当前状态贯穿三个阶段", _font(34, True), fill=COLORS["ink"])

    _rounded_panel(canvas, boxes["observable"], fill=COLORS["blue_pale"], outline=COLORS["blue"], radius=34, shadow=False)
    _rounded_panel(canvas, boxes["boundary"], fill=COLORS["white"], outline=COLORS["boundary"], radius=34, shadow=False, dashed=True)
    _draw_layer_tag(draw, COPY["evidence_layer"], 1460)
    _draw_centered_lines(draw, (370, 1550, 1925, 1700), COPY["observable"], _font(39, True), fill=COLORS["blue_dark"], max_width=1470)
    _draw_centered_lines(draw, (2080, 1550, 3040, 1700), COPY["boundary"], _font(36, True), fill=COLORS["boundary"], max_width=890)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, quality=96)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compose_figure(args.asset, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
