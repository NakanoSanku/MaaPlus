from maa.pipeline import JTemplateMatch


class CommonUI:
    BACK = JTemplateMatch(
        template=["common/back.png"],
        threshold=[0.85],
    )

    LOADING = JTemplateMatch(
        template=["common/loading.png"],
        threshold=[0.85],
    )
