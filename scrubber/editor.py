import io
import re

import pandas as pd
from fastapi import HTTPException

from scan import column_profile, generate_text, provider_order
from code_runner import run_python_code  # your old subprocess.py, renamed

SAMPLE_LINES = 30

EDIT_SYSTEM = (
    "You are a senior data engineer. You edit CSV files by writing pandas code that follows "
    "the user's instruction exactly. You reply ONLY in the requested <message>/<code> format."
)


class EditError(Exception):
    pass


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def build_edit_prompt(instruction: str, csv_data: str, previous_code=None, last_error=None) -> str:
    sample = "\n".join(csv_data.splitlines()[:SAMPLE_LINES])

    try:
        df = pd.read_csv(io.StringIO(csv_data), on_bad_lines="skip")
        profile = column_profile(df)
        shape = f"{df.shape[0]} rows, {df.shape[1]} columns"
    except Exception:
        profile, shape = "(unavailable)", "unknown"

    prompt = (
        "A user wants to change a CSV file. Write a Python script that applies THEIR instruction.\n\n"
        f"--- USER INSTRUCTION ---\n{instruction}\n\n"
        f"ENVIRONMENT: pandas {pd.__version__} (pandas 3.x semantics, Copy-on-Write is ON).\n"
        "   - NEVER use inplace=True and NEVER use chained assignment. They silently do nothing.\n"
        "   - ALWAYS assign results back: df['a'] = df['a'].str.strip().\n\n"
        "RULES:\n"
        '1. Read the input with pd.read_csv("data.csv", dtype=str, keep_default_na=False) so that '
        "untouched columns stay exactly as they are. Convert a column with "
        "pd.to_numeric(..., errors='coerce') or pd.to_datetime(...) only when the instruction "
        "needs it, and write whole numbers back without a trailing .0.\n"
        "2. Do ONLY what the user asked. Do not clean, reformat, reorder or drop anything else.\n"
        "3. Keep the original column names and the row order unless the instruction says otherwise.\n"
        '4. Save the full resulting table with df.to_csv("cleaned.csv", index=False).\n'
        "5. Use only pandas, numpy and the standard library. No network, no input().\n"
        "6. If the instruction is impossible or unclear, make the most reasonable interpretation "
        "and say so in the message.\n\n"
        "REPLY FORMAT (exactly these two tags, nothing outside them):\n"
        "<message>\n"
        "One to three plain sentences telling the user what you changed (or why you could not). "
        "No code in the message.\n"
        "</message>\n"
        "<code>\n"
        "the complete Python script, with no markdown fences\n"
        "</code>\n\n"
        f"--- CSV SHAPE ---\n{shape}\n\n"
        f"--- COLUMN VALUE PROFILE (all rows) ---\n{profile}\n\n"
        f"--- RAW CSV (first {SAMPLE_LINES} lines) ---\n{sample}\n"
    )

    if previous_code and last_error:
        prompt += (
            "\n--- YOUR PREVIOUS ATTEMPT FAILED ---\n"
            f"Code:\n{previous_code}\n\nProblem:\n{last_error}\n\n"
            "Fix the problem and reply again in the same <message>/<code> format.\n"
        )
    return prompt


# ---------------------------------------------------------------------------
# AI reply: message + code
# ---------------------------------------------------------------------------
def parse_ai_reply(text: str) -> tuple[str, str]:
    """Split the model reply into (message, code). Tolerates missing tags and code fences."""
    msg_m = re.search(r"<message>(.*?)</message>", text, re.DOTALL | re.IGNORECASE)
    code_m = re.search(r"<code>(.*?)</code>", text, re.DOTALL | re.IGNORECASE)

    message = msg_m.group(1).strip() if msg_m else ""

    if code_m:
        code = code_m.group(1)
    else:
        fence = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        code = fence.group(1) if fence else ""
        if not message:
            message = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()

    code = re.sub(r"^```(?:python|py)?\s*|\s*```$", "", code.strip(), flags=re.IGNORECASE).strip()
    if not code:
        raise ValueError("No code found in model reply")

    return (message or "I applied your instruction."), code


