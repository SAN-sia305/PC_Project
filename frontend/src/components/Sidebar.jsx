import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API = 'http://127.0.0.1:8000';

const Sidebar = ({ activeTab, setActiveTab, metrics, isSimulating, onEngageEngine }) => {
  const [vehicles, setVehicles] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);

  // Poll fleet status for the sidebar panel
  useEffect(() => {
    const fetchFleet = async () => {
      try {
        const res = await axios.get(`${API}/vehicles`);
        if (res.data?.vehicles) setVehicles(res.data.vehicles);
      } catch { /* engine may be offline */ }
    };
    fetchFleet();
    const interval = setInterval(fetchFleet, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setPendingCount(metrics?.pending_orders ?? 0);
  }, [metrics]);

  const activeCount = vehicles.filter(v => !v.capacity_available).length;
  const totalLoad   = vehicles.reduce((acc, v) => acc + (v.current_volume || 0), 0);
  const maxLoad     = vehicles.reduce((acc, v) => acc + (v.max_volume || 100), 0);
  const loadPct     = maxLoad > 0 ? Math.round((totalLoad / maxLoad) * 100) : 0;

  return (
    <aside className="sidebar brutal-border">
      <div className="logo">
        <h2>DIFM<span className="highlight">//DOS</span></h2>
        <div className="sys-info">SYS.VER: 4.1.0_MPI_REACT</div>
      </div>

      <nav className="nav-menu">
        <button
          className={`nav-item ${activeTab === 'DASHBOARD' ? 'active' : ''}`}
          onClick={() => setActiveTab('DASHBOARD')}
        >
          [01] DASHBOARD
        </button>
        <button
          className={`nav-item ${activeTab === 'NETWORK' ? 'active' : ''}`}
          onClick={() => setActiveTab('NETWORK')}
        >
          [02] NETWORK_GRAPH
        </button>
        <button
          className={`nav-item ${activeTab === 'ORDERS' ? 'active' : ''}`}
          onClick={() => setActiveTab('ORDERS')}
        >
          [03] DISPATCH_ORDERS
          {pendingCount > 0 && (
            <span className="nav-badge">{pendingCount}</span>
          )}
        </button>
      </nav>

      {/* ── System Status Hub ── */}
      <div className="controls-panel brutal-box">
        <div className="decor-line"></div>
        <h3>FLEET_STATUS_HUB</h3>

        <div className="hub-row">
          <span className="hub-label">ENGINE</span>
          <span className={`hub-val ${isSimulating ? 'val-online' : 'val-idle'}`}>
            {isSimulating ? '● ONLINE' : '○ STANDBY'}
          </span>
        </div>

        <div className="hub-row">
          <span className="hub-label">VEHICLES ACTIVE</span>
          <span className="hub-val">{activeCount} / {vehicles.length || 5}</span>
        </div>

        <div className="hub-row">
          <span className="hub-label">PENDING ORDERS</span>
          <span className="hub-val" style={{ color: pendingCount > 0 ? '#ff8c00' : 'inherit' }}>
            {pendingCount}
          </span>
        </div>

        <div className="hub-row">
          <span className="hub-label">FLEET LOAD</span>
          <span className="hub-val">{loadPct}%</span>
        </div>

        {/* Load bar */}
        <div className="load-bar-track">
          <div
            className="load-bar-fill"
            style={{
              width: `${loadPct}%`,
              background: loadPct > 80 ? 'var(--neon-red)' : 'var(--neon-green)'
            }}
          />
        </div>

        <button
          onClick={() => setActiveTab('ORDERS')}
          className="primary-btn glitch-hover"
          style={{ letterSpacing: '1px', fontSize: '12px', marginTop: '14px' }}
        >
          [+] NEW DISPATCH ORDER
        </button>

        {onEngageEngine && (
          <button
            onClick={onEngageEngine}
            className="cancel-btn"
            style={{ marginTop: '8px', fontSize: '11px' }}
          >
            {isSimulating ? 'ENGINE RUNNING...' : '▶ ENGAGE RULE ENGINE'}
          </button>
        )}

        <div className="status-container" style={{ marginTop: '12px' }}>
          {isSimulating && <div className="loader"></div>}
          <div className="status-msg" style={{ display: 'inline-block', color: isSimulating ? 'var(--neon-green)' : '#444' }}>
            {isSimulating ? '> SYSTEM LIVE...' : '> _IDLE'}
          </div>
        </div>
      </div>

      <div className="sidebar-decor-bottom" style={{ marginTop: '20px', fontSize: '10px', display: 'flex', justifyContent: 'space-between' }}>
        <p>UPLINK_SECURE</p>
        <div className="blink-dot" style={{
          width: '8px', height: '8px',
          backgroundColor: isSimulating ? 'var(--neon-green)' : '#333',
          borderRadius: '50%',
          animation: isSimulating ? 'pulse 1.5s infinite' : 'none'
        }}></div>
      </div>
    </aside>
  );
};

export default Sidebar;
