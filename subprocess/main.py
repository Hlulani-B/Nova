from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import sys

# 1. Initialize the FastAPI app
app = FastAPI(title="Python Code Runner API")

# 2. Define a Pydantic model to validate incoming JSON requests
class CodeRequest(BaseModel):
    code: str

# 3. Helper function to execute code safely via subprocess
def run_python_code(code: str) -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=5  # Safeguard against infinite loops
        )
        
        if result.returncode != 0:
            return f"Error:\n{result.stderr}"
        
        return result.stdout

    except subprocess.TimeoutExpired:
        return "Error: Execution timed out."
    except Exception as e:
        return f"Error: {e}"

# 4. Define API Endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI Code Runner! Send a POST request to /run"}

@app.post("/run")
def execute_code(request: CodeRequest):
    """
    Accepts a JSON payload with a 'code' field, runs it, and returns the output.
    """
    output = run_python_code(request.code)
    return {"output": output}