#!/usr/bin/env python3
"""
DAYMARK - Portable HTMX + SQLite todo app with Git sync.
Minimalist, full-featured daily maintenance across categories.
"""

import os
import sqlite3
import subprocess
from datetime import datetime, date, timedelta
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, g, flash, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "edge-todo-dev-key-change-me")

DB_PATH = Path(__file__).parent / "data" / "todo.db"
DATA_DIR = Path(__file__).parent / "data"


def get_db():
    if "db" not in g:
        DATA_DIR.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#6366f1',
            icon TEXT DEFAULT '📁',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category_id INTEGER,
            due_date TEXT,
            status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'doing', 'done', 'blocked')),
            priority INTEGER DEFAULT 2 CHECK(priority BETWEEN 1 AND 4),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category_id);
    """)
    # Seed default categories if empty
    count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if count == 0:
        defaults = [
            ("Job (TA)", "#0ea5e9", "🎓", 1),
            ("Learning", "#8b5cf6", "📚", 2),
            ("Research", "#ec4899", "🔬", 3),
            ("Repos", "#10b981", "💻", 4),
            ("Projects", "#f59e0b", "🚀", 5),
            ("Blogs", "#ef4444", "✍️", 6),
            ("AI Engineering", "#6366f1", "🤖", 7),
        ]
        db.executemany(
            "INSERT INTO categories (name, color, icon, sort_order) VALUES (?, ?, ?, ?)",
            defaults,
        )
        db.commit()


# ---------- Helpers ----------

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def today_str():
    return date.today().isoformat()


def status_badge(status):
    map_ = {
        "todo": ("bg-slate-100 text-slate-700", "Todo"),
        "doing": ("bg-amber-100 text-amber-800", "Doing"),
        "done": ("bg-emerald-100 text-emerald-800", "Done"),
        "blocked": ("bg-rose-100 text-rose-800", "Blocked"),
    }
    return map_.get(status, map_["todo"])


def priority_label(p):
    return {1: "Low", 2: "Med", 3: "High", 4: "Urgent"}.get(p, "Med")


# ---------- Routes ----------

@app.route("/")
def index():
    return redirect(url_for("day_view"))


@app.route("/day")
@app.route("/day/<day>")
def day_view(day=None):
    if day is None:
        day = today_str()
    d = parse_date(day) or date.today()
    day = d.isoformat()

    db = get_db()
    tasks = db.execute("""
        SELECT t.*, c.name as cat_name, c.color as cat_color, c.icon as cat_icon
        FROM tasks t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.due_date = ? OR (t.due_date IS NULL AND date(t.created_at) = ?)
        ORDER BY t.priority DESC, t.status, t.created_at
    """, (day, day)).fetchall()

    # Also pull overdue incomplete
    overdue = db.execute("""
        SELECT t.*, c.name as cat_name, c.color as cat_color, c.icon as cat_icon
        FROM tasks t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.due_date < ? AND t.status != 'done'
        ORDER BY t.due_date, t.priority DESC
    """, (day,)).fetchall()

    categories = db.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()

    prev_day = (d - timedelta(days=1)).isoformat()
    next_day = (d + timedelta(days=1)).isoformat()
    is_today = day == today_str()

    return render_template(
        "day.html",
        tasks=tasks,
        overdue=overdue,
        categories=categories,
        day=day,
        day_display=d.strftime("%A, %b %d %Y"),
        prev_day=prev_day,
        next_day=next_day,
        is_today=is_today,
        status_badge=status_badge,
        priority_label=priority_label,
    )


@app.route("/calendar")
@app.route("/calendar/<int:year>/<int:month>")
def calendar_view(year=None, month=None):
    today = date.today()
    if year is None:
        year, month = today.year, today.month

    first = date(year, month, 1)
    # weekday: Mon=0 ... Sun=6
    start_pad = first.weekday()
    if month == 12:
        next_m, next_y = 1, year + 1
    else:
        next_m, next_y = month + 1, year
    last = date(next_y, next_m, 1) - timedelta(days=1)
    days_in_month = last.day

    # Build grid
    cells = []
    for _ in range(start_pad):
        cells.append(None)
    for d in range(1, days_in_month + 1):
        cells.append(date(year, month, d))

    db = get_db()
    # Tasks for this month
    start_str = first.isoformat()
    end_str = last.isoformat()
    task_rows = db.execute("""
        SELECT due_date, status, COUNT(*) as cnt
        FROM tasks
        WHERE due_date BETWEEN ? AND ?
        GROUP BY due_date, status
    """, (start_str, end_str)).fetchall()

    day_stats = {}
    for r in task_rows:
        dd = r["due_date"]
        if dd not in day_stats:
            day_stats[dd] = {"todo": 0, "doing": 0, "done": 0, "blocked": 0, "total": 0}
        day_stats[dd][r["status"]] = r["cnt"]
        day_stats[dd]["total"] += r["cnt"]

    categories = db.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()

    prev_month = (first - timedelta(days=1))
    next_month = last + timedelta(days=1)

    return render_template(
        "calendar.html",
        year=year,
        month=month,
        month_name=first.strftime("%B %Y"),
        cells=cells,
        day_stats=day_stats,
        today=today.isoformat(),
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month.year,
        next_month=next_month.month,
        categories=categories,
        status_badge=status_badge,
    )


@app.route("/tasks")
def tasks_list():
    status = request.args.get("status", "all")
    cat = request.args.get("cat", "all")
    q = request.args.get("q", "").strip()

    db = get_db()
    sql = """
        SELECT t.*, c.name as cat_name, c.color as cat_color, c.icon as cat_icon
        FROM tasks t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE 1=1
    """
    params = []
    if status != "all":
        sql += " AND t.status = ?"
        params.append(status)
    if cat != "all":
        sql += " AND t.category_id = ?"
        params.append(int(cat))
    if q:
        sql += " AND (t.title LIKE ? OR t.description LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY CASE t.status WHEN 'doing' THEN 0 WHEN 'todo' THEN 1 WHEN 'blocked' THEN 2 ELSE 3 END, t.priority DESC, t.due_date IS NULL, t.due_date, t.created_at DESC"

    tasks = db.execute(sql, params).fetchall()
    categories = db.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()

    return render_template(
        "tasks.html",
        tasks=tasks,
        categories=categories,
        current_status=status,
        current_cat=cat,
        q=q,
        status_badge=status_badge,
        priority_label=priority_label,
    )


@app.route("/task/new", methods=["GET", "POST"])
def task_new():
    db = get_db()
    categories = db.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required", "error")
            return render_template("task_form.html", task=None, categories=categories, mode="new")

        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id") or None
        due_date = request.form.get("due_date") or None
        status = request.form.get("status", "todo")
        priority = int(request.form.get("priority", 2))

        db.execute(
            """INSERT INTO tasks (title, description, category_id, due_date, status, priority)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, description, category_id, due_date, status, priority),
        )
        db.commit()
        flash("Task created", "success")
        return redirect(url_for("day_view", day=due_date or today_str()))

    # prefill due_date from query
    prefill = {"due_date": request.args.get("due", today_str())}
    return render_template(
        "task_form.html", task=prefill, categories=categories, mode="new"
    )


