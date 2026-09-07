"""Run under Xvfb on Linux, or an ordinary Windows/macOS desktop."""
import os
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Needs a display or Xvfb")


@pytest.fixture
def gui(tmp_path):
    import tkinter as tk
    from maaplus_studio.demo import create_demo
    from maaplus_studio.gui import Studio
    root = tk.Tk()
    app = Studio(root, create_demo(tmp_path))
    root.update()
    page = app.project.data["pages"][0]
    app.page_id = page["id"]
    sid = app.project.data["screenshots"][0]["id"]
    app.display_frame(app.project.image(sid), shot_id=sid)
    root.update()
    yield app
    app.form_dirty = False
    app.close()


def test_actual_window_and_code_preview(gui):
    assert "ChallengeUI" in gui.code.get("1.0", "end")
    assert len(gui.tree.get_children()) == 1
    assert gui.canvas.find_all()


def test_zoom_and_scroll_coordinates(gui):
    gui.zoom(2.0)
    gui.root.update()
    gui.canvas.xview_moveto(0.2)
    gui.canvas.yview_moveto(0.1)
    gui.root.update()
    a, b = SimpleNamespace(x=20, y=30), SimpleNamespace(x=100, y=90)
    expected_start = gui.image_point(a)
    expected_end = gui.image_point(b)
    gui.start_drag(a)
    gui.move_drag(b)
    gui.end_drag(b)
    assert gui.parse_rect(gui.vars["crop"].get()) == [*expected_start, expected_end[0] - expected_start[0], expected_end[1] - expected_start[1]]
    assert gui.vars["roi"].get() == gui.vars["crop"].get()
    assert not gui.live.get()


def test_existing_element_does_not_resample_silently(gui):
    page = gui.require_page()
    element = page["elements"][0]
    gui.tree.selection_set(element["id"])
    gui.root.update()
    original_source = element["source"]
    negative = gui.project.data["screenshots"][-1]["id"]
    gui.display_frame(gui.project.image(negative), shot_id=negative)
    gui.vars["threshold"].set("0.91")
    gui.save_element()
    assert gui.project.element(gui.page_id, element["id"])["source"] == original_source


def test_background_job_keeps_tk_responsive(gui):
    events = []
    gui.root.after(20, lambda: events.append("responsive"))
    gui.async_job(lambda: (time.sleep(0.1), 17)[1], lambda value: events.append(value), "test")
    deadline = time.time() + 3
    while gui.busy and time.time() < deadline:
        gui.root.update()
        time.sleep(0.01)
    assert events == ["responsive", 17]


def test_cancelled_result_not_applied(gui):
    events = []
    gui.async_job(lambda: (time.sleep(0.1), 17)[1], events.append, "test")
    gui.disconnect()
    deadline = time.time() + 3
    while gui.busy and time.time() < deadline:
        gui.root.update()
        time.sleep(0.01)
    assert events == []
