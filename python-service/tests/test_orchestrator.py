"""测试 Agent 编排器"""

from agent.orchestrator import Orchestrator
from agent.state import StepType
from unittest.mock import Mock


class TestStepTypeMapping:
    """测试步骤名称到步骤类型的映射"""

    def test_memory_steps_are_not_mapped_to_tool_call(self):
        """会话记忆步骤应该走专用执行器，而不是通用工具调用。"""
        orchestrator = Orchestrator.__new__(Orchestrator)

        assert orchestrator._get_step_type("memory_read") == StepType.MEMORY_READ
        assert orchestrator._get_step_type("memory_write") == StepType.MEMORY_WRITE
        assert orchestrator._get_step_type("memory_compress") == StepType.MEMORY_COMPRESS


class _Planner:
    def plan_steps(self, state):
        return ["answer_generation", "memory_write"]

    def should_terminate(self, state):
        return False, "正常运行中"


class _Executor:
    def __init__(self):
        self.calls = []

    def execute_step(self, state, step):
        self.calls.append(step.step_name)
        step.start()
        if step.step_type == StepType.ANSWER_GENERATION:
            step.complete({"answer": "回答", "sources": []})
        else:
            step.complete({"success": True})


class _Policies:
    def validate_input(self, input_text):
        return True, None

    def should_retry(self, retry_count, error):
        return False

    def format_response(self, answer, sources, success, task_type):
        return {"answer": answer, "sources": sources, "task_type": task_type}


def _orchestrator_for_lifecycle_test():
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.planner = _Planner()
    orchestrator.executor = _Executor()
    orchestrator.event_bus = Mock()
    orchestrator.policies = _Policies()
    orchestrator._states = {}
    return orchestrator


def test_sync_run_executes_memory_write_after_answer_generation():
    orchestrator = _orchestrator_for_lifecycle_test()

    result = orchestrator.run("问题", conversation_id="conversation-1")

    assert orchestrator.executor.calls == ["answer_generation", "memory_write"]
    assert result["answer"] == "回答"


def test_stream_run_executes_memory_write_after_answer_generation():
    orchestrator = _orchestrator_for_lifecycle_test()

    list(orchestrator.run_stream("问题", conversation_id="conversation-1"))

    assert orchestrator.executor.calls == ["answer_generation", "memory_write"]
