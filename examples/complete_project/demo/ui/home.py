from maaplus import Template


class HomeUI:
    MARKER = Template(
        template=["home/marker.png"],
        threshold=[0.85],
    )

    EXPLORE = Template(
        template=["home/explore.png"],
        threshold=[0.85],
    )

    DRAW = Template(
        template=["home/draw.png"],
        threshold=[0.85],
    )
