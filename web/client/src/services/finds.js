const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export async function getFinds(signal) {
  const response = await fetch(`${API_BASE}/api/finds`, { signal });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json();
}
