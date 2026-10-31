import requests
from pathlib import Path

# FastAPI endpoint URL
API_URL = "http://127.0.0.1:8000/analyze-csv"

# Preferred provider: "gemini" or "groq" (the server falls back to the other on failure)
PROVIDER = "groq"

# Seconds to wait for the full report (LLM generation + possible fallback)
REQUEST_TIMEOUT = 180

# List of your local CSV files shown in the project tree
csv_files = [
    "messy_data_one.csv",
    "messy_data_two.csv",
    "messy_data_three.csv",
]


def run_tests():
    print("🚀 Starting Automated CSV Analysis Test Suite...\n")

    for filename in csv_files:
        file_path = Path(filename)

        if not file_path.exists():
            print(f"⚠️ Warning: {filename} not found in the directory. Skipping...")
            continue

        print(f"📂 Reading local file: {filename}...")

        # Read the raw text content of the CSV file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                csv_content = f.read()
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}\n")
            continue

        # Prepare the payload for your FastAPI endpoint
        payload = {"csv_data": csv_content, "provider": PROVIDER}

        print(f"🔄 Sending {filename} to FastAPI endpoint ({API_URL})...")

        try:
            response = requests.post(API_URL, json=payload, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ SUCCESS: {filename}")
                print(f"   - Provider Used: {data.get('provider_used')}")
                print(f"   - Rows Analyzed: {data.get('rows_analyzed')}")
                print(f"   - Columns Analyzed: {data.get('columns_analyzed')}")
                print("-" * 60)
                print(f"📊 AI ANALYSIS REPORT FOR {filename}:\n")
                print(data.get("analysis_report"))
                print("=" * 60 + "\n")
            else:
                print(f"❌ API Error [{response.status_code}] for {filename}: {response.text}\n")

        except requests.exceptions.ReadTimeout:
            print(f"⏱️ Timed out after {REQUEST_TIMEOUT}s waiting for {filename}. "
                  "Check the server logs to see which provider is slow.\n")
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Make sure your FastAPI server is running (`uvicorn main:app --reload`)!\n")
            break
        except Exception as e:
            print(f"❌ Unexpected error occurred: {e}\n")


if __name__ == "__main__":
    run_tests()