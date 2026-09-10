export type LocatorType = 'Template' | 'OCR' | 'FirstOf' | 'AllOf';

export interface LocatorConfig {
  name: string;
  type: LocatorType;
  template?: string[];
  threshold?: number;
  roi?: [number, number, number, number] | null;
  expected?: string[];
}

export interface BoundScreenshot {
  id: string;
  name: string;
  dataUrl?: string;
  path?: string;
  width?: number;
  height?: number;
  addedAt?: string;
}

export interface UIClass {
  name: string;
  locators: LocatorConfig[];
  screenshots?: BoundScreenshot[];
}

export interface Device {
  address: string;
  name: string;
  source: string;
  connected?: boolean;
}

export interface RecognitionResult {
  success: boolean;
  hit?: boolean;
  box?: [number, number, number, number] | null;
  score?: number | null;
  elapsed_ms?: number;
  error?: string;
}

export interface BacktestItem {
  filename: string;
  thumbnail: string;
  hit: boolean;
  box: [number, number, number, number] | null;
  score: number | null;
  elapsed_ms: number;
  passed: boolean;
  fail_reasons: string[];
  expected: Record<string, any>;
}

export interface BacktestSummary {
  success: boolean;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  results: BacktestItem[];
}

export interface ClassLocatorResult {
  hit: boolean;
  score: number | null;
  box: [number, number, number, number] | null;
  elapsed_ms: number;
  error?: string;
}

export interface ClassBacktestMatrixRow {
  screenshot_name: string;
  thumbnail?: string;
  passed: boolean;
  results: Record<string, ClassLocatorResult>;
}

export interface ClassBacktestSummary {
  success: boolean;
  ui_class: string;
  total_screenshots: number;
  total_locators: number;
  total_checks: number;
  passed_checks: number;
  pass_rate: number;
  matrix: ClassBacktestMatrixRow[];
  error?: string;
}
