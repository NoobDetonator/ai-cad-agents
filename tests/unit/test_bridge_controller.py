from __future__ import annotations

from aicad.ui.bridge_controller import GuiBridgeController


class ReentrantDispatcher:
    def __init__(self, controller: GuiBridgeController) -> None:
        self.controller = controller
        self.expire_calls = 0
        self.process_calls = 0

    def expire_requests(self) -> None:
        self.expire_calls += 1
        self.controller._tick()

    def process_next(self) -> None:
        self.process_calls += 1


class RecordingPlanDispatcher:
    def __init__(self) -> None:
        self.process_calls = 0

    def process_next(self) -> None:
        self.process_calls += 1


def test_gui_bridge_tick_rejects_nested_event_loop_dispatch() -> None:
    controller = object.__new__(GuiBridgeController)
    controller._tick_running = False
    controller._dispatcher = ReentrantDispatcher(controller)
    controller._plan_dispatcher = RecordingPlanDispatcher()

    controller._tick()

    assert controller._dispatcher.expire_calls == 1
    assert controller._dispatcher.process_calls == 1
    assert controller._plan_dispatcher.process_calls == 1
    assert controller._tick_running is False
