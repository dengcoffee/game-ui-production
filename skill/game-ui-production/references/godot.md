# Godot 4 适配与专项检查

输入必须是带确切批准的 frozen delivery；同一 Manifest 是布局权威。脚本不修改游戏业务、存档、autoload、导航或数据库，不能把整页组装图变成交互贴图。

```text
python <skill>/scripts/godot_export.py --delivery <delivery> --out <new-isolated-godot-project>
python <skill>/scripts/engine_verify.py --export <isolated-project> --delivery <delivery> --godot <godot-console-executable> --out <new-verification-directory>
python <skill>/scripts/godot_export.py --integrate <verified-staged-project> --project <existing-project> --folder <new-relative-component-directory>
```

fixture 导出/集成需 --test-only，不能当生产。所有目录都须新建；原组件更新先查调用者和共享影响，暂存新版本，核对后按项目现有版本管理切换。integrate 验证 staged 哈希并重定位 res:// 路径，保留宿主 project.godot 和现有场景。

## 组件职责

生成 ui.tscn、ui-data.json、ui_view.gd、text_layer.gd 和独立图层 PNG/FontFile。每张图片单独负责视觉；crop/body/contain/grid/遮罩/透明在同一确定性几何中预处理，Godot TextureRect 显示它们，文字保持实时。九宫格当前按最终逻辑尺寸预处理，不声称能在引擎任意改变面板尺寸而自动保持视觉；改变逻辑尺寸须重建。物理窗口等比适配由宿主现有架构处理。

由现有 UI owner 实例化场景、处理 action_requested(action,control_id)、调用 show_page/page_state 和 set_data。具体 API：

- show_page(id)、show_state(state)：切换声明页面/状态，不猜布局；page_changed 提供当前身份。
- set_data(Dictionary)：更新点路径文字和 fill_binding 资源条；未知字段由游戏负责。adapter.json 的 pending_bindings 列出待绑定数据。
- set_control_disabled(id,bool)、set_control_selected(id,bool)：根据声明状态切换，禁用不发业务动作；Button 只做透明输入区域，不生成默认控件美术。
- set_scroll(region_id,x,y)：ScrollContainer 的实际滚动；滚动区承载独立绝对图层，offset 与 HTML 取样一致。隐藏默认滚动条美术，滚轮/现有导航负责输入；自定义滚动条图片与绑定按项目规范补充。
- show_popup(page_id)、close_popup()：复用同一组件显示嵌套弹窗，阻止下层输入，关闭恢复；游戏 owner 决定开关时机和背景遮挡美术。
- animations：Tween 驱动 opacity、位置、弧度旋转和统一 scale；切换/销毁杀死旧 Tween，独立运动图层需已有图片来源。

参考 [Godot ScrollContainer 官方文档](https://docs.godotengine.org/en/stable/classes/class_scrollcontainer.html)；SCROLL_MODE_SHOW_NEVER 保留滚动而不显示默认滚动条。

## 验证与定位

engine_verify 在副本运行实际 Godot import、无头 behavior probe 和离屏 GPU 截图，不控制用户桌面键盘/鼠标。导入/脚本报错即失败，不能只看 exit code。若图形环境无法运行，明确仅行为检查完成，转用该工程正式截图接口或用户试玩截图，不假造 GPU 截图。

probe 检查声明状态、几何、焦点、ui_accept 引擎输入事件、动作、禁用、实时文字/资源条、滚动、嵌套弹窗和动画结束值。这些模拟事件只进入隔离测试进程。render_probe 保存实际逻辑画布、透明背景的各页状态图；非循环 Tween 在终值取样。循环动画需独立规定验收时间，不能把此通用采样当最终批准。

verification.json 保存导出/交付/引擎版本、PNG 哈希和差异定位；outside_text_changed_pixels 排除文本 bounds 外扩 3 像素，用于区分图片/合成和字体差异，不证明文字正确。Pillow 与 Godot 使用不同字体栅格化，仍须检查字体、字距、阴影、长文本、遮挡和实际玩法。

技术结果不设置 visual_approved/engine_verified。用户明确确认引擎视觉并试玩后，将匹配报告及真实证据写入当前项目权威。其他引擎新增 adapters/<engine>，保持生产核心和项目 Art Bible 分离。
