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


def test_sync_run_saves_final_reply_after_generation():
    from .test_agent_loop import make_agent, QUESTION
    agent = make_agent()
    result = agent.run(QUESTION, conversation_id="conversation-1", run_id="sync")
    saved = agent.executor.memory_agent.save_memory.call_args.args
    assert saved[2] == result["answer"]
    assert agent.get_state("sync").steps[-1].step_name == "memory_write"


def test_stream_run_saves_final_reply_after_verification():
    from .test_agent_loop import make_agent, QUESTION
    agent = make_agent()
    list(agent.run_stream(QUESTION, conversation_id="conversation-1", run_id="stream"))
    agent.executor.memory_agent.save_memory.assert_called_once()
    assert agent.get_state("stream").steps[-1].step_name == "memory_write"
