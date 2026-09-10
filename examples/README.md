# Examples

MaaPlus keeps two example levels on purpose:

- `basic_adb.py` — minimal ADB + App example for first contact.
- `complete_project/` — recommended project structure for a real multi-task application.
- `fixture_project/` — fully offline recognition, task, debug, and trace loop.

The complete project enables the optional bounding-box debug snapshots described in
[`docs/debugging.md`](../docs/debugging.md).

For recognition-only development, see the [fixture inspection workflow](../docs/development.md).

The complete project also demonstrates registering a NumPy-based multi-point color recognizer and
using it as a normal `Tick.match()` locator.

Start with `basic_adb.py` if you only want to understand `Tick`, task handlers, `CONTINUE / YIELD / DONE`, and `App.task()`.

Use `complete_project/` when you want to see how application code should be split into UI definitions, navigation, handlers, task registration, bootstrap, and the entry point. It also demonstrates safe-point preemption and context restoration between a normal exploration task and a higher-priority recurring draw task.
