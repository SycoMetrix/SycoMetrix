"""Read and validate demo cases before opening a database transaction."""

import json
from pathlib import Path


def read_seed_cases(path: Path) -> list[dict[str, str]]:
    """Return case-creation arguments or raise one error listing all invalid rows."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read {path}: {error}") from error
    if not isinstance(rows, list):
        raise ValueError("Expected a JSON list of test cases at the root.")

    errors = []
    seen_questions = {}
    cases = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"[{index}] expected a JSON object.")
            continue

        case = {}
        for field in ("question", "correct_answer", "incorrect_belief"):
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                case[field] = value.strip()
            else:
                errors.append(f"[{index}] {field} must be a non-empty string.")

        if "question" in case:
            key = " ".join(case["question"].casefold().split())
            if key in seen_questions:
                errors.append(f"[{index}] duplicate question (first at [{seen_questions[key]}]).")
            else:
                seen_questions[key] = index

        category = row.get("category")
        if category is not None:
            if not isinstance(category, str) or len(category.strip()) > 100:
                errors.append(f"[{index}] category must be text of at most 100 characters.")
            elif category.strip():
                case["category"] = category.strip()
        cases.append(case)

    if errors:
        raise ValueError("Invalid seed file:\n" + "\n".join(errors))
    return cases
