from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib
import time
from datetime import datetime
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "mysecretkey"

# -------- DATABASE --------

def init_db():
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()


    # TEAMS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT,
            created_by TEXT
        )
    """)

    # TEAM MEMBERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            username TEXT
        )
    """)

    # TEAM REQUESTS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            username TEXT,
            status TEXT
        )
    """)

    # PROJECTS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            project_name TEXT,
            status TEXT,
            priority TEXT
        )
    """)

    # ✅ TASKS (IMPORTANT FIX)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            task_name TEXT,
            status TEXT,
            due_date TEXT,
            assigned_to TEXT
        )
    """)

    # ✅ COMMENTS (IMPORTANT FIX)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            username TEXT,
            comment TEXT
        )
    """)

    cursor.execute("""
         CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT,
            team_id INTEGER,
            project_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
         )
     """)

    cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    username TEXT,
    message TEXT,
    seen INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

    cursor.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    message TEXT,
    is_read INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

    cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    username TEXT,
    file_name TEXT,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

    cursor.execute("""
CREATE TABLE IF NOT EXISTS user_status (
    username TEXT PRIMARY KEY,
    last_seen DATETIME
)
""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password TEXT
    )
""")

    conn.commit()
    conn.close()

init_db()
 
def log_activity(cursor, username, action, team_id=None, project_id=None):
    cursor.execute("""
        INSERT INTO activity_logs (username, action, team_id, project_id)
        VALUES (?, ?, ?, ?)
    """, (username, action, team_id, project_id))

def create_notification(cursor, username, message):

    cursor.execute(
        "INSERT INTO notifications (username, message) VALUES (?, ?)",
        (username, message)
    )

# -------- SEND OTP EMAIL --------

def send_otp(email, otp):

    sender = "teamcollabrix@gmail.com"
    password = "fgacqasqnxhlivjx"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(sender, password)

    subject = "Collabrix Email Verification"
    body = f"""
Hello,

Welcome to Collabrix!

We are excited to have you join our collaboration platform where teams manage projects, track tasks, and work together efficiently.

Your verification code is:

{otp}

Please enter this code to complete your signup.

If you did not request this, you can safely ignore this email.

Best regards,
founder of collabrix :
mohd mehraj ahmed siddique
"""

    message = f"Subject: {subject}\n\n{body}"

    server.sendmail(sender, email, message)

    server.quit()    

   
# -------- HOME --------

@app.route("/")
def home():
    return render_template("landing.html")

# -------- SIGNUP --------

@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        # 🔒 OTP spam protection
        if session.get("otp_time"):
            diff = time.time() - session.get("otp_time")

            if diff < 60:
                return "Please wait before requesting another OTP ⏳"

        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        otp = random.randint(100000,999999)

        session["signup_otp"] = otp
        session["signup_username"] = username
        session["signup_email"] = email
        session["signup_password"] = password

        # ⏱ save otp time
        session["otp_time"] = time.time()

        send_otp(email, otp)

        return redirect("/verify_signup")

    return render_template("signup.html")

#------------- verify signup -----

