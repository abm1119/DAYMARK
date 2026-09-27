# DAYMARK

Portable HTMX + SQLite daily task app with calendar, categories, and Git sync.

## Features

- **Day view** – focus on today (or any day), overdue callouts
- **Calendar** – month grid with task density dots
- **All tasks** – search + filter by status / category
- **Categories** – Job (TA), Learning, Research, Repos, Projects, Blogs, AI Engineering (pre-seeded). Full CRUD
- **Tasks** – title, notes, due date, status (todo/doing/done/blocked), priority 1–4. Inline status change via HTMX
- **Git sync** – commit `data/` (the SQLite file), push/pull from the UI
- **Workspace UI** – Notion-inspired warm neutrals, compact navigation, and responsive task surfaces

## Quick start

```bash
cd todo-app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

Data lives in `data/todo.db`. That folder is what you commit for history.

## Git workflow (edge sync)

```bash
git init
git add .
git commit -m "init DAYMARK"
# add remote, then use the Sync page or:
git add data/
git commit -m "daily tasks"
git push
```

On another machine: clone, run the app, use Sync → Pull.

## Portable

- Single process, no Docker required
- SQLite file travels with the repo
- No external services

## Stack

Flask · HTMX · SQLite · Tailwind CDN
