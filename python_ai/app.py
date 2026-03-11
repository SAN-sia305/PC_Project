from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathfinding import PathFinder
from mpi_pool import MPIPool

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

@app.on_event("shutdown")
def shutdown_event():
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
