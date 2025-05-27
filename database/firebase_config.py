import os
import base64
import tempfile
import firebase_admin
from firebase_admin import credentials, firestore

# Get the base64-encoded Firebase credentials from environment variable
firebase_b64 = os.environ.get("FIREBASE_CREDENTIALS_B64")

if not firebase_b64:
    raise ValueError("FIREBASE_CREDENTIALS_B64 environment variable not set.")

# Decode and write to a temporary JSON file
with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as temp_json:
    json_str = base64.b64decode(firebase_b64).decode("utf-8")
    temp_json.write(json_str)
    temp_json_path = temp_json.name

# Initialize Firebase Admin SDK
cred = credentials.Certificate(temp_json_path)
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()
