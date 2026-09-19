# MaaPlus Studio 0.1 验收记录

验收日期：2026-09-19。环境：Windows x64、Python 3.14.6、MaaFramework 5.13.1、Node.js 24.18.0 LTS、pnpm 11.3.0。前端生产构建使用 React 19.3.0、TypeScript 7.0.2、Vite 8.3.0；浏览器测试使用本机 Microsoft Edge，1440×1000 视口、设备像素比 2。

## 已通过

| 范围 | 实际验证 |
| --- | --- |
| MaaPlus 回归 | 根项目 145 项测试通过 |
| Studio 后端 | 72 项测试通过；ADB 实机用例未开启，跳过 1 项 |
| 前端 | 6 项 Playwright 测试通过，包含坐标/依赖范围检查、完整创作与导入流程、页面批量测试，无页面 JavaScript 错误 |
| 页面批量测试 | 同页全部导出项绑定同一截图；忽略搜索筛选；跨页及内联依赖随组合验证；真实 ColorMatch 命中/未命中、Custom 未注册错误、And 后续命中；点击详情和结果框；停止后续项、编辑期间迟到响应丢弃、换图清除报告 |
| 现有示例导入 | 逐个解析 `examples/complete_project/demo/ui` 中的 UI 定义，重新生成并导入，比较原生识别类型和全部 dataclass 参数 |
| 导入范围 | 仅支持当前 `maa.pipeline` 类型和 `recognition: {type, param}` 组合；正常 Python 导入别名可用；已移除的接口与旧组合格式拒绝接管，源文件保持原样 |
| 显示名称与图片选择 | 显示名称的保存、搜索、重开和重新导入；属性名不变；缩略图与透明通道、中文路径、图片多选、排序、搜索后保留选择、取消、目录边界和认证 |
| 保守 AST 接管 | 动态参数、方法、装饰器、重复赋值、不支持的字段等整文件拒绝；返回文件和行号；预览不改变源文件，明确接管后才能覆盖 |
| 组合 | 结构化原生内联组合、嵌套 And/Or、成员顺序和 box_index；重复生成一致性、循环/缺失引用拒绝；内联展开不依赖其他生成模块 |
| 路径和资源 | 路径逃逸、符号链接逃逸、Windows 保留文件名、模块/包冲突；资源重命名预览与引用同步；依赖图片删除拒绝，包含大小写和分隔符不同的引用 |
| 写入保护 | 手改生成文件冲突、显式重新导入、预览后外部改动、Windows 换行转换；暂存写入失败和替换失败恢复已有文件 |
| 坐标和颜色 | 浏览器 DPR=2、画布放大 200%、平移后裁图仍得到 `[60, 40, 40, 30]`；裁图像素和 RGB 保持一致；ColorMatch 实际验证 RGB/BGR 通道转换 |
| 原生识别 | 真实 TemplateMatch 命中和未命中、修改模板后重新加载资源；FeatureMatch、ColorMatch、嵌套 And/Or 命中、And 未命中和 box_index 结果框选择 |
| 自定义识别 | 复制现有项目多点颜色算法，通过显式 `module:callable` hook 注册，真实命中并返回正确框 |
| 错误区分 | OCR 默认/指定子目录模型缺失、自定义名称未注册均为具体执行错误；正常未命中为 `hit=false` |
| 工作进程 | 超时终止后下一次请求重建；断连后截图拒绝、失效窗口拒绝；超时与原生失败不返回伪命中 |
| Win32 实际截图 | 原生发现、连接、PrintWindow 截图；测试自建屏幕外窗口不激活其他应用；关闭目标后的截图失败清除连接状态 |
| 输入边界 | 后端没有 click/swipe/input/action/shell/task 接口；识别通过 Inspector；离线控制器输入回调拒绝执行 |
| 独立分发 | 构建 sdist 和 wheel，在隔离 uv 环境安装本地 MaaPlus 与 Studio wheel；确认导入路径不在源码目录；网页、所有 JS/CSS、会话 API、CLI 重复生成和生成模块导入均通过；安装包内原生 UI 可再次导入，移除的接口不可导入 |

测试入口见 `tests/test_project.py`、`test_server.py`、`test_native.py`、`test_windows_capture.py`、`frontend/tests/studio.spec.ts`、`frontend/tests/page-inspection.spec.ts`。浏览器项目和输入截图均为测试创建的临时文件，不连接设备。安装测试脚本为 `tests/wheel_smoke.py`：

```powershell
# 在仓库根目录完成 uv build 和 uv build --project studio 后执行
uv run --isolated --no-project `
  --with ./dist/maaplus-1.4.0-py3-none-any.whl `
  --with ./studio/dist/maaplus_studio-0.1.0-py3-none-any.whl `
  python -B ./studio/tests/wheel_smoke.py
```

## 尚未完成的外部设备/模型验收

- **ADB 实机截图**：本轮未显式开启实机用例，相关测试跳过。连接设备后按 README 的环境变量说明运行，不能将本轮结果算作实机截图通过。
- **OCR 成功识别**：本次未下载 OCR 模型；已验证模型缺失的具体错误、参数导入/生成和编辑表单，未声称完成 OCR 文字命中的模型验收。
- Win32 实际截图验收覆盖 PrintWindow。FramePool、ScreenDC、GDI、DXGI_DesktopDup_Window 选项已接入原生枚举，未逐一对外部应用验收。Chrome 未单独执行浏览器套件。

## 已记录的实现取舍

当前 Windows `maafw 5.13.1` wheel 缺少 `MaaDbgControlUnit.dll`，无法创建 DbgController。Studio 在库存在时优先使用 DbgController，否则使用官方 CustomController 扩展提供静态 BGR 帧，并拒绝全部输入操作。原生 Resource、Tasker 和 Inspector 保持真实运行，模板/特征/颜色/组合/自定义集成测试覆盖该路径。

首版为单用户、单项目、单活动设备连接；保存事务处理进程内写入失败，不声称具备断电级多文件原子性。算法源码和模型由项目维护，业务代码引用变更需要开发者同步。测试环境出现 Starlette 测试客户端的上游弃用警告，不影响上述通过结果。
