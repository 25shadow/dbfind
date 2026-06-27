import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAgentPlan,
  createExport,
  createQuery,
  deleteAgentTask,
  deleteQuery,
  executeAgentPlan,
  getAgentTask,
  listAgentTasks,
  listQueryHistory,
  previewAgentPlan,
  runAgentQueryStage
} from "./api";

export function useCreateQuery() {
  return useMutation({
    mutationFn: createQuery
  });
}

export function useCreateAgentPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createAgentPlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
    }
  });
}

export function useExecuteAgentPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: executeAgentPlan,
    onSuccess: (_data, variables) => {
      if (variables.taskId) {
        queryClient.invalidateQueries({ queryKey: ["agent-task", variables.taskId] });
      }
      queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
    }
  });
}

export function usePreviewAgentPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: previewAgentPlan,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
    }
  });
}

export function useRunAgentQueryStage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runAgentQueryStage,
    onSuccess: (task) => {
      queryClient.setQueryData(["agent-task", task.id], task);
      queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
    }
  });
}

export function useAgentTask(taskId?: string) {
  return useQuery({
    queryKey: ["agent-task", taskId],
    queryFn: () => getAgentTask(taskId || ""),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "planned" || status === "querying" || status === "executing" ? 1200 : false;
    }
  });
}

export function useAgentTasks() {
  return useQuery({
    queryKey: ["agent-tasks"],
    queryFn: listAgentTasks
  });
}

export function useQueryHistory(keyword?: string) {
  return useQuery({
    queryKey: ["query-history", keyword ?? ""],
    queryFn: () => listQueryHistory(keyword)
  });
}

export function useCreateExport() {
  return useMutation({
    mutationFn: createExport
  });
}

export function useDeleteQuery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteQuery,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["query-history"] });
    }
  });
}

export function useDeleteAgentTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteAgentTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
    }
  });
}
