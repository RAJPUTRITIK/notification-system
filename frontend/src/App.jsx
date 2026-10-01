import { useEffect, useState } from "react";
import { api } from "./api";
import Auth from "./Auth.jsx";
import Home from "./Home.jsx";
import Admin from "./Admin.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState("site");
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("token")) return setReady(true);
    api("/auth/me/").then(setUser).catch(() => localStorage.removeItem("token")).finally(() => setReady(true));
  }, []);

  const notify = (msg) => { setToast(msg); setTimeout(() => setToast(""), 6000); };
  const summary = (n = {}) => Object.entries(n).map(([c, r]) => `${c}: ${r.ok ? "sent ✓" : "failed ✗ " + r.detail}`).join(" | ") || "no active templates";

  const logout = async () => {
    try { const r = await api("/auth/logout/", { method: "POST" }); notify("Logout trigger → " + summary(r.notifications)); } catch {}
    localStorage.removeItem("token"); setUser(null); setTab("site");
  };

  if (!ready) return <p style={{ padding: 20 }}>Loading…</p>;
  if (!user) return <Auth onAuth={(u, n) => { setUser(u); if (n) notify("Login trigger → " + summary(n)); }} />;

  return (
    <div>
      <header className="nav">
        <b>🔔 Notification System</b>
        <nav>
          <button className={tab === "site" ? "on" : ""} onClick={() => setTab("site")}>Website</button>
          {user.is_staff && <button className={tab === "admin" ? "on" : ""} onClick={() => setTab("admin")}>Admin – Notification Settings</button>}
        </nav>
        <span>{user.username}{user.is_staff && " (admin)"} <button onClick={logout}>Logout</button></span>
      </header>
      {toast && <div className="toast">{toast}</div>}
      <main>
        {tab === "site" ? <Home user={user} setUser={setUser} notify={notify} summary={summary} /> : <Admin />}
      </main>
    </div>
  );
}
