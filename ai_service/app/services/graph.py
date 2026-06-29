from typing import TypedDict

from ai_service.app.schemas import ChatRequest, ChatResponse, IntentResult
from ai_service.app.services.chat_engine import ChatEngine


class ConsultationState(TypedDict, total=False):
    message: str
    intent: IntentResult
    response: ChatResponse
    emergency: bool
    cache_hit: bool


async def safety_node(state: ConsultationState) -> ConsultationState:
    engine = ChatEngine()
    intent = engine.intent_classifier.emergency_filter(state["message"])
    if intent:
        return {**state, "intent": intent, "emergency": True}
    return {**state, "emergency": False}


async def classify_node(state: ConsultationState) -> ConsultationState:
    if state.get("intent"):
        return state
    engine = ChatEngine()
    intent = await engine.intent_classifier.classify(state["message"])
    return {**state, "intent": intent}


async def generate_node(state: ConsultationState) -> ConsultationState:
    engine = ChatEngine()
    response = await engine.answer(ChatRequest(message=state["message"]))
    return {**state, "response": response, "cache_hit": response.cache_hit_level in {"L1", "L2", "L3"}}


def build_consultation_graph():
    """Build the consultation graph described in the design document.

    When langgraph is unavailable, return node metadata so tests and the admin
    surface can still inspect the intended orchestration.
    """
    nodes = [
        "safety_filter",
        "cache_lookup",
        "intent_classification",
        "low_confidence_clarify",
        "rag_retrieval",
        "llm_generate",
        "post_process",
        "persist",
    ]
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return {
            "nodes": nodes,
            "edges": [
                ("safety_filter", "intent_classification"),
                ("intent_classification", "llm_generate"),
                ("llm_generate", "post_process"),
                ("post_process", "persist"),
                ("persist", "END"),
            ],
        }

    graph = StateGraph(ConsultationState)
    graph.add_node("safety_filter", safety_node)
    graph.add_node("intent_classification", classify_node)
    graph.add_node("llm_generate", generate_node)
    graph.set_entry_point("safety_filter")
    graph.add_edge("safety_filter", "intent_classification")
    graph.add_edge("intent_classification", "llm_generate")
    graph.add_edge("llm_generate", END)
    return graph.compile()
