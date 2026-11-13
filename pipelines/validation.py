"""Checks that a pipeline definition is a valid DAG before it is saved."""


class ValidationError(Exception):
    pass


def validate_pipeline(data):
    """`data` looks like:
    {"name": "...", "tasks": [{"name": "a", "duration": 1, "fail_rate": 0, "depends_on": ["b"]}]}

    Returns a cleaned copy or raises ValidationError.
    """
    if not isinstance(data, dict):
        raise ValidationError("Body must be a JSON object.")

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValidationError("Pipeline name is required.")

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValidationError("A pipeline needs at least one task.")

    cleaned = []
    seen = set()
    for i, t in enumerate(tasks, start=1):
        if not isinstance(t, dict):
            raise ValidationError(f"Task #{i} must be an object.")
        tname = str(t.get("name", "")).strip()
        if not tname:
            raise ValidationError(f"Task #{i} needs a name.")
        if tname in seen:
            raise ValidationError(f"Duplicate task name: '{tname}'.")
        seen.add(tname)

        try:
            duration = float(t.get("duration", 1))
            fail_rate = float(t.get("fail_rate", 0))
        except (TypeError, ValueError):
            raise ValidationError(f"Task '{tname}': duration and fail_rate must be numbers.")
        if duration < 0:
            raise ValidationError(f"Task '{tname}': duration can't be negative.")
        if not 0 <= fail_rate <= 1:
            raise ValidationError(f"Task '{tname}': fail_rate must be between 0 and 1.")

        deps = t.get("depends_on") or []
        if not isinstance(deps, list):
            raise ValidationError(f"Task '{tname}': depends_on must be a list.")
        deps = [str(d).strip() for d in deps if str(d).strip()]

        cleaned.append({"name": tname, "duration": duration, "fail_rate": fail_rate, "depends_on": deps})

    for t in cleaned:
        for d in t["depends_on"]:
            if d == t["name"]:
                raise ValidationError(f"Task '{d}' can't depend on itself.")
            if d not in seen:
                raise ValidationError(f"Task '{t['name']}' depends on unknown task '{d}'.")

    check_no_cycles(cleaned)
    return {"name": name, "tasks": cleaned}


def check_no_cycles(tasks):
    """Kahn's algorithm: repeatedly remove tasks with no remaining deps.
    If some tasks can never be removed, they form a cycle."""
    remaining = {t["name"]: set(t["depends_on"]) for t in tasks}
    while True:
        ready = [n for n, deps in remaining.items() if not deps]
        if not ready:
            break
        for n in ready:
            del remaining[n]
        for deps in remaining.values():
            deps.difference_update(ready)
    if remaining:
        names = ", ".join(sorted(remaining))
        raise ValidationError(f"Dependency cycle detected between: {names}.")
