"""LangGraph workflow definition.

triage -> plan -> [log_analysis | code_analysis | knowledge_retrieval] (parallel, via Send)
       -> aggregate -> review --(insufficient, budget left)--> plan
                              --(sufficient or budget spent)--> report
       -> policy_gate --(approval required)--> human_approval (interrupt) -> execute_actions
                      --(not required)-------------------------------------> execute_actions
"""

from __future__ import annotations

from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.context import WorkflowContext
from app.graph.edges import route_after_policy, route_after_review, route_investigations
from app.graph.nodes import NODES, instrumented
from app.graph.state import IncidentState

INVESTIGATION_NODES = ("log_analysis", "code_analysis", "knowledge_retrieval")


def build_workflow(
    checkpointer: BaseCheckpointSaver | None, *, max_rounds: int = 2
) -> CompiledStateGraph:
    graph = StateGraph(IncidentState, context_schema=WorkflowContext)
    for name, fn in NODES.items():
        graph.add_node(name, instrumented(name, fn))

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "plan")
    graph.add_conditional_edges("plan", route_investigations, [*INVESTIGATION_NODES, "aggregate"])
    for name in INVESTIGATION_NODES:
        graph.add_edge(name, "aggregate")
    graph.add_edge("aggregate", "review")
    graph.add_conditional_edges(
        "review", partial(route_after_review, max_rounds=max_rounds), ["plan", "report"]
    )
    graph.add_edge("report", "policy_gate")
    graph.add_conditional_edges(
        "policy_gate", route_after_policy, ["human_approval", "execute_actions"]
    )
    graph.add_edge("human_approval", "execute_actions")
    graph.add_edge("execute_actions", END)

    return graph.compile(checkpointer=checkpointer, name="atlas-incident-investigation")
