# DAYMARK

## About

DAYMARK is a portable, single-process daily task workspace and uncompromising supervision engine built with Flask, HTMX, and SQLite. Rooted in local-first reliability, offline availability, and edge synchronization via Git, it serves as a digital mirror enforcing radical transparency and unrelenting discipline across professional work, technical research, and self-improvement domains. By combining server-rendered hypermedia templates with a Notion-inspired warm neutral aesthetic and an integrated Groq AI assistant, DAYMARK eliminates cloud bloat and friction, delivering a lightning-fast, distraction-free environment designed to resurrect deep focus and absolute accountability.

## Important

- **Local-First Source of Truth:** All task data, categories, and state transitions reside entirely in `data/todo.db`. Never introduce external cloud persistence or remove local SQLite WAL mode and foreign key enforcement.
- **Frontend & Backend Synchronization:** Whenever a new field, status, or category attribute is added to the database or backend model in `app.py`, it must be fully supported across HTML templates (`templates/`) and UI partials (`templates/partials/`) so the interface remains completely in sync.
- **AI Agent Guardrails:** The Groq-backed assistant (`/api/agent`) relies on strict tool schemas (`list_tasks`, `create_task`, `update_task`, `delete_task`). Destructive actions like deletion require explicit user intent ("delete" or "remove" keywords) to prevent accidental data loss.
- **Git Synchronization Integrity:** The SQLite database file (`data/todo.db`) is tracked directly in Git version control to enable seamless multi-machine syncing via `/sync`. Commit database changes cleanly with descriptive messages.
- **Design System Consistency:** All views adhere strictly to the minimalist, Notion-inspired design tokens defined in `design.md` (warm neutral surfaces, OKLCH color tokens, Inter typography, and stable 34-38px control heights).

---

## Architecture & Technology Stack
- **Backend:** Python 3, Flask (`app.py`), serving server-rendered HTML templates.
- **Frontend / Interaction:** HTML5 templates with **HTMX** for hypermedia-driven asynchronous updates (in-place status changes, dynamic partial swapping without full page reloads).
- **Styling:** Vanilla CSS using a Notion-inspired warm neutral design system (`design.md`) with OKLCH color tokens, Inter typography, and compact controls.
- **Persistence:** SQLite 3 (`data/todo.db`) with WAL mode, foreign keys enabled, and optimized indexes on due dates, deadlines, statuses, categories, and series.
- **AI Integration:** Groq-powered chat agent (`/api/agent`) equipped with tool-calling capabilities to manage the workspace via natural language.
- **Sync & Portability:** Local Git version control integration (`/sync`) for tracking and syncing the database across machines.

---

## Database Schema & Business Logic

### 1. Categories Table (`categories`)
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `name`: TEXT NOT NULL UNIQUE (e.g., Job (TA), Learning, Research, Repos, Projects, Blogs, AI Engineering)
- `color`: TEXT DEFAULT '#6366f1'
- `icon`: TEXT DEFAULT '📁'
- `sort_order`: INTEGER DEFAULT 0
- `created_at`: TEXT

### 2. Tasks Table (`tasks`)
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `title`: TEXT NOT NULL
- `description`: TEXT DEFAULT ''
- `category_id`: INTEGER (Foreign Key to `categories.id` ON DELETE SET NULL)
- `due_date`: TEXT (YYYY-MM-DD planned date)
- `deadline`: TEXT (YYYY-MM-DD optional hard deadline)
- `series_id`: TEXT (UUID grouping recurring task occurrences)
- `recurrence_unit`: TEXT ('none', 'day', 'week', 'month')
- `recurrence_interval`: INTEGER DEFAULT 1
- `recurrence_count`: INTEGER DEFAULT 1
- `status`: TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'doing', 'done', 'blocked'))
- `priority`: INTEGER DEFAULT 2 CHECK(priority BETWEEN 1 AND 4) (1: Low, 2: Med, 3: High, 4: Urgent)
- `created_at`, `updated_at`, `completed_at`: TEXT timestamps

### Core Business Logic Rules
- **Recurring Tasks (`add_task_occurrences`):** Generates multiple task instances spaced by day, week, or month intervals up to `recurrence_count`, linked by a shared `series_id`. Only the first occurrence retains the initial status; subsequent occurrences default to `'todo'`.
- **Overdue Detection:** Tasks whose planned date or deadline is strictly before today and whose status is not `'done'` are surfaced as overdue.
- **Completion Timestamping:** Marking a task as `'done'` automatically records `completed_at`; uncompleting resets it to `NULL`.

---

## Application Routes & Endpoints

