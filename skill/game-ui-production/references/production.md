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

task 包含 system、assets 列表。每资产必填 id、kind、purpose、display_size、states、alpha、allowed_changes；新定类 UI 同时填写 ui_type 和 classification，完整判定与询问规则见 classification.md；可添加 effects、完整边缘要求、视觉权重、内容差异及已有公共引用，都会注入提示词。content 还需 explicit_content_authorization 含该类别并通过项目白名单。项目规则不能替代用户授权。

prepare-provider 只准备真实调用参数，不生成图片。Codex 用当前可用图像工具执行 arguments，编辑先 view_image；返回实际 PNG 后 import 使用同一 ticket，避免重复计费式计数。预备/失败均消耗本请求、资产和状态的尝试预算；不靠改 request 时间戳重置预算。因根因或任务范围实质改变才重新规划。

当前内置实现是 Codex 主机的 image_gen.imagegen：生成、参考编辑和透明背景；Python 不调用该主机工具、不要求 API 密钥。每次会话检查接口能力，实际输出再验证。不能像素锁定。工具不可用时直接导入外部 PNG 并记录真实来源，不用虚假 placeholder 冒充结果。

import 核对计划输入未变、范围、重试数、实际 PNG、真实透明、非空 Alpha 主体；稳定 ID 下用内容哈希登记候选。attach 产生新 Manifest，并给出所有受影响页面。不得把生成画布大小误当可见主体或最终显示尺寸。

## 素材包与素材库交接

提取、确认和入库是三个独立阶段。production.py approve 仅记录项目页面批准，不再自动写素材库；asset_package.py 不导入 library.py，也不需要 rules.asset_library。Codex 在提取和完整 build 后为用户准备一个独立候选目录，执行命令与数据由 Codex 编制，不要求用户填写 JSON。

```text
python <skill>/scripts/asset_package.py prepare --config <project.json> --manifest <manifest.json> --build <complete-review> --project <stable-project-name> --out <new-review-package>
python <skill>/scripts/asset_package.py confirm --package <review-package> --evidence <actual-user-message-or-screenshot> --actor <human> --statement <actual-confirmation>
python <skill>/scripts/library.py add --package <confirmed-package> [--root <absolute-library-root>]
```

包目录包含 assets/（集中存放 PNG 和真实字体文件，不按类型分子目录）、review/（复制的完整离线对照）、index.html（入口）、package.json（标准清单）；确认后增加 approval.evidence 并更新清单，确认不调用素材库。prepare 检查参考构建与输入版本、完整页面/状态及组装哈希；缺少 UI 类型或没有素材时拒绝打包。包独立保留文件，移动到别处后仍可确认和入库，不依赖原项目路径。

### 供其他技能读取的数据契约

package.json 的 schema_version=1。project 为稳定项目名称；status 为 candidate 或 visual_approved；test_only 由项目 test_fixture 传递。assets 每项包含 asset_id、name、ui_type、category（中文分类）、kind、classification（分类依据）、tags、asset_state、path、sha256、size、visible_bounds、states、usages、source、license；path 相对包目录，图片 size 是 PNG 画布尺寸，visible_bounds 是区域边界，usages 保存页面/state/rect/anchor；字体 kind=font、ui_type=font，size/visible_bounds 为 null，usages 保存页面/state/字号/位置。旧包缺少 kind 时按 ui 兼容。source_manifest_sha256 记录原 Manifest 身份，files 保存包内所有素材和对照文件的相对路径→SHA-256。

ui_type 稳定代码为 base（底板）、frame（窗口框）、button（按钮）、tab（页签）、avatar_frame（头像框）、item_slot（道具格）、scroll_track（轨道）、scroll_thumb（滑块）、progress_track（进度槽）、progress_fill（进度填充）、decoration（装饰）、ui_icon（图标）、font（字体）。新生产计划传递 ui_type，可选 display_name/tags，attach 保存 asset_state；不按文件名猜类型。旧 separator 兼容归入 decoration，不修改旧源记录或已确认包。人物/头像本体/道具内容图标仍按内容授权处理，不因分类名称扩大生产范围。字体自动登记本次页面使用的真实 TTF/OTF/TTC 文件，保留原来源与许可；不能从截图文字提取完整字体。

确认记录 approval 包含 actor、statement、test_only、content_sha256、evidence_path、evidence_sha256。content_sha256 是去掉顶层 status/approval 后的清单 JSON（ensure_ascii=False、sort_keys=True、默认分隔符、UTF-8）的 SHA-256，绑定类型、几何、来源、项目与文件清单。消费者使用 asset_package.validate(package,approved=True) 核对版本、文件、尺寸、确认内容与证据；未确认、元数据或文件改动后都拒绝入库。测试包只能 --test-only 模拟确认，永远不能正式入库；技术通过不等于人类确认。

