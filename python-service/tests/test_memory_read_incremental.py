from unittest.mock import Mock

from tools.memory_read import ConversationMemoryReadTool


def test_summary_updates_only_newly_aged_messages(monkeypatch):
    from tools import memory_read

    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
        for index in range(14)
    ]
    redis = Mock()
    redis.get_message_count.return_value = len(messages)
    redis.get_messages.return_value = messages[-memory_read.KEEP_RECENT:]
    redis.get_all_messages.return_value = messages
    redis.get_summary.return_value = "已有摘要"
    redis.get_summary_count.return_value = 6
    monkeypatch.setattr(memory_read, "redis_client", redis)

    tool = ConversationMemoryReadTool.__new__(ConversationMemoryReadTool)
    tool.llm_service = Mock()
    tool._compress_history = Mock(return_value="更新摘要")

    result = tool.execute({"conversation_id": "conversation-1"})

    tool._compress_history.assert_called_once_with(
        messages[6:8],
        "conversation-1",
        prior_summary="已有摘要",
    )
    redis.set_summary.assert_called_once_with(
        "conversation-1",
        "更新摘要",
        covered_count=8,
    )
    assert result["compressed"] is True
