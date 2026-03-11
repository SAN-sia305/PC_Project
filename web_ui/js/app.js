document.addEventListener('DOMContentLoaded', () => {
    // References
    const btnRun = document.getElementById('btn-run');
    const inputDeliveries = document.getElementById('input-deliveries');
    const labelDeliveries = document.getElementById('label-deliveries');

    // UI Panels
    const statsBoard = document.getElementById('stats-dashboard');
    const chartSection = document.getElementById('chart-section');
    const networkSection = document.getElementById('network-dashboard');
    const btnDashboard = document.getElementById('btn-dashboard');
    const btnNetwork = document.getElementById('btn-network');

    const loader = document.getElementById('loader');
    const statusText = document.getElementById('status-text');

    // Stats Vals
    const vSpeedup = document.getElementById('val-speedup');
    const vParallel = document.getElementById('val-parallel');
    const vEfficiency = document.getElementById('val-efficiency');
    const vDelayed = document.getElementById('val-delayed');
    const vFuel = document.getElementById('val-fuel');

    let performanceChartInstance = null;

    // Custom glitch characters effect
    function glitchText(element, finalValue) {
        const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*";
        let iteration = 0;
        let interval = setInterval(() => {
            element.innerText = finalValue.split("").map((letter, index) => {
                if (index < iteration) {
                    return finalValue[index];
                }
                return chars[Math.floor(Math.random() * chars.length)];
            }).join("");

            if (iteration >= finalValue.length) {
                clearInterval(interval);
            }
            iteration += 1 / 3;
        }, 30);
    }

    // Navigation setup
    btnDashboard.addEventListener('click', () => {
        btnDashboard.classList.add('active');
        btnNetwork.classList.remove('active');
        if (!statsBoard.classList.contains('hidden')) {
            chartSection.classList.remove('hidden');
        }
        networkSection.classList.add('hidden');
    });

    btnNetwork.addEventListener('click', () => {
        btnNetwork.classList.add('active');
        btnDashboard.classList.remove('active');
        chartSection.classList.add('hidden');
        if (!statsBoard.classList.contains('hidden')) {
            networkSection.classList.remove('hidden');
        }
    });

    // Track input updates
    inputDeliveries.addEventListener('input', (e) => {
        labelDeliveries.textContent = e.target.value;
    });

    let pollingInterval = null;
    let isSimulating = false;

    btnRun.addEventListener('click', async () => {
        if (isSimulating) return;

        // UI Reset
        btnRun.disabled = true;
        btnRun.innerText = "EXECUTING...";
        loader.classList.remove('hidden');
        statsBoard.classList.add('hidden');
        chartSection.classList.add('hidden');
        networkSection.classList.add('hidden');

        statusText.style.color = 'var(--text-color)';
        statusText.textContent = "> INITIATING MPI SUBROUTINES...";
        
        const terminalLogs = document.getElementById('terminal-logs');
        if (terminalLogs) terminalLogs.innerHTML = "";

        try {
            // Initiate Bulk Orders on backend
            await fetch(`http://127.0.0.1:8080/run-simulation?deliveries=${inputDeliveries.value}`);

            // Reveal Live Dashboard
            statsBoard.classList.remove('hidden');
            if (!btnDashboard.classList.contains('active')) {
                networkSection.classList.remove('hidden');
            }
            
            statusText.style.color = 'var(--neon-green)';
            statusText.textContent = "> SYSTEM LIVE. POLLING RULE ENGINE...";
            
            if(!pollingInterval) {
                pollingInterval = setInterval(pollSystemStats, 1500);
            }
        } catch (error) {
            statusText.style.color = 'var(--neon-red)';
            glitchText(statusText, "> ERR: SYS_CORE_OFFLINE");
            console.error(error);
        } finally {
            setTimeout(() => {
                btnRun.disabled = false;
                btnRun.innerText = "INJECT_MORE_ORDERS()";
                loader.classList.add('hidden');
            }, 800);
        }
    });

    async function pollSystemStats() {
        try {
            const response = await fetch("http://127.0.0.1:8080/system-stats");
            const data = await response.json();
            const metrics = data.metrics;

            // Update Numeric Dash
            vSpeedup.innerText = metrics.pending_orders; // Re-using DOM slot for "Pending"
            vSpeedup.previousElementSibling.innerText = "ORDERS_PENDING";
            
            vParallel.innerText = metrics.active_vehicles; // Re-using DOM slot for "Active"
            vParallel.previousElementSibling.innerText = "ACTIVE_DRIVERS";
            
            vEfficiency.innerText = metrics.completed_deliveries; // Re-using DOM slot for "Completed"
            vEfficiency.previousElementSibling.innerText = "DELIVERIES_COMPLETED";
            
            vDelayed.innerText = metrics.delayed;
            vFuel.innerText = metrics.fuel_used.toFixed(0);

            // Handle Terminal Logs
            const terminalLogs = document.getElementById('terminal-logs');
            if(terminalLogs && metrics.recent_logs && metrics.recent_logs.length > 0) {
                metrics.recent_logs.forEach(msg => {
                    const el = document.createElement("div");
                    let formatted = messageFormatter(msg);
                    el.className = getClassForMsg(msg);
                    el.innerHTML = formatted;
                    terminalLogs.appendChild(el);
                });
                
                // Auto-scroll logic
                if(terminalLogs.children.length > 150) {
                    for(let i=0; i < 50; i++) {
                        terminalLogs.removeChild(terminalLogs.firstChild);
                    }
                }
                terminalLogs.scrollTop = terminalLogs.scrollHeight;
            }

        } catch (e) {
            console.warn("Poll missed");
        }
    }

    function messageFormatter(msg) {
        if(msg.includes("[EVENT]")) return msg.replace("[EVENT]", `<span style="color:var(--text-color)">[EVENT]</span>`);
        if(msg.includes("[RULE FIRED]")) {
            let out = msg.replace("[RULE FIRED]", `<span style="color:#0ff">[RULE FIRED]</span>`);
            if (out.includes("delayed by Traffic")) {
                out = `<span style="color:var(--neon-red)">${out}</span>`;
            }
            return out;
        }
        return msg;
    }
    
    function getClassForMsg(msg) {
        if(msg.includes("delayed by Traffic")) return "log-line alert";
        if(msg.includes("[RULE FIRED]")) return "log-line fired";
        return "log-line event";
    }

    // MapLibre GL JS WebGL Geographic Map Implementation
    let map = null;

    async function initializeNetworkMap() {
        const placeholder = document.getElementById('map-placeholder');
        const loadingText = document.getElementById('network-loading-text');

        try {
            const response = await fetch('http://127.0.0.1:8080/graph-status');
            const data = await response.json();

            if (loadingText) loadingText.remove();

            // Initialize MapLibre GL Map Centered on Tamil Nadu
            const centerLat = 11.0;
            const centerLon = 78.2;

            map = new maplibregl.Map({
                container: 'map-placeholder',
                style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                center: [centerLon, centerLat], // MapLibre takes [lng, lat]
                zoom: 6.5,
                pitch: 45, // Cool 3D aesthetic angle
                bearing: -15,
                attributionControl: false
            });

            const nodeMap = new Map();
            data.nodes.forEach(n => {
                nodeMap.set(n.id, [n.lon, n.lat]);
            });

            map.on('load', () => {
                // 1. Build Static Network Edges (Roads) GeoJSON
                const edgeFeatures = [];
                data.links.forEach(link => {
                    const srcCoords = nodeMap.get(link.source);
                    const tgtCoords = nodeMap.get(link.target);

                    if (srcCoords && tgtCoords) {
                        let color = "#00ff41"; // Safe Green
                        if (link.traffic_factor > 2.0) color = "#ff003c"; // Heavy Traffic Red
                        else if (link.traffic_factor > 1.5) color = "#ff8c00"; // Medium Orange

                        edgeFeatures.push({
                            type: "Feature",
                            geometry: {
                                type: "LineString",
                                coordinates: [srcCoords, tgtCoords]
                            },
                            properties: {
                                color: color,
                                weight: Math.max(1, link.traffic_factor)
                            }
                        });
                    }
                });

                map.addSource('network-edges', {
                    type: 'geojson',
                    data: {
                        type: "FeatureCollection",
                        features: edgeFeatures
                    }
                });

                map.addLayer({
                    id: 'edges-layer',
                    type: 'line',
                    source: 'network-edges',
                    paint: {
                        'line-color': ['get', 'color'],
                        'line-width': ['get', 'weight'],
                        'line-opacity': 0.4
                    }
                });

                // 2. Build Static Nodes GeoJSON
                const nodeFeatures = data.nodes.map(n => ({
                    type: "Feature",
                    geometry: {
                        type: "Point",
                        coordinates: [n.lon, n.lat]
                    }
                }));

                map.addSource('network-nodes', {
                    type: 'geojson',
                    data: {
                        type: "FeatureCollection",
                        features: nodeFeatures
                    }
                });

                map.addLayer({
                    id: 'nodes-layer',
                    type: 'circle',
                    source: 'network-nodes',
                    paint: {
                        'circle-radius': 3.5,
                        'circle-color': '#050505',
                        'circle-stroke-color': '#00ff41',
                        'circle-stroke-width': 1.5
                    }
                });

                // 3. Prep Animation Layer
                map.addSource('deliveries', {
                    type: 'geojson',
                    data: { type: "FeatureCollection", features: [] }
                });

                map.addLayer({
                    id: 'deliveries-layer',
                    type: 'circle',
                    source: 'deliveries',
                    paint: {
                        'circle-radius': ['get', 'radius'],
                        'circle-color': ['get', 'color'],
                        'circle-opacity': 1,
                        'circle-blur': 0.2 // Give it a slight glow
                    }
                });

                startDeliveryLoop(nodeMap);
            });

        } catch (error) {
            console.error("Failed to fetch graph data", error);
            if (loadingText) {
                loadingText.style.color = "#ff003c";
                loadingText.innerText = "> ERR: MAP_DATA_UNAVAILABLE";
            }
        }
    }

    function startDeliveryLoop(nodeMap) {
        const processedDeliveries = new Set();
        let activeTraces = []; // Holds the state of all currently animating deliveries

        async function pollDeliveries() {
            try {
                const res = await fetch("http://127.0.0.1:8080/active-deliveries");
                const deliveryData = await res.json();

                if (deliveryData.deliveries && deliveryData.deliveries.length > 0) {
                    if (processedDeliveries.size > 2000) processedDeliveries.clear();

                    // Register new deliveries into the animation queue
                    deliveryData.deliveries.forEach(del => {
                        if (!del.id || processedDeliveries.has(del.id)) return;
                        processedDeliveries.add(del.id);

                        const route = del.route;
                        if (route.length < 2) return;

                        const isHighPriority = del.priority === "HIGH";

                        // Push a tracker object determining where this delivery is right now
                        activeTraces.push({
                            id: del.id,
                            route: route,
                            currentLegIndex: 0,
                            progress: 0.0, // 0.0 to 1.0 interpolation between current and next node
                            color: isHighPriority ? "#ff003c" : "#ffffff",
                            radius: isHighPriority ? 5 : 4
                        });
                    });
                }
            } catch (e) { }
        }

        setInterval(pollDeliveries, 1500);

        // Single atomic WebGL animation loop for ALL markers
        function animateFrame() {
            const currentFeatures = [];

            // Advance each trace mathematically
            for (let i = activeTraces.length - 1; i >= 0; i--) {
                let trace = activeTraces[i];

                const currentCoords = nodeMap.get(trace.route[trace.currentLegIndex]);
                const nextCoords = nodeMap.get(trace.route[trace.currentLegIndex + 1]);

                if (!currentCoords || !nextCoords) {
                    activeTraces.splice(i, 1);
                    continue;
                }

                // Advance progress by 5% per frame
                trace.progress += 0.05;

                if (trace.progress >= 1.0) {
                    // Reached end of leg
                    trace.currentLegIndex++;
                    trace.progress = 0.0;

                    if (trace.currentLegIndex >= trace.route.length - 1) {
                        // Reached absolute destination, remove from map
                        activeTraces.splice(i, 1);
                        continue;
                    }
                }

                // Interpolate exact [lng, lat] coordinate
                const lng = currentCoords[0] + (nextCoords[0] - currentCoords[0]) * trace.progress;
                const lat = currentCoords[1] + (nextCoords[1] - currentCoords[1]) * trace.progress;

                // Push feature for this specific frame
                currentFeatures.push({
                    type: "Feature",
                    geometry: { type: "Point", coordinates: [lng, lat] },
                    properties: { color: trace.color, radius: trace.radius }
                });
            }

            // Fast atomic GPU upload for the entire data layer at once
            if (map && map.getSource('deliveries')) {
                map.getSource('deliveries').setData({
                    type: "FeatureCollection",
                    features: currentFeatures
                });
            }

            requestAnimationFrame(animateFrame);
        }

        animateFrame(); // Kick off 60FPS loop
    }

    // Initialize map on load
    initializeNetworkMap();
});
