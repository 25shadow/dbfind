import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSettings, testSettingsConnection, testVisionSettingsConnection, updateSettings } from "./api";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: getSettings
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    }
  });
}

export function useTestSettingsConnection() {
  return useMutation({
    mutationFn: testSettingsConnection
  });
}

export function useTestVisionSettingsConnection() {
  return useMutation({
    mutationFn: testVisionSettingsConnection
  });
}
