from importlib import import_module


def test_freecad_facing_modules_import_without_freecad_installed() -> None:
    import_module("aicad.adapters.freecad_adapter")
    import_module("aicad.runtime")
    import_module("aicad.ui.chat_panel")
    import_module("aicad.orchestration")
    import_module("aicad.orchestration.turn_controller")
    import_module("aicad.orchestration.plans")
    import_module("aicad.orchestration.plan_service")
    import_module("aicad.core.tool_results")
    import_module("aicad.core.context")
    import_module("aicad.core.tool_selector")
    import_module("aicad.evaluation.benchmark")
