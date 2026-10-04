import { useEffect, useState } from "react";
import { API_BASE } from "./useCaseStorage.js";

export async function authRequest(path, payload) {
  const response = await fetch(`${API_BASE}/api/auth/${path}`, {
    method: payload ? "POST" : "GET", credentials: "include",
    headers: payload ? { "Content-Type": "application/json", "X-Schimmelpilz-Request": "1" } : {},
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  });
  if (!response.ok) { const error = new Error("Authentication failed"); error.status = response.status; throw error; }
  return response.status === 204 ? null : response.json();
}

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("schimmelpilz-session-expired", expired);
    return () => window.removeEventListener("schimmelpilz-session-expired", expired);
  }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(false);
    authRequest("me").then(result => { if (active) setUser(result); }).catch(error => { if (active && error.status !== 401) setError(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [attempt]);
  const logout = async () => { await authRequest("logout", {}); setUser(null); };
  return { user, setUser, loading, error, logout, retry: () => setAttempt(value => value + 1) };
}
