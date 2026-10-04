import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import app as daymark


class TimeSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = daymark.DB_PATH
        self.original_data_dir = daymark.DATA_DIR
        self.original_testing = daymark.app.config.get("TESTING")
        daymark.DATA_DIR = Path(self.temp_dir.name)
        daymark.DB_PATH = daymark.DATA_DIR / "test.db"
        daymark.app.config["TESTING"] = True
        self.client = daymark.app.test_client()
        with daymark.app.app_context():
            daymark.init_db()

    def tearDown(self):
        daymark.DB_PATH = self.original_db_path
        daymark.DATA_DIR = self.original_data_dir
        daymark.app.config["TESTING"] = self.original_testing
        self.temp_dir.cleanup()

    def create_task(self, title, due_date="2026-10-05", start_time="", end_time="", **extra):
        data = {
            "title": title,
            "due_date": due_date,
            "start_time": start_time,
            "end_time": end_time,
            "status": "todo",
            "priority": "2",
            "repeat_unit": "none",
            "repeat_interval": "1",
            "repeat_count": "1",
        }
        data.update(extra)
        return self.client.post("/task/new", data=data)

    def task_rows(self):
        with daymark.app.app_context():
            return daymark.get_db().execute(
                "SELECT * FROM tasks ORDER BY due_date, start_time, id"
            ).fetchall()

    def test_accepts_valid_24_hour_slots_and_rejects_invalid_values(self):
        self.assertEqual(
            daymark.validate_time_slot("2026-10-05", "00:00", "23:59"),
            ("00:00", "23:59"),
        )
        for start, end in (
            ("9:00", "10:00"),
            ("24:00", "25:00"),
            ("12:60", "13:00"),
            ("12:00:00", "13:00"),
            ("10:00", "10:00"),
            ("11:00", "10:00"),
            ("09:00", ""),
        ):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    daymark.validate_time_slot("2026-10-05", start, end)
        with self.assertRaisesRegex(ValueError, "planned date"):
            daymark.validate_time_slot(None, "09:00", "10:00")

    def test_rejects_overlaps_but_allows_back_to_back_slots(self):
        self.assertEqual(self.create_task("First", start_time="09:00", end_time="10:00").status_code, 302)
        self.assertEqual(self.create_task("Adjacent", start_time="10:00", end_time="10:30").status_code, 302)

        response = self.create_task("Overlap", start_time="09:59", end_time="11:00")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"overlaps", response.data)
        self.assertEqual(len(self.task_rows()), 2)

    def test_recurring_slots_are_carried_to_each_occurrence(self):
        response = self.create_task(
            "Daily review",
            start_time="08:30",
            end_time="09:00",
            repeat_unit="day",
            repeat_interval="1",
            repeat_count="3",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [(row["due_date"], row["start_time"], row["end_time"]) for row in self.task_rows()],
            [
                ("2026-10-05", "08:30", "09:00"),
                ("2026-10-06", "08:30", "09:00"),
                ("2026-10-07", "08:30", "09:00"),
            ],
        )

    def test_recurring_deadlines_keep_the_same_offset_from_each_planned_date(self):
        response = self.create_task(
            "Weekly report",
            due_date="2026-10-05",
            deadline="2026-10-07",
            repeat_unit="week",
            repeat_interval="1",
            repeat_count="3",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [(row["due_date"], row["deadline"]) for row in self.task_rows()],
            [
                ("2026-10-05", "2026-10-07"),
                ("2026-10-12", "2026-10-14"),
                ("2026-10-19", "2026-10-21"),
            ],
        )

    def test_assistant_can_suggest_open_slots_around_existing_bookings(self):
        self.create_task("Morning focus", start_time="09:00", end_time="10:00")
        self.create_task("Stand-up", start_time="10:30", end_time="11:00")

        with daymark.app.app_context():
            slots = daymark.run_agent_tool(
                daymark.get_db(),
                "find_open_slots",
                {
                    "due_date": "2026-10-05",
                    "window_start": "08:00",
                    "window_end": "12:00",
                    "duration_minutes": 30,
                },
            )

        self.assertEqual(
            slots,
            [
                {"start_time": "08:00", "end_time": "08:30"},
                {"start_time": "10:00", "end_time": "10:30"},
                {"start_time": "11:00", "end_time": "11:30"},
            ],
        )

    def test_assistant_saves_and_reports_a_booked_task(self):
        first_message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call-create",
                "type": "function",
                "function": {
                    "name": "create_task",
                    "arguments": json.dumps({
                        "title": "Focused reading",
                        "due_date": "2026-10-05",
                        "start_time": "13:00",
                        "end_time": "13:30",
                    }),
                },
            }],
        }
        final_message = {"role": "assistant", "content": "Booked focused reading."}

        class FakeResponse:
            def __init__(self, message):
                self.message = message

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return json.dumps({"choices": [{"message": self.message}]}).encode()

        with daymark.app.app_context():
            db = daymark.get_db()
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                with patch.object(
                    daymark.urllib.request,
                    "urlopen",
                    side_effect=[FakeResponse(first_message), FakeResponse(final_message)],
                ) as open_url:
                    conversation_id = str(uuid.uuid4())
                    reply, actions = daymark.groq_agent_reply(
                        [{"role": "user", "content": "Book focused reading"}],
                        db,
                        conversation_id,
                    )

            request_obj = open_url.call_args_list[0].args[0]
            self.assertEqual(request_obj.get_header("Authorization"), "Bearer test-key")
            request_payload = json.loads(request_obj.data)
            self.assertIn("do not guess the date", request_payload["messages"][0]["content"])
            saved_task = db.execute(
                "SELECT title, due_date, start_time, end_time FROM tasks WHERE title=?",
                ("Focused reading",),
            ).fetchone()

        self.assertEqual(reply, "Booked focused reading.")
        self.assertEqual(
            dict(saved_task),
            {
                "title": "Focused reading",
                "due_date": "2026-10-05",
                "start_time": "13:00",
                "end_time": "13:30",
            },
        )
        self.assertEqual(
            actions,
            [{
                "tool": "create_task",
                "ok": True,
                "result": {
                    "created": 1,
                    "title": "Focused reading",
                    "dates": ["2026-10-05"],
                    "start_time": "13:00",
                    "end_time": "13:30",
                },
            }],
        )
        history = self.client.get(
            f"/api/agent/history?conversation_id={conversation_id}"
        ).get_json()["events"]
        self.assertEqual([event["type"] for event in history], ["action"])
        self.assertEqual(history[0]["result"]["title"], "Focused reading")

    def test_agent_conversation_is_persisted_and_resumed_across_requests(self):
        conversation_id = str(uuid.uuid4())
        seen_contexts = []

        def fake_reply(messages, db, received_conversation_id):
            seen_contexts.append(messages)
            self.assertEqual(received_conversation_id, conversation_id)
            return f"Reply {len(seen_contexts)}", []

        with patch.object(daymark, "groq_agent_reply", side_effect=fake_reply):
            first = self.client.post(
                "/api/agent",
                json={"conversation_id": conversation_id, "message": "Plan my day"},
            )
            second = self.client.post(
                "/api/agent",
                json={"conversation_id": conversation_id, "message": "What about tomorrow?"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            seen_contexts[1],
            [
                {"role": "user", "content": "Plan my day"},
                {"role": "assistant", "content": "Reply 1"},
                {"role": "user", "content": "What about tomorrow?"},
            ],
        )
        history_response = self.client.get(
            f"/api/agent/history?conversation_id={conversation_id}"
        )
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(
            [(event["role"], event["content"]) for event in history_response.get_json()["events"]],
            [
                ("user", "Plan my day"),
                ("assistant", "Reply 1"),
                ("user", "What about tomorrow?"),
                ("assistant", "Reply 2"),
            ],
        )
        log_path = daymark.DATA_DIR / daymark.AGENT_HISTORY_NAME
        self.assertTrue(log_path.is_file())
        self.assertTrue(all(
            json.loads(line)["conversation_id"] == conversation_id
            for line in log_path.read_text(encoding="utf-8").splitlines()
        ))

    def test_clearing_chat_history_keeps_saved_memories(self):
        conversation_id = str(uuid.uuid4())
        with daymark.app.app_context():
            daymark.run_agent_tool(
                daymark.get_db(),
                "remember_memory",
                {"content": "Prefers short morning planning sessions"},
            )
        daymark.append_agent_event({
            "type": "message",
            "conversation_id": conversation_id,
            "role": "user",
            "content": "Remember this conversation",
        })

        response = self.client.delete("/api/agent/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"cleared": True})
        self.assertEqual(
            self.client.get(
                f"/api/agent/history?conversation_id={conversation_id}"
            ).get_json()["events"],
            [],
        )
        with daymark.app.app_context():
            db = daymark.get_db()
            memories = daymark.run_agent_tool(db, "list_memories", {})
            task_database_memories = db.execute(
                "SELECT name FROM main.sqlite_master WHERE name = 'assistant_memories'"
            ).fetchall()
        self.assertEqual(memories[0]["content"], "Prefers short morning planning sessions")
        self.assertEqual(task_database_memories, [])
        self.assertTrue((daymark.DATA_DIR / "assistant_memory.db").is_file())
        self.assertEqual(
            (daymark.DATA_DIR / daymark.AGENT_HISTORY_NAME).read_text(encoding="utf-8"),
            "",
        )

    def test_agent_widget_exposes_history_controls_and_provider_notice(self):
        response = self.client.get("/day")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="agent-history-clear"', response.data)
        self.assertIn(b"Prompts go to Groq", response.data)
        self.assertIn(b"data/assistant_history.log", response.data)

    def test_agent_memory_can_be_saved_found_and_forgotten_but_not_secret(self):
        with daymark.app.app_context():
            db = daymark.get_db()
            saved = daymark.run_agent_tool(
                db,
                "remember_memory",
                {"content": "Prefers concise weekly plans"},
            )
            found = daymark.run_agent_tool(db, "list_memories", {})
            searched = daymark.run_agent_tool(
                db,
                "search_memories",
                {"query": "WEEKLY PLANS"},
            )
            with self.assertRaisesRegex(ValueError, "secrets"):
                daymark.run_agent_tool(
                    db,
                    "remember_memory",
                    {"content": "Remember my API key"},
                )
            forgotten = daymark.run_agent_tool(
                db,
                "forget_memory",
                {"memory_id": saved["memory_id"]},
            )
            remaining = daymark.run_agent_tool(db, "list_memories", {})

        self.assertEqual(found[0]["content"], "Prefers concise weekly plans")
        self.assertEqual(searched[0]["id"], saved["memory_id"])
        self.assertEqual(forgotten["forgotten"], saved["memory_id"])
        self.assertEqual(remaining, [])

    def test_saved_memory_is_included_in_later_assistant_context(self):
        first_response = {"role": "assistant", "content": "I’ll keep that in mind."}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return json.dumps({"choices": [{"message": first_response}]}).encode()

        with daymark.app.app_context():
            db = daymark.get_db()
            daymark.run_agent_tool(
                db,
                "remember_memory",
                {"content": "Prefers concise morning check-ins"},
            )
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                with patch.object(
                    daymark.urllib.request, "urlopen", return_value=FakeResponse()
                ) as open_url:
                    daymark.groq_agent_reply(
                        [{"role": "user", "content": "What do you remember?"}],
                        db,
                    )

        prompt = json.loads(open_url.call_args.args[0].data)["messages"][0]["content"]
        self.assertIn("Prefers concise morning check-ins", prompt)
        self.assertIn("untrusted reference data", prompt)

    def test_agent_task_briefing_reports_overdue_today_and_upcoming_tasks(self):
        today = daymark.date.today()
        self.create_task("Overdue review", due_date=(today - daymark.timedelta(days=1)).isoformat())
        self.create_task("Today's review", due_date=today.isoformat())
        self.create_task("Upcoming review", due_date=(today + daymark.timedelta(days=3)).isoformat())
        self.create_task("Done review", due_date=today.isoformat(), status="done")

        with daymark.app.app_context():
            briefing = daymark.run_agent_tool(daymark.get_db(), "get_task_briefing", {})

        self.assertEqual(briefing["as_of"], today.isoformat())
        self.assertEqual([task["title"] for task in briefing["overdue"]], ["Overdue review"])
        self.assertEqual([task["title"] for task in briefing["due_today"]], ["Today's review"])
        self.assertEqual([task["title"] for task in briefing["upcoming"]], ["Upcoming review"])

    def test_agent_requires_explicit_task_id_confirmation_before_deletion(self):
        first_message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call-delete",
                "type": "function",
                "function": {
                    "name": "delete_task",
                    "arguments": json.dumps({"task_id": 1}),
                },
            }],
        }
        final_message = {"role": "assistant", "content": "The task was not deleted."}

        class FakeResponse:
            def __init__(self, message):
                self.message = message

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return json.dumps({"choices": [{"message": self.message}]}).encode()

        self.create_task("Keep this task")
        with daymark.app.app_context():
            db = daymark.get_db()
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                with patch.object(
                    daymark.urllib.request,
                    "urlopen",
                    side_effect=[FakeResponse(first_message), FakeResponse(final_message)],
                ):
                    reply, actions = daymark.groq_agent_reply(
                        [{"role": "user", "content": "Don't delete task 1"}],
                        db,
                    )
            remaining = db.execute(
                "SELECT title FROM tasks WHERE id = 1"
            ).fetchone()

        self.assertEqual(reply, "The task was not deleted.")
        self.assertFalse(actions[0]["ok"])
        self.assertIn("Confirm delete 1", actions[0]["result"]["error"])
        self.assertEqual(remaining["title"], "Keep this task")

    def test_recurring_series_cadence_is_visible_on_task_cards(self):
        self.create_task(
            "Daily review",
            repeat_unit="day",
            repeat_count="2",
        )

        response = self.client.get("/tasks")

        self.assertIn(b"Every day", response.data)
        self.assertIn(b"2 total", response.data)

    def test_recurring_creation_is_atomic_when_a_future_slot_conflicts(self):
        self.create_task(
            "Existing",
            due_date="2026-10-06",
            start_time="09:00",
            end_time="10:00",
        )

        response = self.create_task(
            "Daily review",
            start_time="09:00",
            end_time="10:00",
            repeat_unit="day",
            repeat_interval="1",
            repeat_count="3",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"overlaps", response.data)
        self.assertEqual([row["title"] for row in self.task_rows()], ["Existing"])

    def test_day_and_all_task_views_order_tasks_by_date_and_time(self):
        self.create_task(
            "Previous day",
            due_date="2026-10-04",
            start_time="20:00",
            end_time="21:00",
        )
        self.create_task("Later", start_time="15:00", end_time="15:30")
        self.create_task("Flexible", start_time="", end_time="")
        self.create_task("Earlier", start_time="09:00", end_time="10:00")

        day_response = self.client.get("/day/2026-10-05")
        day_body = day_response.data.decode()
        self.assertLess(day_body.index("Earlier"), day_body.index("Later"))
        self.assertLess(day_body.index("Later"), day_body.index("Flexible"))
        self.assertIn("Timeline · 24-hour clock", day_body)
        self.assertIn("Any time", day_body)

        task_response = self.client.get("/tasks")
        task_body = task_response.data.decode()
        self.assertLess(task_body.index("Previous day"), task_body.index("Earlier"))
        self.assertLess(task_body.index("Earlier"), task_body.index("Later"))
        self.assertLess(task_body.index("Later"), task_body.index("Flexible"))

    def test_edit_form_renders_empty_optional_dates_and_times_cleanly(self):
        self.create_task("Flexible task")
        task = self.task_rows()[0]

        response = self.client.get(f"/task/{task['id']}/edit")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'value="None"', response.data)

    def test_new_task_form_labels_repeat_controls_and_defaults_to_once(self):
        response = self.client.get("/task/new")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Repeat pattern", response.data)
        self.assertIn(b"Total occurrences", response.data)
        self.assertIn(b"Does not repeat", response.data)
        self.assertIn(b'id="repeat-fields"', response.data)
        self.assertIn(b"repeatFields.hidden = repeatUnit.value === 'none'", response.data)

    def test_edit_allows_its_current_slot_and_rejects_other_task_overlap(self):
        self.create_task("First", start_time="09:00", end_time="10:00")
        self.create_task("Second", start_time="10:00", end_time="11:00")
        first = self.task_rows()[0]

        unchanged = self.client.post(
            f"/task/{first['id']}/edit",
            data={
                "title": "First",
                "due_date": first["due_date"],
                "start_time": first["start_time"],
                "end_time": first["end_time"],
                "status": "todo",
                "priority": "2",
            },
        )
        self.assertEqual(unchanged.status_code, 302)

        updated = self.client.post(
            f"/task/{first['id']}/edit",
            data={
                "title": "First",
                "due_date": first["due_date"],
                "start_time": "08:00",
                "end_time": "09:00",
                "status": "todo",
                "priority": "2",
            },
        )
        self.assertEqual(updated.status_code, 302)
        self.assertEqual(self.task_rows()[0]["start_time"], "08:00")

        response = self.client.post(
            f"/task/{first['id']}/edit",
            data={
                "title": "First",
                "due_date": first["due_date"],
                "start_time": "09:30",
                "end_time": "10:30",
                "status": "todo",
                "priority": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"overlaps", response.data)
        self.assertEqual(self.task_rows()[0]["start_time"], "08:00")

    def test_edit_persists_all_task_fields(self):
        self.create_task("Draft")
        task = self.task_rows()[0]
        with daymark.app.app_context():
            category_id = daymark.get_db().execute(
                "SELECT id FROM categories ORDER BY id LIMIT 1"
            ).fetchone()["id"]

        response = self.client.post(
            f"/task/{task['id']}/edit",
            data={
                "title": "Revised task",
                "description": "Updated notes",
                "category_id": str(category_id),
                "due_date": "2026-10-06",
                "deadline": "2026-10-08",
                "start_time": "11:00",
                "end_time": "11:45",
                "status": "doing",
                "priority": "4",
            },
        )

        self.assertEqual(response.status_code, 302)
        updated = self.task_rows()[0]
        self.assertEqual(updated["title"], "Revised task")
        self.assertEqual(updated["description"], "Updated notes")
        self.assertEqual(updated["category_id"], category_id)
        self.assertEqual(updated["due_date"], "2026-10-06")
        self.assertEqual(updated["deadline"], "2026-10-08")
        self.assertEqual((updated["start_time"], updated["end_time"]), ("11:00", "11:45"))
        self.assertEqual(updated["status"], "doing")
        self.assertEqual(updated["priority"], 4)

    def test_invalid_category_does_not_create_a_partial_task(self):
        response = self.create_task("No category", category_id="999999")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"valid category", response.data)
        self.assertEqual(self.task_rows(), [])

    def test_assistant_can_create_update_and_list_task_times(self):
        with daymark.app.app_context():
            db = daymark.get_db()
            daymark.run_agent_tool(
                db,
                "create_task",
                {
                    "title": "Assistant task",
                    "due_date": "2026-10-05",
                    "start_time": "13:00",
                    "end_time": "14:00",
                },
            )
            task = db.execute(
                "SELECT id FROM tasks WHERE title = ?", ("Assistant task",)
            ).fetchone()
            daymark.run_agent_tool(
                db,
                "update_task",
                {
                    "task_id": task["id"],
                    "start_time": "14:00",
                    "end_time": "15:00",
                },
            )
            listed = daymark.run_agent_tool(db, "list_tasks", {"query": "Assistant"})

        self.assertEqual(listed[0]["start_time"], "14:00")
        self.assertEqual(listed[0]["end_time"], "15:00")

    def test_existing_database_migration_preserves_tasks(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript("""
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#6366f1',
                icon TEXT DEFAULT '📁',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                category_id INTEGER,
                due_date TEXT,
                deadline TEXT,
                series_id TEXT,
                recurrence_unit TEXT,
                recurrence_interval INTEGER DEFAULT 1,
                recurrence_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'todo',
                priority INTEGER DEFAULT 2,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );
            INSERT INTO tasks (title, due_date) VALUES ('Legacy task', '2026-10-05');
        """)
        connection.close()
        daymark.DB_PATH = legacy_path

        with daymark.app.app_context():
            daymark.init_db()
            task = daymark.get_db().execute(
                "SELECT title, due_date, start_time, end_time FROM tasks"
            ).fetchone()

        self.assertEqual(task["title"], "Legacy task")
        self.assertEqual(task["due_date"], "2026-10-05")
        self.assertIsNone(task["start_time"])
        self.assertIsNone(task["end_time"])


if __name__ == "__main__":
    unittest.main()
