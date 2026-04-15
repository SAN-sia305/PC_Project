from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import httpx
import asyncio
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

app = FastAPI(title="DIFM-DOS Web Interface Backend")

# --- Database Setup ---
MONGO_URI = os.getenv("MONGO_URI", "")
mongodb_client = None
db = None

if MONGO_URI:
    try:
        # Wait up to 5 seconds for a connection
        mongodb_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongodb_client.admin.command("ping")
        db = mongodb_client["pc_project_db"]
        print("✅ Successfully connected to MongoDB Atlas!")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
else:
    print("⚠️ WARNING: MONGO_URI not found in .env file.")
# ----------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/run-simulation")
async def run_simulation(deliveries: int = 100):
    """
    Submits a large burst of mock orders into the Live Engine.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:8000/bulk-orders?count={deliveries}")
            return resp.json()
    except Exception as e:
        print(f"Failed to submit orders: {e}")
        return {"status": "error"}

@app.get("/system-stats")
async def fetch_system_stats():
    """
    Proxy to the live Python AI Engine's real-time state.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/engine-state")
            data = resp.json()
            
            # Format to match the UI's expected 'metrics' envelope
            return {
                "metrics": {
                    "pending_orders": data.get("pending_orders", 0),
                    "active_vehicles": data.get("active_vehicles", 0),
                    "completed_deliveries": data.get("completed_deliveries", 0),
                    "delayed": data.get("delayed_tasks", 0),
                    "fuel_used": data.get("total_fuel", 0.0),
                    "parallel_time": data.get("last_parallel_time", 0.0),
                    "seq_time": data.get("last_seq_time", 0.0),
                    "recent_logs": data.get("recent_logs", [])
                }
            }
    except Exception as e:
        return {"metrics": {"pending_orders": 0, "active_vehicles": 0, "completed_deliveries": 0, "delayed": 0, "fuel_used": 0.0, "parallel_time": 0.0, "seq_time": 0.0, "recent_logs": []}}


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

@app.get("/active-deliveries")
async def fetch_active_deliveries():
    """
    Reverse proxy to get and clear the active delivery paths from the Python Pathfinding service.
    """
    try:
        async with httpx.AsyncClient() as client:
            # We clear the queue so the UI only gets fresh animations
            resp = await client.get("http://127.0.0.1:8000/active-deliveries?clear=true")
            return resp.json()
    except Exception:
        return {"deliveries": []}

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Map the root URL to serve static files from the web_ui directory
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="web_ui")

if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8090, reload=True)
