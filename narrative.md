# DAYMARK: The Narrative & Architecture

## 1. The Genesis: Why DAYMARK Exists

For two years, the hustle went quiet. The version of me that learned relentlessly, shipped code seamlessly, managed multiple complex streams of work, and stayed grounded as a practicing Muslim slipped away into the background. 

Instead, Abdul fell into procrastination. A habit of leaning on others took root. That was the reality. No excuses.

DAYMARK isn't just a todo app. It is a mirror and a supervision engine. It forces transparency, tracks progress against strict timelines, and keeps me accountable across professional work, self-improvement, and supporting my father at the bakery. It is the bridge to resurrecting the discipline of my past self.

---

## 2. The Vision & Responsibilities

This system anchors four core pillars:
1. **Borlo Labs Revision & Bootcamp Launch** – Rebuilding technical depth and teaching it forward.
2. **Portfolio Website Development** – Showcasing real craft and engineering competence.
3. **Trubblx** – Turning raw ideas into deployed reality.
4. **Prologware Solutions** – Bringing the venture back to active life.

### Immediate Action (Tomorrow)
- **BakeryOS:** Complete development and deploy live for KBB.
- **Bakery Wall:** Frame the FBR NTN number, print posters, and mount them securely.
- **Learning:** Resume technical studies right where I left off, with uncompromising pace.

---

## 3. The Architecture: Portable, Fast, and Minimal

DAYMARK is designed around zero friction. No bloated cloud services, no heavy client-side JavaScript frameworks, no Docker overhead. Just clean, direct code that lives entirely on the machine and travels with the repository.

```
DAYMARK/
├── app.py              # Flask core controller & SQLite database manager
├── data/
│   └── todo.db         # Local SQLite database (the source of truth)
├── static/
│   ├── app.css         # Notion-inspired warm neutral styling (Vanilla CSS)
│   └── daymark_logo.png# Workspace branding
├── templates/
│   ├── base.html       # Workbench layout frame
│   ├── day.html        # Daily focus & overdue tracking
│   ├── calendar.html   # Monthly density grid
│   ├── tasks.html      # Filterable master task list
│   └── partials/       # HTMX dynamic rendering partials
└── design.md           # Design system spec
```

### Technical Stack
- **Backend:** Python / Flask (lightweight, single-process, routing and SQLite execution).
- **Database:** SQLite (`data/todo.db`). Foreign keys enforced, indexes optimized for due dates, status, and categories. Every single task state change is securely stored locally.
- **Frontend / Interaction:** HTML templates powered by **HTMX**. When checking off a task, changing priority, or updating status, requests are sent asynchronously (`fetch`), swapping out targeted HTML partials (`partials/task_card.html`) without full page reloads.
- **Styling:** Vanilla CSS using a warm-neutral design system (`--color-paper`, `--color-ink`, `--color-accent`) inspired by Notion's quiet workspaces.
- **Sync & Portability:** Git version control. Committing the `data/` folder turns Git into a sync engine between machines. Pull, push, and review task history directly from the UI.

---

## 4. Execution Protocol

DAYMARK runs on strict feedback loops:
- **Day View:** Focuses entirely on today. Overdue tasks are flagged immediately so nothing slips through the cracks.
- **Categories:** Grouped cleanly into Job (TA), Learning, Research, Repos, Projects, Blogs, and AI Engineering.
- **Git Sync:** Committing daily database changes locks in accountability.

The tools are ready. The system is live. Time to execute.
