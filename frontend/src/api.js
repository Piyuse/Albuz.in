const TOKEN_KEY = 'stills_tokens';
// The backend origin is public configuration. Secrets stay on the Django host.
const API_ROOT = `${(import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')}/api`;

export function getTokens() {
  try { return JSON.parse(sessionStorage.getItem(TOKEN_KEY) || 'null'); }
  catch { return null; }
}

export function saveTokens(tokens) { sessionStorage.setItem(TOKEN_KEY, JSON.stringify(tokens)); }
export function clearTokens() { sessionStorage.removeItem(TOKEN_KEY); }

function message(data) {
  if (typeof data?.detail === 'string') return data.detail;
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' · ');
  }
  return 'The request could not be completed.';
}

export async function api(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  const tokens = getTokens();
  if (tokens?.access) headers.set('Authorization', `Bearer ${tokens.access}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, { ...options, headers, credentials: 'same-origin' });
  } catch {
    throw new Error('Cannot reach the server. Check the API connection and try again.');
  }
  if (response.status === 401 && retry && tokens?.refresh) {
    const refreshed = await fetch(`${API_ROOT}/auth/refresh/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: tokens.refresh }),
    });
    if (refreshed.ok) {
      const updated = await refreshed.json();
      saveTokens({ refresh: updated.refresh || tokens.refresh, access: updated.access });
      return api(path, options, false);
    }
    clearTokens();
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(message(data));
  return data;
}

export async function allPhotos(albumId) {
  const photos = [];
  let path = `/albums/${albumId}/photos/`;
  while (path) {
    const page = await api(path);
    photos.push(...page.results);
    if (!page.next) break;
    const next = new URL(page.next, location.origin);
    path = `${next.pathname.replace(/^\/api/, '')}${next.search}`;
  }
  return photos;
}
