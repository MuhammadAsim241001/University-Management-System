import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
# Set CAMPUSFLOW_SECRET_KEY in your environment before deploying.
app.secret_key = os.environ.get("CAMPUSFLOW_SECRET_KEY", "dev-only-change-this-secret-key")
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "university.db"

GRADE_POINTS = {
    "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "D": 1.0, "F": 0.0
}
VALID_GRADES = {"", *GRADE_POINTS.keys(), "W", "I"}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_no TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            semester INTEGER NOT NULL CHECK(semester BETWEEN 1 AND 12),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            credit_hours INTEGER NOT NULL CHECK(credit_hours BETWEEN 1 AND 6),
            instructor TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            grade TEXT DEFAULT '',
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, course_id),
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
        );
        """)
        # A demo administrator is created once. Change this password before real deployment.
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.execute(
                "INSERT INTO users(username, password_hash, role) VALUES(?,?,?)",
                ("admin", generate_password_hash("Admin123!"), "admin")
            )
        if db.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO students(student_no, full_name, email, department, semester) VALUES(?,?,?,?,?)",
                [
                    ("STU-1001", "Ayesha Khan", "ayesha@example.com", "Computer Science", 4),
                    ("STU-1002", "Hamza Ali", "hamza@example.com", "Software Engineering", 2),
                    ("STU-1003", "Sara Ahmed", "sara@example.com", "Business Administration", 6),
                ],
            )
        if db.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO courses(course_code, title, department, credit_hours, instructor) VALUES(?,?,?,?,?)",
                [
                    ("CS201", "Object-Oriented Programming", "Computer Science", 3, "Dr. Ahmed"),
                    ("CS305", "Database Systems", "Computer Science", 3, "Ms. Fatima"),
                    ("SE210", "Software Requirements Engineering", "Software Engineering", 3, "Mr. Usman"),
                ],
            )

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.before_request
def require_login():
    allowed = {"login", "static"}
    if request.endpoint not in allowed and not session.get("user_id"):
        return redirect(url_for("login", next=request.path))

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            destination = request.args.get("next", "")
            # Only allow local relative paths to prevent open redirects.
            if not destination.startswith("/") or destination.startswith("//"):
                destination = url_for("dashboard")
            return redirect(destination)
        flash("Incorrect username or password.", "error")
    return render_template("login.html")

@app.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    with get_db() as db:
        stats = {
            "students": db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "courses": db.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
            "enrollments": db.execute("SELECT COUNT(*) FROM enrollments").fetchone()[0],
            "departments": db.execute("SELECT COUNT(DISTINCT department) FROM students").fetchone()[0],
        }
        recent = db.execute("SELECT student_no, full_name, department, semester FROM students ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent)

def calculate_gpa(db, student_id):
    """Credit-hour-weighted cumulative GPA; W, I, and ungraded courses are excluded."""
    rows = db.execute("""
        SELECT e.grade, c.credit_hours
        FROM enrollments e JOIN courses c ON c.id=e.course_id
        WHERE e.student_id=?
    """, (student_id,)).fetchall()
    total_points = 0.0
    total_credits = 0
    for row in rows:
        grade = (row["grade"] or "").upper()
        if grade in GRADE_POINTS:
            credits = row["credit_hours"]
            total_points += GRADE_POINTS[grade] * credits
            total_credits += credits
    if not total_credits:
        return None
    return round(total_points / total_credits, 2)

@app.route("/students")
@login_required
def students():
    q = request.args.get("q", "").strip()
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM students
            WHERE student_no LIKE ? OR full_name LIKE ? OR email LIKE ? OR department LIKE ?
            ORDER BY id DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        student_gpas = {s["id"]: calculate_gpa(db, s["id"]) for s in rows}
    return render_template("students.html", students=rows, student_gpas=student_gpas, q=q)

@app.route("/students/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in ("student_no", "full_name", "email", "department", "semester")]
        try:
            semester = int(data[4])
            if not all(data[:4]) or not 1 <= semester <= 12:
                raise ValueError
            with get_db() as db:
                db.execute("INSERT INTO students(student_no, full_name, email, department, semester) VALUES(?,?,?,?,?)",
                           (data[0], data[1], data[2], data[3], semester))
            flash("Student added successfully.", "success")
            return redirect(url_for("students"))
        except ValueError:
            flash("Please complete every field and choose a semester from 1 to 12.", "error")
        except sqlite3.IntegrityError:
            flash("Student number or email already exists.", "error")
    return render_template("student_form.html", student=None, page_title="Add Student")

@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    with get_db() as db:
        student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if student is None:
            flash("Student not found.", "error")
            return redirect(url_for("students"))
        if request.method == "POST":
            data = [request.form.get(k, "").strip() for k in ("student_no", "full_name", "email", "department", "semester")]
            try:
                semester = int(data[4])
                if not all(data[:4]) or not 1 <= semester <= 12:
                    raise ValueError
                db.execute("UPDATE students SET student_no=?, full_name=?, email=?, department=?, semester=? WHERE id=?",
                           (data[0], data[1], data[2], data[3], semester, student_id))
                flash("Student updated successfully.", "success")
                return redirect(url_for("students"))
            except ValueError:
                flash("Please complete every field and choose a semester from 1 to 12.", "error")
            except sqlite3.IntegrityError:
                flash("Student number or email already exists.", "error")
    return render_template("student_form.html", student=student, page_title="Edit Student")

@app.post("/students/<int:student_id>/delete")
@login_required
def delete_student(student_id):
    with get_db() as db:
        db.execute("DELETE FROM students WHERE id=?", (student_id,))
    flash("Student deleted.", "success")
    return redirect(url_for("students"))

@app.route("/courses")
@login_required
def courses():
    q = request.args.get("q", "").strip()
    with get_db() as db:
        rows = db.execute("""
            SELECT c.*, COUNT(e.id) AS enrollment_count
            FROM courses c LEFT JOIN enrollments e ON e.course_id=c.id
            WHERE c.course_code LIKE ? OR c.title LIKE ? OR c.department LIKE ? OR c.instructor LIKE ?
            GROUP BY c.id ORDER BY c.id DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    return render_template("courses.html", courses=rows, q=q)

