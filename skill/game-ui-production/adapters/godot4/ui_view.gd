extends Control

signal action_requested(action: String, control_id: String)
signal page_changed(page_id: String, state: String)

var document: Dictionary
var page_spec: Dictionary
var current_state := "normal"
var current_page := ""
var values: Dictionary
var visual_root: Control
var input_root: Control
var layer_nodes: Dictionary = {}
var controls: Dictionary = {}
var tweens: Array[Tween] = []
var scroll_nodes: Dictionary = {}
var fill_nodes: Dictionary = {}
var popup_stack: Array[Control] = []
var text_script = preload("res://text_layer.gd")

func _ready() -> void:
	document = JSON.parse_string(FileAccess.get_file_as_string("res://ui-data.json"))
	size = Vector2(document.canvas[0], document.canvas[1])
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visual_root = Control.new()
	visual_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(visual_root)
	input_root = Control.new()
	input_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(input_root)
	show_page(document.pages[0].id)

func show_page(page_id: String) -> void:
	for candidate in document.pages:
		if candidate.id == page_id:
			page_spec = candidate
			current_page = page_id
			values = candidate.data.duplicate(true)
			_build_inputs()
			show_state("normal")
			return
	push_error("Unknown UI page: " + page_id)

func show_state(state: String) -> void:
	if not page_spec.states.has(state):
		push_error("Unknown UI state: " + state)
		return
	for tween in tweens:
		tween.kill()
	tweens.clear()
	for child in visual_root.get_children():
		visual_root.remove_child(child)
		child.queue_free()
	layer_nodes.clear()
	scroll_nodes.clear()
	fill_nodes.clear()
	current_state = state
	for spec in page_spec.states[state]:
		var node := Control.new()
		node.name = spec.id
		node.position = Vector2(spec.position[0], spec.position[1])
		node.size = Vector2(spec.control_size[0], spec.control_size[1])
		node.mouse_filter = Control.MOUSE_FILTER_IGNORE
		node.z_as_relative = false
		node.z_index = spec.z
		node.visible = spec.get("visible", true)
		visual_root.add_child(node)
		layer_nodes[spec.id] = node
		if spec.has("texture"):
			var texture := TextureRect.new()
			texture.texture = load(spec.texture)
			texture.position = Vector2(spec.texture_offset[0], spec.texture_offset[1])
			texture.size = texture.texture.get_size()
			texture.mouse_filter = Control.MOUSE_FILTER_IGNORE
			if spec.has("fill_binding"):
				var fill := Control.new()
				fill.clip_contents = true
				fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
				node.add_child(fill)
				fill.add_child(texture)
				fill_nodes[spec.id] = {"node":fill,"spec":spec}
			else:
				node.add_child(texture)
		elif spec.has("text"):
			var text := Control.new()
			text.set_script(text_script)
			text.size = node.size
			if spec.get("overflow", "wrap") == "clip" and spec.has("max_width"):
				text.clip_contents = true
			node.modulate.a = spec.get("opacity", 1.0)
			node.add_child(text)
			text.configure(spec, values)
	# Reparent with absolute geometry retained; parent motion propagates to children.
	for spec in page_spec.states[state]:
		if spec.has("parent"):
			layer_nodes[spec.id].reparent(layer_nodes[spec.parent], true)
		if spec.has("clip") and spec.has("text"):
			var wrapper := Control.new()
			wrapper.position = Vector2(spec.clip[0], spec.clip[1])
			wrapper.size = Vector2(spec.clip[2], spec.clip[3])
			wrapper.clip_contents = true
			wrapper.mouse_filter = Control.MOUSE_FILTER_IGNORE
			visual_root.add_child(wrapper)
			layer_nodes[spec.id].reparent(wrapper, true)
	for region in page_spec.get("scroll_regions", []):
		var scroll := ScrollContainer.new()
		scroll.position = Vector2(region.rect[0], region.rect[1])
		scroll.size = Vector2(region.rect[2], region.rect[3])
		# Native scrolling without introducing default scrollbar artwork.
		scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
		scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
		visual_root.add_child(scroll)
		var content := Control.new()
		content.custom_minimum_size = Vector2(region.content_size[0], region.content_size[1])
		content.mouse_filter = Control.MOUSE_FILTER_IGNORE
		scroll.add_child(content)
		for id in region.layers:
			layer_nodes[id].reparent(content, true)
		scroll_nodes[region.id] = scroll
		set_scroll.call_deferred(region.id, region.offset[0], region.offset[1])
	_update_fills()
	for animation in page_spec.animations:
		var node: Control = layer_nodes[animation.layer]
		var property: String = {"opacity":"modulate:a", "x":"position:x", "y":"position:y", "rotation":"rotation", "scale":"scale"}[animation.property]
		var start: Variant = animation.from
		var finish: Variant = animation.to
		if animation.property == "scale":
			start = Vector2.ONE * start
			finish = Vector2.ONE * finish
		node.set_indexed(NodePath(property), start)
		var tween := create_tween()
		if animation.get("loop", false):
			tween.set_loops()
		tween.tween_property(node, property, finish, animation.duration)
		tweens.append(tween)
	page_changed.emit(current_page, state)

