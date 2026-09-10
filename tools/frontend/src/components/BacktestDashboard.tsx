import * as React from 'react';
import {
  AlertTriangle,
  BarChart3,
  Camera,
  Check,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  Filter,
  FlaskConical,
  History,
  Play,
  RefreshCcw,
  Upload,
  X,
} from 'lucide-react';
import { Button } from './ui/button';
import { BoundScreenshot, ClassBacktestMatrixRow, ClassBacktestSummary, UIClass } from '../types';

interface BacktestDashboardProps {
  uiClasses: UIClass[];
  selectedClassIndex: number;
  onSelectClassIndex: (index: number) => void;
  onRunClassBacktest: (uiClass: UIClass) => Promise<ClassBacktestSummary>;
  onInspectScreenshotOnCanvas: (screenshot: BoundScreenshot, rowResult?: ClassBacktestMatrixRow) => void;
  onBindCurrentScreenshot: (classIndex: number) => void;
  onUploadScreenshot: (classIndex: number, file: File) => void;
}

type ResultFilter = 'all' | 'failed' | 'passed';

type RunHistoryItem = {
  id: string;
  at: string;
  passRate: number;
  totalChecks: number;
  failedChecks: number;
  durationMs: number;
};

function historyKey(className?: string) {
  return `maaplus_backtest_history_v2_${className || 'unknown'}`;
}

function loadHistory(className?: string): RunHistoryItem[] {
  try {
    return JSON.parse(localStorage.getItem(historyKey(className)) || '[]');
  } catch {
    return [];
  }
}

