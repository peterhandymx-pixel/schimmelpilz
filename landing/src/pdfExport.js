import { API_BASE } from './useCaseStorage.js';

export async function pdfRequest(path, payload) {
  const response = await fetch(`${API_BASE}/api${path}`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Schimmelpilz-Request': '1' }, body: JSON.stringify(payload) });
  if (!response.ok) {
    const error = new Error('PDF request failed');
    error.status = response.status;
    throw error;
  }
  return response.blob();
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}
