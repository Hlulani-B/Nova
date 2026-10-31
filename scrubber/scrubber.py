import io
import re

import pandas as pd
from fastapi import HTTPException

from scan import column_profile, generate_text, provider_order
from code_runner import run_python_code  # your old subprocess.py, renamed

SAMPLE_LINES = 30
CODE_SYSTEM = (
    "You are a senior data engineer. You respond with ONLY runnable Python code: "
    "no explanations, no markdown commentary."
)


class CleaningError(Exception):
    pass


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def build_code_prompt(scan_report, overview, csv_data, previous_code=None, last_error=None) -> str:
    sample = "\n".join(csv_data.splitlines()[:SAMPLE_LINES])

    # What the data REALLY looks like, computed over every row (not just the sample)
    try:
        df = pd.read_csv(io.StringIO(csv_data), on_bad_lines="skip")
        profile = column_profile(df)
    except Exception:
        profile = "(unavailable)"

    prompt = (
        "Write a complete Python script that cleans a messy CSV file.\n\n"
        f"ENVIRONMENT: pandas {pd.__version__} (pandas 3.x semantics, Copy-on-Write is ON).\n"
        "   - NEVER use inplace=True and NEVER use chained assignment like df['a'].fillna(0, inplace=True). "
        "They silently do nothing.\n"
        "   - ALWAYS assign results back: df['a'] = df['a'].fillna(0); df['b'] = df['b'].str.strip().\n"
        "   - String columns use the 'str' dtype, so missing values are NaN: check with isna().\n\n"
        "RULES:\n"
        '1. Read the input with pd.read_csv("data.csv") from the current directory. '
        'Be defensive: use on_bad_lines="skip" if rows may be ragged.\n'
        "2. Fix every problem in the scan report and overview below so that a re-scan finds NONE of these:\n"
        "   - missing values. Remember pandas treats 'N/A', 'NA', 'null', 'none', '-' and '' as missing, "
        "so replace or convert them. Fill numeric columns with the median.\n"
        "   - CRITICAL RULE ON TEXT/CATEGORICAL MISSINGS & NORMALIZATION: NEVER use the word 'Unknown' as a lazy fallback. "
        "Use your brain and apply common sense based on surrounding data context. For example, if a categorical column contains "
        "variations like 'MALE', 'male', 'm', and 'M', normalize them intelligently to a consistent title-case form (e.g., 'Male') "
        "instead of creating messy separate categories or dumping placeholder text. Infer missing categorical values logically "
        "from other correlated columns if possible, or derive them from common-sense data distributions.\n"
        "   - duplicate rows (drop them AFTER normalising text so near-duplicates match)\n"
        "   - blank strings, or leading/trailing whitespace\n"
        "   - inconsistent casing or formats (e.g. 'new york ' vs 'New York', use Title Case)\n"
        "   - numbers stored as text (convert to numeric with pd.to_numeric(..., errors='coerce'), "
        "then fill any resulting NaN)\n"
        "   Only strip leading/trailing whitespace and collapse repeated inner spaces to ONE space. "
        "NEVER remove spaces inside a value ('New York' must stay 'New York').\n"
        "3. SEMANTIC FIXES. Use the COLUMN VALUE PROFILE and the scan report below to find and fix:\n"
        "   - CURRENCIES: if a column mixes currencies, convert every monetary amount to ONE base "
        "currency (USD unless the file clearly uses another). Put a RATES dict at the top of the "
        "script with approximate fixed rates to USD: EUR 1.08, GBP 1.27, ZAR 0.055, JPY 0.0067, "
        "INR 0.012, CAD 0.73, AUD 0.65, CNY 0.14, CHF 1.12. If the file already has an "
        "exchange-rate column, use that instead. Overwrite the amount column with the converted "
        "values and set the currency column to the base currency code for EVERY row.\n"
        "   - FLOATS: round all float columns to 2 decimals (removes noise like 112.45300000000002).\n"
        "   - DATES: parse with pd.to_datetime(..., format='mixed', errors='coerce') and write as "
        "ISO YYYY-MM-DD. If an end date is before its start date (e.g. discharge before admission), "
        "swap the two values for that row.\n"
        "   - IMPOSSIBLE VALUES: negative amounts or prices -> fix the sign (abs); ages outside 0-120 -> "
        "replace with the column median.\n"
        "4. Keep the ORIGINAL column names unchanged. Do not add or remove columns.\n"
        '5. Right before saving, assert there are no missing values: assert not df.isna().any().any()\n'
        '6. Save the result with df.to_csv("cleaned.csv", index=False).\n'
        "7. Use only pandas, numpy and the standard library. No network, no input().\n"
        "8. Output ONLY the Python code.\n\n"
        f"--- COLUMN VALUE PROFILE (computed over ALL rows) ---\n{profile}\n\n"
        f"--- SCAN REPORT ---\n{scan_report}\n\n"
        f"--- OVERVIEW ---\n{overview}\n\n"
        f"--- RAW CSV (first {SAMPLE_LINES} lines) ---\n{sample}\n"
    )

    if previous_code and last_error:
        prompt += (
            "\n--- YOUR PREVIOUS ATTEMPT FAILED ---\n"
            f"Code:\n{previous_code}\n\nProblem:\n{last_error}\n\n"
            "Fix the problem and output the complete corrected script. Check that every "
            "transformation is assigned back to the DataFrame.\n"
        )
    return prompt


# ---------------------------------------------------------------------------
# AI code generation (provider + model fallback lives in scan.generate_text)
# ---------------------------------------------------------------------------
def extract_code(text: str) -> str:
    """Pull the Python code out of the model reply (handles ```python fences)."""
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    code = (match.group(1) if match else text).strip()
    code = re.sub(r"^```(?:python|py)?\s*", "", code, flags=re.IGNORECASE).strip()
    if not code:
        raise ValueError("No code found in model output")
    return code


