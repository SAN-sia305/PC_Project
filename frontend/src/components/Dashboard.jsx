import React, { useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const Dashboard = ({ metrics, isSimulating }) => {
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: [
      { label: 'Sequential (Est)', data: [], borderColor: '#ff003c', tension: 0.1 },
      { label: 'Parallel (MPI)', data: [], borderColor: '#00ff41', tension: 0.1 }
    ]
  });

  useEffect(() => {
    if (isSimulating && (metrics.seq_time > 0 || metrics.parallel_time > 0)) {
      const now = new Date().toLocaleTimeString();
      setChartData(prev => {
        const newLabels = [...prev.labels, now].slice(-20);
        const newSeq = [...prev.datasets[0].data, metrics.seq_time.toFixed(4)].slice(-20);
        const newPar = [...prev.datasets[1].data, metrics.parallel_time.toFixed(4)].slice(-20);
        
        return {
          labels: newLabels,
          datasets: [
            { ...prev.datasets[0], data: newSeq },
            { ...prev.datasets[1], data: newPar }
          ]
        };
      });
    }
  }, [metrics, isSimulating]);

  let speedup = 1.0;
  if (metrics.parallel_time > 0) {
    speedup = metrics.seq_time / metrics.parallel_time;
  }

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      y: { beginAtZero: true, grid: { color: '#333' }, title: { display: true, text: 'Execution Time (s)' } },
      x: { grid: { display: false } }
    }
  };

  return (
    <>
      <div className="stats-grid">
        <div className="stat-card brutal-box">
          <div className="stat-label">MPI_SPEEDUP</div>
          <span className="stat-value flicker">{speedup.toFixed(2)}x</span>
        </div>
        <div className="stat-card brutal-box">
          <div className="stat-label">PARALLEL_TIME</div>
          <span className="stat-value">{metrics.parallel_time.toFixed(4)}s</span>
        </div>
        <div className="stat-card brutal-box">
          <div className="stat-label">DELIVERIES_COMPLETED</div>
          <span className="stat-value">{metrics.completed_deliveries}</span>
        </div>
        <div className="stat-card brutal-box alert-card">
          <div className="stat-label">DELAYED_TASKS</div>
          <span className="stat-value alert">{metrics.delayed}</span>
        </div>
      </div>

      <div className="chart-container" style={{ display: 'flex', gap: '20px', minHeight: '300px', flex: 1 }}>
        <div className="chart-card brutal-box" style={{ flex: 3 }}>
          <h3>PERFORMANCE_MATRIX <span style={{ fontSize: '12px', color: '#888' }}>(SEQ vs MPI)</span></h3>
          <div style={{ position: 'relative', height: '250px', width: '100%' }}>
             <Line data={chartData} options={chartOptions} />
          </div>
        </div>

        <div className="chart-card brutal-box" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <h3>FUEL_CONSUMPTION_MODEL</h3>
          <div style={{ margin: '20px 0', fontSize: '32px', fontFamily: 'var(--font-display)', color: 'var(--neon-green)' }}>
            {metrics.fuel_used.toFixed(0)} <span style={{ fontSize: '14px', color: '#fff' }}>Liters</span>
          </div>
          <p style={{ fontSize: '10px', color: '#888' }}>{">"} computed via shortest-path base heuristic.</p>
        </div>
      </div>
    </>
  );
};

export default Dashboard;
