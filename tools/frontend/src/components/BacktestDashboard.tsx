import * as React from 'react';
import {
  CheckSquare,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Percent,
  Layers,
  Camera,
  Upload,
  Eye,
  AlertTriangle,
  FileCheck,
  ChevronDown,
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  BoundScreenshot,
  ClassBacktestMatrixRow,
  ClassBacktestSummary,
  UIClass,
} from '../types';

interface BacktestDashboardProps {
  uiClasses: UIClass[];
  selectedClassIndex: number;
  onSelectClassIndex: (index: number) => void;
  onRunClassBacktest: (uiClass: UIClass) => Promise<ClassBacktestSummary>;
  onInspectScreenshotOnCanvas: (
    screenshot: BoundScreenshot,
    rowResult?: ClassBacktestMatrixRow
  ) => void;
  onBindCurrentScreenshot: (classIndex: number) => void;
  onUploadScreenshot: (classIndex: number, file: File) => void;
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
  const [isRunning, setIsRunning] = React.useState(false);
  const [summary, setSummary] = React.useState<ClassBacktestSummary | null>(null);
  const [filterMode, setFilterMode] = React.useState<'all' | 'passed' | 'failed'>('all');

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const activeClass = uiClasses[selectedClassIndex] || uiClasses[0];
  const screenshots = activeClass?.screenshots || [];
  const locators = activeClass?.locators || [];

  // Reset summary when switching class
  React.useEffect(() => {
    setSummary(null);
  }, [selectedClassIndex]);

  const handleStartBacktest = async () => {
    if (!activeClass || screenshots.length === 0) return;
    setIsRunning(true);
    try {
      const res = await onRunClassBacktest(activeClass);
      setSummary(res);
    } catch (err) {
      console.error('Class backtest error:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const handleUploadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUploadScreenshot(selectedClassIndex, e.target.files[0]);
      e.target.value = '';
    }
  };

  const filteredMatrix = React.useMemo(() => {
    if (!summary || !summary.matrix) return [];
    if (filterMode === 'passed') return summary.matrix.filter((r) => r.passed);
    if (filterMode === 'failed') return summary.matrix.filter((r) => !r.passed);
    return summary.matrix;
  }, [summary, filterMode]);

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 p-6 overflow-y-auto space-y-6 select-none">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleUploadFile}
        accept="image/*"
        className="hidden"
      />

      {/* Top Banner & Context Switcher */}
      <div className="flex items-center justify-between bg-slate-900/70 p-4 rounded-xl border border-slate-800">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-3">
            <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2">
              <CheckSquare className="w-5 h-5 text-sky-400" />
              <span>UI 类样本回测 (UI Class Backtesting)</span>
            </h2>

            {/* UI Class Selector Dropdown */}
            <div className="flex items-center space-x-1.5 bg-slate-950 border border-slate-700/80 rounded-lg px-2 py-1">
              <Layers className="w-3.5 h-3.5 text-sky-400" />
              <select
                value={selectedClassIndex}
                onChange={(e) => onSelectClassIndex(parseInt(e.target.value))}
                className="bg-transparent text-xs font-semibold text-sky-300 focus:outline-none cursor-pointer"
              >
                {uiClasses.map((cls, idx) => (
                  <option key={cls.name + idx} value={idx} className="bg-slate-900 text-slate-200">
                    {cls.name} ({cls.locators.length} 元素 · {(cls.screenshots || []).length} 截图)
                  </option>
                ))}
              </select>
            </div>
          </div>

          <p className="text-xs text-slate-400">
            针对当前 UI 类「<span className="text-sky-300 font-mono font-medium">{activeClass?.name}</span>」绑定的{' '}
            <span className="text-emerald-400 font-mono font-semibold">{screenshots.length}</span> 张样本截图，
            全面测试其包含的{' '}
            <span className="text-sky-400 font-mono font-semibold">{locators.length}</span> 个元素能否全部准确匹配识别。
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onBindCurrentScreenshot(selectedClassIndex)}
            className="h-8 text-xs text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
            title="将当前画布画面加入此类作为测试样本"
          >
            <Camera className="w-3.5 h-3.5 mr-1" />
            <span>绑定当前画面</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            className="h-8 text-xs text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/10"
            title="上传本地图片绑定到当前类"
          >
            <Upload className="w-3.5 h-3.5 mr-1" />
            <span>上传样本截图</span>
          </Button>

