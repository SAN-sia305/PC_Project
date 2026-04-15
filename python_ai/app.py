import asyncio
import random
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathfinding import PathFinder
from mpi_pool import MPIPool
from db_connection import db_instance
import time

app = FastAPI(title="DIFM-DOS Python Pathfinding Microservice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instance
pathfinder = PathFinder(num_nodes=1000, seed=42)
mpi_pool = MPIPool(pathfinder)
pathfinder.engine.mpi_pool = mpi_pool

from pymongo.errors import DuplicateKeyError

# Initialize global performance metrics doc
if not db_instance.performance_metrics.find_one({"_id": "global_stats"}):
    try:
        db_instance.performance_metrics.insert_one({
            "_id": "global_stats",
            "total_deliveries_injected": 0,
            "total_delayed": 0,
            "fuel_used": 0.0
        })
    except DuplicateKeyError:
        pass

engine_running = False

async def function_loop():
    while engine_running:
        pathfinder.engine.evaluate_rules()
        
        # Calculate derived metrics to update the global_stats for UI
        delayed_count = db_instance.deliveries.count_documents({"status": "DELAYED"})
        db_instance.performance_metrics.update_one(
            {"_id": "global_stats"},
            {"$set": {"total_delayed": delayed_count}}
        )

        # Auto-complete orders that have passed their ETA
        now = time.time()
        overdue = db_instance.deliveries.find({
            "status": "ASSIGNED",
            "dispatched_at": {"$exists": True},
            "eta_minutes": {"$exists": True}
        })
        for order in overdue:
            eta_secs = order["eta_minutes"] * 60
            if now >= order["dispatched_at"] + eta_secs:
                db_instance.deliveries.update_one(
                    {"order_id": order["order_id"]},
                    {"$set": {"status": "COMPLETED"}}
                )
                pathfinder.engine._log(f"[AUTO] Order {order['order_id']} marked COMPLETED (ETA elapsed).")

        await asyncio.sleep(2) # Tick the engine every 2 seconds

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine_running
    if mpi_pool.is_master():
        engine_running = True
        asyncio.create_task(function_loop())
    yield
    engine_running = False
    mpi_pool.stop_workers()

app.router.lifespan_context = lifespan


@app.get("/get-route")
def get_route(src: int, dst: int):
    """
    Computes and returns the route cost between two nodes in the system.
    Instead of calculating blindly, it submits the request to the Rule Engine.
    """
    if src < 0 or src >= pathfinder.num_nodes or dst < 0 or dst >= pathfinder.num_nodes:
        raise HTTPException(status_code=400, detail="Invalid node index")
    
    priority = "HIGH" if random.random() > 0.8 else "LOW"
    
    # Send through the Inference Engine
    pathfinder.engine.submit_order(src, dst, priority)
    pathfinder.engine.evaluate_rules()
    
    return abs(dst - src) * 1.5 + 10.0

@app.get("/update-traffic")
def update_traffic(multiplier: float = 3.0):
    """
    Applies new random traffic factors across the road network.
    """
    pathfinder.apply_traffic(multiplier)
    mpi_pool.sync_graph()
    return {"status": "success", "message": "Traffic updated and synced across MPI cluster"}

@app.get("/graph-data")
def graph_data():
    """
    Returns the graph structure for the Web UI layer visualization.
    """
    return pathfinder.get_graph_data()

@app.get("/bulk-orders")
def bulk_orders(count: int = 100):
    """
    Injects hundreds of new mock orders into the Live Engine instantly.
    """
    orders_to_insert = []
    base_time = int(time.time() * 1000)
    
    for i in range(count):
        src = random.randint(0, pathfinder.num_nodes - 1)
        dst = random.randint(0, pathfinder.num_nodes - 1)
        while dst == src:
            dst = random.randint(0, pathfinder.num_nodes - 1)
            
        priority = "HIGH" if random.random() > 0.8 else "LOW"
        orders_to_insert.append({
            "order_id": base_time + i,
            "src": src,
            "dst": dst,
            "priority": priority,
            "status": "PENDING",
            "assigned_vehicle": None
        })
        
    if orders_to_insert:
        db_instance.deliveries.insert_many(orders_to_insert)
        
    db_instance.performance_metrics.update_one(
        {"_id": "global_stats"},
        {"$inc": {"total_deliveries_injected": count}}
    )
        
    db_instance.events.insert_one({
        "message": f"[EVENT] {count} Bulk Orders Injected Automatically.",
        "timestamp": time.time(),
        "read": False
    })
    return {"status": "success", "orders_injected": count}

from pydantic import BaseModel

class OrderRequest(BaseModel):
    lat: float
    lon: float
    priority: str = "LOW"
    
class QuoteRequest(BaseModel):
    src_lat: float
    src_lon: float
    dst_lat: float
    dst_lon: float
    volume: int

class ConfirmDispatchRequest(BaseModel):
    src_node: int
    dst_node: int
    volume: int
    vehicle_id: int
    eta_minutes: float
    path_cost: float
    src_name: str = ""
    dst_name: str = ""

@app.post("/create-order")
def create_order(req: OrderRequest):
    """
    Live Custom Dispatcher API
    Snaps GPS coordinates to the physical street network.
    """
    dst_node = pathfinder.get_nearest_node(req.lat, req.lon)
    # Warehouse is centrally located (or node 0)
    src_node = 0 
    
    if src_node == dst_node:
        return {"status": "error", "message": "Destination too close to warehouse"}
        
    order_id = pathfinder.engine.submit_order(src_node, dst_node, req.priority)
    return {"status": "success", "order_id": order_id, "dst_node": dst_node}

@app.post("/api/quote-delivery")
def quote_delivery(req: QuoteRequest):
    import math

    def haversine_km(lat1, lon1, lat2, lon2):
        """Returns straight-line distance in km between two GPS points."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    def realistic_eta_minutes(src_lat, src_lon, dst_lat, dst_lon):
        """
        Compute ETA in minutes using haversine distance + real-world speed model.
        City (<30km): 30 km/h avg (traffic, signals)
        Regional (<150km): 60 km/h avg (state highways)
        Inter-city (>=150km): 80 km/h avg (national highway)
        Applies 1.35x road-factor (roads are never straight-line).
        """
        dist_km = haversine_km(src_lat, src_lon, dst_lat, dst_lon)
        road_dist_km = dist_km * 1.35  # Road factor

        if dist_km < 30:
            speed_kmh = 30.0   # City driving
        elif dist_km < 150:
            speed_kmh = 60.0   # State highway
        else:
            speed_kmh = 80.0   # National highway

        return (road_dist_km / speed_kmh) * 60.0  # → minutes

    # 1. Spatial Snapping (for graph routing visualization)
    src_node = pathfinder.get_nearest_node(req.src_lat, req.src_lon)
    dst_node = pathfinder.get_nearest_node(req.dst_lat, req.dst_lon)

    # 2. Real-world delivery ETA from actual coordinates
    delivery_eta = realistic_eta_minutes(req.src_lat, req.src_lon, req.dst_lat, req.dst_lon)

    # Real distance (for display as path_cost in km)
    delivery_dist_km = haversine_km(req.src_lat, req.src_lon, req.dst_lat, req.dst_lon) * 1.35

    # 3. Fleet Scan — find vehicle with enough capacity
    vehicles = list(db_instance.vehicles.find())
    candidate = None
    min_pickup_eta = float('inf')

    for v in vehicles:
        max_vol = v.get("max_volume", 100)
        curr_vol = v.get("current_volume", 0)

        if max_vol - curr_vol >= req.volume:
            # Pickup ETA: real-world distance from vehicle's current node to src
            v_node_data = pathfinder.graph.nodes.get(v["current_node"], {})
            v_lat = v_node_data.get("lat", req.src_lat)
            v_lon = v_node_data.get("lon", req.src_lon)
            pickup_eta = realistic_eta_minutes(v_lat, v_lon, req.src_lat, req.src_lon)

            if pickup_eta < min_pickup_eta:
                min_pickup_eta = pickup_eta
                candidate = v

    if candidate:
        total_eta = min_pickup_eta + delivery_eta
        return {
            "status": "success",
            "vehicle_id": candidate["vid"],
            "eta_minutes": round(total_eta, 1),
            "path_cost": round(delivery_dist_km, 1),   # Now in km (road distance)
            "distance_km": round(delivery_dist_km, 1),
            "src_node": src_node,
            "dst_node": dst_node
        }
    else:
        return {"status": "BUSY", "message": "WARNING: Global Fleet at Maximum Capacity. Estimated bottleneck 5-10 mins. Retry soon."}


@app.post("/api/confirm-dispatch")
def confirm_dispatch(req: ConfirmDispatchRequest):
    """
    Confirms the quote and explicitly dispatches to the pre-assigned vehicle.
    """
    order_id = int(time.time() * 1000)
    
    # Check if vehicle is still available
    v = db_instance.vehicles.find_one({"vid": req.vehicle_id})
    if not v or v.get("max_volume", 100) - v.get("current_volume", 0) < req.volume:
        return {"status": "error", "message": "Vehicle no longer has capacity"}

    # Insert delivery record
    db_instance.deliveries.insert_one({
        "order_id": order_id,
        "src": req.src_node,
        "dst": req.dst_node,
        "src_name": req.src_name or f"Node {req.src_node}",
        "dst_name": req.dst_name or f"Node {req.dst_node}",
        "priority": req.priority if hasattr(req, 'priority') else "HIGH",
        "status": "ASSIGNED",
        "assigned_vehicle": req.vehicle_id,
        "volume": req.volume,
        "dispatched_at": time.time(),
        "eta_minutes": req.eta_minutes
    })
    
    # Calculate route for UI visualization
    delivery_cost, route = pathfinder.compute_shortest_path(req.src_node, req.dst_node, record_ui=True, priority="HIGH")

    # Update vehicle strictly with new volume math
    # If the vehicle already had a route, in reality we'd append or merge ways.
    # For simplicity of the simulation update, we overwrite its active properties
    # but increment current_volume.
    db_instance.vehicles.update_one(
        {"vid": req.vehicle_id},
        {"$inc": {"current_volume": req.volume},
         "$set": {
            "capacity_available": False, # Setting to False triggers the engine's movement loop
            "active_order_id": order_id,
            "active_order_dst": req.dst_node,
            "eta_minutes": req.eta_minutes,
            "expected_cost": req.path_cost,
            "route": route,
            "current_leg": 0,
            "route_progress": 0.0
         }}
    )
    
    pathfinder.engine._log(f"[QUOTE DISPATCH] Order {order_id} explicitly assigned to Vehicle {req.vehicle_id}. Vol: {req.volume}, ETA: {req.eta_minutes:.1f}m")
    
    return {"status": "success", "order_id": order_id, "vehicle_id": req.vehicle_id}

@app.get("/orders")
def get_orders():
    """
    Fetch the most recent 50 delivery orders directly from the Active Record DB.
    """
    orders_cursor = db_instance.deliveries.find().sort("order_id", -1).limit(50)
    data = []
    for doc in orders_cursor:
        doc.pop('_id', None)
        data.append(doc)
    return {"orders": data}

VALID_STATUSES = {"PENDING", "ASSIGNED", "COMPLETED", "FAILED", "DELAYED"}

class StatusUpdateRequest(BaseModel):
    status: str

@app.patch("/api/orders/{order_id}/status")
def update_order_status(order_id: int, req: StatusUpdateRequest):
    """
    Manually override the status of any delivery order.
    """
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    result = db_instance.deliveries.update_one(
        {"order_id": order_id},
        {"$set": {"status": req.status}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")

    pathfinder.engine._log(f"[MANUAL] Order {order_id} status → {req.status}")
    return {"status": "success", "order_id": order_id, "new_status": req.status}

@app.get("/engine-state")
def get_engine_state():
    """
    Returns the real-time aggregated metrics and the most recent rule engine logs for UI display.
    """
    pending = db_instance.deliveries.count_documents({"status": "PENDING"})
    assigned_count = db_instance.vehicles.count_documents({"capacity_available": False})
    
    stats = db_instance.performance_metrics.find_one({"_id": "global_stats"})
    if not stats: 
        stats = {"total_deliveries_injected": 0, "total_delayed": 0, "fuel_used": 0.0}
        
    completed_deliveries = stats["total_deliveries_injected"] - pending - assigned_count
    
    # Extract unread logs
    logs_cursor = db_instance.events.find({"read": False}).sort("timestamp", 1)
    logs = [log["message"] for log in logs_cursor]
    
    # Mark them as read
    db_instance.events.update_many({"read": False}, {"$set": {"read": True}})
    
    return {
        "pending_orders": pending,
        "active_vehicles": assigned_count,
        "completed_deliveries": max(0, completed_deliveries),
        "delayed_tasks": stats.get("total_delayed", 0),
        "total_fuel": stats.get("fuel_used", 0.0),
        "last_parallel_time": stats.get("last_parallel_time", 0.0),
        "last_seq_time": stats.get("last_seq_time", 0.0),
        "recent_logs": logs
    }

@app.get("/active-deliveries")
def get_active_deliveries(clear: bool = False):
    """
    Returns the routing history of active deliveries requested by workers.
    Pass ?clear=true to flush the queue from memory after reading.
    """
    routes_cursor = db_instance.routes.find({"read": False})
    
    deliveries = []
    for doc in routes_cursor:
        doc.pop('_id', None)
        deliveries.append(doc)
        
    if clear and deliveries:
        db_instance.routes.update_many({"read": False}, {"$set": {"read": True}})
        
    return {"deliveries": deliveries}

@app.get("/vehicles")
def get_vehicles():
    """
    Returns the full live fleet status for the sidebar Fleet Status Hub.
    """
    vehicles_cursor = db_instance.vehicles.find()
    data = []
    for doc in vehicles_cursor:
        doc.pop('_id', None)
        data.append(doc)
    return {"vehicles": data}


if __name__ == "__main__":
    if mpi_pool.is_master():
        print(f"Starting API Server on Master Node (Rank 0). Total pool size: {mpi_pool.size}")
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    else:
        mpi_pool.worker_loop()
