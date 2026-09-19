import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { screenToImage, selectionRect } from '../src/Canvas';
import { projectForLocator } from '../src/inspection';
import type { Project } from '../src/types';

test('coordinate transforms preserve frame pixels under zoom and pan', () => {
  expect(screenToImage(153, 87, { x: 13, y: 7, zoom: 2 })).toEqual([70, 40]);
  expect(selectionRect([70.2, 40.1], [12.5, 19.5], 320, 200)).toEqual([12, 19, 59, 22]);
  expect(selectionRect([-5, -5], [400, 300], 320, 200)).toEqual([0, 0, 320, 200]);
});

test('inspection scope includes nested cross-page dependencies and excludes unrelated invalid items', () => {
  const config: Project = { version: 1, resource_dir: 'resource', output_dir: 'ui', resource_hook: '', managed_files: {},
    groups: [{ id: 'g', module: 'home', class_name: 'HomeUI', label: '' }, { id: 'shared', module: 'shared', class_name: 'SharedUI', label: '' }],
    locators: [
      { id: 'leaf', group_id: 'shared', name: 'LEAF', kind: 'OCR', params: { expected: ['确认'] }, children: [], export: false },
      { id: 'or', group_id: 'g', name: 'OR', kind: 'Or', params: {}, children: ['leaf'], export: true },
      { id: 'all', group_id: 'g', name: 'ALL', kind: 'And', params: {}, children: ['or', 'leaf'], export: true },
      { id: 'bad', group_id: 'g', name: 'BAD', kind: 'OCR', params: { unknown: true }, children: [], export: true },
    ],
  };
  const scoped = projectForLocator(config, 'all');
  expect(scoped.locators.map(item => item.id)).toEqual(['leaf', 'or', 'all']);
  expect(scoped.groups.map(group => group.id)).toEqual(['g', 'shared']);
  expect(config.locators).toHaveLength(4);
});

test('author, crop, validate, generate, reopen and import existing UI', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#token=browser-tests');
  await expect(page.getByText('从一张截图开始')).toBeVisible();
  const state = await (await request.get('/api/project', { headers: { Authorization: 'Bearer browser-tests' } })).json();
  await page.getByRole('button', { name: '新建 UI 分组', exact: true }).click();
  await page.getByLabel('模块名称', { exact: true }).fill('home');
  await page.getByLabel('Python 类名', { exact: true }).fill('HomeUI');
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await page.getByRole('button', { name: '＋ 新建定位项', exact: true }).first().click();
  await page.getByLabel('Python 属性名').fill('START');
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'START', exact: true })).toBeVisible();
  await page.locator('input[type=file]').setInputFiles({ name: 'frame.png', mimeType: 'image/png', buffer: readFileSync(`${state.root}/frame.png`) });
  await expect(page.getByText('320 × 200 px', { exact: false })).toBeVisible();
  const canvas = page.getByLabel('截图编辑画布');
  const bounds = (await canvas.boundingBox())!;
  const center = { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 };
  await page.getByRole('button', { name: '放大画布', exact: true }).click();
  await expect(page.getByText('200%', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '平移', exact: true }).click();
  await page.mouse.move(center.x, center.y);
  await page.mouse.down();
  await page.mouse.move(center.x + 30, center.y + 20, { steps: 4 });
  await page.mouse.up();
  await page.getByRole('button', { name: '裁图', exact: true }).click();
  await page.mouse.move(center.x - 200 + 30, center.y - 120 + 20);
  await page.mouse.down();
  await page.mouse.move(center.x - 120 + 30, center.y - 60 + 20, { steps: 5 });
  await page.mouse.up();
  await expect(page.getByText('选区 [60, 40, 40, 30]', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '保存模板', exact: true }).click();
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByText('模板已保存：home/start.png')).toBeVisible();
  await page.getByRole('button', { name: '▷ 验证识别', exact: true }).click();
  await expect(page.getByText('✓ 命中', { exact: true })).toBeVisible({ timeout: 20000 });
  await expect(page.locator('.result-summary code')).toHaveText('[60, 40, 40, 30]');
  await page.getByRole('button', { name: '保存并生成', exact: false }).first().click();
  await expect(page.getByRole('heading', { name: '保存前检查变更' })).toBeVisible();
  await page.getByRole('button', { name: '确认保存并生成', exact: true }).click();
  await expect(page.getByText('配置与 Python 文件已保存', { exact: true })).toBeVisible();
  expect(readFileSync(`${state.root}/ui/home.py`, 'utf-8')).toContain('START = JTemplateMatch');
  await page.reload();
  await expect(page.locator('.locator-row').filter({ hasText: 'START' })).toBeVisible();
  await page.getByRole('button', { name: '导入 Python', exact: true }).click();
  await page.getByRole('button', { name: 'ui/existing.py 预览导入 →' }).click();
  await expect(page.getByText('1 个 UI 类 · 1 个定位项')).toBeVisible();
  await page.getByRole('button', { name: '接入配置草稿' }).click();
  await expect(page.locator('.locator-row').filter({ hasText: 'CONFIRM' })).toBeVisible();
  await page.locator('.locator-row').filter({ hasText: 'CONFIRM' }).click();
  const expected = page.getByLabel('期望文字 / 正则');
  await expected.fill('确认');
  await expected.press('End');
  await expected.press('Enter');
  await expected.pressSequentially('Confirm');
  await expect(expected).toHaveValue('确认\nConfirm');
  await page.getByRole('button', { name: '保存并生成', exact: false }).first().click();
  await page.getByRole('button', { name: '确认保存并生成', exact: true }).click();
  await expect(page.getByText('配置与 Python 文件已保存', { exact: true })).toBeVisible();
  expect(readFileSync(`${state.root}/ui/existing.py`, 'utf-8')).toContain("expected=['确认', 'Confirm']");
  await page.locator('.locator-row').filter({ hasText: 'START' }).click();
  const threshold = page.getByLabel('匹配阈值', { exact: false });
  await threshold.fill('0.85,');
  await expect(page.getByRole('alert')).toBeVisible();
  await threshold.pressSequentially(' 0.9');
  await expect(threshold).toHaveValue('0.85, 0.9');
  await threshold.fill('0.85');
  await page.locator('input[type=file]').setInputFiles({ name: 'frame.png', mimeType: 'image/png', buffer: readFileSync(`${state.root}/frame.png`) });
  await page.getByRole('button', { name: '▷ 验证识别', exact: true }).click();
  await expect(page.getByText('✓ 命中', { exact: true })).toBeVisible({ timeout: 20000 });
  await page.screenshot({ path: 'test-results/studio-desktop.png', fullPage: true });
  await page.getByLabel('识别方式', { exact: false }).selectOption('ColorMatch');
  const lower = page.getByLabel('颜色下限', { exact: false });
  await lower.fill('[[200,');
  await expect(lower).toHaveValue('[[200,');
  await expect(page.getByRole('alert')).toBeVisible();
  await lower.pressSequentially(' 10, 30]]');
  await expect(lower).toHaveValue('[[200, 10, 30]]');
  await expect(page.getByRole('alert')).not.toBeVisible();
  expect(errors).toEqual([]);
});

