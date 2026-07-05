"""测试 Agent 编排器"""

from agent.orchestrator import Orchestrator
from agent.state import StepType


class TestStepTypeMapping:
    """测试步骤名称到步骤类型的映射"""

    def test_memory_steps_are_not_mapped_to_tool_call(self):
        """会话记忆步骤应该走专用执行器，而不是通用工具调用。"""
        orchestrator = Orchestrator.__new__(Orchestrator)

        assert orchestrator._get_step_type("memory_read") == StepType.MEMORY_READ
        assert orchestrator._get_step_type("memory_write") == StepType.MEMORY_WRITE
        assert orchestrator._get_step_type("memory_compress") == StepType.MEMORY_COMPRESS

