import unittest
import subprocess
import os
import json
import tempfile
from pathlib import Path

class TestTaskManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, "tasks.json")
        self.env = os.environ.copy()
        self.env["TASKMAN_DB"] = self.db_path

    def tearDown(self):
        self.test_dir.cleanup()

    def run_cmd(self, cmd):
        return subprocess.run(
            ["python3", "taskman.py"] + cmd,
            env=self.env,
            capture_output=True,
            text=True
        )

    def test_1_add(self):
        res = self.run_cmd(["add", "test task"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Task 1 added", res.stdout)

    def test_2_list(self):
        self.run_cmd(["add", "task 1"])
        res = self.run_cmd(["list"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("task 1", res.stdout)
        self.assertIn("○", res.stdout)

    def test_3_done(self):
        self.run_cmd(["add", "task 1"])
        res = self.run_cmd(["done", "1"])
        self.assertEqual(res.returncode, 0)
        res = self.run_cmd(["list"])
        self.assertIn("✔", res.stdout)

    def test_4_rm(self):
        self.run_cmd(["add", "task 1"])
        res = self.run_cmd(["rm", "1"])
        self.assertEqual(res.returncode, 0)
        res = self.run_cmd(["list"])
        self.assertNotIn("task 1", res.stdout)

    def test_5_stats(self):
        self.run_cmd(["add", "t1"])
        self.run_cmd(["add", "t2"])
        self.run_cmd(["done", "1"])
        res = self.run_cmd(["stats"])
        self.assertIn("Total      2", res.stdout)
        self.assertIn("Done       1", res.stdout)

    def test_6_rm_nonexistent(self):
        res = self.run_cmd(["rm", "99"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error", res.stdout)

    def test_7_done_nonexistent(self):
        res = self.run_cmd(["done", "99"])
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error", res.stdout)

    def test_8_list_empty(self):
        res = self.run_cmd(["list"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("No tasks found", res.stdout)

    def test_9_id_persistence(self):
        self.run_cmd(["add", "a"])
        self.run_cmd(["add", "b"])
        self.run_cmd(["rm", "1"])
        self.run_cmd(["add", "c"])
        # ID should be 3, not 2
        with open(self.db_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data[0]["id"], 2)
        self.assertEqual(data[1]["id"], 3)

    def test_10_help(self):
        res = self.run_cmd(["--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage", res.stdout)

if __name__ == "__main__":
    unittest.main()
