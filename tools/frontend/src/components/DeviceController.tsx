import * as React from 'react';
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Home,
  Menu,
  MousePointer,
  Move,
  Smartphone,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';

interface DeviceControllerProps {
  connectedDevice: string | null;
  onSendKey: (keycode: number) => void;
  onSendTap: (x: number, y: number) => void;
  onSendSwipe: (x1: number, y1: number, x2: number, y2: number, duration?: number) => void;
}

export function DeviceController({ connectedDevice, onSendKey, onSendTap, onSendSwipe }: DeviceControllerProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [tapX, setTapX] = React.useState('500');
  const [tapY, setTapY] = React.useState('500');
  const [swipeX1, setSwipeX1] = React.useState('300');
  const [swipeY1, setSwipeY1] = React.useState('800');
  const [swipeX2, setSwipeX2] = React.useState('300');
  const [swipeY2, setSwipeY2] = React.useState('200');
  const [swipeDuration, setSwipeDuration] = React.useState('400');
  const liveInput = Boolean(connectedDevice && connectedDevice !== 'offline');

  const handleTap = () => {
    const x = Number.parseInt(tapX);
    const y = Number.parseInt(tapY);
    if (Number.isFinite(x) && Number.isFinite(y)) onSendTap(x, y);
  };

  const handleSwipe = () => {
    const x1 = Number.parseInt(swipeX1);
    const y1 = Number.parseInt(swipeY1);
    const x2 = Number.parseInt(swipeX2);
    const y2 = Number.parseInt(swipeY2);
    const duration = Number.parseInt(swipeDuration) || 400;
    if ([x1, y1, x2, y2].every(Number.isFinite)) onSendSwipe(x1, y1, x2, y2, duration);
  };

  return (
    <div className="shrink-0 border-t border-[#ecece8] bg-white px-3 py-2 select-none">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1.5">
          <div className="mr-1 flex items-center gap-1.5 whitespace-nowrap text-[9px] font-semibold text-[#77776f]">
            <Smartphone className="h-3.5 w-3.5" />
            <span>{liveInput ? '设备按键' : '未连接设备'}</span>
          </div>
          <Button size="sm" variant="outline" disabled={!liveInput} onClick={() => onSendKey(4)} className="h-7 px-2 text-[10px]" title="Android 返回键 · KeyCode 4">
            <ArrowLeft className="h-3.5 w-3.5" />返回
          </Button>
          <Button size="sm" variant="outline" disabled={!liveInput} onClick={() => onSendKey(3)} className="h-7 px-2 text-[10px]" title="Android 主页键 · KeyCode 3">
            <Home className="h-3.5 w-3.5" />主页
          </Button>
          <Button size="sm" variant="outline" disabled={!liveInput} onClick={() => onSendKey(187)} className="h-7 px-2 text-[10px]" title="Android 最近任务 · KeyCode 187">
            <Menu className="h-3.5 w-3.5" />最近任务
          </Button>
        </div>

        <button
          onClick={() => setIsExpanded((value) => !value)}
          className="flex shrink-0 items-center gap-1 whitespace-nowrap text-[9px] font-medium text-[#7d7d76] hover:text-[#2e2e2b]"
        >
          精确输入
          {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-2 grid grid-cols-2 gap-3 border-t border-[#eeeeea] pt-2">
          <div className="flex items-center gap-1.5">
            <span className="mr-1 whitespace-nowrap text-[9px] font-medium text-[#77776f]">点击坐标</span>
            <Input value={tapX} onChange={(event) => setTapX(event.target.value)} placeholder="X" className="h-7 w-16 px-1 text-center font-mono text-[9px]" />
            <Input value={tapY} onChange={(event) => setTapY(event.target.value)} placeholder="Y" className="h-7 w-16 px-1 text-center font-mono text-[9px]" />
            <Button size="sm" disabled={!liveInput} onClick={handleTap} className="h-7 px-2 text-[9px]">
              <MousePointer className="h-3 w-3" />发送
            </Button>
          </div>

          <div className="flex items-center justify-end gap-1.5">
            <span className="mr-1 whitespace-nowrap text-[9px] font-medium text-[#77776f]">滑动</span>
            <Input value={swipeX1} onChange={(event) => setSwipeX1(event.target.value)} placeholder="X1" className="h-7 w-12 px-1 text-center font-mono text-[9px]" />
            <Input value={swipeY1} onChange={(event) => setSwipeY1(event.target.value)} placeholder="Y1" className="h-7 w-12 px-1 text-center font-mono text-[9px]" />
            <span className="text-[9px] text-[#aaa9a2]">→</span>
            <Input value={swipeX2} onChange={(event) => setSwipeX2(event.target.value)} placeholder="X2" className="h-7 w-12 px-1 text-center font-mono text-[9px]" />
            <Input value={swipeY2} onChange={(event) => setSwipeY2(event.target.value)} placeholder="Y2" className="h-7 w-12 px-1 text-center font-mono text-[9px]" />
            <Input value={swipeDuration} onChange={(event) => setSwipeDuration(event.target.value)} placeholder="ms" className="h-7 w-14 px-1 text-center font-mono text-[9px]" />
            <Button size="sm" disabled={!liveInput} onClick={handleSwipe} className="h-7 px-2 text-[9px]">
              <Move className="h-3 w-3" />发送
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
