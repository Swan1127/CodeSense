from pathlib import Path

from PIL import Image

from scripts.compose_guided_learning_illustration import COPY, layout_boxes


OUTPUT = Path(
    "research/guided_learning_paper/figures/activity_chain_evidence_illustrated.png"
)


def test_illustrated_figure_has_fixed_copy_and_non_overlapping_regions():
    required = {
        "状态驱动的三阶段程序设计引导方法",
        "教师型智能体",
        "真实学生",
        "虚拟学生",
        "1 思路外化",
        "2 程序构建",
        "3 讲解纠错",
        "日志不能直接证明：认知质量、学习增益与因果效果",
    }
    assert required <= set(COPY.values())

    boxes = layout_boxes()
    names = list(boxes)
    for index, left_name in enumerate(names):
        lx1, ly1, lx2, ly2 = boxes[left_name]
        for right_name in names[index + 1 :]:
            rx1, ry1, rx2, ry2 = boxes[right_name]
            assert lx2 <= rx1 or rx2 <= lx1 or ly2 <= ry1 or ry2 <= ly1, (
                left_name,
                right_name,
            )


def test_illustrated_figure_is_print_ready():
    image = Image.open(OUTPUT)
    assert image.size == (3200, 1800)
    assert image.mode == "RGB"


def test_ai_role_asset_is_large_and_text_free_by_contract():
    asset = Path(
        "research/guided_learning_paper/figures/assets/ai_three_role_scene.png"
    )
    image = Image.open(asset)
    assert image.width >= 1600
    assert image.height >= 900
    assert image.mode == "RGB"