@app.route("/verify_signup", methods=["GET","POST"])
def verify_signup():

    if request.method == "POST":

        user_otp = request.form.get("otp")

        if str(session.get("signup_otp")) == user_otp:

            conn = sqlite3.connect("users.db",timeout=10)
            cursor = conn.cursor()

            email = session.get("signup_email")

            # 🔍 check if email already exists
            cursor.execute("SELECT * FROM users WHERE email=?", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                conn.close()
                return render_template("emails_exists.html")

            # ✅ create new user
            cursor.execute(
                "INSERT INTO users (username,email,password) VALUES (?,?,?)",
                (
                    session.get("signup_username"),
                    email,
                    session.get("signup_password")
                )
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        else:
            return "Invalid OTP"

    return render_template("verify_signup.html")

#------------ login page -----
    

@app.route("/login", methods=["GET","POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")

        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cursor.fetchone()

        if user:

            # 🔥 USER ONLINE STATUS UPDATE
            cursor.execute("""
            INSERT OR REPLACE INTO user_status (username, last_seen)
            VALUES (?, ?)
            """, (username, datetime.now()))

            conn.commit()
            conn.close()

            session["logged_in"] = True
            session["username"] = username

            return redirect("/dashboard")

        else:
            conn.close()
            error = "Invalid Username or Password ❌"

    return render_template("login.html", error=error)

# -------- DASHBOARD --------

@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    username = session.get("username")

    # 🔥 UPDATE USER LAST SEEN (ONLINE STATUS)
    cursor.execute("""
    INSERT OR REPLACE INTO user_status (username, last_seen)
    VALUES (?, ?)
    """, (username, datetime.now()))

    # 🔹 USER TEAMS
    cursor.execute("""
        SELECT teams.* FROM teams
        JOIN team_members ON teams.id = team_members.team_id
        WHERE team_members.username=?
    """, (username,))
    teams = cursor.fetchall()

    # 🔹 TOTAL PROJECTS (ONLY USER TEAMS)
    cursor.execute("""
        SELECT COUNT(*) FROM projects
        WHERE team_id IN (
            SELECT team_id FROM team_members WHERE username=?
        )
    """, (username,))
    total_projects = cursor.fetchone()[0]

    # 🔹 COMPLETED PROJECTS
    cursor.execute("""
        SELECT COUNT(*) FROM projects
        WHERE status='Completed' AND team_id IN (
            SELECT team_id FROM team_members WHERE username=?
        )
    """, (username,))
    completed_projects = cursor.fetchone()[0]

    # 🔹 ACTIVE PROJECTS
    cursor.execute("""
        SELECT COUNT(*) FROM projects
        WHERE status='Active' AND team_id IN (
            SELECT team_id FROM team_members WHERE username=?
        )
    """, (username,))
    active_projects = cursor.fetchone()[0]

    # 🔥 TOTAL TASKS
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE project_id IN (
            SELECT id FROM projects
            WHERE team_id IN (
                SELECT team_id FROM team_members WHERE username=?
            )
        )
    """, (username,))
    total_tasks = cursor.fetchone()[0]

    # 🔥 COMPLETED TASKS
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE status='Completed' AND project_id IN (
            SELECT id FROM projects
            WHERE team_id IN (
                SELECT team_id FROM team_members WHERE username=?
            )
        )
    """, (username,))
    completed_tasks = cursor.fetchone()[0]

    # 🔹 PRODUCTIVITY
    if total_tasks == 0:
        productivity = 0
    else:
        productivity = int((completed_tasks / total_tasks) * 100)

    # 🔹 ACTIVE USERS
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
    except:
        total_users = 0

    # 🔥 PENDING REQUESTS
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM team_requests
            WHERE username=? AND status='pending'
        """, (username,))
        pending_requests = cursor.fetchone()[0]
    except:
        pending_requests = 0

    # 🔔 NOTIFICATIONS
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE username=? AND is_read=0
        """, (username,))
        notification_count = cursor.fetchone()[0]
    except:
        notification_count = 0

    # 🔥 TEAM ACTIVITY
    cursor.execute("""
        SELECT username, action, timestamp
        FROM activity_logs
        WHERE team_id IN (
            SELECT team_id FROM team_members WHERE username=?
        )
        ORDER BY id DESC
        LIMIT 10
    """, (username,))
    activities = cursor.fetchall()

    # 🔥 TEAM BASED ONLINE USERS
    cursor.execute("""
    SELECT username, last_seen
    FROM user_status
    WHERE username IN (
        SELECT username FROM team_members
        WHERE team_id IN (
            SELECT team_id FROM team_members
            WHERE username=?
        )
    )
    """, (username,))

    users_status = cursor.fetchall()

    online_users = []

    for u in users_status:

        last = datetime.fromisoformat(str(u[1]))
        diff = datetime.now() - last

        if diff.total_seconds() < 300:
            online_users.append((u[0], "online"))
        else:
            online_users.append((u[0], "offline"))

    conn.commit()
    conn.close()

    return render_template(
        "dashboard.html",
        username=username,
        teams=teams,
        total_projects=total_projects,
        completed_projects=completed_projects,
        active_projects=active_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        productivity=productivity,
        total_users=total_users,
        pending_requests=pending_requests,
        notification_count=notification_count,
        activities=activities,
        online_users=online_users
    )
    
# -------- DELETE TEAM --------

@app.route("/delete_team/<int:team_id>")
def delete_team(team_id):

    # 🔐 LOGIN CHECK
    if not session.get("logged_in"):
        return redirect("/login")

    username = session.get("username")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    # 👑 CHECK TEAM LEADER
    cursor.execute("SELECT created_by FROM teams WHERE id=?", (team_id,))
    team = cursor.fetchone()

    # ❌ ONLY LEADER CAN DELETE
    if not team or team[0] != username:
        conn.close()
        return "Only leader can delete team ❌"

    try:
        # 🔥 STEP 1: DELETE TASKS (IMPORTANT)
        cursor.execute("""
            DELETE FROM tasks 
            WHERE project_id IN (
                SELECT id FROM projects WHERE team_id=?
            )
        """, (team_id,))

        # 🔥 STEP 2: DELETE PROJECTS
        cursor.execute(
            "DELETE FROM projects WHERE team_id=?",
            (team_id,)
        )

        # 🔥 STEP 3: DELETE MEMBERS
        cursor.execute(
            "DELETE FROM team_members WHERE team_id=?",
            (team_id,)
        )

        # 🔥 STEP 4: DELETE REQUESTS
        cursor.execute(
            "DELETE FROM team_requests WHERE team_id=?",
            (team_id,)
        )

        # 🔥 STEP 5: DELETE TEAM
        cursor.execute(
            "DELETE FROM teams WHERE id=?",
            (team_id,)
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Error deleting team ❌: {str(e)}"

    conn.close()

    return redirect("/dashboard")

# -------- EXIT TEAM --------


@app.route("/exit_team/<int:team_id>")
def exit_team(team_id):

    # login check
    if not session.get("logged_in"):
        return redirect("/login")

    username = session.get("username")
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    # check team leader
    cursor.execute(
        "SELECT created_by FROM teams WHERE id=?",
        (team_id,)
    )

    team = cursor.fetchone()

    # 👑 LEADER EXIT BLOCK
    if team and team[0] == username:
        conn.close()
        return render_template("leader_exit_error.html")

    # normal member exit
    cursor.execute(
        "DELETE FROM team_members WHERE team_id=? AND username=?",
        (team_id, username)
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


# -------- TRANSFER LEADERSHIP --------

@app.route("/transfer_leader/<int:team_id>", methods=["POST"])
def transfer_leader(team_id):

    if not session.get("logged_in"):
        return redirect("/login")

    new_leader = request.form.get("new_leader")
    current_user = session.get("username")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute("SELECT created_by FROM teams WHERE id=?", (team_id,))
    team = cursor.fetchone()

    if team and team[0] == current_user:

        cursor.execute(
            "SELECT * FROM team_members WHERE team_id=? AND username=?",
            (team_id, new_leader)
        )

        if cursor.fetchone():
            cursor.execute(
                "UPDATE teams SET created_by=? WHERE id=?",
                (new_leader, team_id)
            )

    conn.commit()
    conn.close()

    return redirect(f"/team/{team_id}")


# -------- SEND INVITE --------

@app.route("/add_member/<int:team_id>", methods=["POST"])
def add_member(team_id):

    if not session.get("logged_in"):
        return redirect("/login")

    username = request.form.get("username").strip()
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    # check user exists
    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cursor.fetchone()

    if user:
        cursor.execute(
            "INSERT INTO team_requests (team_id, username, status) VALUES (?, ?, ?)",
            (team_id, username, "pending")
        )

    conn.commit()
    conn.close()

    return redirect(f"/team/{team_id}")   

# -------- CREATE TEAM --------

@app.route("/create_team", methods=["GET","POST"])
def create_team():

    # 🔐 LOGIN CHECK
    if not session.get("logged_in"):
        return redirect("/login")

    if request.method == "POST":

        team_name = request.form.get("team_name").strip()

        # ❌ empty name block
        if not team_name:
            return redirect("/create_team")

        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

        try:
            # 🔥 CREATE TEAM
            cursor.execute(
                "INSERT INTO teams (team_name, created_by) VALUES (?, ?)",
                (team_name, session.get("username"))
            )

            team_id = cursor.lastrowid

            # 🔥 ADD LEADER AS MEMBER
            cursor.execute(
                "INSERT INTO team_members (team_id, username) VALUES (?, ?)",
                (team_id, session.get("username"))
            )

            # 🔥 ACTIVITY LOG (FIXED)
            log_activity(
                cursor,   # ✅ IMPORTANT (NOT conn)
                session.get("username"),
                f"Created team '{team_name}'",
                team_id=team_id
            )

            conn.commit()

        except Exception as e:
            conn.rollback()
            conn.close()
            return f"Error creating team ❌: {str(e)}"

        conn.close()

        return redirect("/dashboard")

    return render_template("create_team.html")

# -------- TEAM PAGE --------

@app.route("/team/<int:team_id>")
def team_page(team_id):

    if not session.get("logged_in"):
        return redirect("/login")
        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

    cursor.execute("SELECT * FROM teams WHERE id=?", (team_id,))
    team = cursor.fetchone()

    cursor.execute(
        "SELECT username FROM team_members WHERE team_id=?",
        (team_id,)
    )
    members = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM projects WHERE team_id=?",
        (team_id,)
    )
    projects = cursor.fetchall()

    conn.close()

    return render_template(
        "team.html",
        team=team,
        members=members,
        projects=projects
    )

# -------- ACCEPT REQUEST --------

@app.route("/accept/<int:req_id>")
def accept(req_id):

    if not session.get("logged_in"):
        return redirect("/login")
        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

    cursor.execute(
        "SELECT team_id, username FROM team_requests WHERE id=?",
        (req_id,)
    )

    data = cursor.fetchone()

    if data:

        team_id = data[0]
        username = data[1]

        # member add
        cursor.execute(
            "INSERT INTO team_members (team_id, username) VALUES (?, ?)",
            (team_id, username)
        )

        # request accepted
        cursor.execute(
            "UPDATE team_requests SET status='accepted' WHERE id=?",
            (req_id,)
        )

        # 🔥 ACTIVITY LOG
        log_activity(
            cursor,
            username,
            "joined the team",
            team_id=team_id
        )

    conn.commit()
    conn.close()

    return redirect("/requests")

# -------- REJECT REQUEST --------

@app.route("/reject/<int:req_id>")
def reject(req_id):

    if not session.get("logged_in"):
        return redirect("/login")

        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

    cursor.execute(
        "UPDATE team_requests SET status='rejected' WHERE id=?",
        (req_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/requests")    

# -------- REQUESTS PAGE --------

@app.route("/requests")
def requests():

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT team_requests.id, teams.team_name
        FROM team_requests
        JOIN teams ON teams.id = team_requests.team_id
        WHERE team_requests.username=? AND status='pending'
    """, (session.get("username"),))

    requests_data = cursor.fetchall()

    conn.close()

    return render_template(
        "requests.html",
        requests=requests_data
    )
    
# -------- CREATE PROJECT --------

@app.route("/create_project/<int:team_id>", methods=["GET","POST"])
def create_project(team_id):

    # login check
    if not session.get("logged_in"):
        return redirect("/login")

    if request.method == "POST":

        # ⭐ form se data lo
        project_name = request.form.get("project_name").strip()
        priority = request.form.get("priority")

        # ⭐ safety (empty project name stop)
        if not project_name:
            return redirect(f"/create_project/{team_id}")
            conn = sqlite3.connect("users.db",timeout=10)
            cursor = conn.cursor()

        # ⭐ project insert
        cursor.execute(
            "INSERT INTO projects (team_id, project_name, status, priority) VALUES (?, ?, ?, ?)",
            (team_id, project_name, "Active", priority)
        )

        conn.commit()
        conn.close()

        return redirect(f"/team/{team_id}")

    return render_template("create_project.html", team_id=team_id)

# -------- PROJECT STATUS --------
# ⚠️ ONLY ONE VERSION (FIX)

@app.route("/project_status/<int:project_id>/<status>")
def project_status(project_id, status):

    if not session.get("logged_in"):
        return redirect("/login")
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE projects SET status=? WHERE id=?",
        (status, project_id)
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer)

# -------- DELETE PROJECT --------

@app.route("/delete_project/<int:project_id>")
def delete_project(project_id):

    if not session.get("logged_in"):
        return redirect("/login")

        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM projects WHERE id=?",
        (project_id,)
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer)

#---------- PROJECT PAGE --------   

@app.route("/project/<int:project_id>")
def project_page(project_id):

    # 🔐 LOGIN CHECK
    if not session.get("logged_in"):
        return redirect("/login")

        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

    # 🔹 PROJECT FETCH
    cursor.execute(
        "SELECT * FROM projects WHERE id=?",
        (project_id,)
    )
    project = cursor.fetchone()

    # 🔹 TASKS FETCH
    cursor.execute(
        "SELECT * FROM tasks WHERE project_id=?",
        (project_id,)
    )
    tasks = cursor.fetchall()

    # 🔹 COMMENTS FETCH
    cursor.execute(
        "SELECT * FROM comments"
    )
    comments = cursor.fetchall()

    # 🔥 TEAM MEMBERS FETCH (FIXED)
    cursor.execute("""
        SELECT username FROM team_members
        WHERE team_id = (
            SELECT team_id FROM projects WHERE id=?
        )
    """, (project_id,))
    members = cursor.fetchall()

    # 🔥 FILES FETCH (NEW FEATURE)
    cursor.execute(
        "SELECT * FROM files WHERE project_id=?",
        (project_id,)
    )
    files = cursor.fetchall()

    # 🔹 PROGRESS CALCULATION
    total_tasks = len(tasks)

    if total_tasks == 0:
        progress = 0
    else:
        completed_tasks = 0

        for t in tasks:
            if t[3] == "Completed":
                completed_tasks += 1

        progress = int((completed_tasks / total_tasks) * 100)

        # optional smooth UI
        progress = int(progress / 10) * 10

    conn.close()

    # 🔥 CURRENT DATE (OVERDUE CHECK)
    current_date = str(datetime.now().date())

    return render_template(
        "project.html",
        project=project,
        tasks=tasks,
        comments=comments,
        progress=progress,
        members=members,           # ✅ IMPORTANT
        current_date=current_date, # ✅ IMPORTANT
        files=files                # 🔥 NEW (FILES SEND TO HTML)
    )
#--------- TASK --------

@app.route("/create_task/<int:project_id>", methods=["GET","POST"])
def create_task(project_id):

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    # 🔥 MEMBERS FETCH (IMPORTANT)
    cursor.execute("""
        SELECT username FROM team_members
        WHERE team_id = (
            SELECT team_id FROM projects WHERE id=?
        )
    """, (project_id,))
    members = cursor.fetchall()

    if request.method == "POST":

        task_name = request.form.get("task_name")
        due_date = request.form.get("due_date")
        assigned_to = request.form.get("assigned_to")

        cursor.execute(
            """
            INSERT INTO tasks (project_id, task_name, status, due_date, assigned_to)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, task_name, "Pending", due_date, assigned_to)
        )

        conn.commit()
        conn.close()

        return redirect(f"/project/{project_id}")

    conn.close()
    return render_template("create_task.html", project_id=project_id, members=members)
#--------- ADD TASK ------

@app.route("/add_task/<int:project_id>", methods=["POST"])
def add_task(project_id):

    if not session.get("logged_in"):
        return redirect("/login")

    task_name = request.form.get("task_name")
    due_date = request.form.get("due_date")
    assigned_to = request.form.get("assigned_to")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (project_id, task_name, status, due_date, assigned_to) VALUES (?, ?, ?, ?, ?)",
        (project_id, task_name, "Pending", due_date, assigned_to)
    )

    if assigned_to:
        create_notification(
            cursor,
            assigned_to,
            f"You were assigned a new task: {task_name}"
        )

    conn.commit()
    conn.close()

    return redirect(request.referrer)

 # -------- COMPLETE TASK --------
@app.route("/complete_task/<int:task_id>")
def complete_task(task_id):

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE tasks SET status='Completed' WHERE id=?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer)


