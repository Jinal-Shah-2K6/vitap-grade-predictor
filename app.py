from flask import Flask, render_template, request, redirect, url_for, session
import json, os, statistics, hashlib

app = Flask(__name__)
app.secret_key = "vitap_grade_secret_2024"

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE_DIR, "database", "data.json")
USERS_FILE = os.path.join(BASE_DIR, "database", "users.json")

for folder in [os.path.join(BASE_DIR, "database")]:
    if not os.path.exists(folder):
        os.makedirs(folder)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump([], f)


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def compute_grade(marks, mean_marks, sd):
    s_boundary = max(mean_marks + 1.5 * sd, 80)   # S never starts below 80
    a_boundary = mean_marks + 0.5 * sd
    b_boundary = mean_marks - 0.5 * sd
    c_boundary = mean_marks - 1.0 * sd
    d_boundary = mean_marks - 1.5 * sd
    e_boundary = min(mean_marks - 2.0 * sd, 50)   # F never starts above 50

    if marks >= s_boundary:    grade = "S"
    elif marks >= a_boundary:  grade = "A"
    elif marks >= b_boundary:  grade = "B"
    elif marks >= c_boundary:  grade = "C"
    elif marks >= d_boundary:  grade = "D"
    elif marks >= e_boundary:  grade = "E"
    else:                      grade = "F"

    return grade, round(s_boundary,2), round(a_boundary,2), round(b_boundary,2), \
           round(c_boundary,2), round(d_boundary,2), round(e_boundary,2)


GRADE_POINTS = {"S": 10, "A": 9, "B": 8, "C": 7, "D": 6, "E": 5, "F": 0}


# ── AUTH ──────────────────────────────────────────────

@app.route("/", methods=["GET","POST"])
def login():
    if "student_id" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        reg   = request.form["reg"].strip().upper()
        pw    = request.form["password"]
        users = load_json(USERS_FILE)
        user  = next((u for u in users if u["student_id"] == reg), None)

        if not user:
            error = "No account found. Please register first."
        elif user["password"] != hash_password(pw):
            error = "Incorrect password."
        else:
            session["student_id"] = reg
            return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET","POST"])
def register():
    error = None
    if request.method == "POST":
        reg   = request.form["reg"].strip().upper()
        email = request.form["email"].strip().lower()
        pw    = request.form["password"]
        users = load_json(USERS_FILE)

        if any(u["student_id"] == reg for u in users):
            error = "Registration number already exists."
        else:
            users.append({
                "student_id": reg,
                "email":      email,
                "password":   hash_password(pw)
            })
            save_json(USERS_FILE, users)
            session["student_id"] = reg
            return redirect(url_for("dashboard"))

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── DASHBOARD ─────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if "student_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", student_id=session["student_id"])


# ── ADD MARKS ─────────────────────────────────────────

@app.route("/add", methods=["GET","POST"])
def add():
    if "student_id" not in session:
        return redirect(url_for("login"))

    result = None
    if request.method == "POST":
        student_id = session["student_id"]
        faculty_id = request.form["faculty_id"].strip()
        subject    = request.form["subject"].strip()
        marks      = float(request.form["marks"])

        data = load_json(DATA_FILE)

        updated = False
        for entry in data:
            if entry.get("student_id") == student_id and entry["subject"] == subject:
                entry["marks"]      = marks
                entry["faculty_id"] = faculty_id
                updated = True
                break

        if not updated:
            data.append({
                "student_id": student_id,
                "faculty_id": faculty_id,
                "subject":    subject,
                "marks":      marks
            })

        save_json(DATA_FILE, data)

        subject_marks = [
            e["marks"] for e in data
            if e["faculty_id"] == faculty_id and e["subject"] == subject
        ]

        submissions = len(subject_marks)
        mean_marks  = round(statistics.mean(subject_marks), 2)
        sd          = round(statistics.stdev(subject_marks), 2) if submissions > 1 else 0

        grade, s_b, a_b, b_b, c_b, d_b, e_b = compute_grade(marks, mean_marks, sd)

        result = dict(
            faculty_id=faculty_id, subject=subject, marks=marks,
            submissions=submissions, mean=mean_marks, sd=sd,
            grade=grade, s_b=s_b, a_b=a_b, b_b=b_b,
            c_b=c_b, d_b=d_b, e_b=e_b
        )

    return render_template("add.html", student_id=session["student_id"], result=result)


