# 生产操作

以下参数由 Codex 编制和执行；用户不需要操作 CLI。共用 Python 环境及项目配置。所有输出要求新路径。候选登记账本记录尝试/来源，status_source 记录当前确认状态，两者职责不同。

## 项目发现与初始化

```text
production.py discover --root <project-root>
production.py adopt --root <root> --out <project.json> --art-bible <relative-file> --documents <relative-file> ... --status-source <relative-file> --engine <engine> --canvas <w> <h>
production.py init --root <empty-root> --brief <explicit-art-brief.txt> --font <real-font-file> --canvas <w> <h> --engine <engine> --out <project.json>
```

discover 不推断确认。init/adopt 前先完成 SKILL.md 的尺寸基线确认：沿用当前工作区适用的明确尺寸记录，缺项或无法消解的冲突须先请用户确认；将明确的逻辑宽高传入 --canvas。adopt 只写新配置，保留原规范及目录。init 要求空白工程和明确 brief，创建候选 Art Bible/状态索引、复制字体；代表性样板由 Codex 按该 brief 规划并生产。没有工具默认画风，也不假称初始化即批准。

项目 rules 的可执行项：production_scope 默认 `["ui"]`，artistic_retry_budget 默认 2，candidate_dir 默认 `.ui-production/candidates`，max_upscale 默认 2，asset_constraints 是资产 ID→{alpha,size}，state_groups 是需保持源画布一致的 ID 分组；status_snapshot_limit 默认 8。protected_manifests 列出其他当前有效/已确认 Manifest 的项目相对路径，清理共同保护其资源；Codex 从权威索引填入完整清单。logical_canvas 记录项目方向，Manifest.canvas 是实际合成权威，Codex 应保持一致。

## 计划和 provider

```text
production.py plan --config <config> --manifest <manifest> --task <task.json> --out <request.json>
production.py capabilities
production.py prepare-provider --config <config> --request <request> --id <asset-id> --state <state> --operation <generate|edit_with_reference|transparent_asset> --out <call.json> [--references <project-relative-file> ...]
production.py provider-failure --config <config> --ticket <attempt-ticket> --reason <actual-error>
production.py import --config <config> --request <request> --file <returned-PNG> --id <asset-id> --state <state> --source <provenance> --license <license-status> --method <external|builtin_imagegen|extraction|repair> [--attempt <ticket>]
production.py attach --config <config> --manifest <manifest> --candidate <registered-relative-path> --id <stable-manifest-asset-id> --out <new-manifest>
```

task 包含 system、assets 列表。每资产必填 id、kind、purpose、display_size、states、alpha、allowed_changes；可添加 effects、完整边缘要求、视觉权重、内容差异及已有公共引用，都会注入提示词。content 还需 explicit_content_authorization 含该类别并通过项目白名单。项目规则不能替代用户授权。

prepare-provider 只准备真实调用参数，不生成图片。Codex 用当前可用图像工具执行 arguments，编辑先 view_image；返回实际 PNG 后 import 使用同一 ticket，避免重复计费式计数。预备/失败均消耗本请求、资产和状态的尝试预算；不靠改 request 时间戳重置预算。因根因或任务范围实质改变才重新规划。

当前内置实现是 Codex 主机的 image_gen.imagegen：生成、参考编辑和透明背景；Python 不调用该主机工具、不要求 API 密钥。每次会话检查接口能力，实际输出再验证。不能像素锁定。工具不可用时直接导入外部 PNG 并记录真实来源，不用虚假 placeholder 冒充结果。

import 核对计划输入未变、范围、重试数、实际 PNG、真实透明、非空 Alpha 主体；稳定 ID 下用内容哈希登记候选。attach 产生新 Manifest，并给出所有受影响页面。不得把生成画布大小误当可见主体或最终显示尺寸。

## 自动分层识别

有参考图的 UI 提取任务，先查看已核对身份的原图及本次适用的页面/状态，结合功能稿、实际显示尺寸和既有资源判断分层。以下是默认判断，项目已确认规格及用户明确要求优先；识别用于规划，不等于工具已经完成像素分割。

