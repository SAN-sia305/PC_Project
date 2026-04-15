import networkx as nx
import random
from dispatch_engine import RuleEngine
from db_connection import db_instance

class PathFinder:
    def __init__(self, num_nodes=50, seed=42):
        self.num_nodes = num_nodes
        self.graph = nx.Graph()
        self.random_state = random.Random(seed)
        
        # Real-time routes are now written to MongoDB 'routes' collection
        self._generate_mock_graph()
        self.engine = RuleEngine(self)

    def _generate_mock_graph(self):
        """
        Creates an authentic road network representing real streets using OSMnx.
        Assigns 'base_time' and 'traffic_factor' attributes to all edges.
        """
        try:
            import osmnx as ox
            print("> DOWNLOADING REAL-TIME OSMNX STREET GRAPH FOR COIMBATORE... (This might take 10 seconds)", flush=True)
            # Disable cache to avoid MPI 4-process simultaneous lock deadlocks
            ox.settings.use_cache = False
            
            # Focused Bounding Box for Coimbatore (Gandhipuram Area)
            center_point = (11.0168, 76.9558) 
            G = ox.graph_from_point(center_point, dist=2500, network_type='drive')
            
            # Map MultiDiGraph to simple generic Graph for our simplistic inference engine
            self.graph = nx.Graph(G)
            self.num_nodes = len(self.graph.nodes)
            
            # Remap osmnx node IDs to 0...N range
            mapping = {old_label: new_label for new_label, old_label in enumerate(self.graph.nodes())}
            self.graph = nx.relabel_nodes(self.graph, mapping)
            
            for n, data in self.graph.nodes(data=True):
                data['lat'] = data.get('y', 11.01)
                data['lon'] = data.get('x', 76.95)
                
            for u, v, data in self.graph.edges(data=True):
                dist_m = data.get('length', 100.0)
                # Assume 40 km/h avg speed -> ~666 meters per minute
                base_time = max(1.0, dist_m / 666.0)
                self.graph[u][v]['base_time'] = base_time
                self.graph[u][v]['traffic_factor'] = 1.0
                
            print(f"> OSMNX GRAPH CONSTRUCTED. SYSTEM LOADED WITH {self.num_nodes} REAL INTERSECTIONS.", flush=True)
            
        except Exception as e:
            print(f"> OSMNX FETCH FAILED, FALLING BACK TO DEV MOCK: {e}", flush=True)
            self.graph = nx.barabasi_albert_graph(self.num_nodes, 3, seed=self.random_state.randint(0, 1000))
            
            LAT_MIN, LAT_MAX = 10.9, 11.1
            LON_MIN, LON_MAX = 76.9, 77.0
            
            for n in self.graph.nodes():
                self.graph.nodes[n]['lat'] = self.random_state.uniform(LAT_MIN, LAT_MAX)
                self.graph.nodes[n]['lon'] = self.random_state.uniform(LON_MIN, LON_MAX)
            
            for u, v in self.graph.edges():
                base_time = self.random_state.uniform(1.0, 10.0)
                self.graph[u][v]['base_time'] = base_time
                self.graph[u][v]['traffic_factor'] = 1.0

    def get_nearest_node(self, lat, lon):
        from scipy.spatial import KDTree
        if not hasattr(self, 'kdtree'):
            coords = []
            for n in range(self.num_nodes):
                coords.append((self.graph.nodes[n]['lat'], self.graph.nodes[n]['lon']))
            self.kdtree = KDTree(coords)
            
        distance, idx = self.kdtree.query((lat, lon))
        return int(idx)
            
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
                db_instance.routes.insert_one({
                    "id": int(time.time() * 1000) + self.random_state.randint(0, 10000),
                    "src": src,
                    "dst": dst,
                    "route": route,
                    "cost": cost,
                    "priority": priority,
                    "read": False
                })

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
