from maa.pipeline import JCustomRecognition, JOCR, JTemplateMatch



class ExploreUI:
    MARKER = JTemplateMatch(
        template=["explore/marker.png"],
        threshold=[0.85],
    )

    MONSTER = JTemplateMatch(
        template=["explore/monster.png"],
        threshold=[0.82],
    )

    BATTLE = JCustomRecognition(
        custom_recognition="MultiPointColor",
        roi=(0, 0, 0, 0),
        custom_recognition_param={"tolerance": 18},
    )

    BATTLE_RESULT = JOCR(
        expected=["胜利", "失败"],
    )

    RESULT_CONFIRM = JOCR(
        expected=["确定", "继续"],
    )
