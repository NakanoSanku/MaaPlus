"""Generate redistributable fixtures, without game screenshots or OCR model downloads."""
from __future__ import annotations

import random

from PIL import Image, ImageDraw

from .project import Project


def _button(size, seed, label):
    rng = random.Random(seed)
    image = Image.new("RGB", size)
    image.putdata([(rng.randrange(40, 200), rng.randrange(60, 230), rng.randrange(80, 240))
                   for _ in range(size[0] * size[1])])
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, size[0] - 5, size[1] - 5), outline="white", width=3)
    draw.text((14, size[1] // 2 - 5), label, fill="white")
    return image


def create_demo(root):
    project = Project.create(root)
    page = project.add_page("ChallengeUI", "ui/generated/challenge.py")
    challenge = _button((170, 90), 17, "CHALLENGE")
    back = _button((90, 60), 23, "BACK")
    source = Image.new("RGB", (1280, 720), (35, 45, 62))
    source.paste(challenge, (1050, 570))
    source.paste(back, (35, 30))
    positive = Image.new("RGB", (1280, 720), (62, 42, 35))
    positive.paste(challenge, (1046, 574))
    positive.paste(back, (39, 33))
    negative = Image.new("RGB", (1280, 720), (20, 30, 40))
    shots = [project.add_screenshot(image, {"kind": "synthetic", "name": name})
             for image, name in ((source, "crop-source"), (positive, "shifted-positive"), (negative, "negative"))]
    a = project.put_element(page, name="CHALLENGE", shot_id=shots[0], crop=[1050, 570, 170, 90],
                            roi=[1030, 550, 220, 140], threshold=0.9)
    b = project.put_element(page, name="BACK", shot_id=shots[0], crop=[35, 30, 90, 60],
                            roi=[10, 10, 150, 100], threshold=0.9)
    c = project.put_element(page, name="READY", kind="AllOf", refs=[a, b], box_index=0)
    for sid, boxes in ((shots[0], ([1050, 570, 170, 90], [35, 30, 90, 60])),
                       (shots[1], ([1046, 574, 170, 90], [39, 33, 90, 60]))):
        for eid, box in ((a, boxes[0]), (b, boxes[1]), (c, boxes[0])):
            project.expect(page, sid, eid, True, box)
    for eid in (a, b, c):
        project.expect(page, shots[2], eid, False)
    project.generate()
    return project
