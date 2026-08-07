"""sutradhara: skills.py.

Teaches skill discovery: a skill is a directory holding a SKILL.md, found by
walking workdir/skills/ once. Only its description goes in the system prompt
up front — the full body loads on demand, so idle skills cost nothing.
"""

import os

SKILLS_DIR = "skills"


def catalog(workdir):
    """Map skill name -> {"description", "path"} for every workdir/skills/<name>/SKILL.md."""
    root = os.path.join(workdir, SKILLS_DIR)
    found = {}
    if not os.path.isdir(root):
        return found
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, "SKILL.md")
        if os.path.isfile(path):
            found[name] = {"description": _description(path), "path": path}
    return found


def _description(path):
    """Read the description: line out of a SKILL.md's --- front matter, if any."""
    with open(path, encoding="utf-8") as f:
        in_front_matter = False
        for line in f:
            stripped = line.strip()
            if stripped == "---":
                if in_front_matter:
                    break
                in_front_matter = True
                continue
            if in_front_matter and stripped.startswith("description:"):
                return stripped[len("description:"):].strip()
    return ""


def catalog_prompt(workdir):
    """Render the skills catalog as system-prompt text, or "" when there are none."""
    skills = catalog(workdir)
    if not skills:
        return ""
    lines = ["Skills available (load one with the use_skill tool when relevant):"]
    lines += [f"- {name}: {info['description']}" for name, info in skills.items()]
    return "\n".join(lines)


def read_skill(workdir, name):
    """Return a skill's full SKILL.md text, or an ERROR message listing what exists."""
    skills = catalog(workdir)
    if name not in skills:
        available = ", ".join(sorted(skills)) or "(none)"
        return f"ERROR: no skill named {name}. Available: {available}"
    with open(skills[name]["path"], encoding="utf-8") as f:
        return f.read()
