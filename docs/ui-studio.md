# MaaPlus UI Studio

UI Studio 是开发工具，不是游戏运行器的最终用户 UI。它管理截图、模板、UI Python 定义与识别回归，**不会执行点击、滑动或 Flow**。

```text
项目 → 连接 / 导入 → 完整截图 → 模板裁剪 / ROI → 元素定义
                         ↓                       ↓
                    正反测试样本 ←──────────── Python 生成
                         ↓                       ↓
                    可视化回归 ←────── MaaPlus Runtime.match
```

## 安装与启动

在包含这项功能的 MaaPlus 仓库根目录，使用项目要求的 Python 3.14：

```bash
python -m pip install -e ".[studio,dev]"
maaplus-studio
# 等价入口
python -m maaplus_studio
```

也可以用 `uv sync --extra studio --extra dev`，然后 `uv run maaplus-studio`。本变更增加了构建后端和可选依赖；旧 `uv.lock` 需要首次 `uv sync` 重新解析，不能直接使用旧锁的 `--frozen` 模式。

Tkinter 必须可用；先运行 `python -m tkinter` 检查。Linux 需要与所用 Python 配套的 Tk 支持和图形会话；Windows 使用包含 Tcl/Tk 的 Python 安装。CLI 的 `init/check/generate` 不需要显示器，也不导入 MaaFramework；图像管理需要 Pillow。

## 先运行完整示例

无需模拟器即可生成三个合成截图、两个模板、组合识别、三组测试样本：

```bash
maaplus-studio --project ./studio-demo demo
maaplus-studio --project ./studio-demo check --strict
maaplus-studio --project ./studio-demo gui
maaplus-studio --project ./studio-demo test
```

最后一条使用真正的 MaaFramework，而不是另一套近似匹配算法。示例共有 **9 个识别断言**：源截图、按钮移位的正样本、按钮不存在的负样本，各验证 `CHALLENGE`、`BACK`、`READY`。示例是工具演示，不是游戏素材，也不证明真实游戏的识别质量。

报告位于 `.debug/studio-report/index.html`，同时输出 `report.json` 和带框截图。绿框是实际识别框，黄框是预期框。每次运行使用独立的 `runs/<id>/` 图像目录，避免旧报告混入新一轮的截图。

## 接入现有 MaaYYS 项目

在 Studio 所在的 Python 环境中执行；`--project` 指向 MaaYYS，而不是 MaaPlus：

```bash
maaplus-studio --project ../MaaYYS init \
  --ui maayys/ui/generated \
  --resource resource \
  --fixtures tests/ui \
  --width 1280 --height 720

maaplus-studio --project ../MaaYYS gui
```

Windows PowerShell 中将初始化命令写成一行，或使用 PowerShell 的续行语法。路径支持中文和空格；命令行参数含空格时加引号。

生成文件和既有 UI Python 文件分开放置，避免覆盖手写常量、跨页引用和业务组合。可以逐个页面迁移，不需要重构全部 Flow。例如：

```python
# maayys/ui/awakening.py：继续由开发者维护
from maaplus import FirstOf
from .generated.awakening import AwakeningChallengeGeneratedUI

class AwakeningChallengeUI(AwakeningChallengeGeneratedUI):
    MARKER = FirstOf(
        AwakeningChallengeGeneratedUI.CHALLENGE,
        AwakeningChallengeGeneratedUI.BACK,
    )
```

生成类名可以是 `AwakeningChallengeUI`，不强制 `Generated` 后缀。上例仅用于明确手写层与生成层的边界。

## 实际操作流程

### 1. 创建项目与页面

新建项目时设置项目根目录、UI Python 目录、MaaFramework 资源目录、测试截图目录和运行时截图分辨率。目录均是项目相对路径；三类目录不得相互包含。已有项目配置不会被覆盖。

新增页面时设置 Python 类名，例如 `AwakeningChallengeUI`，以及文件，例如 `maayys/ui/generated/awakening.py`。多个页面可以共用一个文件；同一文件中不能有同名类。“页面设置”可以改类名或文件位置。

代码输出必须在配置的 UI 目录内，且不能直接写 `__init__.py`。类名、常量名使用非关键字的 ASCII Python 标识符，说明文字和 OCR 内容可以是中文。

### 2. 连接、预览、冻结截图

“发现设备”使用 MaaFramework Toolkit；可以先填写模拟器自带 adb 的路径。选择设备后点击“连接”。发现不到设备时，使用“手动连接”指定 adb 可执行文件和地址／序列号。

