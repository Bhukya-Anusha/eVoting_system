from flask import Flask, request, jsonify, send_from_directory
import os, base64
import numpy as np
import pandas as pd
import cv2
import face_recognition
from collections import defaultdict

# Serve frontend from ../frontend
app = Flask(__name__, static_folder="../frontend", static_url_path="")

# --- FILE PATHS ---
BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "voters.csv")   # voters file
ADMINS_CSV = os.path.join(BASE_DIR, "admins.csv") # admins file
IMAGES_DIR = os.path.join(BASE_DIR, "images")

# --- VOTERS CSV ---
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"Missing {CSV_PATH}. Create voters.csv")

voters_df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
voters_df["aadhar"] = voters_df["aadhar"].astype(str)

# --- PRELOAD VOTER FACE ENCODINGS ---
known_by_aadhar = {}  # aadhar -> details
for _, row in voters_df.iterrows():
    img_path = os.path.join(IMAGES_DIR, row["image"])
    if not os.path.exists(img_path):
        print(f"[WARN] Missing image for {row['name']} at {img_path}")
        continue
    img = face_recognition.load_image_file(img_path)
    encs = face_recognition.face_encodings(img)
    if encs:
        known_by_aadhar[row["aadhar"]] = {
            "name": row["name"],
            "image": row["image"],
            "encoding": encs[0]
        }
    else:
        print(f"[WARN] No face found in {row['name']} ({img_path})")

# --- VOTE STORE ---
vote_tally = defaultdict(int)
already_voted = set()

# --- PARTIES ---
TELANGANA_PARTIES = [
    {"name": "BRS", "logo": "🚗 Car"},
    {"name": "INC", "logo": "✋ Hand"},
    {"name": "BJP", "logo": "🌸 Lotus"},
    {"name": "AIMIM", "logo": "🪁 Kite"},
    {"name": "BSP", "logo": "🐘 Elephant"},
    {"name": "CPI(M)", "logo": "☭ Hammer & Sickle"}
]

# --- FRONTEND ---
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

# --- API ROUTES ---

@app.route("/api/parties", methods=["GET"])
def get_parties():
    return jsonify(TELANGANA_PARTIES)

@app.route("/api/login-user", methods=["POST"])
def login_user():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    aadhar = str(data.get("aadhar") or "").strip()
    if not name or not aadhar:
        return jsonify({"success": False, "message": "Name and Aadhaar are required"})
    row = voters_df[(voters_df["name"] == name) & (voters_df["aadhar"] == aadhar)]
    if row.empty:
        return jsonify({"success": False, "message": "Not found in voter list"})
    return jsonify({"success": True})

@app.route("/api/verify-and-vote", methods=["POST"])
def verify_and_vote():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    aadhar = str(data.get("aadhar") or "").strip()
    party = (data.get("party") or "").strip()
    data_url = data.get("image")

    if not (name and aadhar and party and data_url):
        return jsonify({"success": False, "message": "Missing required fields"})

    row = voters_df[(voters_df["name"] == name) & (voters_df["aadhar"] == aadhar)]
    if row.empty:
        return jsonify({"success": False, "message": "Voter not found in CSV"})

    if aadhar in already_voted:
        return jsonify({"success": False, "message": "Vote already cast for this Aadhaar"})

    try:
        header, b64 = data_url.split(",", 1)
        img_bytes = base64.b64decode(b64)
        np_img = np.frombuffer(img_bytes, np.uint8)
        bgr = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if bgr is None:
            return jsonify({"success": False, "message": "Invalid image data"})
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image decode error: {e}"})

    captured_encs = face_recognition.face_encodings(rgb)
    if not captured_encs:
        return jsonify({"success": False, "message": "No face detected in captured image"})
    captured_enc = captured_encs[0]

    kb = known_by_aadhar.get(aadhar)
    if not kb or kb.get("encoding") is None:
        return jsonify({"success": False, "message": "No stored face for this Aadhaar"})

    match = face_recognition.compare_faces([kb["encoding"]], captured_enc, tolerance=0.5)[0]
    if not match:
        return jsonify({"success": False, "message": "Face does not match registered photo"})

    vote_tally[party] += 1
    already_voted.add(aadhar)
    return jsonify({"success": True, "message": f"✅ Vote cast for {party}", "tally": dict(vote_tally)})

# --- ADMIN ROUTES ---
# @app.route("/api/admin/login", methods=["POST"])
# def admin_login():
#     data = request.get_json(force=True)
#     email = (data.get("email") or "").strip()
#     password = (data.get("password") or "").strip()

#     if not os.path.exists(ADMINS_CSV):
#         return jsonify({"success": False, "message": "Admins file not found"})

#     admins_df = pd.read_csv(ADMINS_CSV, dtype=str).fillna("")
#     row = admins_df[(admins_df["email"] == email) & (admins_df["password"] == password)]

#     if row.empty:
#         return jsonify({"success": False, "message": "Invalid credentials"})
#     return jsonify({"success": True, "name": row.iloc[0]["name"]})

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    print("🔐 Admin login attempt:")
    print("   Email:", email)
    print("   Password:", password)

    if not os.path.exists(ADMINS_CSV):
        print("❌ Admin CSV not found at", ADMINS_CSV)
        return jsonify({"success": False, "message": "Admins file not found"})

    admins_df = pd.read_csv(ADMINS_CSV, dtype=str).fillna("")
    print("📄 Admins DataFrame:\n", admins_df)

    row = admins_df[(admins_df["email"] == email) & (admins_df["password"] == password)]
    print("🔍 Matching row:", row)

    if row.empty:
        return jsonify({"success": False, "message": "Invalid credentials"})
    
    return jsonify({"success": True, "name": row.iloc[0]["name"]})


@app.route("/api/admin/summary", methods=["GET"])
def admin_summary():
    return jsonify({
        "previous": [
            {"year": 2018, "winner": "TRS/BRS"},
            {"year": 2014, "winner": "TRS/BRS"}
        ],
        "upcoming": [
            {"year": 2028, "type": "Assembly Elections"}
        ],
        "live": dict(vote_tally)
    })

if __name__ == "__main__":
    # Run server
    app.run(host="0.0.0.0", port=5000, debug=True)



import os
import pandas as pd
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
ADMINS_CSV = os.path.join(BASE_DIR, "backend/admins.csv")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# ---------- Serve Frontend ----------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "admin_login.html")

# ---------- API: Admin Login ----------
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not os.path.exists(ADMINS_CSV):
        return jsonify({"success": False, "message": "Admin CSV file not found"}), 500

    admins_df = pd.read_csv(ADMINS_CSV, dtype=str).fillna("")
    row = admins_df[(admins_df["email"] == email) & (admins_df["password"] == password)]

    if row.empty:
        return jsonify({"success": False, "message": "Invalid credentials"})
    else:
        return jsonify({"success": True, "name": row.iloc[0]["name"]})

# ---------- API: Election Summary (Mock) ----------
@app.route("/api/admin/summary", methods=["GET"])
def admin_summary():
    data = {
        "live": {"Party A": 1240, "Party B": 980, "Party C": 450},
        "upcoming": [
            {"type": "State Election", "year": 2026, "date": "2026-05-12"},
            {"type": "Local Body", "year": 2025, "date": "2025-11-10"}
        ],
        "previous": [
            {"year": 2021, "winner": "Party A"},
            {"year": 2016, "winner": "Party B"}
        ]
    }
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
    
   