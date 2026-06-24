from typing import TypedDict

from ai_service.app.schemas import ChatRequest, ChatResponse, IntentResult
from ai_service.app.services.chat_engine import ChatEngine


class ConsultationState(TypedDict, total=False):
    message: str
    intent: IntentResult
    response: ChatResponse


async def classify_node(state: ConsultationState) -> ConsultationState:
    engine = ChatEngine()
    intent = await engine.intent_classifier.classify(state["message"])
    return {**state, "intent": intent}


async def generate_node(state: ConsultationState) -> ConsultationState:
    engine = ChatEngine()
    response = await engine.answer(ChatRequest(message=state["message"]))
    return {**state, "response": response}


def build_consultation_graph():
    """Return a LangGraph graph when langgraph is installed; otherwise return node metadata."""
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return {"nodes": ["classify", "generate"], "edges": [("classify", "generate"), ("generate", "END")]}

    graph = StateGraph(ConsultationState)
    graph.add_node("classify", classify_node)
    graph.add_node("generate", generate_node)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
