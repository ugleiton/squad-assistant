import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, Member, Squad } from "../api";
import { useList } from "../useList";

export default function Squads() {
  const { t } = useTranslation();
  const members = useList<Member>("/members");
  const squads = useList<Squad>("/squads");
  const emptyMember = { name: "", chat_user_id: "", chat_username: "", gitlab_username: "" };
  const [m, setM] = useState<typeof emptyMember & { id?: number }>(emptyMember);
  const [squad, setSquad] = useState<{ id?: number; name: string; member_ids: number[] }>({ name: "", member_ids: [] });

  const addMember = async (e: FormEvent) => {
    e.preventDefault();
    if (m.id) await api.put(`/members/${m.id}`, m);
    else await api.post("/members", m);
    setM(emptyMember);
    members.reload();
  };
  const saveSquad = async (e: FormEvent) => {
    e.preventDefault();
    if (squad.id) await api.put(`/squads/${squad.id}`, squad);
    else await api.post("/squads", squad);
    setSquad({ name: "", member_ids: [] });
    squads.reload();
  };
  const toggle = (id: number) =>
    setSquad((s) => ({ ...s, member_ids: s.member_ids.includes(id) ? s.member_ids.filter((x) => x !== id) : [...s.member_ids, id] }));
  const nameOf = (id: number) => members.items.find((x) => x.id === id)?.name ?? id;

  return (
    <>
      <section className="card">
        <h2>{t("squads.squads")}</h2>
        <table>
          <tbody>
            {squads.items.map((s) => (
              <tr key={s.id}>
                <td><b>{s.name}</b></td>
                <td>{s.member_ids.map(nameOf).join(", ")}</td>
                <td>
                  <button className="link" onClick={() => setSquad(s)}>{t("common.edit")}</button>
                  <button className="link" onClick={() => api.del(`/squads/${s.id}`).then(squads.reload)}>{t("common.delete")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form onSubmit={saveSquad}>
          <div className="row">
            <label>{t("common.name")}<input required value={squad.name} onChange={(e) => setSquad({ ...squad, name: e.target.value })} /></label>
            <button className="primary">{squad.id ? t("common.save") : t("common.add")}</button>
          </div>
          <div className="row">
            {members.items.map((x) => (
              <label key={x.id} className="inline">
                <input type="checkbox" checked={squad.member_ids.includes(x.id)} onChange={() => toggle(x.id)} /> {x.name}
              </label>
            ))}
          </div>
        </form>
      </section>
      <section className="card">
        <h2>{t("squads.members")}</h2>
        <table>
          <thead><tr><th>{t("common.name")}</th><th>{t("squads.chat_user_id")}</th><th>{t("squads.chat_username")}</th><th>GitLab</th><th /></tr></thead>
          <tbody>
            {members.items.map((x) => (
              <tr key={x.id}>
                <td>{x.name}</td><td>{x.chat_user_id}</td><td>{x.chat_username}</td><td>{x.gitlab_username}</td>
                <td>
                  <button className="link" onClick={() => setM({ id: x.id, name: x.name, chat_user_id: x.chat_user_id ?? "", chat_username: x.chat_username ?? "", gitlab_username: x.gitlab_username ?? "" })}>{t("common.edit")}</button>
                  <button className="link" onClick={() => api.del(`/members/${x.id}`).then(members.reload)}>{t("common.delete")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form className="row" onSubmit={addMember}>
          <label>{t("common.name")}<input required value={m.name} onChange={(e) => setM({ ...m, name: e.target.value })} /></label>
          <label>{t("squads.chat_user_id")}<input value={m.chat_user_id} onChange={(e) => setM({ ...m, chat_user_id: e.target.value })} /></label>
          <label>{t("squads.chat_username")}<input value={m.chat_username} onChange={(e) => setM({ ...m, chat_username: e.target.value })} /></label>
          <label>GitLab<input value={m.gitlab_username} onChange={(e) => setM({ ...m, gitlab_username: e.target.value })} /></label>
          <button className="primary">{m.id ? t("common.save") : t("common.add")}</button>
          {m.id && <button type="button" className="link" onClick={() => setM(emptyMember)}>{t("common.cancel")}</button>}
        </form>
      </section>
    </>
  );
}
