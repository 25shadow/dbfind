from dataclasses import dataclass
from typing import Literal, Protocol

from app.adapters.ai_adapter import AiAdapter, AiResponseError


AgentRouteKind = Literal["query_only", "report_generation", "operation_planning"]


@dataclass(frozen=True)
class AgentRoute:
    kind: AgentRouteKind


class AgentRouteClassifier(Protocol):
    def classify_agent_route(self, instruction: str) -> AgentRouteKind:
        ...


class AiAgentRouteClassifier:
    def __init__(self, ai_adapter: AiAdapter | None = None) -> None:
        self.ai_adapter = ai_adapter or AiAdapter()

    def classify_agent_route(self, instruction: str) -> AgentRouteKind:
        return self.ai_adapter.classify_agent_route(instruction)


class AgentRouter:
    def __init__(self, classifier: AgentRouteClassifier | None = None) -> None:
        self.classifier = classifier or AiAgentRouteClassifier()

    def route(self, instruction: str) -> AgentRoute:
        text = instruction.strip()
        if not text:
            return AgentRoute(kind="query_only")

        try:
            kind = self.classifier.classify_agent_route(text)
        except (AiResponseError, ValueError):
            return AgentRoute(kind="query_only")

        if kind in {"query_only", "report_generation", "operation_planning"}:
            return AgentRoute(kind=kind)
        return AgentRoute(kind="query_only")
