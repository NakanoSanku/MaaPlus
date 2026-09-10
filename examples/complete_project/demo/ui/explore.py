from maa.pipeline import JCustomRecognition

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

    BATTLE = JCustomRecognition(
        custom_recognition="MultiPointColor",
        roi=(0, 0, 0, 0),
        custom_recognition_param={"tolerance": 18},
    )

    BATTLE_RESULT = OCR(
        expected=["胜利", "失败"],
    )

    RESULT_CONFIRM = OCR(
        expected=["确定", "继续"],
    )
