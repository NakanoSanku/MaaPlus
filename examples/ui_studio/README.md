# UI Studio 完整项目示例

这是一个可生成的项目示例，而不是只有 UI 类片段。它包含完整截图、裁剪模板、生成 Python、组合识别和 9 个正反样本断言。

从 MaaPlus 仓库根目录运行：

```bash
python -m pip install -e ".[studio,dev]"
python -m maaplus_studio --project ./studio-demo demo
python -m maaplus_studio --project ./studio-demo gui
python -m maaplus_studio --project ./studio-demo check --strict
python -m maaplus_studio --project ./studio-demo test
```

`demo` 拒绝覆盖已有项目。三个截图为可重复生成的合成素材，不需要连接模拟器，也不包含游戏账号信息。真正的识别测试仍依赖 MaaPlus 与 MaaFramework 原生库。

生成器实现在 `maaplus_studio/demo.py`，可作为通过 Python API 创建项目、页面、元素和断言的完整示例。项目分层、MaaYYS 接入方法、坐标规则和手工验收见 [UI Studio 使用指南](../../docs/ui-studio.md)。

实际设备验收：发现或手动连接模拟器 → 开启预览 → 保存一帧 → 同图裁剪两个元素 → 设置各自 ROI → 生成 Python → 测试当前截图 → 换页面抓取负样本 → 标记“不应命中” → 全部回归 → 回溯原图确认来源。
