# MaaPlus

MaaPlus is a code-first layer for building game automation with MaaFramework. Its domain language
describes repeated observations of a game UI, decisions at safe handoff points, and actions that
change the observed UI.

## Language

**Tick**:
One observation window in which a task handler makes a decision from one captured game screen.
_Avoid_: Frame, loop iteration

**Task**:
A named piece of game work that may remain active across multiple ticks and may yield ownership to
higher-priority work.
_Avoid_: Thread, pipeline node

**Task result**:
The handler's decision after one tick: continue owning the current UI state, yield at a safe point,
or finish the task.
_Avoid_: Status code, event

**Safe point**:
A handler boundary at which unfinished work has left the game UI in a state another task can safely
observe or take over.
_Avoid_: Sleep, retry point

**Locator**:
A declaration of the visual evidence used to decide whether a UI state is present. MaaFramework
provides the recognition algorithms; MaaPlus carries their result into handler code.
_Avoid_: Selector, custom recognizer

**Recognition result**:
The outcome of applying one locator to a tick's captured screen, including whether it hit and, when
available, the screen rectangle that was recognized.
_Avoid_: Match object, element

**Debug snapshot**:
An annotated copy of a captured screen that records the locator decision, search region, or manual
probe without changing the screen used for recognition.
_Avoid_: Screenshot, log line

**Inspection**:
A recognition-only evaluation of a locator against a known screen, with no controller input.
_Avoid_: Replay, task run

**Fixture**:
A stable screen and its optional expected recognition data used to reproduce one inspection.
_Avoid_: Resource bundle, test mock

**Trace**:
An ordered record of task decisions, recognition outcomes, controller intentions, and timings from
an automation run.
_Avoid_: Console output, debug snapshot

**Execution context**:
The state belonging to one scheduled run of a task, from its start until it finishes, fails, or is
cancelled.
_Avoid_: Tick, handler instance

**Context activation**:
The period in which a task acquires or reacquires ownership of its required UI context. Navigator
restoration runs at activation; after `READY`, the task handler owns its private substates until it
yields or finishes.
_Avoid_: Every tick, scene cache

**Global guard**:
An application-wide check that runs on the current Tick before routing and task business logic, used
for UI conditions that may interrupt any task. An idle watcher can run the same checks between tasks.
_Avoid_: High-priority task, background thread

**Application instance**:
One independent `App` and its MaaFramework runtime bound to one device. Its scheduler, route
state, guards, traces, debug output, and lifecycle are isolated from other instances.
_Avoid_: Task, background thread

**Instance manager**:
The optional orchestration layer that creates, starts, pauses, resumes, stops, and observes one
application instance per device. It does not arbitrate multiple apps targeting the same device.
_Avoid_: Scheduler, device pool

**Guard result**:
The guard's decision to ignore the current screen, handle it and defer the task, invalidate the
task's route, or abort the task.
_Avoid_: Task result, recognition result

**Task failure**:
A terminal outcome for one task execution after its configured recovery attempts are exhausted.
_Avoid_: Scheduler failure, recognition miss

**Inspection session**:
A sequence of fixture inspections that records recognition evidence without granting controller
input authority.
_Avoid_: Replay session, live run

**First-run path**:
The shortest supported journey from an installed MaaPlus project to one verified recognition
result, without requiring a live device.
_Avoid_: Installation guide, quickstart page

**Fixture assertion**:
The expected recognition outcome attached to a fixture, including hit state and optional geometry
constraints.
_Avoid_: Snapshot comparison, mock assertion

**Failure report**:
A human-readable account of one failed task or inspection that points to the evidence needed for
the next diagnosis step.
_Avoid_: Trace, exception string

**Task status**:
The observable lifecycle state of a scheduled task at a point in time, including whether it is
waiting, running, paused, complete, failed, or cancelled.
_Avoid_: Task result, log level

**Offline example**:
A runnable project path that demonstrates recognition and task behavior against fixtures without
requiring a connected device.
_Avoid_: Mock project, replay run

**Fixture runner**:
The repeatable operation that evaluates one or more fixtures with a locator and produces
recognition results and assertions.
_Avoid_: Inspection, test case

**Failure artifact**:
The collection of readable and structured evidence produced for one failed task or fixture run.
_Avoid_: Log file, debug snapshot

**Task lifecycle**:
The current state of a task registration across scheduling, execution, completion, failure, and
cancellation.
_Avoid_: Execution context, task result

**Execution summary**:
The outcome and evidence for the most recent execution of a task, separate from the task's current
lifecycle.
_Avoid_: Task status, trace

**Device diagnosis**:
A preflight assessment of the available MaaFramework runtime, resources, devices, and controller
capabilities before a live run.
_Avoid_: Connection attempt, health check

**Locator reference**:
The stable project-level name used to select one locator for an inspection or fixture run.
_Avoid_: Locator instance, resource path

**Trace session**:
One bounded capture of task, recognition, controller, and inspection evidence with a shared identity.
_Avoid_: Log file, scheduler run

**Navigation wait policy**:
The explicit choice of whether a task keeps or releases UI ownership while its required context is
being restored.
_Avoid_: Task priority, retry policy

**Recurring failure policy**:
The rule that determines whether a periodic task remains scheduled after one execution reaches a
terminal failure.
_Avoid_: Retry count, task cancellation

**Image format**:
The channel ordering and color interpretation attached to a screenshot supplied for recognition.
_Avoid_: Resolution, fixture type
