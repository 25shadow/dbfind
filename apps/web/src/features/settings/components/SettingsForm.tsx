import { useEffect, useState } from "react";
import { useSettings, useTestSettingsConnection, useTestVisionSettingsConnection, useUpdateSettings } from "../hooks";

export function SettingsForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();
  const testConnectionMutation = useTestSettingsConnection();
  const testVisionConnectionMutation = useTestVisionSettingsConnection();
  const [aiBaseUrl, setAiBaseUrl] = useState("");
  const [aiChatPath, setAiChatPath] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [visionAiBaseUrl, setVisionAiBaseUrl] = useState("");
  const [visionAiChatPath, setVisionAiChatPath] = useState("");
  const [visionModel, setVisionModel] = useState("");
  const [visionApiKey, setVisionApiKey] = useState("");

  useEffect(() => {
    if (settings) {
      setAiBaseUrl(settings.ai_base_url);
      setAiChatPath(settings.ai_chat_path);
      setModel(settings.model);
      setApiKey(settings.api_key);
      setVisionAiBaseUrl(settings.vision_ai_base_url);
      setVisionAiChatPath(settings.vision_ai_chat_path);
      setVisionModel(settings.vision_model);
      setVisionApiKey(settings.vision_api_key);
    }
  }, [settings]);

  if (isLoading) {
    return <div className="muted">正在读取配置...</div>;
  }

  const settingsPayload = {
    ai_base_url: aiBaseUrl,
    ai_chat_path: aiChatPath,
    model,
    api_key: apiKey,
    vision_ai_base_url: visionAiBaseUrl,
    vision_ai_chat_path: visionAiChatPath,
    vision_model: visionModel,
    vision_api_key: visionApiKey
  };
  const canTestAgent = Boolean(aiBaseUrl.trim() && aiChatPath.trim() && model.trim());
  const canTestVision = Boolean(visionAiBaseUrl.trim() && visionAiChatPath.trim() && visionModel.trim());

  return (
    <form
      className="settings-form"
      onSubmit={(event) => {
        event.preventDefault();
        updateMutation.mutate(settingsPayload);
      }}
    >
      <section className="settings-section">
        <div className="settings-section-head">
          <div className="settings-section-title">
            <span className="settings-section-kicker">Conversation</span>
            <h2>Agent / 查询模型</h2>
            <p>用于任务规划、Text2SQL、结果解释和普通对话式 Excel 操作。</p>
          </div>
          <button
            className="settings-test-button"
            type="button"
            disabled={testConnectionMutation.isPending || !canTestAgent}
            onClick={() => testConnectionMutation.mutate(settingsPayload)}
          >
            {testConnectionMutation.isPending ? "测试中..." : "测试连接"}
          </button>
        </div>
        <div className="settings-field-grid">
          <label>
            <span>AI API 地址</span>
            <input
              value={aiBaseUrl}
              placeholder="https://api.openai.com"
              onChange={(event) => setAiBaseUrl(event.target.value)}
            />
          </label>
          <label>
            <span>Chat 接口路径</span>
            <input
              value={aiChatPath}
              placeholder="/v1/chat/completions"
              onChange={(event) => setAiChatPath(event.target.value)}
            />
          </label>
          <label>
            <span>模型名</span>
            <input
              value={model}
              placeholder="gpt-4o-mini / deepseek-chat / qwen-plus"
              onChange={(event) => setModel(event.target.value)}
            />
          </label>
          <label>
            <span>API Key</span>
            <input
              type="password"
              value={apiKey}
              placeholder="sk-..."
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
        </div>
        <div className="settings-section-status">
          {testConnectionMutation.data && (
            <span className={testConnectionMutation.data.ok ? "success-text" : "error-text"}>
              {testConnectionMutation.data.message}
            </span>
          )}
          {testConnectionMutation.isError && <span className="error-text">测试连接失败</span>}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-head">
          <div className="settings-section-title">
            <span className="settings-section-kicker">Vision</span>
            <h2>Excel 视觉结构识别</h2>
            <p>用于复杂表格截图识别，只输出单元格坐标计划，数据仍从 Excel 原始单元格读取。</p>
          </div>
          <button
            className="settings-test-button"
            type="button"
            disabled={testVisionConnectionMutation.isPending || !canTestVision}
            onClick={() =>
              testVisionConnectionMutation.mutate({
                ai_base_url: visionAiBaseUrl,
                ai_chat_path: visionAiChatPath,
                model: visionModel,
                api_key: visionApiKey,
                vision_ai_base_url: visionAiBaseUrl,
                vision_ai_chat_path: visionAiChatPath,
                vision_model: visionModel,
                vision_api_key: visionApiKey
              })
            }
          >
            {testVisionConnectionMutation.isPending ? "测试中..." : "测试视觉模型"}
          </button>
        </div>
        <div className="settings-field-grid">
          <label>
            <span>视觉 API 地址</span>
            <input
              value={visionAiBaseUrl}
              placeholder="https://api.openai.com"
              onChange={(event) => setVisionAiBaseUrl(event.target.value)}
            />
          </label>
          <label>
            <span>视觉 Chat 接口路径</span>
            <input
              value={visionAiChatPath}
              placeholder="/v1/chat/completions"
              onChange={(event) => setVisionAiChatPath(event.target.value)}
            />
          </label>
          <label>
            <span>视觉模型名</span>
            <input
              value={visionModel}
              placeholder="gpt-4o / gpt-4.1 / 支持图片输入的模型"
              onChange={(event) => setVisionModel(event.target.value)}
            />
          </label>
          <label>
            <span>视觉 API Key</span>
            <input
              type="password"
              value={visionApiKey}
              placeholder="留空则不会调用 VLM"
              onChange={(event) => setVisionApiKey(event.target.value)}
            />
          </label>
        </div>
        <div className="settings-section-status">
          {testVisionConnectionMutation.data && (
            <span className={testVisionConnectionMutation.data.ok ? "success-text" : "error-text"}>
              {testVisionConnectionMutation.data.message}
            </span>
          )}
          {testVisionConnectionMutation.isError && <span className="error-text">测试视觉模型失败</span>}
        </div>
      </section>
      <div className="settings-actions">
        <button type="submit" disabled={updateMutation.isPending}>
          保存配置
        </button>
        <span className="settings-save-hint">测试不会自动保存；确认无误后再保存当前配置。</span>
      </div>
      {updateMutation.isSuccess && <span className="success-text">配置已保存</span>}
      {updateMutation.isError && <span className="error-text">配置保存失败</span>}
    </form>
  );
}
