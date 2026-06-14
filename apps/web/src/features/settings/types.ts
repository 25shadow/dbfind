export type AppSettings = {
  ai_base_url: string;
  ai_chat_path: string;
  model: string;
  api_key: string;
  vision_ai_base_url: string;
  vision_ai_chat_path: string;
  vision_model: string;
  vision_api_key: string;
};

export type SettingsConnectionTestResult = {
  ok: boolean;
  message: string;
  model: string;
};
