import { useState } from 'react';

const initialForm = {
  flavor: '',
  size: '',
  locationName: '',
  address: '',
  imageUrl: '',
};

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

export function FindForm({ flavors, onSubmit }) {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [fileKey, setFileKey] = useState(0);
  const isBusy = status === 'submitting';

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      setImageFile(null);
      return;
    }
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('only png, jpg, webp, or gif files are allowed');
      event.target.value = '';
      setImageFile(null);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setError('image must be under 8MB');
      event.target.value = '';
      setImageFile(null);
      return;
    }
    setError('');
    setImageFile(file);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.flavor || !form.size || !form.locationName || !form.address) {
      setError('please fill all required fields');
      return;
    }
    setStatus('submitting');
    setError('');
    try {
      await onSubmit({
        flavor: form.flavor,
        size: form.size.trim(),
        locationName: form.locationName.trim(),
        address: form.address.trim(),
        imageUrl: form.imageUrl.trim() || undefined,
        imageFile,
      });
      setForm(initialForm);
      setImageFile(null);
      setFileKey((prev) => prev + 1);
      setStatus('success');
      setTimeout(() => setStatus('idle'), 2000);
    } catch (err) {
      setError(err.message || 'failed to submit find');
      setStatus('error');
    }
  };

  return (
    <form className="find-form" onSubmit={handleSubmit}>
      <label>
        flavor
        <select name="flavor" value={form.flavor} onChange={handleChange} disabled={isBusy || !flavors.length}>
          <option value="">choose a flavor</option>
          {flavors.map((flavor) => (
            <option key={flavor} value={flavor}>
              {flavor}
            </option>
          ))}
        </select>
      </label>
      <label>
        size
        <input
          name="size"
          value={form.size}
          onChange={handleChange}
          placeholder="20oz, 12pk, etc."
          disabled={isBusy}
        />
      </label>
      <label>
        store or venue
        <input
          name="locationName"
          value={form.locationName}
          onChange={handleChange}
          placeholder="Dew Stop Market"
          disabled={isBusy}
        />
      </label>
      <label>
        address
        <input
          name="address"
          value={form.address}
          onChange={handleChange}
          placeholder="123 Main St, City State, Zip"
          disabled={isBusy}
        />
      </label>
      <label>
        image url (optional)
        <input
          name="imageUrl"
          value={form.imageUrl}
          onChange={handleChange}
          placeholder="https://..."
          disabled={isBusy}
        />
      </label>
      <label>
        or upload an image
        <input
          key={fileKey}
          type="file"
          accept=".png,.jpg,.jpeg,.webp,.gif"
          onChange={handleFileChange}
          disabled={isBusy}
        />
        <span className="form-hint">png, jpg, webp, or gif — max 8MB</span>
      </label>
      {error && <p className="form-error">{error}</p>}
      <button type="submit" disabled={isBusy}>
        {isBusy ? 'submitting…' : 'log find'}
      </button>
      {status === 'success' && <p className="form-success">submitted! thanks for keeping the map fresh.</p>}
    </form>
  );
}
