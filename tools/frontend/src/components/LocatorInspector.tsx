import * as React from 'react';
import {
  Sparkles,
  Image as ImageIcon,
  Type,
  Sliders,
  Play,
  Save,
  Download,
  Scissors,
  MousePointer,
  RotateCcw,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Slider } from './ui/slider';
import { Badge } from './ui/badge';
import { LocatorConfig, LocatorType, RecognitionResult } from '../types';

interface LocatorInspectorProps {
  locator: LocatorConfig | null;
  className: string;
  imageSrc: string | null;
  recognitionResult: RecognitionResult | null;
  isRecognizing: boolean;
  onUpdateLocator: (updated: LocatorConfig) => void;
  onTestRecognition: () => void;
  onSaveTemplateToProject: (path: string, base64: string) => Promise<boolean>;
  onTapCoordinate: (x: number, y: number) => void;
}

export function LocatorInspector({
  locator,
  className: uiClassName,
  imageSrc,
  recognitionResult,
  isRecognizing,
  onUpdateLocator,
  onTestRecognition,
  onSaveTemplateToProject,
  onTapCoordinate,
}: LocatorInspectorProps) {
  const [croppedThumbnail, setCroppedThumbnail] = React.useState<string | null>(null);
  const [isSavingTemplate, setIsSavingTemplate] = React.useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = React.useState<string | null>(null);

  if (!locator) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center text-slate-500 select-none">
        <Sliders className="w-10 h-10 text-slate-700 mb-2" />
        <p className="text-xs font-medium text-slate-400">未选择定位符</p>
        <p className="text-[11px] text-slate-600 mt-1">
          在左侧 UI 树中选择或添加定位符以进行配置和调试
        </p>
      </div>
    );
  }

  // Crop image from ROI to create template thumbnail
  const handleCropFromRoi = () => {
    if (!imageSrc || !locator.roi) return;
    const [rx, ry, rw, rh] = locator.roi;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const cvs = document.createElement('canvas');
      cvs.width = rw;
      cvs.height = rh;
      const ctx = cvs.getContext('2d');
      if (ctx) {
        ctx.drawImage(img, rx, ry, rw, rh, 0, 0, rw, rh);
        const dataUrl = cvs.toDataURL('image/png');
        setCroppedThumbnail(dataUrl);
      }
    };
    img.src = imageSrc;
  };

  // Save template to project
  const handleSaveTemplate = async () => {
    if (!croppedThumbnail) return;
    const templatePath =
      locator.template && locator.template[0]
        ? locator.template[0]
        : `assets/image/${locator.name}.png`;

    setIsSavingTemplate(true);
    const ok = await onSaveTemplateToProject(templatePath, croppedThumbnail);
    setIsSavingTemplate(false);
    if (ok) {
      setSaveSuccessMsg('模板图片已保存至工程目录！');
      setTimeout(() => setSaveSuccessMsg(null), 3000);
    }
  };

  // Download cropped template as PNG
  const handleDownloadTemplate = () => {
    if (!croppedThumbnail) return;
    const a = document.createElement('a');
    a.href = croppedThumbnail;
    a.download = `${locator.name}.png`;
    a.click();
  };

  const handleRoiChange = (index: number, val: number) => {
    const current = locator.roi ? [...locator.roi] : [0, 0, 0, 0];
    current[index] = Math.max(0, val);
    onUpdateLocator({ ...locator, roi: current as [number, number, number, number] });
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/40 border-l border-slate-800 overflow-y-auto select-none p-4 space-y-4">
      {/* Header */}
      <div className="space-y-1 pb-3 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <Badge variant="outline" className="text-[10px] font-mono text-sky-400 border-sky-500/30">
            {uiClassName}
          </Badge>
          <span className="text-[10px] text-slate-500">Locator Inspector</span>
        </div>
        <div className="pt-1">
          <label className="text-xs font-semibold text-slate-300">定位符名称 (Name)</label>
          <Input
            value={locator.name}
            onChange={(e) => onUpdateLocator({ ...locator, name: e.target.value })}
            className="mt-1 font-mono text-xs"
            placeholder="例如: start_btn"
          />
        </div>
      </div>

      {/* Type Selector: Template vs OCR */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-300">识别模式 (Mode)</label>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onUpdateLocator({ ...locator, type: 'Template' })}
            className={`flex items-center justify-center space-x-1.5 p-2 rounded-lg border text-xs font-medium transition-all ${
              locator.type === 'Template'
                ? 'bg-sky-950/60 border-sky-500 text-sky-300 shadow-xs'
                : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5 text-sky-400" />
            <span>模板匹配 (Template)</span>
          </button>
          <button
            onClick={() => onUpdateLocator({ ...locator, type: 'OCR' })}
            className={`flex items-center justify-center space-x-1.5 p-2 rounded-lg border text-xs font-medium transition-all ${
              locator.type === 'OCR'
                ? 'bg-emerald-950/60 border-emerald-500 text-emerald-300 shadow-xs'
                : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
            }`}
          >
            <Type className="w-3.5 h-3.5 text-emerald-400" />
            <span>文字识别 (OCR)</span>
          </button>
        </div>
      </div>

      {/* ROI Settings */}
      <div className="space-y-2 p-3 rounded-lg border border-slate-800 bg-slate-950/40">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-slate-300">识别区域 (ROI)</label>
          <div className="flex items-center space-x-1">
            <button
              onClick={() => onUpdateLocator({ ...locator, roi: null })}
              className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
            >
              全屏 (Clear)
            </button>
          </div>
        </div>

        {locator.roi ? (
          <div className="grid grid-cols-4 gap-2">
            <div>
              <span className="text-[10px] text-slate-500 font-mono">X</span>
              <Input
                type="number"
                value={locator.roi[0]}
                onChange={(e) => handleRoiChange(0, parseInt(e.target.value) || 0)}
                className="h-7 text-xs font-mono text-center p-1"
              />
            </div>
            <div>
              <span className="text-[10px] text-slate-500 font-mono">Y</span>
              <Input
                type="number"
                value={locator.roi[1]}
                onChange={(e) => handleRoiChange(1, parseInt(e.target.value) || 0)}
                className="h-7 text-xs font-mono text-center p-1"
              />
            </div>
            <div>
              <span className="text-[10px] text-slate-500 font-mono">W</span>
              <Input
                type="number"
                value={locator.roi[2]}
                onChange={(e) => handleRoiChange(2, parseInt(e.target.value) || 0)}
                className="h-7 text-xs font-mono text-center p-1"
              />
            </div>
            <div>
              <span className="text-[10px] text-slate-500 font-mono">H</span>
              <Input
                type="number"
                value={locator.roi[3]}
                onChange={(e) => handleRoiChange(3, parseInt(e.target.value) || 0)}
                className="h-7 text-xs font-mono text-center p-1"
              />
            </div>
          </div>
        ) : (
          <div className="text-center py-2 text-[11px] text-slate-500 italic">
            当前为全屏识别 (0, 0, 0, 0)。可在左侧画布使用「框选 ROI」快速划定范围。
          </div>
        )}
      </div>

      {/* Template Specific Options */}
      {locator.type === 'Template' ? (
        <div className="space-y-3 p-3 rounded-lg border border-slate-800 bg-slate-950/40">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300">模板图片路径 (Path)</label>
            <Input
              value={locator.template ? locator.template[0] || '' : ''}
              onChange={(e) =>
                onUpdateLocator({ ...locator, template: [e.target.value] })
              }
              className="h-8 font-mono text-xs"
              placeholder="assets/image/xxx.png"
            />
          </div>

          {/* Template Visual Thumbnail & Crop Actions */}
          <div className="space-y-2 pt-1 border-t border-slate-800/80">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">模板图采样子窗口</span>
              <Button
                id="btnCropSelection"
                size="sm"
                variant="outline"
                onClick={handleCropFromRoi}
                disabled={!locator.roi || !imageSrc}
                className="h-6 px-2 text-[10px]"
                title="从画布当前 ROI 框中裁剪生成模板图片"
              >
                <Scissors className="w-3 h-3 mr-1" />
                从当前 ROI 截取
              </Button>
            </div>

            {croppedThumbnail && (
              <div className="space-y-2">
                <div className="flex items-center justify-center p-2 rounded border border-slate-800 bg-black/40 min-h-[64px]">
                  <img
                    src={croppedThumbnail}
                    alt="Template Preview"
                    className="max-h-24 max-w-full object-contain rounded shadow-xs"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    size="sm"
                    onClick={handleSaveTemplate}
                    disabled={isSavingTemplate}
                    className="flex-1 h-7 text-xs bg-sky-600 hover:bg-sky-500 text-white"
                  >
                    <Save className="w-3 h-3 mr-1" />
                    <span>{isSavingTemplate ? '保存中...' : '保存至工程'}</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleDownloadTemplate}
                    className="h-7 px-2 text-xs"
                    title="下载为本地 PNG"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </Button>
                </div>
                {saveSuccessMsg && (
                  <p className="text-[11px] text-emerald-400 text-center animate-in fade-in">
                    {saveSuccessMsg}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Threshold Slider */}
          <div className="pt-2 border-t border-slate-800/80">
            <Slider
              label="相似度阈值 (Threshold)"
              min={0.5}
              max={1.0}
              step={0.01}
              value={locator.threshold ?? 0.85}
              onChange={(val) => onUpdateLocator({ ...locator, threshold: val })}
              unit=""
            />
          </div>
        </div>
      ) : (
        /* OCR Specific Options */
        <div className="space-y-3 p-3 rounded-lg border border-slate-800 bg-slate-950/40">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300">期望识别文本 (Expected)</label>
            <Input
              value={locator.expected ? locator.expected.join(', ') : ''}
              onChange={(e) =>
                onUpdateLocator({
                  ...locator,
                  expected: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                })
              }
              className="h-8 text-xs font-medium"
              placeholder="例如: 开始行动, 确定"
            />
          </div>
        </div>
      )}

      {/* Recognition Test Trigger */}
      <div className="space-y-3 pt-2">
        <Button
          id="btnTestRecognition"
          onClick={onTestRecognition}
          disabled={isRecognizing}
          className="w-full h-9 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white font-medium text-xs shadow-md shadow-sky-950/40"
        >
          <Play className={`w-3.5 h-3.5 mr-1.5 ${isRecognizing ? 'animate-spin' : ''}`} />
          <span>{isRecognizing ? '正在进行识别算法推理...' : '测试当前识别 (Test)'}</span>
        </Button>

        {/* Recognition Result Summary */}
        {recognitionResult && (
          <div
            className={`p-3 rounded-lg border space-y-2 animate-in fade-in duration-200 ${
              recognitionResult.hit
                ? 'bg-emerald-950/30 border-emerald-500/50'
                : 'bg-rose-950/30 border-rose-500/50'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5">
                {recognitionResult.hit ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-400" />
                )}
                <span className="text-xs font-bold text-slate-200">
                  {recognitionResult.hit ? '识别成功 (HIT)' : '未匹配 (MISS)'}
                </span>
              </div>
              {recognitionResult.elapsed_ms !== undefined && (
                <span className="text-[10px] text-slate-400 font-mono">
                  耗时: {recognitionResult.elapsed_ms.toFixed(1)} ms
                </span>
              )}
            </div>

            {recognitionResult.score !== null && recognitionResult.score !== undefined && (
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">匹配得分 (Score):</span>
                <span className="font-bold text-emerald-400">
                  {(recognitionResult.score * 100).toFixed(1)}%
                </span>
              </div>
            )}

            {recognitionResult.box && (
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">命中位置 (Box):</span>
                <span className="text-slate-300">
                  [{recognitionResult.box.join(', ')}]
                </span>
              </div>
            )}

            {recognitionResult.error && (
              <p className="text-[11px] text-rose-400 bg-rose-950/50 p-1.5 rounded font-mono">
                错误: {recognitionResult.error}
              </p>
            )}

            {/* Click on Match Button */}
            {recognitionResult.hit && recognitionResult.box && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (recognitionResult.box) {
                    const [bx, by, bw, bh] = recognitionResult.box;
                    onTapCoordinate(Math.round(bx + bw / 2), Math.round(by + bh / 2));
                  }
                }}
                className="w-full h-7 text-xs border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10"
              >
                <MousePointer className="w-3 h-3 mr-1" />
                <span>点击命中中心点</span>
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
