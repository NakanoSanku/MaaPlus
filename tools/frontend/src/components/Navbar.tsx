import * as React from 'react';
import {
  Camera,
  Code2,
  FlaskConical,
  FolderOpen,
  Layers3,
  MonitorDot,
  PencilLine,
  Plug,
  Radio,
  RefreshCw,
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
  { id: 'canvas', label: '定位', icon: Layers3 },
  { id: 'backtest', label: '回归', icon: FlaskConical },
  { id: 'code', label: '代码', icon: Code2 },
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
  const isKnownDevice = selectedDevice === 'offline' || devices.some((device) => device.address === selectedDevice);

  const handleManualDevice = () => {
    const current = selectedDevice && selectedDevice !== 'offline' ? selectedDevice : '127.0.0.1:5555';
    const value = window.prompt('输入 ADB 设备序列号或网络地址', current);
    if (value?.trim()) onSelectDevice(value.trim());
  };

  return (
    <header className="h-14 shrink-0 border-b border-[#e7e7e3] bg-white px-4 grid grid-cols-[minmax(210px,1fr)_auto_minmax(520px,1fr)] items-center gap-4 z-30 select-none">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-7 h-7 rounded-lg bg-[#1b1b1a] text-white flex items-center justify-center shadow-[0_1px_2px_rgba(0,0,0,0.12)]">
          <MonitorDot className="w-4 h-4" />
        </div>
        <div className="min-w-0 leading-tight">
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs font-semibold tracking-tight text-[#191918]">MaaPlus</span>
            <span className="text-[10px] text-[#8a8a83]">UI Workbench</span>
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[9px] text-[#999991] whitespace-nowrap">
            <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-emerald-500' : 'bg-[#c4c4be]'}`} />
            <span>{backendOnline ? '后端已连接' : '离线工作区'}</span>
            {connectedDevice && (
              <>
                <span>·</span>
                <span className="truncate max-w-[130px]">{connectedDevice === 'offline' ? '离线设备模式' : connectedDevice}</span>
              </>
            )}
          </div>
        </div>
      </div>

      <nav className="flex items-center rounded-lg border border-[#e7e7e3] bg-[#f7f7f5] p-0.5">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`h-8 min-w-[78px] rounded-md px-3 flex items-center justify-center gap-1.5 text-[11px] font-medium whitespace-nowrap transition-all ${
                active
                  ? 'bg-white text-[#191918] shadow-[0_1px_2px_rgba(20,20,18,0.06)] border border-[#e1e1dd]'
                  : 'text-[#77776f] border border-transparent hover:text-[#30302e]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="justify-self-end flex items-center gap-1.5 min-w-0">
        <div className="hidden xl:flex h-8 items-center rounded-lg border border-[#e1e1dd] bg-white shadow-[0_1px_2px_rgba(20,20,18,0.02)]">
          <Smartphone className="w-3.5 h-3.5 ml-2.5 text-[#8a8a83] shrink-0" />
          <select
            value={selectedDevice}
            onChange={(e) => onSelectDevice(e.target.value)}
            className="h-full max-w-[172px] min-w-[118px] bg-transparent pl-2 pr-1 text-[10px] text-[#4d4d48] outline-none"
            title="选择已发现设备"
          >
            <option value="offline">离线模式</option>
            {!isKnownDevice && selectedDevice && (
              <option value={selectedDevice}>手动 · {selectedDevice}</option>
            )}
            {devices.map((device) => (
              <option key={device.address} value={device.address}>
                {device.name || device.address}
              </option>
            ))}
          </select>
          <button
            onClick={handleManualDevice}
            className="h-full px-2 border-l border-[#ecece8] text-[#7f7f78] transition-colors hover:bg-[#f7f7f5] hover:text-[#30302e]"
            title="手动输入 ADB 序列号或 127.0.0.1:5555"
          >
            <PencilLine className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onRefreshDevices}
            className="h-full px-2 border-l border-[#ecece8] text-[#92928b] transition-colors hover:bg-[#f7f7f5] hover:text-[#30302e]"
            title="重新扫描设备"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {connectedDevice ? (
          <Button id="btnConnectDevice" variant="ghost" size="sm" onClick={onDisconnectDevice} className="h-8 px-2.5 text-[10px] text-rose-600 hover:bg-[#fff3f2]">
            <Unplug className="w-3.5 h-3.5" />断开
          </Button>
        ) : (
          <Button
            id="btnConnectDevice"
            variant="outline"
            size="sm"
            onClick={onConnectDevice}
            disabled={!backendOnline && selectedDevice !== 'offline'}
            className="h-8 px-2.5 text-[10px]"
            title={!backendOnline && selectedDevice !== 'offline' ? '真实设备连接需要启动 Workbench 后端' : '连接当前设备'}
          >
            <Plug className="w-3.5 h-3.5" />连接
          </Button>
        )}

        <Button
          size="sm"
          variant="ghost"
          onClick={onToggleLiveMonitor}
          className={`h-8 px-2.5 text-[10px] ${liveMonitor ? 'ds-status-success' : 'text-[#77776f]'}`}
          title="实时预览"
        >
          <Radio className={`w-3.5 h-3.5 ${liveMonitor ? 'animate-pulse' : ''}`} />
          {liveMonitor ? '实时' : '预览'}
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
        <Button
          variant="outline"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          className="h-8 px-2.5 text-[10px]"
          title="导入本地截图"
        >
          <FolderOpen className="w-3.5 h-3.5" />
          <span className="hidden 2xl:inline">导入</span>
        </Button>

        <Button
          id="btnTakeScreenshot"
          size="sm"
          onClick={onCaptureScreenshot}
          disabled={isCapturing}
          className="h-8 px-3 text-[10px]"
          title="截图（R）"
        >
          <Camera className={`w-3.5 h-3.5 ${isCapturing ? 'animate-spin' : ''}`} />
          截图
          <kbd className="ml-0.5 rounded border border-white/20 px-1 text-[8px] opacity-70">R</kbd>
        </Button>
      </div>
    </header>
  );
}
