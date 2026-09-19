# Changelog

## Unreleased

- Studio can test every exported locator on a UI page against one fixed screenshot, with progress,
  per-item results, errors, timings, and selectable match details. Failures do not stop later items;
  users can stop after the active item. Draft edits and new screenshots invalidate old results.
- Removed the `Template`, `OCR`, `FirstOf`, and `AllOf` exports. Define recognition with
  `maa.pipeline.JTemplateMatch`, `JOCR`, `JOr`, and `JAnd` directly. Studio generates only native
  recognition types, including inline nested combinations. AST import accepts current native
  definitions only. Examples, project scaffolding, and documentation use the same native API.
- Studio locators now support separate display names, and template fields provide a searchable
  multi-select image browser with thumbnails while preserving Python attribute names and resource paths.
- Added the independent `maaplus-studio` package for local visual UI authoring: ADB/Win32 screenshots,
  ROI and PNG cropping, native recognition validation, safe AST import, versioned project configuration,
  and deterministic Python generation with file conflict detection and rollback. The built web UI ships
  inside the Studio wheel; MaaPlus core does not gain web dependencies.
- Removed `maaplus.dev.create_adb_controller`, `find_adb_devices`, and `DiscoveredDevice`. Use
  `maa.controller.AdbController` and `maa.toolkit.Toolkit.find_adb_devices()` directly, matching
  native Win32 controller setup. Application code owns device selection and connection.
- Updated ADB examples, instance documentation, and device diagnostics to use native MaaFramework
  APIs. Example startup reports an undiscovered explicit address instead of using fallback methods.

## 1.4.0 — 2026-09-09

- Added offline `inspect` and read-only `doctor` CLI commands with fixture assertions.
- Added a runnable offline `maaplus init` scaffold and fixture inspection batch API.
- Added isolated trace sessions, run IDs, failure reports, traceback files, and evidence paths.
- Added task lifecycle status, execution summaries, resumable tasks, and recurring-failure pausing.
- Added explicit ndarray image formats and configurable navigation wait behavior.
- Improved ADB example selection and device capability diagnostics.
- Added `InstanceManager` for isolated per-device app instances with batch lifecycle controls.
- Instance lifecycle now exposes health and retained task-failure counts, closes owned trace/runtime
  resources, coordinates device leases across managers in one process, and handles worker self-stop
  and concurrent batch-stop requests without self-joins or manager-lock stalls.
- Global guards support cadence/cooldown controls and optional idle watching for popups that appear
  between tasks.

## 1.3.0 — 2026-09-09

- Added `maaplus.dev` inspection, fixture, JSONL trace, and MaaFramework controller adapters.
- Added `maaplus init` project scaffolding and the `maaplus[dev]` optional extra.
- Added task execution contexts, bounded retries, terminal failure inspection, and task timeouts.
- Added structured navigation states with step and timeout limits.
- Periodic triggers now replace an existing recurring trigger for the same task.

## 1.2.0 — 2026-09-09

- Added opt-in PNG bounding-box debugging through `Debug`, `Runtime`, and `Tick.draw()`.
- Automatic recognition snapshots expose `MatchResult.debug_path`, keep original coordinates, and
  retain only the newest configured number of images.
- Added the `maaplus[debug]` Pillow extra and a complete-project configuration example.

## 1.1.0 — 2026-09-09

- Expanded the complete project with an example-owned NumPy multi-point color recognizer,
  guide, and tests for RGB/BGR conversion, ROI, and tolerance overrides.
- The example registers callbacks through MaaFramework's `Resource` and uses its native
  `JCustomRecognition` parameters with the existing `Tick.match()` API.

## 1.0.0 — 2026-09-09

MaaPlus is ready for its first public release.

- Added a compact `App` facade for task registration, routing, and scheduling.
- Added cooperative priority scheduling with safe preemption, pause/resume, recurring triggers,
  and task cancellation through `TaskHandle.cancel()`.
- Added fixed-snapshot `Tick` handlers and synchronous MaaFramework recognition and input helpers.
- Added composable `FirstOf` and `AllOf` locators, configurable click/swipe behavior, and timing
  and geometry strategies.
- Updated the supported MaaFramework baseline to 5.13.0 and added standard build metadata.
