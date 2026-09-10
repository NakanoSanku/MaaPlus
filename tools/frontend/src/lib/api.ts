import {
  BacktestSummary,
  BoundScreenshot,
  ClassBacktestSummary,
  Device,
  LocatorConfig,
  RecognitionResult,
  UIClass,
} from '../types';

export const API_BASE = window.location.origin.startsWith('http')
  ? window.location.origin
  : 'http://127.0.0.1:8080';

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  let payload: any = null;
  try {
    payload = await response.json();
  } catch {
    // handled below
  }
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.error || fallbackMessage);
  }
  return payload as T;
}

export async function fetchStatus(): Promise<{
  maa_available: boolean;
  project_root: string;
  connected_device: any;
}> {
  const res = await fetch(`${API_BASE}/api/status`);
  return readJson(res, 'Status request failed');
}

export async function fetchDevices(): Promise<Device[]> {
  const res = await fetch(`${API_BASE}/api/devices`);
  const data = await readJson<{ devices?: Device[] }>(res, 'Failed to scan devices');
  return data.devices || [];
}

export async function connectDevice(address: string, adb_path = 'adb'): Promise<{ success: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/api/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address, adb_path }),
  });
  return readJson(res, 'Failed to connect device');
}

export async function disconnectDevice(): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/disconnect`, { method: 'POST' });
  return readJson(res, 'Failed to disconnect device');
}

export async function captureScreenshot(): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/screencap?_t=${Date.now()}`);
  if (!res.ok) throw new Error('Screencap failed');
  return res.blob();
}

export async function sendTap(x: number, y: number): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/input/tap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ x, y }),
  });
  return readJson(res, 'Tap failed');
}

export async function sendSwipe(x1: number, y1: number, x2: number, y2: number, duration = 500): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/input/swipe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ x1, y1, x2, y2, duration }),
  });
  return readJson(res, 'Swipe failed');
}

export async function sendKey(keycode: number): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/input/key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keycode }),
  });
  return readJson(res, 'Key input failed');
}

export async function testRecognition(locator: LocatorConfig, imageBase64?: string): Promise<RecognitionResult> {
  const res = await fetch(`${API_BASE}/api/recognize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locator, image: imageBase64 }),
  });
  return readJson(res, 'Recognition request failed');
}

export async function saveTemplateImage(path: string, imageBase64: string): Promise<{ success: boolean; relative_path?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/api/save_template`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, image: imageBase64 }),
  });
  return readJson(res, 'Failed to save template');
}

