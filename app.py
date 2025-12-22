# ...existing code...
from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Initialize database
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            task TEXT,
            deadline TEXT,
            completed INTEGER DEFAULT 0
            -- progress column may be added below if missing
        )
    """)
    conn.commit()

    # Ensure progress column exists (for upgrades)
    cur.execute("PRAGMA table_info(tasks)")
    cols = [r[1] for r in cur.fetchall()]
    if "progress" not in cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0")
        conn.commit()

    conn.close()

init_db()

# Register
@app.route("/register", methods=["GET","POST"], endpoint="register")
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username,password) VALUES (?,?)",(username,password))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except:
            conn.close()
            return "Username already exists!"
    return render_template("register.html")

# Login
@app.route("/login", methods=["GET","POST"], endpoint="login")
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user = cur.fetchone()
        conn.close()
        if user:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# Logout
@app.route("/logout", endpoint="logout")
def logout():
    session.pop("user",None)
    return redirect(url_for("login"))



# Add task
@app.route("/add", methods=["POST"], endpoint="add_task")
def add_task():
    if "user" not in session:
        return redirect(url_for("login"))
    task_name = request.form["task"]
    deadline = request.form["deadline"]
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # include progress column (default 0)
    cur.execute("INSERT INTO tasks (username,task,deadline,progress) VALUES (?,?,?,?)",
                (session["user"], task_name, deadline, 0))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# Update task progress
@app.route("/update_progress", methods=["POST"], endpoint="update_progress")
def update_progress():
    if "user" not in session:
        return redirect(url_for("login"))
    try:
        task_id = int(request.form["id"])
        prog = int(request.form["progress"])
        prog = max(0, min(100, prog))
    except:
        return redirect(url_for("dashboard"))

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # if progress is 100 mark completed
    completed_flag = 1 if prog == 100 else 0
    cur.execute("UPDATE tasks SET progress = ?, completed = ? WHERE id=? AND username=?",
                (prog, completed_flag, task_id, session["user"]))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# Mark done (legacy route - keeps compatibility)
@app.route("/done/<int:id>", endpoint="done_task")
def done_task(id):
    if "user" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET completed=1, progress=100 WHERE id=? AND username=?",(id,session["user"]))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# Delete task
@app.route("/delete/<int:id>", endpoint="delete_task")
def delete_task(id):
    if "user" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id=? AND username=?",(id,session["user"]))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# Dashboard
@app.route("/", endpoint="dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE username=?",(session["user"],))
    tasks = cur.fetchall()
    conn.close()

    total = len(tasks)
    completed = sum(1 for t in tasks if t["completed"]==1)
    # overall progress = average of per-task progress (0-100)
    if total > 0:
        overall_progress = round(sum((t["progress"] or 0) for t in tasks) / total)
    else:
        overall_progress = 0

    today_date = date.today().isoformat()
    alert = any((t["deadline"] == today_date) and (t["completed"] == 0) for t in tasks)

    # build reminders list (due today or within next 2 days)
    reminders = []
    for t in tasks:
        if t["completed"] == 1:
            continue
        try:
            d = date.fromisoformat(t["deadline"])
            delta = (d - date.today()).days
            if 0 <= delta <= 2:
                reminders.append({"id": t["id"], "task": t["task"], "deadline": t["deadline"], "days": delta})
        except Exception:
            # ignore invalid dates
            continue

    return render_template("dashboard.html", username=session["user"], tasks=tasks,
                           total=total, completed=completed, progress=overall_progress,
                           alert=alert, reminders=reminders)

if __name__=="__main__":
    app.run(debug=True)
# ...existing code...