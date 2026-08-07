import json
import os
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Use environment variable for DB path, default to local tasks.json
DB_FILE = os.getenv("TASKMAN_DB", "tasks.json")

def load_tasks():
    path = Path(DB_FILE)
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def save_tasks(tasks):
    with open(DB_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def add_task(args):
    tasks = load_tasks()
    new_id = max([t['id'] for t in tasks], default=0) + 1
    task = {
        "id": new_id,
        "title": args.title,
        "done": False,
        "created_at": datetime.now().isoformat()
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"✔ Task {new_id} added: '{args.title}'")

def list_tasks(args):
    tasks = load_tasks()
    if not tasks:
        print("No tasks found.")
        return
    print(f"{'ID':<4} {'Status':<10} {'Title'}")
    print("-" * 40)
    for t in tasks:
        status = "✔" if t['done'] else "○"
        print(f"{t['id']:<4} {status:<10} {t['title']}")

def done_task(args):
    tasks = load_tasks()
    found = False
    for t in tasks:
        if t['id'] == args.id:
            t['done'] = True
            found = True
            break
    if found:
        save_tasks(tasks)
        print(f"✔ Task {args.id} marked as complete.")
    else:
        print(f"✘ Error: Task {args.id} not found.")
        sys.exit(1)

def rm_task(args):
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t['id'] != args.id]
    if len(tasks) == len(new_tasks):
        print(f"✘ Error: Task {args.id} not found.")
        sys.exit(1)
    else:
        save_tasks(new_tasks)
        print(f"✔ Task {args.id} removed.")

def stats_task(args):
    tasks = load_tasks()
    total = len(tasks)
    done = sum(1 for t in tasks if t['done'])
    pending = total - done
    print("--- Task Statistics ---")
    print(f"{'Total':<10} {total}")
    print(f"{'Done':<10} {done}")
    print(f"{'Pending':<10} {pending}")

def main():
    parser = argparse.ArgumentParser(description="TaskMan: A simple CLI task manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_p = subparsers.add_parser("add", help="Add a new task")
    add_p.add_argument("title", help="Task title")

    list_p = subparsers.add_parser("list", help="List all tasks")

    done_p = subparsers.add_parser("done", help="Mark a task as done")
    done_p.add_argument("id", type=int, help="Task ID")

    rm_p = subparsers.add_parser("rm", help="Remove a task")
    rm_p.add_argument("id", type=int, help="Task ID")

    stats_p = subparsers.add_parser("stats", help="Show task statistics")

    args = parser.parse_args()

    commands = {
        "add": add_task,
        "list": list_tasks,
        "done": done_task,
        "rm": rm_task,
        "stats": stats_task
    }
    commands[args.command](args)

if __name__ == "__main__":
    main()
