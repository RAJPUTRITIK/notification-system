import { useEffect, useState } from "react";
import { api } from "./api";

const CHANNELS = [["whatsapp", "WhatsApp"], ["email", "Email"], ["push", "Web Push"]];

export default function Admin() {
  const [triggers, setTriggers] = useState([]);
  const [editing, setEditing] = useState(null); // {trigger, channel, tpl}
  const [logs, setLogs] = useState(null);
  const [msg, setMsg] = useState("");
  const [nt, setNt] = useState({ key: "", name: "" });
  const [showCountries, setShowCountries] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [filters, setFilters] = useState({ channel: "", trigger: "", success: "" });
  const loadLogs = () => {
    const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    api("/admin/logs/" + (q ? "?" + q : "")).then(setLogs).catch((e) => setMsg(e.message));
  };
  useEffect(() => { if (showLogs) loadLogs(); }, [showLogs, filters]);

  const load = () => api("/admin/triggers/").then(setTriggers).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);

  const act = async (fn) => { try { setMsg(""); await fn(); await load(); } catch (e) { setMsg("❌ " + e.message); } };
  const toggle = (t) => act(() => api(`/admin/templates/${t.id}/toggle/`, { method: "POST" }));
  const test = (t) => act(async () => { const r = await api(`/admin/templates/${t.id}/test/`, { method: "POST" }); setMsg("✅ Test sent: " + r.detail); });
  const addTrigger = (e) => { e.preventDefault(); act(async () => { await api("/admin/triggers/", { method: "POST", body: { ...nt, key: nt.key.replace(/\s+/g, "_").toLowerCase() } }); setNt({ key: "", name: "" }); }); };
  const delTrigger = (t) => confirm(`Delete trigger ${t.name}?`) && act(() => api(`/admin/triggers/${t.id}/`, { method: "DELETE" }));

  return (
    <div>
      <h2>Notification Settings</h2>
      {msg && <div className="toast inline">{msg}</div>}
      <table className="tbl">
        <thead><tr><th>Trigger</th>{CHANNELS.map(([, l]) => <th key={l}>{l}</th>)}<th /></tr></thead>
        <tbody>
          {triggers.map((tr) => (
            <tr key={tr.id}>
              <td><b>{tr.name}</b><div className="muted">{tr.key}</div></td>
              {CHANNELS.map(([ch]) => {
                const t = tr.templates.find((x) => x.channel === ch);
                return (
                  <td key={ch}>
                    {!t ? <button onClick={() => setEditing({ trigger: tr, channel: ch })}>+ Create</button> : (
                      <div className="cell">
                        <div className="muted">{t.name || "template"}{ch === "whatsapp" && <span className={`pill ${t.wa_status}`}>{t.wa_status}</span>}</div>
                        <label className="sw"><input type="checkbox" checked={t.is_active} onChange={() => toggle(t)} /> {t.is_active ? "On" : "Off"}</label>
                        <div>
                          <button onClick={() => setEditing({ trigger: tr, channel: ch, tpl: t })}>Edit</button>
                          <button onClick={() => test(t)}>Test</button>
                        </div>
                      </div>
                    )}
                  </td>
                );
              })}
              <td><button className="danger" onClick={() => delTrigger(tr)}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="row" onSubmit={addTrigger}>
        <input placeholder="New trigger name (e.g. Order shipped)" value={nt.name} onChange={(e) => setNt({ name: e.target.value, key: e.target.value })} required />
        <button className="primary">+ Add trigger</button>
      </form>
      <p className="muted">Test sends go to the logged-in admin’s email, phone and subscribed browser (set them in the Website tab).</p>

      <button onClick={() => setShowCountries(!showCountries)}>{showCountries ? "Hide" : "Manage"} countries</button>
      {showCountries && <Countries />}
      <button onClick={() => setShowLogs(!showLogs)}>{showLogs ? "Hide" : "Show"} delivery logs</button>
      {showLogs && <LogFilters filters={filters} setFilters={setFilters} triggers={triggers} onRefresh={loadLogs} />}
      {showLogs && logs && (
        <table className="tbl">
          <thead><tr><th>Time</th><th>Trigger</th><th>Channel</th><th>User</th><th>Result</th></tr></thead>
          <tbody>{logs.map((l) => (
            <tr key={l.id}><td>{new Date(l.created_at).toLocaleString()}</td><td>{l.trigger_key}{l.is_test && " (test)"}</td><td>{l.channel}</td><td>{l.user}</td>
              <td className={l.success ? "ok" : "err"}>{l.success ? "sent" : l.detail}</td></tr>))}</tbody>
        </table>
      )}

      {editing && <Editor {...editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function Editor({ trigger, channel, tpl, onClose, onSaved }) {
  const [f, setF] = useState({
    name: tpl?.name || `${trigger.key}-${channel}`, subject: tpl?.subject || "", title: tpl?.title || "",
    body: tpl?.body || "", wa_language: tpl?.wa_language || "en_US",
    vars: Object.entries(tpl?.variables || {}).map(([k, v]) => `${k}=${v}`).join("\n"),
  });
  const [err, setErr] = useState("");
  const [cur, setCur] = useState(tpl);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const save = async () => {
    setErr("");
    const variables = {};
    f.vars.split("\n").filter(Boolean).forEach((l) => { const [k, v] = l.split("="); if (k && v) variables[k.trim()] = v.trim(); });
    const body = { trigger: trigger.id, channel, name: f.name, subject: f.subject, title: f.title, body: f.body, wa_language: f.wa_language, variables };
    try {
      if (tpl) await api(`/admin/templates/${tpl.id}/`, { method: "PATCH", body });
      else await api("/admin/templates/", { method: "POST", body });
      onSaved();
    } catch (e) { setErr(e.message); }
  };
  const sync = async () => { try { setCur(await api(`/admin/templates/${tpl.id}/sync/`, { method: "POST" })); } catch (e) { setErr(e.message); } };

  return (
    <div className="modal" onClick={onClose}>
      <div className="card" onClick={(e) => e.stopPropagation()}>
        <h3>{tpl ? "Edit" : "Create"} {channel} template — {trigger.name}</h3>
        <input placeholder="Template name" value={f.name} onChange={set("name")} />
        {channel === "email" && <input placeholder="Subject" value={f.subject} onChange={set("subject")} />}
        {channel === "push" && <input placeholder="Push title" value={f.title} onChange={set("title")} />}
        <textarea rows={5} placeholder={channel === "whatsapp" ? "Hi {{1}}, welcome back!" : "Hi {{name}}, …"} value={f.body} onChange={set("body")} />
        {channel === "whatsapp" && <>
          <input placeholder="Language code (en_US)" value={f.wa_language} onChange={set("wa_language")} />
          <textarea rows={2} placeholder={"Variable mapping, one per line:\n1=name"} value={f.vars} onChange={set("vars")} />
          {cur && <p className="muted">Status: <span className={`pill ${cur.wa_status}`}>{cur.wa_status}</span> {cur.wa_note} <button onClick={sync}>Sync</button></p>}
        </>}
        {channel === "push" && <p className="muted">Web Push only (browser). iOS / Android are not used.</p>}
        <p className="muted">Variables: {"{{name}} {{username}} {{email}} {{order_id}}"}</p>
        {err && <p className="err">{err}</p>}
        <div className="row"><button className="primary" onClick={save}>Save</button><button onClick={onClose}>Cancel</button></div>
      </div>
    </div>
  );
}

function Countries() {
  const [list, setList] = useState([]);
  const [n, setN] = useState({ name: "", iso_code: "", dial_code: "" });
  const [err, setErr] = useState("");
  const load = () => api("/admin/countries/").then(setList);
  useEffect(() => { load(); }, []);
  const run = async (fn) => { try { setErr(""); await fn(); await load(); } catch (e) { setErr(e.message); } };
  const add = (e) => { e.preventDefault(); run(async () => { await api("/admin/countries/", { method: "POST", body: n }); setN({ name: "", iso_code: "", dial_code: "" }); }); };
  return (
    <div className="card" style={{ margin: "12px 0" }}>
      <h3>Countries (phone codes)</h3>
      <form className="row" onSubmit={add}>
        <input placeholder="Name" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} required />
        <input placeholder="ISO (IN)" maxLength={3} value={n.iso_code} onChange={(e) => setN({ ...n, iso_code: e.target.value })} required />
        <input placeholder="Code (91)" value={n.dial_code} onChange={(e) => setN({ ...n, dial_code: e.target.value })} required />
        <button className="primary">Add</button>
      </form>
      {err && <p className="err">{err}</p>}
      <table className="tbl"><tbody>{list.map((c) => (
        <tr key={c.id}><td>{c.name}</td><td>{c.iso_code}</td><td>+{c.dial_code}</td>
          <td><label className="sw"><input type="checkbox" checked={c.is_active} style={{ width: "auto" }}
            onChange={() => run(() => api(`/admin/countries/${c.id}/`, { method: "PATCH", body: { is_active: !c.is_active } }))} /> {c.is_active ? "Active" : "Hidden"}</label></td>
          <td><button className="danger" onClick={() => confirm("Delete?") && run(() => api(`/admin/countries/${c.id}/`, { method: "DELETE" }))}>✕</button></td></tr>))}
      </tbody></table>
    </div>
  );
}

function LogFilters({ filters, setFilters, triggers, onRefresh }) {
  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  return (
    <div className="row" style={{ margin: "8px 0" }}>
      <select value={filters.trigger} onChange={set("trigger")}>
        <option value="">All triggers</option>
        {triggers.map((t) => <option key={t.id} value={t.key}>{t.name}</option>)}
      </select>
      <select value={filters.channel} onChange={set("channel")}>
        <option value="">All channels</option><option value="whatsapp">WhatsApp</option>
        <option value="email">Email</option><option value="push">Web Push</option>
      </select>
      <select value={filters.success} onChange={set("success")}>
        <option value="">All results</option><option value="true">Sent</option><option value="false">Failed</option>
      </select>
      <button onClick={onRefresh}>⟳ Refresh</button>
    </div>
  );
}
