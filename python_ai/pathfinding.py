import networkx as nx
import random
from dispatch_engine import RuleEngine

class PathFinder:
    def __init__(self, num_nodes=50, seed=42):
        self.num_nodes = num_nodes
        self.graph = nx.Graph()
        self.random_state = random.Random(seed)
        self.active_deliveries = [] # Track real-time routes
        self._generate_mock_graph()
        self.engine = RuleEngine(self)

    def _generate_mock_graph(self):
        """
        Creates a connected Erdős-Rényi graph or similar simple network to ensure connectivity.
        Assigns 'base_time' and 'traffic_factor' attributes to all edges.
        Assigns Lat/Lon coordinates mapped to Tamil Nadu region for Leaflet UI mapping.
        """
        # A simple connected network for tests
        # Barabasi-Albert guarantees a single connected component
        self.graph = nx.barabasi_albert_graph(self.num_nodes, 3, seed=self.random_state.randint(0, 1000))
        
        # Approximate Bounding Box for Tamil Nadu, India
        LAT_MIN, LAT_MAX = 8.5, 13.5
        LON_MIN, LON_MAX = 76.2, 80.3
        
        for n in self.graph.nodes():
            self.graph.nodes[n]['lat'] = self.random_state.uniform(LAT_MIN, LAT_MAX)
            self.graph.nodes[n]['lon'] = self.random_state.uniform(LON_MIN, LON_MAX)
        
        for u, v in self.graph.edges():
            # Distance / Base cost mapping between 10 to 100 mins
            base_time = self.random_state.uniform(10.0, 100.0)
            self.graph[u][v]['base_time'] = base_time
            self.graph[u][v]['traffic_factor'] = 1.0
            
    def apply_traffic(self, max_multiplier=3.0):
        """
        Updates the graph edges with random congestion multipliers simulating traffic shifts.
        """
        for u, v in self.graph.edges():
            new_multiplier = self.random_state.uniform(1.0, max_multiplier)
            self.graph[u][v]['traffic_factor'] = new_multiplier

    def apply_edge_updates(self, edge_updates):
        """
        Applies a dict of {(u,v): traffic_factor} to sync graphs across MPI nodes.
        """
        for (u, v), new_factor in edge_updates.items():
            if self.graph.has_edge(u, v):
                self.graph[u][v]['traffic_factor'] = new_factor

    def compute_shortest_path(self, src: int, dst: int, record_ui=True, priority="LOW"):
        """
        Runs Dijkstra to find the fastest route. Uses 'weight' = base_time * traffic_factor
        Returns: (cost: float, route: list)
        """
        # Dynamic Weight mapping
        def dynamic_weight(u, v, d):
            return d['base_time'] * d['traffic_factor']

        try:
            route = nx.shortest_path(self.graph, source=src, target=dst, weight=dynamic_weight)
            cost = nx.shortest_path_length(self.graph, source=src, target=dst, weight=dynamic_weight)
            
            # Register active delivery for UI animation tracking, IF authorized by engine
            if record_ui:
                import time
                self.active_deliveries.append({
                    "id": int(time.time() * 1000) + self.random_state.randint(0, 10000),
                    "src": src,
                    "dst": dst,
                    "route": route,
                    "cost": cost,
                    "priority": priority
                })
                
                # Keep array clean for UI (keep last 100 max for memory)
                if len(self.active_deliveries) > 100:
                    self.active_deliveries.pop(0)

            return cost, route
        except nx.NetworkXNoPath:
            return float('inf'), []

    def get_graph_data(self):
        """
        Export graph representation for Web UI visualization (Cytoscape/D3/ChartJS/Leaflet format)
        """
        # Simplified export to be consumed by JS Frontend
        nodes = []
        for n, data in self.graph.nodes(data=True):
            nodes.append({
                'id': n,
                'lat': data.get('lat', 0.0),
                'lon': data.get('lon', 0.0)
            })

        links = []
        for u, v, data in self.graph.edges(data=True):
            links.append({
                'source': u,
                'target': v,
                'base_time': data['base_time'],
                'traffic_factor': data['traffic_factor']
            })
        return {'nodes': nodes, 'links': links}
