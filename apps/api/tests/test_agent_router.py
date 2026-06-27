import pytest

from app.adapters.ai_adapter import AiResponseError
from app.services.agent_router import AgentRoute, AgentRouter


class FakeClassifier:
    def __init__(self, kind):
        self.kind = kind
        self.calls = []

    def classify_agent_route(self, instruction: str):
        self.calls.append(instruction)
        if isinstance(self.kind, Exception):
            raise self.kind
        return self.kind


def test_agent_router_routes_plain_questions_to_query_only():
    classifier = FakeClassifier("query_only")

    route = AgentRouter(classifier=classifier).route("仁化县2024年水田面积是多少")

    assert route == AgentRoute(kind="query_only")
    assert classifier.calls == ["仁化县2024年水田面积是多少"]


def test_agent_router_routes_query_report_generation_without_sdk_planning():
    classifier = FakeClassifier("report_generation")

    route = AgentRouter(classifier=classifier).route(
        "仁化县2022-2024年水田分别是多少，增长了多少，占全市比重多少，生成一张表格给我"
    )

    assert route == AgentRoute(kind="report_generation")


def test_agent_router_routes_editing_and_formatting_to_operation_planner():
    classifier = FakeClassifier("operation_planning")

    route = AgentRouter(classifier=classifier).route("把空值填成0并生成新表")

    assert route == AgentRoute(kind="operation_planning")


def test_agent_router_falls_back_to_readonly_query_when_classifier_fails():
    classifier = FakeClassifier(AiResponseError("model unavailable"))

    route = AgentRouter(classifier=classifier).route("生成一个工作簿")

    assert route == AgentRoute(kind="query_only")


def test_agent_router_falls_back_to_readonly_query_for_unknown_classifier_output():
    classifier = FakeClassifier("unknown")

    route = AgentRouter(classifier=classifier).route("生成一个工作簿")

    assert route == AgentRoute(kind="query_only")


@pytest.mark.parametrize("blank", ["", "   "])
def test_agent_router_does_not_call_classifier_for_blank_instruction(blank):
    classifier = FakeClassifier("operation_planning")

    route = AgentRouter(classifier=classifier).route(blank)

    assert route == AgentRoute(kind="query_only")
    assert classifier.calls == []