- **底图**：连续的公共底色与底纹按完整一张保留，不因列表、子面板或布局矩形切成碎块。与底图不可分且无需独立行为的固定美术结构可保留在底图；可干净分离的边框、装饰、阴影和光效按覆盖层处理，不把所有静态部件一概合并。
- **独立控件与覆盖层**：需要点击、独立复用、状态切换或动画的按钮、页签、框体及效果单独分层。按实际行为和组装职责拆分，不因颜色、材质或轮廓不同就拆，也不把每条框线、每片装饰机械拆成独立资源。
- **按钮**：默认提取完整控件美术，保留按钮自身底色、填充纹理、边框、固定装饰及完整阴影/光效，不得仅交付边框。按钮外部无关区域透明，内部是否透明以参考为准，不把按钮填充当作页面底图去掉；文字独立渲染，可变图标另层处理。只有需独立复用、状态切换或动画的部分才拆层；各状态使用一致画布、锚点及控件位置，并保留效果留边。
- **滑动条与滚动条**：轨道（线/槽）与滑块（可移动标记/滑动柄）分开提取，保留各自填充、边缘及效果；固定刻度归轨道，可独立变化的刻度或标记另层处理，不将所有标记一概当作滑块。记录方向、有效移动范围、滑块尺寸与锚点；滑块遮住的轨道部分无法直接提取时，明确记录补绘需求及来源。分层不等于已完成运行时交互绑定。
- **进度条**：槽底/外框与随数值变化的填充层分开，移动端点标记按行为另层处理。区分控件长度适配与进度变化：长度适配时，适合拉伸的条形素材保留两端端帽/装饰，仅沿长度方向拉伸中段，使用已有 grid 分段字段记录固定端部与伸缩区；有明显重复纹理时先判断平铺或裁切是否更合适，不拉伸整张图导致端帽、边框或纹理变形。进度变化优先按参考裁切显示填充；只有设计允许且效果经验证时才选择缩放中段等方案，不默认伸缩整个外框。当前 fill_binding 仅支持从左向右裁剪 0..1 比例，其他方向、平铺或移动端帽等行为须先核对工具及宿主能力，不能编造 Manifest 字段或宣称已接入。单张部分填充截图不能证明完整填充纹理已提取，缺失段按参考编辑或重制记录。
- **动态内容**：文字、数值、人物、头像和道具 ICON 与底图分开；文字保持实时，内容资源按已有授权引用或占位。头像框与头像本体职责不同，仍遵守 SKILL.md 的提取范围。
- **公共母版**：有多个页面/状态参考时，对照相同位置的轮廓、材质、装饰及变化，识别共享部分并复用同一资源 ID；不能仅凭位置或相似颜色认定相同。仅有一张参考时，将共享判断标为推定，不宣称已跨页验证。

提取前提供标注参考图或区域示意作为分层预览，附简短清单：区域/资源职责、整块保留或独立分层、共享范围、判断理由、来源路径及裁切/蒙版范围、处理方式（真实提取、已有资源复用、参考编辑或重新制作），并标出遮挡与无法确定的部分。写入现有项目规格/计划，不另建竞争索引。明确的部分继续执行，不新增逐层批准流程；只有歧义会影响底图完整性、共享身份或控件行为且现有依据无法消解时，才集中询问用户。

移除动态内容后，底图应保持连续，覆盖层无关区域应透明；被遮挡的像素及半透明效果不能声称精确恢复，需补绘时如实标为参考编辑并遵守尝试预算。按实际层序重新组装，与同尺寸、同状态参考对照，检查内容残留、重复底纹、接缝、缺失装饰和效果截断；依据差异修正分层判断后重建，技术检查通过不等于分层正确或用户视觉批准。

涉及上述控件时，视觉检查覆盖已声明按钮状态、滑块行程两端及中间、进度 0%/低值/50%/100%；有长度适配要求时同时检查目标长短尺寸，确认按钮填充未丢失、轨道连续、滑块对齐、端帽未变形、小进度无溢出且效果未截断。预览只能证明对应静态样例；运行时行为仍按 Godot 接入流程验证。

## 提取、质量与压力测试

