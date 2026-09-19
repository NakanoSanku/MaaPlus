import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import { ParameterText } from './ParameterText';
import './templates.css';

interface Asset { path: string; bytes: number }
interface AssetList { items: Asset[]; case_sensitive: boolean }
interface Props {
  directory: string;
  value: unknown;
  disabled: boolean;
  onChange: (paths: string[]) => void;
  onError: (message: string) => void;
}

function ResourceThumbnail({ directory, path }: { directory: string; path: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, { rootMargin: '120px' });
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!visible) return;
    let active = true, objectUrl = '';
    setUrl(''); setError('');
    void api<string>('assets/thumbnail', { resource_dir: directory, path }).then(value => {
      if (active) { objectUrl = value; setUrl(value); }
      else URL.revokeObjectURL(value);
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [visible, directory, path]);
  return <div ref={host} className={'asset-thumbnail' + (error ? ' unavailable' : '')} title={error || path}>
    {url ? <img src={url} alt={`模板预览 ${path}`} /> : <span>{error ? '无法预览' : '载入中…'}</span>}
  </div>;
}

function PickerDialog({ directory, value, onApply, onClose }: {
  directory: string; value: string[]; onApply: (paths: string[]) => void; onClose: () => void;
}) {
  const [listing, setListing] = useState<AssetList | null>(null);
  const [pending, setPending] = useState([...value]);
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(48);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setListing(null); setError('');
    void api<AssetList>('assets/browse', { resource_dir: directory }).then(result => {
      if (active) setListing(result);
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { active = false; };
  }, [directory, revision]);
  useEffect(() => { setLimit(48); }, [search]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);

  function key(path: string) {
    const normalized = path.replaceAll('\\', '/');
    return listing?.case_sensitive ? normalized : normalized.toLowerCase();
  }
  function toggle(path: string) {
    setPending(previous => previous.some(value => key(value) === key(path))
      ? previous.filter(value => key(value) !== key(path)) : [...previous, path]);
  }
  const filtered = listing?.items.filter(asset => asset.path.toLowerCase().includes(search.toLowerCase())) || [];
  const missing = listing ? pending.filter(path => !listing.items.some(asset => key(asset.path) === key(path))) : [];

  return <div className="modal-overlay"><div className="modal template-picker-modal" role="dialog" aria-modal="true" aria-labelledby="template-picker-title">
    <div className="modal-title"><h2 id="template-picker-title">选择模板图片</h2><button aria-label="关闭图片选择器" onClick={onClose}>×</button></div>
    <p className="hint">{directory}/image · 可多选，按选择顺序添加；已有模板保留原顺序。</p>
    <div className="template-picker-search">
      <input autoFocus aria-label="搜索模板图片" placeholder="搜索文件名或文件夹…" value={search} onChange={event => setSearch(event.target.value)} />
      <button onClick={() => setRevision(value => value + 1)}>刷新列表</button>
    </div>
    {error ? <p className="field-error" role="alert">{error}</p> : !listing ? <p className="hint">正在读取图片资源…</p> : <>
      {missing.length > 0 && <div className="missing-templates"><p>以下已有路径不在资源列表中；确认选择时会保留，可在下方移除。</p>
        {missing.map((path, index) => <div key={index}><code>{path}</code><button onClick={() => setPending(items => items.filter(value => key(value) !== key(path)))}>移除</button></div>)}
      </div>}
      <div className="template-picker-grid">
        {filtered.slice(0, limit).map(asset => {
          const index = pending.findIndex(path => key(path) === key(asset.path));
          return <label key={`${revision}:${asset.path}`} className={'template-choice' + (index >= 0 ? ' chosen' : '')}>
            <input type="checkbox" aria-label={`选择 ${asset.path}`} checked={index >= 0} onChange={() => toggle(asset.path)} />
            <ResourceThumbnail directory={directory} path={asset.path} />
            <code title={asset.path}>{asset.path}</code>
            <small>{(asset.bytes / 1024).toFixed(1)} KB{index >= 0 && ` · 第 ${index + 1} 个模板`}</small>
          </label>;
        })}
        {!filtered.length && <p className="template-picker-empty">{listing.items.length ? '没有符合搜索条件的图片' : '资源目录内暂无图片。可先在画布裁图并保存模板，或将图片放入此目录。'}</p>}
      </div>
      {filtered.length > limit && <button className="wide" onClick={() => setLimit(value => value + 48)}>加载更多（已显示 {limit} / {filtered.length}）</button>}
    </>}
    <div className="modal-actions template-picker-actions"><span>已选 {pending.length} 张</span><button onClick={onClose}>取消</button>
      <button className="primary" disabled={!listing} onClick={() => { onApply(pending); onClose(); }}>使用所选图片</button>
    </div>
  </div></div>;
}

export function TemplatePicker({ directory, value: input, disabled, onChange, onError }: Props) {
  const [open, setOpen] = useState(false);
  const valid = Array.isArray(input) && input.every(path => typeof path === 'string');
  const value: string[] = valid ? input as string[] : [];
  function move(index: number) {
    const updated = [...value];
    [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
    onChange(updated);
  }
  return <section className="template-field" aria-label="模板图片">
    <div className="section-title">模板图片 <small>{value.length} 张</small></div>
    <button className="wide" disabled={disabled} onClick={() => setOpen(true)}>▧ 选择模板图片</button>
    {!valid && <p className="field-error" role="alert">template 参数需要字符串数组，请选择图片或修正高级 JSON。</p>}
    <div className="selected-templates">
      {value.map((path, index) => <div className="selected-template" key={`${index}:${path}`}>
        <ResourceThumbnail directory={directory} path={path} />
        <div className="template-path"><small>模板 {index + 1}</small><code title={path}>{path}</code></div>
        <div className="template-row-actions">
          <button disabled={disabled || index === 0} title="上移模板" aria-label={`上移模板 ${path}`} onClick={() => move(index)}>↑</button>
          <button disabled={disabled} title="移除此模板引用" aria-label={`移除模板 ${path}`} onClick={() => onChange(value.filter((_, position) => position !== index))}>×</button>
        </div>
      </div>)}
    </div>
    {!value.length && <p className="hint">从资源目录选择图片，或在画布裁图并保存模板。</p>}
    <details className="template-manual"><summary>手动编辑路径</summary><label>模板图片相对路径
      <ParameterText format="lines" value={value} placeholder="home/button.png（一行一个）" onValue={paths => onChange(paths as string[])} onError={onError} />
    </label></details>
    {open && <PickerDialog directory={directory} value={value} onApply={onChange} onClose={() => setOpen(false)} />}
  </section>;
}