@app.route("/task/<int:tid>/edit", methods=["GET", "POST"])
def task_edit(tid):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
    if not task:
        flash("Task not found", "error")
        return redirect(url_for("tasks_list"))

    categories = db.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required", "error")
            return render_template("task_form.html", task=task, categories=categories, mode="edit")

        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id") or None
        due_date = request.form.get("due_date") or None
        status = request.form.get("status", "todo")
        priority = int(request.form.get("priority", 2))
        completed_at = task["completed_at"]
        if status == "done" and not completed_at:
            completed_at = datetime.utcnow().isoformat()
        elif status != "done":
            completed_at = None

        db.execute(
            """UPDATE tasks SET title=?, description=?, category_id=?, due_date=?,
               status=?, priority=?, updated_at=datetime('now'), completed_at=?
               WHERE id=?""",
            (title, description, category_id, due_date, status, priority, completed_at, tid),
        )
        db.commit()
        flash("Task updated", "success")
        return redirect(url_for("day_view", day=due_date or today_str()))

    return render_template(
        "task_form.html", task=task, categories=categories, mode="edit"
    )


@app.route("/task/<int:tid>/status", methods=["POST"])
def task_status(tid):
    status = request.form.get("status")
    if status not in ("todo", "doing", "done", "blocked"):
        return "Invalid", 400
    db = get_db()
    completed_at = None
    if status == "done":
        completed_at = datetime.utcnow().isoformat()
    db.execute(
        "UPDATE tasks SET status=?, updated_at=datetime('now'), completed_at=? WHERE id=?",
        (status, completed_at, tid),
    )
    db.commit()

    if request.headers.get("HX-Request"):
        task = db.execute("""
            SELECT t.*, c.name as cat_name, c.color as cat_color, c.icon as cat_icon
            FROM tasks t LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.id = ?
        """, (tid,)).fetchone()
        return render_template(
            "partials/task_card.html",
            task=task,
            status_badge=status_badge,
            priority_label=priority_label,
        )
    return redirect(request.referrer or url_for("day_view"))


