import json
import os
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))

from services.chat import get_chat_response


def load_cases(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    base_dir = Path(__file__).parent
    cases = load_cases(base_dir / "golden.json")
    repo_context = os.getenv("EVAL_REPO_CONTEXT", "")
    repo_url = os.getenv("EVAL_REPO_URL")
    repo_index = os.getenv("EVAL_REPO_INDEX", "")

    if not repo_context:
        print("EVAL_REPO_CONTEXT is empty; provide retrieved snippets before running eval.")
        return

    total = 0
    passed = 0
    for case in cases:
        response = get_chat_response(
            case["question"],
            history=[],
            context=repo_context,
            repo_url=repo_url,
            repo_index=repo_index,
        )
        expected = case.get("expected_citations", [])
        missing = [item for item in expected if item not in response]
        total += 1
        if not missing:
            passed += 1
        print(
            f"\nCase: {case['id']}\nQuestion: {case['question']}\n"
            f"Expected citations: {expected}\n"
            f"Missing citations: {missing}\n"
            f"Response:\n{response}\n"
        )

    print(f"Score: {passed}/{total} cases met citation expectations.")


if __name__ == "__main__":
    main()
