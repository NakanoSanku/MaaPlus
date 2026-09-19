# MaaPlus Studio

独立安装的本地 UI 层创建与管理工具。通过截图建立定位项，在真实 MaaFramework 中验证，再生成任务和导航代码可直接引用的 Python UI 类。

`打开项目 → 获取截图 → 创建或导入 UI → 编辑参数 → 验证识别 → 检查差异 → 保存配置和 Python`

## 启动

在 MaaPlus 仓库根目录运行，Python 环境和锁文件由 Studio 子项目单独管理：

```powershell
uv sync --project studio --locked --dev
uv run --project studio maaplus-studio --project examples/complete_project
```

命令默认打开浏览器，支持 Windows 上的 Chrome 和 Edge。使用 `--no-browser` 仅输出访问链接，`--port 8765` 指定端口；默认自动选择空闲端口。服务仅监听 `127.0.0.1`，访问时使用终端输出的完整会话链接。按 Ctrl+C 关闭服务和原生工作进程。

网页文件已经包含在包内，使用者不需要安装 Node.js。拿到独立发布的 wheel 后可安装到工具环境：

```powershell
uv tool install ./maaplus_studio-0.1.0-py3-none-any.whl
maaplus-studio --project D:/Projects/MyMaaProject
```

自定义识别所依赖的第三方 Python 包也需要安装到 Studio 的环境中。仓库开发时用 `uv add --project studio <包>`；使用工具环境时可用 `uv tool install --with <包> <wheel>`。

## 第一次编辑

1. 在“项目设置”填写资源目录和 Python 输出目录，均相对于当前项目。现有完整示例使用 `resource` 和 `demo/ui`。
2. 导入、拖入或粘贴截图，或点击“选择设备 / 窗口”连接原生控制器。
3. 创建 UI 分组，填写模块和类名，如 `login`、`LoginUI`。模块可用 `screens.login` 表示子目录。一个模块可以有多个类。
4. 创建定位项，如 Python 属性名 `START`、显示名称“开始按钮”。显示名称可在右侧直接修改，项目树和组合成员优先显示它，搜索同时匹配显示名称和属性名；留空时显示属性名。选择识别方式，编辑常用参数，或在“高级原生参数”中编辑 JSON 并点击“应用 JSON”。
5. 点击“选择模板图片”，从资源目录浏览缩略图、搜索路径并多选，确认后加入当前 Template/Feature 定位项。已选模板可移除或上移；多个阈值按模板顺序对应，调整顺序后应同步核对阈值。“手动编辑路径”保留直接输入方式。在画布选择 ROI 后点击“应用为 ROI”；切换“裁图”并“保存模板”会创建 `resource/image/…png` 并自动选中。
6. 点击“验证识别”测试单项，或点击“测试当前页面”批量验证选中 UI 分组的全部定位项。查看命中、未命中、执行错误、耗时及原生详情；编辑参数或更换截图会清除旧结果。
7. 点击“保存并生成”，检查配置和代码差异，再确认写入。

左侧管理 UI 类和定位项；中间画布支持滚轮缩放、平移模式、空格拖动、中键拖动、适应画布和 1:1。底部显示原始像素坐标、RGB 和十六进制颜色。右侧可精确编辑 ROI 的 `x, y, width, height`，`[0, 0, 0, 0]` 表示全图。

**画布缩放仅影响显示。ROI、裁图和识别结果始终使用实际识别帧的像素坐标。** 设备的截图缩放设置应与业务运行时一致；截图的原始尺寸、来源和缩放设置保存在 `.maaplus/studio/shots` 的元数据中。

## 识别和组合

选中左侧 UI 分组或其中的定位项，准备好截图后，点击底部“测试当前页面”。一次测试使用同一份配置和同一张截图，按项目树顺序测试该分组的全部导出定位项；搜索筛选不影响范围，组合的内联成员随所属组合验证。

“页面测试”面板显示进度、命中/未命中/错误数量和每项耗时。点击结果可切换对应定位项，在画布查看命中框，在列表下方查看原生详情或具体错误。每项只带入自身及递归依赖的定义，其他定位项的参数错误不会阻断此项；单项执行错误或超时后继续测试后续项。超时仍按单项 30 秒处理并重建原生工作进程。

“停止测试”会等待当前项返回，不再测试剩余项，未执行项显示“未测试”。修改草稿时停止后续测试并清除结果；更换截图也会清除结果，迟到的响应不会覆盖新状态。批量测试复用只读识别接口，不采集新截图或向设备发送输入。

