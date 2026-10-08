extends Control

var spec: Dictionary
var data: Dictionary
var real_font: Font

func configure(value: Dictionary, values: Dictionary) -> void:
	spec = value
	data = values
	real_font = load(spec.font_path)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	queue_redraw()

func set_data(values: Dictionary) -> void:
	data = values
	queue_redraw()

func lookup(key: String, fallback: Variant) -> Variant:
	var value: Variant = data
	for part in key.split("."):
		if not value is Dictionary or not value.has(part):
			return fallback
		value = value[part]
	return value

func formatted() -> String:
	var value := str(lookup(spec.get("binding", ""), spec.text)) if spec.has("binding") else str(spec.text)
	var width := int(spec.get("max_width", 0))
	if width <= 0 or spec.get("overflow", "wrap") == "clip":
		return value
	var lines: Array[String] = []
	for paragraph in value.split("\n"):
		var line := ""
		if spec.get("overflow", "wrap") == "ellipsis":
			line = paragraph
			if real_font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size).x > width:
				while not line.is_empty() and real_font.get_string_size(line + "…", HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size).x > width:
					line = line.left(-1)
				line += "…"
			lines.append(line)
		else:
			for char in paragraph:
				if not line.is_empty() and real_font.get_string_size(line + char, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size).x > width:
					lines.append(line)
					line = ""
				line += char
			lines.append(line)
	var maximum := int(spec.get("max_lines", 0))
	if maximum > 0 and lines.size() > maximum:
		lines.resize(maximum)
		while not lines[-1].is_empty() and real_font.get_string_size(lines[-1] + "…", HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size).x > width:
			lines[-1] = lines[-1].left(-1)
		lines[-1] += "…"
	return "\n".join(lines)

func _draw() -> void:
	if spec.is_empty() or real_font == null:
		return
	var row := 0
	for line in formatted().split("\n"):
		var origin := Vector2(spec.offset_x, spec.baseline + row * spec.line_height)
		if spec.has("shadow"):
			draw_string(real_font, origin + Vector2(spec.shadow.offset[0], spec.shadow.offset[1]), line, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size, Color(spec.shadow.color))
		if spec.get("stroke", 0) > 0:
			draw_string_outline(real_font, origin, line, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size, spec.stroke, Color(spec.get("stroke_color", spec.color)))
		if spec.get("letter_spacing", 0) != 0:
			for char in line:
				draw_string(real_font, origin, char, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size, Color(spec.color))
				origin.x += real_font.get_string_size(char, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size).x + spec.letter_spacing
		else:
			draw_string(real_font, origin, line, HORIZONTAL_ALIGNMENT_LEFT, -1, spec.size, Color(spec.color))
		row += 1
