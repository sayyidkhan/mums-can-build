from app.voice_pm import decide_next_step


def test_voice_pm_asks_for_more_detail_on_short_input() -> None:
    decision = decide_next_step("build app")

    assert decision.kind == "question"
    assert decision.question


def test_voice_pm_creates_structured_task_for_build_request() -> None:
    decision = decide_next_step("Build a cake order app with a menu and checkout request form")

    assert decision.kind == "task_ready"
    assert decision.task is not None
    assert "cake order app" in decision.task.user_goal
    assert decision.task.requirements
    assert decision.task.acceptance_criteria
