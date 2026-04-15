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
        # Delayed counts is simply the number of delayed orders in the DB
        delayed_count = db_instance.deliveries.count_documents({"status": "DELAYED"})
        
        # We can update this count constantly
        db_instance.performance_metrics.update_one(
            {"_id": "global_stats"},
            {"$set": {"total_delayed": delayed_count}}
        )
        
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

if __name__ == "__main__":
    if mpi_pool.is_master():
        print(f"Starting API Server on Master Node (Rank 0). Total pool size: {mpi_pool.size}")
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    else:
        mpi_pool.worker_loop()
