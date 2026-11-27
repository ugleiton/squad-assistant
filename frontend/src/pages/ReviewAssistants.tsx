import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ChatConnection, GitLabConnection, Meta, ReviewAssistant, Squad } from "../api";
import { useList } from "../useList";

type Form = Omit<ReviewAssistant, "id" | "webhook_url"> & { id?: number };
type Creds = { webhook_url: string; webhook_token: string };

const empty = (meta?: Meta): Form => ({
  name: "", enabled: true, language: "en", chat_connection_id: 0, channel_id: "",
  gitlab_connection_id: 0, gitlab_projects: [], squad_ids: [], scan_interval_minutes: 5,
  emojis: { ...(meta?.review_emojis ?? {}) }, features: { ...(meta?.review_features ?? {}) },
});

export default function ReviewAssistants() {
  const { t } = useTranslation();
  const list = useList<ReviewAssistant>("/review-assistants");
  const chats = useList<ChatConnection>("/chat-connections");
  const gitlabs = useList<GitLabConnection>("/gitlab-connections");
  const squads = useList<Squad>("/squads");
  const [meta, setMeta] = useState<Meta>();
  const [form, setForm] = useState<Form>(empty());
  const [creds, setCreds] = useState<Creds | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Meta>("/meta").then((m) => { setMeta(m); setForm(empty(m)); });
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (form.id) await api.put(`/review-assistants/${form.id}`, form);
      else setCreds(await api.post<Creds>("/review-assistants", form));
      setForm(empty(meta));
      list.reload();
    } catch (err) { setError(String(err)); }
  };
  const regenerate = async (id: number) => setCreds(await api.post<Creds>(`/review-assistants/${id}/regenerate-token`));
  const scan = async (id: number) => {
    const r = await api.post<{ new_threads: number }>(`/review-assistants/${id}/scan`);
    alert(t("review.scan_result", { count: r.new_threads }));
  };
  const toggleSquad = (id: number) => setForm((f) => ({
    ...f, squad_ids: f.squad_ids.includes(id) ? f.squad_ids.filter((x) => x !== id) : [...f.squad_ids, id],
  }));

  return (
    <>
      {creds && (
        <div className="notice">
          <p><b>{t("review.webhook_title")}</b> {t("review.webhook_help")}</p>
          <p>URL: <code>{creds.webhook_url}</code></p>
          <p>Secret token: <code className="secret">{creds.webhook_token}</code></p>
          <button className="link" onClick={() => setCreds(null)}>{t("common.close")}</button>
        </div>
      )}
      <section className="card">
        <h2>{t("nav.review")}</h2>
        <table>
          <tbody>
            {list.items.map((a) => (
              <tr key={a.id}>
                <td><b>{a.name}</b> {a.enabled ? "" : `(${t("common.disabled")})`}</td>
                <td>#{a.channel_id}</td>
                <td><code>{a.webhook_url}</code></td>
                <td>
                  <button className="link" onClick={() => setForm(a)}>{t("common.edit")}</button>
                  <button className="link" onClick={() => regenerate(a.id)}>{t("review.regenerate")}</button>
                  <button className="link" onClick={() => scan(a.id)}>{t("review.scan_now")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <form className="card" onSubmit={save}>
        <h2>{form.id ? t("common.edit") : t("review.new")}</h2>
        <div className="row">
          <label>{t("common.name")}<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>{t("common.bot_language")}
            <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              {meta?.languages.map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
          <label className="inline"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> {t("common.enabled")}</label>
        </div>
        <div className="row">
          <label>{t("common.chat_connection")}
            <select required value={form.chat_connection_id || ""} onChange={(e) => setForm({ ...form, chat_connection_id: Number(e.target.value) })}>
              <option value="" />{chats.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>{t("common.channel_id")}<input required value={form.channel_id} onChange={(e) => setForm({ ...form, channel_id: e.target.value })} /></label>
          <label>{t("review.scan_interval")}<input type="number" min={1} value={form.scan_interval_minutes} onChange={(e) => setForm({ ...form, scan_interval_minutes: Number(e.target.value) })} /></label>
        </div>
        <div className="row">
          <label>GitLab
            <select required value={form.gitlab_connection_id || ""} onChange={(e) => setForm({ ...form, gitlab_connection_id: Number(e.target.value) })}>
              <option value="" />{gitlabs.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label style={{ flex: 1 }}>{t("review.projects")}
            <input placeholder="group/project, group/other" value={form.gitlab_projects.join(", ")}
              onChange={(e) => setForm({ ...form, gitlab_projects: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
          </label>
        </div>
        <h3>{t("review.squads")}</h3>
        <div className="row">
          {squads.items.map((s) => (
            <label key={s.id} className="inline"><input type="checkbox" checked={form.squad_ids.includes(s.id)} onChange={() => toggleSquad(s.id)} /> {s.name}</label>
          ))}
        </div>
        <h3>{t("review.status_emojis")}</h3>
        <div className="row">
          {Object.keys(meta?.review_emojis ?? {}).map((k) => (
            <label key={k}>{t(`review.state.${k}`)}
              <input value={form.emojis[k] ?? ""} onChange={(e) => setForm({ ...form, emojis: { ...form.emojis, [k]: e.target.value } })} />
            </label>
          ))}
        </div>
        <h3>{t("review.features_title")}</h3>
        <div className="row">
          {Object.keys(meta?.review_features ?? {}).map((k) => (
            <label key={k} className="inline">
              <input type="checkbox" checked={form.features[k] ?? true} onChange={(e) => setForm({ ...form, features: { ...form.features, [k]: e.target.checked } })} /> {t(`review.features.${k}`)}
            </label>
          ))}
        </div>
        {error && <p className="error">{error}</p>}
        <p><button className="primary">{t("common.save")}</button></p>
      </form>
    </>
  );
}