# ── MY GRADES ─────────────────────────────────────────

@app.route("/grades")
def grades():
    if "student_id" not in session:
        return redirect(url_for("login"))

    student_id = session["student_id"]
    data       = load_json(DATA_FILE)

    student_entries = [e for e in data if e.get("student_id") == student_id]
    submissions = []

    for entry in student_entries:
        subject_marks = [
            e["marks"] for e in data
            if e["faculty_id"] == entry["faculty_id"] and e["subject"] == entry["subject"]
        ]
        mean_marks = round(statistics.mean(subject_marks), 2)
        sd = round(statistics.stdev(subject_marks), 2) if len(subject_marks) > 1 else 0
        grade, s_b, a_b, b_b, c_b, d_b, e_b = compute_grade(entry["marks"], mean_marks, sd)

        submissions.append({
            "subject":    entry["subject"],
            "faculty_id": entry["faculty_id"],
            "marks":      entry["marks"],
            "grade":      grade,
            "mean":       mean_marks,
            "sd":         sd,
            "count":      len(subject_marks),
            "s_b": s_b, "a_b": a_b, "b_b": b_b,
            "c_b": c_b, "d_b": d_b, "e_b": e_b
        })

    return render_template("grades.html",
        student_id=student_id, submissions=submissions)


# ── CGPA ──────────────────────────────────────────────

@app.route("/cgpa")
def cgpa():
    if "student_id" not in session:
        return redirect(url_for("login"))

    student_id = session["student_id"]
    data       = load_json(DATA_FILE)

    student_entries = [e for e in data if e.get("student_id") == student_id]
    subjects = []

    for entry in student_entries:
        subject_marks = [
            e["marks"] for e in data
            if e["faculty_id"] == entry["faculty_id"] and e["subject"] == entry["subject"]
        ]
        mean_marks = round(statistics.mean(subject_marks), 2)
        sd = round(statistics.stdev(subject_marks), 2) if len(subject_marks) > 1 else 0
        grade, *_ = compute_grade(entry["marks"], mean_marks, sd)

        subjects.append({
            "subject": entry["subject"],
            "grade":   grade,
            "points":  GRADE_POINTS[grade]
        })

    return render_template("cgpa.html",
        student_id=student_id, subjects=subjects)


# ── LEADERBOARD ───────────────────────────────────────

@app.route("/leaderboard")
def leaderboard():
    if "student_id" not in session:
        return redirect(url_for("login"))

    data = load_json(DATA_FILE)

    student_scores = {}
    for entry in data:
        sid = entry.get("student_id")
        if not sid:
            continue

        subject_marks = [
            e["marks"] for e in data
            if e["faculty_id"] == entry["faculty_id"] and e["subject"] == entry["subject"]
        ]
        mean_marks = round(statistics.mean(subject_marks), 2)
        sd = round(statistics.stdev(subject_marks), 2) if len(subject_marks) > 1 else 0
        grade, *_ = compute_grade(entry["marks"], mean_marks, sd)

        if sid not in student_scores:
            student_scores[sid] = {"points": [], "student_id": sid}
        student_scores[sid]["points"].append(GRADE_POINTS[grade])

    leaderboard_data = []
    for sid, val in student_scores.items():
        avg = round(sum(val["points"]) / len(val["points"]), 2)
        leaderboard_data.append({
            "student_id":  sid,
            "avg_points":  avg,
            "subjects":    len(val["points"]),
            "is_me":       sid == session["student_id"]
        })

    leaderboard_data.sort(key=lambda x: x["avg_points"], reverse=True)

    for i, entry in enumerate(leaderboard_data):
        entry["rank"] = i + 1
        entry["display"] = (entry["student_id"] + " (You)") if entry["is_me"] else f"Student #{i+1}"

    return render_template("leaderboard.html",
        student_id=session["student_id"],
        leaderboard=leaderboard_data)


if __name__ == "__main__":
    app.run(debug=True)