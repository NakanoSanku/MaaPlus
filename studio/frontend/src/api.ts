const incoming = new URLSearchParams(location.hash.slice(1)).get('token');
if (incoming) {
  sessionStorage.setItem('studio-token', incoming);
  history.replaceState(null, '', location.pathname);
}
const token = incoming || sessionStorage.getItem('studio-token') || '';

export async function api<T = any>(path: string, body?: unknown, raw?: Blob): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body !== undefined || raw ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: raw || (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail); } catch { /* HTTP error without JSON */ }
    throw new Error(message);
  }
  if (response.headers.get('Content-Type')?.startsWith('image/')) return URL.createObjectURL(await response.blob()) as T;
  return response.json();
}
