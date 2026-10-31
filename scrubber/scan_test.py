import sys
from pathlib import Path

import requests

SCAN_URL = "http://127.0.0.1:8000/analyze-csv"
CSV_FILES = [
    "messy_data_one.csv",
    "messy_data_two.csv",
    "messy_data_three.csv",
]
PROVIDER = "gemini"  # or "groq"


def scan_csv(path: Path) -> dict:
    csv_data = path.read_text(encoding="utf-8")
    response = requests.post(
        SCAN_URL,
        json={"csv_data": csv_data, "provider": PROVIDER},
        timeout=120,  # LLM calls can be slow
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    base_dir = Path(__file__).parent
    failures = 0

    for name in CSV_FILES:
        path = base_dir / name
        print("=" * 70)
        print(f"Scanning: {name}")
        print("=" * 70)

        if not path.exists():
            print(f"  FILE NOT FOUND: {path}\n")
            failures += 1
            continue

        try:
            result = scan_csv(path)
        except requests.HTTPError as e:
            print(f"  HTTP error: {e}\n  {e.response.text}\n")
            failures += 1
            continue
        except requests.RequestException as e:
            print(f"  Request failed: {e}\n")
            failures += 1
            continue

        # Validate the response shape: {"ok": bool, "report": str}
        assert set(result) == {"ok", "report"}, f"Unexpected keys: {set(result)}"
        assert isinstance(result["ok"], bool), "'ok' must be a boolean"
        assert isinstance(result["report"], str) and result["report"], "'report' must be a non-empty string"

        print(f"ok (no further cleaning needed): {result['ok']}\n")
        print(result["report"])
        print()

    print("-" * 70)
    print(f"Done. {len(CSV_FILES) - failures}/{len(CSV_FILES)} files scanned successfully.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())