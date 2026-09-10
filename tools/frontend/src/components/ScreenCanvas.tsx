import * as React from 'react';
import {
  Hand,
  MousePointer,
  Crop,
  Pipette,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Scan,
  Crosshair,
  Eye,
  EyeOff,
} from 'lucide-react';
import { Button } from './ui/button';
import { LocatorConfig, RecognitionResult } from '../types';

export type CanvasTool = 'hand' | 'touch' | 'roi' | 'pick';

interface ScreenCanvasProps {
  imageSrc: string | null;
  imageDimensions: { width: number; height: number };
  activeLocator: LocatorConfig | null;
  allLocators: LocatorConfig[];
  recognitionResult: RecognitionResult | null;
  multiRecognitionBoxes?: Array<{
    name: string;
    hit: boolean;
    score?: number | null;
    box?: [number, number, number, number] | null;
  }>;
  activeScreenshotName?: string | null;
  onReturnToLive?: () => void;
  onRoiSelected: (roi: [number, number, number, number]) => void;
  onTouchTap: (x: number, y: number) => void;
  className?: string;
}

export function ScreenCanvas({
  imageSrc,
  imageDimensions,
  activeLocator,
  allLocators,
  recognitionResult,
  multiRecognitionBoxes,
  activeScreenshotName,
  onReturnToLive,
  onRoiSelected,
  onTouchTap,
  className,
}: ScreenCanvasProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const imageRef = React.useRef<HTMLImageElement>(null);

  // Pan & Zoom state
  const [scale, setScale] = React.useState(1);
  const [pan, setPan] = React.useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = React.useState(false);
  const [panStart, setPanStart] = React.useState({ x: 0, y: 0 });

  // Tool selection
  const [activeTool, setActiveTool] = React.useState<CanvasTool>('roi');

  // ROI Selection dragging
  const [isSelectingRoi, setIsSelectingRoi] = React.useState(false);
  const [roiStart, setRoiStart] = React.useState<{ x: number; y: number } | null>(null);
  const [currentRoi, setCurrentRoi] = React.useState<[number, number, number, number] | null>(null);

  // Magnifier & Cursor coordinate inspection
  const [cursorPos, setCursorPos] = React.useState<{ x: number; y: number } | null>(null);
  const [canvasCursorPos, setCanvasCursorPos] = React.useState<{ x: number; y: number } | null>(null);
  const [showMagnifier, setShowMagnifier] = React.useState(true);
  const [sampledColor, setSampledColor] = React.useState<string | null>(null);

  // Hidden canvas for sampling pixel colors
  const colorCanvasRef = React.useRef<HTMLCanvasElement | null>(null);

  // Reset zoom to fit
  const fitToScreen = React.useCallback(() => {
    if (!containerRef.current || !imageDimensions.width || !imageDimensions.height) return;
    const { clientWidth, clientHeight } = containerRef.current;
    const pad = 40;
    const scaleX = (clientWidth - pad) / imageDimensions.width;
    const scaleY = (clientHeight - pad) / imageDimensions.height;
    const newScale = Math.min(scaleX, scaleY, 1);
    setScale(Math.max(newScale, 0.1));
    setPan({
      x: (clientWidth - imageDimensions.width * newScale) / 2,
      y: (clientHeight - imageDimensions.height * newScale) / 2,
    });
  }, [imageDimensions]);

  // Initial fit when image loads
  React.useEffect(() => {
    if (imageDimensions.width > 0) {
      fitToScreen();
    }
  }, [imageDimensions.width, imageDimensions.height, fitToScreen]);

  // Wheel zoom centered on cursor
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newScale = Math.min(Math.max(scale * zoomFactor, 0.05), 10);

    const newPanX = mouseX - (mouseX - pan.x) * (newScale / scale);
    const newPanY = mouseY - (mouseY - pan.y) * (newScale / scale);

    setScale(newScale);
    setPan({ x: newPanX, y: newPanY });
  };

  // Convert client coordinates to image pixel coordinates
  const clientToImageCoords = (clientX: number, clientY: number) => {
    if (!containerRef.current || imageDimensions.width === 0) return null;
    const rect = containerRef.current.getBoundingClientRect();
    const containerX = clientX - rect.left;
    const containerY = clientY - rect.top;

    const imgX = Math.round((containerX - pan.x) / scale);
    const imgY = Math.round((containerY - pan.y) / scale);

    if (imgX < 0 || imgY < 0 || imgX >= imageDimensions.width || imgY >= imageDimensions.height) {
      return null;
    }
    return { x: imgX, y: imgY };
  };

  // Mouse move over canvas
  const handleMouseMove = (e: React.MouseEvent) => {
    const coords = clientToImageCoords(e.clientX, e.clientY);
    setCursorPos(coords);

    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setCanvasCursorPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }

    // Panning
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
      return;
    }

    // ROI Dragging
    if (isSelectingRoi && roiStart && coords) {
      const x1 = Math.min(roiStart.x, coords.x);
      const y1 = Math.min(roiStart.y, coords.y);
      const x2 = Math.max(roiStart.x, coords.x);
      const y2 = Math.max(roiStart.y, coords.y);
      setCurrentRoi([x1, y1, Math.max(1, x2 - x1), Math.max(1, y2 - y1)]);
    }

    // Sample color
    if (coords && imageRef.current && colorCanvasRef.current) {
      const ctx = colorCanvasRef.current.getContext('2d');
      if (ctx) {
        try {
          const pixel = ctx.getImageData(coords.x, coords.y, 1, 1).data;
          setSampledColor(
            `#${pixel[0].toString(16).padStart(2, '0')}${pixel[1]
              .toString(16)
              .padStart(2, '0')}${pixel[2].toString(16).padStart(2, '0')}`.toUpperCase()
          );
        } catch {
          // Cross-origin or tainted canvas
        }
      }
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    // Middle click or Space held or Hand tool -> Pan
    if (e.button === 1 || activeTool === 'hand' || e.spaceKey) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      return;
    }

    if (e.button === 0) {
      const coords = clientToImageCoords(e.clientX, e.clientY);
      if (!coords) return;

      if (activeTool === 'touch') {
        onTouchTap(coords.x, coords.y);
      } else if (activeTool === 'roi') {
        setIsSelectingRoi(true);
        setRoiStart({ x: coords.x, y: coords.y });
        setCurrentRoi([coords.x, coords.y, 1, 1]);
      }
    }
  };

  const handleMouseUp = () => {
    if (isPanning) {
      setIsPanning(false);
    }
    if (isSelectingRoi) {
      setIsSelectingRoi(false);
      if (currentRoi && currentRoi[2] > 5 && currentRoi[3] > 5) {
        onRoiSelected(currentRoi);
      }
      setCurrentRoi(null);
      setRoiStart(null);
    }
  };

  // Sync image to color canvas for fast pixel inspection
  React.useEffect(() => {
    if (!imageSrc) return;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const cvs = document.createElement('canvas');
      cvs.width = img.width;
      cvs.height = img.height;
      const ctx = cvs.getContext('2d');
      if (ctx) {
        ctx.drawImage(img, 0, 0);
        colorCanvasRef.current = cvs;
      }
    };
    img.src = imageSrc;
  }, [imageSrc]);

  const activeRoi = currentRoi || (activeLocator?.roi ? activeLocator.roi : null);

  return (
    <div className={`relative flex flex-col h-full bg-slate-950 overflow-hidden ${className || ''}`}>
      {/* Top Floating Toolbar */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 flex items-center bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-lg p-1 shadow-xl space-x-1">
        {/* Tool selector */}
        <div className="flex items-center space-x-0.5 border-r border-slate-800 pr-1 mr-1">
          <Button
            size="sm"
            variant={activeTool === 'roi' ? 'secondary' : 'ghost'}
            onClick={() => setActiveTool('roi')}
            className={`h-7 px-2 text-xs ${activeTool === 'roi' ? 'bg-sky-500/20 text-sky-300 font-semibold' : 'text-slate-400'}`}
            title="选择 ROI (拖拽框选定位符范围)"
          >
            <Crop className="w-3.5 h-3.5 mr-1" />
            <span>框选 ROI</span>
          </Button>
          <Button
            size="sm"
            variant={activeTool === 'touch' ? 'secondary' : 'ghost'}
            onClick={() => setActiveTool('touch')}
            className={`h-7 px-2 text-xs ${activeTool === 'touch' ? 'bg-sky-500/20 text-sky-300 font-semibold' : 'text-slate-400'}`}
            title="点击屏幕 (向设备发送 ADB 触控)"
          >
            <MousePointer className="w-3.5 h-3.5 mr-1" />
            <span>触控调试</span>
          </Button>
          <Button
            size="sm"
            variant={activeTool === 'hand' ? 'secondary' : 'ghost'}
            onClick={() => setActiveTool('hand')}
            className={`h-7 px-2 text-xs ${activeTool === 'hand' ? 'bg-sky-500/20 text-sky-300 font-semibold' : 'text-slate-400'}`}
            title="平移画布 (也可按住空格或中键拖拽)"
          >
            <Hand className="w-3.5 h-3.5 mr-1" />
            <span>平移</span>
          </Button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setScale((s) => Math.min(s * 1.25, 10))}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800"
            title="放大"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] font-mono font-medium text-slate-300 min-w-[42px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={() => setScale((s) => Math.max(s / 1.25, 0.05))}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800"
            title="缩小"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={fitToScreen}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800"
            title="适应窗口"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => {
              setScale(1);
              if (containerRef.current && imageDimensions.width) {
                setPan({
                  x: (containerRef.current.clientWidth - imageDimensions.width) / 2,
                  y: (containerRef.current.clientHeight - imageDimensions.height) / 2,
                });
              }
            }}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 text-[10px] font-mono px-1.5"
            title="100% 原始比例"
          >
            1:1
          </button>
        </div>

        <div className="w-px h-4 bg-slate-800" />

        {/* Magnifier Toggle */}
        <button
          onClick={() => setShowMagnifier(!showMagnifier)}
          className={`p-1 rounded transition-colors ${
            showMagnifier ? 'text-sky-400 bg-sky-500/10' : 'text-slate-500 hover:text-slate-300'
          }`}
          title="开关放大镜悬浮窗"
        >
          {showMagnifier ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Main Interactive Canvas Area */}
      <div
        id="screenCanvas"
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          setCursorPos(null);
          setIsPanning(false);
          setIsSelectingRoi(false);
        }}
        className={`flex-1 relative overflow-hidden select-none ${
          isPanning || activeTool === 'hand'
            ? 'cursor-grab active:cursor-grabbing'
            : activeTool === 'touch'
            ? 'cursor-pointer'
            : 'cursor-crosshair'
        }`}
        style={{
          backgroundImage:
            'radial-gradient(circle, rgba(51, 65, 85, 0.25) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      >
        {imageSrc ? (
          <div
            className="absolute top-0 left-0 origin-top-left transition-transform duration-75"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
            }}
          >
            {/* Base Screenshot Image */}
            <img
              ref={imageRef}
              src={imageSrc}
              alt="Screen"
              draggable={false}
              className="max-w-none shadow-2xl rounded-xs select-none pointer-events-none"
              style={{
                width: imageDimensions.width,
                height: imageDimensions.height,
              }}
            />

            {/* Inactive Locators Outlines (subtle indicators) */}
            {allLocators.map((loc, idx) => {
              if (!loc.roi || loc === activeLocator) return null;
              const [rx, ry, rw, rh] = loc.roi;
              return (
                <div
                  key={loc.name + idx}
                  className="absolute border border-slate-400/40 bg-slate-500/10 pointer-events-none rounded-xs"
                  style={{
                    left: `${rx}px`,
                    top: `${ry}px`,
                    width: `${rw}px`,
                    height: `${rh}px`,
                  }}
                >
                  <span className="absolute -top-4 left-0 text-[10px] bg-slate-900/80 px-1 rounded text-slate-400 font-mono">
                    {loc.name}
                  </span>
                </div>
              );
            })}

            {/* Active Locator ROI Box */}
            {activeRoi && (
              <div
                className="absolute border-2 border-sky-400 bg-sky-500/15 pointer-events-none rounded-xs shadow-[0_0_12px_rgba(56,189,248,0.4)]"
                style={{
                  left: `${activeRoi[0]}px`,
                  top: `${activeRoi[1]}px`,
                  width: `${activeRoi[2]}px`,
                  height: `${activeRoi[3]}px`,
                }}
              >
                {/* ROI label */}
                <div className="absolute -top-6 left-0 flex items-center space-x-1.5 bg-sky-950/90 border border-sky-500/60 px-1.5 py-0.5 rounded text-[11px] font-mono text-sky-200 shadow-md">
                  <span>ROI: {activeRoi[0]}, {activeRoi[1]} ({activeRoi[2]}×{activeRoi[3]})</span>
                </div>
              </div>
            )}

            {/* Recognition Result Overlay */}
            {recognitionResult && recognitionResult.box && (
              <div
                className={`absolute border-2 pointer-events-none rounded-xs animate-in fade-in zoom-in-95 duration-200 ${
                  recognitionResult.hit
                    ? 'border-emerald-400 bg-emerald-500/20 shadow-[0_0_16px_rgba(52,211,153,0.5)]'
                    : 'border-rose-400 bg-rose-500/20'
                }`}
                style={{
                  left: `${recognitionResult.box[0]}px`,
                  top: `${recognitionResult.box[1]}px`,
                  width: `${recognitionResult.box[2]}px`,
                  height: `${recognitionResult.box[3]}px`,
                }}
              >
                <div
                  className={`absolute -bottom-6 left-0 px-2 py-0.5 rounded text-[10px] font-mono font-bold shadow-md ${
                    recognitionResult.hit
                      ? 'bg-emerald-950/95 border border-emerald-500 text-emerald-300'
                      : 'bg-rose-950/95 border border-rose-500 text-rose-300'
                  }`}
                >
                  {recognitionResult.hit ? 'HIT' : 'MISS'} (
                  {recognitionResult.score !== null && recognitionResult.score !== undefined
                    ? `${(recognitionResult.score * 100).toFixed(1)}%`
                    : 'Matched'}
                  {recognitionResult.elapsed_ms !== undefined && ` · ${recognitionResult.elapsed_ms.toFixed(0)}ms`}
                  )
                </div>
              </div>
            )}

            {/* Multi-Recognition Boxes (Class Backtest Review Mode) */}
            {multiRecognitionBoxes &&
              multiRecognitionBoxes.map((boxItem, idx) => {
                if (!boxItem.box) return null;
                const [bx, by, bw, bh] = boxItem.box;
                return (
                  <div
                    key={boxItem.name + idx}
                    className={`absolute border-2 pointer-events-none rounded-xs ${
                      boxItem.hit
                        ? 'border-emerald-400 bg-emerald-500/15 shadow-[0_0_12px_rgba(52,211,153,0.4)]'
                        : 'border-rose-400 bg-rose-500/20'
                    }`}
                    style={{
                      left: `${bx}px`,
                      top: `${by}px`,
                      width: `${bw}px`,
                      height: `${bh}px`,
                    }}
                  >
                    <div
                      className={`absolute -top-5 left-0 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold shadow-md ${
                        boxItem.hit
                          ? 'bg-emerald-950/90 border border-emerald-500/80 text-emerald-300'
                          : 'bg-rose-950/90 border border-rose-500/80 text-rose-300'
                      }`}
                    >
                      {boxItem.name}: {boxItem.hit ? 'HIT' : 'MISS'}{' '}
                      {boxItem.score ? `${(boxItem.score * 100).toFixed(0)}%` : ''}
                    </div>
                  </div>
                );
              })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-3">
            <Scan className="w-12 h-12 text-slate-700 animate-pulse" />
            <p className="text-sm font-medium">尚未获取设备屏幕画面</p>
            <p className="text-xs text-slate-600">
              请点击右上角「截图 (R)」或导入本地截图
            </p>
          </div>
        )}

        {/* Floating Magnifier Window (Loupe) */}
        {showMagnifier && cursorPos && canvasCursorPos && imageSrc && (
          <div
            className="absolute z-30 pointer-events-none rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-2xl backdrop-blur-md"
            style={{
              left: `${Math.min(
                Math.max(16, canvasCursorPos.x + 20),
                (containerRef.current?.clientWidth || 800) - 170
              )}px`,
              top: `${Math.min(
                Math.max(16, canvasCursorPos.y + 20),
                (containerRef.current?.clientHeight || 600) - 170
              )}px`,
            }}
          >
            {/* Loupe Canvas Simulation */}
            <div className="w-32 h-32 relative overflow-hidden rounded border border-slate-800 bg-black">
              {colorCanvasRef.current && (
                <canvas
                  id="loupeCanvas"
                  width={128}
                  height={128}
                  ref={(node) => {
                    if (node && colorCanvasRef.current && cursorPos) {
                      const ctx = node.getContext('2d');
                      if (ctx) {
                        ctx.imageSmoothingEnabled = false;
                        ctx.clearRect(0, 0, 128, 128);
                        // Draw 9x9 zoomed pixel area
                        const size = 9;
                        const half = Math.floor(size / 2);
                        ctx.drawImage(
                          colorCanvasRef.current,
                          cursorPos.x - half,
                          cursorPos.y - half,
                          size,
                          size,
                          0,
                          0,
                          128,
                          128
                        );
                        // Center crosshair
                        ctx.strokeStyle = '#38bdf8';
                        ctx.lineWidth = 1;
                        ctx.strokeRect(56, 56, 16, 16);
                      }
                    }
                  }}
                  className="w-full h-full"
                />
              )}
            </div>

            {/* Coordinates & Color Data */}
            <div className="mt-1.5 space-y-0.5 text-[10px] font-mono">
              <div className="flex items-center justify-between text-slate-300">
                <span className="text-slate-500">坐标:</span>
                <span className="font-bold text-sky-400">
                  {cursorPos.x}, {cursorPos.y}
                </span>
              </div>
              {sampledColor && (
                <div className="flex items-center justify-between text-slate-300">
                  <span className="text-slate-500">颜色:</span>
                  <div className="flex items-center space-x-1">
                    <span
                      className="w-2.5 h-2.5 rounded-full border border-slate-600 inline-block"
                      style={{ backgroundColor: sampledColor }}
                    />
                    <span className="text-slate-200">{sampledColor}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Bottom Bar: Image info & Cursor position */}
        <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between pointer-events-none text-[11px] text-slate-400 font-mono">
          {activeScreenshotName ? (
            <div className="flex items-center space-x-2 bg-emerald-950/90 border border-emerald-500/50 px-2.5 py-1 rounded text-emerald-300 pointer-events-auto shadow-lg">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>当前样本: {activeScreenshotName}</span>
              {onReturnToLive && (
                <button
                  onClick={onReturnToLive}
                  className="ml-1 px-1.5 py-0.2 bg-emerald-900/60 hover:bg-emerald-800 rounded text-[10px] text-emerald-200 border border-emerald-500/30 transition-colors cursor-pointer"
                >
                  返回实时
                </button>
              )}
            </div>
          ) : (
            <div className="bg-slate-900/80 px-2 py-1 rounded border border-slate-800">
              {imageDimensions.width > 0 ? (
                <span>
                  分辨率: {imageDimensions.width} × {imageDimensions.height}
                </span>
              ) : (
                <span>未就绪</span>
              )}
            </div>
          )}
          {cursorPos && (
            <div className="bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800 text-sky-400 font-semibold">
              X: {cursorPos.x} | Y: {cursorPos.y}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
