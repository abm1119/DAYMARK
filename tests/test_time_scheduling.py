import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_assistant_prompt_includes_current_local_datetime_and_offset(self):
        fixed_now = datetime(
            2026, 10, 4, 17, 35, tzinfo=timezone(timedelta(hours=5))
        )
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"choices":[{"message":{"content":"Ready."}}]}'

        with daymark.app.app_context():
            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                with patch.object(daymark, "datetime") as datetime_mock:
                    datetime_mock.now.return_value = fixed_now
                    with patch.object(
                        daymark.urllib.request, "urlopen", return_value=response
                    ) as urlopen:
                        daymark.groq_agent_reply(
                            [{"role": "user", "content": "Schedule a task later today"}],
                            daymark.get_db(),
                        )

        payload = json.loads(urlopen.call_args.args[0].data)
        system_message = payload["messages"][0]["content"]
        self.assertIn("2026-10-04T17:35+05:00", system_message)
        self.assertIn("Interpret relative dates and times using this local context", system_message)

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
