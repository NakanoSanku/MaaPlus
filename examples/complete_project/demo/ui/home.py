from maa.pipeline import JTemplateMatch


class HomeUI:
    MARKER = JTemplateMatch(
        template=["home/marker.png"],
        threshold=[0.85],
    )

    EXPLORE = JTemplateMatch(
        template=["home/explore.png"],
        threshold=[0.85],
    )

    DRAW = JTemplateMatch(
        template=["home/draw.png"],
        threshold=[0.85],
    )