| 编辑类型 | 生成的构造 | 常用表单 |
| --- | --- | --- |
| TemplateMatch | `maa.pipeline.JTemplateMatch` | 模板相对路径、阈值、ROI |
| OCR | `maa.pipeline.JOCR` | 期望文字/正则、置信度、仅识别、ROI |
| FeatureMatch | `maa.pipeline.JFeatureMatch` | 模板、算法、匹配点数、距离比值、ROI |
| ColorMatch | `maa.pipeline.JColorMatch` | RGB/HSV 上下限、像素数、ROI |
| And / Or | `maa.pipeline.JAnd` / `maa.pipeline.JOr` | 有序成员、And 的结果框索引 |
| Custom | `maa.pipeline.JCustomRecognition` | 注册名称和原生 JSON 参数 |

所有类型的其余原生字段通过高级 JSON 设置，保存和验证使用相同的参数转换逻辑。模板和期望文字可以一行填写一个。组合成员通过稳定 ID 引用，支持跨类、跨模块；点击成员可编辑导入的内联识别。重命名不破坏组合关系，循环引用和删除仍被引用的定位项会被拒绝。

生成的 UI 文件只导入 `maa.pipeline` 中的原生识别类型。组合成员展开为 `all_of` / `any_of` 中的内联识别字典，嵌套组合、成员顺序和 `box_index` 保持原生语义，不生成 UI 模块间的相互导入。同一配置重复生成得到相同文件内容。名称与识别构造重名时，生成器会给导入名称添加别名。

资源列表显示图片引用。重命名图片会同时预览并更新配置、文件和 Python；被草稿或已保存配置引用的图片不能直接删除。删除定位项后先保存配置，才可删除其不再使用的图片。

## ADB 和 Win32 截图

- **ADB**：可填写 `adb.exe` 完整路径，刷新设备列表并明确选中目标。内部使用 `Toolkit.find_adb_devices()` 和原生 `AdbController`。
- **Win32**：刷新窗口列表，按标题或窗口类名筛选。支持 FramePool、PrintWindow、ScreenDC、GDI、DXGI_DesktopDup_Window 截图方式，内部使用原生 `Win32Controller`。
- 两种控制器均可使用 MaaFramework 默认缩放、原始分辨率、指定短边或长边。一次连接一个目标，截图手动刷新。

设备接口只有发现、连接、断开和截图；画布拖动不会向设备发送鼠标、键盘、触摸、ADB shell 或任务动作。

所有原生对象在独立工作进程中持有，操作串行执行。识别默认 30 秒、截图 20 秒、发现/连接 45 秒超时；超时结束工作进程并在下一次请求重建，活动设备需要重新连接。每次验证重新加载 Resource 和 Tasker，使修改后的模板立即生效。

离线截图优先使用原生 `DbgController`。当前 Windows `maafw 5.13.1` wheel 未附带 `MaaDbgControlUnit.dll`，这时使用 MaaFramework 的原生 `CustomController` 扩展提供静态 BGR 图像，所有输入回调返回失败。识别仍调用真实 `Inspector` 和 MaaFramework，不模拟识别结果。

## 导入已有 Python UI

先将输出目录设置为现有 UI 目录，再点击“导入 Python”，逐个选择模块。预览展示转换出的类、定位项、参数和组合；点击“接入配置草稿”后，保存时才允许接管源文件。取消预览不会授予覆盖权限。一个文件有不支持的代码时，整个文件拒绝接管，并显示文件、行号和原因。

仅支持从 `maa.pipeline` 导入原生识别类型，包括普通导入、Python 导入别名、静态 UI 类和字面量具名参数。`JAnd/JOr` 的成员统一使用 `{"recognition": {"type": "…", "param": {…}}}` 结构，并支持按此格式嵌套。导入过程只解析和编译检查 AST，不执行源文件，不进行历史接口转换。

类方法、继承、装饰器、动态参数、`**kwargs`、其他模块级逻辑、流水线节点名组合引用及无法保留的内联组合字段需要人工整理。可将 UI 静态定义移到单独模块再导入。模块、类名和导出属性名会保留；业务代码引用由开发者维护。

接管后以 `maaplus-studio.json` 为唯一编辑来源。生成文件统一换行后的 SHA-256 记录在配置中，兼容 Git 的 LF/CRLF 转换；手动编辑生成文件后，工具报告冲突并停止覆盖。需要保留手工修改时重新导入该文件并检查转换预览。保存时先暂存全部新内容，再次校验磁盘文件后替换；写入或替换失败时恢复本次变更的原始文件。

## 配置与命令行生成

当前配置版本号为 `1`。`groups` 描述模块和 UI 类，`locators` 存储识别类型、原生参数和成员 ID。定位项的 `label` 保存显示名称，允许留空；`name` 保存 Python 属性名。显示名称不会写入 Python，重新导入同名类与属性时保留配置中的显示名称。`export: false` 表示组合内联成员。`managed_files` 由工具维护，不应手工更改。

```json
{
  "version": 1,
  "resource_dir": "resource",
  "output_dir": "demo/ui",
  "resource_hook": "",
  "groups": [{"id": "login", "module": "login", "class_name": "LoginUI", "label": "登录页"}],
  "locators": [{
    "id": "login-start", "group_id": "login", "name": "START", "label": "开始按钮",
    "kind": "TemplateMatch", "params": {"template": ["login/start.png"], "threshold": [0.85]},
    "children": [], "export": true
  }],
  "managed_files": {}
}
```

