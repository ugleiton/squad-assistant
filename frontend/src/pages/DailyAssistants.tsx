import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ChatConnection, DailyAssistant, Member } from "../api";
import { useList } from "../useList";

type Form = Omit<DailyAssistant, "id"> & { id?: number };
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

const empty = (): Form => ({
  name: "", enabled: true, language: "en", timezone: browserTz, delivery: "bot",
  chat_connection_id: null, channel_id: "", webhook_url: "", lead_time_minutes: 10,
  rotation_mode: "daily", meeting_url: "", schedules: [], participants: [],
});

export default function DailyAssistants() {
  const { t } = useTranslation();
  const list = useList<DailyAssistant>("/daily-assistants");
  const chats = useList<ChatConnection>("/chat-connections");
  const members = useList<Member>("/members");
  const [form, setForm] = useState<Form>(empty());
  const [error, setError] = useState<string | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const body = { ...form, webhook_url: form.webhook_url || null };
    try {
      if (form.id) await api.put(`/daily-assistants/${form.id}`, body);
      else await api.post("/daily-assistants", body);
      setForm(empty());
      list.reload();
    } catch (err) { setError(String(err)); }
  };

  const scheduleFor = (d: number) => form.schedules.find((s) => s.weekday === d);
  const setSchedule = (d: number, time: string | null) => setForm((f) => ({
    ...f, schedules: [...f.schedules.filter((s) => s.weekday !== d), ...(time ? [{ weekday: d, time }] : [])],
  }));
  const isParticipant = (id: number) => form.participants.some((p) => p.member_id === id);
  const toggleParticipant = (id: number) => setForm((f) => ({
    ...f,
    participants: isParticipant(id)
      ? f.participants.filter((p) => p.member_id !== id)
      : [...f.participants, { member_id: id, order: f.participants.length, active: true }],
  }));
  const nameOf = (id?: number | null) => members.items.find((m) => m.id === id)?.name ?? "—";

  return (
    <>
      <section className="card">
        <h2>{t("nav.daily")}</h2>
        <table>
          <tbody>
            {list.items.map((a) => (
              <tr key={a.id}>
                <td><b>{a.name}</b> {a.enabled ? "" : `(${t("common.disabled")})`}</td>
                <td>{a.schedules.map((s) => `${t(`weekday.${s.weekday}`)} ${s.time.slice(0, 5)}`).join(", ")}</td>
                <td>{t("daily.facilitator")}: {nameOf(a.current_facilitator_id)}</td>
                <td>
                  <button className="link" onClick={() => setForm({ ...a, webhook_url: "" })}>{t("common.edit")}</button>
                  <button className="link" onClick={() => api.post(`/daily-assistants/${a.id}/send-test`)}>{t("daily.send_test")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <form className="card" onSubmit={save}>
        <h2>{form.id ? t("common.edit") : t("daily.new")}</h2>
        <div className="row">
          <label>{t("common.name")}<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>{t("daily.timezone")}<input required value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></label>
          <label>{t("common.bot_language")}
            <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              <option>en</option><option>pt_BR</option>
            </select>
          </label>
          <label className="inline"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> {t("common.enabled")}</label>
        </div>
        <h3>{t("daily.schedule")}</h3>
        <div className="row">
          {WEEKDAYS.map((d) => (
            <label key={d}>
              <span><input type="checkbox" checked={!!scheduleFor(d)} onChange={(e) => setSchedule(d, e.target.checked ? "09:30" : null)} /> {t(`weekday.${d}`)}</span>
              <input type="time" disabled={!scheduleFor(d)} value={scheduleFor(d)?.time.slice(0, 5) ?? ""} onChange={(e) => setSchedule(d, e.target.value)} />
            </label>
          ))}
        </div>
        <h3>{t("daily.participants")}</h3>
        <div className="row">
          {members.items.map((m) => (
            <label key={m.id} className="inline"><input type="checkbox" checked={isParticipant(m.id)} onChange={() => toggleParticipant(m.id)} /> {m.name}</label>
          ))}
        </div>
        <div className="row">
          <label>{t("daily.rotation")}
            <select value={form.rotation_mode} onChange={(e) => setForm({ ...form, rotation_mode: e.target.value as Form["rotation_mode"] })}>
              <option value="none">{t("daily.rotation_none")}</option>
              <option value="daily">{t("daily.rotation_daily")}</option>
              <option value="weekly">{t("daily.rotation_weekly")}</option>
            </select>
          </label>
          <label>{t("daily.lead_time")}<input type="number" min={0} value={form.lead_time_minutes} onChange={(e) => setForm({ ...form, lead_time_minutes: Number(e.target.value) })} /></label>
          <label style={{ flex: 1 }}>{t("daily.meeting_url")}<input value={form.meeting_url ?? ""} onChange={(e) => setForm({ ...form, meeting_url: e.target.value })} /></label>
        </div>
        <h3>{t("daily.delivery")}</h3>
        <div className="row">
          <label>
            <select value={form.delivery} onChange={(e) => setForm({ ...form, delivery: e.target.value as Form["delivery"] })}>
              <option value="bot">{t("daily.delivery_bot")}</option>
              <option value="webhook">{t("daily.delivery_webhook")}</option>
            </select>
          </label>
          {form.delivery === "bot" ? (
            <>
              <label>{t("common.chat_connection")}
                <select required value={form.chat_connection_id ?? ""} onChange={(e) => setForm({ ...form, chat_connection_id: Number(e.target.value) })}>
                  <option value="" />{chats.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              <label>{t("common.channel_id")}<input required value={form.channel_id ?? ""} onChange={(e) => setForm({ ...form, channel_id: e.target.value })} /></label>
            </>
          ) : (
            <label style={{ flex: 1 }}>{t("daily.webhook_url")}
              <input type="password" required={!form.has_webhook_url} placeholder={form.has_webhook_url ? "••••••" : ""} value={form.webhook_url ?? ""} onChange={(e) => setForm({ ...form, webhook_url: e.target.value })} />
            </label>
          )}
        </div>
        {error && <p className="error">{error}</p>}
        <p><button className="primary">{t("common.save")}</button></p>
      </form>
    </>
  );
}
