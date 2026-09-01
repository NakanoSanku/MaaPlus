from maaplus import Template


class CommonUI:
    BACK = Template(
        template=["common/back.png"],
        threshold=[0.85],
    )

    LOADING = Template(
        template=["common/loading.png"],
        threshold=[0.85],
    )
