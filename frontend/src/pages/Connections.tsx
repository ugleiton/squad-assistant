import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ChatConnection, GitLabConnection } from "../api";
import { Notice, Status } from "../Notice";
import { useList } from "../useList";

export default function Connections() {
  const { t } = useTranslation();
  const chats = useList<ChatConnection>("/chat-connections");
  const gitlabs = useList<GitLabConnection>("/gitlab-connections");
  const [chat, setChat] = useState({ name: "", provider: "slack", base_url: "", bot_token: "" });
  const [gl, setGl] = useState({ name: "", base_url: "https://gitlab.com", access_token: "" });
  const [status, setStatus] = useState<Status>(null);
  const testChat = async (id: number) => {
    try {
      const r = await api.post<{ bot_user_id: string }>(`/chat-connections/${id}/test`);
      setStatus({ kind: "ok", text: t("connections.test_ok_chat", { id: r.bot_user_id }) });
      chats.reload();
    } catch (e) { setStatus({ kind: "error", text: String(e) }); }
  };
  const testGl = async (id: number) => {
    try {
      const r = await api.post<{ username: string }>(`/gitlab-connections/${id}/test`);
      setStatus({ kind: "ok", text: t("connections.test_ok_gitlab", { user: r.username }) });
    } catch (e) { setStatus({ kind: "error", text: String(e) }); }
  };

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
      <Notice status={status} onClose={() => setStatus(null)} />
      <section className="card">
        <h2>{t("connections.chat")}</h2>
        <table>
          <tbody>
            {chats.items.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td><td>{c.provider}</td><td>{c.base_url}</td>
                <td>{c.has_token ? "🔑" : "—"}</td>
                <td>
                  <button className="link" onClick={() => testChat(c.id)}>{t("connections.test")}</button>
                  <button className="link" onClick={() => api.del(`/chat-connections/${c.id}`).then(chats.reload)}>{t("common.delete")}</button>
                </td>
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
                <td>
                  <button className="link" onClick={() => testGl(c.id)}>{t("connections.test")}</button>
                  <button className="link" onClick={() => api.del(`/gitlab-connections/${c.id}`).then(gitlabs.reload)}>{t("common.delete")}</button>
                </td>
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
