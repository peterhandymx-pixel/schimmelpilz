import { useCallback, useEffect, useState } from "react";
import { documentTemplate } from "./draftTemplates.js";

export const API_BASE = import.meta.env.VITE_API_BASE || "";
const SELECTED_CASE_KEY = "schimmelpilz.selectedCase";

export function readPreference(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function writePreference(key, value) {
  try { localStorage.setItem(key, value); } catch { /* Server data works without browser storage. */ }
}

export async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, { ...options, credentials: "include", headers: { ...options.headers, "X-Schimmelpilz-Request": "1" } });
  if (!response.ok) {
    const error = new Error(`Request failed: ${response.status}`);
    error.status = response.status;
    if (response.status === 401) window.dispatchEvent(new Event("schimmelpilz-session-expired"));
    throw error;
  }
  return response.json();
}

const jsonOptions = (method, body) => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export function useCaseStorage(enabled = true) {
  const [cases, setCases] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const selectedCase = cases.find(item => item.id === selectedId) || null;

  const selectCase = (id) => {
    setSelectedId(id);
    writePreference(SELECTED_CASE_KEY, id || "demo");
  };

  const reload = useCallback(async (signal) => {
    setLoading(true);
    setLoadError(false);
    try {
      const savedCases = await request("/cases", { signal });
      if (signal?.aborted) return;
      setCases(savedCases);
      const remembered = readPreference(SELECTED_CASE_KEY);
      setSelectedId(remembered === "demo" ? "" : savedCases.find(item => item.id === remembered)?.id || savedCases[0]?.id || "");
    } catch (error) {
      if (error.name !== "AbortError") setLoadError(true);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) { setCases([]); setSelectedId(""); setLoading(false); setLoadError(false); return; }
    const controller = new AbortController();
    reload(controller.signal);
    return () => controller.abort();
  }, [reload, enabled]);

  const createCase = async (payload) => {
    const created = await request("/cases", jsonOptions("POST", payload));
    setCases(current => [created, ...current]);
    selectCase(created.id);
    return created;
  };

  const replaceCase = item => setCases(current => current.map(saved => saved.id === item.id ? item : saved));
  const updateCase = async (caseId, payload) => {
    const { title, description, language, details } = payload;
    const updated = await request(`/cases/${caseId}`, jsonOptions("PUT", { title, description, language, details }));
    replaceCase(updated);
    selectCase(updated.id);
    return updated;
  };
  const saveTask = async (caseId, payload, taskId) => {
    const updated = await request(`/cases/${caseId}/tasks${taskId ? `/${taskId}` : ""}`, jsonOptions(taskId ? "PUT" : "POST", payload));
    replaceCase(updated);
    return updated;
  };

  const uploadDocuments = async (selected) => {
    if (!selectedId || uploading) return;
    const caseId = selectedId;
    setUploading(true);
    const results = [];
    try {
      for (const file of selected) {
        try {
          const body = new FormData();
          body.append("file", file);
          const document = await request(`/cases/${caseId}/documents`, { method: "POST", body });
          // Keep each successful upload visible even if a later file fails.
          setCases(current => current.map(item => item.id === caseId ? { ...item, documents: [...item.documents, document], activities: [document.activity, ...(item.activities || [])].filter(Boolean) } : item));
          results.push({ name: file.name, ok: true });
        } catch (error) {
          results.push({ name: file.name, ok: false, status: error.status });
        }
      }
      return results;
    } finally {
      setUploading(false);
    }
  };

  const saveDraft = async (payload, draftId) => {
    if (!selectedId || savingDraft) return;
    const caseId = selectedId;
    setSavingDraft(true);
    try {
      const draft = await request(
        `/cases/${caseId}/drafts${draftId ? `/${draftId}` : ""}`,
        jsonOptions(draftId ? "PUT" : "POST", payload),
      );
      setCases(current => current.map(item => item.id === caseId ? { ...item, drafts: [draft, ...item.drafts.filter(saved => saved.id !== draft.id)], activities: [draft.activity, ...(item.activities || [])].filter(Boolean) } : item));
      return draft;
    } finally {
      setSavingDraft(false);
    }
  };

  const applyDraft = draft => setCases(current => current.map(item => item.id === selectedId ? {...item,drafts:item.drafts.map(saved => saved.id === draft.id && (saved.version < draft.version || (saved.version === draft.version && saved.review_revision <= draft.review_revision)) ? draft : saved),activities:[draft.activity,...(item.activities || [])].filter(Boolean)} : item));
  return { cases, selectedCase, selectCase, loading, loadError, reload, createCase, updateCase, saveTask, uploadDocuments, saveDraft, applyDraft, uploading, savingDraft };
}

export function letterTemplate(item, language) {
  return documentTemplate(item, language);
}