export async function runBacktest(locator: LocatorConfig, fixture_dir?: string): Promise<BacktestSummary> {
  const res = await fetch(`${API_BASE}/api/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locator, fixture_dir }),
  });
  return readJson(res, 'Backtest failed');
}

function enrichRegressionSummary(
  summary: ClassBacktestSummary,
  params: { locators: LocatorConfig[]; screenshots: BoundScreenshot[] }
): ClassBacktestSummary {
  if (!summary.success || !summary.matrix) return summary;

  const screenshotMap = new Map(params.screenshots.map((shot) => [shot.name, shot]));
  const stats = new Map<string, { total: number; passed: number; failed: number; elapsed: number }>();
  let totalChecks = 0;
  let passedChecks = 0;
  let durationMs = 0;

  const matrix = summary.matrix.map((row) => {
    const expectations = screenshotMap.get(row.screenshot_name)?.expectations || {};
    const results = Object.fromEntries(
      Object.entries(row.results).map(([name, result]) => {
        const expectation = expectations[name] || {};
        const expectedHit = expectation.hit ?? true;
        const minScore = expectation.min_score;
        const hitMatches = Boolean(result.hit) === expectedHit;
        const scoreMatches = !expectedHit || minScore == null || (result.score ?? 0) >= minScore;
        const passed = !result.error && hitMatches && scoreMatches;
        const elapsed = Number(result.elapsed_ms || 0);

        totalChecks += 1;
        durationMs += elapsed;
        if (passed) passedChecks += 1;

        const stat = stats.get(name) || { total: 0, passed: 0, failed: 0, elapsed: 0 };
        stat.total += 1;
        stat.elapsed += elapsed;
        if (passed) stat.passed += 1;
        else stat.failed += 1;
        stats.set(name, stat);

        let failureReason: string | null = null;
        if (result.error) failureReason = result.error;
        else if (!hitMatches) failureReason = `expected ${expectedHit ? 'HIT' : 'MISS'}, got ${result.hit ? 'HIT' : 'MISS'}`;
        else if (!scoreMatches) failureReason = `score ${(result.score ?? 0).toFixed(3)} < ${Number(minScore).toFixed(3)}`;

        return [name, {
          ...result,
          passed,
          expected_hit: expectedHit,
          min_score: minScore ?? null,
          failure_reason: failureReason,
        }];
      })
    );

    return {
      ...row,
      results,
      passed: Object.values(results).every((result) => result.passed),
    };
  });

  const locatorStats = params.locators.map((locator) => {
    const stat = stats.get(locator.name) || { total: 0, passed: 0, failed: 0, elapsed: 0 };
    return {
      locator_name: locator.name,
      total: stat.total,
      passed: stat.passed,
      failed: stat.failed,
      pass_rate: stat.total ? Math.round((stat.passed / stat.total) * 1000) / 10 : 0,
      avg_elapsed_ms: stat.total ? Math.round((stat.elapsed / stat.total) * 100) / 100 : 0,
    };
  });

  return {
    ...summary,
    total_screenshots: matrix.length,
    total_locators: params.locators.length,
    total_checks: totalChecks,
    passed_checks: passedChecks,
    failed_checks: Math.max(0, totalChecks - passedChecks),
    pass_rate: totalChecks ? Math.round((passedChecks / totalChecks) * 1000) / 10 : 0,
    duration_ms: Math.round(durationMs * 100) / 100,
    locator_stats: locatorStats,
    matrix,
  };
}

export async function runClassBacktest(params: {
  ui_class: string;
  locators: LocatorConfig[];
  screenshots: BoundScreenshot[];
  fixture_dir?: string;
}): Promise<ClassBacktestSummary> {
  const res = await fetch(`${API_BASE}/api/class_backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const summary = await readJson<ClassBacktestSummary>(res, 'Regression run failed');
  return enrichRegressionSummary(summary, params);
}

export async function saveBoundScreenshot(
  ui_class: string,
  name: string,
  imageBase64: string
): Promise<{ success: boolean; id?: string; name?: string; path?: string; dataUrl?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/api/save_bound_screenshot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ui_class, name, image: imageBase64 }),
  });
  return readJson(res, 'Failed to save fixture');
}

function normalizeLocator(raw: any): LocatorConfig {
  const threshold = Array.isArray(raw?.threshold) ? raw.threshold[0] : raw?.threshold;
  return {
    ...raw,
    threshold: threshold === undefined ? undefined : Number(threshold),
    roi: Array.isArray(raw?.roi) && raw.roi.length === 4 ? raw.roi.map(Number) : raw?.roi ?? null,
  } as LocatorConfig;
}

export async function scanProjectUI(): Promise<UIClass[]> {
  const res = await fetch(`${API_BASE}/api/project_ui`);
  const data = await readJson<{ ui_files?: Array<{ rel_path?: string; classes?: any[] }> }>(res, 'Failed to scan project UI');
  const classes: UIClass[] = [];
  for (const file of data.ui_files || []) {
    for (const cls of file.classes || []) {
      classes.push({
        ...cls,
        sourceFile: file.rel_path,
        locators: (cls.locators || []).map(normalizeLocator),
      });
    }
  }
  return classes;
}

export async function saveUIFile(file_path: string, code: string): Promise<{ success: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/api/save_ui`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path, code }),
  });
  return readJson(res, 'Failed to write UI file');
}