def generate_cleaning_code(prompt: str, provider: str) -> str:
    errors = {}
    for p in provider_order(provider):
        try:
            raw_text = generate_text(p, CODE_SYSTEM, prompt, json_mode=False)
            return extract_code(raw_text)
        except Exception as e:
            errors[p] = str(e)
    print(f"All AI providers and model chains failed: {errors}", flush=True)
    raise CleaningError("Could not write cleaning code. Please try again.")


# ---------------------------------------------------------------------------
# Safety net: fills any missing values the AI script forgot
# ---------------------------------------------------------------------------
SAFETY_NET = '''# safety net: fill any remaining missing values intelligently without dumping generic placeholder text
for _c in df.columns:
    if df[_c].isna().any():
        _s = df[_c]
        if pd.api.types.is_datetime64_any_dtype(_s):
            df[_c] = _s.fillna(pd.Timestamp("2000-01-01"))
        elif pd.api.types.is_bool_dtype(_s):
            df[_c] = _s.fillna(False)
        elif pd.api.types.is_numeric_dtype(_s):
            _m = _s.median()
            _m = 0 if pd.isna(_m) else _m
            if pd.api.types.is_integer_dtype(_s):
                _m = int(round(_m))
            df[_c] = _s.fillna(_m)
        else:
            # Use mode if available to keep common-sense integrity instead of 'Unknown'
            _mode = _s.mode()
            _fallback = _mode.iloc[0] if not _mode.empty else "Missing"
            df[_c] = _s.astype("object").fillna(_fallback)
'''


def add_safety_net(code: str) -> str:
    """Insert the fill loop before the missing value assert (or before saving)."""
    for pattern in (
        r"^[ \t]*assert\s+not\s+df\.isna\(\)\.any\(\)\.any\(\).*$",
        r"^[ \t]*df\.to_csv\(\s*[\"']cleaned\.csv[\"'].*$",
    ):
        new_code, n = re.subn(
            pattern, lambda m: SAFETY_NET + m.group(0), code, count=1, flags=re.MULTILINE
        )
        if n:
            return new_code
    return code


# ---------------------------------------------------------------------------
# Validation of the cleaned output
# ---------------------------------------------------------------------------
def find_problems(cleaned: str) -> list[str]:
    """Check the cleaned CSV the same way the scan does. Empty list means it's clean."""
    df = pd.read_csv(io.StringIO(cleaned))
    problems = []

    if df.empty:
        return ["cleaned.csv is empty"]

    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if not nulls.empty:
        problems.append(
            f"Missing values remain: {nulls.to_dict()}. Fill or drop them before saving "
            "(remember to assign results back: df[col] = df[col].fillna(...))."
        )

    if df.duplicated().any():
        problems.append(f"{int(df.duplicated().sum())} duplicate rows remain.")

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            continue
        s = df[col].dropna().astype(str)      # dropna: NaN must not count as "whitespace"
        if (s.str.strip() != s).any():
            problems.append(f"Column '{col}' still has leading/trailing whitespace.")
        if (s.str.strip() == "").any():
            problems.append(f"Column '{col}' still has blank strings.")

    return problems


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def clean_csv(
    scan,
    overview: str,
    csv_data: str,
    provider: str = "gemini",
    max_attempts: int = 3,
    on_code=None,
    on_progress=None,
) -> str:
    """
    scan        - result of analyze_csv_data ({"ok", "report"}) or the report string
    overview    - output of generate_csv_overview()
    csv_data    - the raw CSV string
    on_code     - optional callback, called with every cleaning script the AI writes
    on_progress - optional callback, called with human-readable progress messages
    Returns the cleaned CSV as a string, or raises CleaningError.
    """
    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    scan_report = scan["report"] if isinstance(scan, dict) else str(scan)

    previous_code, last_error = None, None
    for attempt in range(1, max_attempts + 1):
        tag = f"Attempt {attempt}/{max_attempts}"

        progress(f"{tag}: writing cleaning code...")
        prompt = build_code_prompt(scan_report, overview, csv_data, previous_code, last_error)
        code = add_safety_net(generate_cleaning_code(prompt, provider))

        if on_code:
            on_code(code)   # sent to the frontend over SSE, exactly as it will run
        progress(f"{tag}: got {len(code.splitlines())} lines of code, running it...")

        try:
            result = run_python_code(code, csv_data)    # writes data.csv, runs, reads cleaned.csv
            cleaned = result["cleaned_csv"]

            problems = find_problems(cleaned)
            if not problems:
                progress(f"{tag}: cleaned CSV passed all checks")
                return cleaned

            # Ran fine but the output still isn't clean: send the problems back
            previous_code = code
            last_error = (
                "The script ran, but the cleaned CSV still has problems:\n"
                + "\n".join(problems)
            )
            progress(f"{tag}: output still has {len(problems)} problem(s): " + "; ".join(problems))

        except HTTPException as e:                      # crash / timeout / no output file
            previous_code, last_error = code, str(e.detail)
            lines = last_error.strip().splitlines()
            progress(f"{tag}: script failed: {lines[-1] if lines else 'unknown error'}")
        except Exception as e:                          # unreadable cleaned csv
            previous_code, last_error = code, f"cleaned.csv was invalid: {e}"
            progress(f"{tag}: cleaned.csv was invalid: {e}")

    raise CleaningError(
        f"Cleaning failed after {max_attempts} attempts.\n"
        f"Last error:\n{last_error}\n\n"
        f"Last generated code:\n{previous_code}"
    )