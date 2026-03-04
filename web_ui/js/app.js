document.addEventListener('DOMContentLoaded', () => {
    // References
    const btnRun = document.getElementById('btn-run');
    const inputDeliveries = document.getElementById('input-deliveries');
    const labelDeliveries = document.getElementById('label-deliveries');
    
    // UI Panels
    const statsBoard = document.getElementById('stats-dashboard');
    const chartSection = document.getElementById('chart-section');
    
    const loader = document.getElementById('loader');
    const statusText = document.getElementById('status-text');

    // Stats Vals
    const vSpeedup = document.getElementById('val-speedup');
    const vParallel = document.getElementById('val-parallel');
    const vEfficiency = document.getElementById('val-efficiency');
    const vDelayed = document.getElementById('val-delayed');
    const vFuel = document.getElementById('val-fuel');

    let performanceChartInstance = null;

    // Track input updates
    inputDeliveries.addEventListener('input', (e) => {
        labelDeliveries.textContent = e.target.value;
    });

    btnRun.addEventListener('click', async () => {
        // UI Reset
        btnRun.disabled = true;
        btnRun.classList.remove('pulse');
        loader.classList.remove('hidden');
        statsBoard.classList.add('hidden');
        chartSection.classList.add('hidden');
        
        statusText.style.color = '#38bdf8';
        statusText.textContent = "Compiling paths and running MPI nodes...";

        try {
            // Trigger Backend Simulation
            const response = await fetch(`http://127.0.0.1:8080/run-simulation?deliveries=${inputDeliveries.value}`);
            const data = await response.json();
            
            // Build metrics output
            updateDash(data.metrics);
        } catch (error) {
            statusText.style.color = '#f43f5e';
            statusText.textContent = "Failed to reach simulation core.";
            console.error(error);
        } finally {
            btnRun.disabled = false;
            btnRun.classList.add('pulse');
            loader.classList.add('hidden');
        }
    });

    function updateDash(metrics) {
        // Render Panels
        statsBoard.classList.remove('hidden');
        chartSection.classList.remove('hidden');
        statusText.style.color = '#10b981';
        statusText.textContent = "Simulation completed successfully.";

        // Update Text
        vSpeedup.textContent = `${metrics.speedup.toFixed(2)} x`;
        vParallel.textContent = `${metrics.parallel_time.toFixed(2)} s`;
        vEfficiency.textContent = `${(metrics.efficiency * 100).toFixed(1)} %`;
        vDelayed.textContent = metrics.delayed;
        vFuel.textContent = metrics.fuel_used.toFixed(0);

        renderChart(metrics.sequential_time, metrics.parallel_time);
    }

    function renderChart(seqTime, parTime) {
        const ctx = document.getElementById('performanceChart').getContext('2d');
        
        if (performanceChartInstance) {
            performanceChartInstance.destroy();
        }

        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = "'Inter', sans-serif";

        performanceChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Sequential', 'Parallel (MPI)'],
                datasets: [{
                    label: 'Execution Time (s)',
                    data: [seqTime, parTime],
                    backgroundColor: [
                        'rgba(244, 63, 94, 0.8)', // Rose for slow seq
                        'rgba(56, 189, 248, 0.8)'  // Sky blue for fast par
                    ],
                    borderColor: [
                        'rgb(244, 63, 94)',
                        'rgb(56, 189, 248)'
                    ],
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }
});
