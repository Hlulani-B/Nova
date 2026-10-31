import io
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

DATA_DIR = Path(__file__).parent
CSV_FILES = [
    "messy_data_one.csv",
    "messy_data_two.csv",
    "messy_data_three.csv",
]


def read_sse(csv_data: str, max_rounds: int = 5) -> list[tuple[str, dict]]:
    """POST to the stream endpoint and return the list of (event, data) pairs."""
    events = []
    event_name = None
    with client.stream(
        "POST",
        "/clean-csv/stream",
        json={"csv_data": csv_data, "max_rounds": max_rounds},
        timeout=600,
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event: "):
                event_name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
                events.append((event_name, data))
                if event_name == "status":          # show progress live
                    print(f"[status] {data['message']}", flush=True)
    return events


def log_events(filename: str, events: list[tuple[str, dict]]) -> None:
    """console.log the report and code as they arrived."""
    print("\n" + "#" * 70)
    print(f"# {filename}")
    print("#" * 70)

    for name, data in events:
        if name == "report":
            print("\n" + "=" * 70)
            print(f"REPORT (round {data['round']}) ok={data['ok']}")
            print("=" * 70)
            print(data["report"])
        elif name == "code":
            print("\n" + "-" * 70)
            print(f"CODE (round {data['round']}, attempt {data['attempt']})")
            print("-" * 70)
            print(data["code"])
        elif name == "error":
            print(f"\n[ERROR] {data['message']}")
        elif name == "done":
            print("\n" + "=" * 70)
            print(f"DONE: ok={data['ok']} rounds={data['rounds']} reason={data['reason']}")
            print("=" * 70)
            print(data["csv"])


@pytest.mark.parametrize("filename", CSV_FILES)
def test_pipeline_cleans_messy_file(filename):
    path = DATA_DIR / filename
    assert path.exists(), f"Missing test file: {path}"

    raw = path.read_text(encoding="utf-8")
    events = read_sse(raw)
    log_events(filename, events)

    names = [n for n, _ in events]
    errors = [d["message"] for n, d in events if n == "error"]
    assert not errors, errors

    # The stream has the pieces we expect
    assert "report" in names, "no report event was streamed"
    assert "code" in names, "messy data should have triggered the cleaner"
    assert names[-1] == "done"

    done = events[-1][1]
    assert done["ok"] is True, done["reason"]

    # The first scan flagged the messy file
    reports = [d for n, d in events if n == "report"]
    assert reports[0]["ok"] is False

    # The final CSV string really is clean (hard checks, not the AI's opinion)
    df = pd.read_csv(io.StringIO(done["csv"]))
    original = pd.read_csv(io.StringIO(raw), on_bad_lines="skip")

    assert len(df) > 0, "cleaned CSV is empty"
    assert list(df.columns) == list(original.columns), "column names changed"
    assert not df.duplicated().any(), "duplicates remain"
    assert not df.isnull().any().any(), "missing values remain"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))