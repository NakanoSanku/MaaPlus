# Examples

MaaPlus keeps two example levels on purpose:

- `basic_adb.py` — minimal ADB + App example for first contact.
- `complete_project/` — recommended project structure for a real multi-task application.

Start with `basic_adb.py` if you only want to understand `Tick`, `CONTINUE / YIELD / DONE`, and `App.task()`.

Use `complete_project/` when you want to see how application code should be split into UI definitions, navigation, flows, task registration, bootstrap, and the entry point. It also demonstrates safe-point preemption and context restoration between a normal exploration task and a higher-priority recurring draw task.
