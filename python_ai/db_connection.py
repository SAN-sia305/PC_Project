import os
from pymongo import MongoClient

# Fetch MongoDB URI from environment variable or use default local instance
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("MONGO_DB_NAME", "difm_dos_tn")

class Database:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DATABASE_NAME]
        
        # Initialize references to the 7 collections
        self.deliveries = self.db["deliveries"]
        self.vehicles = self.db["vehicles"]
        self.traffic_conditions = self.db["traffic_conditions"]
        self.routes = self.db["routes"]
        self.simulation_runs = self.db["simulation_runs"]
        self.performance_metrics = self.db["performance_metrics"]
        self.events = self.db["events"]

    def ping(self):
        """Test the database connection."""
        try:
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB!")
            return True
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            return False

# Create a singleton instance to be imported across the application
db_instance = Database()