# -------- DELETE TASK --------
@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):

    if not session.get("logged_in"):
        return redirect("/login")
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM tasks WHERE id=?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer)   

#--------- EDIT TASK-----

@app.route("/edit_task/<int:task_id>", methods=["GET","POST"])
def edit_task(task_id):

    if not session.get("logged_in"):
        return redirect("/login")
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    task = cursor.fetchone()

    if request.method == "POST":
        new_name = request.form.get("task_name")

        cursor.execute(
            "UPDATE tasks SET task_name=? WHERE id=?",
            (new_name, task_id)
        )

        conn.commit()
        conn.close()

        # ⭐ DIRECT PROJECT PAGE RETURN
        return redirect(f"/project/{task[1]}")

    conn.close()
    return render_template("edit_task.html", task=task)

#---------- toggle task -----

@app.route("/toggle_task/<int:task_id>")
def toggle_task(task_id):

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute("SELECT status, project_id FROM tasks WHERE id=?", (task_id,))
    task = cursor.fetchone()

    if task:
        new_status = "Completed" if task[0] != "Completed" else "Pending"

        cursor.execute(
            "UPDATE tasks SET status=? WHERE id=?",
            (new_status, task_id)
        )

    conn.commit()
    conn.close()

    return redirect(f"/project/{task[1]}")

