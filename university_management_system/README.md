# CampusFlow — University Management System

A portfolio-focused university management web application built with **Python, Flask, SQLite, HTML, and CSS**.

## Features
- Login screen with password hashing and session-based authentication
- Protected application pages and logout
- Dashboard with student, course, enrollment, and department totals
- Student management: add, view, search, edit, and delete
- Course management: add, view, search, edit, and delete
- Course enrollment: enroll students, prevent duplicate enrollments, remove enrollments
- Grade management for each enrollment
- Automatic credit-hour-weighted cumulative GPA calculation, displayed on the Students page
- SQLite database created automatically, with sample data
- Responsive UI, server-side validation, parameterized SQL queries

## Requirements
- Python 3.10 or newer
- pip

## Run on Windows (VS Code terminal)
Open a terminal in the folder that contains `app.py` and `requirements.txt`:

```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

If `.venv` already exists and is activated, skip the first two commands. If the terminal says it cannot find `requirements.txt`, use `cd` to navigate into the project folder that contains that file, then run the install command again.

Open http://127.0.0.1:5000 in your browser. The database is created automatically on first launch.

## Demo login
- Username: `admin`
- Password: `Admin123!`

These demo credentials are for local learning only. Change the password strategy and set a strong `CAMPUSFLOW_SECRET_KEY` environment variable before any deployment. The app currently provides an administrator login, not separate teacher/student accounts.

## GPA calculation
The Students page shows cumulative GPA on a 4.00 scale. The formula is:

`GPA = sum(grade points × course credit hours) / sum(graded course credit hours)`

| Grade | Points |
|---|---:|
| A | 4.0 |
| A- | 3.7 |
| B+ | 3.3 |
| B | 3.0 |
| B- | 2.7 |
| C+ | 2.3 |
| C | 2.0 |
| D | 1.0 |
| F | 0.0 |

Ungraded courses, W (withdrawal), and I (incomplete) are excluded. When you save a grade in Enrollments & grades, the GPA is recalculated automatically. This version calculates cumulative GPA across all graded enrollments; it does not yet calculate separate semester GPAs.

## Project structure
```text
university_management_system/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── university.db          # created on first run; intentionally gitignored
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── students.html
│   ├── student_form.html
│   ├── courses.html
│   ├── course_form.html
│   ├── enrollments.html
│   └── about.html
└── static/
    └── style.css
```

## Suggested next improvements
- Separate admin, instructor, and student roles with permissions
- CSRF protection and secure production configuration
- Attendance tracking and timetable management
- Semester GPA and transcript PDF export
- Automated tests with pytest
- Deployment to Render or another Python hosting service

## Security note
This is a learning/portfolio prototype, not a production-ready student information system. Before real deployment, add CSRF protection, account management/password changes, rate limiting, secure cookie settings, tests, backups, and privacy/security controls. Do not use the demo credentials or development secret key in production.