“实时预览”以串行方式获取新截图，**不会堆积并发截图请求**。默认轮询间隔 600 ms，真实刷新速度取决于设备；不是视频帧率承诺。“抓取一帧”立即停止预览并显示新帧。“保存当前截图”保存眼前这一帧，而不是另抓一帧。框选也会冻结预览。

连接时调用 `set_screenshot_target_short_side()`，与项目的短边一致。完整帧尺寸必须与项目配置精确相同；不同宽高比、竖屏或错误尺寸都会提示错误，**不会静默拉伸截图**。业务运行器必须使用同样的控制器缩放设置。

这里的“原图”指 **送入识别引擎的完整、归一化截图**，不是裁剪小图，也不是另存的设备原始分辨率图。元数据记录设备来源、原始分辨率、实际帧分辨率和缩放短边。导入图片只记录导入文件名，不猜测其真实拍摄时间。

### 3. 一张截图定义多个元素

选择“模板裁剪”，拖出 `CHALLENGE` 的模板框，再选择“识别 ROI”设置搜索范围。输入常量名、阈值并保存，随后点击“新元素”继续裁剪 `BACK`。截图不会重复复制。

三种框含义不同：

| 框 | 用途 |
|---|---|
| 模板裁剪框 | 从完整源截图截取模板图片 |
| 识别 ROI | MaaFramework 搜索元素的区域，可以比模板大 |
| 测试预期框 | 断言实际匹配位置，防止命中错误的相似按钮 |

坐标始终是完整截图的 `x, y, width, height`。预览缩放和滚动会进行坐标换算。可以手动修改坐标；超界、非整数、空框和比 ROI 更大的模板会被拒绝。

已有元素默认沿用原图。切到另一张截图后，仅修改阈值或常量名，不会偷偷重新裁剪。替换模板时点击“从当前截图重新取样”，再保存。旧模板保留，方便排查或回退。

当前可视化支持 `Template`、`OCR`、`FirstOf`、`AllOf`。OCR 的 `expected` 填 JSON 字符串数组，例如 `["挑战", "开始"]`；识别区域和阈值同样可配置。组合引用填写当前页已有的常量名，逗号分隔；引用必须在生成顺序中先定义，禁止循环。`AllOf.box_index` 指定使用哪个子识别结果框。

OCR 模型由项目自己的 MaaFramework 资源提供。工具**不自动下载模型**；缺少模型或资源加载失败应当视为执行错误，而不是识别未命中。

### 4. 生成 Python

保存元素后点击“生成 Python”。预览区在未写文件时也能显示待生成代码，例如：

```python
from maaplus import AllOf, FirstOf, OCR, Template

class AwakeningChallengeUI:
    CHALLENGE = Template(
        template=["studio/<stable-element-id>/<content-sha256>.png"],
        threshold=[0.85],
        roi=(1030, 550, 220, 140),
    )
```

实际文件还包含页面 ID、元素 ID、源截图 ID 和裁剪坐标注释。模板路径以 MaaFramework `resource/image` 为基准，不把测试原图作为运行时资源。

项目元数据是 Studio 管理范围内的事实来源，Python 是确定性生成物。生成时先检查全部目标文件：没有登记的已有文件，以及在工具外被修改过的已生成文件，都**拒绝覆盖**，不是靠文件头注释判断。已有生成文件的替换前版本保存在 `.studio-backups/`。

本工具不执行任意 UI Python，也不尝试把手写代码反向解析并接管。测试前要求磁盘上的生成文件与元数据一致，再通过受限 AST 读取其中的实际 Locator 构造表达式。构造器只允许 MaaPlus 的四种已支持接口，没有 `exec()` 或任意模块导入。

### 5. 测试与可视化

“测试当前截图”使用保存的当前完整帧；“实时识别”先从已连接模拟器取得新帧，保存为可溯源截图，再对该帧执行同一套识别。所有元素在一次页面测试中使用同一张图。测试不会点击设备。

识别结果包括命中状态、实际框、原生 detail 和耗时；可视化叠加在截图上。原生 detail 中可包含算法给出的得分和文字，工具不会把它们伪装成统一概率。

先选择元素，在不同截图上分别标记“应命中”或“不应命中”。对容易误识别的按钮，用“测试预期框”标出正确位置再标记应命中；默认要求实际框与预期框的 IoU 至少 0.5。只标“应命中”而不画预期框时仅断言命中。

