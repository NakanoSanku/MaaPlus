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

export async function fetchStatus(): Promise<{
  maa_available: boolean;
  project_root: string;
  connected_device: any;
}> {
  const res = await fetch(`${API_BASE}/api/status`);
  if (!res.ok) throw new Error('Status request failed');
  return res.json();
}

export async function fetchDevices(): Promise<Device[]> {
  const res = await fetch(`${API_BASE}/api/devices`);
  if (!res.ok) throw new Error('Failed to scan devices');
  const data = await res.json();
  return data.devices || [];
}

export async function connectDevice(address: string, adb_path = 'adb'): Promise<{ success: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/api/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address, adb_path }),
  });
  return res.json();
}

export async function disconnectDevice(): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/disconnect`, { method: 'POST' });
  return res.json();
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
  return res.json();
}

export async function sendSwipe(x1: number, y1: number, x2: number, y2: number, duration = 500): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/input/swipe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ x1, y1, x2, y2, duration }),
  });
  return res.json();
}

export async function sendKey(keycode: number): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/input/key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keycode }),
  });
  return res.json();
}

export async function testRecognition(locator: LocatorConfig, imageBase64?: string): Promise<RecognitionResult> {
  const res = await fetch(`${API_BASE}/api/recognize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locator, image: imageBase64 }),
  });
  return res.json();
}

export async function saveTemplateImage(path: string, imageBase64: string): Promise<{ success: boolean; relative_path?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/api/save_template`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, image: imageBase64 }),
  });
  return res.json();
}

export async function runBacktest(locator: LocatorConfig, fixture_dir?: string): Promise<BacktestSummary> {
  const res = await fetch(`${API_BASE}/api/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locator, fixture_dir }),
  });
  return res.json();
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
  return res.json();
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
  return res.json();
}

export async function scanProjectUI(): Promise<UIClass[]> {
  const res = await fetch(`${API_BASE}/api/project_ui`);
  if (!res.ok) throw new Error('Failed to scan project UI');
  const data = await res.json();
  const classes: UIClass[] = [];
  if (data.ui_files) {
    for (const f of data.ui_files) {
      if (f.classes) {
        classes.push(...f.classes);
      }
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
  return res.json();
}
