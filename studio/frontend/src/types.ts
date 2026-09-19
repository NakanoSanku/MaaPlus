export type Kind = 'TemplateMatch' | 'OCR' | 'FeatureMatch' | 'ColorMatch' | 'Custom' | 'And' | 'Or';
export type Rect = [number, number, number, number];
export interface Group { id: string; module: string; class_name: string; label: string }
export interface Locator { id: string; group_id: string; name: string; label?: string; kind: Kind; params: Record<string, any>; children: string[]; export: boolean }
export interface Project { version: 1; resource_dir: string; output_dir: string; resource_hook: string; groups: Group[]; locators: Locator[]; managed_files: Record<string, string> }
export interface Snapshot { id: string; width: number; height: number; source: { kind: string; name?: string; scale?: string; size?: number } }
export interface Inspection { hit: boolean; box: Rect | null; elapsed_ms: number; raw_detail: unknown; snapshot_id: string; locator_id: string }
export interface PageInspectionItem {
  locator: Locator;
  status: 'pending' | 'running' | 'hit' | 'miss' | 'error';
  result?: Inspection;
  error?: string;
  elapsed_ms?: number;
}
export interface PageInspection {
  group: Group;
  snapshot: Snapshot;
  status: 'running' | 'stopping' | 'completed' | 'stopped';
  items: PageInspectionItem[];
  elapsed_ms: number;
}
export interface Preview { preview_id: string; changes: { path: string; action: string; diff: string }[]; files: Record<string, string>; project: Project }
export function locatorTitle(item: Locator) { return item.label?.trim() || item.name; }
export function locatorCaption(item: Locator) { const title = locatorTitle(item); return title === item.name ? title : `${title} · ${item.name}`; }
export const labels: Record<Kind, string> = { TemplateMatch: '模板匹配', OCR: '文字识别', FeatureMatch: '特征匹配', ColorMatch: '颜色匹配', Custom: '自定义识别', And: '全部匹配 · And', Or: '任一匹配 · Or' };
export function defaults(kind: Kind): Record<string, any> {
  const roi = [0, 0, 0, 0];
  switch (kind) {
    case 'TemplateMatch': return { template: [], threshold: [0.85], roi };
    case 'OCR': return { expected: [], threshold: 0.3, roi };
    case 'FeatureMatch': return { template: [], count: 4, ratio: 0.6, detector: 'SIFT', roi };
    case 'ColorMatch': return { lower: [[0, 0, 0]], upper: [[255, 255, 255]], method: 4, count: 1, roi };
    case 'Custom': return { custom_recognition: '', custom_recognition_param: {}, roi };
    case 'And': return { box_index: 0 };
    case 'Or': return {};
  }
}
