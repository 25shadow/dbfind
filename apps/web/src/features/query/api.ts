import { apiRequest } from "../../api/http";
import type {
  AgentRequest,
  AgentExecuteRequest,
  AgentExecuteResult,
  AgentPreviewRequest,
  AgentOperationPreview,
  AgentTaskListResult,
  AgentTaskItem,
  AgentTaskResult,
  ExportRequest,
  ExportResult,
  QueryRequest,
  QueryResult
} from "./types";

export function createQuery(payload: QueryRequest) {
  return apiRequest<QueryResult>("/api/query", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createAgentPlan(payload: AgentRequest) {
  return apiRequest<AgentTaskResult>("/api/agent/plan", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function executeAgentPlan(payload: AgentExecuteRequest) {
  return apiRequest<AgentExecuteResult>("/api/agent/execute", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function previewAgentPlan(payload: AgentPreviewRequest) {
  return apiRequest<AgentOperationPreview>("/api/agent/preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runAgentQueryStage(taskId: string) {
  return apiRequest<AgentTaskItem>(`/api/agent/tasks/${taskId}/run-query`, {
    method: "POST"
  });
}

export function getAgentTask(taskId: string) {
  return apiRequest<AgentTaskItem>(`/api/agent/tasks/${taskId}`);
}

export function listAgentTasks() {
  return apiRequest<AgentTaskListResult>("/api/agent/tasks");
}

export function listQueryHistory(keyword?: string) {
  const searchParams = new URLSearchParams();
  if (keyword?.trim()) {
    searchParams.set("keyword", keyword.trim());
  }

  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiRequest<QueryResult[]>(`/api/query/history${suffix}`);
}

export function deleteQuery(queryId: string) {
  return apiRequest<void>(`/api/query/${queryId}`, {
    method: "DELETE"
  });
}

export function deleteAgentTask(taskId: string) {
  return apiRequest<void>(`/api/agent/tasks/${taskId}`, {
    method: "DELETE"
  });
}

export function createExport(payload: ExportRequest) {
  return apiRequest<ExportResult>("/api/export", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