“全部回归”只统计显式标记的断言。未标注的截图／元素**不等于通过**；没有断言时测试拒绝以成功状态退出。引擎异常与未命中严格区分，因此模型缺失、资源损坏或进程错误不会让负样本“通过”。

资源检查会提醒无断言、缺负样本、只测试了裁剪源图。至少额外保存另一时刻的正样本，并加入弹窗遮挡、按钮不存在、其他相似页面等负样本，避免源图自匹配带来的虚假信心。

## 资源与代码的双向溯源

```text
MaaYYS/
├── maaplus-studio.json                 # 页面、元素、稳定 ID、来源、断言、生成文件哈希
├── maayys/ui/generated/awakening.py    # 运行时使用的纯 Python 定义
├── resource/
│   ├── image/studio/<element-id>/<hash>.png
│   └── pipeline/
├── tests/ui/screenshots/<hash>.png     # 完整截图，按内容去重
├── .studio-backups/<hash>.py           # 生成代码替换前的备份
└── .debug/studio-report/               # HTML、JSON、可视化结果
```

从元素点击“回溯裁剪原图”，可查看完整截图、裁剪框、输出文件和测试用例。从截图列表打开原图，诊断区列出这张图关联的所有元素、模板和 Python 文件。相同像素图再次入库时追加来源观察记录，而不是重复创建文件。

删除元素会清除对应断言；被组合识别引用的元素不能直接删除。删除页面会清除其元素和断言，但不自动删除截图、模板或旧 Python。资源检查报告未引用裁剪图和遗留生成文件，清理交给开发者审核，避免破坏手写代码的外部引用。

截图／模板使用 SHA-256 检查完整性；项目保存使用同目录临时文件和替换。生成代码会预检查所有目标，并在普通写入异常时回滚已替换文件。它不是跨所有文件的断电事务：异常中断后仍应运行 `check`，确认一致性再使用。

并发编辑通过短时写锁和项目版本检查阻止覆盖。提示版本冲突时重新打开项目。异常退出遗留 `.maaplus-studio.lock` 时，先确认没有 Studio 进程，再手动删除锁文件。

建议将 `maaplus-studio.json`、生成 Python、模板和必要回归原图纳入版本管理；原图较多时可单独制定存储策略。截图可能包含账号信息，元数据可能包含设备地址，提交前先检查。将以下本地文件加入业务项目的 `.gitignore`：

```gitignore
.debug/
.studio-backups/
.maaplus-studio.lock
```

## CLI / CI

```bash
maaplus-studio --project ../MaaYYS generate
maaplus-studio --project ../MaaYYS check
maaplus-studio --project ../MaaYYS check --strict
maaplus-studio --project ../MaaYYS test --timeout 90 --report .debug/ui-regression
```

退出码：`0` 成功；`1` 检查发现问题或测试存在失败／错误；`2` 配置、依赖、无用例等运行前提错误。`check --strict` 将覆盖率警告也作为失败。

设备发现、连接、截图和识别运行在隔离子进程中，由后台线程串行通信。GUI 线程只负责交互。默认 GUI 单次原生请求超时 45 秒；CLI 可用 `--timeout` 调整。超时、停止／断开或关闭窗口都会终止工作进程；后续设备操作需要重连。退出测试不会发送游戏操作。

测试工具本身：

```bash
python -m pytest -q tests/test_studio.py tests/test_studio_gui.py
# Linux 有 Xvfb 时运行真实 Tk 控件测试
xvfb-run -a python -m pytest -q tests/test_studio.py tests/test_studio_gui.py
# 原生识别集成测试（Linux/macOS shell 语法）
MAAPLUS_STUDIO_NATIVE=1 python -m pytest -q tests/test_studio.py -k native
```

PowerShell 启用原生测试：先执行 `$env:MAAPLUS_STUDIO_NATIVE="1"`，再运行 pytest。原生测试使用合成图，不需要模拟器；模拟器实际连接、截图通道和游戏素材识别仍需本机验收。

## 当前边界

这版覆盖从取图到回归的主流程，不声称支持任意 MaaFramework Locator 或任意 Python 代码的双向编辑。暂不包含手写 UI 自动迁移、跨页组合编辑、模板 mask 编辑、多分辨率自动适配、Win32 设备连接、点击测试、OCR 模型下载和截图垃圾回收。高级参数与跨页复用继续放在手写 UI 包装层中。

模板来源截图到运行时模板、测试断言到生成 Python 的关联已经建立；不要把业务流程、任务调度或最终用户配置再塞进这个工具。