def generate_edit_reply(prompt: str, provider: str) -> tuple[str, str]:
    errors = {}
    for p in provider_order(provider):
        try:
            raw = generate_text(p, EDIT_SYSTEM, prompt, json_mode=False)
            return parse_ai_reply(raw)
        except Exception as e:
            errors[p] = str(e)
    print(f"All AI providers and model chains failed: {errors}", flush=True)
    raise EditError("Could not write code for that instruction. Please try again.")


# ---------------------------------------------------------------------------
# Validation of the edited output
# ---------------------------------------------------------------------------
def same_table(a: str, b: str) -> bool:
    """True if two CSV strings hold identical cell values (ignores quoting/line-ending differences)."""
    try:
        da = pd.read_csv(io.StringIO(a), dtype=str, keep_default_na=False)
        db = pd.read_csv(io.StringIO(b), dtype=str, keep_default_na=False)
        return da.equals(db)
    except Exception:
        return False


def check_output(original: str, edited: str, final_attempt: bool) -> list[str]:
    try:
        df = pd.read_csv(io.StringIO(edited))
    except Exception as e:
        return [f"cleaned.csv is not a valid CSV: {e}"]

    if df.shape[1] == 0:
        return ["cleaned.csv has no columns."]
    if df.empty:
        return ["cleaned.csv has no rows: keep the rows unless the instruction asks to delete them."]

    # Identical output usually means the change silently did nothing. Retry, but accept it at the end
    # (the instruction may genuinely require no change).
    if not final_attempt and same_table(original, edited):
        return [
            "The output is identical to the input, so the instruction was not applied. "
            "Make sure every change is assigned back to the DataFrame (no inplace=True, "
            "no chained assignment)."
        ]
    return []


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def edit_csv(
    prompt: str,
    csv_data: str,
    provider: str = "gemini",
    max_attempts: int = 3,
    on_message=None,
    on_code=None,
    on_progress=None,
) -> str:
    """
    prompt       - the user's instruction, e.g. "remove rows where age is under 18"
    csv_data     - the current CSV as a string
    on_message   - optional callback, called with the AI's plain-language message for each attempt
    on_code      - optional callback, called with every script the AI writes
    on_progress  - optional callback, called with human-readable progress messages

    The AI writes a script that reads data.csv and saves cleaned.csv; the script runs in a
    subprocess and the resulting CSV is returned as a string. Failed or no-op attempts are
    sent back to the AI for another try. Raises EditError if it cannot be done.
    """
    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    instruction = (prompt or "").strip()
    if not instruction:
        raise EditError("Please type an instruction first.")
    if not csv_data or not csv_data.strip():
        raise EditError("There is no CSV data to edit.")

    previous_code, last_error = None, None
    for attempt in range(1, max_attempts + 1):
        tag = f"Attempt {attempt}/{max_attempts}"

        progress(f"{tag}: writing code for your instruction...")
        full_prompt = build_edit_prompt(instruction, csv_data, previous_code, last_error)
        message, code = generate_edit_reply(full_prompt, provider)

        if on_message:
            on_message(message)
        if on_code:
            on_code(code)
        progress(f"{tag}: got {len(code.splitlines())} lines of code, running it...")

        try:
            result = run_python_code(code, csv_data)   # writes data.csv, runs, reads cleaned.csv
            edited = result["cleaned_csv"]

            problems = check_output(csv_data, edited, final_attempt=(attempt == max_attempts))
            if not problems:
                progress(f"{tag}: edit applied")
                return edited

            previous_code = code
            last_error = "The script ran, but:\n" + "\n".join(problems)
            progress(f"{tag}: {problems[0]}")

        except HTTPException as e:                      # crash / timeout / no output file
            previous_code, last_error = code, str(e.detail)
            lines = last_error.strip().splitlines()
            progress(f"{tag}: script failed: {lines[-1] if lines else 'unknown error'}")
        except Exception as e:
            previous_code, last_error = code, f"The result could not be read: {e}"
            progress(f"{tag}: result could not be read: {e}")

    print(f"Edit failed after {max_attempts} attempts.\nLast error:\n{last_error}\n"
          f"Last code:\n{previous_code}", flush=True)
    summary = (last_error or "unknown error").strip().splitlines()
    raise EditError(
        f"Could not apply that instruction after {max_attempts} attempts. "
        f"Last problem: {summary[-1][:300] if summary else 'unknown'}"
    )