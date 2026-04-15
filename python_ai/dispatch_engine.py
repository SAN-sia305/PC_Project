import time
from db_connection import db_instance

class RuleEngine:
    def __init__(self, pathfinder_ref):
        self.pathfinder = pathfinder_ref # Reference to query costs
        
        # Initialize default 5 drivers if DB is empty
        from pymongo.errors import DuplicateKeyError
        for i in range(5):
            if not db_instance.vehicles.find_one({"vid": i}):
                try:
                    db_instance.vehicles.insert_one({
                        "vid": i,
                        "current_node": 0,
                        "max_volume": 100,
                        "current_volume": 0,
                        "active_order_id": None,
                        "active_order_dst": None,
                        "eta_minutes": 0.0
                    })
                except DuplicateKeyError:
                    pass

    def _log(self, message):
        db_instance.events.insert_one({
            "message": message,
            "timestamp": time.time(),
            "read": False
        })
        print(message) # Also print to console

    def submit_order(self, src, dst, priority="LOW"):
        # Unique ID based on time to avoid concurrency collisions
        order_id = int(time.time() * 1000)
        
        db_instance.deliveries.insert_one({
            "order_id": order_id,
            "src": src,
            "dst": dst,
            "priority": priority,
            "status": "PENDING",
            "assigned_vehicle": None
        })
        self._log(f"[EVENT] New Order {order_id} ({priority}) placed: Node {src} -> {dst}")
        return order_id

    def evaluate_rules(self):
        """
        Forward Chaining Inference Loop. Runs continuously or per interval
        """
        self._complete_orders() # Step time forward to free occupied vehicles
        self._check_delays()
        self._assign_orders()
        
    def _complete_orders(self):
        """
        Advance vehicle dynamically along the physical path to represent realistic movement.
        """
        time_step = 2.0  # Actual seconds since last tick
        simulation_speedup = 30.0 # 1 real sec = 30 sim secs

        busy_vehicles = db_instance.vehicles.find({"capacity_available": False})
        
        for v in busy_vehicles:
            route = v.get("route", [])
            leg = v.get("current_leg", 0)
            
            if not route or leg >= len(route) - 1:
                # COMPLETED
                self._log(f"[RULE FIRED] Vehicle {v['vid']} COMPLETED Order {v['active_order_id']}. Freeing capacity.")
                db_instance.deliveries.update_one(
                     {"order_id": v["active_order_id"]},
                     {"$set": {"status": "COMPLETED"}}
                )
                db_instance.vehicles.update_one(
                     {"_id": v["_id"]},
                     {"$set": {
                         "current_node": v["active_order_dst"],
                         "capacity_available": True,
                         "current_volume": 0,
                         "active_order_id": None,
                         "active_order_dst": None,
                         "route": [],
                         "expected_cost": 0.0
                     }}
                )
                continue
                
            # Current edge progress
            src_node = route[leg]
            dst_node = route[leg+1]
            
            # Fetch base_time and traffic factor
            edge_data = self.pathfinder.graph.get_edge_data(src_node, dst_node)
            if edge_data is None: 
                 edge_data = {'base_time': 1.0, 'traffic_factor': 1.0}
            
            cost_of_leg = edge_data.get('base_time', 1.0) * edge_data.get('traffic_factor', 1.0)
            
            # Simulated minutes advanced
            progress_made_mins = (time_step * simulation_speedup) / 60.0
            
            # Add to route_progress
            new_prog = v.get("route_progress", 0.0) + (progress_made_mins / max(0.1, cost_of_leg))
            
            if new_prog >= 1.0:
                # Passed the node
                db_instance.vehicles.update_one(
                     {"_id": v["_id"]},
                     {"$set": {
                         "current_node": dst_node,
                         "current_leg": leg + 1,
                         "route_progress": 0.0
                     }}
                )
            else:
                db_instance.vehicles.update_one(
                     {"_id": v["_id"]},
                     {"$set": {
                         "route_progress": new_prog
                     }}
                )

    def _check_delays(self):
        """
        Rule: IF vehicle.delay > 20 mins THEN reassign / flag delayed
        """
        busy_vehicles = list(db_instance.vehicles.find({"capacity_available": False}))
        if not busy_vehicles:
            return
            
        tasks = []
        for v in busy_vehicles:
            tasks.append((v["current_node"], v["active_order_dst"], v["active_order_id"], v["vid"]))
                
        if hasattr(self, 'mpi_pool') and self.mpi_pool is not None:
            results = self.mpi_pool.compute_batch(tasks)
            costs = {res["v_id"]: res["cost"] for res in results}
        else:
            costs = {}
            for v_curr, o_dst, o_id, v_id in tasks:
                 c, _ = self.pathfinder.compute_shortest_path(v_curr, o_dst, record_ui=False)
                 costs[v_id] = c

        for v in busy_vehicles:
            current_cost = costs.get(v["vid"], 0.0)
            expected = v.get("expected_cost", 0.0)
            
            # Compare fresh traffic cost against the original expected cost
            if expected > 0 and current_cost > expected + 20.0:
                self._log(f"[RULE FIRED] Vehicle {v['vid']} delayed by Traffic! Reassigning Order {v['active_order_id']}")
                
                # Re-queue the delivery
                db_instance.deliveries.update_one(
                    {"order_id": v["active_order_id"]},
                    {"$set": {
                        "status": "DELAYED",
                        "assigned_vehicle": None
                    }}
                )
                
                # Free the vehicle
                db_instance.vehicles.update_one(
                    {"_id": v["_id"]},
                    {"$set": {
                        "capacity_available": True,
                        "active_order_id": None,
                        "active_order_dst": None,
                        "expected_cost": 0.0
                    }}
                )

    def _assign_orders(self):
        """
        Rule: IF order.priority == HIGH AND vehicle.capacity_available THEN assign immediately
        Fallback: Assign LOW priority if capacity available.
        """
        # Fetch pending/delayed orders, sorted so HIGH priority evaluate first
        pending_orders = list(db_instance.deliveries.find({"status": {"$in": ["PENDING", "DELAYED"]}}))
        pending_orders.sort(key=lambda x: 0 if x.get("priority") == "HIGH" else 1)

        available_vehicles = list(db_instance.vehicles.find({"capacity_available": True}))
        
        if not available_vehicles or not pending_orders:
            return
            
        tasks = []
        for order in pending_orders:
            for v in available_vehicles:
                tasks.append((v["current_node"], order["src"], order["order_id"], v["vid"]))
                
        if hasattr(self, 'mpi_pool') and self.mpi_pool is not None:
            results = self.mpi_pool.compute_batch(tasks)
        else:
            results = []
            for src, dst, o_id, v_id in tasks:
                c, _ = self.pathfinder.compute_shortest_path(src, dst, record_ui=False)
                results.append({"order_id": o_id, "v_id": v_id, "cost": c})
                
        order_costs = {}
        for r in results:
            order_costs.setdefault(r["order_id"], []).append((r["v_id"], r["cost"]))

        for order in pending_orders:
            available_vehicles = list(db_instance.vehicles.find({"capacity_available": True}))
            if not available_vehicles:
                break
                
            v_costs = order_costs.get(order["order_id"], [])
            v_costs.sort(key=lambda x: x[1]) # Sort by lowest dispatch cost
            
            for v_id, cost in v_costs:
                v = next((x for x in available_vehicles if x["vid"] == v_id), None)
                if v:
                    if cost < 50.0 or order.get("priority") == "HIGH": 
                        delivery_cost, route = self.pathfinder.compute_shortest_path(
                            order["src"], order["dst"], record_ui=True, priority=order.get("priority")
                        )
                        eta = cost + delivery_cost
                        
                        db_instance.vehicles.update_one(
                            {"_id": v["_id"]},
                            {"$set": {
                                "capacity_available": False,
                                "active_order_id": order["order_id"],
                                "active_order_dst": order["dst"],
                                "eta_minutes": eta,
                                "expected_cost": delivery_cost,
                                "route": route,
                                "current_leg": 0,
                                "route_progress": 0.0
                            }}
                        )
                        
                        db_instance.deliveries.update_one(
                            {"_id": order["_id"]},
                            {"$set": {
                                "assigned_vehicle": v["vid"],
                                "status": "ASSIGNED"
                            }}
                        )
                        
                        self._log(f"[RULE FIRED] Assigned Order {order['order_id']} ({order.get('priority')}) to Vehicle {v['vid']}. ETA: {eta:.1f}m")
                        break
