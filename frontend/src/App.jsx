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

  // Poll system stats globally
  useEffect(() => {
    let interval;
    if (isSimulating) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get("http://127.0.0.1:8090/system-stats");
          if (response.data?.metrics) {
            setMetrics(response.data.metrics);
            
            // Append new logs
            if (response.data.metrics.recent_logs?.length > 0) {
              setTerminalLogs(prev => {
                const newLogs = response.data.metrics.recent_logs.map(log => ({ msg: log }));
                const combined = [...prev, ...newLogs];
                // Keep only last 100 logs
                return combined.slice(-100);
              });
            }
          }
        } catch (e) {
          console.warn("Poll missed", e);
        }
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isSimulating]);

  const handleRunSimulation = async () => {
    setIsSimulating(true);
    setTerminalLogs([{ msg: "> INITIATING MPI SUBROUTINES..." }]);
    try {
      await axios.get(`http://127.0.0.1:8090/run-simulation?deliveries=${deliveriesCount}`);
      setTerminalLogs(prev => [...prev, { msg: "> SYSTEM LIVE. POLLING RULE ENGINE..." }]);
    } catch (e) {
      setTerminalLogs(prev => [...prev, { msg: "> ERR: SYS_CORE_OFFLINE" }]);
      setIsSimulating(false);
    }
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
