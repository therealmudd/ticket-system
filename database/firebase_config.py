# firebase_config.py
import firebase_admin
from firebase_admin import credentials, firestore

# Path to your service account key JSON file
cred = credentials.Certificate("database/credentials.json")
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()
