# Pause periodic tasks after terminal failure

Periodic tasks will pause after an execution exhausts its configured retries. Applications may opt
into continued recurrence with `continue_recurring=True`, but the safe default prevents a broken
recognizer or controller action from repeating against a live game indefinitely. `TaskHandle.resume()`
starts a fresh execution context while preserving the last failure summary.
