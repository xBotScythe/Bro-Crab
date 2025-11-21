const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export async function getFinds(signal) {
  const options = {};
  if (signal) options.signal = signal;
  const response = await fetch(`${API_BASE}/api/finds`, options);
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json();
}

export async function getFlavors(signal) {
  const options = {};
  if (signal) options.signal = signal;
  const response = await fetch(`${API_BASE}/api/flavors`, options);
  if (!response.ok) {
    throw new Error('Failed to load flavors');
  }
  return response.json();
}

export async function submitFind(payload) {
  const formData = new FormData();
  formData.append('flavor', payload.flavor);
  formData.append('size', payload.size);
  formData.append('locationName', payload.locationName);
  formData.append('address', payload.address);
  if (payload.imageUrl) {
    formData.append('imageUrl', payload.imageUrl);
  }
  if (payload.imageFile) {
    formData.append('image_file', payload.imageFile);
  }

  const response = await fetch(`${API_BASE}/api/finds`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data?.detail || `status ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}
