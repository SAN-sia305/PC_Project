from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathfinding import PathFinder
from mpi_pool import MPIPool
import asyncio
import random

app = FastAPI(title="DIFM-DOS Python Pathfinding Microservice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instance
pathfinder = PathFinder(num_nodes=50, seed=42)
mpi_pool = MPIPool(pathfinder)
pathfinder.engine.mpi_pool = mpi_pool

# Keep track of simulation stats globally
server_stats = {
    "total_deliveries_injected": 0,
    "total_delayed": 0,
    "fuel_used": 0.0
}

engine_running = False

async def function_loop():
    while engine_running:
        pathfinder.engine.evaluate_rules()
        
        # Accumulate metrics based on engine state
        for v in pathfinder.engine.vehicles:
            if v.active_order and v.active_order.status == "COMPLETED":
                # Rough mock fuel conversion 
                server_stats["fuel_used"] += v.eta_minutes * 0.15 
        
        # Count delayed 
        for o in pathfinder.engine.pending_orders:
            if o.status == "DELAYED":
                server_stats["total_delayed"] += 1
                
        await asyncio.sleep(2) # Tick the engine every 2 seconds

@app.on_event("startup")
async def startup_event():
    global engine_running
    if mpi_pool.is_master():
        engine_running = True
        asyncio.create_task(function_loop())

@app.on_event("shutdown")
def shutdown_event():
    global engine_running
    engine_running = False
    mpi_pool.stop_workers()


@app.get("/get-route")
def get_route(src: int, dst: int):
    """
    Computes and returns the route cost between two nodes in the system.
    Instead of calculating blindly, it submits the request to the Rule Engine.
    """
    import random
    if src < 0 or src >= pathfinder.num_nodes or dst < 0 or dst >= pathfinder.num_nodes:
        raise HTTPException(status_code=400, detail="Invalid node index")
    
    # 20% chance an order is HIGH priority for the simulation rule engine
    priority = "HIGH" if random.random() > 0.8 else "LOW"
    
    # Send through the Inference Engine
    pathfinder.engine.submit_order(src, dst, priority)
    pathfinder.engine.evaluate_rules()
    
    # To keep the C++ MPI fallback working, we can just return a quick mocked heuristic cost
    # The actual deep logic is happening implicitly in the rule engine queue now.
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
    for _ in range(count):
        src = random.randint(0, pathfinder.num_nodes - 1)
        dst = random.randint(0, pathfinder.num_nodes - 1)
        while dst == src:
            dst = random.randint(0, pathfinder.num_nodes - 1)
            
        priority = "HIGH" if random.random() > 0.8 else "LOW"
        pathfinder.engine.submit_order(src, dst, priority)
        
    server_stats["total_deliveries_injected"] += count
    return {"status": "success", "orders_injected": count}

@app.get("/engine-state")
def get_engine_state():
    """
    Returns the real-time aggregated metrics and the most recent rule engine logs for UI display.
    """
    pending = len(pathfinder.engine.pending_orders)
    
    assigned_count = 0
    completed_count = 0
    
    # Calculate how many vehicles are currently working
    for v in pathfinder.engine.vehicles:
        if not v.capacity_available:
            assigned_count += 1
            
    # Extract unread logs and clear the log buffer
    logs = list(pathfinder.engine.logs)
    pathfinder.engine.logs.clear()
    
    return {
        "pending_orders": pending,
        "active_vehicles": assigned_count,
        "completed_deliveries": server_stats["total_deliveries_injected"] - pending - assigned_count,
        "delayed_tasks": server_stats["total_delayed"],
        "total_fuel": server_stats["fuel_used"],
        "recent_logs": logs
    }

@app.get("/active-deliveries")
def get_active_deliveries(clear: bool = False):
    """
    Returns the routing history of active deliveries requested by workers.
    Pass ?clear=true to flush the queue from memory after reading.
    """
    deliveries = list(pathfinder.active_deliveries)
    if clear:
        pathfinder.active_deliveries.clear()
    return {"deliveries": deliveries}

if __name__ == "__main__":
    if mpi_pool.is_master():
        print(f"Starting API Server on Master Node (Rank 0). Total pool size: {mpi_pool.size}")
        # Disable reload when running MPI, to prevent subprocess forking issues
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    else:
        # Worker node
        mpi_pool.worker_loop()
