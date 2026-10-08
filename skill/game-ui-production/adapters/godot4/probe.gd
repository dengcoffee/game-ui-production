extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var scene = load("res://ui.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	var failures: Array[String] = []
	var checks := 0
	var actions: Array = []
	scene.action_requested.connect(func(action,id): actions.append([action,id]))
	for page in scene.document.pages:
		scene.show_page(page.id)
		for state in page.states:
			scene.show_state(state)
			await process_frame
			checks += 1
			if scene.current_state != state:
				failures.append("State mismatch: " + page.id)
			for spec in page.states[state]:
				var node: Control = scene.layer_nodes[spec.id]
				var moves := false
				for animation in page.animations:
					if animation.layer == spec.id and animation.property in ["x","y"]: moves = true
				if not spec.has("clip") and not moves:
					if not node.global_position.is_equal_approx(Vector2(spec.position[0], spec.position[1])):
						failures.append("Position mismatch: " + spec.id)
		for control in scene.controls.values():
			control.grab_focus()
			await process_frame
			checks += 1
			if not control.has_focus() and not control.disabled:
				failures.append("Focus mismatch: " + control.name)
			checks += 1
			var before := actions.size()
			control.pressed.emit()
			if actions.size() != before + (0 if control.disabled else 1): failures.append("Action routing mismatch")
			before = actions.size()
			var press := InputEventAction.new()
			press.action = "ui_accept"
			press.pressed = true
			Input.parse_input_event(press)
			await process_frame
			var release := InputEventAction.new()
			release.action = "ui_accept"
			Input.parse_input_event(release)
			await process_frame
			checks += 1
			if not control.disabled and actions.size() != before + 1: failures.append("Focused ui_accept input failed")
			scene.set_control_disabled(control.name, true)
			before = actions.size()
			control.pressed.emit()
			if actions.size() != before: failures.append("Disabled action emitted")
			scene.set_control_disabled(control.name, false)
		scene.set_data({"name":"Extremely long live bound name", "amount":999999999, "empty":[], "ratio":0.25})
		for node in scene.layer_nodes.values():
			for child in node.get_children():
				if child.has_method("formatted") and child.spec.has("binding"):
					checks += 1
					if child.data.get("amount") != 999999999:
						failures.append("Binding data was not delivered")
		for region in page.get("scroll_regions", []):
			await process_frame
			scene.set_scroll(region.id, 0, 50)
			checks += 1
			if scene.scroll_nodes[region.id].scroll_vertical != 50: failures.append("Scroll did not move")
		for tween in scene.tweens:
			tween.custom_step(100)
		for animation in page.animations:
			checks += 1
			if animation.property == "opacity" and not is_equal_approx(scene.layer_nodes[animation.layer].modulate.a,float(animation.to)):
				failures.append("Animation final opacity mismatch")
		for entry in scene.fill_nodes.values():
			checks += 1
			if entry.node.size.x != round(entry.spec.control_size[0]*0.25): failures.append("Live resource fill mismatch")
		checks += 1
		var first: Control = scene.show_popup(page.id)
		var second: Control = scene.show_popup(page.id)
		if scene.input_root.visible or first.input_root.visible or not second.input_root.visible: failures.append("Modal input isolation failed")
		scene.close_popup()
		if not first.input_root.visible: failures.append("Nested modal restore failed")
		scene.close_popup()
		if not scene.input_root.visible: failures.append("Modal restore failed")
	var result := {"passed":failures.is_empty(), "checks":checks, "failures":failures,
		"engine_version":Engine.get_version_info(), "visual_approved":false}
	var file := FileAccess.open("res://engine-tests.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "\t"))
	print(JSON.stringify(result))
	quit(0 if failures.is_empty() else 1)
