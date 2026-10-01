const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export async function api(path, { method = "GET", body } = {}) {
  const token = localStorage.getItem("token");
  console.log(token,'tokennn')
  const res = await fetch(BASE + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.error || data.detail || data.detail || JSON.stringify(data));
  return data;
}

// ---- OneSignal Web Push ----
let loaded = false;
export function enablePush() {
  const appId = import.meta.env.VITE_ONESIGNAL_APP_ID;
  return new Promise((resolve, reject) => {
    if (!appId) return reject(new Error("Set VITE_ONESIGNAL_APP_ID"));
    window.OneSignalDeferred = window.OneSignalDeferred || [];
    window.OneSignalDeferred.push(async (OS) => {
      try {
        await OS.init({ appId, allowLocalhostAsSecureOrigin: true });
        await OS.Notifications.requestPermission();
        await OS.User.PushSubscription.optIn();
        let id = OS.User.PushSubscription.id;
        for (let i = 0; i < 20 && !id; i++) {
          await new Promise((r) => setTimeout(r, 500));
          id = OS.User.PushSubscription.id;
        }
        if (!id) throw new Error("No subscription id (was permission allowed?)");
        await api("/push/subscribe/", { method: "POST", body: { subscription_id: id } });
        resolve(id);
      } catch (e) { reject(e); }
    });
    if (!loaded) {
      loaded = true;
      const s = document.createElement("script");
      s.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js";
      s.defer = true;
      document.head.appendChild(s);
    }
  });
}