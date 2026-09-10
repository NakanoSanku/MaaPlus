import * as React from 'react';
import {
  Camera,
  Code2,
  FlaskConical,
  FolderOpen,
  Image as ImageIcon,
  Layers3,
  MonitorDot,
  Plug,
  RefreshCw,
  Radio,
  Smartphone,
  Unplug,
} from 'lucide-react';
import { Button } from './ui/button';
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

const tabs = [
  { id: 'canvas', label: '定位工作台', short: '定位', description: 'Capture & locate', icon: Layers3 },
  { id: 'backtest', label: 'Regression Lab', short: '回归', description: 'Test & triage', icon: FlaskConical },
  { id: 'code', label: 'Code Studio', short: '代码', description: 'Review & ship', icon: Code2 },
];

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

  return (
    <header className="h-[68px] shrink-0 border-b border-white/8 bg-[#0c0f14]/95 backdrop-blur-xl px-4 grid grid-cols-[minmax(230px,1fr)_auto_minmax(420px,1fr)] items-center gap-4 z-30 select-none">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-9 h-9 rounded-xl border border-violet-400/20 bg-violet-400/10 flex items-center justify-center shadow-[0_8px_30px_rgba(139,92,246,0.08)]">
          <MonitorDot className="w-5 h-5 text-violet-300" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-tight text-slate-100">MaaPlus</span>
            <span className="text-xs text-slate-500">UI Workbench</span>
            <span className="rounded-md border border-white/8 bg-white/[0.03] px-1.5 py-0.5 text-[9px] font-mono text-slate-500">v2</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5 text-[10px] text-slate-600">
            <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            {backendOnline ? 'backend online' : 'offline workspace'}
            {connectedDevice && <><span>·</span><span className="truncate max-w-[140px]">{connectedDevice === 'offline' ? 'offline device mode' : connectedDevice}</span></>}
          </div>
        </div>
      </div>

      <nav className="flex items-center rounded-xl border border-white/8 bg-black/20 p-1 shadow-inner">
        {tabs.map((tab, index) => {
          const Icon = tab.icon;
          const active = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`group min-w-[132px] rounded-lg px-3 py-1.5 flex items-center gap-2.5 text-left transition-all ${active ? 'bg-white/[0.08] shadow-sm text-slate-100' : 'text-slate-500 hover:bg-white/[0.035] hover:text-slate-300'}`}
            >
              <span className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-mono border ${active ? 'border-violet-400/25 bg-violet-400/10 text-violet-300' : 'border-white/6 bg-black/20 text-slate-600'}`}>
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-[11px] font-medium truncate">{tab.label}</span>
                <span className="hidden 2xl:block text-[9px] text-slate-600 group-hover:text-slate-500 truncate">{tab.description}</span>
              </span>
              <Icon className={`w-3.5 h-3.5 ml-auto ${active ? 'text-violet-300' : 'text-slate-700'}`} />
            </button>
          );
        })}
      </nav>

      <div className="justify-self-end flex items-center gap-2 min-w-0">
        <div className="hidden xl:flex items-center rounded-lg border border-white/8 bg-black/20 h-8">
          <Smartphone className="w-3.5 h-3.5 ml-2.5 text-slate-600" />
          <select
            value={selectedDevice}
            onChange={(e) => onSelectDevice(e.target.value)}
            className="bg-transparent outline-none text-[11px] text-slate-300 pl-2 pr-1 max-w-[150px] h-full"
            title="选择设备"
          >
            <option value="offline" className="bg-[#10131a]">离线模式</option>
            {devices.map((device) => (
              <option key={device.address} value={device.address} className="bg-[#10131a]">{device.name || device.address}</option>
            ))}
          </select>
          <button onClick={onRefreshDevices} className="h-full px-2 text-slate-600 hover:text-slate-300" title="重新扫描设备">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {connectedDevice ? (
          <Button id="btnConnectDevice" variant="ghost" size="sm" onClick={onDisconnectDevice} className="h-8 px-2.5 text-[11px] text-rose-300 hover:bg-rose-400/10">
            <Unplug className="w-3.5 h-3.5 mr-1" />断开
          </Button>
        ) : (
          <Button id="btnConnectDevice" variant="outline" size="sm" onClick={onConnectDevice} className="h-8 px-2.5 text-[11px] border-white/10 text-slate-300 hover:bg-white/5">
            <Plug className="w-3.5 h-3.5 mr-1" />连接
          </Button>
        )}

        <div className="w-px h-5 bg-white/8" />

        <Button
          id="btnTakeScreenshot"
          size="sm"
          onClick={onCaptureScreenshot}
          disabled={isCapturing}
          className="h-8 px-3 text-[11px] bg-violet-500 hover:bg-violet-400 text-white"
          title="截图（R）"
        >
          <Camera className={`w-3.5 h-3.5 mr-1.5 ${isCapturing ? 'animate-spin' : ''}`} />截图
          <kbd className="ml-1.5 rounded border border-white/20 px-1 text-[9px] opacity-70">R</kbd>
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={onToggleLiveMonitor}
          className={`h-8 px-2.5 text-[11px] ${liveMonitor ? 'text-emerald-300 bg-emerald-400/10' : 'text-slate-500'}`}
          title="实时预览"
        >
          <Radio className={`w-3.5 h-3.5 mr-1 ${liveMonitor ? 'animate-pulse' : ''}`} />{liveMonitor ? '实时' : '预览'}
        </Button>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onOpenLocalImage(file);
            e.target.value = '';
          }}
        />
        <Button variant="ghost" size="sm" onClick={() => fileInputRef.current?.click()} className="h-8 px-2.5 text-[11px] text-slate-500" title="导入本地截图">
          <FolderOpen className="w-3.5 h-3.5 mr-1" /><span className="hidden 2xl:inline">导入</span><ImageIcon className="w-3 h-3 ml-1 2xl:hidden" />
        </Button>
      </div>
    </header>
  );
}
