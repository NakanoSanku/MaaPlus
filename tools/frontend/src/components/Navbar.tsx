import * as React from 'react';
import {
  Camera,
  RefreshCw,
  Smartphone,
  CheckCircle2,
  XCircle,
  FolderOpen,
  Layers,
  CheckSquare,
  Code,
  Radio,
  Play,
  Square,
  Cpu,
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Device } from '../types';

interface NavbarProps {
  backendOnline: boolean;
  devices: Device[];
  selectedDevice: string;
  onSelectDevice: (address: string) => void;
  onRefreshDevices: () => void;
  connectedDevice: string | null;
  onConnectDevice: () => void;
  onDisconnectDevice: () => void;
  onCaptureScreenshot: () => void;
  isCapturing: boolean;
  liveMonitor: boolean;
  onToggleLiveMonitor: () => void;
  onOpenLocalImage: (file: File) => void;
  currentTab: string;
  onTabChange: (tab: string) => void;
}

export function Navbar({
  backendOnline,
  devices,
  selectedDevice,
  onSelectDevice,
  onRefreshDevices,
  connectedDevice,
  onConnectDevice,
  onDisconnectDevice,
  onCaptureScreenshot,
  isCapturing,
  liveMonitor,
  onToggleLiveMonitor,
  onOpenLocalImage,
  currentTab,
  onTabChange,
}: NavbarProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onOpenLocalImage(e.target.files[0]);
    }
  };

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md px-4 flex items-center justify-between z-30 shrink-0 select-none">
      {/* Left: Brand & Main Navigation */}
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-950/50">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm tracking-tight bg-gradient-to-r from-sky-400 via-sky-200 to-slate-200 bg-clip-text text-transparent">
                MaaPlus
              </span>
              <span className="text-xs font-semibold text-slate-300">UI Workbench</span>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-sky-500/30 text-sky-400 bg-sky-500/10">
                v1.4
              </Badge>
            </div>
            <div className="flex items-center space-x-1.5 text-[10px] text-slate-500">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  backendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                }`}
              />
              <span>{backendOnline ? 'FastAPI 后端在线' : '后端未连接'}</span>
            </div>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <nav className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
          <button
            onClick={() => onTabChange('canvas')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              currentTab === 'canvas'
                ? 'bg-slate-800 text-sky-400 shadow-xs border border-slate-700/60 font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>画布与定位</span>
          </button>
          <button
            onClick={() => onTabChange('backtest')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              currentTab === 'backtest'
                ? 'bg-slate-800 text-sky-400 shadow-xs border border-slate-700/60 font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>UI 类回测</span>
          </button>
          <button
            onClick={() => onTabChange('code')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              currentTab === 'code'
                ? 'bg-slate-800 text-sky-400 shadow-xs border border-slate-700/60 font-semibold'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            <span>代码生成</span>
          </button>
        </nav>
      </div>

      {/* Right: Device & Capture Controls */}
      <div className="flex items-center space-x-2.5">
        {/* Device Select */}
        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
          <Smartphone className="w-4 h-4 ml-2.5 text-slate-400 shrink-0" />
          <select
            value={selectedDevice}
            onChange={(e) => onSelectDevice(e.target.value)}
            className="bg-transparent text-xs text-slate-200 px-2 py-1.5 focus:outline-none cursor-pointer max-w-[170px] truncate"
            title="选择要连接的设备或离线模拟器"
          >
            <option value="offline" className="bg-slate-900 text-slate-300">
              离线模式 (Offline)
            </option>
            {devices.map((d) => (
              <option key={d.address} value={d.address} className="bg-slate-900 text-slate-300">
                {d.name || d.address} ({d.source})
              </option>
            ))}
          </select>
          <button
            onClick={onRefreshDevices}
            className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-md transition-colors"
            title="扫描设备"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Connect / Disconnect */}
        {connectedDevice ? (
          <Button
            id="btnConnectDevice"
            size="sm"
            variant="outline"
            onClick={onDisconnectDevice}
            className="h-8 text-xs border-rose-500/40 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500/60"
          >
            <XCircle className="w-3.5 h-3.5 mr-1" />
            断开
          </Button>
        ) : (
          <Button
            id="btnConnectDevice"
            size="sm"
            onClick={onConnectDevice}
            className="h-8 text-xs bg-sky-600 hover:bg-sky-500 text-white shadow-xs"
          >
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
            连接设备
          </Button>
        )}

        <div className="w-px h-5 bg-slate-800 mx-1" />

        {/* Screenshot Button */}
        <Button
          id="btnTakeScreenshot"
          size="sm"
          variant="secondary"
          onClick={onCaptureScreenshot}
          disabled={isCapturing}
          className="h-8 text-xs font-medium"
          title="截取当前屏幕 (快捷键: R)"
        >
          <Camera className={`w-3.5 h-3.5 mr-1.5 ${isCapturing ? 'animate-spin' : ''}`} />
          <span>截图 (R)</span>
        </Button>

        {/* Live Monitor Toggle */}
        <Button
          size="sm"
          variant={liveMonitor ? 'default' : 'ghost'}
          onClick={onToggleLiveMonitor}
          className={`h-8 text-xs ${
            liveMonitor
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          title="实时刷新画面 (1秒轮询)"
        >
          <Radio className={`w-3.5 h-3.5 mr-1.5 ${liveMonitor ? 'animate-pulse' : ''}`} />
          <span>{liveMonitor ? '监听中' : '实时预览'}</span>
        </Button>

        {/* Open Local Image */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*"
          className="hidden"
        />
        <Button
          size="sm"
          variant="ghost"
          onClick={() => fileInputRef.current?.click()}
          className="h-8 text-xs text-slate-400 hover:text-slate-200"
          title="导入本地截图进行调试分析"
        >
          <FolderOpen className="w-3.5 h-3.5 mr-1.5" />
          <span>导入截图</span>
        </Button>
      </div>
    </header>
  );
}