@app.route("/task/<int:tid>/delete", methods=["POST"])
def task_delete(tid):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (tid,))
    db.commit()
    flash("Task deleted", "success")
    if request.headers.get("HX-Request"):
        return ""
    return redirect(request.referrer or url_for("tasks_list"))


# ---------- Categories ----------

@app.route("/categories")
def categories_list():
    db = get_db()
    cats = db.execute("""
        SELECT c.*, COUNT(t.id) as task_count
        FROM categories c
        LEFT JOIN tasks t ON t.category_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order, c.name
    """).fetchall()
    return render_template("categories.html", categories=cats)


@app.route("/category/new", methods=["GET", "POST"])
def category_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name required", "error")
            return render_template("category_form.html", cat=None, mode="new")
        color = request.form.get("color", "#6366f1")
        icon = request.form.get("icon", "📁")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO categories (name, color, icon) VALUES (?, ?, ?)",
                (name, color, icon),
            )
            db.commit()
            flash("Category created", "success")
            return redirect(url_for("categories_list"))
        except sqlite3.IntegrityError:
            flash("Category name already exists", "error")
    return render_template("category_form.html", cat=None, mode="new")


@app.route("/category/<int:cid>/edit", methods=["GET", "POST"])
def category_edit(cid):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id = ?", (cid,)).fetchone()
    if not cat:
        flash("Not found", "error")
        return redirect(url_for("categories_list"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name required", "error")
            return render_template("category_form.html", cat=cat, mode="edit")
        color = request.form.get("color", "#6366f1")
        icon = request.form.get("icon", "📁")
        try:
            db.execute(
                "UPDATE categories SET name=?, color=?, icon=? WHERE id=?",
                (name, color, icon, cid),
            )
            db.commit()
            flash("Category updated", "success")
            return redirect(url_for("categories_list"))
        except sqlite3.IntegrityError:
            flash("Name already exists", "error")
    return render_template("category_form.html", cat=cat, mode="edit")


@app.route("/category/<int:cid>/delete", methods=["POST"])
def category_delete(cid):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (cid,))
    db.commit()
    flash("Category deleted", "success")
    return redirect(url_for("categories_list"))


# ---------- Git Sync ----------

@app.route("/sync", methods=["GET", "POST"])
def git_sync():
    repo_root = Path(__file__).parent
    result = {"ok": False, "msg": "", "log": ""}

    def run(cmd):
        try:
            p = subprocess.run(
                cmd,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return p.returncode, p.stdout + p.stderr
        except Exception as e:
            return 1, str(e)

    if request.method == "POST":
        action = request.form.get("action", "commit")
        message = request.form.get("message", f"DAYMARK sync {datetime.now().isoformat()}")

        # Ensure data dir is tracked
        run(["git", "add", "data/"])
        if action == "commit":
            code, out = run(["git", "status", "--porcelain"])
            if not out.strip():
                result = {"ok": True, "msg": "Nothing to commit", "log": out}
            else:
                code, out = run(["git", "commit", "-m", message])
                result = {
                    "ok": code == 0,
                    "msg": "Committed" if code == 0 else "Commit failed",
                    "log": out,
                }
        elif action == "push":
            code, out = run(["git", "push"])
            result = {
                "ok": code == 0,
                "msg": "Pushed" if code == 0 else "Push failed (check remote)",
                "log": out,
            }
        elif action == "pull":
            code, out = run(["git", "pull", "--rebase"])
            result = {
                "ok": code == 0,
                "msg": "Pulled" if code == 0 else "Pull failed",
                "log": out,
            }
        elif action == "status":
            code, out = run(["git", "status"])
            result = {"ok": True, "msg": "Status", "log": out}

        if request.headers.get("HX-Request"):
            return render_template("partials/sync_result.html", result=result)
        flash(result["msg"], "success" if result["ok"] else "error")
        return redirect(url_for("git_sync"))

    # GET: show status
    code, status_out = run(["git", "status", "--short"])
    code2, log_out = run(["git", "log", "--oneline", "-5"])
    return render_template(
        "sync.html",
        status=status_out,
        recent=log_out,
        is_git=(repo_root / ".git").exists(),
    )


@app.route("/api/stats")
def api_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    done = db.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
    today = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE due_date=? AND status!='done'",
        (today_str(),),
    ).fetchone()[0]
    return jsonify({"total": total, "done": done, "today": today})


# ---------- Bootstrap ----------

@app.before_request
def ensure_db():
    init_db()


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    # init with app context
    with app.app_context():
        init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
