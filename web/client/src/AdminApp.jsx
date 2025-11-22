import { useEffect, useMemo, useState } from 'react';
import './App.css';
import './AdminApp.css';
import { adminFinds, adminLogin, adminLogout, adminProfile, adminDeleteFind } from './services/admin';

// simple admin dashboard and login flow sitting on top of the same styles

function LoginForm({ onSubmit, error }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!username || !password) return;
    setPending(true);
    try {
      await onSubmit({ username, password });
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="admin-card">
      <h1>Admin Portal</h1>
      <p className="muted">Sign in to moderate community finds.</p>
      {error && <p className="error-text">{error}</p>}
      <form onSubmit={handleSubmit} className="admin-form">
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button type="submit" disabled={pending}>
          {pending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}

function FindsTable({ finds, onDelete, deletingId }) {
  if (!finds.length) {
    return <p className="muted">No submissions yet.</p>;
  }
  return (
    <div className="table-scroll">
      <table className="admin-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Flavor</th>
            <th>Size</th>
            <th>Location</th>
            <th>Address</th>
            <th>Submitted</th>
            <th>By</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {finds.map((find) => (
            <tr key={find.id}>
              <td>{find.id}</td>
              <td>{find.flavor}</td>
              <td>{find.size}</td>
              <td>{find.locationName}</td>
              <td>{find.address}</td>
              <td>{new Date(find.createdAt).toLocaleString()}</td>
              <td>{find.submittedBy || 'unknown'}</td>
              <td>
                <button
                  type="button"
                  className="danger"
                  onClick={() => onDelete(find.id)}
                  disabled={deletingId === find.id}
                >
                  {deletingId === find.id ? 'Removing…' : 'Remove'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminApp() {
  const [stage, setStage] = useState('loading');
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  const [finds, setFinds] = useState([]);
  const [limit, setLimit] = useState(25);
  const [loadingFinds, setLoadingFinds] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const profile = await adminProfile();
        setUser(profile);
        setStage('authed');
        await refreshFinds(limit);
      } catch {
        setStage('guest');
      }
    };
    bootstrap();
  }, []);

  const refreshFinds = async (count = limit) => {
    setLoadingFinds(true);
    try {
      const rows = await adminFinds(count);
      setFinds(rows);
      setLimit(count);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingFinds(false);
    }
  };

  const handleLogin = async (creds) => {
    try {
      setError('');
      await adminLogin(creds);
      const profile = await adminProfile();
      setUser(profile);
      setStage('authed');
      await refreshFinds();
    } catch (err) {
      setError(err.message || 'Failed to sign in');
    }
  };

  const handleLogout = async () => {
    await adminLogout();
    setUser(null);
    setFinds([]);
    setStage('guest');
  };

  const stats = useMemo(() => {
    const total = finds.length;
    const byFlavor = finds.reduce((acc, find) => {
      acc[find.flavor] = (acc[find.flavor] || 0) + 1;
      return acc;
    }, {});
    const topFlavor = Object.entries(byFlavor).sort((a, b) => b[1] - a[1])[0];
    return { total, topFlavor };
  }, [finds]);

  const handleDelete = async (id) => {
    setDeletingId(id);
    try {
      await adminDeleteFind(id);
      setFinds((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError(err.message || 'Failed to remove find');
    } finally {
      setDeletingId(null);
    }
  };

  if (stage === 'loading') {
    return (
      <div className="admin-shell">
        <p className="muted">Loading…</p>
      </div>
    );
  }

  if (stage === 'guest') {
    return (
      <div className="admin-shell">
        <LoginForm onSubmit={handleLogin} error={error} />
      </div>
    );
  }

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <div>
          <h1>Dew Finder Admin</h1>
          <p className="muted">Review new submissions and keep the feed clean.</p>
        </div>
        <div className="admin-header__actions">
          <span>{user?.username}</span>
          <button type="button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="admin-content">
        <div className="stat-grid">
          <article className="stat-card">
            <p className="stat-label">Loaded Finds</p>
            <p className="stat-value">{stats.total}</p>
          </article>
          <article className="stat-card">
            <p className="stat-label">Top Flavor</p>
            <p className="stat-value">{stats.topFlavor ? `${stats.topFlavor[0]} (${stats.topFlavor[1]})` : '—'}</p>
          </article>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <h2>Recent submissions</h2>
            <div className="panel-actions">
              <label>
                Show
                <select value={limit} onChange={(event) => refreshFinds(Number(event.target.value))} disabled={loadingFinds}>
                  {[25, 50, 100].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={() => refreshFinds(limit)} disabled={loadingFinds}>
                {loadingFinds ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
          </div>
          <FindsTable finds={finds} onDelete={handleDelete} deletingId={deletingId} />
        </div>
      </section>
    </div>
  );
}