```text
assets.py --source <image> --out <new-candidate.png> [--crop <left> <top> <right> <bottom>] [--alpha-mask <same-canvas-grayscale.png>]
production.py quality --config <config> --manifest <manifest>
production.py stress --config <config> --manifest <manifest> --cases <cases.json> --out <new-stress-directory>
```

assets.py 支持有明确几何的裁切与已有蒙版 Alpha 合成，保存哈希、bounds 和来源，不自动分割、不补回遮挡。复杂对象分割可由外部工具产生蒙版，仍需检查薄雾、辉光和边缘完整性。

quality 检查真实透明、非空主体、声明尺寸/状态组、实际字体 cmap 缺字，报告许可、放大精度、显式非等比和占位绑定警告。材质/装饰完整性、风格、视觉权重由 Codex 按 SKILL.md 的参考身份核对与逐部件视觉匹配步骤检查真实图片。明显美术偏差须返修、重建并复查；只有明显偏差已消除、剩余差异较小且逐项说明后，才交给用户评审，不能靠门禁返回值替代，也不能以“待确认”代替返修。

cases 是 `{id,data,text,layers}` 数组：data 替换页面数据；text 是本页层 ID→文本；layers 是本页层 ID→字段 patch。用数据和约束构造空列表、超长文本、最大列表、极端数值及缺字。最大列表先按实际字段生成文本/层布局，再指定 scroll_regions 的 content_size/offset；业务列表数据转布局属于现有游戏 owner，适配器不猜数据库。

## 确认和冻结

```text
production.py approve --config <config> --manifest <manifest> --build <full-review> --evidence <actual-human-evidence-file> --actor <human-identity> --statement <exact-approval> --out <approval.json>
production.py freeze --config <config> --manifest <manifest> --build <review> --approval <approval.json> --out <new-delivery>
production.py verify-delivery --delivery <delivery>
```

保存用户真实消息或明确批准截图为 evidence，指向确切版本；Codex 不得生成假批准。approve 拒绝部分页面/状态、已变输入/组装 PNG、失败素材门禁。freeze 再核对批准和 PNG，复制便携源、规范、字体、布局、对照、证据与全文件哈希；拒绝已有目录。生产许可/分发权限仍需按实际来源处理。

隔离自动测试的 rules.test_fixture=true，approve 必须加 --test-only；fixture 交付、导出及集成不能冒充生产。测试并不批准游戏美术。

## 权威索引与恢复

```text
production.py sync-status --config <config> --manifest <manifest> --system <id> --state <state> --expected-sha <current-index-sha256> --evidence <file> --actor <actor> --statement <statement> [--delivery <frozen-package>] [--verification <verification.json>]
production.py clean-plan --config <config> --manifest <manifest> --out <plan.json>
production.py clean --config <config> --manifest <manifest> --plan <plan.json> --archive <new-project-relative-directory>
production.py restore --config <config> --archive <project-relative-directory>
production.py migrate --manifest <schema-1-file> --out <new-schema-2-file>
```

sync-status 只更新 init 创建的 format=game-ui-production-status 索引，带期待哈希并先留有限快照。state 为 draft/candidate/approved_reference/assets_verified/visual_approved/engine_verified。技术资产状态要求 quality；视觉状态要求确切冻结交付；引擎状态还要求匹配交付的技术验证及用户试玩证据。人工批准类状态的证据必须来自用户；脚本无法代替 Codex 核实消息。测试状态加 --test-only。

既有项目 Markdown/自定义索引不强行转换；Codex 按原格式就地更新当前条款和版本链接，保留必要恢复记录。状态属于输入身份，更新之后须重建后续候选，旧冻结包不可随之改写。不得把全局 Skill 文档作为项目状态账本。

clean-plan 仅列旧登记候选，排除最新状态候选和 Manifest 所有引用。clean 复核计划、哈希、登记、路径及引用，只移入全新归档，逐步记录恢复日志，不永久删除。restore 核对来源、不覆盖当前文件。检查冻结包、其他有效 Manifest 和历史确认引用后才执行清理；如保留候选另被旧确认包引用，先从清理计划移除。版本快照预算耗尽时停止并交代恢复状态，不悄悄删除已确认版本。
