# 数据契约与合成

Python 3.11+，依赖见 requirements.txt。运行脚本时使用 Skill 的绝对路径；浏览器只需要生成的 index.html，不需要服务或联网。Pixelmatch 7.2.0 的 ISC 许可随包保留。

```text
python <skill>/scripts/ui.py inspect --config <project.json> --manifest <manifest.json>
python <skill>/scripts/ui.py build --config <project.json> --manifest <manifest.json> --out <new-review>
python <skill>/scripts/ui.py build --config <project.json> --manifest <manifest.json> --out <new-review> --previous <old-review> --pages <page-id> ...
```

配置 source_root/output_root 相对配置文件解析，资源路径相对 source_root。documents/art_bible/status_source 指向现有权威；rules 保存该项目白名单、画布、重试、精度、状态组和尺寸约束。它们不能扩大本次授权。输出必须在 output_root 子目录，与输入隔离。

Schema 1/2 都可读，当前新数据使用 2。schema JSON 是可执行字段权威，未知字段被拒绝；migrate 创建新文件完成 1→2，不改原文件。ID 仅用英文字母、数字、单下划线/连字符，双连字符保留作产物身份分隔符。

## Manifest

- canvas 为项目逻辑宽高。assets 是稳定 ID→path/sha256/kind/source/license/status；kind=ui/content/font。保留许可未知，不假定可再分发。
- systems 包含系统 ID、名称、页面列表；masters 定义公共图层，pages.master 引用而非复制。pages 含 reference、layers、状态覆盖和责任范围。参考图必须同画布、哈希吻合，不能作为组装层。
- 图片层：asset、rect=[x,y,width,height]、z；anchor=[0..1,0..1]、parent；rect 相对父层左上角。clip=[x,y,w,h] 为绝对画布裁剪。crop=[left,top,right,bottom] 是源像素边界；body=true 取透明主体，两者互斥。
- resize=native（禁止隐式缩放）、contain、cover、stretch（显式可伸缩）或 grid。grid 的 source_x/y、target_x/y 定义分段，保留固定角部。不用非等比整图拉伸迁就错误。
- 文本层：text、xy、font/size/color 或 typography_token。支持 stroke/stroke_color、shadow={offset,color}、spacing、letter_spacing、text_anchor、max_width、max_lines、overflow=wrap/ellipsis/clip。typography 字典提供复用 token。字段引用真实字体；字体渲染差异需单独验收。
- binding 是 data 中点分隔字典路径，缺项使用 text 占位并警告；数值由游戏提供。图片层 fill_binding 读取 0..1 比例，从左向右裁剪显示，支持实时资源条；不生成数值美术。超过范围截断，不对数据意义作假设。
- state_overrides 将状态映射为指定层的 patch，其余共享层保持一致。interactions 定义 id/rect/action/focus_order/disabled，以及 normal/hover/pressed/selected/disabled/focus 到已声明页面状态的映射；不凭空造状态美术。
- animations 声明 layer/property/from/to/duration/loop；property 为 opacity/x/y/rotation（弧度）/scale。PNG 是静态版本，Godot 驱动运动。验收引擎截图按非循环动画结束值取样，循环动画需另定采样时刻。
- scroll_regions 定义 id/rect/layers/content_size/offset，指定绝对坐标根层；每层最多属于一个滚动区。Python 按声明 offset 平移并裁切，Godot 用原始独立图层实时滚动。滚动图片不混用静态 clip；复杂嵌套父运动应先显式拆分，拒绝不可靠映射。

## 视觉与增量

assessment 是参与分析的矩形并集，exclude 减去责任外内容；省略 assessment 表示全画布。scope_mask 引用同画布灰度 PNG，非零参与。蒙版不得遮掉当前负责的问题。空范围被拒绝。

build 输出独立组装 PNG、蒙版、build.json 和离线 HTML。报告保存资源引用、主体边界、真实文字、参考/输入/工具/Schema 哈希。连续同输入的 PNG 可复现；生图提示词不保证复现。页面指纹只复用未变依赖，复用前核对旧 PNG 哈希；共享变化覆盖所有引用页，局部修改不改其他页。筛选构建用于返修检查，完整冻结必须包含 Manifest 全部页面/状态。

网页支持系统/页面/状态、并排、同步缩放/平移、叠加透明度、Pixelmatch 热图与容差、棋盘格、布局/主体辅助线及 PNG/JSON 导出。身份包括系统、页面、状态、参考/组装/Manifest SHA-256。浏览器展示同一合成 PNG，不另建字体/布局权威；动态文字仍在源 Manifest，不烘焙进源图片。
