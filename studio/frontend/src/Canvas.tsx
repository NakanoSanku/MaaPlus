import { useEffect, useRef, useState } from 'react';
import type { Rect, Snapshot } from './types';

export function screenToImage(x: number, y: number, camera: { x: number; y: number; zoom: number }) {
  return [(x - camera.x) / camera.zoom, (y - camera.y) / camera.zoom];
}
export function selectionRect(start: number[], end: number[], width: number, height: number): Rect {
  const left = Math.max(0, Math.min(width, Math.floor(Math.min(start[0], end[0]))));
  const top = Math.max(0, Math.min(height, Math.floor(Math.min(start[1], end[1]))));
  const right = Math.max(left, Math.min(width, Math.ceil(Math.max(start[0], end[0]))));
  const bottom = Math.max(top, Math.min(height, Math.ceil(Math.max(start[1], end[1]))));
  return [left, top, right - left, bottom - top];
}

interface Props { url: string; shot: Snapshot | null; rect: Rect | null; match: Rect | null; mode: 'roi' | 'crop' | 'pan'; onRect: (r: Rect) => void }
export function ImageCanvas({ url, shot, rect, match, mode, onRect }: Props) {
  const host = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const image = useRef<HTMLImageElement | null>(null), pixels = useRef<ImageData | null>(null);
  const [camera, setCamera] = useState({ x: 0, y: 0, zoom: 1 });
  const cameraRef = useRef(camera); cameraRef.current = camera;
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [pixel, setPixel] = useState('移动指针查看坐标和颜色');
  const [loaded, setLoaded] = useState(0);
  const drag = useRef<{ point: number[]; camera: typeof camera; pan: boolean } | null>(null);
  const space = useRef(false);

  function fit() {
    const bounds = host.current?.getBoundingClientRect();
    if (!bounds || !image.current) return;
    const zoom = Math.min((bounds.width - 64) / image.current.width, (bounds.height - 64) / image.current.height, 1);
    setCamera({ zoom: Math.max(zoom, 0.02), x: (bounds.width - image.current.width * zoom) / 2, y: (bounds.height - image.current.height * zoom) / 2 });
  }
  function zoomTo(value: number) {
    const bounds = host.current?.getBoundingClientRect();
    if (!bounds || !image.current) return;
    const zoom = Math.max(0.02, Math.min(16, value));
    const [x, y] = screenToImage(bounds.width / 2, bounds.height / 2, cameraRef.current);
    setCamera({ zoom, x: bounds.width / 2 - x * zoom, y: bounds.height / 2 - y * zoom });
  }
  useEffect(() => {
    let previous: { width: number; height: number } | null = null;
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (previous) {
        const dx = (width - previous.width) / 2, dy = (height - previous.height) / 2;
        setCamera(current => ({ ...current, x: current.x + dx, y: current.y + dy }));
      }
      previous = { width, height };
      setSize(previous);
    });
    if (host.current) observer.observe(host.current);
    const down = (event: KeyboardEvent) => { if (event.code === 'Space' && event.target === canvas.current) { space.current = true; event.preventDefault(); } };
    const up = () => { space.current = false; };
    window.addEventListener('keydown', down); window.addEventListener('keyup', up); window.addEventListener('blur', up);
    return () => { observer.disconnect(); window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('blur', up); };
  }, []);
  useEffect(() => {
    image.current = null; pixels.current = null;
    if (!url) { setLoaded(v => v + 1); return; }
    let active = true;
    const img = new Image();
    img.onload = () => {
      if (!active) return;
      image.current = img;
      const offscreen = document.createElement('canvas'); offscreen.width = img.width; offscreen.height = img.height;
      const ctx = offscreen.getContext('2d')!; ctx.drawImage(img, 0, 0); pixels.current = ctx.getImageData(0, 0, img.width, img.height);
      fit(); setLoaded(v => v + 1);
    };
    img.src = url;
    return () => { active = false; };
  }, [url]);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    function wheel(event: WheelEvent) {
      event.preventDefault();
      const bounds = element!.getBoundingClientRect(), current = cameraRef.current;
      const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
      const [ix, iy] = screenToImage(x, y, current);
      const zoom = Math.max(0.02, Math.min(16, current.zoom * Math.exp(-event.deltaY * 0.001)));
      setCamera({ zoom, x: x - ix * zoom, y: y - iy * zoom });
    }
    element.addEventListener('wheel', wheel, { passive: false });
    return () => element.removeEventListener('wheel', wheel);
  }, []);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const dpr = window.devicePixelRatio || 1;
    element.width = Math.round(size.width * dpr); element.height = Math.round(size.height * dpr);
    const ctx = element.getContext('2d')!; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, size.width, size.height);
    if (!image.current) return;
    ctx.save(); ctx.translate(camera.x, camera.y); ctx.scale(camera.zoom, camera.zoom); ctx.imageSmoothingEnabled = camera.zoom < 1;
    ctx.drawImage(image.current, 0, 0);
    function box(value: Rect | null, color: string, label: string) {
      if (!value || value[2] <= 0 || value[3] <= 0) return;
      const [x, y, w, h] = value;
      ctx.lineWidth = 1.5 / camera.zoom; ctx.strokeStyle = color; ctx.fillStyle = color + '18'; ctx.fillRect(x, y, w, h); ctx.strokeRect(x, y, w, h);
      ctx.font = `${11 / camera.zoom}px monospace`; ctx.fillStyle = color; ctx.fillText(label, x + 4 / camera.zoom, Math.max(12 / camera.zoom, y - 5 / camera.zoom));
      for (const [hx, hy] of [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]) ctx.fillRect(hx - 2 / camera.zoom, hy - 2 / camera.zoom, 4 / camera.zoom, 4 / camera.zoom);
    }
    box(rect, '#63d9de', `${mode === 'crop' ? 'CROP' : 'ROI'}  ${rect?.join(', ')}`); box(match, '#92dd78', 'MATCH');
    ctx.restore();
  }, [camera, size, rect, match, loaded, mode]);

  function position(event: React.PointerEvent) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return [event.clientX - bounds.left, event.clientY - bounds.top];
  }
  return <div className="image-workspace">
    <div ref={host} className="canvas-host">
      <canvas ref={canvas} aria-label="截图编辑画布" tabIndex={0} className={mode === 'pan' ? 'pan' : 'crosshair'}
        onPointerDown={event => {
          if (!image.current || ![0, 1].includes(event.button)) return;
          event.currentTarget.focus(); event.currentTarget.setPointerCapture(event.pointerId);
          const point = position(event), pan = mode === 'pan' || space.current || event.button === 1;
          drag.current = { point: pan ? point : screenToImage(point[0], point[1], camera), camera, pan };
        }}
        onPointerMove={event => {
          if (!image.current) return;
          const point = position(event), coords = screenToImage(point[0], point[1], camera);
          const x = Math.floor(coords[0]), y = Math.floor(coords[1]), source = pixels.current;
          if (source && x >= 0 && y >= 0 && x < source.width && y < source.height) {
            const offset = (y * source.width + x) * 4, rgb = Array.from(source.data.slice(offset, offset + 3));
            setPixel(`X ${x}   Y ${y}     RGB ${rgb.join(', ')}     #${rgb.map(v => v.toString(16).padStart(2, '0')).join('')}`);
          }
          if (!drag.current) return;
          if (drag.current.pan) setCamera({ ...drag.current.camera, x: drag.current.camera.x + point[0] - drag.current.point[0], y: drag.current.camera.y + point[1] - drag.current.point[1] });
          else onRect(selectionRect(drag.current.point, coords, image.current.width, image.current.height));
        }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} />
      {!shot && <div className="canvas-empty"><div className="frame-symbol">⌗</div><h2>从一张截图开始</h2><p>连接设备采集画面，或导入、粘贴一张截图</p><span>拖入图片 · Ctrl + V 粘贴</span></div>}
      {shot && <div className="zoom-tools"><button onClick={fit}>适应画布</button><button onClick={() => zoomTo(1)}>1:1</button><button aria-label="缩小画布" disabled={!image.current} onClick={() => zoomTo(camera.zoom / 2)}>−</button><span>{Math.round(camera.zoom * 100)}%</span><button aria-label="放大画布" disabled={!image.current} onClick={() => zoomTo(camera.zoom * 2)}>＋</button></div>}
    </div>
    <div className="canvas-status"><span>{pixel}</span><span>{shot ? `${shot.width} × ${shot.height} px` : '等待截图'}　·　滚轮缩放 / 空格拖动</span></div>
  </div>;
}
