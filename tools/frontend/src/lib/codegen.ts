import { LocatorConfig, UIClass } from '../types';

export type DiagnosticSeverity = 'error' | 'warning' | 'info';

export interface CodeDiagnostic {
  severity: DiagnosticSeverity;
  message: string;
  className?: string;
  locatorName?: string;
}

export interface RenderedCode {
  code: string;
  diagnostics: CodeDiagnostic[];
}

export type LocatorRenderer = (
  locator: LocatorConfig,
  className: string,
  diagnostics: CodeDiagnostic[]
) => string;

const locatorRenderers = new Map<string, LocatorRenderer>();

/** Register a code renderer without changing the Code Studio component. */
export function registerLocatorRenderer(type: string, renderer: LocatorRenderer): void {
  locatorRenderers.set(type, renderer);
}

function pythonString(value: string): string {
  return JSON.stringify(value).replace(/\\u2028|\\u2029/g, (match) =>
    match === '\\u2028' ? '\\u2028' : '\\u2029'
  );
}

function pythonLiteral(value: unknown): string {
  if (value === null || value === undefined) return 'None';
  if (typeof value === 'string') return pythonString(value);
  if (typeof value === 'boolean') return value ? 'True' : 'False';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'None';
  if (Array.isArray(value)) return `[${value.map(pythonLiteral).join(', ')}]`;
  if (typeof value === 'object') {
    const fields = Object.entries(value as Record<string, unknown>);
    return `{${fields.map(([key, item]) => `${pythonString(key)}: ${pythonLiteral(item)}`).join(', ')}}`;
  }
  return pythonString(String(value));
}

function pythonList(values: string[]): string {
  return `[${values.map(pythonString).join(', ')}]`;
}

function pythonRoi(roi: LocatorConfig['roi']): string | null {
  if (!roi) return null;
  return `(${roi.map((value) => Math.max(0, Math.round(Number(value) || 0))).join(', ')})`;
}

function safeIdentifier(value: string): boolean {
  return /^[A-Za-z_]\w*$/.test(value);
}

const WORKBENCH_FIELDS = new Set(['name', 'type', 'source', 'template', 'threshold', 'roi', 'expected']);

function appendPreservedKwargs(locator: LocatorConfig, args: string[]): void {
  for (const [key, value] of Object.entries(locator)) {
    if (WORKBENCH_FIELDS.has(key) || value === undefined) continue;
    if (!safeIdentifier(key)) continue;
    args.push(`${key}=${pythonLiteral(value)}`);
  }
}

registerLocatorRenderer('Template', (locator, className, diagnostics) => {
  const templates = Array.isArray(locator.template) ? locator.template.filter(Boolean) : [];
  if (templates.length === 0) {
    diagnostics.push({
      severity: 'warning',
      message: 'Template 尚未配置模板图片路径。',
      className,
      locatorName: locator.name,
    });
  }

  const args = [`template=${pythonList(templates.length ? templates : [`${locator.name}.png`])}`];
  const threshold = Number(locator.threshold ?? 0.85);
  args.push(`threshold=[${Number.isFinite(threshold) ? threshold : 0.85}]`);
  const roi = pythonRoi(locator.roi);
  if (roi) args.push(`roi=${roi}`);
  appendPreservedKwargs(locator, args);
  return `    ${locator.name} = Template(\n        ${args.join(',\n        ')},\n    )`;
});

registerLocatorRenderer('OCR', (locator, className, diagnostics) => {
  const expected = Array.isArray(locator.expected) ? locator.expected.filter(Boolean) : [];
  if (expected.length === 0) {
    diagnostics.push({
      severity: 'warning',
      message: 'OCR 尚未配置 expected 文本。',
      className,
      locatorName: locator.name,
    });
  }

  const args = [`expected=${pythonList(expected)}`];
  const roi = pythonRoi(locator.roi);
  if (roi) args.push(`roi=${roi}`);
  appendPreservedKwargs(locator, args);
  return `    ${locator.name} = OCR(\n        ${args.join(',\n        ')},\n    )`;
});

