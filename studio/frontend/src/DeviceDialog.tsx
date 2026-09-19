import { useState } from 'react';
import { api } from './api';

interface Device { id: string; name: string; class_name?: string; address?: string }
interface Props {
  busy: boolean;
  run: (label: string, work: () => Promise<void>) => Promise<void>;
  onClose: () => void;
  onConnect: (options: Record<string, unknown>) => Promise<void>;
}

export function DeviceDialog({ busy, run, onClose, onConnect }: Props) {
  const [kind, setKind] = useState('adb');
  const [adbPath, setAdbPath] = useState('');
  const [devices, setDevices] = useState<Device[]>([]);
  const [selected, setSelected] = useState('');
  const [search, setSearch] = useState('');
  const [method, setMethod] = useState('FramePool');
  const [scale, setScale] = useState('default');
  const [size, setSize] = useState(720);
  const choices = devices.filter(device => `${device.name} ${device.class_name || ''} ${device.address || ''} ${device.id}`.toLowerCase().includes(search.toLowerCase()));

  return <div className="modal-overlay"><div className="modal device-modal">
    <div className="modal-title"><h2>连接截图来源</h2><button onClick={onClose}>×</button></div>
    <div className="segmented large">
      {[['adb', 'Android / ADB'], ['win32', 'Windows 窗口']].map(([value, label]) =>
        <button key={value} disabled={busy} className={kind === value ? 'active' : ''} onClick={() => {
          setKind(value); setDevices([]); setSelected(''); setSearch('');
        }}>{label}</button>)}
    </div>
    {kind === 'adb' && <label>ADB 执行文件（留空自动发现）
      <input value={adbPath} onChange={event => setAdbPath(event.target.value)} placeholder="C:\…\adb.exe" />
    </label>}
    <button className="wide" disabled={busy} onClick={() => void run('发现设备', async () => {
      setDevices(await api('devices', { kind, adb_path: adbPath })); setSelected('');
    })}>刷新{kind === 'adb' ? '设备' : '窗口'}列表</button>
    <input aria-label="筛选设备或窗口" placeholder={kind === 'win32' ? '按窗口标题、类名筛选' : '按设备名称、地址筛选'} value={search} onChange={event => setSearch(event.target.value)} />
    <div className="device-list">
      {choices.length ? choices.map(device => <button key={device.id} className={selected === device.id ? 'chosen' : ''} onClick={() => setSelected(device.id)}>
        <strong>{device.name || device.id}</strong><small>{device.class_name || device.address} · {device.id}</small>
      </button>) : <p>{search ? '没有符合条件的目标' : '刷新列表后，选择要采集画面的目标'}</p>}
    </div>
    {kind === 'win32' && <label>截图方式<select value={method} onChange={event => setMethod(event.target.value)}>
      {['FramePool', 'PrintWindow', 'ScreenDC', 'GDI', 'DXGI_DesktopDup_Window'].map(value => <option key={value}>{value}</option>)}
    </select></label>}
    <div className="field-row">
      <label>截图尺寸<select value={scale} onChange={event => setScale(event.target.value)}>
        <option value="default">MaaFramework 默认</option><option value="raw">原始分辨率</option>
        <option value="short">指定短边</option><option value="long">指定长边</option>
      </select></label>
      {['short', 'long'].includes(scale) && <label>像素<input type="number" min="64" max="8192" value={size} onChange={event => setSize(Number(event.target.value))} /></label>}
    </div>
    <p className="hint">尺寸应与业务程序一致。此工具只读取截图，鼠标操作画布用于选区。</p>
    <div className="modal-actions"><button onClick={onClose}>取消</button>
      <button className="primary" disabled={!selected || busy} onClick={() => void run('连接截图来源', () =>
        onConnect({ kind, id: selected, adb_path: adbPath, method, scale, size }))}>连接并截图</button>
    </div>
  </div></div>;
}
