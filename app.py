from flask import Flask, render_template, request, jsonify, Response, session, send_from_directory
from datetime import datetime
from dotenv import load_dotenv
import csv
import io
import os
import shutil
import sqlite3

import database
import face_utils

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-dev-key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
database.init_db()


def is_admin():
    return session.get("is_admin", False)


# ---------- PAGES ----------

@app.route("/")
def dashboard():
    stats = database.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats)


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/attendance")
def attendance_page():
    return render_template("attendance.html")


@app.route("/records")
def records_page():
    users = database.get_all_users()
    return render_template("records.html", users=users)


# ---------- ADMIN ----------

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if data.get("password") == ADMIN_PASSWORD:
        session["is_admin"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "That password isn't correct. Please try again."}), 401


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return jsonify({"success": True})


@app.route("/admin/status")
def admin_status():
    return jsonify({"is_admin": is_admin()})


@app.route("/api/clear_all", methods=["POST"])
def api_clear_all():
    if not is_admin():
        return jsonify({"success": False, "message": "Please log in as admin first to do this."}), 403

    database.clear_all()
    if os.path.exists(face_utils.DATASET_DIR):
        shutil.rmtree(face_utils.DATASET_DIR)
        os.makedirs(face_utils.DATASET_DIR, exist_ok=True)
    if os.path.exists(face_utils.TRAINER_PATH):
        os.remove(face_utils.TRAINER_PATH)
    face_utils.reload_recognizer()
    return jsonify({"success": True})


# ---------- API: REGISTRATION ----------

@app.route("/api/check_duplicate_face", methods=["POST"])
def api_check_duplicate_face():
    data = request.get_json()
    image_data = data.get("image")
    if not image_data:
        return jsonify({"success": False, "message": "No image received."}), 400

    img = face_utils.decode_base64_image(image_data)
    face, box = face_utils.detect_largest_face(img)

    if face is None:
        return jsonify({"success": True, "face_found": False})

    user_id, confidence = face_utils.recognize_face(face, threshold=50)

    if user_id is None:
        return jsonify({"success": True, "face_found": True, "duplicate": False})

    user = database.get_user(user_id)
    return jsonify({"success": True, "face_found": True, "duplicate": True, "user": user})


@app.route("/api/register_user", methods=["POST"])
def api_register_user():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    reg_no = (data.get("reg_no") or "").strip()
    department = (data.get("department") or "").strip()

    if not name or not reg_no:
        return jsonify({"success": False, "message": "Please fill in both the name and ID before continuing."}), 400

    try:
        user_id = database.add_user(name, reg_no, department)
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": f'ID "{reg_no}" is already taken. Try a different one.'}), 400
    except Exception as e:
        print("REGISTRATION ERROR:", e)
        return jsonify({"success": False, "message": "We couldn't save that right now. Please try again in a moment."}), 500

    return jsonify({"success": True, "user_id": user_id})


@app.route("/api/capture_face", methods=["POST"])
def api_capture_face():
    data = request.get_json()
    user_id = data.get("user_id")
    index = data.get("index", 0)
    image_data = data.get("image")

    if not user_id or not image_data:
        return jsonify({"success": False, "message": "Something's missing. Please refresh and try again."}), 400

    img = face_utils.decode_base64_image(image_data)
    face, box = face_utils.detect_largest_face(img)

    if face is None:
        return jsonify({"success": False, "message": "We couldn't see your face clearly. Move closer to the camera or improve lighting."})

    face_utils.save_face_sample(user_id, face, index)

    return jsonify({"success": True, "box": box})


@app.route("/api/train_model", methods=["POST"])
def api_train_model():
    people, samples = face_utils.train_model()
    face_utils.reload_recognizer()
    return jsonify({"success": True, "people": people, "samples": samples})


@app.route("/api/users", methods=["GET"])
def api_get_users():
    return jsonify(database.get_all_users())


@app.route("/api/user_photo/<int:user_id>")
def api_user_photo(user_id):
    path = os.path.join("static", "dataset", str(user_id))
    if os.path.exists(os.path.join(path, "reference.jpg")):
        return send_from_directory(path, "reference.jpg")
    return "", 404


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    if not is_admin():
        return jsonify({"success": False, "message": "Please log in as admin first to do this."}), 403

    database.delete_user(user_id)

    user_dataset_dir = os.path.join("static", "dataset", str(user_id))
    if os.path.exists(user_dataset_dir):
        shutil.rmtree(user_dataset_dir)

    face_utils.train_model()
    face_utils.reload_recognizer()
    return jsonify({"success": True})


# ---------- API: LIVE ATTENDANCE ----------

@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    data = request.get_json()
    image_data = data.get("image")
    if not image_data:
        return jsonify({"success": False, "message": "No image received."}), 400

    img = face_utils.decode_base64_image(image_data)
    face, box = face_utils.detect_largest_face(img)

    if face is None:
        return jsonify({"success": True, "face_found": False})

    user_id, confidence = face_utils.recognize_face(face)

    if user_id is None:
        return jsonify({
            "success": True,
            "face_found": True,
            "box": box,
            "recognized": False,
            "confidence": confidence,
        })

    user = database.get_user(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    already_marked = database.has_marked_today(user_id, today)
    status = "already_marked"
    if not already_marked:
        database.mark_attendance(user_id, today, now_time, confidence)
        status = "marked"

    return jsonify({
        "success": True,
        "face_found": True,
        "box": box,
        "recognized": True,
        "user": user,
        "status": status,
        "confidence": confidence,
        "time": now_time,
    })


# ---------- API: RECORDS ----------

@app.route("/api/records", methods=["GET"])
def api_records():
    date_filter = request.args.get("date")
    search = request.args.get("search")
    records = database.get_records(date_filter=date_filter, search=search)
    return jsonify(records)


@app.route("/api/export")
def api_export():
    if not is_admin():
        return jsonify({"success": False, "message": "Please log in as admin first to do this."}), 403

    date_filter = request.args.get("date")
    search = request.args.get("search")
    records = database.get_records(date_filter=date_filter, search=search)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "ID", "Department", "Date", "Time", "Confidence"])
    for r in records:
        writer.writerow([r["name"], r["reg_no"], r["department"], r["date"], r["time"], r["confidence"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=attendance_records.csv"},
    )


@app.route("/api/stats")
def api_stats():
    return jsonify(database.get_dashboard_stats())


if __name__ == "__main__":
    app.run(debug=True)