registerLocatorRenderer('JCustomRecognition', (locator, className, diagnostics) => {
  const customName = locator.custom_recognition;
  if (!customName) {
    diagnostics.push({
      severity: 'warning',
      message: 'JCustomRecognition 缺少 custom_recognition。',
      className,
      locatorName: locator.name,
    });
  }

  const args: string[] = [];
  for (const [key, value] of Object.entries(locator)) {
    if (['name', 'type', 'source', 'template', 'threshold', 'expected'].includes(key) || value === undefined) continue;
    if (key === 'roi') {
      const roi = pythonRoi(locator.roi);
      if (roi) args.push(`roi=${roi}`);
      continue;
    }
    if (!safeIdentifier(key)) continue;
    args.push(`${key}=${pythonLiteral(value)}`);
  }
  return `    ${locator.name} = JCustomRecognition(\n        ${args.join(',\n        ')},\n    )`;
});

function renderLocator(
  locator: LocatorConfig,
  className: string,
  diagnostics: CodeDiagnostic[]
): string {
  if (!safeIdentifier(locator.name)) {
    diagnostics.push({
      severity: 'error',
      message: `“${locator.name}” 不是合法的 Python 标识符。`,
      className,
      locatorName: locator.name,
    });
  }

  const renderer = locatorRenderers.get(locator.type);
  if (renderer) return renderer(locator, className, diagnostics);

  if (typeof locator.source === 'string' && locator.source.trim()) {
    diagnostics.push({
      severity: 'info',
      message: `${locator.type} 由项目源码原样保留；可在 Code Studio 中继续编辑。`,
      className,
      locatorName: locator.name,
    });
    return `    ${locator.name} = ${locator.source.trim()}`;
  }

  diagnostics.push({
    severity: 'warning',
    message: `${locator.type} 暂无结构化渲染器，已生成 TODO 占位；可通过 registerLocatorRenderer() 扩展。`,
    className,
    locatorName: locator.name,
  });
  return `    # TODO: configure ${locator.type}\n    ${locator.name} = None`;
}

export function renderMaaPlusUI(classes: UIClass[]): RenderedCode {
  const diagnostics: CodeDiagnostic[] = [];
  const usedTypes = new Set<string>();

  for (const cls of classes) {
    for (const locator of cls.locators) usedTypes.add(locator.type);
  }

  const maaplusImports = ['OCR', 'Template'].filter((name) => usedTypes.has(name));
  if (usedTypes.has('FirstOf')) maaplusImports.push('FirstOf');
  if (usedTypes.has('AllOf')) maaplusImports.push('AllOf');

  const lines: string[] = [
    '"""UI locators generated by MaaPlus UI Workbench.',
    '',
    'Review diagnostics in Code Studio before writing this file.',
    '"""',
    '',
  ];

  if (maaplusImports.length) {
    lines.push(`from maaplus import ${Array.from(new Set(maaplusImports)).sort().join(', ')}`);
  }
  if (usedTypes.has('JCustomRecognition')) {
    lines.push('from maa.pipeline import JCustomRecognition');
  }
  if (lines[lines.length - 1] !== '') lines.push('');

  for (const cls of classes) {
    if (!safeIdentifier(cls.name)) {
      diagnostics.push({
        severity: 'error',
        message: `类名“${cls.name}”不是合法的 Python 标识符。`,
        className: cls.name,
      });
    }

    lines.push(`class ${cls.name}:`);
    if (cls.locators.length === 0) {
      lines.push('    pass');
    } else {
      cls.locators.forEach((locator, index) => {
        if (index > 0) lines.push('');
        lines.push(renderLocator(locator, cls.name, diagnostics));
      });
    }
    lines.push('');
    lines.push('');
  }

  const code = `${lines.join('\n').trimEnd()}\n`;
  return { code, diagnostics };
}

export function suggestedUiPath(uiClass?: UIClass): string {
  if (uiClass?.sourceFile) return uiClass.sourceFile;
  if (!uiClass?.name) return 'ui/generated.py';
  const stem = uiClass.name
    .replace(/UI$/, '')
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[^A-Za-z0-9_]+/g, '_')
    .toLowerCase() || 'generated';
  return `ui/${stem}.py`;
}
