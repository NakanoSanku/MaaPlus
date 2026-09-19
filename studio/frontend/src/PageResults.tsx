import { locatorCaption, locatorTitle } from './types';
import type { PageInspection, PageInspectionItem } from './types';
import './page-results.css';

const statuses: Record<PageInspectionItem['status'], string> = {
  pending: '未测试', running: '识别中', hit: '命中', miss: '未命中', error: '执行错误',
};
const runStatuses: Record<PageInspection['status'], string> = {
  running: '测试中', stopping: '等待当前项结束', completed: '已完成', stopped: '已停止',
};

export function PageResults({ report, selected, onSelect, onStop }: {
  report: PageInspection | null; selected: string; onSelect: (id: string) => void; onStop: () => void;
}) {
  if (!report) return <div className="result-empty"><span>▤</span><p>选择一个页面和截图，测试该页面全部定位项</p><small>使用同一张截图；搜索筛选不影响测试范围</small></div>;
  const count = (status: PageInspectionItem['status']) => report.items.filter(item => item.status === status).length;
  const completed = count('hit') + count('miss') + count('error');
  const active = report.status === 'running' || report.status === 'stopping';
  const current = report.items.find(item => item.locator.id === selected);
  return <div className="page-results" aria-label="页面测试结果">
    <div className="page-test-summary" aria-live="polite">
      <div className="page-test-heading"><strong>{report.group.label || report.group.class_name}</strong><code>{report.group.class_name}</code><span>{runStatuses[report.status]}</span>
        {active && <button disabled={report.status === 'stopping'} onClick={onStop} title="等待当前项返回后停止，不再测试剩余定位项">{report.status === 'stopping' ? '正在停止' : '停止测试'}</button>}
      </div>
      <div className="page-test-counts"><span>已完成 {completed} / {report.items.length}</span><span className="page-hit">命中 {count('hit')}</span><span className="page-miss">未命中 {count('miss')}</span><span className="page-error">错误 {count('error')}</span><span>总耗时 {(report.elapsed_ms / 1000).toFixed(2)} s</span></div>
      <progress aria-label="页面测试进度" value={completed} max={report.items.length} />
      <small>截图 {report.snapshot.width} × {report.snapshot.height} · {report.snapshot.id.slice(0, 8)} · 点击定位项查看命中框和详情</small>
    </div>
    <table className="page-test-table"><thead><tr><th>定位项</th><th>结果</th><th>耗时</th></tr></thead><tbody>
      {report.items.map(item => <tr key={item.locator.id} data-status={item.status} className={selected === item.locator.id ? 'chosen' : ''}>
        <td><button onClick={() => onSelect(item.locator.id)} aria-label={`查看 ${locatorCaption(item.locator)} 的测试结果`}><span>{locatorTitle(item.locator)}</span><code>{item.locator.name}</code></button></td>
        <td><span className={'page-test-status page-' + item.status}>{statuses[item.status]}</span></td>
        <td>{item.elapsed_ms === undefined ? '—' : `${item.elapsed_ms.toFixed(1)} ms`}</td>
      </tr>)}
    </tbody></table>
    {current && <div className="page-test-detail" aria-label="定位项测试详情"><div><strong>{locatorCaption(current.locator)}</strong><span className={'page-' + current.status}>{statuses[current.status]}</span></div>
      {current.error ? <p className="result-error">{current.error}</p> : current.result ? <><code>{current.result.box ? `[${current.result.box.join(', ')}]` : '无匹配框'}</code><pre>{JSON.stringify(current.result.raw_detail, null, 2)}</pre></> : <p className="hint">{current.status === 'running' ? '正在使用当前截图识别…' : '此项尚未测试。'}</p>}
    </div>}
  </div>;
}
