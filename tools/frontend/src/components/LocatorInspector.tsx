import * as React from 'react';
import {
  AlertCircle,
  CheckCircle,
  Download,
  Image as ImageIcon,
  MousePointer,
  Play,
  Save,
  Scissors,
  Sliders,
  Type,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Slider } from './ui/slider';
import { LocatorConfig, RecognitionResult } from '../types';

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
      <div className="flex h-full flex-col items-center justify-center bg-white p-6 text-center select-none">
        <Sliders className="mb-2 h-8 w-8 text-[#c5c5bf]" />
        <p className="text-[11px] font-semibold text-[#65655f]">未选择定位符</p>
        <p className="mt-1 max-w-[220px] text-[10px] leading-4 text-[#9b9b94]">从左侧页面树中选择一个定位符进行配置。</p>
      </div>
    );
  }

  const handleCropFromRoi = () => {
    if (!imageSrc || !locator.roi) return;
    const [rx, ry, rw, rh] = locator.roi;
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = rw;
      canvas.height = rh;
      const context = canvas.getContext('2d');
      if (!context) return;
      context.drawImage(image, rx, ry, rw, rh, 0, 0, rw, rh);
      setCroppedThumbnail(canvas.toDataURL('image/png'));
    };
    image.src = imageSrc;
  };

  const handleSaveTemplate = async () => {
    if (!croppedThumbnail) return;
    const templatePath = locator.template?.[0] || `assets/image/${locator.name}.png`;
    setIsSavingTemplate(true);
    const ok = await onSaveTemplateToProject(templatePath, croppedThumbnail);
    setIsSavingTemplate(false);
    if (ok) {
      setSaveSuccessMsg('模板已保存到工程');
      setTimeout(() => setSaveSuccessMsg(null), 3000);
    }
  };

  const handleDownloadTemplate = () => {
    if (!croppedThumbnail) return;
    const anchor = document.createElement('a');
    anchor.href = croppedThumbnail;
    anchor.download = `${locator.name}.png`;
    anchor.click();
  };

  const handleRoiChange = (index: number, value: number) => {
    const next = locator.roi ? [...locator.roi] : [0, 0, 0, 0];
    next[index] = Math.max(0, value);
    onUpdateLocator({ ...locator, roi: next as [number, number, number, number] });
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-white p-4 text-[#292927] select-none">
      <div className="mb-4 border-b border-[#ecece8] pb-3">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="rounded-md border border-[#e3e3df] bg-[#f7f7f5] px-2 py-1 font-mono text-[9px] font-medium text-[#55554f]">
            {uiClassName}
          </span>
          <span className="text-[9px] font-medium tracking-wide text-[#9a9a93]">定位符属性</span>
        </div>
        <label className="mb-1.5 block text-[10px] font-semibold text-[#585852]">名称</label>
        <Input
          value={locator.name}
          onChange={(event) => onUpdateLocator({ ...locator, name: event.target.value })}
          className="h-9 font-mono text-[11px]"
          placeholder="start_button"
        />
      </div>

      <section className="mb-4">
        <label className="mb-2 block text-[10px] font-semibold text-[#585852]">识别方式</label>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onUpdateLocator({ ...locator, type: 'Template' })}
            className={`flex h-10 items-center justify-center gap-2 rounded-lg border text-[11px] font-medium transition-colors ${
              locator.type === 'Template'
                ? 'border-[#9d9d96] bg-[#f2f2ef] text-[#262623]'
                : 'border-[#e7e7e3] bg-white text-[#77776f] hover:bg-[#fafaf8]'
            }`}
          >
            <ImageIcon className="h-3.5 w-3.5" />
            模板匹配
          </button>
          <button
            onClick={() => onUpdateLocator({ ...locator, type: 'OCR' })}
            className={`flex h-10 items-center justify-center gap-2 rounded-lg border text-[11px] font-medium transition-colors ${
              locator.type === 'OCR'
                ? 'border-[#9d9d96] bg-[#f2f2ef] text-[#262623]'
                : 'border-[#e7e7e3] bg-white text-[#77776f] hover:bg-[#fafaf8]'
            }`}
          >
            <Type className="h-3.5 w-3.5 text-emerald-600" />
            OCR 文字
          </button>
        </div>
      </section>

      <section className="mb-4 rounded-lg border border-[#e9e9e5] bg-[#fafaf8] p-3">
        <div className="mb-2.5 flex items-center justify-between">
          <label className="text-[10px] font-semibold text-[#585852]">识别区域</label>
          <button
            onClick={() => onUpdateLocator({ ...locator, roi: null })}
            className="text-[9px] font-medium text-[#85857e] hover:text-[#30302e]"
          >
            使用全屏
          </button>
        </div>
        {locator.roi ? (
          <div className="grid grid-cols-4 gap-2">
            {['X', 'Y', 'W', 'H'].map((label, index) => (
              <label key={label} className="block">
                <span className="mb-1 block font-mono text-[8px] font-semibold text-[#9b9b94]">{label}</span>
                <Input
                  type="number"
                  value={locator.roi?.[index] ?? 0}
                  onChange={(event) => handleRoiChange(index, Number.parseInt(event.target.value) || 0)}
                  className="h-8 px-1 text-center font-mono text-[10px]"
                />
              </label>
            ))}
          </div>
        ) : (
          <p className="py-1 text-[10px] leading-4 text-[#96968f]">当前使用全屏识别。也可以在画布中直接框选 ROI。</p>
        )}
      </section>

      {locator.type === 'Template' ? (
        <section className="mb-4 rounded-lg border border-[#e9e9e5] bg-white p-3">
          <label className="mb-1.5 block text-[10px] font-semibold text-[#585852]">模板路径</label>
          <Input
            value={locator.template?.[0] || ''}
            onChange={(event) => onUpdateLocator({ ...locator, template: [event.target.value] })}
            className="h-8 font-mono text-[10px]"
            placeholder="assets/image/button.png"
          />

          <div className="mt-3 border-t border-[#eeeeea] pt-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-[10px] font-medium text-[#77776f]">模板采样</span>
              <Button
                id="btnCropSelection"
                size="sm"
                variant="outline"
                onClick={handleCropFromRoi}
                disabled={!locator.roi || !imageSrc}
                className="h-7 px-2 text-[9px]"
                title="从当前 ROI 截取模板"
              >
                <Scissors className="h-3 w-3" />
                截取 ROI
              </Button>
            </div>

            {croppedThumbnail ? (
              <div className="space-y-2">
                <div className="flex min-h-[72px] items-center justify-center rounded-md border border-[#ecece8] bg-[#f7f7f5] p-2">
                  <img src={croppedThumbnail} alt="模板预览" className="max-h-24 max-w-full rounded object-contain" />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleSaveTemplate} disabled={isSavingTemplate} className="h-7 flex-1 text-[9px]">
                    <Save className="h-3 w-3" />
                    {isSavingTemplate ? '保存中' : '保存模板'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleDownloadTemplate} className="h-7 w-8 px-0" title="下载模板">
                    <Download className="h-3.5 w-3.5" />
                  </Button>
                </div>
                {saveSuccessMsg && <p className="text-center text-[9px] text-emerald-700">{saveSuccessMsg}</p>}
              </div>
            ) : (
              <p className="text-[9px] leading-4 text-[#9a9a93]">框选 ROI 后可直接截取并保存为模板图片。</p>
            )}
          </div>

          <div className="mt-3 border-t border-[#eeeeea] pt-3">
            <Slider
              label="相似度阈值"
              min={0.5}
              max={1.0}
              step={0.01}
              value={locator.threshold ?? 0.85}
              onChange={(value) => onUpdateLocator({ ...locator, threshold: value })}
              unit=""
            />
          </div>
        </section>
      ) : (
        <section className="mb-4 rounded-lg border border-[#e9e9e5] bg-white p-3">
          <label className="mb-1.5 block text-[10px] font-semibold text-[#585852]">期望文字</label>
          <Input
            value={locator.expected?.join(', ') || ''}
            onChange={(event) =>
              onUpdateLocator({
                ...locator,
                expected: event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
              })
            }
            className="h-8 text-[10px]"
            placeholder="开始行动, 确定"
          />
          <p className="mt-1.5 text-[9px] text-[#a0a099]">多个候选文本使用英文逗号分隔。</p>
        </section>
      )}

      <div className="mt-auto pt-1">
        <Button
          id="btnTestRecognition"
          onClick={onTestRecognition}
          disabled={isRecognizing}
          className="h-9 w-full text-[11px] font-semibold"
        >
          <Play className={`h-3.5 w-3.5 ${isRecognizing ? 'animate-spin' : ''}`} />
          {isRecognizing ? '正在识别…' : '测试识别'}
        </Button>

        {recognitionResult && (
          <div className={`mt-3 rounded-lg border p-3 ${recognitionResult.hit ? 'ds-status-success' : 'ds-status-danger'}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold">
                {recognitionResult.hit ? <CheckCircle className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
                <span>{recognitionResult.hit ? '识别成功' : '未匹配'}</span>
              </div>
              {recognitionResult.elapsed_ms !== undefined && (
                <span className="font-mono text-[9px] opacity-70">{recognitionResult.elapsed_ms.toFixed(1)} ms</span>
              )}
            </div>

            <div className="mt-2 space-y-1 text-[9px]">
              {recognitionResult.score !== null && recognitionResult.score !== undefined && (
                <div className="flex justify-between gap-3">
                  <span className="opacity-70">匹配得分</span>
                  <span className="font-mono font-semibold">{(recognitionResult.score * 100).toFixed(1)}%</span>
                </div>
              )}
              {recognitionResult.box && (
                <div className="flex justify-between gap-3">
                  <span className="opacity-70">命中位置</span>
                  <span className="font-mono">[{recognitionResult.box.join(', ')}]</span>
                </div>
              )}
              {recognitionResult.error && <p className="mt-2 break-words font-mono text-[9px]">{recognitionResult.error}</p>}
            </div>

            {recognitionResult.hit && recognitionResult.box && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (!recognitionResult.box) return;
                  const [x, y, width, height] = recognitionResult.box;
                  onTapCoordinate(Math.round(x + width / 2), Math.round(y + height / 2));
                }}
                className="mt-2 h-7 w-full border-current bg-white/60 text-[9px]"
              >
                <MousePointer className="h-3 w-3" />
                点击命中中心
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
