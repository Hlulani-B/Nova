import json
import sys
from pathlib import Path

import requests

# FastAPI streaming endpoint URL
API_URL = "http://127.0.0.1:8000/analyze-csv/stream"

# Preferred provider: "gemini" or "groq" (the server falls back to the other on failure)
PROVIDER = "groq"

# Max seconds to wait between events (not for the whole report)
READ_TIMEOUT = 120

csv_files = [
    "messy_data_one.csv",
    "messy_data_two.csv",
    "messy_data_three.csv",
]


def stream_analysis(filename: str, csv_content: str) -> None:
    payload = {"csv_data": csv_content, "provider": PROVIDER}

    with requests.post(
        API_URL,
        json=payload,
        stream=True,
        timeout=(5, READ_TIMEOUT),  # (connect, read-between-chunks)
    ) as response:
        if response.status_code != 200:
            print(f"❌ API Error [{response.status_code}] for {filename}: {response.text}\n")
            return

        event = None
        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            if raw_line.startswith("event:"):
                event = raw_line[len("event:"):].strip()
            elif raw_line.startswith("data:"):
                data = json.loads(raw_line[len("data:"):].strip())

                if event == "status":
                    print(f"\n⏳ {data['message']}")
                elif event == "meta":
                    print(f"📐 Rows: {data['rows']}, Columns: {data['columns']}")
                elif event == "provider":
                    print(f"🤖 Provider: {data['name']}\n" + "-" * 60)
                elif event == "token":
                    sys.stdout.write(data["text"])
                    sys.stdout.flush()
                elif event == "fallback":
                    print(f"\n⚠️ {data['failed']} failed: {data['error']}")
                elif event == "done":
                    print(f"\n{'-' * 60}\n✅ Done (provider: {data['provider_used']})")
                elif event == "error":
                    print(f"\n❌ Error: {data['message']}")
            # blank lines separate events; nothing to do


def run_tests():
    print("🚀 Starting Streaming CSV Analysis Test Suite...\n")

    for filename in csv_files:
        file_path = Path(filename)

        if not file_path.exists():
            print(f"⚠️ Warning: {filename} not found in the directory. Skipping...")
            continue

        print(f"📂 {filename}")
        try:
            csv_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}\n")
            continue

        try:
            stream_analysis(filename, csv_content)
        except requests.exceptions.ReadTimeout:
            print(f"\n⏱️ No data received for {READ_TIMEOUT}s. Check the server logs.")
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Make sure your FastAPI server is running (`uvicorn main:app --reload`)!\n")
            break
        except Exception as e:
            print(f"❌ Unexpected error occurred: {e}")

        print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()