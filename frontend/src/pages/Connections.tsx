import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ChatConnection, GitLabConnection } from "../api";
import { useList } from "../useList";

export default function Connections() {
  const { t } = useTranslation();
  const chats = useList<ChatConnection>("/chat-connections");
  const gitlabs = useList<GitLabConnection>("/gitlab-connections");
  const [chat, setChat] = useState({ name: "", provider: "slack", base_url: "", bot_token: "" });
  const [gl, setGl] = useState({ name: "", base_url: "https://gitlab.com", access_token: "" });

  const addChat = async (e: FormEvent) => {
    e.preventDefault();
    await api.post("/chat-connections", { ...chat, base_url: chat.base_url || null });
    setChat({ ...chat, name: "", bot_token: "" });
    chats.reload();
  };
  const addGl = async (e: FormEvent) => {
    e.preventDefault();
    await api.post("/gitlab-connections", gl);
    setGl({ ...gl, name: "", access_token: "" });
    gitlabs.reload();
  };

  return (
    <>
      <section className="card">
        <h2>{t("connections.chat")}</h2>
        <table>
          <tbody>
            {chats.items.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td><td>{c.provider}</td><td>{c.base_url}</td>
                <td>{c.has_token ? "🔑" : "—"}</td>
                <td><button className="link" onClick={() => api.del(`/chat-connections/${c.id}`).then(chats.reload)}>{t("common.delete")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <form className="row" onSubmit={addChat}>
          <label>{t("common.name")}<input required value={chat.name} onChange={(e) => setChat({ ...chat, name: e.target.value })} /></label>
          <label>{t("connections.provider")}
            <select value={chat.provider} onChange={(e) => setChat({ ...chat, provider: e.target.value })}>
              <option value="slack">Slack</option><option value="mattermost">Mattermost</option>
            </select>
          </label>
          {chat.provider === "mattermost" && (
            <label>{t("connections.server_url")}<input required value={chat.base_url} onChange={(e) => setChat({ ...chat, base_url: e.target.value })} /></label>
          )}
          <label>{t("connections.bot_token")}<input type="password" required value={chat.bot_token} onChange={(e) => setChat({ ...chat, bot_token: e.target.value })} /></label>
          <button className="primary">{t("common.add")}</button>
        </form>
      </section>
      <section className="card">
        <h2>GitLab</h2>
        <table>
          <tbody>
            {gitlabs.items.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td><td>{c.base_url}</td><td>{c.has_token ? "🔑" : "—"}</td>
                <td><button className="link" onClick={() => api.del(`/gitlab-connections/${c.id}`).then(gitlabs.reload)}>{t("common.delete")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <form className="row" onSubmit={addGl}>
          <label>{t("common.name")}<input required value={gl.name} onChange={(e) => setGl({ ...gl, name: e.target.value })} /></label>
          <label>URL<input required value={gl.base_url} onChange={(e) => setGl({ ...gl, base_url: e.target.value })} /></label>
          <label>{t("connections.access_token")}<input type="password" required value={gl.access_token} onChange={(e) => setGl({ ...gl, access_token: e.target.value })} /></label>
          <button className="primary">{t("common.add")}</button>
        </form>
      </section>
    </>
  );
}
