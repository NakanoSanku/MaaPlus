# Offline fixture project

This example runs without ADB or a game. It demonstrates the complete development loop:

1. create a deterministic screenshot fixture;
2. inspect one locator without controller input;
3. run the same locator through an `App` task;
4. retain the annotated PNG and JSONL trace in one session directory.

Run it from the repository root:

```bash
uv run python examples/fixture_project/main.py
```

The fake Tasker/controller are intentionally tiny. Replace them with `DbgController`, a real
Tasker, and a Resource when moving to a game project.
