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
  return readJson(res, 'Regression run failed');
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
