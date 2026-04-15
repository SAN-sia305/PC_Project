import { useState, useEffect } from 'react';
import axios from 'axios';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import NetworkGraph from './components/NetworkGraph';
import Orders from './components/Orders';

function App() {
  const [activeTab, setActiveTab] = useState('DASHBOARD');
  const [metrics, setMetrics] = useState({
    pending_orders: 0,
    active_vehicles: 0,
    completed_deliveries: 0,
    delayed: 0,
    fuel_used: 0.0,
    parallel_time: 0.0,
    seq_time: 0.0,
    recent_logs: []
  });
  
  const [terminalLogs, setTerminalLogs] = useState([{ msg: "> WAITING_FOR_UPLINK..." }]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [deliveriesCount, setDeliveriesCount] = useState(100);

  // Always poll /engine-state on mount — no isSimulating gate needed
  useEffect(() => {
    const poll = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/engine-state");
        const data = response.data;

        setMetrics({
          pending_orders:       data.pending_orders       ?? 0,
          active_vehicles:      data.active_vehicles      ?? 0,
          completed_deliveries: data.completed_deliveries ?? 0,
          delayed:              data.delayed_tasks        ?? 0,
          fuel_used:            data.total_fuel           ?? 0.0,
          parallel_time:        data.last_parallel_time   ?? 0.0,
          seq_time:             data.last_seq_time        ?? 0.0,
          recent_logs:          data.recent_logs          ?? [],
        });

        // Auto-mark engine as online on first successful response
        setIsSimulating(true);

        // Append new rule engine logs to terminal stream
        if (data.recent_logs?.length > 0) {
          setTerminalLogs(prev => {
            const newLogs = data.recent_logs.map(log => ({ msg: log }));
            const combined = [...prev, ...newLogs];
            return combined.slice(-200);
          });
        }
      } catch (e) {
        // Engine offline — silently retry
      }
    };

    poll(); // immediate first call
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []); // runs once on mount

  const handleRunSimulation = () => {
    setTerminalLogs(prev => [...prev, { msg: "> ENGINE STATUS CONFIRMED. POLLING ACTIVE." }]);
  };

  return (
    <>
      <div className="crt-overlay"></div>
      <div className="app-container">
        <Sidebar 
          activeTab={activeTab} 
          setActiveTab={setActiveTab}
          metrics={metrics}
          onEngageEngine={handleRunSimulation}
          isSimulating={isSimulating}
        />
        
        <main className="main-content">
          <header className="brutal-header">
            <div className="header-top">
              <h1>FLEET_OPTIMIZATION_MODULE</h1>
              <div className="status-badge">{isSimulating ? "ONLINE" : "STANDBY"}</div>
            </div>
            <p>{"> DISTRIBUTED INTELLIGENT FLEET MANAGEMENT & DELIVERY OPTIMIZATION SYSTEM"}</p>
          </header>

          <div className="views-container">
            {activeTab === 'DASHBOARD' && <Dashboard metrics={metrics} isSimulating={isSimulating} />}
            {activeTab === 'NETWORK' && (
              <NetworkGraph 
                isSimulating={isSimulating} 
                terminalLogs={terminalLogs} 
              />
            )}
            {activeTab === 'ORDERS' && <Orders isSimulating={isSimulating} />}
          </div>
        </main>
      </div>
    </>
  );
}

export default App;
