import { SettingsForm } from "../features/settings/components/SettingsForm";

export function SettingsPage() {
  return (
    <section className="page-section settings-page">
      <div className="settings-page-heading">
        <h1>设置</h1>
        <p>配置查询 Agent 和 Excel 视觉识别模型。测试动作放在各自分区内，保存只负责写入当前配置。</p>
      </div>
      <SettingsForm />
    </section>
  );
}
