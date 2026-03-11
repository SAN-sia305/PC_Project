import time
from typing import Optional

class Order:
    def __init__(self, order_id, src, dst, priority="LOW"):
        self.order_id = order_id
        self.src = src
        self.dst = dst
        self.priority = priority # HIGH or LOW
        self.status = "PENDING"  # PENDING, ASSIGNED, COMPLETED, DELAYED
        self.assigned_vehicle = None

class Vehicle:
    def __init__(self, vid, current_node):
        self.vid = vid
        self.current_node = current_node
        self.capacity_available = True
        self.active_order: Optional[Order] = None
        self.eta_minutes = 0.0
        
class RuleEngine:
    def __init__(self, pathfinder_ref):
        self.pathfinder = pathfinder_ref # Reference to query costs
        self.vehicles = [Vehicle(i, 0) for i in range(5)] # Mock 5 drivers
        self.pending_orders = []
        self.logs = []

    def submit_order(self, src, dst, priority="LOW"):
        order_id = len(self.pending_orders) + 100
        new_order = Order(order_id, src, dst, priority)
        self.pending_orders.append(new_order)
        self.logs.append(f"[EVENT] New Order {order_id} ({priority}) placed: Node {src} -> {dst}")
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
        Rule: Simulate time passing. IF vehicle finishes route, flag capacity as available again to accept new maps.
        """
        # We simulate a "chunk" of time passing every time the engine is evaluated via API ping
        time_step = 25.0 
        
        for v in self.vehicles:
            order = v.active_order
            if not v.capacity_available and order:
                v.eta_minutes -= time_step
                
                if v.eta_minutes <= 0.0:
                    self.logs.append(f"[RULE FIRED] Vehicle {v.vid} COMPLETED Order {order.order_id}. Freeing capacity.")
                    order.status = "COMPLETED"
                    v.current_node = order.dst # Relocate to destination
                    
                    # Free up vehicle for next Rule Chain
                    v.capacity_available = True
                    v.active_order = None

    def _check_delays(self):
        """
        Rule: IF vehicle.delay > 20 mins THEN reassign / flag delayed
        """
        tasks = []
        active_vehicles = []
        for v in self.vehicles:
            order = v.active_order
            if not v.capacity_available and order:
                tasks.append((v.current_node, order.dst, order.order_id, v.vid))
                active_vehicles.append((v, order))
                
        if not tasks:
            return
            
        if hasattr(self, 'mpi_pool') and self.mpi_pool is not None:
            results = self.mpi_pool.compute_batch(tasks)
            costs = {res["v_id"]: res["cost"] for res in results}
        else:
            costs = {}
            for v_curr, o_dst, o_id, v_id in tasks:
                 c, _ = self.pathfinder.compute_shortest_path(v_curr, o_dst, record_ui=False)
                 costs[v_id] = c

        for v, order in active_vehicles:
            current_cost = costs[v.vid]
            # If traffic suddenly spiked the ETA
            if current_cost > v.eta_minutes + 20.0:
                self.logs.append(f"[RULE FIRED] Vehicle {v.vid} delayed by Traffic! Reassigning Order {order.order_id}")
                order.status = "DELAYED"
                order.assigned_vehicle = None
                self.pending_orders.append(order) # throw back in queue
                v.capacity_available = True
                v.active_order = None

    def _assign_orders(self):
        """
        Rule: IF order.priority == HIGH AND vehicle.capacity_available THEN assign immediately
        Fallback: Assign LOW priority if capacity available.
        """
        # Sort so HIGH priority orders are evaluated first (Forward Chain priority)
        self.pending_orders.sort(key=lambda x: 0 if x.priority == "HIGH" else 1)

        available_vehicles = [v for v in self.vehicles if v.capacity_available]
        if not available_vehicles or not self.pending_orders:
            return
            
        tasks = []
        for order in self.pending_orders:
            for v in available_vehicles:
                tasks.append((v.current_node, order.src, order.order_id, v.vid))
                
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

        unassigned = []
        for order in self.pending_orders:
            assigned = False
            v_costs = order_costs.get(order.order_id, [])
            v_costs.sort(key=lambda x: x[1]) # Sort by lowest dispatch cost
            
            for v_id, cost in v_costs:
                v = next((x for x in self.vehicles if x.vid == v_id), None)
                if v and v.capacity_available:
                    # Assume threshold heuristic: Nearest vehicle under 50 mins away gets it
                    if cost < 50.0 or order.priority == "HIGH": 
                        # HIGH priority bypasses distance threshold entirely! Rule 1 logic
                        v.capacity_available = False
                        v.active_order = order
                        order.assigned_vehicle = v.vid
                        order.status = "ASSIGNED"
                        
                        # Full route cost (Vehicle -> Src -> Dst)
                        delivery_cost, route = self.pathfinder.compute_shortest_path(order.src, order.dst, record_ui=True, priority=order.priority)
                        v.eta_minutes = cost + delivery_cost
                        
                        self.logs.append(f"[RULE FIRED] Assigned Order {order.order_id} ({order.priority}) to Vehicle {v.vid}. ETA: {v.eta_minutes:.1f}m")
                        assigned = True
                        break
            if not assigned:
                unassigned.append(order)
                
        self.pending_orders = unassigned