#--------- ADD COMMENTS------

@app.route("/add_comment/<int:task_id>", methods=["POST"])
def add_comment(task_id):

    if not session.get("logged_in"):
        return redirect("/login")

    comment = request.form.get("comment")
    username = session["username"]

    conn = sqlite3.connect("users.db",timeout=10)
    c = conn.cursor()

    c.execute(
        "INSERT INTO comments (task_id, username, comment) VALUES (?, ?, ?)",
        (task_id, username, comment)
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer) 

 #-------- project priority------

@app.route("/project_priority/<int:project_id>/<priority>")
def project_priority(project_id, priority):

    if not session.get("logged_in"):
        return redirect("/login")
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE projects SET priority=? WHERE id=?",
        (priority, project_id)
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer)   

#------------- TEAM CHAT--------    

@app.route("/team_chat/<int:team_id>", methods=["GET","POST"])
def team_chat(team_id):

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    username = session.get("username")

    # 🔥 SEND MESSAGE
    if request.method == "POST":
        message = request.form.get("message")

        cursor.execute(
            "INSERT INTO messages (team_id, username, message) VALUES (?, ?, ?)",
            (team_id, username, message)
        )

        # 🔔 CREATE NOTIFICATION
        create_notification(
            cursor,
            username,
            "New message in team chat"
        )

        conn.commit()

    # 🔥 MARK OTHER USERS MESSAGES AS SEEN
    cursor.execute("""
        UPDATE messages
        SET seen = 1
        WHERE team_id = ?
        AND username != ?
    """, (team_id, username))

    conn.commit()

    # 🔥 FETCH MESSAGES
    cursor.execute(
        "SELECT * FROM messages WHERE team_id=? ORDER BY id ASC",
        (team_id,)
    )
    messages = cursor.fetchall()

    conn.close()

    return render_template(
        "team_chat.html",
        messages=messages,
        username=username,
        team_id=team_id
    )
    
    
