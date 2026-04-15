import pymongo
from pymongo import MongoClient

# Provide the MongoDB Atlas connection string
uri = "mongodb+srv://difmdos01:1231234@cluster0.sadmk.mongodb.net/difm_dos"

try:
    # Create a new client and connect to the server
    client = MongoClient(uri)
    
    # Send a ping to confirm a successful connection
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
    
    # Access the specific database
    db = client.get_database("difm_dos")
    print(f"Successfully accessed database: {db.name}")
    
except Exception as e:
    print(f"An error occurred while connecting to MongoDB:")
    print(e)
