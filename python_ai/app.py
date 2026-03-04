from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathfinding import PathFinder

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

@app.get("/get-route")
def get_route(src: int, dst: int):
    """
    Computes and returns the route cost between two nodes in the system.
    """
    if src < 0 or src >= pathfinder.num_nodes or dst < 0 or dst >= pathfinder.num_nodes:
        raise HTTPException(status_code=400, detail="Invalid node index")
    
    cost, route = pathfinder.compute_shortest_path(src, dst)
    
    if cost == float('inf'):
        raise HTTPException(status_code=404, detail="No path found")
        
    return cost # Return pure number for C++ ease of parsing prototype

@app.get("/update-traffic")
def update_traffic(multiplier: float = 3.0):
    """
    Applies new random traffic factors across the road network.
    """
    pathfinder.apply_traffic(multiplier)
    return {"status": "success", "message": "Traffic updated"}

@app.get("/graph-data")
def graph_data():
    """
    Returns the graph structure for the Web UI layer visualization.
    """
    return pathfinder.get_graph_data()

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.1", port=8000, reload=True)
