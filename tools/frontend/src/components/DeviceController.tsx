import * as React from 'react';
import {
  Smartphone,
  ArrowLeft,
  Home,
  Menu,
  Volume2,
  Volume1,
  Move,
  MousePointer,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';

interface DeviceControllerProps {
  connectedDevice: string | null;
  onSendKey: (keycode: number) => void;
  onSendTap: (x: number, y: number) => void;
  onSendSwipe: (x1: number, y1: number, x2: number, y2: number, duration?: number) => void;
}

export function DeviceController({
  connectedDevice,
  onSendKey,
  onSendTap,
  onSendSwipe,
}: DeviceControllerProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [tapX, setTapX] = React.useState('500');
  const [tapY, setTapY] = React.useState('500');

  const [swipeX1, setSwipeX1] = React.useState('300');
  const [swipeY1, setSwipeY1] = React.useState('800');
  const [swipeX2, setSwipeX2] = React.useState('300');
  const [swipeY2, setSwipeY2] = React.useState('200');
  const [swipeDuration, setSwipeDuration] = React.useState('400');

  const handleTap = () => {
    const x = parseInt(tapX);
    const y = parseInt(tapY);
    if (!isNaN(x) && !isNaN(y)) {
      onSendTap(x, y);
    }
  };

  const handleSwipe = () => {
    const x1 = parseInt(swipeX1);
    const y1 = parseInt(swipeY1);
    const x2 = parseInt(swipeX2);
    const y2 = parseInt(swipeY2);
    const d = parseInt(swipeDuration) || 400;
    if (!isNaN(x1) && !isNaN(y1) && !isNaN(x2) && !isNaN(y2)) {
      onSendSwipe(x1, y1, x2, y2, d);
    }
  };

  return (
    <div className="border-t border-slate-800 bg-slate-950/80 backdrop-blur-md px-4 py-2 select-none">
      <div className="flex items-center justify-between">
        {/* Hardware Keys Bar */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 mr-2 text-xs font-semibold text-slate-400">
            <Smartphone className="w-3.5 h-3.5 text-sky-400" />
            <span>按键控制:</span>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSendKey(4)}
            className="h-7 px-2.5 text-xs text-slate-300"
            title="返回键 (Back, KeyCode 4)"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            <span>返回 (Back)</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSendKey(3)}
            className="h-7 px-2.5 text-xs text-slate-300"
            title="主页键 (Home, KeyCode 3)"
          >
            <Home className="w-3.5 h-3.5 mr-1" />
            <span>桌面 (Home)</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSendKey(187)}
            className="h-7 px-2.5 text-xs text-slate-300"
            title="多任务菜单 (Recents/AppSwitch, KeyCode 187)"
          >
            <Menu className="w-3.5 h-3.5 mr-1" />
            <span>任务 (AppSwitch)</span>
          </Button>
        </div>

        {/* Toggle Expand Manual Input */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center space-x-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <span>精确坐标调试</span>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Expanded Manual Input Controls */}
      {isExpanded && (
        <div className="grid grid-cols-2 gap-4 mt-2.5 pt-2.5 border-t border-slate-800/80 text-xs">
          {/* Tap input */}
          <div className="flex items-center space-x-2">
            <span className="text-slate-400 font-medium">指定坐标点击:</span>
            <Input
              value={tapX}
              onChange={(e) => setTapX(e.target.value)}
              placeholder="X"
              className="w-16 h-7 text-xs font-mono text-center"
            />
            <Input
              value={tapY}
              onChange={(e) => setTapY(e.target.value)}
              placeholder="Y"
              className="w-16 h-7 text-xs font-mono text-center"
            />
            <Button size="sm" onClick={handleTap} className="h-7 text-xs bg-slate-800 hover:bg-slate-700">
              <MousePointer className="w-3 h-3 mr-1" />
              点击
            </Button>
          </div>

          {/* Swipe input */}
          <div className="flex items-center space-x-2">
            <span className="text-slate-400 font-medium">滑动:</span>
            <Input
              value={swipeX1}
              onChange={(e) => setSwipeX1(e.target.value)}
              placeholder="X1"
              className="w-14 h-7 text-xs font-mono text-center"
            />
            <Input
              value={swipeY1}
              onChange={(e) => setSwipeY1(e.target.value)}
              placeholder="Y1"
              className="w-14 h-7 text-xs font-mono text-center"
            />
            <span className="text-slate-500">→</span>
            <Input
              value={swipeX2}
              onChange={(e) => setSwipeX2(e.target.value)}
              placeholder="X2"
              className="w-14 h-7 text-xs font-mono text-center"
            />
            <Input
              value={swipeY2}
              onChange={(e) => setSwipeY2(e.target.value)}
              placeholder="Y2"
              className="w-14 h-7 text-xs font-mono text-center"
            />
            <Button size="sm" onClick={handleSwipe} className="h-7 text-xs bg-slate-800 hover:bg-slate-700">
              <Move className="w-3 h-3 mr-1" />
              滑动
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
