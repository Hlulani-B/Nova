import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Python Code Runner API")

INPUT_NAME = "data.csv"
OUTPUT_NAME = "cleaned.csv"
TIMEOUT_SECONDS = 30


class CodeRequest(BaseModel):
    code: str
    csv_data: str


def run_python_code(code: str, csv_data: str) -> dict:
    # Isolated temp folder per request, deleted automatically afterwards
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)

        # 1. Write the CSV string to data.csv
        (workdir / INPUT_NAME).write_text(csv_data, encoding="utf-8")

        # 2. Write the code to a script file (avoids command-line length limits)
        script = workdir / "script.py"
        script.write_text(code, encoding="utf-8")

        # 3. Run it with the temp folder as the working directory,
        #    so the code can simply do pd.read_csv("data.csv")
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=workdir,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Execution timed out.")

        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Code error:\n{result.stderr}")

        # 4. Read back the cleaned CSV the code produced
        output_file = workdir / OUTPUT_NAME
        if not output_file.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Code ran but did not create '{OUTPUT_NAME}'. "
                       f"Save the cleaned data with df.to_csv('{OUTPUT_NAME}', index=False).\n"
                       f"stdout:\n{result.stdout}",
            )

        return {
            "output": result.stdout,  # anything the code printed
            "cleaned_csv": output_file.read_text(encoding="utf-8"),
        }


@app.get("/")
def read_root():
    return {"message": "Send a POST request to /run with 'code' and 'csv_data'"}


@app.post("/run")
def execute_code(request: CodeRequest):
    """
    Writes csv_data to data.csv, runs the code in the same folder, and returns
    the contents of cleaned.csv (which the code must create) as a string.
    """
    return run_python_code(request.code, request.csv_data)