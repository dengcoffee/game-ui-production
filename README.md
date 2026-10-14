# game-ui-production

一套**全局安装、按项目配置、可持续迭代**的游戏 UI 素材生产 Skill（面向 Codex / OpenCode 类编码代理），用于从已确认的视觉参考中识别分层、提取、复用和生产游戏 UI 素材，并以统一 Manifest 输出离线视觉对照、冻结交付和 Godot 4 组件。

> 首个落地项目为《东方年代记》Godot 4 重制工程的试点验证；全局工具本身不携带任何项目的名称、画风、分辨率或路径。

## 核心理念

**项目级风格先行、共享组件不重复生成、确定性工具管几何与文字、图像素材承载美术、Godot 承载交互、验收通过才接入。**

- **单一数据来源**：网页预览、素材清单、Godot 接入读取同一个版本化 UI Manifest，禁止各自猜测坐标。
- **图像生产三路径**：优先复用已确认资源 → 其次对参考图做明确范围的提取/修复 → 缺项再单独生成。
- **严格生产范围**：默认只生产窗口/边框/按钮/底纹/光效等 UI 部件；人物立绘、道具 ICON、地图等内容资源默认引用或占位。
- **几何是硬约束，美术相似度允许合理容差**：画布、宽高、位置、锚点、间距未经授权不得改变；模糊/遮挡区域允许重绘，不以非零像素差反复返修。
- **状态机验收**：`draft → candidate → approved_reference → assets_verified → visual_approved → engine_verified`，用户确认不可伪造，技术测试不能自动晋升为视觉批准。

## 功能一览

| 能力 | 说明 |
|---|---|
| 项目发现与接管 | 只读盘点已有工程，非破坏性接管现有目录与规范 |
| 13 类素材判定 | 底板、窗口框、按钮、页签、头像框、道具格、轨道、滑块、进度槽、进度填充、装饰、图标、字体；无法定类必须询问用户 |
| 轻量候选分层 | 矩形裁切、边缘连通去底、显式灰度蒙版，输出独立候选与固定坐标组装预览 |
| 素材包交接 | `prepare / confirm / validate` 产出可移动的独立候选包（assets/ + review/ + package.json） |
| 素材库 | 按项目/类型索引已确认包，拒绝未确认、测试或被篡改的包 |
| 离线视觉工作台 | `file://` 直接打开的静态 HTML：并排、同步缩放、透明叠加、Pixelmatch 差异热图、多系统多状态切换 |
| 压力测试 | 空态、超长文本、最大列表、极端数值、缺字等真实数据压力样例 |
| Godot 4 适配器 | 冻结 Manifest → 独立图层、实时文字、状态、输入、Tween、滚动、嵌套弹窗；`engine_verify.py` 实机截图与差异定位 |
| 版本与安全 | 候选/正式区分离、有限快照、可恢复归档清理、冻结包篡改检测、Schema 1→2 迁移 |

## 目录结构

```
skill/game-ui-production/     Skill 主体（全局安装源）
├── SKILL.md                  执行协议总纲
├── references/               数据契约、生产操作、分类判定、Godot 接入等参考文档
├── scripts/                  production.py / layers.py / asset_package.py / library.py 等工具
└── requirements.txt          Python 依赖
tests/                        单元与集成测试（隔离夹具）
tools/                        安装器、全流程试运行等辅助脚本
output/                       试运行产物（工作台、交付包、引擎验证结果）
game-ui-production.md         原始实施方案（设计任务书）
开发与验收.md                  当前版本能力、验证证据与已知边界
```

## 快速开始

依赖：Python 3.11+

```powershell
# 安装依赖
.venv/Scripts/python.exe -m pip install -r skill/game-ui-production/requirements.txt

# 运行测试
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v

# 完整流程试运行（生成两套模拟项目的对照工作台与冻结交付）
.venv/Scripts/python.exe tools/full_trial.py --out output/<new-trial> --font <real-font>

# Godot 4 引擎专项验证
.venv/Scripts/python.exe skill/game-ui-production/scripts/engine_verify.py `
  --export <trial/godot-0> --delivery <trial/project-0/delivery> `
  --godot <console-executable> --out output/<new-engine-check>

# 全局安装 / 更新 / 回退
.venv/Scripts/python.exe tools/install.py --update
.venv/Scripts/python.exe tools/install.py --update --restore <verified-snapshot-directory>
```

安装到全局 Skill 目录后，在任意已配置项目中用自然语言请求：

> 使用 $game-ui-production，按当前项目已确认风格完成指定系统 UI。

用户只需审核关键视觉方向、提供截图反馈和最终确认；计划、文件、命令与提示词由代理组织。

## 使用流程概览

1. **发现与方向** — `discover` 只读盘点项目，新项目集中确认一次美术方向。
2. **参考身份核对** — 校验参考图路径、SHA-256、尺寸与确认范围，不凭文件名选图。
3. **尺寸基线确认** — 明确逻辑画布与各面板目标几何，不把参考图片像素当已确认尺寸。
4. **系统计划** — 从功能稿整理系统/页面/状态/共享母版，页面只记录差异。
5. **素材生产** — 复用 → 提取 → 生成；候选分层、分类判定、独立候选包。
6. **检查与对照** — 真实字体合成、离线工作台逐部件视觉匹配。
7. **返修与压力测试** — 按用户截图定位根因，增量重建影响范围。
8. **确认与冻结** — 记录真实用户证据，freeze 保存可复现交付包。
9. **引擎接入** — Godot 组件导出与实机验证，业务绑定由游戏负责。
10. **维护收尾** — 单一权威状态索引、安全清理与恢复。

## 依赖与开源复用

- Pillow、jsonschema（Draft 2020-12）、fontTools
- [Pixelmatch](https://github.com/mapbox/pixelmatch)（ISC，唯一改动为移除 ESM export 以嵌入离线 script）
- Godot 4 复用 TextureRect / FontFile / Button / ScrollContainer / Tween，不重复开发引擎能力

## 已知边界

- 不承诺语义分割、被遮挡图层无损重建或 AI 生图像素级锁定。
- 浏览器与引擎字体栅格化存在约 1–2% 文本区域差异，须专项检查而非以数值宣称视觉通过。
- 测试批准仅在隔离夹具内标记 `test_only`，不会进入生产工程。

详细的能力边界与验证证据见 [开发与验收.md](开发与验收.md)。
