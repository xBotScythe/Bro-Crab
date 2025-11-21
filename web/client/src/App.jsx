import { useEffect, useMemo, useState } from 'react';
import './App.css';
import { DewMap } from './components/DewMap';
import { getFinds } from './services/finds';

function formatTimestamp(timestamp, timeZone) {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      timeZone: timeZone || 'UTC',
    });
    return formatter.format(new Date(timestamp));
  } catch {
    return timestamp;
  }
}

function App() {
  const [finds, setFinds] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // hydrate once so the map + cards have data ready
  useEffect(() => {
    const controller = new AbortController();
    getFinds(controller.signal)
      .then((data) => {
        setFinds(data);
        setStatus('idle');
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setError(err.message || 'Unable to load map data.');
        setStatus('error');
      });
    return () => controller.abort();
  }, []);

  // mirror leaflet filtering without hitting the api again
  const filteredFinds = useMemo(() => {
    if (!searchQuery.trim()) return finds;
    const q = searchQuery.trim().toLowerCase();
    return finds.filter((find) => {
      return (
        find.flavor.toLowerCase().includes(q) ||
        find.locationName.toLowerCase().includes(q) ||
        find.address.toLowerCase().includes(q)
      );
    });
  }, [finds, searchQuery]);

  const flavorCount = useMemo(() => new Set(filteredFinds.map((find) => find.flavor)).size, [filteredFinds]);
  const latestFinds = useMemo(() => {
    return [...filteredFinds]
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
      .slice(0, 5);
  }, [filteredFinds]);
  const topFlavors = useMemo(() => {
    const counts = filteredFinds.reduce((acc, find) => {
      acc[find.flavor] = (acc[find.flavor] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([flavor, count]) => ({ flavor, count }));
  }, [finds]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>DEW Community Locator</h1>
          <p className="lede">
            See every community-reported flavor drop in real time. Log your own finds with the{' '}
            <span>/dewfind</span> command in the Dew Drinker Discord. Website finds coming soon!
          </p>
          <div className="search-bar">
            {/* quick client-side filter across flavor + place text */}
            <input
              type="search"
              placeholder="search flavor or location"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>
        </div>
        <a className="primary-link" href="https://discord.com/invite/dew" target="_blank" rel="noreferrer">
          Open Discord
        </a>
      </header>

      {status === 'error' && (
        <div className="error-banner">
          <p>We couldn&apos;t load the map data: {error}</p>
        </div>
      )}

      <main className="content">
        <section className="sidebar">
          <div className="stat-grid">
            <article className="stat-card">
              <p className="stat-label">Total finds</p>
              <p className="stat-value">{filteredFinds.length}</p>
            </article>
            <article className="stat-card">
              <p className="stat-label">Flavors tracked</p>
              <p className="stat-value">{flavorCount}</p>
            </article>
            <article className="stat-card">
              <p className="stat-label">Latest activity</p>
              <p className="stat-value">{latestFinds[0] ? formatTimestamp(latestFinds[0].createdAt, latestFinds[0].timeZone) : '—'}</p>
            </article>
          </div>

          <div className="panel">
            <h2>Recent finds</h2>
            <ol>
              {latestFinds.map((find) => (
                <li key={find.id}>
                  <p className="list-title">
                    {find.flavor} <span>· {find.size}</span>
                  </p>
                  <p className="list-subtitle">{find.locationName}</p>
                  <p className="list-meta">{formatTimestamp(find.createdAt, find.timeZone)}</p>
                </li>
              ))}
              {!latestFinds.length && <p className="muted">No finds logged yet.</p>}
            </ol>
          </div>

          <div className="panel">
            <h2>Top flavors</h2>
            <ul className="flavor-list">
              {topFlavors.map((item) => (
                <li key={item.flavor}>
                  <span>{item.flavor}</span>
                  <span className="badge">{item.count}</span>
                </li>
              ))}
              {!topFlavors.length && <p className="muted">Flavors will appear here once finds roll in.</p>}
            </ul>
          </div>
        </section>

        <section className="map-panel">
          {status === 'loading' && <div className="map-overlay">Loading map…</div>}
          <DewMap finds={filteredFinds} />
        </section>
      </main>
    </div>
  );
}

export default App;