- `GET /` — Redirects to `/day`.
- `GET /day`, `GET /day/<day>` — Daily focus workbench view with scheduled tasks, overdue tasks, and day navigation.
- `GET /calendar`, `GET /calendar/<year>/<month>` — Monthly grid calendar view with task status counts per day.
- `GET /tasks` — Filterable master task list by status, category, and text search query.
- `GET/POST /task/new` — Create a new task or recurring series.
- `GET/POST /task/<tid>/edit` — Edit task details, status, dates, and priority.
- `POST /task/<tid>/status` — Update task status asynchronously (returns HTMX task card partial).
- `POST /task/<tid>/delete` — Delete a task.
- `GET /categories`, `GET/POST /category/new`, `GET/POST /category/<cid>/edit`, `POST /category/<cid>/delete` — Category taxonomy management.
- `GET/POST /sync` — Git synchronization dashboard (status, commit, push, pull).
- `POST /api/agent` — Groq AI assistant endpoint for natural language task management.
- `GET /api/stats` — JSON statistics endpoint (total, done, today's pending tasks).

## Skills

* Always load and use `hallmark`, `Taste-skills`, `tool-ui` skills.


## Frontend / Backend Sync

* Whenever a new field is added to a backend model or database entity that is surfaced in the frontend (e.g. settings panels), it must also be handled in the corresponding frontend component so the two stay in sync. This is a convention/reminder only — there is no automatic syncing mechanism; the frontend enumerates fields explicitly.

## Planning/Spec-ing

Always Use Tracer bullets approach for creating specs

> Use Tracer bullets comes from the Pragmatic Programmer. When building systems, you want to write code that gets you feedback as quickly as possible. Tracer bullets are small slices of functionality that go through all layers of the system, allowing you to test and validate your approach early. This helps in identifying potential issues and ensures that the overall architecture is sound before investing significant time in development.

create specs in `specs/`. Maintain a PROGRESS.md file to track the progress of the implementation phases.

### Before starting work
* Always in plan mode to make a plan
* After get the plan, make sure you Write the plan to `.agents/tasks/PLAN.md` 
* The plan should be a detailed implementation plan and the reasoning behind them, as well as tasks broken down.
* If the task require external knowledge or certain package, also research to get latest knowledge (Use Task tool for research)
* Don't over plan it, always think MVP.
* Once you write the plan, firstly ask me to review it. Do not continue until I approve the plan.
### While implementing
* You should update the plan as you work.
* After you complete tasks in the plan, you should update and append detailed descriptions of the changes you made, so following tasks can be easily hand over to other engineers.

## Implementation Guidelines

* Create a new branch before working on a new feature/spec (branch name patterns: feat/, fix/, just like conventional commit pre-fixes)
* Reconcile the spec and log the progress after each phase of development
* Commit after each meaningful phase
* Commit the spec before the development commits
* Use comments only when necessary to explain "why?" not "how?", how must be clear from the code itself


## Development Details

### Guidelines for writing good code for a developer
0. Please Do-not Generate patch Fix, always Generate Root Fix Only!
1. Choose clean code over clever code.
2. Write object oriented code as much as possible.
3. Keep function sizes small, ideally 10 lines.
4. Try and keep files between 100 and 300 lines.
5. Don't keep too many files in a folder or module. Try and keep it under 15.
6. Avoid abbreviations.
7. Use standard API as much as possible.
8. Reuse. Write as little code as possible.
9. Use the project's design system or existing UI component library for UI styling.
10. Always write tests, and make sure they work.
11. Build the minimum working app, then iterate towards your goals.
12. Keep the verbosity low in new changes (inline comments, docstrings, etc.).
    Explain only what's absolutely needed in inline comments.
    Actual changes explanation can be part of the commit message.

## Regression tests

* When we fix a bug, add at the very least a Unit test, and verify before/after by temp revert of fix to make sure the test tests what is intended
* For bigger features/workflows, e2e playwright tests are a must.
* also use agent-browser to test in the browser

## Another Details

(Add any additional environment setups, deployment scripts, or miscellaneous rules here)

# Commit or PR Style

### Pull Requests

* The canonical repo is `abm1119/DAYMARK` (git remote upstream). fork (origin) entirely.
    * Branch off upstream/develop (run git fetch upstream develop first), not local/fork develop - the fork's develop is often stale and inflates the diff.
    * Push the feature branch to upstream (`abm1119/DAYMARK`) and raise the PR there: gh pr create --repo `abm1119/DAYMARK` --base develop .... Set gh repo   set-default `abm1119/DAYMARK` so this is the default.
    * Before raising, sanity-check the diff is only your files: git diff --stat upstream/develop..<branch>. A huge diff means you based on or targeted the wrong (fork) develop - fix the base before opening the PR.
    * Raise PR always against the develop branch
    * Keep pull request descriptions stupid simple
* Some formats:
    1.  h2 Problem (1-2 sentences), h2 Solution: good for bugs, etc.
    2.  h2 Why? h2 What? h2 How?: good for new features and enhancements