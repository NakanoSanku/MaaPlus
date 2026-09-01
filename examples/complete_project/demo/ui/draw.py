from maaplus import OCR, Template


class DrawUI:
    MARKER = Template(
        template=["draw/marker.png"],
        threshold=[0.85],
    )

    FREE_DRAW = OCR(
        expected=["免费"],
    )

    CONFIRM = OCR(
        expected=["确定"],
    )

    RESULT_CLOSE = Template(
        template=["draw/result_close.png"],
        threshold=[0.85],
    )
