from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import httpx
import asyncio

app = FastAPI(title="DIFM-DOS Web Interface Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Host Web Directory
app.mount("/static", StaticFiles(directory="web_ui"), name="static")

@app.get("/run-simulation")
async def run_simulation():
    """
    Kicks off the MPI job / Sequential script. 
    Here we mock the C++ pipeline execution assuming it drops a results CSV.
    """
    # Assuming the C++ output yields data in an agreed upon time/format
    # MOCK DATA for prototype validation visualization
    import random
    mock_metrics = {
        "metrics": {
            "parallel_time": random.uniform(2.5, 4.0),
            "sequential_time": random.uniform(8.0, 12.0),
            "speedup": random.uniform(2.0, 3.5),
            "efficiency": random.uniform(0.6, 0.9),
            "total_deliveries": 100,
            "delayed": random.randint(5, 15),
            "fuel_used": random.uniform(1000.0, 1500.0)
        }
    }
    return mock_metrics

@app.get("/graph-status")
async def fetch_graph_status():
    """
    Reverse proxy to Python AI Microservice to get graph data
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/graph-data")
            return resp.json()
    except Exception:
        return {"nodes": [], "links": []}

if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8080, reload=True)