test('locator display names and visual template selection persist independently of Python names', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#token=browser-tests');
  const state = await (await request.get('/api/project', { headers: { Authorization: 'Bearer browser-tests' } })).json();
  await page.getByRole('button', { name: '新建 UI 分组', exact: true }).click();
  await page.getByLabel('模块名称', { exact: true }).fill('chooser');
  await page.getByLabel('Python 类名', { exact: true }).fill('ChooserUI');
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await page.getByRole('button', { name: '＋ 新建定位项', exact: true }).first().click();
  await page.getByLabel('Python 属性名').fill('CONFIRM');
  await page.getByLabel('显示名称（可选）', { exact: true }).fill('确认按钮');
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByRole('heading', { name: '确认按钮', exact: true })).toBeVisible();
  const search = page.getByPlaceholder('搜索定位项');
  await search.fill('确认按钮');
  await expect(page.locator('.locator-row')).toHaveCount(1);
  await search.fill('CONFIRM');
  await expect(page.locator('.locator-row').filter({ hasText: '确认按钮' })).toBeVisible();
  await search.fill('');
  await page.getByLabel('显示名称', { exact: true }).fill('确定按钮');
  await expect(page.locator('.property-heading > span')).toHaveText('ChooserUI.CONFIRM');

  const choose = page.getByRole('button', { name: '▧ 选择模板图片', exact: true });
  await choose.click();
  const picker = page.getByRole('dialog', { name: '选择模板图片', exact: true });
  await picker.getByRole('checkbox', { name: '选择 按钮/确定.png', exact: true }).check();
  await picker.getByRole('checkbox', { name: '选择 icons/back.png', exact: true }).check();
  await expect(picker.getByText('已选 2 张', { exact: true })).toBeVisible();
  const image = picker.getByAltText('模板预览 按钮/确定.png', { exact: true });
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate(node => (node as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await page.screenshot({ path: 'test-results/studio-template-picker.png', fullPage: true });
  await picker.getByRole('button', { name: '取消', exact: true }).click();
  await expect(page.locator('.selected-template')).toHaveCount(0);

  await choose.click();
  await picker.getByRole('checkbox', { name: '选择 按钮/确定.png', exact: true }).check();
  await picker.getByRole('checkbox', { name: '选择 icons/back.png', exact: true }).check();
  await picker.getByRole('textbox', { name: '搜索模板图片' }).fill('确定');
  await expect(picker.getByRole('checkbox')).toHaveCount(1);
  await expect(picker.getByText('已选 2 张', { exact: true })).toBeVisible();
  await picker.getByRole('button', { name: '使用所选图片', exact: true }).click();
  await expect(page.locator('.template-path code')).toHaveText(['按钮/确定.png', 'icons/back.png']);
  await page.getByRole('button', { name: '上移模板 icons/back.png', exact: true }).click();
  await expect(page.locator('.template-path code')).toHaveText(['icons/back.png', '按钮/确定.png']);
  await page.getByRole('button', { name: '保存并生成', exact: false }).first().click();
  await page.getByRole('button', { name: '确认保存并生成', exact: true }).click();
  await expect(page.getByText('配置与 Python 文件已保存', { exact: true })).toBeVisible();
  const generated = readFileSync(`${state.root}/ui/chooser.py`, 'utf-8');
  expect(generated).toContain('CONFIRM = JTemplateMatch');
  expect(generated).not.toContain('确定按钮');
  await page.reload();
  await page.locator('.locator-row').filter({ hasText: '确定按钮' }).click();
  await expect(page.getByLabel('显示名称', { exact: true })).toHaveValue('确定按钮');
  await expect(page.locator('.template-path code')).toHaveText(['icons/back.png', '按钮/确定.png']);
  await page.getByLabel('识别方式', { exact: false }).selectOption('FeatureMatch');
  await choose.click();
  await picker.getByRole('checkbox', { name: '选择 按钮/确定.png', exact: true }).check();
  await picker.getByRole('button', { name: '使用所选图片', exact: true }).click();
  await expect(page.locator('.template-path code')).toHaveText(['按钮/确定.png']);
  expect(errors).toEqual([]);
});