func _build_inputs() -> void:
	for node in input_root.get_children():
		input_root.remove_child(node)
		node.queue_free()
	controls.clear()
	var entries: Array = page_spec.interactions.duplicate()
	entries.sort_custom(func(a, b): return a.get("focus_order", 0) < b.get("focus_order", 0))
	for spec in entries:
		var button := Button.new()
		button.name = spec.id
		button.position = Vector2(spec.rect[0], spec.rect[1])
		button.size = Vector2(spec.rect[2], spec.rect[3])
		button.disabled = spec.get("disabled", false)
		button.focus_mode = Control.FOCUS_ALL
		button.z_index = 4096
		for key in ["normal", "hover", "pressed", "disabled", "focus"]:
			button.add_theme_stylebox_override(key, StyleBoxEmpty.new())
		input_root.add_child(button)
		controls[spec.id] = button
		button.pressed.connect(func():
			if not button.disabled: action_requested.emit(spec.action, spec.id))
		button.mouse_entered.connect(func(): _control_state(spec, "hover"))
		button.mouse_exited.connect(func(): _control_state(spec, "normal"))
		button.button_down.connect(func(): _control_state(spec, "pressed"))
		button.button_up.connect(func(): _control_state(spec, "normal"))
		button.focus_entered.connect(func(): _control_state(spec, "focus"))
		button.focus_exited.connect(func(): _control_state(spec, "normal"))

func _control_state(spec: Dictionary, state: String) -> void:
	if spec.get("states", {}).has(state):
		show_state(spec.states[state])

func set_data(data: Dictionary) -> void:
	values = data.duplicate(true)
	for node in layer_nodes.values():
		for child in node.get_children():
			if child.has_method("set_data"):
				child.set_data(values)
	_update_fills()

func _update_fills() -> void:
	for entry in fill_nodes.values():
		var value: Variant = values
		for key in entry.spec.fill_binding.split("."):
			value = value.get(key, 1.0) if value is Dictionary else 1.0
		entry.node.size = Vector2(round(entry.spec.control_size[0] * clampf(float(value),0,1)), entry.spec.control_size[1])

func set_scroll(region_id: String, x: int, y: int) -> void:
	var scroll: ScrollContainer = scroll_nodes[region_id]
	scroll.scroll_horizontal = x
	scroll.scroll_vertical = y

func show_popup(page_id: String) -> Control:
	var popup := Control.new()
	popup.set_script(get_script())
	popup.z_index = 4096
	add_child(popup)
	popup.show_page(page_id)
	popup.action_requested.connect(func(action, id): action_requested.emit(action,id))
	if not popup_stack.is_empty(): popup_stack[-1].input_root.hide()
	input_root.hide()
	popup_stack.append(popup)
	return popup

func close_popup() -> void:
	if popup_stack.is_empty(): return
	var popup: Control = popup_stack.pop_back()
	remove_child(popup)
	popup.queue_free()
	if popup_stack.is_empty(): input_root.show()
	else: popup_stack[-1].input_root.show()

func set_control_disabled(control_id: String, disabled: bool) -> void:
	controls[control_id].disabled = disabled
	for spec in page_spec.interactions:
		if spec.id == control_id:
			_control_state(spec, "disabled" if disabled else "normal")

func set_control_selected(control_id: String, selected: bool) -> void:
	for spec in page_spec.interactions:
		if spec.id == control_id:
			_control_state(spec, "selected" if selected else "normal")

func _exit_tree() -> void:
	for tween in tweens:
		tween.kill()
