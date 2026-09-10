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

  const errorCount = rendered.diagnostics.filter((item) => item.severity === 'error').length;
  const warningCount = rendered.diagnostics.filter((item) => item.severity === 'warning').length;
  const infoCount = rendered.diagnostics.filter((item) => item.severity === 'info').length;

  return (
    <div className="flex-1 min-h-0 bg-[#f5f5f2] text-[#191918] overflow-hidden p-3">
      <div className="h-full grid grid-cols-[250px_minmax(0,1fr)_286px] gap-3">
        <aside className="ds-panel p-4 overflow-y-auto">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div>
              <div className="ds-eyebrow mb-1">Code Studio</div>
              <h2 className="text-sm font-semibold text-[#191918]">工程输出</h2>
              <p className="text-[11px] leading-5 text-[#7d7d76] mt-1">生成、检查并写回真实 MaaPlus UI 定义。</p>
            </div>
            <div className="w-8 h-8 rounded-lg bg-[#f2f2ef] border border-[#e6e6e2] flex items-center justify-center">
              <FileCode2 className="w-4 h-4 text-[#494945]" />
            </div>
          </div>

          <div className="mb-5">
            <div className="ds-eyebrow mb-2">生成范围</div>
            <div className="space-y-2">
              <button
                onClick={() => { setScope('active'); setDirty(false); setFilePath(suggestedUiPath(activeClass)); }}
                className={`w-full text-left rounded-lg border px-3 py-2.5 transition-all ${scope === 'active' ? 'border-[#cfcfca] bg-[#f4f4f1] shadow-[inset_2px_0_0_#1b1b1a]' : 'border-[#e8e8e4] bg-white hover:bg-[#fafaf8]'}`}
              >
                <div className="text-xs font-medium text-[#2a2a28]">当前 UI 类</div>
                <div className="text-[10px] text-[#8a8a83] mt-1 truncate">{activeClass?.name || '未选择'}</div>
              </button>
              <button
                onClick={() => { setScope('all'); setDirty(false); setFilePath('ui/workbench_generated.py'); }}
                className={`w-full text-left rounded-lg border px-3 py-2.5 transition-all ${scope === 'all' ? 'border-[#cfcfca] bg-[#f4f4f1] shadow-[inset_2px_0_0_#1b1b1a]' : 'border-[#e8e8e4] bg-white hover:bg-[#fafaf8]'}`}
              >
                <div className="text-xs font-medium text-[#2a2a28]">全部 UI 类</div>
                <div className="text-[10px] text-[#8a8a83] mt-1">{uiClasses.length} classes · {uiClasses.reduce((n, cls) => n + cls.locators.length, 0)} locators</div>
              </button>
            </div>
          </div>

          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="ds-eyebrow">项目源</span>
              <button
                onClick={handleScanProject}
                disabled={isScanning}
                className="inline-flex items-center gap-1 text-[10px] font-medium text-[#696963] hover:text-[#222220] disabled:opacity-50"
              >
                <FolderSync className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                {isScanning ? '扫描中' : '重新扫描'}
              </button>
            </div>
            <div className="rounded-lg border border-[#e8e8e4] bg-[#fafaf8] divide-y divide-[#ecece8]">
              {classesToRender.map((cls) => (
                <div key={cls.name} className="px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[11px] font-medium text-[#31312e] truncate">{cls.name}</span>
                    <span className="rounded bg-white border border-[#e5e5e1] px-1.5 py-0.5 text-[9px] text-[#86867f]">{cls.locators.length}</span>
                  </div>
                  <div className="text-[9px] text-[#9b9b94] mt-1 truncate">{cls.sourceFile || 'workspace only'}</div>
                </div>
              ))}
            </div>
          </div>

          <input ref={importInputRef} type="file" accept=".json" className="hidden" onChange={handleImportJson} />
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" onClick={handleExportJson} className="h-8 text-[10px]">
              <Download className="w-3.5 h-3.5" />Workspace
            </Button>
            <Button variant="outline" size="sm" onClick={() => importInputRef.current?.click()} className="h-8 text-[10px]">
              <Upload className="w-3.5 h-3.5" />导入
            </Button>
          </div>
        </aside>

        <main className="ds-panel min-w-0 flex flex-col overflow-hidden">
          <div className="h-14 shrink-0 px-3 border-b border-[#ecece8] flex items-center gap-2 bg-white">
            <div className="flex-1 min-w-0 flex items-center gap-2 rounded-lg border border-[#e3e3df] bg-[#fafaf8] px-3">
              <Code2 className="w-3.5 h-3.5 text-[#96968f]" />
              <Input
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                className="h-8 border-0 bg-transparent px-0 font-mono text-[11px] shadow-none focus-visible:ring-0"
                placeholder="ui/home.py"
              />
            </div>
            {sourceChanged && (
              <span className="hidden 2xl:inline-flex text-[9px] ds-status-warning rounded-md px-2 py-1">工作区已变化</span>
            )}
            <Button variant="ghost" size="sm" onClick={resetDraft} className="h-8 text-[10px]">
              <RotateCcw className="w-3.5 h-3.5" />重置
            </Button>
            <Button variant="outline" size="sm" onClick={handleCopy} className="h-8 text-[10px]">
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? '已复制' : '复制'}
            </Button>
            <Button size="sm" onClick={handleSaveToFile} disabled={isSaving || !draft.trim()} className="h-8 px-3 text-[10px]">
              <Save className="w-3.5 h-3.5" />{isSaving ? '写入中' : '写入工程'}
            </Button>
          </div>

          <div className="flex-1 min-h-0 relative bg-[#fbfbf9]">
            <textarea
              id="codePreviewBox"
              spellCheck={false}
              value={draft}
              onChange={(e) => { setDraft(e.target.value); setDirty(true); }}
              className="absolute inset-0 w-full h-full resize-none border-0 outline-none bg-[#fbfbf9] text-[12px] leading-6 text-[#2f2f2c] font-mono p-5 selection:bg-black/10"
              aria-label="Python UI code editor"
            />
          </div>

          <div className="h-9 shrink-0 border-t border-[#ecece8] px-4 flex items-center justify-between bg-white text-[9px] text-[#8d8d86]">
            <span>Python · UTF-8 · MaaPlus {dirty ? '· 已编辑' : '· 与工作区同步'}</span>
            <div className="flex items-center gap-3">
              {statusMsg && <span className="text-emerald-300">{statusMsg}</span>}
              <button onClick={handleExportPython} className="font-medium text-[#666660] hover:text-[#1f1f1d] transition-colors">下载 .py</button>
            </div>
          </div>
        </main>

        <aside className="ds-panel p-4 overflow-y-auto">
          <div className="mb-4">
            <div className="ds-eyebrow mb-1">Diagnostics</div>
            <h3 className="text-sm font-semibold text-[#191918]">生成诊断</h3>
            <p className="text-[11px] text-[#7d7d76] mt-1 leading-5">写入前检查生成模型，复杂表达式优先保留项目源码。</p>
          </div>

          <div className="grid grid-cols-3 gap-2 mb-4">
            {[
              ['Error', errorCount],
              ['Warning', warningCount],
              ['Info', infoCount],
            ].map(([label, count]) => (
              <div key={String(label)} className="ds-subtle px-2 py-2 text-center">
                <div className="text-base font-semibold font-mono text-[#2a2a28]">{count}</div>
                <div className="text-[8px] uppercase tracking-wider text-[#999991]">{label}</div>
              </div>
            ))}
          </div>

          {rendered.diagnostics.length === 0 ? (
            <div className="rounded-lg ds-status-success p-3 text-[10px] flex gap-2 leading-5">
              <Check className="w-4 h-4 shrink-0 mt-0.5" />
              <span>当前生成模型没有发现结构问题，可以继续编辑或写入工程。</span>
            </div>
          ) : (
            <div className="space-y-2">
              {rendered.diagnostics.map((item, index) => {
                const Icon = item.severity === 'error' ? CircleAlert : item.severity === 'warning' ? AlertTriangle : Info;
                const tone = item.severity === 'error'
                  ? 'ds-status-danger'
                  : item.severity === 'warning'
                  ? 'ds-status-warning'
                  : 'border-[#e5e5e1] bg-[#f7f7f5] text-[#686862]';
                return (
                  <div key={`${item.message}-${index}`} className={`rounded-lg border p-3 text-[10px] leading-5 ${tone}`}>
                    <div className="flex items-start gap-2">
                      <Icon className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div>{item.message}</div>
                        {(item.className || item.locatorName) && (
                          <div className="mt-1 font-mono text-[9px] opacity-70 truncate">
                            {[item.className, item.locatorName].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-5 pt-4 border-t border-[#ecece8]">
            <div className="ds-eyebrow mb-2">输出约束</div>
            <div className="space-y-2 text-[10px] leading-5 text-[#7d7d76]">
              <p>• 只生成 UI locator 定义，不生成业务 click/action。</p>
              <p>• Template / OCR 使用当前 MaaPlus 公共 API。</p>
              <p>• 无法安全还原的高级 locator 会给出诊断，而不是伪造代码。</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