在已经保存的项目中重新生成，无需启动网页：

```powershell
maaplus-studio generate --project D:/Projects/MyMaaProject
# 仓库开发环境：
uv run --project studio maaplus-studio generate --project examples/complete_project
```

输出如 `demo/ui/login.py`，业务代码继续使用 `from demo.ui.login import LoginUI` 和 `tick.match(LoginUI.START)`。CLI 同样执行配置校验、手改冲突检查和事务写入。截图、原生日志等临时数据放入已有忽略目录 `.maaplus`；持久配置、PNG 资源和生成的 Python 应纳入版本控制。

## OCR 与自定义识别扩展

OCR 模型由项目提供。默认目录为 `resource/model/ocr`，需要 `rec.onnx`、`keys.txt`，普通检测识别还需要 `det.onnx`；`only_rec` 不需要检测模型。原生 `model` 参数使用相对于 `model/ocr` 的子目录。缺失文件会作为执行错误列出。模型结构和下载来源见 [MaaFramework 资源说明](https://github.com/MaaXYZ/MaaFramework/blob/v5.13.1/docs/en_us/1.1-QuickStarted.md) 与 [OCR 协议](https://github.com/MaaXYZ/MaaFramework/blob/v5.13.1/docs/en_us/3.1-PipelineProtocol.md#ocr)。首版不下载和管理神经网络模型。

在项目中维护注册函数，例如完整示例可增加 `studio_support.py`：

```python
from maa.resource import Resource
from demo.custom_recognition import create_custom_recognitions


def register(resource: Resource) -> None:
    # resource 已完成 post_bundle；这里只需注册项目自己的算法。
    for name, callback in create_custom_recognitions().items():
        if not resource.register_custom_recognition(name, callback):
            raise RuntimeError(f"注册失败：{name}")
```

将“资源扩展函数”设置为 `studio_support:register`。Custom 定位项使用 `custom_recognition="MultiPointColor"`，高级 JSON 中设置 `custom_recognition_param={"tolerance": 12}`。函数只在实际验证时执行；未注册的名称会报告明确错误。运行任务时仍由业务 bootstrap 注册相同算法。Studio 不封装 MaaPlus 的控制器创建方式。

## 开发、构建和验收

Python 使用 `uv.lock`，前端使用 `pnpm-lock.yaml`，Node LTS 版本见 `.node-version`。版本选择核对了 [React 稳定线](https://react.dev/versions)、[Vite 支持线](https://vite.dev/releases)、[Node 发布状态](https://nodejs.org/en/about/previous-releases) 和各包发布信息。当前锁定 React 19.3、Vite 8.3、Node 24.18 LTS、FastAPI 0.141.1、Uvicorn 0.53.0、MaaFramework 5.13.1。

在仓库根目录：

```powershell
uv sync --project studio --locked --dev
pnpm --dir studio/frontend install --frozen-lockfile
pnpm --dir studio/frontend build
uv build --project studio
```

Vite 输出到 `src/maaplus_studio/web`，静态文件随 wheel 分发。修改前端后必须重新构建；发布时只发布 `studio/dist` 中的独立包。根包 MaaPlus 不引入 FastAPI 或前端依赖。安装尚未发布的本地 MaaPlus 和 Studio 两个 wheel 可用 `uv tool install --with <maaplus-wheel> <studio-wheel>`。

```powershell
# 核心回归
uv run --locked python -B -m pytest -q -p no:cacheprovider
# Studio 后端与真实原生识别
uv run --project studio --locked python -B -m pytest -q -p no:cacheprovider studio/tests
# Chrome/Edge 目标中的 Edge，DPR=2，临时测试项目
pnpm --dir studio/frontend test
```

ADB 实机验收显式开启，可指定执行文件和设备地址：

```powershell
$env:STUDIO_TEST_ADB = "1"
$env:STUDIO_ADB_PATH = "C:/Android/platform-tools/adb.exe"
$env:STUDIO_ADB_SERIAL = "127.0.0.1:5555"
uv run --project studio --locked python -B -m pytest -q -rs studio/tests/test_adb_capture.py
```

没有目标或存在多个目标且未指定地址时跳过，不自动任选设备。完整验证结果、环境和未验收项记录在 [验收记录](ACCEPTANCE.md)。

后端按职责分为 `models.py`（配置及原生转换）、`generator.py`、`importer.py`、`storage.py`（路径与事务）、`worker.py`（进程边界）和 `server.py`（同源会话 API）。新增识别类型时同步扩展原生类型映射、AST 规则和前端表单；生成器从类型映射获取原生构造，并复用验证识别的配置编译逻辑。用真实识别与导入/生成等价测试验证扩展。