确认范围是整个包，证据必须对应确切版本；confirm 后不修改包内文件。返修重新 prepare 到新目录，重新评审。素材包确认不自动替代项目冻结所需的版本证据；同一真实用户证据如明确覆盖两个确切版本，可按原批准流程沿用，不编造第二次确认。

### 可选素材库消费者

库根默认用户桌面“素材库”，只维护项目入口。library.py add --package 从包读取项目身份及分类，无需原项目配置；新哈希另存、同版本幂等，不覆盖旧资产。项目下独立分类目录、index.json/index.html 与证据副本；素材记录是依据，索引可重建。入库失败独立报告，可重试，不改变已确认包。旧 add --config/--manifest/--build/--approval 保留为显式兼容入口，仍不自动运行。

检索/复用配置 rules.asset_library={"root":"<absolute-library-path>","project":"<stable-project-name>"}，root 可省略，project 不随当前工作目录变动。search/reindex/use 命令保持现有接口：

```text
python <skill>/scripts/library.py search --config <project.json> [--type button] [--query <name-or-tag>] [--state normal] [--size <width> <height>]
python <skill>/scripts/library.py reindex --config <project.json>
python <skill>/scripts/library.py use --config <project.json> --asset <library-relative-PNG-path> --out <project-relative-new-PNG>
```

默认限定当前项目，用户明确要求跨项目时 search/use 同时传 --project <source-project> --cross-project。use 复制而不缩放，保存来源记录；字体必须保留真实文件扩展名，浏览页展示文件链接而非错误图片预览；输出仍为 candidate，按原 import/attach/build 流程登记、核对主体尺寸及内部几何，美术允许合理容差。库内原批准不表示新页面批准。未知 PNG 不自动收录，已有资源不自动搬迁。

## 自动分层识别

分类先读 [分类判定与证据传递](classification.md)。所有无法明确的分类都必须询问用户，不限于影响底图完整性或行为的歧义；待回答项不提取、不登记、不打包。其他分层判断仍按下述职责规则执行。

有参考图的 UI 提取任务，先查看已核对身份的原图及本次适用的页面/状态，结合功能稿、实际显示尺寸和既有资源判断分层。以下是默认判断，项目已确认规格及用户明确要求优先；识别用于规划，不等于工具已经完成像素分割。

- **底图**：连续的公共底色与底纹按完整一张保留，不因列表、子面板或布局矩形切成碎块。与底图不可分且无需独立行为的固定美术结构可保留在底图；可干净分离的边框、装饰、阴影和光效按覆盖层处理，不把所有静态部件一概合并。
- **独立控件与覆盖层**：需要点击、独立复用、状态切换或动画的按钮、页签、框体及效果单独分层。按实际行为和组装职责拆分，不因颜色、材质或轮廓不同就拆，也不把每条框线、每片装饰机械拆成独立资源。
- **按钮**：默认提取完整控件美术，保留按钮自身底色、填充纹理、边框、固定装饰及完整阴影/光效，不得仅交付边框。按钮外部无关区域透明，内部是否透明以参考为准，不把按钮填充当作页面底图去掉；文字独立渲染，可变图标另层处理。只有需独立复用、状态切换或动画的部分才拆层；各状态使用一致画布、锚点及控件位置，并保留效果留边。
- **滑动条与滚动条**：轨道（线/槽）与滑块（可移动标记/滑动柄）分开提取，保留各自填充、边缘及效果；固定刻度归轨道，可独立变化的刻度或标记另层处理，不将所有标记一概当作滑块。记录方向、有效移动范围、滑块尺寸与锚点；滑块遮住的轨道部分无法直接提取时，明确记录补绘需求及来源。分层不等于已完成运行时交互绑定。
- **进度条**：槽底/外框与随数值变化的填充层分开，移动端点标记按行为另层处理。区分控件长度适配与进度变化：长度适配时，适合拉伸的条形素材保留两端端帽/装饰，仅沿长度方向拉伸中段，使用已有 grid 分段字段记录固定端部与伸缩区；有明显重复纹理时先判断平铺或裁切是否更合适，不拉伸整张图导致端帽、边框或纹理变形。进度变化优先按参考裁切显示填充；只有设计允许且效果经验证时才选择缩放中段等方案，不默认伸缩整个外框。当前 fill_binding 仅支持从左向右裁剪 0..1 比例，其他方向、平铺或移动端帽等行为须先核对工具及宿主能力，不能编造 Manifest 字段或宣称已接入。单张部分填充截图不能证明完整填充纹理已提取，缺失段按参考编辑或重制记录。
- **动态内容**：文字、数值、人物、头像和道具 ICON 与底图分开；文字保持实时，内容资源按已有授权引用或占位。头像框与头像本体职责不同，仍遵守 SKILL.md 的提取范围。
- **公共母版**：有多个页面/状态参考时，对照相同位置的轮廓、材质、装饰及变化，识别共享部分并复用同一资源 ID；不能仅凭位置或相似颜色认定相同。仅有一张参考时，将共享判断标为推定，不宣称已跨页验证。

