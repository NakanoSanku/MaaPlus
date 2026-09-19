import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { Locator, Project } from '../src/types';

async function openTestPage(page: Page, request: APIRequestContext, prefix: string, label: string) {
  const headers = { Authorization: 'Bearer browser-tests' };
  const state = await (await request.get('/api/project', { headers })).json();
  const config: Project = state.project;
  const id = (value: string) => `${prefix}-${value}`;
  const locator = (name: string, display: string, kind: Locator['kind'], params: Locator['params'], children: string[] = []): Locator => ({
    id: id(name), group_id: prefix, name, label: display, kind, params, children, export: true,
  });
  const color = { lower: [[0, 0, 0]], upper: [[255, 255, 255]], method: 4, count: 1, roi: [10, 10, 30, 20] };
  config.groups.push({ id: prefix, module: prefix, class_name: 'BatchUI', label }, { id: id('other'), module: `${prefix}_other`, class_name: 'OtherUI', label: `${label}之外` });
  config.locators.push(
    locator('HIT', '页面标记', 'ColorMatch', color),
    locator('MISS', '未出现的元素', 'ColorMatch', { ...color, lower: [[255, 255, 255]], upper: [[255, 255, 255]], count: 1000 }),
    locator('ERROR', '未注册算法', 'Custom', { custom_recognition: 'BatchMissingRecognition' }),
    locator('COMPOSITE', '组合校验', 'And', { box_index: 1 }, [id('HIT'), id('INLINE')]),
    { ...locator('INLINE', '内联成员', 'ColorMatch', { ...color, roi: [40, 20, 15, 10] }), group_id: id('other'), export: false },
    { ...locator('OTHER', '其他页面定位项', 'ColorMatch', color), group_id: id('other') },
  );
  const preview = await request.post('/api/preview', { headers, data: { project: config, revision: state.revision } });
  expect(preview.ok(), await preview.text()).toBeTruthy();
  const saved = await request.post('/api/commit', { headers, data: { preview_id: (await preview.json()).preview_id } });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto('/#token=browser-tests');
  await page.locator('.group-row').filter({ hasText: label }).first().click();
  await page.locator('input[type=file]').setInputFiles({ name: 'frame.png', mimeType: 'image/png', buffer: readFileSync(`${state.root}/frame.png`) });
  await expect(page.getByText('320 × 200 px', { exact: false })).toBeVisible();
  return { id, root: state.root };
}

test('tests every page locator on one frame, continues after an error, and opens result details', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const { id, root } = await openTestPage(page, request, 'page_batch', '主页识别');
  const calls: any[] = [];
  page.on('request', request => { if (request.url().endsWith('/api/inspect')) calls.push(request.postDataJSON()); });
  const search = page.getByPlaceholder('搜索定位项');
  await search.fill('HIT');
  await page.getByRole('button', { name: '测试当前页面', exact: true }).click();
  const report = page.getByLabel('页面测试结果', { exact: true });
  await expect(report.getByText('已完成', { exact: true })).toBeVisible({ timeout: 25000 });
  await expect(report.locator('tbody tr')).toHaveCount(4);
  await expect(report.getByText('命中 2', { exact: true })).toBeVisible();
  await expect(report.getByText('未命中 1', { exact: true })).toBeVisible();
  await expect(report.getByText('错误 1', { exact: true })).toBeVisible();
  expect(calls.map(call => call.locator_id)).toEqual(['HIT', 'MISS', 'ERROR', 'COMPOSITE'].map(id));
  expect(new Set(calls.map(call => call.snapshot_id)).size).toBe(1);
  expect(calls[3].project.locators.map((item: Locator) => item.id)).toEqual(['HIT', 'COMPOSITE', 'INLINE'].map(id));
  expect(calls.every(call => !call.project.locators.some((item: Locator) => item.id === id('OTHER')))).toBeTruthy();
  await report.getByRole('button', { name: '查看 未注册算法 · ERROR 的测试结果', exact: true }).click();
  await expect(report.getByLabel('定位项测试详情')).toContainText('尚未注册');
  await report.getByRole('button', { name: '查看 组合校验 · COMPOSITE 的测试结果', exact: true }).click();
  await expect(report.getByLabel('定位项测试详情').locator('code')).toHaveText('[40, 20, 15, 10]');
  await expect(page.getByRole('heading', { name: '组合校验', exact: true })).toBeVisible();
  await search.fill('');
  await page.screenshot({ path: 'test-results/studio-page-inspection.png', fullPage: true });
  await page.locator('input[type=file]').setInputFiles({ name: 'new-frame.png', mimeType: 'image/png', buffer: readFileSync(`${root}/frame.png`) });
  await expect(report).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('stops after the current item and discards in-flight results when the draft changes', async ({ page, request }) => {
  await openTestPage(page, request, 'page_stop', '停止验收');
  let release: () => void = () => {};
  let calls = 0;
  await page.route('**/api/inspect', async route => {
    calls++;
    const body = route.request().postDataJSON();
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ json: { hit: true, box: [10, 10, 30, 20], elapsed_ms: 2, raw_detail: {}, snapshot_id: body.snapshot_id, locator_id: body.locator_id } });
  });
  const trigger = page.getByRole('button', { name: '测试当前页面', exact: true });
  await trigger.click();
  await expect.poll(() => calls).toBe(1);
  const report = page.getByLabel('页面测试结果', { exact: true });
  await report.getByRole('button', { name: '停止测试', exact: true }).click();
  await expect(report.getByText('等待当前项结束', { exact: true })).toBeVisible();
  release();
  await expect(report.getByText('已停止', { exact: true })).toBeVisible();
  await expect(report.locator('tr[data-status="pending"]')).toHaveCount(3);
  expect(calls).toBe(1);
  await expect(trigger).toBeEnabled();
  await trigger.click();
  await expect.poll(() => calls).toBe(2);
  await page.getByLabel('显示名称', { exact: true }).fill('编辑后的定位项');
  await expect(report).toHaveCount(0);
  release();
  await expect(trigger).toBeEnabled();
  expect(calls).toBe(2);
  await expect(report).toHaveCount(0);
});