@app.route("/courses/add", methods=["GET", "POST"])
@login_required
def add_course():
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in ("course_code", "title", "department", "credit_hours", "instructor")]
        try:
            hours = int(data[3])
            if not all([data[0], data[1], data[2], data[4]]) or not 1 <= hours <= 6:
                raise ValueError
            with get_db() as db:
                db.execute("INSERT INTO courses(course_code, title, department, credit_hours, instructor) VALUES(?,?,?,?,?)",
                           (data[0], data[1], data[2], hours, data[4]))
            flash("Course added successfully.", "success")
            return redirect(url_for("courses"))
        except ValueError:
            flash("Complete every field and choose credit hours from 1 to 6.", "error")
        except sqlite3.IntegrityError:
            flash("That course code already exists.", "error")
    return render_template("course_form.html", course=None, page_title="Add Course")

@app.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
def edit_course(course_id):
    with get_db() as db:
        course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if course is None:
            flash("Course not found.", "error")
            return redirect(url_for("courses"))
        if request.method == "POST":
            data = [request.form.get(k, "").strip() for k in ("course_code", "title", "department", "credit_hours", "instructor")]
            try:
                hours = int(data[3])
                if not all([data[0], data[1], data[2], data[4]]) or not 1 <= hours <= 6:
                    raise ValueError
                db.execute("UPDATE courses SET course_code=?, title=?, department=?, credit_hours=?, instructor=? WHERE id=?",
                           (data[0], data[1], data[2], hours, data[4], course_id))
                flash("Course updated successfully.", "success")
                return redirect(url_for("courses"))
            except ValueError:
                flash("Complete every field and choose credit hours from 1 to 6.", "error")
            except sqlite3.IntegrityError:
                flash("That course code already exists.", "error")
    return render_template("course_form.html", course=course, page_title="Edit Course")

@app.post("/courses/<int:course_id>/delete")
@login_required
def delete_course(course_id):
    with get_db() as db:
        db.execute("DELETE FROM courses WHERE id=?", (course_id,))
    flash("Course deleted.", "success")
    return redirect(url_for("courses"))

@app.route("/enrollments", methods=["GET", "POST"])
@login_required
def enrollments():
    with get_db() as db:
        if request.method == "POST":
            try:
                student_id = int(request.form.get("student_id", ""))
                course_id = int(request.form.get("course_id", ""))
                db.execute("INSERT INTO enrollments(student_id, course_id) VALUES(?,?)", (student_id, course_id))
                flash("Student enrolled in course.", "success")
                return redirect(url_for("enrollments"))
            except (ValueError, sqlite3.IntegrityError):
                flash("Enrollment could not be created. Check the selections or whether the student is already enrolled.", "error")
        students_list = db.execute("SELECT id, student_no, full_name FROM students ORDER BY full_name").fetchall()
        courses_list = db.execute("SELECT id, course_code, title FROM courses ORDER BY course_code").fetchall()
        rows = db.execute("""
            SELECT e.id, e.grade, e.enrolled_at, s.student_no, s.full_name, c.course_code, c.title
            FROM enrollments e JOIN students s ON s.id=e.student_id JOIN courses c ON c.id=e.course_id
            ORDER BY e.id DESC
        """).fetchall()
    return render_template("enrollments.html", enrollments=rows, students=students_list, courses=courses_list)

@app.post("/enrollments/<int:enrollment_id>/grade")
@login_required
def update_grade(enrollment_id):
    grade = request.form.get("grade", "").strip().upper()
    if grade not in VALID_GRADES:
        flash("Choose a valid grade.", "error")
    else:
        with get_db() as db:
            db.execute("UPDATE enrollments SET grade=? WHERE id=?", (grade, enrollment_id))
        flash("Grade updated. Student GPA has been recalculated.", "success")
    return redirect(url_for("enrollments"))

@app.post("/enrollments/<int:enrollment_id>/delete")
@login_required
def delete_enrollment(enrollment_id):
    with get_db() as db:
        db.execute("DELETE FROM enrollments WHERE id=?", (enrollment_id,))
    flash("Enrollment removed.", "success")
    return redirect(url_for("enrollments"))

@app.route("/about")
@login_required
def about():
    return render_template("about.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