提取前提供标注参考图或区域示意作为分层预览，附简短清单：区域/资源职责、整块保留或独立分层、共享范围、判断理由、来源路径及裁切/蒙版范围、处理方式（真实提取、已有资源复用、参考编辑或重新制作），并标出遮挡与无法确定的部分。写入现有项目规格/计划，不另建竞争索引。明确的部分继续执行，不新增逐层批准流程；分类无法明确时必须询问用户。其他分层歧义在影响底图完整性、共享身份或控件行为且现有依据无法消解时集中询问。

移除动态内容后，底图应保持连续，覆盖层无关区域应透明；被遮挡的像素及半透明效果不能声称精确恢复，需补绘时如实标为参考编辑并遵守尝试预算。按实际层序重新组装，与同尺寸、同状态参考对照，检查内容残留、重复底纹、接缝、缺失装饰和效果截断；依据差异修正分层判断后重建，技术检查通过不等于分层正确或用户视觉批准。

涉及上述控件时，视觉检查覆盖已声明按钮状态、滑块行程两端及中间、进度 0%/低值/50%/100%；有长度适配要求时同时检查目标长短尺寸，确认按钮填充未丢失、轨道连续、滑块对齐、端帽未变形、小进度无溢出且效果未截断。预览只能证明对应静态样例；运行时行为仍按 Godot 接入流程验证。

## 提取、质量与压力测试

### 候选分层执行（轻量版）

Codex 先查看目标原图并结合功能职责提出区域计划，用户不必编写 JSON。连续底板保持完整；按钮保留填充/框/固定效果，文字独立；头像本体不提取，框与轨道按职责分层。区域计划是参考坐标下的候选中间文件，不替代项目规格或 Manifest，不自动晋升正式资产。

```text
python <skill>/scripts/layers.py --source <reference.png> --plan <regions.json> --out <new-candidate-directory>
```

计划字段示例（坐标和哈希由 Codex 根据本次参考填写）：

```json
{
  "canvas": [400, 300],
  "source_sha256": "<actual-reference-sha256>",
  "regions": [
    {"id": "button", "purpose": "complete button without live text",
     "rect": [20, 30, 120, 50], "method": "border", "tolerance": 12,
     "subject_bounds": [4, 4, 116, 46], "occlusions": [[30, 15, 60, 20]]}
  ]
}
```

- rect=[x,y,w,h] 固定源图位置与输出尺寸，不按蒙版外接框重新裁切/缩放。regions 顺序就是从底到顶的组装层序；职责或重叠错误由组装对照发现，不能用截图重复覆盖冒充分层。
- method=rect 只产出 reference_crop；method=border 自动移除与边缘连通且接近边缘主色的像素，tolerance 是 RGB 各通道最大差值，限底色较均匀、主体不贴边的区域。相同颜色但不连通边缘的内部填充保留。该方法不估计半透明，不适用于复杂底纹、细弱框线或光晕，输出须检查后才能采用。
- method=mask 使用 mask 指定的区域尺寸灰度 PNG，路径相对计划文件。保持连续 Alpha，不宣称去除了原截图背景混色。头像框需蒙版排除头像显示区。
- subject_bounds=[left,top,right,bottom] 是区域内预先核对的非零 Alpha 边界（右下不含），提供时精确检查，变化直接拒绝；适用于边界明确的实体部件。半透明效果须用预览另查主体边界，不用效果外接框代替主体。缺少此字段时报告明确标记未检查主体尺寸。
- occlusions 使用区域内 [x,y,w,h]，标出可变内容或待补绘区域。没有 repair 时移除这些区域并标记 pending_reconstruction；有 repair 时读取区域同尺寸 RGBA PNG，仅采纳遮挡区域内像素，再应用分层蒙版。尺寸不符直接拒绝，不自动拉伸。复杂框体补绘需提供覆盖目标完整轮廓的显式蒙版，不能用原可见蒙版截掉补绘部分。
- 输出包括每部件 PNG、分层蒙版、补绘范围蒙版、preview.png、assembly.png、report.json 与离线 index.html。报告保存参考/计划/蒙版/补绘/产物哈希、固定位置、主体检查与待补绘项；不声称自动识别全部内部几何，也不自动批准美术。

先验几何再验美术：尺寸、锚点、框线、端点和间距不允许变化；脚本负责画布、固定区域、补绘尺寸及声明的 Alpha 边界检查，内部结构仍在同尺寸组装对照中检查。模糊或遮挡部分允许重绘，纹理/颜色/细节差异较小且整体协调可通过视觉评审，不要求像素完全一致。矩形截图、待补绘项、明显色边或缺项仍不能当成完成资源。候选导入沿用 production.py import/attach，最终使用现有 build/quality 与批准流程。

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
