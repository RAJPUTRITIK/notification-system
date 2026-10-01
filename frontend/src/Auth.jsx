import { useState } from "react";
import { api } from "./api";

export default function Auth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", password: "", email: "", phone: "", first_name: "" });
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try {
      const r = await api(`/auth/${mode}/`, { method: "POST", body: f });
      localStorage.setItem("token", r.token);
      onAuth(r.user, r.notifications);
    } catch (x) { setErr(x.message); }
  };

  return (
    <div className="card auth">
      <h2>{mode === "login" ? "Log in" : "Create account"}</h2>
      <form onSubmit={submit}>
        <input placeholder="Username" value={f.username} onChange={set("username")} required />
        <input placeholder="Password" type="password" value={f.password} onChange={set("password")} required />
        {mode === "register" && <>
          <input placeholder="First name" value={f.first_name} onChange={set("first_name")} />
          <input placeholder="Email" type="email" value={f.email} onChange={set("email")} />
          <input placeholder="WhatsApp number e.g. 919999999999" value={f.phone} onChange={set("phone")} />
        </>}
        {err && <p className="err">{err}</p>}
        <button className="primary">{mode === "login" ? "Log in" : "Register"}</button>
      </form>
      <p className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "No account? Register" : "Have an account? Log in"}
      </p>
    </div>
  );
}
