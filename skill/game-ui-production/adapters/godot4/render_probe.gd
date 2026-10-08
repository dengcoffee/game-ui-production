extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var document: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://ui-data.json"))
	var viewport := SubViewport.new()
	viewport.size = Vector2i(document.canvas[0], document.canvas[1])
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var scene = load("res://ui.tscn").instantiate()
	viewport.add_child(scene)
	await process_frame
	for page in document.pages:
		scene.show_page(page.id)
		for state in page.states:
			scene.show_state(state)
			for tween in scene.tweens:
				tween.custom_step(100.0)
			await process_frame
			await RenderingServer.frame_post_draw
			var image := viewport.get_texture().get_image()
			image.save_png("res://" + page.id + "--" + state + "--engine.png")
	print("UI_RENDER_CAPTURE_COMPLETE")
	quit()
