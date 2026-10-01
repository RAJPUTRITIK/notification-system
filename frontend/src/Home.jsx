import { useState } from "react";
import { api, enablePush } from "./api";

export default function Home({ user, setUser, notify, summary }) {
  const [phone, setPhone] = useState(user.phone || "");
  const [email, setEmail] = useState(user.email || "");

  const saveProfile = async () => {
    setUser(await api("/auth/me/", { method: "PATCH", body: { phone, email } }));
    notify("Profile saved");
  };
  const push = async () => {
    try { await enablePush(); setUser(await api("/auth/me/")); notify("Web Push enabled for this browser ✓"); }
    catch (e) { notify("Push error: " + e.message); }
  };
  const fire = async (key) => {
    try { const r = await api(`/events/${key}/`, { method: "POST", body: { order_id: "ORD-" + Date.now() } }); notify(`${key} trigger → ` + summary(r.notifications)); }
    catch (e) { notify("Error: " + e.message); }
  };

  return (
    <div className="grid">
      <section className="card">
        <h3>Welcome, {user.username}</h3>
        <p>Set where you receive notifications:</p>
        <input placeholder="WhatsApp number (must be a Meta test recipient)" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <button className="primary" onClick={saveProfile}>Save profile</button>
        <button onClick={push}>{user.push_subscribed ? "Re-subscribe Web Push" : "Enable Web Push"}</button>
        <p className="muted">Push: {user.push_subscribed ? "subscribed ✓" : "not subscribed"}</p>
      </section>
      <section className="card">
        <h3>Fire triggers on the website</h3>
        <p className="muted">Login & Logout fire automatically. Try the others:</p>
        <button onClick={() => fire("order_placed")}>🛒 Place order</button>
        <button onClick={() => fire("password_reset")}>🔑 Request password reset</button>
        <button onClick={() => fire("not_logged_in_1_day")}>⏰ Simulate “not logged in 1 day”</button>
        <button onClick={() => fire("not_logged_in_1_week")}>📅 Simulate “not logged in 1 week”</button>
        <p className="muted">Inactivity triggers also run for real via <code>python manage.py fire_inactive</code> (daily cron).</p>
      </section>
    </div>
  );
}
