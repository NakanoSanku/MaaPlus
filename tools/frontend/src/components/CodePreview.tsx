import * as React from 'react';
import {
  AlertTriangle,
  Check,
  CircleAlert,
  Code2,
  Copy,
  Download,
  FileCode2,
  FolderSync,
  Info,
  RotateCcw,
  Save,
  Upload,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { UIClass } from '../types';
import { renderMaaPlusUI, suggestedUiPath } from '../lib/codegen';
import { scanProjectUI } from '../lib/api';

interface CodePreviewProps {
  uiClasses: UIClass[];
  selectedClassIndex: number;
  onSaveUiFile: (filePath: string, code: string) => Promise<boolean>;
  onImportClasses: (classes: UIClass[]) => void;
}

type Scope = 'active' | 'all';

export function CodePreview({
  uiClasses,
  selectedClassIndex,
  onSaveUiFile,
  onImportClasses,
}: CodePreviewProps) {
  const [scope, setScope] = React.useState<Scope>('active');
  const [copied, setCopied] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [statusMsg, setStatusMsg] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState('');
  const [dirty, setDirty] = React.useState(false);
  const [sourceChanged, setSourceChanged] = React.useState(false);
  const [isScanning, setIsScanning] = React.useState(false);
  const importInputRef = React.useRef<HTMLInputElement>(null);

  const activeClass = uiClasses[selectedClassIndex];
  const classesToRender = React.useMemo(
    () => (scope === 'active' && activeClass ? [activeClass] : uiClasses),
    [scope, activeClass, uiClasses]
  );
  const rendered = React.useMemo(() => renderMaaPlusUI(classesToRender), [classesToRender]);
  const [filePath, setFilePath] = React.useState(() => suggestedUiPath(activeClass));

  React.useEffect(() => {
    if (!dirty) {
      setDraft(rendered.code);
      setSourceChanged(false);
    } else if (draft !== rendered.code) {
      setSourceChanged(true);
    }
  }, [rendered.code]);

  React.useEffect(() => {
    if (!dirty && scope === 'active') {
      setFilePath(suggestedUiPath(activeClass));
    }
  }, [activeClass?.name, activeClass?.sourceFile, scope, dirty]);

  const resetDraft = () => {
    setDraft(rendered.code);
    setDirty(false);
    setSourceChanged(false);
  };

  const handleScanProject = async () => {
    setIsScanning(true);
    try {
      const classes = await scanProjectUI();
      if (classes.length) {
        onImportClasses(classes);
        setDirty(false);
        setStatusMsg(`已从项目同步 ${classes.length} 个 UI 类`);
      } else {
        setStatusMsg('项目中没有扫描到 UI 类');
      }
    } catch (err: any) {
      setStatusMsg(`扫描失败：${err?.message || 'backend unavailable'}`);
    } finally {
      setIsScanning(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(draft);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const handleSaveToFile = async () => {
    if (!filePath.trim()) return;
    const hasBlockingError = rendered.diagnostics.some((item) => item.severity === 'error');
    if (hasBlockingError && !dirty) {
      setStatusMsg('存在阻塞诊断，请先修复标识符或直接编辑草稿。');
      return;
    }
    setIsSaving(true);
    const ok = await onSaveUiFile(filePath.trim(), draft);
    setIsSaving(false);
    if (ok) {
      setDirty(false);
      setSourceChanged(false);
      setStatusMsg(`已写入 ${filePath.trim()}`);
      setTimeout(() => setStatusMsg(null), 3500);
    }
  };

  const handleExportPython = () => {
    const blob = new Blob([draft], { type: 'text/x-python;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filePath.split('/').filter(Boolean).pop() || 'ui.py';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportJson = () => {
    const blob = new Blob([JSON.stringify(uiClasses, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'maaplus_ui_workspace.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (!Array.isArray(parsed)) throw new Error('root must be an array');
        onImportClasses(parsed);
        setDirty(false);
        setStatusMsg('工作区配置已导入');
      } catch {
        setStatusMsg('导入失败：JSON 结构无效');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <div className="flex-1 min-h-0 bg-[#0b0d12] text-slate-100 overflow-hidden">
      <div className="h-full grid grid-cols-[270px_minmax(0,1fr)_300px]">
        <aside className="border-r border-white/8 bg-[#10131a] p-4 overflow-y-auto">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">Code Studio</div>
              <h2 className="text-sm font-semibold text-slate-100">工程输出</h2>
              <p className="text-[11px] leading-5 text-slate-500 mt-1">生成可直接使用的 MaaPlus UI 定义，而不是独立 DSL。</p>
            </div>
            <FileCode2 className="w-5 h-5 text-violet-300" />
          </div>

          <div className="space-y-2 mb-5">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">生成范围</div>
            <button
              onClick={() => { setScope('active'); setDirty(false); }}
              className={`w-full text-left rounded-lg border px-3 py-2.5 transition-colors ${scope === 'active' ? 'border-violet-400/40 bg-violet-400/10' : 'border-white/8 bg-white/[0.02] hover:bg-white/[0.04]'}`}
            >
              <div className="text-xs font-medium text-slate-200">当前 UI 类</div>
              <div className="text-[11px] text-slate-500 mt-0.5 truncate">{activeClass?.name || '未选择'}</div>
            </button>
            <button
              onClick={() => { setScope('all'); setDirty(false); }}
              className={`w-full text-left rounded-lg border px-3 py-2.5 transition-colors ${scope === 'all' ? 'border-violet-400/40 bg-violet-400/10' : 'border-white/8 bg-white/[0.02] hover:bg-white/[0.04]'}`}
            >
              <div className="text-xs font-medium text-slate-200">全部 UI 类</div>
              <div className="text-[11px] text-slate-500 mt-0.5">{uiClasses.length} classes · {uiClasses.reduce((n, cls) => n + cls.locators.length, 0)} locators</div>
            </button>
          </div>

          <div className="space-y-2 mb-5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">项目状态</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleScanProject}
                disabled={isScanning}
                className="h-7 px-2 text-[11px] text-slate-400 hover:text-slate-100"
              >
                <FolderSync className={`w-3.5 h-3.5 mr-1 ${isScanning ? 'animate-spin' : ''}`} />
                {isScanning ? '扫描中' : '重新扫描'}
              </Button>
            </div>
            <div className="rounded-lg border border-white/8 bg-black/20 divide-y divide-white/6">
              {classesToRender.map((cls) => (
                <div key={cls.name} className="px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-slate-200 truncate">{cls.name}</span>
                    <span className="text-[10px] text-slate-500">{cls.locators.length}</span>
                  </div>
                  <div className="text-[10px] text-slate-600 mt-1 truncate">{cls.sourceFile || 'workspace only'}</div>
                </div>
              ))}
            </div>
          </div>

          <input ref={importInputRef} type="file" accept=".json" className="hidden" onChange={handleImportJson} />
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" onClick={handleExportJson} className="h-8 text-[11px] border-white/10 text-slate-400">
              <Download className="w-3.5 h-3.5 mr-1" />JSON
            </Button>
            <Button variant="outline" size="sm" onClick={() => importInputRef.current?.click()} className="h-8 text-[11px] border-white/10 text-slate-400">
              <Upload className="w-3.5 h-3.5 mr-1" />导入
            </Button>
          </div>
        </aside>

        <main className="min-w-0 flex flex-col bg-[#0b0d12]">
          <div className="h-14 shrink-0 px-4 border-b border-white/8 flex items-center gap-3 bg-[#0e1117]">
            <div className="flex-1 min-w-0 flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3">
              <Code2 className="w-3.5 h-3.5 text-slate-500" />
              <Input
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                className="h-8 border-0 bg-transparent px-0 font-mono text-xs focus-visible:ring-0"
                placeholder="ui/home.py"
              />
            </div>
            {sourceChanged && (
              <span className="hidden xl:inline-flex text-[11px] text-amber-300 bg-amber-400/10 border border-amber-400/20 rounded-md px-2 py-1">
                画布配置已变化，草稿未自动覆盖
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={resetDraft} className="h-8 text-xs text-slate-400" title="用当前工作区重新生成">
              <RotateCcw className="w-3.5 h-3.5 mr-1" />重置
            </Button>
            <Button variant="ghost" size="sm" onClick={handleCopy} className="h-8 text-xs text-slate-400">
              {copied ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
              {copied ? '已复制' : '复制'}
            </Button>
            <Button size="sm" onClick={handleSaveToFile} disabled={isSaving || !draft.trim()} className="h-8 px-3 text-xs bg-violet-500 hover:bg-violet-400 text-white">
              <Save className="w-3.5 h-3.5 mr-1.5" />{isSaving ? '写入中' : '写入工程'}
            </Button>
          </div>

          <div className="flex-1 min-h-0 relative">
            <textarea
              id="codePreviewBox"
              spellCheck={false}
              value={draft}
              onChange={(e) => { setDraft(e.target.value); setDirty(true); }}
              className="absolute inset-0 w-full h-full resize-none border-0 outline-none bg-[#090b10] text-[13px] leading-6 text-slate-200 font-mono p-5 selection:bg-violet-500/25"
              aria-label="Python UI code editor"
            />
          </div>

          <div className="h-9 shrink-0 border-t border-white/8 px-4 flex items-center justify-between bg-[#0e1117] text-[10px] text-slate-500">
            <span>Python · UTF-8 · MaaPlus {dirty ? '· 已编辑' : '· 与工作区同步'}</span>
            <div className="flex items-center gap-3">
              {statusMsg && <span className="text-emerald-300">{statusMsg}</span>}
              <button onClick={handleExportPython} className="hover:text-slate-200 transition-colors">下载 .py</button>
            </div>
          </div>
        </main>

        <aside className="border-l border-white/8 bg-[#10131a] p-4 overflow-y-auto">
          <div className="mb-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">Diagnostics</div>
            <h3 className="text-sm font-semibold text-slate-100">生成诊断</h3>
            <p className="text-[11px] text-slate-500 mt-1 leading-5">复杂定位符优先保留项目扫描到的原始表达式，避免生成器破坏手写能力。</p>
          </div>

          <div className="grid grid-cols-3 gap-2 mb-4">
            {(['error', 'warning', 'info'] as const).map((severity) => {
              const count = rendered.diagnostics.filter((item) => item.severity === severity).length;
              return (
                <div key={severity} className="rounded-lg border border-white/8 bg-black/20 px-2.5 py-2 text-center">
                  <div className="text-base font-semibold font-mono text-slate-200">{count}</div>
                  <div className="text-[9px] uppercase tracking-wider text-slate-600">{severity}</div>
                </div>
              );
            })}
          </div>

          {rendered.diagnostics.length === 0 ? (
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-3 text-[11px] text-emerald-300 flex gap-2">
              <Check className="w-4 h-4 shrink-0" />
              <span>当前生成模型没有发现结构问题，可以继续编辑或写入工程。</span>
            </div>
          ) : (
            <div className="space-y-2">
              {rendered.diagnostics.map((item, index) => {
                const Icon = item.severity === 'error' ? CircleAlert : item.severity === 'warning' ? AlertTriangle : Info;
                const tone = item.severity === 'error' ? 'text-rose-300 border-rose-400/20 bg-rose-400/5' : item.severity === 'warning' ? 'text-amber-300 border-amber-400/20 bg-amber-400/5' : 'text-sky-300 border-sky-400/20 bg-sky-400/5';
                return (
                  <div key={`${item.className}-${item.locatorName}-${index}`} className={`rounded-lg border p-3 ${tone}`}>
                    <div className="flex gap-2">
                      <Icon className="w-4 h-4 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="text-[11px] leading-5">{item.message}</div>
                        {(item.className || item.locatorName) && (
                          <div className="font-mono text-[10px] opacity-60 mt-1 truncate">{[item.className, item.locatorName].filter(Boolean).join(' · ')}</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-5 rounded-lg border border-white/8 bg-black/20 p-3 text-[10px] leading-5 text-slate-500">
            <div className="text-slate-300 font-medium mb-1">输出原则</div>
            <div>• 使用 <span className="font-mono text-slate-400">from maaplus import Template, OCR</span></div>
            <div>• 不自动生成业务 action / click 逻辑</div>
            <div>• 写入前保留人工编辑草稿</div>
            <div>• 项目扫描结果可回到工作区继续调参</div>
          </div>
        </aside>
      </div>
    </div>
  );
}
