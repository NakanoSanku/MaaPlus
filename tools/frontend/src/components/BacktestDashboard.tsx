import * as React from 'react';
import {
  AlertTriangle,
  BarChart3,
  Camera,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Download,
  Eye,
  Filter,
  FlaskConical,
  History,
  Play,
  RefreshCcw,
  RotateCcw,
  SquareStack,
  Upload,
  X,
  XCircle,
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

  return (
    <div className="flex-1 min-h-0 bg-[#0b0d12] text-slate-100 overflow-hidden">
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

      <div className="h-full grid grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-r border-white/8 bg-[#10131a] p-4 overflow-y-auto">
          <div className="mb-5">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">Regression Lab</div>
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">回归套件</h2>
              <FlaskConical className="w-5 h-5 text-emerald-300" />
            </div>
            <p className="text-[11px] leading-5 text-slate-500 mt-1">先定义本次要验证的样本和定位符，再运行、复盘失败并重复验证。</p>
          </div>

          <label className="block text-[10px] uppercase tracking-wider text-slate-500 mb-2">UI 类</label>
          <select
            value={selectedClassIndex}
            onChange={(e) => onSelectClassIndex(Number(e.target.value))}
            className="w-full h-9 rounded-lg border border-white/10 bg-black/25 px-3 text-xs text-slate-200 outline-none mb-5"
          >
            {uiClasses.map((cls, index) => (
              <option key={`${cls.name}-${index}`} value={index}>{cls.name}</option>
            ))}
          </select>

          <section className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">样本 {selectedScreenshots.size}/{screenshots.length}</span>
              <div className="flex items-center gap-2 text-[10px]">
                <button onClick={() => setSelectedScreenshots(new Set(screenshots.map((s) => s.name)))} className="text-slate-500 hover:text-slate-200">全选</button>
                <button onClick={() => setSelectedScreenshots(new Set())} className="text-slate-600 hover:text-slate-300">清空</button>
              </div>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {screenshots.length === 0 ? (
                <div className="rounded-lg border border-dashed border-white/10 p-3 text-[11px] text-slate-600">暂无样本。先从画布绑定或上传截图。</div>
              ) : screenshots.map((shot) => (
                <button
                  key={shot.name}
                  onClick={() => toggleName(setSelectedScreenshots, shot.name)}
                  className={`w-full flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${selectedScreenshots.has(shot.name) ? 'border-emerald-400/25 bg-emerald-400/10' : 'border-white/6 bg-black/10 opacity-60'}`}
                >
                  <span className={`w-4 h-4 rounded border flex items-center justify-center ${selectedScreenshots.has(shot.name) ? 'border-emerald-400 bg-emerald-400/15 text-emerald-300' : 'border-slate-700'}`}>
                    {selectedScreenshots.has(shot.name) && <Check className="w-3 h-3" />}
                  </span>
                  <span className="truncate font-mono text-[11px] text-slate-300 flex-1">{shot.name}</span>
                  <Camera className="w-3.5 h-3.5 text-slate-600" />
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <Button variant="outline" size="sm" onClick={() => onBindCurrentScreenshot(selectedClassIndex)} className="h-7 text-[10px] border-white/10 text-slate-400">
                <Camera className="w-3 h-3 mr-1" />绑定画面
              </Button>
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="h-7 text-[10px] border-white/10 text-slate-400">
                <Upload className="w-3 h-3 mr-1" />上传样本
              </Button>
            </div>
          </section>

          <section className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">定位符 {selectedLocators.size}/{locators.length}</span>
              <div className="flex items-center gap-2 text-[10px]">
                <button onClick={() => setSelectedLocators(new Set(locators.map((l) => l.name)))} className="text-slate-500 hover:text-slate-200">全选</button>
                <button onClick={() => setSelectedLocators(new Set())} className="text-slate-600 hover:text-slate-300">清空</button>
              </div>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {locators.map((locator) => (
                <button
                  key={locator.name}
                  onClick={() => toggleName(setSelectedLocators, locator.name)}
                  className={`w-full flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${selectedLocators.has(locator.name) ? 'border-sky-400/20 bg-sky-400/10' : 'border-white/6 bg-black/10 opacity-60'}`}
                >
                  <span className={`w-4 h-4 rounded border flex items-center justify-center ${selectedLocators.has(locator.name) ? 'border-sky-400 bg-sky-400/15 text-sky-300' : 'border-slate-700'}`}>
                    {selectedLocators.has(locator.name) && <Check className="w-3 h-3" />}
                  </span>
                  <span className="truncate font-mono text-[11px] text-slate-300 flex-1">{locator.name}</span>
                  <span className="text-[9px] text-slate-600">{locator.type}</span>
                </button>
              ))}
            </div>
          </section>

          <Button
            id="btnRunBacktest"
            onClick={handleStartBacktest}
            disabled={isRunning || selectedScreenshots.size === 0 || selectedLocators.size === 0}
            className="w-full h-9 text-xs bg-emerald-500 hover:bg-emerald-400 text-[#07100b] font-semibold"
          >
            <Play className={`w-3.5 h-3.5 mr-1.5 ${isRunning ? 'animate-spin' : ''}`} />
            {isRunning ? '正在运行回归…' : `运行 ${selectedScreenshots.size * selectedLocators.size} 项检查`}
          </Button>

          {errorMessage && (
            <div className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/5 p-3 text-[11px] text-rose-300 flex gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />{errorMessage}
            </div>
          )}
        </aside>

        <main className="min-w-0 overflow-y-auto p-5">
          {!summary ? (
            <div className="h-full min-h-[420px] flex items-center justify-center">
              <div className="max-w-lg text-center">
                <div className="mx-auto w-12 h-12 rounded-2xl border border-white/10 bg-white/[0.03] flex items-center justify-center mb-4">
                  <SquareStack className="w-6 h-6 text-slate-500" />
                </div>
                <h3 className="text-sm font-semibold text-slate-200">把回测当成一个可重复的套件</h3>
                <p className="text-xs leading-6 text-slate-500 mt-2">左侧选择样本和定位符。运行后默认只显示失败项，并可一键只重跑失败组合，避免每次面对整张矩阵。</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-w-[1600px] mx-auto">
              <header className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    {failedChecks === 0 ? <CheckCircle2 className="w-5 h-5 text-emerald-300" /> : <XCircle className="w-5 h-5 text-rose-300" />}
                    <h2 className="text-base font-semibold">{summary.ui_class} · {failedChecks === 0 ? '回归通过' : `${failedChecks} 项需要处理`}</h2>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1 font-mono">{summary.total_screenshots} samples × {summary.total_locators} locators · {summary.duration_ms ? `${summary.duration_ms.toFixed(1)} ms` : 'duration unavailable'}</div>
                </div>
                <div className="flex items-center gap-2">
                  {failedChecks > 0 && (
                    <Button variant="outline" size="sm" onClick={handleRerunFailures} disabled={isRunning} className="h-8 text-xs border-amber-400/20 text-amber-300">
                      <RefreshCcw className="w-3.5 h-3.5 mr-1" />只重跑失败项
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={exportResult} className="h-8 text-xs text-slate-400">
                    <Download className="w-3.5 h-3.5 mr-1" />结果 JSON
                  </Button>
                </div>
              </header>

              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="通过率" value={`${summary.pass_rate}%`} hint={passRateDelta === null ? '首次运行' : `${passRateDelta >= 0 ? '+' : ''}${passRateDelta.toFixed(1)}% vs 上次`} icon={<BarChart3 className="w-4 h-4" />} />
                <MetricCard label="通过检查" value={`${summary.passed_checks}/${summary.total_checks}`} hint={`${failedChecks} failed`} icon={<CheckCircle2 className="w-4 h-4" />} />
                <MetricCard label="样本" value={`${summary.total_screenshots}`} hint={`${summary.matrix.filter((row) => !row.passed).length} failed rows`} icon={<Camera className="w-4 h-4" />} />
                <MetricCard label="耗时" value={summary.duration_ms ? `${summary.duration_ms.toFixed(0)} ms` : '—'} hint="本次总识别耗时" icon={<Clock3 className="w-4 h-4" />} />
              </div>

              {summary.locator_stats && summary.locator_stats.length > 0 && (
                <section className="rounded-xl border border-white/8 bg-[#10131a] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">定位符稳定性</div>
                  <div className="grid grid-cols-2 xl:grid-cols-4 gap-2">
                    {summary.locator_stats.map((stat) => (
                      <div key={stat.locator_name} className="rounded-lg border border-white/6 bg-black/15 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-[11px] text-slate-300 truncate">{stat.locator_name}</span>
                          <span className={`font-mono text-[11px] ${stat.pass_rate === 100 ? 'text-emerald-300' : 'text-rose-300'}`}>{stat.pass_rate}%</span>
                        </div>
                        <div className="text-[10px] text-slate-600 mt-1">{stat.failed} failed · {stat.avg_elapsed_ms.toFixed(1)} ms avg</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="rounded-xl border border-white/8 bg-[#10131a] overflow-hidden">
                <div className="h-11 px-3 border-b border-white/8 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-300"><Filter className="w-3.5 h-3.5 text-slate-500" />结果</div>
                  <div className="flex items-center gap-1 rounded-lg bg-black/20 border border-white/6 p-0.5">
                    {(['failed', 'all', 'passed'] as ResultFilter[]).map((mode) => (
                      <button key={mode} onClick={() => setFilterMode(mode)} className={`px-2.5 py-1 text-[10px] rounded-md transition-colors ${filterMode === mode ? 'bg-white/8 text-slate-200' : 'text-slate-600 hover:text-slate-400'}`}>
                        {mode === 'failed' ? `失败 ${summary.matrix.filter((r) => !r.passed).length}` : mode === 'passed' ? `通过 ${summary.matrix.filter((r) => r.passed).length}` : `全部 ${summary.matrix.length}`}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="bg-black/20 text-[10px] uppercase tracking-wider text-slate-600">
                      <tr>
                        <th className="px-3 py-2.5 min-w-[220px]">Sample</th>
                        {summary.locator_stats?.map((stat) => <th key={stat.locator_name} className="px-3 py-2.5 min-w-[130px] text-center font-mono normal-case tracking-normal">{stat.locator_name}</th>) || Object.keys(summary.matrix[0]?.results || {}).map((name) => <th key={name} className="px-3 py-2.5 min-w-[130px] text-center font-mono normal-case tracking-normal">{name}</th>)}
                        <th className="px-3 py-2.5 text-right">Review</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/6">
                      {filteredRows.map((row) => {
                        const shot = screenshots.find((item) => item.name === row.screenshot_name) || { id: row.screenshot_name, name: row.screenshot_name, dataUrl: row.thumbnail };
                        return (
                          <tr key={row.screenshot_name} className="hover:bg-white/[0.025]">
                            <td className="px-3 py-3">
                              <div className="flex items-center gap-2.5">
                                <div className="w-14 h-9 rounded-md overflow-hidden bg-black border border-white/8 shrink-0">
                                  {row.thumbnail && <img src={row.thumbnail} alt="" className="w-full h-full object-cover" />}
                                </div>
                                <div className="min-w-0">
                                  <div className="font-mono text-[11px] text-slate-300 truncate">{row.screenshot_name}</div>
                                  <div className={`text-[10px] mt-0.5 ${row.passed ? 'text-emerald-400' : 'text-rose-400'}`}>{row.passed ? 'PASS' : 'FAIL'}</div>
                                </div>
                              </div>
                            </td>
                            {Object.entries(row.results).map(([name, result]) => {
                              const passed = result.passed ?? result.hit;
                              return (
                                <td key={name} className="px-3 py-3 text-center">
                                  <div className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[10px] ${passed ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300' : 'border-rose-400/25 bg-rose-400/10 text-rose-300'}`} title={result.failure_reason || result.error || ''}>
                                    {passed ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                                    {result.hit ? (result.score != null ? `${Math.round(result.score * 100)}%` : 'HIT') : 'MISS'}
                                  </div>
                                  {result.expected_hit === false && <div className="text-[9px] text-slate-600 mt-1">expected miss</div>}
                                </td>
                              );
                            })}
                            <td className="px-3 py-3 text-right">
                              <Button variant="ghost" size="sm" onClick={() => onInspectScreenshotOnCanvas(shot, row)} className="h-7 text-[10px] text-sky-300">
                                <Eye className="w-3.5 h-3.5 mr-1" />画布复盘<ChevronRight className="w-3 h-3 ml-0.5" />
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {filteredRows.length === 0 && (
                  <div className="py-10 text-center text-xs text-slate-600">当前筛选下没有结果。</div>
                )}
              </section>

              {history.length > 0 && (
                <section className="rounded-xl border border-white/8 bg-[#10131a] p-3">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-500 mb-2"><History className="w-3.5 h-3.5" />最近运行</div>
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {history.map((item, index) => (
                      <div key={item.id} className="min-w-[150px] rounded-lg border border-white/6 bg-black/15 px-3 py-2">
                        <div className="flex items-center justify-between"><span className="font-mono text-xs text-slate-300">{item.passRate}%</span>{index === 0 && <span className="text-[9px] text-emerald-400">current</span>}</div>
                        <div className="text-[10px] text-slate-600 mt-1">{item.failedChecks} failed · {new Date(item.at).toLocaleTimeString()}</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function MetricCard({ label, value, hint, icon }: { label: string; value: string; hint: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/8 bg-[#10131a] px-4 py-3">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-600"><span>{label}</span><span className="text-slate-500">{icon}</span></div>
      <div className="font-mono text-xl font-semibold text-slate-100 mt-2">{value}</div>
      <div className="text-[10px] text-slate-600 mt-1">{hint}</div>
    </div>
  );
}
