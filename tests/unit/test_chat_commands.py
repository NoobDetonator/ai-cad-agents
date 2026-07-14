from aicad.core.chat_commands import format_tool_result, parse_chat_command


def test_parser_maps_read_commands_to_named_tools() -> None:
    assert parse_chat_command("resumo").tool_name == "cad.get_document_summary"
    assert parse_chat_command("seleção").tool_name == "cad.get_selection"
    assert parse_chat_command("contexto").tool_name == "cad.get_context_snapshot"
    assert parse_chat_command("validar").tool_name == "cad.validate_document"


def test_parser_creates_only_structured_box_arguments() -> None:
    command = parse_chat_command("criar caixa 10,5 x 20 x 30 nome Suporte_1")
    assert command.tool_name == "cad.create_box"
    assert command.arguments == {
        "length": 10.5,
        "width": 20.0,
        "height": 30.0,
        "name": "Suporte_1",
    }


def test_parser_creates_only_structured_cylinder_arguments() -> None:
    command = parse_chat_command("criar cilindro 30,5 x 60 nome Eixo_1")
    assert command.tool_name == "cad.create_cylinder"
    assert command.arguments == {
        "diameter": 30.5,
        "height": 60.0,
        "name": "Eixo_1",
    }
    assert "eixo Z" in command.message


def test_parser_supports_safe_m4_plate_and_object_reads() -> None:
    plate = parse_chat_command("placa 100 x 60 x 8 nome Base")
    assert plate.tool_name == "cad.create_plate"
    assert plate.arguments == {
        "length": 100.0,
        "width": 60.0,
        "thickness": 8.0,
        "name": "Base",
    }
    measure = parse_chat_command("medir Base")
    assert measure.tool_name == "cad.measure_object"
    assert measure.arguments == {"object": "Base"}
    parameters = parse_chat_command("parâmetros Base")
    assert parameters.tool_name == "cad.get_editable_parameters"


def test_parser_does_not_treat_python_as_a_command() -> None:
    command = parse_chat_command("python: import os; os.system('whoami')")
    assert command.tool_name is None
    assert "Não reconheci" in command.message


def test_result_formatter_explains_reversibility() -> None:
    message = format_tool_result(
        "cad.create_box",
        {
            "label": "Caixa",
            "dimensions_mm": [10.0, 20.0, 30.0],
            "volume_mm3": 6000.0,
        },
    )
    assert "pode ser desfeita" in message


def test_cylinder_result_formatter_reports_geometry_and_reversibility() -> None:
    message = format_tool_result(
        "cad.create_cylinder",
        {
            "label": "Eixo",
            "diameter_mm": 30.0,
            "height_mm": 60.0,
            "volume_mm3": 42411.5,
        },
    )
    assert "diâmetro 30 mm" in message
    assert "altura 60 mm" in message
    assert "eixo Z" in message
    assert "pode ser desfeita" in message


def test_result_formatter_escapes_document_labels() -> None:
    message = format_tool_result(
        "cad.get_document_summary",
        {"active": True, "label": "<img src=x>", "objects": []},
    )
    assert "<img" not in message
    assert "&lt;img" in message


def test_context_result_formatter_reports_revision_and_recent_objects() -> None:
    message = format_tool_result(
        "cad.get_context_snapshot",
        {
            "active": True,
            "document_label": "Peça",
            "state_token": {"revision": 3},
            "summary": {
                "object_count": 2,
                "selected_count": 1,
                "error_count": 0,
            },
            "recent_objects": ["Box"],
        },
    )

    assert "revisão 3" in message
    assert "2 objetos" in message
    assert "recentes: Box" in message
