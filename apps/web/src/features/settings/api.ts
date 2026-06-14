import { apiRequest } from "../../api/http";
import type { AppSettings, SettingsConnectionTestResult } from "./types";

export function getSettings() {
  return apiRequest<AppSettings>("/api/settings");
}

export function updateSettings(payload: AppSettings) {
  return apiRequest<AppSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function testSettingsConnection(payload: AppSettings) {
  return apiRequest<SettingsConnectionTestResult>("/api/settings/test-connection", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function testVisionSettingsConnection(payload: AppSettings) {
  return apiRequest<SettingsConnectionTestResult>("/api/settings/test-vision", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