          <Button
            id="btnRunBacktest"
            onClick={handleStartBacktest}
            disabled={!activeClass || screenshots.length === 0 || locators.length === 0 || isRunning}
            className="h-8 px-4 text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white shadow-md shadow-sky-950/40"
          >
            <Play className={`w-3.5 h-3.5 mr-1.5 ${isRunning ? 'animate-spin' : ''}`} />
            <span>
              {isRunning
                ? '回测推理中...'
                : `执行「${activeClass?.name || 'UI'}」类回测`}
            </span>
          </Button>
        </div>
      </div>

      {/* Bound Screenshots Strip (Shows the N bound screenshots of this UI Class) */}
      <div className="bg-slate-900/40 p-3 rounded-xl border border-slate-800 space-y-2">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-300 px-1">
          <div className="flex items-center space-x-1.5">
            <Camera className="w-4 h-4 text-emerald-400" />
            <span>「{activeClass?.name}」已绑定的样本截图 ({screenshots.length})</span>
          </div>
          <span className="text-[11px] text-slate-500 font-normal">
            点击缩略图可在画布中载入检查
          </span>
        </div>

        {screenshots.length === 0 ? (
          <div className="p-4 border border-dashed border-slate-800 rounded-lg text-center text-xs text-slate-500 space-y-1">
            <p>该 UI 类尚未绑定任何样本截图。</p>
            <p className="text-[11px] text-slate-600">
              请点击右上角「绑定当前画面」或「上传样本截图」，为 {activeClass?.name} 添加用于回归测试的真实游戏画面。
            </p>
          </div>
        ) : (
          <div className="flex items-center space-x-3 overflow-x-auto pb-1 pt-1">
            {screenshots.map((shot) => (
              <div
                key={shot.id}
                onClick={() => onInspectScreenshotOnCanvas(shot)}
                className="group relative flex flex-col items-center p-1.5 rounded-lg border border-slate-800 hover:border-emerald-500/50 bg-slate-950/60 hover:bg-slate-900 cursor-pointer transition-all shrink-0 w-32"
                title={`查看 ${shot.name}`}
              >
                <div className="w-full h-16 bg-black rounded overflow-hidden flex items-center justify-center border border-slate-800/80">
                  {shot.dataUrl ? (
                    <img
                      src={shot.dataUrl}
                      alt={shot.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                  ) : (
                    <Camera className="w-6 h-6 text-slate-700" />
                  )}
                </div>
                <span className="text-[11px] font-mono text-slate-300 truncate w-full text-center mt-1">
                  {shot.name}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Summary Metrics Cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-4 animate-in fade-in duration-200">
          <div className="bg-slate-900/40 border border-slate-800 p-4 rounded-xl space-y-1">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>绑定样本数 (Screenshots)</span>
              <FileCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {summary.total_screenshots}
            </div>
          </div>

          <div className="bg-slate-900/40 border border-slate-800 p-4 rounded-xl space-y-1">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>包含元素数 (Locators)</span>
              <Layers className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-sky-400">
              {summary.total_locators}
            </div>
          </div>

          <div className="bg-slate-900/40 border border-slate-800 p-4 rounded-xl space-y-1">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>元素匹配项 (Passed / Total)</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {summary.passed_checks} / {summary.total_checks}
            </div>
          </div>

          <div className="bg-slate-900/40 border border-slate-800 p-4 rounded-xl space-y-1">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>综合通过率 (Pass Rate)</span>
              <Percent className="w-4 h-4 text-sky-400" />
            </div>
            <div
              className={`text-2xl font-bold font-mono ${
                summary.pass_rate >= 100
                  ? 'text-emerald-400'
                  : summary.pass_rate >= 70
                  ? 'text-amber-400'
                  : 'text-rose-400'
              }`}
            >
              {summary.pass_rate}%
            </div>
          </div>
        </div>
      )}

      {/* Class Matrix Table: Screenshots × Locators */}
      {summary ? (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden flex flex-col flex-1">
          {/* Table Toolbar */}
          <div className="p-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-200">
              「{summary.ui_class}」匹配矩阵 ({filteredMatrix.length} / {summary.total_screenshots} 张截图)
            </span>
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setFilterMode('all')}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                  filterMode === 'all'
                    ? 'bg-slate-800 text-sky-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                全部 ({summary.total_screenshots})
              </button>
              <button
                onClick={() => setFilterMode('passed')}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                  filterMode === 'passed'
                    ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                全部元素通过 ({summary.matrix.filter((r) => r.passed).length})
              </button>
              <button
                onClick={() => setFilterMode('failed')}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                  filterMode === 'failed'
                    ? 'bg-rose-950/60 text-rose-400 border border-rose-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                存在未匹配元素 ({summary.matrix.filter((r) => !r.passed).length})
              </button>
            </div>
          </div>

          {/* Matrix Header & Rows */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold font-mono">
                  <th className="p-3 min-w-[200px]">样本截图 (Screenshot)</th>
                  {locators.map((loc) => (
                    <th key={loc.name} className="p-3 min-w-[140px] text-center">
                      <span className="text-slate-200">{loc.name}</span>
                      <span className="block text-[10px] text-slate-500 font-normal">
                        ({loc.type})
                      </span>
                    </th>
                  ))}
                  <th className="p-3 text-center min-w-[100px]">整页判定</th>
                  <th className="p-3 text-right min-w-[110px]">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {filteredMatrix.map((row, idx) => {
                  const correspondingShot = screenshots.find(
                    (s) => s.name === row.screenshot_name
                  );

                  return (
                    <tr
                      key={row.screenshot_name + idx}
                      className="hover:bg-slate-800/30 transition-colors"
                    >
                      {/* Screenshot Col */}
                      <td className="p-3">
                        <div className="flex items-center space-x-2.5">
                          {row.thumbnail ? (
                            <div className="w-12 h-8 rounded border border-slate-800 bg-black overflow-hidden shrink-0">
                              <img
                                src={row.thumbnail}
                                alt={row.screenshot_name}
                                className="w-full h-full object-cover"
                              />
                            </div>
                          ) : (
                            <Camera className="w-5 h-5 text-slate-600 shrink-0" />
                          )}
                          <span className="font-mono font-medium text-slate-200 truncate">
                            {row.screenshot_name}
                          </span>
                        </div>
                      </td>

                      {/* Locators Result Cells */}
                      {locators.map((loc) => {
                        const locRes = row.results[loc.name];
                        if (!locRes) {
                          return (
                            <td key={loc.name} className="p-3 text-center text-slate-600">
                              -
                            </td>
                          );
                        }

                        return (
                          <td key={loc.name} className="p-3 text-center">
                            {locRes.hit ? (
                              <div className="inline-flex flex-col items-center">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 border border-emerald-500/50 text-emerald-400">
                                  HIT {locRes.score !== null ? `${(locRes.score * 100).toFixed(0)}%` : ''}
                                </span>
                                {locRes.box && (
                                  <span className="text-[9px] font-mono text-slate-500 mt-0.5">
                                    [{locRes.box[0]},{locRes.box[1]}]
                                  </span>
                                )}
                              </div>
                            ) : (
                              <div className="inline-flex flex-col items-center">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950 border border-rose-500/50 text-rose-400">
                                  MISS
                                </span>
                                {locRes.error && (
                                  <span className="text-[9px] text-rose-400 max-w-[120px] truncate" title={locRes.error}>
                                    {locRes.error}
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                        );
                      })}

                      {/* Overall Status Col */}
                      <td className="p-3 text-center">
                        <Badge
                          variant={row.passed ? 'default' : 'destructive'}
                          className="text-[10px] font-mono px-2 py-0.5"
                        >
                          {row.passed ? 'PASS' : 'FAIL'}
                        </Badge>
                      </td>

                      {/* Action Col */}
                      <td className="p-3 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const targetShot: BoundScreenshot = correspondingShot || {
                              id: row.screenshot_name,
                              name: row.screenshot_name,
                              dataUrl: row.thumbnail,
                            };
                            onInspectScreenshotOnCanvas(targetShot, row);
                          }}
                          className="h-7 px-2 text-xs text-sky-400 border-sky-500/30 hover:bg-sky-500/10"
                          title="在画布中载入此截图并标出各元素识别框"
                        >
                          <Eye className="w-3.5 h-3.5 mr-1" />
                          <span>画布复盘</span>
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-52 border border-dashed border-slate-800 rounded-xl text-slate-500 space-y-2">
          <CheckSquare className="w-8 h-8 text-slate-700" />
          <p className="text-xs font-medium text-slate-400">尚未执行此类回测</p>
          <p className="text-[11px] text-slate-600 text-center max-w-md">
            点击上方「执行「{activeClass?.name}」类回测」按钮，系统将使用绑定的 {screenshots.length} 张样本截图
            对该 UI 类的所有元素进行批量推理检验。
          </p>
        </div>
      )}
    </div>
  );
}
