export type LocatorType = 'Template' | 'OCR' | 'FirstOf' | 'AllOf' | 'JCustomRecognition';

export interface LocatorConfig {
  name: string;
  type: LocatorType;
  template?: string[];
  threshold?: number;
  roi?: [number, number, number, number] | null;
  expected?: string[];
  /** Original Python expression for complex/read-only locators scanned from the project. */
  source?: string;
  /** Preserve future MaaFramework options without forcing the visual editor to know them. */
  [key: string]: unknown;
}

export interface BacktestExpectation {
  hit?: boolean;
  min_score?: number;
}

export interface BoundScreenshot {
  id: string;
  name: string;
  dataUrl?: string;
  path?: string;
  width?: number;
  height?: number;
  addedAt?: string;
  /** Per-locator assertions. Missing entries default to { hit: true }. */
  expectations?: Record<string, BacktestExpectation>;
}

export interface UIClass {
  name: string;
  locators: LocatorConfig[];
  screenshots?: BoundScreenshot[];
  /** Relative path returned by the project scanner. */
  sourceFile?: string;
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
  passed?: boolean;
  expected_hit?: boolean;
  min_score?: number | null;
  failure_reason?: string | null;
}

export interface ClassBacktestMatrixRow {
  screenshot_name: string;
  thumbnail?: string;
  passed: boolean;
  results: Record<string, ClassLocatorResult>;
}

export interface LocatorBacktestStat {
  locator_name: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  avg_elapsed_ms: number;
}

export interface ClassBacktestSummary {
  success: boolean;
  ui_class: string;
  total_screenshots: number;
  total_locators: number;
  total_checks: number;
  passed_checks: number;
  failed_checks?: number;
  pass_rate: number;
  duration_ms?: number;
  matrix: ClassBacktestMatrixRow[];
  locator_stats?: LocatorBacktestStat[];
  error?: string;
}
