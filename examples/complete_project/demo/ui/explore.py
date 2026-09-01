from maaplus import OCR, Template


class ExploreUI:
    MARKER = Template(
        template=["explore/marker.png"],
        threshold=[0.85],
    )

    MONSTER = Template(
        template=["explore/monster.png"],
        threshold=[0.82],
    )

    BATTLE = Template(
        template=["battle/auto.png"],
        threshold=[0.85],
    )

    BATTLE_RESULT = OCR(
        expected=["胜利", "失败"],
    )

    RESULT_CONFIRM = OCR(
        expected=["确定", "继续"],
    )
