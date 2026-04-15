import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import axios from 'axios';

const NetworkGraph = ({ isSimulating, terminalLogs }) => {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const animationFrameRef = useRef(null);
  const nodeMapRef = useRef(new Map());
  const activeTracesRef = useRef([]);

  useEffect(() => {
    const initMap = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:8000/graph-data');
        const data = response.data;
        
        // React 18 StrictMode Protection:
        // Ensure the component hasn't unmounted while we were awaiting the graph data
        if (!mapContainer.current) return;
        
        // Setup coordinate lookup
        const nMap = new Map();
        data.nodes.forEach(n => {
          nMap.set(n.id, [n.lon, n.lat]);
        });
        nodeMapRef.current = nMap;

        const map = new maplibregl.Map({
          container: mapContainer.current,
          style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
          center: [76.9558, 11.0168], // Coimbatore Center
          zoom: 13,
          pitch: 45,
          bearing: -15,
          attributionControl: false
        });

        map.on('load', () => {
          // Static Edges
          const edgeFeatures = [];
          data.links.forEach(link => {
            const srcCoords = nMap.get(link.source);
            const tgtCoords = nMap.get(link.target);
            if (srcCoords && tgtCoords) {
              let color = "#00ff41"; 
              if (link.traffic_factor > 2.0) color = "#ff003c"; 
              else if (link.traffic_factor > 1.5) color = "#ff8c00"; 
              
              edgeFeatures.push({
                type: "Feature",
                geometry: { type: "LineString", coordinates: [srcCoords, tgtCoords] },
                properties: { color, weight: Math.max(1, link.traffic_factor) }
              });
            }
          });

          map.addSource('network-edges', {
            type: 'geojson',
            data: { type: "FeatureCollection", features: edgeFeatures }
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

          // Static Nodes
          const nodeFeatures = data.nodes.map(n => ({
            type: "Feature",
            geometry: { type: "Point", coordinates: [n.lon, n.lat] }
          }));

          map.addSource('network-nodes', {
            type: 'geojson',
            data: { type: "FeatureCollection", features: nodeFeatures }
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

          // Dynamic deliveries layer
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
              'circle-blur': 0.2
            }
          });

          // DISPATCH MODE: Add clickable orders!
          map.on('click', async (e) => {
            const lat = e.lngLat.lat;
            const lon = e.lngLat.lng;
            
            const el = document.createElement('div');
            el.className = 'pulse-marker';
            
            const marker = new maplibregl.Marker({ element: el })
              .setLngLat([lon, lat])
              .addTo(map);

            try {
              await axios.post('http://127.0.0.1:8000/create-order', { lat, lon, priority: 'HIGH' });
              // Remove marker after 30 seconds
              setTimeout(() => marker.remove(), 30000);
            } catch (err) {
              console.error("Manual order routing failed", err);
              marker.remove();
            }
          });

          startAnimationLoop();
        });
        
        mapRef.current = map;
      } catch (err) {
        console.error("Map Data Fetch Error", err);
      }
    };

    if (!mapRef.current) {
      initMap();
    }

    return () => {
      // Cleanup map on unmount
    };
  }, []);

  const processedDeliveries = useRef(new Set());

  // Polling for deliveries
  useEffect(() => {
    let interval;
    if (isSimulating) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get("http://127.0.0.1:8000/active-deliveries");
          if (res.data.deliveries?.length > 0) {
            if (processedDeliveries.current.size > 2000) processedDeliveries.current.clear();
            
            res.data.deliveries.forEach(del => {
              if (!del.id || processedDeliveries.current.has(del.id)) return;
              processedDeliveries.current.add(del.id);
              
              if (del.route?.length < 2) return;

              // Scale animation speed down slightly to visualize the delivery better
              activeTracesRef.current.push({
                id: del.id,
                route: del.route,
                currentLegIndex: 0,
                progress: 0.0,
                color: del.priority === "HIGH" ? "#ff003c" : "#ffffff",
                radius: del.priority === "HIGH" ? 5 : 4
              });
            });
          }
        } catch (e) {}
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isSimulating]);

  const startAnimationLoop = () => {
    const animateFrame = () => {
      const currentFeatures = [];
      const traces = activeTracesRef.current;
      const nMap = nodeMapRef.current;

      for (let i = traces.length - 1; i >= 0; i--) {
        let trace = traces[i];
        const currentCoords = nMap.get(trace.route[trace.currentLegIndex]);
        const nextCoords = nMap.get(trace.route[trace.currentLegIndex + 1]);

        if (!currentCoords || !nextCoords) {
          traces.splice(i, 1);
          continue;
        }

        // Reduced from 0.05 so dots survive longer on UI
        trace.progress += 0.02;

        if (trace.progress >= 1.0) {
          trace.currentLegIndex++;
          trace.progress = 0.0;
          if (trace.currentLegIndex >= trace.route.length - 1) {
            traces.splice(i, 1);
            continue;
          }
        }

        const lng = currentCoords[0] + (nextCoords[0] - currentCoords[0]) * trace.progress;
        const lat = currentCoords[1] + (nextCoords[1] - currentCoords[1]) * trace.progress;

        currentFeatures.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: [lng, lat] },
          properties: { color: trace.color, radius: trace.radius }
        });
      }

      if (mapRef.current && mapRef.current.getSource('deliveries')) {
        mapRef.current.getSource('deliveries').setData({
          type: "FeatureCollection",
          features: currentFeatures
        });
      }

      animationFrameRef.current = requestAnimationFrame(animateFrame);
    };
    
    animateFrame();
  };

  const terminalScrollRef = useRef(null);
  
  useEffect(() => {
    if (terminalScrollRef.current) {
        terminalScrollRef.current.scrollTop = terminalScrollRef.current.scrollHeight;
    }
  }, [terminalLogs]);

  return (
    <div className="network-split">
      <div className="chart-card brutal-box map-wrapper">
        <h3>LIVE_ROAD_NETWORK_NODES</h3>
        <div ref={mapContainer} style={{ position: 'absolute', top: 50, bottom: 20, left: 20, right: 20 }} />
      </div>

      <div className="terminal-container brutal-box" style={{ padding: 0 }}>
        <div className="terminal-header" style={{ padding: '20px' }}>{">"} RULE_ENGINE_OUTPUT_STREAM</div>
        <div className="log-scroll" ref={terminalScrollRef} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {terminalLogs.map((log, i) => {
            let className = "log-line";
            if (log.msg.includes("delayed by Traffic")) className += " alert";
            else if (log.msg.includes("[RULE FIRED]")) className += " fired";
            else className += " event";

            return <div key={i} className={className}>{log.msg}</div>;
          })}
        </div>
      </div>
    </div>
  );
};

export default NetworkGraph;
