from agent.executor import Executor


def make_executor():
    return Executor.__new__(Executor)


def test_normalize_chunk_recovers_metadata_from_serialized_dict():
    executor = make_executor()
    raw_chunk = {
        "content": (
            "{'content': '术后夜间疼痛明显时，应观察疼痛评分、生命体征和切口渗血。', "
            "'metadata': {'source': '术后护理指南.pdf', 'doc_id': 12, 'page': 3, 'chunk_index': 1}}"
        ),
        "score": 0.72,
    }

    chunk = executor._normalize_chunk(raw_chunk)
    source = executor._source_from_chunk(chunk)

    assert chunk["content"] == "术后夜间疼痛明显时，应观察疼痛评分、生命体征和切口渗血。"
    assert chunk["metadata"]["source"] == "术后护理指南.pdf"
    assert source["title"] == "术后护理指南.pdf"
    assert source["doc_id"] == 12
    assert source["page"] == 3
    assert source["chunk_index"] == 1
    assert "生命体征" in source["snippet"]


def test_source_from_chunk_skips_empty_metadata():
    executor = make_executor()

    assert executor._source_from_chunk({"content": "无来源片段", "metadata": {}}) == {}