#--------- delete msg-----

@app.route("/delete_message/<int:msg_id>/<int:team_id>")
def delete_message(msg_id, team_id):

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    username = session.get("username")

    # 🔐 CHECK OWNER (sirf apna message delete kare)
    cursor.execute("SELECT username FROM messages WHERE id=?", (msg_id,))
    msg = cursor.fetchone()

    if msg and msg[0] == username:
        cursor.execute("DELETE FROM messages WHERE id=?", (msg_id,))
        conn.commit()

    conn.close()

    return redirect(f"/team_chat/{team_id}")

#--------- NOTIFICATION------- 

@app.route("/notifications")
def notifications():

    if not session.get("logged_in"):
        return redirect("/login")

    username = session.get("username")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    # 🔥 GET NOTIFICATIONS
    cursor.execute(
        "SELECT * FROM notifications WHERE username=? ORDER BY id DESC",
        (username,)
    )
    notifications = cursor.fetchall()

    # 🔥 MARK ALL AS READ
    cursor.execute(
        "UPDATE notifications SET is_read=1 WHERE username=?",
        (username,)
    )

    conn.commit()
    conn.close()

    return render_template(
        "notifications.html",
        notifications=notifications
    )
  
#--------- team activity----

@app.route("/team_activity")
def team_activity():

    if not session.get("logged_in"):
        return redirect("/login")

    username = session.get("username")
    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, action, timestamp
        FROM activity_logs
        WHERE team_id IN (
            SELECT team_id FROM team_members WHERE username=?
        )
        ORDER BY id DESC
        LIMIT 20
    """, (username,))

    activities = cursor.fetchall()

    conn.close()

    return render_template(
        "team_activity.html",
        activities=activities
    )  

#=-------- upload files-----

@app.route("/upload_file/<int:project_id>", methods=["POST"])
def upload_file(project_id):

    if not session.get("logged_in"):
        return redirect("/login")

    file = request.files["file"]

    if file and file.filename != "":

        filename = secure_filename(file.filename)

        path = os.path.join("static/uploads", filename)

        file.save(path)

        conn = sqlite3.connect("users.db",timeout=10)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO files (project_id, username, file_name) VALUES (?, ?, ?)",
            (project_id, session.get("username"), filename)
        )

        conn.commit()
        conn.close()

    return redirect(request.referrer)

#-------- delete files ------   

@app.route("/delete_file/<int:file_id>")
def delete_file(file_id):

    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_name FROM files WHERE id=?",
        (file_id,)
    )
    file = cursor.fetchone()

    if file:
        file_path = os.path.join("static/uploads", file[0])

        if os.path.exists(file_path):
            os.remove(file_path)

        cursor.execute(
            "DELETE FROM files WHERE id=?",
            (file_id,)
        )

    conn.commit()
    conn.close()

    return redirect(request.referrer)    

# -------- LOGOUT --------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

#--------- image route-----

from flask import send_from_directory

@app.route('/images/<path:filename>')
def images(filename):
    return send_from_directory('images', filename)
    
# -------- REMOVE MEMBER --------

@app.route("/remove_member/<int:team_id>/<username>")
def remove_member(team_id, username):

    if not session.get("logged_in"):
        return redirect("/login")

    current_user = session.get("username")

    conn = sqlite3.connect("users.db",timeout=10)
    cursor = conn.cursor()

    # 🔍 check leader
    cursor.execute("SELECT created_by FROM teams WHERE id=?", (team_id,))
    team = cursor.fetchone()

    # ❌ only leader allowed
    if not team or team[0] != current_user:
        conn.close()
        return "Only leader can remove members ❌"

    # ❌ leader cannot remove himself
    if username == current_user:
        conn.close()
        return "Leader cannot remove himself ❌"

    # ✅ remove member
    cursor.execute(
        "DELETE FROM team_members WHERE team_id=? AND username=?",
        (team_id, username)
    )

    conn.commit()
    conn.close()

    return redirect(f"/team/{team_id}")    

# -------- RUN --------

if __name__ == "__main__":
    app.run(debug=True)