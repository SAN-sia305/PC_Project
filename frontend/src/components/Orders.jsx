import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const API = 'http://127.0.0.1:8000';
const NOMINATIM = 'https://nominatim.openstreetmap.org/search';

const STATUS_COLOR = {
  COMPLETED: 'var(--neon-green)',
  DELAYED:   'var(--neon-red)',
  ASSIGNED:  '#ff8c00',
  PENDING:   '#888',
  FAILED:    '#ff003c',
};

const ALLOWED_STATUSES = ['ASSIGNED', 'COMPLETED', 'FAILED', 'DELAYED', 'PENDING'];

// Shows live countdown to ETA; blanks out once complete
const EtaCell = ({ dispatchedAt, etaMinutes }) => {
  const [remaining, setRemaining] = React.useState('');
  React.useEffect(() => {
    if (!dispatchedAt || !etaMinutes) { setRemaining('—'); return; }
    const tick = () => {
      const elapsedSec = (Date.now() / 1000) - dispatchedAt;
      const remainSec  = etaMinutes * 60 - elapsedSec;
      if (remainSec <= 0) { setRemaining('ETA PASSED'); return; }
      const m = Math.floor(remainSec / 60);
      const s = Math.floor(remainSec % 60);
      setRemaining(`${m}m ${s}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [dispatchedAt, etaMinutes]);
  return <span style={{ color: remaining === 'ETA PASSED' ? '#555' : '#aaa', fontSize: '11px' }}>{remaining}</span>;
};

const VOLUME_PRESETS = [
  { label: 'PARCEL', value: 10 },
  { label: 'PALLET', value: 40 },
  { label: 'HALF',   value: 60 },
  { label: 'FULL',   value: 100 },
];

/* ─── Geocoding Search Field ─── */
const LocationSearch = ({ label, tag, onSelect }) => {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [selectedName, setSelectedName] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef(null);

  const search = useCallback(async (q) => {
    if (q.length < 3) { setSuggestions([]); return; }
    setIsSearching(true);
    try {
      const res = await axios.get(NOMINATIM, {
        params: { q, format: 'json', limit: 5, countrycodes: 'in' },
        headers: { 'Accept-Language': 'en' }
      });
      setSuggestions(res.data);
    } catch {
      setSuggestions([]);
    }
    setIsSearching(false);
  }, []);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    setSelectedName('');
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  const handleSelect = (item) => {
    const name = item.display_name.split(',').slice(0, 2).join(',');
    setSelectedName(name);
    setQuery(name);
    setSuggestions([]);
    onSelect({ lat: parseFloat(item.lat), lon: parseFloat(item.lon), name });
  };

  return (
    <div className="form-group loc-search-wrap">
      <label>&#62; {label}</label>
      <div className="loc-input-row">
        <input
          className="brutal-input"
          value={query}
          onChange={handleInput}
          placeholder={`e.g. ${tag}`}
          autoComplete="off"
        />
        {isSearching && <span className="loc-spinner">◌</span>}
        {selectedName && !isSearching && <span className="loc-check">✓</span>}
      </div>
      {suggestions.length > 0 && (
        <ul className="loc-suggestions">
          {suggestions.map((s) => (
            <li key={s.place_id} onClick={() => handleSelect(s)} className="loc-suggestion-item">
              <span className="loc-suggestion-name">{s.display_name.split(',').slice(0, 2).join(', ')}</span>
              <span className="loc-suggestion-type">{s.type}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

/* ─── Orders Main Component ─── */
const Orders = ({ isSimulating }) => {
  const [orders, setOrders] = useState([]);
  const [srcCoords, setSrcCoords] = useState(null);
  const [dstCoords, setDstCoords] = useState(null);
  const [srcName, setSrcName]     = useState('');
  const [dstName, setDstName]     = useState('');
  const [volume, setVolume]       = useState(30);
  const [priority, setPriority]   = useState('LOW');

  const [phase, setPhase]               = useState('idle');
  const [quote, setQuote]               = useState(null);
  const [dispatchResult, setDispatchResult] = useState(null);
  const [errorMsg, setErrorMsg]         = useState('');

  /* Poll orders table */
  useEffect(() => {
    let interval;
    const fetchOrders = async () => {
      try {
        const res = await axios.get(`${API}/orders`);
        if (res.data?.orders) setOrders(res.data.orders);
      } catch (err) { console.error('Failed to fetch orders', err); }
    };
    fetchOrders();
    interval = setInterval(fetchOrders, 3000);
    return () => clearInterval(interval);
  }, []);

  const [editingStatus, setEditingStatus] = useState(null); // order_id being edited

  const updateStatus = async (orderId, newStatus) => {
    try {
      await axios.patch(`${API}/api/orders/${orderId}/status`, { status: newStatus });
      // Optimistically update local state immediately
      setOrders(prev => prev.map(o => o.order_id === orderId ? { ...o, status: newStatus } : o));
    } catch (err) {
      console.error('Status update failed', err);
    }
    setEditingStatus(null);
  };

  const canQuote = srcCoords && dstCoords;

  const handleGetQuote = async () => {
    if (!canQuote) return;
    setPhase('loading');
    setQuote(null);
    setErrorMsg('');
    try {
      const payload = {
        src_lat: srcCoords.lat, src_lon: srcCoords.lon,
        dst_lat: dstCoords.lat, dst_lon: dstCoords.lon,
        volume: parseInt(volume, 10),
      };
      const res = await axios.post(`${API}/api/quote-delivery`, payload);
      if (res.data.status === 'success') { setQuote(res.data); setPhase('quoted'); }
      else { setPhase('busy'); setErrorMsg(res.data.message || 'Fleet at capacity.'); }
    } catch (err) {
      setPhase('error');
      setErrorMsg(err?.response?.data?.detail || 'Network error. Is the engine online?');
    }
  };

  const handleConfirmDispatch = async () => {
    if (!quote) return;
    setPhase('dispatching');
    try {
      const payload = {
        src_node: quote.src_node,
        dst_node: quote.dst_node,
        volume: parseInt(volume, 10),
        vehicle_id: quote.vehicle_id,
        eta_minutes: quote.eta_minutes,
        path_cost: quote.path_cost,
        priority,
        src_name: srcName,
        dst_name: dstName,
      };
      const res = await axios.post(`${API}/api/confirm-dispatch`, payload);
      setDispatchResult(res.data);
      setPhase('dispatched');
    } catch (err) {
      setPhase('error');
      setErrorMsg(err?.response?.data?.detail || 'Dispatch failed. Vehicle may have been reassigned.');
    }
  };

  const handleReset = () => {
    setPhase('idle');
    setQuote(null);
    setDispatchResult(null);
    setErrorMsg('');
  };

  const isFormBusy = phase === 'loading' || phase === 'dispatching';

  return (
    <div className="orders-layout">

      {/* ─── LEFT: Quote Form ─── */}
      <div className="quote-panel brutal-box">
        <div className="panel-title">
          <span className="panel-tag">[03]</span> NEW_ORDER_QUOTATION
        </div>
        <p className="panel-sub">Search locations by name. System resolves coordinates automatically.</p>

        {/* Source */}
        <LocationSearch
          label="PICKUP LOCATION"
          tag="Gandhipuram Bus Stand"
          onSelect={(coords) => { setSrcCoords(coords); setSrcName(coords.name || ''); handleReset(); }}
        />

        {/* Destination */}
        <LocationSearch
          label="DELIVERY DESTINATION"
          tag="Peelamedu Airport"
          onSelect={(coords) => { setDstCoords(coords); setDstName(coords.name || ''); handleReset(); }}
        />

        {/* Volume */}
        <div className="form-group">
          <label>&#62; CARGO_VOLUME: <span className="highlight">{volume} units</span></label>
          <div className="preset-row">
            {VOLUME_PRESETS.map((p) => (
              <button
                key={p.label}
                className={`preset-btn ${volume === p.value ? 'active' : ''}`}
                onClick={() => setVolume(p.value)}
              >
                {p.label}<br /><span>{p.value}u</span>
              </button>
            ))}
          </div>
          <input
            type="range" min="1" max="100"
            value={volume}
            onChange={(e) => setVolume(parseInt(e.target.value, 10))}
            className="brutal-slider"
            style={{ marginTop: '10px' }}
          />
        </div>

        {/* Priority */}
        <div className="form-group">
          <label>&#62; SERVICE_LEVEL</label>
          <div className="priority-toggle">
            <button
              className={`priority-btn ${priority === 'LOW' ? 'active-std' : ''}`}
              onClick={() => setPriority('LOW')}
            >STANDARD</button>
            <button
              className={`priority-btn ${priority === 'HIGH' ? 'active-exp' : ''}`}
              onClick={() => setPriority('HIGH')}
            >EXPRESS ⚡</button>
          </div>
        </div>

        {/* CTA */}
        <button
          className="primary-btn glitch-hover"
          onClick={handleGetQuote}
          disabled={isFormBusy || !canQuote}
          style={{ marginTop: '4px' }}
        >
          {phase === 'loading' ? (
            <><span className="loader" style={{ width: '14px', height: '14px' }}></span>&nbsp;COMPUTING OPTIMAL ROUTE...</>
          ) : !canQuote ? '[ SELECT BOTH LOCATIONS FIRST ]' : '[ CALCULATE OPTIMAL ROUTE ]'}
        </button>

        {phase === 'idle' && (
          <div className="idle-hint">
            &#62; Search for pickup &amp; destination above, then calculate your route.
          </div>
        )}

        {/* ─── Quote Result ─── */}
        {phase === 'quoted' && quote && (
          <div className="quote-result quote-success">
            <div className="qr-header">&#62;&#62; OPTIMAL VEHICLE FOUND</div>
            <div className="qr-vehicle">V_{quote.vehicle_id}</div>
            <div className="qr-route-labels">
              <span className="qr-loc src-loc">&#9678; {srcCoords?.name || `Node ${quote.src_node}`}</span>
              <span className="qr-arrow">──▶</span>
              <span className="qr-loc dst-loc">&#9675; {dstCoords?.name || `Node ${quote.dst_node}`}</span>
            </div>
            <div className="qr-stats">
              <div className="qr-stat">
                <span className="qr-stat-label">ETA</span>
                <span className="qr-stat-value">{quote.eta_minutes.toFixed(1)} min</span>
              </div>
              <div className="qr-stat">
                <span className="qr-stat-label">PATH_COST</span>
                <span className="qr-stat-value">{quote.path_cost.toFixed(1)}</span>
              </div>
              <div className="qr-stat">
                <span className="qr-stat-label">CARGO</span>
                <span className="qr-stat-value">{volume}u</span>
              </div>
              <div className="qr-stat">
                <span className="qr-stat-label">LEVEL</span>
                <span className="qr-stat-value" style={{ color: priority === 'HIGH' ? 'var(--neon-red)' : 'inherit' }}>
                  {priority === 'HIGH' ? 'EXPRESS' : 'STD'}
                </span>
              </div>
            </div>
            <div className="qr-actions">
              <button className="primary-btn" onClick={handleConfirmDispatch} disabled={phase === 'dispatching'}>
                {phase === 'dispatching' ? '[ DISPATCHING... ]' : '[ ✓ CONFIRM DISPATCH ]'}
              </button>
              <button className="cancel-btn" onClick={handleReset}>CANCEL</button>
            </div>
          </div>
        )}

        {phase === 'busy' && (
          <div className="quote-result quote-busy">
            <div className="qr-header">&#62;&#62; FLEET SATURATED</div>
            <p>{errorMsg}</p>
            <button className="cancel-btn" style={{ marginTop: '12px' }} onClick={handleReset}>RETRY</button>
          </div>
        )}

        {phase === 'dispatched' && dispatchResult && (
          <div className="quote-result quote-dispatched">
            <div className="qr-header">&#62;&#62; ORDER DISPATCHED</div>
            <p>ORDER_ID: <span className="highlight">#{String(dispatchResult.order_id).slice(-6)}</span></p>
            <p>VEHICLE: <span className="highlight">V_{dispatchResult.vehicle_id}</span></p>
            <p style={{ color: '#555', fontSize: '11px', marginTop: '8px' }}>
              {srcCoords?.name} ──▶ {dstCoords?.name}
            </p>
            <p style={{ color: '#444', fontSize: '11px', marginTop: '4px' }}>
              Route visualization active on NETWORK_GRAPH tab.
            </p>
            <button className="cancel-btn" style={{ marginTop: '12px' }} onClick={handleReset}>[ + NEW ORDER ]</button>
          </div>
        )}

        {phase === 'error' && (
          <div className="quote-result quote-busy">
            <div className="qr-header">&#62;&#62; ERROR</div>
            <p>{errorMsg}</p>
            <button className="cancel-btn" style={{ marginTop: '12px' }} onClick={handleReset}>DISMISS</button>
          </div>
        )}
      </div>

      {/* ─── RIGHT: Orders Table ─── */}
      <div className="chart-card brutal-box orders-table-panel">
        <div className="panel-title">
          <span className="panel-tag">[DB]</span> LIVE_DELIVERY_MATRIX
          <span className="orders-count">{orders.length} RECORDS</span>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, border: '1px solid var(--border-color)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
            <thead style={{ position: 'sticky', top: 0, background: '#111', borderBottom: '1px solid var(--neon-green)' }}>
              <tr>
                <th style={{ padding: '12px 10px' }}>ORDER_ID</th>
                <th style={{ padding: '12px 10px' }}>PICKUP</th>
                <th style={{ padding: '12px 10px' }}>DESTINATION</th>
                <th style={{ padding: '12px 10px' }}>VOL</th>
                <th style={{ padding: '12px 10px' }}>LEVEL</th>
                <th style={{ padding: '12px 10px' }}>DRIVER</th>
                <th style={{ padding: '12px 10px' }}>ETA</th>
                <th style={{ padding: '12px 10px' }}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o, idx) => (
                <tr key={o.order_id || idx} style={{ borderBottom: '1px solid #1a1a1a' }} className="orders-row">
                  <td style={{ padding: '10px', color: '#555', fontSize: '11px' }}>#{String(o.order_id).slice(-6)}</td>
                  <td style={{ padding: '10px', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={o.src_name || o.src}>
                    {o.src_name || `Node ${o.src}`}
                  </td>
                  <td style={{ padding: '10px', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={o.dst_name || o.dst}>
                    {o.dst_name || `Node ${o.dst}`}
                  </td>
                  <td style={{ padding: '10px', color: '#aaa' }}>{o.volume ?? '—'}</td>
                  <td style={{ padding: '10px', color: o.priority === 'HIGH' ? 'var(--neon-red)' : '#666' }}>
                    {o.priority === 'HIGH' ? 'EXPRESS' : 'STD'}
                  </td>
                  <td style={{ padding: '10px', color: 'var(--neon-green)' }}>
                    {o.assigned_vehicle != null ? `V_${o.assigned_vehicle}` : '—'}
                  </td>
                  <td style={{ padding: '10px' }}>
                    <EtaCell dispatchedAt={o.dispatched_at} etaMinutes={o.eta_minutes} />
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    {editingStatus === o.order_id ? (
                      <select
                        autoFocus
                        defaultValue={o.status}
                        onBlur={() => setEditingStatus(null)}
                        onChange={(e) => updateStatus(o.order_id, e.target.value)}
                        style={{
                          background: '#0d0d0d',
                          border: `1px solid ${STATUS_COLOR[o.status] || '#fff'}`,
                          color: STATUS_COLOR[o.status] || '#fff',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '12px',
                          padding: '4px 6px',
                          cursor: 'pointer',
                          outline: 'none',
                          width: '100%',
                        }}
                      >
                        {ALLOWED_STATUSES.map(s => (
                          <option key={s} value={s} style={{ background: '#0d0d0d', color: STATUS_COLOR[s] || '#fff' }}>
                            {s}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span
                        onClick={() => setEditingStatus(o.order_id)}
                        title="Click to change status"
                        style={{
                          color: STATUS_COLOR[o.status] || '#fff',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          borderBottom: '1px dashed ' + (STATUS_COLOR[o.status] || '#555'),
                          paddingBottom: '1px',
                          userSelect: 'none',
                        }}
                      >
                        {o.status}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr>
                  <td colSpan="8" style={{ padding: '30px', textAlign: 'center', color: '#333' }}>
                    AWAITING INPUT — NO RECORDS FOUND
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Orders;
