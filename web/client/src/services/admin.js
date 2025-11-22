const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

// thin fetch helpers so admin ui can hit protected endpoints

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = data?.detail || `request failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}

export function adminLogin({ username, password }) {
  return request('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export function adminLogout() {
  return request('/api/admin/logout', { method: 'POST' });
}

export function adminProfile() {
  return request('/api/admin/me');
}

export function adminFinds(limit = 25) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/api/admin/finds?${params.toString()}`);
}

export function adminDeleteFind(findId) {
  return request(`/api/admin/finds/${encodeURIComponent(findId)}`);
}