export function BacktestDashboard({
  uiClasses,
  selectedClassIndex,
  onSelectClassIndex,
  onRunClassBacktest,
  onInspectScreenshotOnCanvas,
  onBindCurrentScreenshot,
  onUploadScreenshot,
}: BacktestDashboardProps) {
  const activeClass = uiClasses[selectedClassIndex] || uiClasses[0];
  const screenshots = activeClass?.screenshots || [];
  const locators = activeClass?.locators || [];
  const [selectedScreenshots, setSelectedScreenshots] = React.useState<Set<string>>(new Set());
  const [selectedLocators, setSelectedLocators] = React.useState<Set<string>>(new Set());
  const [isRunning, setIsRunning] = React.useState(false);
  const [summary, setSummary] = React.useState<ClassBacktestSummary | null>(null);
  const [filterMode, setFilterMode] = React.useState<ResultFilter>('failed');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [history, setHistory] = React.useState<RunHistoryItem[]>([]);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    setSelectedScreenshots(new Set(screenshots.map((shot) => shot.name)));
    setSelectedLocators(new Set(locators.map((locator) => locator.name)));
    setSummary(null);
    setErrorMessage(null);
    setFilterMode('failed');
    setHistory(loadHistory(activeClass?.name));
  }, [selectedClassIndex, activeClass?.name]);

  React.useEffect(() => {
    setSelectedScreenshots((current) => {
      const allowed = new Set(screenshots.map((shot) => shot.name));
      const next = new Set([...current].filter((name) => allowed.has(name)));
      if (next.size === 0 && screenshots.length) screenshots.forEach((shot) => next.add(shot.name));
      return next;
    });
    setSelectedLocators((current) => {
      const allowed = new Set(locators.map((locator) => locator.name));
      const next = new Set([...current].filter((name) => allowed.has(name)));
      if (next.size === 0 && locators.length) locators.forEach((locator) => next.add(locator.name));
      return next;
    });
  }, [screenshots.length, locators.length]);

  const pushHistory = (result: ClassBacktestSummary) => {
    const item: RunHistoryItem = {
      id: `${Date.now()}`,
      at: new Date().toISOString(),
      passRate: result.pass_rate,
      totalChecks: result.total_checks,
      failedChecks: result.failed_checks ?? Math.max(0, result.total_checks - result.passed_checks),
      durationMs: result.duration_ms ?? 0,
    };
    const next = [item, ...loadHistory(activeClass?.name)].slice(0, 8);
    localStorage.setItem(historyKey(activeClass?.name), JSON.stringify(next));
    setHistory(next);
  };

  const runSuite = async (shotNames: Set<string>, locatorNames: Set<string>) => {
    if (!activeClass || shotNames.size === 0 || locatorNames.size === 0) return;
    const suite: UIClass = {
      ...activeClass,
      screenshots: screenshots.filter((shot) => shotNames.has(shot.name)),
      locators: locators.filter((locator) => locatorNames.has(locator.name)),
    };
    setIsRunning(true);
    setErrorMessage(null);
    try {
      const result = await onRunClassBacktest(suite);
      if (!result.success) {
        setErrorMessage(result.error || '回归运行失败');
        return;
      }
      setSummary(result);
      setFilterMode((result.failed_checks ?? result.total_checks - result.passed_checks) > 0 ? 'failed' : 'all');
      pushHistory(result);
    } catch (err: any) {
      setErrorMessage(err?.message || '回归运行失败');
    } finally {
      setIsRunning(false);
    }
  };

  const handleStartBacktest = () => runSuite(selectedScreenshots, selectedLocators);

  const handleRerunFailures = () => {
    if (!summary) return;
    const failedShots = new Set<string>();
    const failedLocators = new Set<string>();
    summary.matrix.forEach((row) => {
      Object.entries(row.results).forEach(([name, result]) => {
        const passed = result.passed ?? result.hit;
        if (!passed) {
          failedShots.add(row.screenshot_name);
          failedLocators.add(name);
        }
      });
    });
    if (failedShots.size === 0 || failedLocators.size === 0) return;
    setSelectedScreenshots(failedShots);
    setSelectedLocators(failedLocators);
    runSuite(failedShots, failedLocators);
  };

  const toggleName = (setter: React.Dispatch<React.SetStateAction<Set<string>>>, name: string) => {
    setter((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const filteredRows = React.useMemo(() => {
    if (!summary) return [];
    if (filterMode === 'failed') return summary.matrix.filter((row) => !row.passed);
    if (filterMode === 'passed') return summary.matrix.filter((row) => row.passed);
    return summary.matrix;
  }, [summary, filterMode]);

  const failedChecks = summary ? summary.failed_checks ?? Math.max(0, summary.total_checks - summary.passed_checks) : 0;
  const previousRun = history[1];
  const passRateDelta = summary && previousRun ? summary.pass_rate - previousRun.passRate : null;

  const exportResult = () => {
    if (!summary) return;
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${summary.ui_class}-regression-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const metricCards = summary ? [
    { label: 'Pass Rate', value: `${summary.pass_rate.toFixed(1)}%`, meta: passRateDelta === null ? '首次运行' : `${passRateDelta >= 0 ? '+' : ''}${passRateDelta.toFixed(1)}% vs previous`, good: summary.pass_rate >= 95 },
    { label: 'Passed', value: `${summary.passed_checks}/${summary.total_checks}`, meta: `${summary.total_screenshots} samples · ${summary.total_locators} locators`, good: failedChecks === 0 },
    { label: 'Failed', value: `${failedChecks}`, meta: failedChecks === 0 ? 'No regression detected' : '需要优先复盘', good: failedChecks === 0 },
    { label: 'Duration', value: `${Math.round(summary.duration_ms ?? 0)} ms`, meta: 'Whole regression run', good: true },
  ] : [];

  return (
    <div className="flex-1 min-h-0 bg-[#f5f5f2] text-[#191918] overflow-hidden p-3">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onUploadScreenshot(selectedClassIndex, file);
          event.target.value = '';
        }}
      />

      <div className="h-full grid grid-cols-[264px_minmax(0,1fr)] gap-3">
        <aside className="ds-panel p-4 overflow-y-auto">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div>
              <div className="ds-eyebrow mb-1">Regression Lab</div>
              <h2 className="text-sm font-semibold text-[#191918]">回归套件</h2>
              <p className="text-[11px] leading-5 text-[#7d7d76] mt-1">定义本次范围，再运行、复盘失败并重复验证。</p>
            </div>
            <div className="w-8 h-8 rounded-lg bg-[#f2f2ef] border border-[#e6e6e2] flex items-center justify-center">
              <FlaskConical className="w-4 h-4 text-[#494945]" />
            </div>
          </div>

          <label className="ds-eyebrow block mb-2">UI Class</label>
          <select
            value={selectedClassIndex}
            onChange={(e) => onSelectClassIndex(Number(e.target.value))}
            className="w-full h-9 rounded-lg border border-[#e1e1dd] bg-white px-3 text-[11px] text-[#343431] outline-none mb-5 shadow-[0_1px_2px_rgba(20,20,18,0.02)]"
          >
            {uiClasses.map((cls, index) => (
              <option key={`${cls.name}-${index}`} value={index}>{cls.name}</option>
            ))}
          </select>

          <section className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="ds-eyebrow">Samples {selectedScreenshots.size}/{screenshots.length}</span>
              <div className="flex items-center gap-2 text-[9px]">
                <button onClick={() => setSelectedScreenshots(new Set(screenshots.map((s) => s.name)))} className="text-[#77776f] hover:text-[#222220]">全选</button>
                <button onClick={() => setSelectedScreenshots(new Set())} className="text-[#a0a099] hover:text-[#444440]">清空</button>
              </div>
            </div>
            <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
              {screenshots.length === 0 ? (
                <div className="rounded-lg border border-dashed border-[#dfdfdb] bg-[#fafaf8] p-3 text-[10px] leading-5 text-[#92928b]">暂无样本。先从画布绑定或上传截图。</div>
              ) : screenshots.map((shot) => {
                const selected = selectedScreenshots.has(shot.name);
                return (
                  <button
                    key={shot.name}
                    onClick={() => toggleName(setSelectedScreenshots, shot.name)}
                    className={`w-full flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${selected ? 'border-[#d7d7d2] bg-[#f5f5f2]' : 'border-[#ecece8] bg-white opacity-65'}`}
                  >
                    <span className={`w-4 h-4 rounded border flex items-center justify-center ${selected ? 'border-[#2a2a28] bg-[#2a2a28] text-white' : 'border-[#cecec8] bg-white'}`}>
                      {selected && <Check className="w-3 h-3" />}
                    </span>
                    <span className="truncate font-mono text-[10px] text-[#4b4b46] flex-1">{shot.name}</span>
                    <Camera className="w-3 h-3 text-[#a0a099]" />
                  </button>
                );
              })}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <Button variant="outline" size="sm" onClick={() => onBindCurrentScreenshot(selectedClassIndex)} className="h-7 text-[9px]">
                <Camera className="w-3 h-3" />绑定画面
              </Button>
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="h-7 text-[9px]">
                <Upload className="w-3 h-3" />上传
              </Button>
            </div>
          </section>

          <section className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="ds-eyebrow">Locators {selectedLocators.size}/{locators.length}</span>
              <div className="flex items-center gap-2 text-[9px]">
                <button onClick={() => setSelectedLocators(new Set(locators.map((l) => l.name)))} className="text-[#77776f] hover:text-[#222220]">全选</button>
                <button onClick={() => setSelectedLocators(new Set())} className="text-[#a0a099] hover:text-[#444440]">清空</button>
              </div>
            </div>
            <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
              {locators.map((locator) => {
                const selected = selectedLocators.has(locator.name);
                return (
                  <button
                    key={locator.name}
                    onClick={() => toggleName(setSelectedLocators, locator.name)}
                    className={`w-full flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${selected ? 'border-[#d7d7d2] bg-[#f5f5f2]' : 'border-[#ecece8] bg-white opacity-65'}`}
                  >
                    <span className={`w-4 h-4 rounded border flex items-center justify-center ${selected ? 'border-[#2a2a28] bg-[#2a2a28] text-white' : 'border-[#cecec8] bg-white'}`}>
                      {selected && <Check className="w-3 h-3" />}
                    </span>
                    <span className="truncate font-mono text-[10px] text-[#4b4b46] flex-1">{locator.name}</span>
                    <span className="text-[8px] uppercase text-[#9b9b94]">{locator.type}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <Button
            id="btnRunBacktest"
            onClick={handleStartBacktest}
            disabled={isRunning || selectedScreenshots.size === 0 || selectedLocators.size === 0}
            className="w-full h-9 text-[10px]"
          >
            <Play className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
            {isRunning ? '运行中…' : `运行 ${selectedScreenshots.size * selectedLocators.size} checks`}
          </Button>

          {errorMessage && (
            <div className="mt-3 rounded-lg ds-status-danger p-3 text-[10px] leading-5 flex gap-2">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}
        </aside>

        <main className="min-w-0 flex flex-col overflow-y-auto pr-0.5">
          <div className="ds-panel p-4 flex items-center justify-between gap-4 mb-3">
            <div>
              <div className="ds-eyebrow mb-1">Regression Dashboard</div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-[#191918]">{activeClass?.name || 'UI Class'}</h2>
                <span className="rounded-md border border-[#e6e6e2] bg-[#f7f7f5] px-2 py-0.5 text-[9px] text-[#7d7d76]">{screenshots.length} samples</span>
                <span className="rounded-md border border-[#e6e6e2] bg-[#f7f7f5] px-2 py-0.5 text-[9px] text-[#7d7d76]">{locators.length} locators</span>
              </div>
              <p className="text-[10px] text-[#8d8d86] mt-1">失败优先复盘；调参后可只重跑失败集合。</p>
            </div>
            <div className="flex items-center gap-2">
              {summary && failedChecks > 0 && (
                <Button variant="outline" size="sm" onClick={handleRerunFailures} disabled={isRunning} className="h-8 text-[10px]">
                  <RefreshCcw className="w-3.5 h-3.5" />重跑失败项
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={exportResult} disabled={!summary} className="h-8 text-[10px]">
                <Download className="w-3.5 h-3.5" />导出结果
              </Button>
            </div>
          </div>

          {summary ? (
            <>
              <div className="grid grid-cols-4 gap-3 mb-3">
                {metricCards.map((metric) => (
                  <div key={metric.label} className="ds-card p-3.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] font-medium text-[#85857e]">{metric.label}</span>
                      <span className={`w-1.5 h-1.5 rounded-full ${metric.good ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                    </div>
                    <div className="mt-1.5 text-xl font-semibold tracking-tight text-[#222220]">{metric.value}</div>
                    <div className={`mt-1 text-[9px] ${metric.good ? 'text-emerald-300' : 'text-amber-300'}`}>{metric.meta}</div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-[minmax(0,1fr)_240px] gap-3 mb-3">
                <section className="ds-panel overflow-hidden min-w-0">
                  <div className="h-12 px-3 border-b border-[#ecece8] flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Filter className="w-3.5 h-3.5 text-[#8b8b84]" />
                      <span className="text-[11px] font-semibold text-[#343431]">Run Results</span>
                      <span className="text-[9px] text-[#999991]">{filteredRows.length}/{summary.matrix.length}</span>
                    </div>
                    <div className="flex items-center rounded-lg border border-[#e6e6e2] bg-[#f7f7f5] p-0.5">
                      {(['failed', 'all', 'passed'] as ResultFilter[]).map((mode) => (
                        <button
                          key={mode}
                          onClick={() => setFilterMode(mode)}
                          className={`h-6 rounded-md px-2 text-[9px] font-medium transition-all ${filterMode === mode ? 'bg-white border border-[#dfdfdb] text-[#2d2d2a] shadow-[0_1px_1px_rgba(0,0,0,0.04)]' : 'border border-transparent text-[#8d8d86]'}`}
                        >
                          {mode === 'failed' ? `Failed ${failedChecks}` : mode === 'passed' ? 'Passed' : 'All'}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="overflow-auto max-h-[430px]">
                    <table className="w-full border-collapse text-left">
                      <thead className="sticky top-0 z-10 bg-[#fafaf8]">
                        <tr className="border-b border-[#ecece8] text-[8px] uppercase tracking-wider text-[#92928b]">
                          <th className="px-3 py-2 font-semibold">Sample</th>
                          <th className="px-3 py-2 font-semibold">Status</th>
                          <th className="px-3 py-2 font-semibold">Failed locators</th>
                          <th className="px-3 py-2 font-semibold">Time</th>
                          <th className="px-3 py-2 font-semibold text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#efefeb]">
                        {filteredRows.map((row) => {
                          const failedNames = Object.entries(row.results)
                            .filter(([, result]) => !(result.passed ?? result.hit))
                            .map(([name]) => name);
                          const totalTime = Object.values(row.results).reduce((sum, result) => sum + (result.elapsed_ms || 0), 0);
                          const shot = screenshots.find((item) => item.name === row.screenshot_name) || {
                            id: row.screenshot_name,
                            name: row.screenshot_name,
                            dataUrl: row.thumbnail,
                          };
                          return (
                            <tr key={row.screenshot_name} className="hover:bg-[#fafaf8] transition-colors">
                              <td className="px-3 py-2.5">
                                <div className="flex items-center gap-2.5 min-w-0">
                                  <div className="w-10 h-7 rounded-md border border-[#e4e4e0] bg-[#f1f1ee] overflow-hidden shrink-0">
                                    {row.thumbnail ? <img src={row.thumbnail} alt="" className="w-full h-full object-cover" /> : <Camera className="w-3.5 h-3.5 text-[#aaa9a2] m-auto mt-1.5" />}
                                  </div>
                                  <span className="font-mono text-[10px] text-[#444440] truncate">{row.screenshot_name}</span>
                                </div>
                              </td>
                              <td className="px-3 py-2.5">
                                <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[8px] font-semibold ${row.passed ? 'ds-status-success' : 'ds-status-danger'}`}>
                                  {row.passed ? <CheckCircle2 className="w-2.5 h-2.5" /> : <X className="w-2.5 h-2.5" />}
                                  {row.passed ? 'PASS' : 'FAIL'}
                                </span>
                              </td>
                              <td className="px-3 py-2.5">
                                {failedNames.length ? (
                                  <div className="flex flex-wrap gap-1">
                                    {failedNames.slice(0, 3).map((name) => <span key={name} className="rounded bg-[#fff2f1] px-1.5 py-0.5 font-mono text-[8px] text-rose-300">{name}</span>)}
                                    {failedNames.length > 3 && <span className="text-[8px] text-[#999991]">+{failedNames.length - 3}</span>}
                                  </div>
                                ) : <span className="text-[9px] text-[#a0a099]">—</span>}
                              </td>
                              <td className="px-3 py-2.5 text-[9px] text-[#77776f] font-mono">{totalTime.toFixed(1)} ms</td>
                              <td className="px-3 py-2.5 text-right">
                                <button onClick={() => onInspectScreenshotOnCanvas(shot, row)} className="inline-flex items-center gap-1 text-[9px] font-medium text-[#5e5e58] hover:text-[#1d1d1b]">
                                  <Eye className="w-3 h-3" />画布复盘
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    {filteredRows.length === 0 && (
                      <div className="py-12 text-center text-[10px] text-[#989891]">当前筛选没有结果。</div>
                    )}
                  </div>
                </section>

                <aside className="space-y-3">
                  <div className="ds-panel p-3.5">
                    <div className="flex items-center gap-2 mb-3">
                      <BarChart3 className="w-3.5 h-3.5 text-[#77776f]" />
                      <span className="text-[10px] font-semibold text-[#3b3b37]">Locator Health</span>
                    </div>
                    <div className="space-y-2.5">
                      {(summary.locator_stats || []).length === 0 ? (
                        <div className="text-[9px] leading-5 text-[#999991]">本次响应没有 locator stats。</div>
                      ) : summary.locator_stats!.map((stat) => (
                        <div key={stat.locator_name}>
                          <div className="flex items-center justify-between gap-2 text-[9px]">
                            <span className="font-mono text-[#55554f] truncate">{stat.locator_name}</span>
                            <span className={stat.pass_rate >= 100 ? 'text-emerald-300' : 'text-amber-300'}>{stat.pass_rate.toFixed(0)}%</span>
                          </div>
                          <div className="mt-1 h-1 rounded-full bg-[#ededE9] overflow-hidden">
                            <div className="h-full bg-[#363633]" style={{ width: `${Math.max(2, stat.pass_rate)}%` }} />
                          </div>
                          <div className="mt-1 text-[8px] text-[#a0a099]">avg {stat.avg_elapsed_ms.toFixed(1)} ms · {stat.failed} failed</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="ds-panel p-3.5">
                    <div className="flex items-center gap-2 mb-3">
                      <History className="w-3.5 h-3.5 text-[#77776f]" />
                      <span className="text-[10px] font-semibold text-[#3b3b37]">Recent Runs</span>
                    </div>
                    <div className="space-y-2">
                      {history.slice(0, 5).map((item) => (
                        <div key={item.id} className="flex items-center justify-between gap-2 text-[9px]">
                          <div className="min-w-0">
                            <div className="text-[#55554f]">{new Date(item.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                            <div className="text-[8px] text-[#a0a099]">{item.totalChecks} checks · {Math.round(item.durationMs)} ms</div>
                          </div>
                          <span className={item.failedChecks === 0 ? 'text-emerald-300' : 'text-amber-300'}>{item.passRate.toFixed(1)}%</span>
                        </div>
                      ))}
                      {history.length === 0 && <div className="text-[9px] text-[#999991]">尚无运行历史。</div>}
                    </div>
                  </div>
                </aside>
              </div>
            </>
          ) : (
            <div className="ds-panel flex-1 min-h-[320px] flex items-center justify-center text-center">
              <div className="max-w-sm px-8">
                <div className="w-11 h-11 mx-auto rounded-xl border border-[#e5e5e1] bg-[#f7f7f5] flex items-center justify-center mb-3">
                  <FlaskConical className="w-5 h-5 text-[#77776f]" />
                </div>
                <h3 className="text-sm font-semibold text-[#343431]">准备运行回归套件</h3>
                <p className="text-[10px] leading-5 text-[#8f8f88] mt-1">左侧选择样本和 locator，然后运行。结果会按失败优先展示，并保留最近历史。</p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
