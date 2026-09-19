from maa.pipeline import JOCR, JTemplateMatch


class DrawUI:
    MARKER = JTemplateMatch(
        template=["draw/marker.png"],
        threshold=[0.85],
    )

    FREE_DRAW = JOCR(
        expected=["免费"],
    )

    CONFIRM = JOCR(
        expected=["确定"],
    )

    RESULT_CLOSE = JTemplateMatch(
        template=["draw/result_close.png"],
        threshold=[0.85],
    )
