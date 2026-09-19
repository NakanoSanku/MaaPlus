import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { ImageCanvas } from './Canvas';
import { ParameterText } from './ParameterText';
import { DeviceDialog } from './DeviceDialog';
import { TemplatePicker } from './TemplatePicker';
import { PageResults } from './PageResults';
import { projectForLocator } from './inspection';
import { defaults, labels, locatorCaption, locatorTitle } from './types';
import type { Group, Inspection, Kind, Locator, PageInspection, PageInspectionItem, Preview, Project, Rect, Snapshot } from './types';
import './style.css';

type Form = { title: string; description?: string; fields: { key: string; label: string; value: string }[]; submit: (values: Record<string, string>) => void | Promise<void> };
function App() {
  const [project, setProject] = useState<Project | null>(null), [revision, setRevision] = useState(''), [root, setRoot] = useState('');
  const [selected, setSelected] = useState(''), [groupId, setGroupId] = useState(''), [search, setSearch] = useState('');
  const [dirty, setDirty] = useState(false), [busy, setBusy] = useState(''), [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null);
  const [shot, setShot] = useState<Snapshot | null>(null), [imageUrl, setImageUrl] = useState('');
  const [selection, setSelection] = useState<Rect | null>(null), [mode, setMode] = useState<'roi' | 'crop' | 'pan'>('roi');
  const [inspection, setInspection] = useState<Inspection | null>(null), [inspectionError, setInspectionError] = useState('');
  const [pageInspection, setPageInspection] = useState<PageInspection | null>(null);
  const pageRun = useRef<{ stop: boolean } | null>(null);
  const [tab, setTab] = useState('result'), [preview, setPreview] = useState<Preview | null>(null), [confirmPreview, setConfirmPreview] = useState(false);
  const [form, setForm] = useState<Form | null>(null), [formValues, setFormValues] = useState<Record<string, string>>({});
  const [showDevice, setShowDevice] = useState(false), [device, setDevice] = useState<any>({ connected: false });
  const [showImport, setShowImport] = useState(false), [pythonFiles, setPythonFiles] = useState<string[]>([]), [importResult, setImportResult] = useState<any>(null);
  const [showAssets, setShowAssets] = useState(false), [assets, setAssets] = useState<any[]>([]);
  const [advanced, setAdvanced] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const fileInput = useRef<HTMLInputElement>(null), sequence = useRef(0), shotId = useRef(''), busyRef = useRef('');
  const current = project?.locators.find(item => item.id === selected), group = project?.groups.find(g => g.id === (current?.group_id || groupId));

  async function run(label: string, work: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = label; setBusy(label); setNotice(null);
    try { await work(); } catch (error) { setNotice({ text: String(error instanceof Error ? error.message : error), error: true }); }
    finally { busyRef.current = ''; setBusy(''); }
  }
  function clearInspection() {
    if (pageRun.current) pageRun.current.stop = true;
    setInspection(null); setInspectionError(''); setPageInspection(null);
  }
  function edit(value: Project) { sequence.current++; setProject(value); setDirty(true); clearInspection(); setPreview(null); }
  function updateItem(changes: Partial<Locator>) { if (project && current) edit({ ...project, locators: project.locators.map(item => item.id === current.id ? { ...item, ...changes } : item) }); }
  function param(name: string, value: unknown) { if (current) updateItem({ params: { ...current.params, [name]: value } }); }
  function fieldError(name: string, value: string) { setFieldErrors(errors => ({ ...errors, [name]: value })); }
  function requireValidFields() { if (Object.values(fieldErrors).some(Boolean)) throw new Error('请先完成参数输入，修正标红的字段'); }
  function ask(value: Form) { setForm(value); setFormValues(Object.fromEntries(value.fields.map(field => [field.key, field.value]))); }
  function success(text: string) { setNotice({ text, error: false }); }
  async function load() {
    const value = await api('project'); setProject(value.project); setRevision(value.revision); setRoot(value.root); setDevice(value.device); setDirty(false);
  }
  useEffect(() => { void run('打开项目', load); }, []);
  useEffect(() => { setAdvanced(current ? JSON.stringify(current.params, null, 2) : ''); }, [selected, current?.params]);
  useEffect(() => { setFieldErrors({}); }, [selected, current?.kind]);
  useEffect(() => { const prevent = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault(); }; window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent); }, [dirty]);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  async function displayShot(value: Snapshot) {
    const url = await api<string>(`snapshots/${value.id}`);
    shotId.current = value.id; setShot(value); setImageUrl(url); setSelection(null); clearInspection();
  }
  function upload(file: Blob) { void run('读取截图', async () => displayShot(await api('snapshots', undefined, file))); }
  useEffect(() => { const paste = (event: ClipboardEvent) => { const image = Array.from(event.clipboardData?.files || []).find(file => file.type.startsWith('image/')); if (image) { event.preventDefault(); upload(image); } }; window.addEventListener('paste', paste); return () => window.removeEventListener('paste', paste); }, []);
  async function makePreview(value = project) {
    if (!value) return;
    requireValidFields();
    const version = sequence.current;
    const result = await api<Preview>('preview', { project: value, revision });
    if (version !== sequence.current) throw new Error('草稿已变化，请重新生成预览');
    setPreview(result); setTab('code'); return result;
  }
  async function commit() {
    if (!preview) return;
    const value = await api('commit', { preview_id: preview.preview_id }); setProject(value.project); setRevision(value.revision); setDirty(false); setConfirmPreview(false); success('配置与 Python 文件已保存');
  }
  function newGroup() {
    ask({ title: '新建 UI 分组', fields: [{ key: 'module', label: '模块名称', value: 'home' }, { key: 'class_name', label: 'Python 类名', value: 'HomeUI' }, { key: 'label', label: '显示名称（可选）', value: '' }], submit: values => {
      const id = crypto.randomUUID(); edit({ ...project!, groups: [...project!.groups, { id, ...values } as Group] }); setGroupId(id); setSelected('');
    } });
  }
  function newLocator() {
    if (!group) { newGroup(); return; }
    ask({ title: '新建定位项', fields: [{ key: 'name', label: 'Python 属性名', value: 'BUTTON' }, { key: 'label', label: '显示名称（可选）', value: '' }], submit: values => {
      const id = crypto.randomUUID(); edit({ ...project!, locators: [...project!.locators, { id, group_id: group.id, name: values.name, label: values.label.trim(), kind: 'TemplateMatch', params: defaults('TemplateMatch'), children: [], export: true }] }); setSelected(id);
    } });
  }
  function renameGroup() {
    if (!group) return;
    ask({ title: '修改 UI 分组', description: '模块或类名变化会改变 Python 导入接口，请同步更新业务代码。', fields: [{ key: 'module', label: '模块名称', value: group.module }, { key: 'class_name', label: 'Python 类名', value: group.class_name }, { key: 'label', label: '显示名称', value: group.label }], submit: values => edit({ ...project!, groups: project!.groups.map(g => g.id === group.id ? { ...g, ...values } : g) }) });
  }
  function removeLocator() {
    if (!current || !project) return;
    const references = project.locators.filter(i => i.children.includes(current.id));
    if (references.length) { setNotice({ text: `仍被引用：${references.map(locatorCaption).join('、')}`, error: true }); return; }
    ask({ title: `删除 ${locatorCaption(current)}`, description: '删除后生成接口会变化，业务代码中的引用需要同步修改。', fields: [], submit: () => { edit({ ...project, locators: project.locators.filter(i => i.id !== current.id) }); setSelected(''); } });
  }
  function removeGroup() {
    if (!group || !project) return;
    const ids = new Set(project.locators.filter(i => i.group_id === group.id).map(i => i.id));
    const refs = project.locators.filter(i => !ids.has(i.id) && i.children.some(child => ids.has(child)));
    if (refs.length) { setNotice({ text: `分组仍被引用：${refs.map(locatorCaption).join('、')}`, error: true }); return; }
    ask({ title: `删除分组 ${group.class_name}`, description: '该分组下的定位项也会删除；保存前可检查文件差异。', fields: [], submit: () => { edit({ ...project, groups: project.groups.filter(g => g.id !== group.id), locators: project.locators.filter(i => !ids.has(i.id)) }); setSelected(''); setGroupId(''); } });
  }
  function crop() {
    if (!selection || !shot || !project) return;
    ask({ title: '保存模板裁图', fields: [{ key: 'path', label: '相对 image 目录的路径', value: `${group?.module.replaceAll('.', '/') || 'common'}/${current?.name.toLowerCase() || 'template'}.png` }], submit: async values => {
      await api('crop', { project, snapshot_id: shot.id, rect: selection, path: values.path });
      if (current && ['TemplateMatch', 'FeatureMatch'].includes(current.kind)) param('template', [...new Set([...(current.params.template || []), values.path])]);
      success(`模板已保存：${values.path}`);
    } });
  }
  async function inspect() {
    if (!project || !current || !shot) return;
    requireValidFields();
    const version = sequence.current, frame = shot.id;
    setTab('result'); setInspectionError(''); setInspection(null);
    try {
      const result = await api<Inspection>('inspect', { project: projectForLocator(project, current.id), locator_id: current.id, snapshot_id: frame });
      if (version === sequence.current && frame === shotId.current) setInspection(result);
    } catch (error) {
      if (version === sequence.current && frame === shotId.current) setInspectionError(error instanceof Error ? error.message : String(error));
      try { setDevice((await api('project')).device); } catch { /* Preserve the original inspection error. */ }
      throw error;
    }
  }
  async function inspectPage() {
    if (!project || !group || !shot) return;
    requireValidFields();
    const draft = structuredClone(project), snapshot = structuredClone(shot);
    const targets = draft.locators.filter(item => item.group_id === group.id && item.export);
    if (!targets.length) throw new Error('当前页面没有可测试的定位项');
    const version = sequence.current, control = { stop: false }, started = performance.now();
    const isCurrent = () => version === sequence.current && snapshot.id === shotId.current && pageRun.current === control;
    pageRun.current = control;
    setTab('page'); setInspection(null); setInspectionError('');
    setPageInspection({ group: { ...group }, snapshot, status: 'running', elapsed_ms: 0, items: targets.map(locator => ({ locator, status: 'pending' })) });
    if (!targets.some(item => item.id === selected)) { setSelected(targets[0].id); setGroupId(group.id); setSelection(null); }
    let hadError = false, completed = 0;
    const update = (id: string, changes: Partial<PageInspectionItem>) => {
      if (!isCurrent()) return;
      setPageInspection(report => report ? { ...report, elapsed_ms: performance.now() - started, items: report.items.map(item => item.locator.id === id ? { ...item, ...changes } : item) } : null);
    };
    try {
      for (const item of targets) {
        if (control.stop || !isCurrent()) break;
        update(item.id, { status: 'running' });
        const itemStarted = performance.now();
        try {
          const result = await api<Inspection>('inspect', { project: projectForLocator(draft, item.id), locator_id: item.id, snapshot_id: snapshot.id });
          if (result.snapshot_id !== snapshot.id || result.locator_id !== item.id) throw new Error('识别结果与请求的截图或定位项不一致');
          update(item.id, { status: result.hit ? 'hit' : 'miss', result, elapsed_ms: result.elapsed_ms });
        } catch (error) {
          hadError = true;
          update(item.id, { status: 'error', error: error instanceof Error ? error.message : String(error), elapsed_ms: performance.now() - itemStarted });
        }
        completed++;
      }
      if (isCurrent()) setPageInspection(report => report ? { ...report, status: completed === targets.length ? 'completed' : 'stopped', elapsed_ms: performance.now() - started } : null);
      if (hadError) {
        try { setDevice((await api('project')).device); } catch { /* Keep the per-item errors visible. */ }
      }
    } finally {
      if (pageRun.current === control) pageRun.current = null;
    }
  }
  function stopPageInspection() {
    if (!pageRun.current) return;
    pageRun.current.stop = true;
    setPageInspection(report => report ? { ...report, status: 'stopping' } : null);
  }
  const pageResult = pageInspection && pageInspection.snapshot.id === shot?.id ? pageInspection.items.find(item => item.locator.id === selected)?.result : null;
  const visibleResult = inspection?.snapshot_id === shot?.id && inspection?.locator_id === selected ? inspection : tab === 'page' ? pageResult : null;
  const pageCount = project?.locators.filter(item => item.group_id === group?.id && item.export).length || 0;
  const roi = Array.isArray(current?.params.roi) ? current!.params.roi as Rect : null;
  const disabled = Boolean(busy);

  return <div className="app" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); const file = Array.from(e.dataTransfer.files).find(f => f.type.startsWith('image/')); if (file) upload(file); }}>
    <header className="topbar"><div className="brand"><span className="brand-mark">M<span>+</span></span><strong>MaaPlus <em>Studio</em></strong><span className="version">UI EDITOR</span></div><div className="project-name" title={root}>{root.split(/[\\/]/).pop() || '打开项目'}<span className={dirty ? 'dirty-dot' : 'saved-dot'} />{dirty ? '未保存' : '已同步'}</div><div className="top-actions"><button onClick={() => ask({ title: '项目设置', description: '目录均相对于当前项目。截图尺寸设置应与业务运行时保持一致。', fields: [{ key: 'resource_dir', label: 'MaaFramework 资源目录', value: project?.resource_dir || 'resource' }, { key: 'output_dir', label: 'Python UI 输出目录', value: project?.output_dir || 'ui' }, { key: 'resource_hook', label: '资源扩展函数（可选，module:callable）', value: project?.resource_hook || '' }], submit: values => edit({ ...project!, ...values }) })} disabled={!project || disabled}>项目设置</button><button className="primary" disabled={!project || disabled} onClick={() => void run('生成变更预览', async () => { await makePreview(); setConfirmPreview(true); })}>保存并生成 <span>↗</span></button></div></header>
    <div className="connection-bar"><span className={'status-dot ' + (device.connected ? 'online' : '')} /><span>{device.connected ? device.name : '尚未连接设备'}</span><span className="muted">仅截图与识别</span><button onClick={() => setShowDevice(true)} disabled={disabled}>选择设备 / 窗口</button>{device.connected && <button disabled={disabled} onClick={() => void run('断开连接', async () => setDevice(await api('disconnect', {})))}>断开</button>}<span className="connection-spacer" /><span className="busy-status">{busy && <><i className="spinner" /> {busy}…</>}</span><button disabled={!device.connected || disabled} onClick={() => void run('采集截图', async () => { try { await displayShot(await api('capture', {})); } catch (error) { setDevice({ connected: false }); throw error; } })}>◎ 采集截图</button><button disabled={disabled} onClick={() => fileInput.current?.click()}>↑ 导入截图</button><input ref={fileInput} type="file" accept="image/*" hidden onChange={e => { if (e.target.files?.[0]) upload(e.target.files[0]); e.target.value = ''; }} /></div>
    {notice && <div role="status" className={'notice ' + (notice.error ? 'error' : 'success')}><span>{notice.text}</span><button onClick={() => setNotice(null)} aria-label="关闭提示">×</button></div>}
    <main className="workspace">
      <aside className="sidebar"><div className="panel-title"><strong>项目结构</strong><button title="新建 UI 分组" aria-label="新建 UI 分组" onClick={newGroup} disabled={!project}>＋</button></div><div className="search"><span>⌕</span><input placeholder="搜索定位项" value={search} onChange={e => setSearch(e.target.value)} /></div><div className="tree">{project?.groups.map(g => <div className="tree-group" key={g.id}><button className={'group-row ' + (group?.id === g.id ? 'active-group' : '')} onClick={() => { setGroupId(g.id); setSelected(''); }}><span>⌄</span><span className="folder-icon">▧</span><strong>{g.label || g.class_name}</strong><small>{project.locators.filter(i => i.group_id === g.id && i.export).length}</small></button>{project.locators.filter(i => i.group_id === g.id && i.export && `${i.name} ${i.label || ''} ${labels[i.kind]}`.toLowerCase().includes(search.toLowerCase())).map(item => <button key={item.id} title={locatorCaption(item)} className={'locator-row ' + (selected === item.id ? 'selected' : '')} onClick={() => { setSelected(item.id); setGroupId(g.id); setSelection(null); }}><span className={'kind-icon ' + item.kind}>{item.kind === 'OCR' ? 'T' : item.kind === 'And' || item.kind === 'Or' ? '◇' : '⌗'}</span><span className="locator-names"><span>{locatorTitle(item)}</span>{item.label?.trim() && <code>{item.name}</code>}</span><small>{item.kind === 'TemplateMatch' ? 'IMG' : item.kind.toUpperCase()}</small></button>)}</div>)}{project && !project.groups.length && <div className="tree-empty"><p>按页面组织你的 UI</p><button onClick={newGroup}>＋ 创建第一个分组</button></div>}</div><div className="sidebar-actions"><button onClick={newLocator} disabled={!project}>＋ 新建定位项</button><div><button disabled={!project || disabled} onClick={() => void run('扫描 UI 文件', async () => { setPythonFiles(await api('files', { project })); setImportResult(null); setShowImport(true); })}>导入 Python</button><button disabled={!project || disabled} onClick={() => void run('读取图片资源', async () => { setAssets(await api('assets', { project })); setShowAssets(true); })}>图片资源</button></div></div></aside>
      <section className="editor"><div className="editor-toolbar"><div className="breadcrumb"><span>{group?.module || '画面'}</span><b>/</b><strong>{current ? locatorTitle(current) : (shot ? '截图预览' : '未选择定位项')}</strong></div><div className="segmented">{(['roi', 'crop', 'pan'] as const).map(value => <button className={mode === value ? 'active' : ''} key={value} onClick={() => { setMode(value); setSelection(null); }}>{value === 'roi' ? '框选 ROI' : value === 'crop' ? '裁图' : '平移'}</button>)}</div></div><ImageCanvas url={imageUrl} shot={shot} rect={selection || roi} match={visibleResult?.hit ? visibleResult.box : null} mode={mode} onRect={setSelection} /><div className="selection-bar"><span>{selection ? `选区 [${selection.join(', ')}]` : shot ? `${shot.source.name || '导入截图'} · ${shot.source.scale || '原图'} · 所有坐标基于识别帧` : '截图将在这里显示'} </span><div><button disabled={!selection || !current || ['And', 'Or'].includes(current.kind)} onClick={() => { param('roi', selection); setSelection(null); }}>应用为 ROI</button><button disabled={!selection || !selection[2] || !selection[3] || disabled} onClick={crop}>保存模板</button></div></div><div className={'bottom-panel' + (tab === 'page' ? ' page-test-panel' : '')}><div className="bottom-tabs"><button className={tab === 'result' ? 'active' : ''} onClick={() => setTab('result')}>识别结果</button><button className={tab === 'page' ? 'active' : ''} onClick={() => setTab('page')}>页面测试</button><button className={tab === 'code' ? 'active' : ''} onClick={() => { setTab('code'); if (!preview && project) void run('预览代码', async () => { await makePreview(); }); }}>Python 预览</button><span /><button className="page-test-trigger" disabled={!shot || !group || !pageCount || disabled} title={group ? `${group.label || group.class_name} · ${pageCount} 个定位项 · 使用当前截图` : '请选择页面'} onClick={() => void run('测试当前页面', inspectPage)}>测试当前页面</button><button className="primary compact" disabled={!shot || !current || disabled} onClick={() => void run('验证识别', inspect)}>▷ 验证识别</button></div><div className="bottom-content">{tab === 'page' ? <PageResults report={pageInspection} selected={selected} onStop={stopPageInspection} onSelect={id => { setSelected(id); setGroupId(pageInspection!.group.id); setSelection(null); }} /> : tab === 'result' ? inspectionError ? <div className="result-error"><b>识别执行错误</b><p>{inspectionError}</p></div> : visibleResult ? <><div className="result-summary"><span className={'result-badge ' + (visibleResult.hit ? 'hit' : 'miss')}>{visibleResult.hit ? '✓ 命中' : '○ 未命中'}</span><span>{visibleResult.elapsed_ms.toFixed(1)} ms</span><code>{visibleResult.box ? `[${visibleResult.box.join(', ')}]` : '无匹配框'}</code></div><pre>{JSON.stringify(visibleResult.raw_detail, null, 2)}</pre></> : <div className="result-empty"><span>◈</span><p>选定截图和定位项，验证实际识别效果</p><small>参数变化后，旧结果会清除</small></div> : preview ? Object.entries(preview.files).filter(([path]) => !group || path.endsWith(group.module.replaceAll('.', '/') + '.py')).map(([path, source]) => <div key={path}><div className="code-path">{path}</div><pre>{source}</pre></div>) : <div className="result-empty"><p>保存前会展示生成文件的完整差异</p></div>}</div></div></section>
      <aside className="properties"><div className="panel-title"><strong>定位参数</strong>{current && <span className="small-tag">{current.kind}</span>}</div>{current ? <div className="property-body"><div className="property-heading"><h2>{locatorTitle(current)}</h2><span>{group?.class_name}.{current.name}</span></div><label>显示名称<input aria-label="显示名称" placeholder={current.name} value={current.label || ''} onChange={event => updateItem({ label: event.target.value })} /><small>用于界面显示和搜索，留空显示 Python 属性名</small></label><label>识别方式<select value={current.kind} onChange={e => { const kind = e.target.value as Kind; updateItem({ kind, params: defaults(kind), children: [] }); }}>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>{!['And', 'Or'].includes(current.kind) && <section className="property-section"><div className="section-title">识别范围 <button onClick={() => param('roi', [0, 0, 0, 0])}>全图</button></div>{roi ? <div className="roi-grid">{['X', 'Y', '宽度', '高度'].map((label, index) => <label key={label}>{label}<input type="number" min="0" value={roi[index]} onChange={e => { const value = [...roi]; value[index] = Math.max(0, Math.trunc(Number(e.target.value))); param('roi', value); }} /></label>)}</div> : <p className="hint">当前 ROI 使用原生引用，请在高级参数中编辑。</p>}<p className="hint">[0, 0, 0, 0] 表示全图</p></section>}
      {['TemplateMatch', 'FeatureMatch'].includes(current.kind) && <TemplatePicker key={current.id + ':template'} directory={project!.resource_dir} value={current.params.template || []} disabled={disabled} onChange={value => param('template', value)} onError={value => fieldError('template', value)} />}
      {current.kind === 'TemplateMatch' && <label>匹配阈值<ParameterText key={current.id + ':threshold'} format="thresholds" value={current.params.threshold || [0.7]} onValue={value => param('threshold', value)} onError={value => fieldError('threshold', value)} /><small>多个阈值使用逗号分隔</small></label>}
      {current.kind === 'OCR' && <><label>期望文字 / 正则<ParameterText key={current.id + ':expected'} format="lines" placeholder="一行一个，例如：确认" value={current.params.expected || []} onValue={value => param('expected', value)} onError={value => fieldError('expected', value)} /></label><label>置信度阈值<input type="number" min="0" max="1" step="0.05" value={current.params.threshold ?? 0.3} onChange={e => param('threshold', Number(e.target.value))} /></label><label className="checkbox"><input type="checkbox" checked={current.params.only_rec || false} onChange={e => param('only_rec', e.target.checked)} />仅识别 ROI 内的文字</label></>}
      {current.kind === 'FeatureMatch' && <><label>特征算法<select value={current.params.detector || 'SIFT'} onChange={e => param('detector', e.target.value)}>{['SIFT', 'KAZE', 'AKAZE', 'ORB', 'BRISK'].map(v => <option key={v}>{v}</option>)}</select></label><label>最少匹配点<input type="number" min="1" value={current.params.count ?? 4} onChange={e => param('count', Number(e.target.value))} /></label><label>距离比值<input type="number" step="0.05" value={current.params.ratio ?? 0.6} onChange={e => param('ratio', Number(e.target.value))} /></label></>}
      {current.kind === 'ColorMatch' && <><label>颜色空间<select value={current.params.method ?? 4} onChange={e => param('method', Number(e.target.value))}><option value={4}>RGB</option><option value={40}>HSV</option></select></label>{['lower', 'upper'].map(key => <label key={key}>{key === 'lower' ? '颜色下限' : '颜色上限'}<ParameterText key={current.id + ':' + key} format="colors" value={current.params[key] || []} onValue={value => param(key, value)} onError={value => fieldError(key, value)} /></label>)}<label>最少像素数<input type="number" min="1" value={current.params.count ?? 1} onChange={e => param('count', Number(e.target.value))} /></label></>}
      {current.kind === 'Custom' && <><label>识别注册名称<input value={current.params.custom_recognition || ''} onChange={e => param('custom_recognition', e.target.value)} /></label><p className="hint">在项目设置中指定资源扩展函数，注册你的识别算法。参数可在下方 JSON 中编辑。</p></>}
      {['And', 'Or'].includes(current.kind) && <section className="property-section"><div className="section-title">组合成员 <small>{current.children.length}</small></div><div className="members">{current.children.map((id, index) => { const item = project!.locators.find(i => i.id === id); return <div key={index}><button className="member-name" title="编辑成员参数" onClick={() => { setSelected(id); setSelection(null); }}>{index} · {item ? item.export ? locatorCaption(item) : item.label?.trim() || `${labels[item.kind]}（内联）` : '引用已失效'}</button><button disabled={index === 0} onClick={() => { const next = [...current.children]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; updateItem({ children: next }); }}>↑</button><button onClick={() => updateItem({ children: current.children.filter((_, position) => position !== index) })}>×</button></div>; })}</div><select value="" onChange={e => updateItem({ children: [...current.children, e.target.value] })}><option value="" disabled>添加成员…</option>{project!.locators.filter(i => i.id !== current.id && !current.children.includes(i.id)).map(i => <option key={i.id} value={i.id}>{project!.groups.find(g => g.id === i.group_id)?.class_name} · {locatorCaption(i)}</option>)}</select>{current.kind === 'And' && <label>结果框来自成员索引<input type="number" min="0" max={current.children.length - 1} value={current.params.box_index ?? 0} onChange={e => param('box_index', Number(e.target.value))} /></label>}</section>}
      <details className="advanced"><summary>高级原生参数</summary><textarea aria-label="高级原生参数 JSON" rows={12} value={advanced} onChange={e => setAdvanced(e.target.value)} /><button onClick={() => { try { const params = JSON.parse(advanced); if (!params || Array.isArray(params) || typeof params !== 'object') throw new Error('参数必须是 JSON 对象'); updateItem({ params }); } catch (error) { setNotice({ text: String(error), error: true }); } }}>应用 JSON</button></details><div className="item-actions"><button onClick={() => ask({ title: '重命名定位项', description: '显示名称用于界面；修改 Python 属性名时，请同步更新业务引用。组合关系会保留。', fields: [{ key: 'name', label: 'Python 属性名', value: current.name }, { key: 'label', label: '显示名称（可选）', value: current.label || '' }], submit: value => updateItem({ name: value.name, label: value.label.trim() }) })}>重命名</button><button onClick={() => { const id = crypto.randomUUID(); edit({ ...project!, locators: [...project!.locators, { ...structuredClone(current), id, name: current.name + '_COPY', label: current.label?.trim() ? current.label + '（副本）' : '' }] }); setSelected(id); }}>复制</button><button className="danger" onClick={removeLocator}>删除</button></div></div> : group ? <div className="property-body"><h2>{group.class_name}</h2><code>{group.module}.py</code><p className="hint">UI 类只描述识别条件。新建定位项，开始管理此页面中的元素。</p><button className="wide" onClick={newLocator}>＋ 新建定位项</button><button className="wide" onClick={renameGroup}>修改分组</button><button className="wide danger" onClick={removeGroup}>删除分组</button></div> : <div className="property-empty"><span>⌘</span><p>选择一个定位项</p><small>在此编辑识别方式与参数</small></div>}</aside>
    </main><footer className="app-footer"><span>LOCAL WORKSPACE</span><span title={root}>{root}</span><span>{project?.locators.filter(i => i.export).length || 0} 个定位项 · {project?.groups.length || 0} 个分组</span></footer>
    {form && <div className="modal-overlay"><form className="modal" onSubmit={e => { e.preventDefault(); void run('应用修改', async () => { await form.submit(formValues); setForm(null); }); }}><div className="modal-title"><h2>{form.title}</h2><button type="button" onClick={() => setForm(null)}>×</button></div>{form.description && <p className="hint">{form.description}</p>}{form.fields.map(field => <label key={field.key}>{field.label}<input autoFocus={field === form.fields[0]} value={formValues[field.key] || ''} onChange={e => setFormValues({ ...formValues, [field.key]: e.target.value })} /></label>)}<div className="modal-actions"><button type="button" onClick={() => setForm(null)}>取消</button><button className="primary" disabled={disabled} type="submit">确认</button></div></form></div>}
    {showDevice && <DeviceDialog busy={disabled} run={run} onClose={() => setShowDevice(false)} onConnect={async options => {
      try { setDevice(await api('connect', options)); await displayShot(await api('capture', {})); setShowDevice(false); }
      catch (error) { setDevice({ connected: false }); throw error; }
    }} />}
    {showImport && <div className="modal-overlay"><div className="modal wide-modal"><div className="modal-title"><h2>导入现有 Python UI</h2><button onClick={() => setShowImport(false)}>×</button></div><p className="hint">读取静态定义并转换为配置。不会执行源文件；保存生成前原文件保持不变。</p><div className="file-list">{pythonFiles.length ? pythonFiles.map(path => <button key={path} disabled={disabled || Boolean(importResult)} onClick={() => void run('转换 UI 定义', async () => setImportResult(await api('import', { project, path })))}><code>{path}</code><span>预览导入 →</span></button>) : <p>所选输出目录没有 Python 文件，请先检查项目设置。</p>}</div>{importResult && <div className="import-summary"><b>已转换 {importResult.path}</b><p>{importResult.groups} 个 UI 类 · {importResult.locators} 个定位项</p><pre>{JSON.stringify({ groups: importResult.project.groups.filter((g: Group) => !project?.groups.some(old => old.id === g.id)), locators: importResult.project.locators.filter((i: Locator) => !project?.locators.some(old => old.id === i.id)) }, null, 2)}</pre><div className="modal-actions"><button disabled={disabled} onClick={() => setImportResult(null)}>返回选择</button><button className="primary" disabled={disabled} onClick={() => void run('接管 UI 文件', async () => { const result = await api('import/accept', { import_id: importResult.import_id }); edit(result.project); setShowImport(false); setImportResult(null); success('转换结果已加入草稿，可继续导入其他文件或保存生成'); })}>接入配置草稿</button></div></div>}</div></div>}
    {showAssets && <div className="modal-overlay"><div className="modal wide-modal"><div className="modal-title"><h2>图片资源</h2><button onClick={() => setShowAssets(false)}>×</button></div><p className="hint">{project?.resource_dir}/image · 重命名会同步更新模板引用和生成代码。</p><div className="asset-list">{assets.length ? assets.map(asset => <div key={asset.path}><code>{asset.path}</code><small>{(asset.bytes / 1024).toFixed(1)} KB · {asset.references.length ? asset.references.join('、') : '未引用'}</small><button onClick={() => { setShowAssets(false); ask({ title: '重命名图片', fields: [{ key: 'path', label: '新相对路径', value: asset.path }], submit: async values => { const result = await api<Preview>('assets/rename', { project, revision, source: asset.path, target: values.path }); setPreview(result); setConfirmPreview(true); } }); }}>重命名</button><button className="danger" disabled={disabled || asset.references.length > 0} onClick={() => { setShowAssets(false); ask({ title: `删除图片 ${asset.path}`, fields: [], submit: async () => { await api('assets/delete', { project, path: asset.path }); success('图片已删除'); } }); }}>删除</button></div>) : <p>没有图片资源。在画布中框选区域并保存模板。</p>}</div></div></div>}
    {confirmPreview && preview && <div className="modal-overlay"><div className="modal diff-modal"><div className="modal-title"><h2>保存前检查变更</h2><button onClick={() => setConfirmPreview(false)}>×</button></div><p className="hint">配置与生成文件一并保存。属性、类或模块名称发生变化时，请同步更新业务引用。</p><div className="diff-list">{preview.changes.length ? preview.changes.map(change => <details key={change.path} open={change.path.endsWith('.py')}><summary><span className="small-tag">{change.action}</span> {change.path}</summary><pre>{change.diff || '图片资源变更'}</pre></details>) : <p>当前内容与磁盘一致。</p>}</div><div className="modal-actions"><button onClick={() => setConfirmPreview(false)}>返回编辑</button><button className="primary" disabled={disabled} onClick={() => void run('保存生成文件', commit)}>确认保存并生成</button></div></div></div>}
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
