import io
import json
import re
import time
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env should contain:
#    GEMINI_TOKEN=your_gemini_key
#    GROQ_TOKEN=your_groq_key
#    OPEN_TOKEN=your_openrouter_key
class Settings(BaseSettings):
    gemini_token: str
    groq_token: str
    open_token: str

    # Fallback lists per provider, tried in order. A model that fails is skipped.
    gemini_models: list[str] = [
        "gemini-3.8-flash",        # unverified, kept in case your key has access
        "gemini-3.5-flash",        # unverified, kept in case your key has access
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",        # may already be shut down
        "gemini-2.5-flash-lite",   # may already be shut down
    ]
    groq_models: list[str] = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
    ]
    openrouter_models: list[str] = [
        "deepseek/deepseek-chat:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
    ]

    provider_timeout: float = 60.0   # client-level ceiling
    model_timeout: float = 25.0      # max seconds for ONE model attempt
    provider_budget: float = 50.0    # stop trying more models of a provider after this many seconds
    max_output_tokens: int = 6000

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
app = FastAPI(title="CSV Scan API")

gemini_client = genai.Client(
    api_key=settings.gemini_token,
    http_options=types.HttpOptions(timeout=int(settings.provider_timeout * 1000)),  # ms
)
# max_retries=0: the model/provider fallback chain IS the retry. SDK retries multiply the waits.
groq_client = Groq(
    api_key=settings.groq_token,
    timeout=settings.provider_timeout,
    max_retries=0,
)  # seconds

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.open_token,
    timeout=settings.provider_timeout,
    max_retries=0,
    default_headers={
        "HTTP-Referer": "https://github.com/Hlulani-B",
        "X-Title": "CSV Scan API",
    },
)

ALL_PROVIDERS = ["gemini", "groq", "openrouter"]


class CSVAnalysisRequest(BaseModel):
    csv_data: str
    provider: Literal["gemini", "groq", "openrouter"] = "gemini"


SYSTEM_PERSONA = (
    "You are a meticulous, elite Senior Data Analyst with an expert eye for anomalies, "
    "data hygiene issues, statistical trends, and business insights. "
    "You respond ONLY with a single valid JSON object and nothing else."
)

EDA_INSTRUCTIONS = (
    "Perform an exhaustive, deep, and rigorous Exploratory Data Analysis (EDA) on the dataset profile below. "
    "You must analyze the data from two dimensions:\n"
    "1. Column-by-Column Individual Breakdown: Examine every single column in isolation. Understand its semantic meaning, "
    "expected format, distribution, unique characteristics, whitespace/padding issues, case inconsistencies, and corrupt or stray tokens.\n"
    "2. Holistic Cross-Column & Dataset Synthesis: Understand the dataset as a cohesive whole. Deduce business logic, "
    "relational constraints, and dependencies between columns (e.g., mathematical relationships like Total = Quantity * Price, "
    "chronological order of dates, categorical alignment, mixed currencies or units).\n\n"
    "CRITICAL REQUIREMENT: Meticulously evaluate what makes logical sense and what doesn't. "
    "Explicitly point out specific values, corrupt tokens, formatting mismatches, and logical contradictions that do not belong. "
    "Highlight exact records, rows, or column intersections where data is malformed or violates real-world business expectations, "
    "and explain precisely why it fails logic. Use the COLUMN VALUE PROFILE section: it lists the most common values "
    "and formats of every column across ALL rows, so it reveals mixed currencies, mixed date formats and spelling variants "
    "that summary statistics hide.\n\n"
    "Return a JSON object with EXACTLY these two keys:\n"
    '  "ok": a boolean. true ONLY if the dataset needs NO further cleaning and is ready to use. '
    "false if any cleaning is still required (missing values, duplicates, wrong types, "
    "inconsistent formatting, mixed currencies or units, invalid values, outliers that are errors, logical mismatches, etc.).\n"
    '  "report": a string (markdown allowed) with your professional analysis, using these sections: '
    "Dataset Overview & Metadata Summary, Column-by-Column Deep Dive, Key Observations & Patterns Noticed, "
    "Data Quality Issues & Anomalies Found, Required Data Fixes & Cleaning Steps, "
    "Actionable Recommendations. Be specific about WHICH columns need WHICH fix. "
    "If ok is true, say so and keep the fixes section brief. "
    "Keep the report under about 1400 words.\n\n"
    "Output raw JSON only: no markdown fences, no commentary before or after."
)


# ---------------------------------------------------------------------------
# CSV parsing + profiling
# ---------------------------------------------------------------------------
def parse_csv(csv_data: str) -> tuple[pd.DataFrame, int]:
    if not csv_data or not csv_data.strip():
        raise HTTPException(status_code=400, detail="csv_data is empty")

    try:
        df = pd.read_csv(io.StringIO(csv_data))
        skipped = 0
    except Exception:
        try:
            skipped_lines = []
            df = pd.read_csv(
                io.StringIO(csv_data),
                engine="python",
                on_bad_lines=lambda row: skipped_lines.append(row),
            )
            skipped = len(skipped_lines)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {e}")

    if df.shape[1] == 0:
        raise HTTPException(status_code=400, detail="CSV has no columns")
    return df, skipped


def _shape_of(value: str) -> str:
    """Pattern of a value: letters -> 'a', digits -> '9' (e.g. '2024-07-22' -> '9999-99-99')."""
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]+", "a", value.strip()))


def column_profile(df: pd.DataFrame, max_values: int = 8, max_chars: int = 6000) -> str:
    """Per-column top values and format patterns over ALL rows (reveals mixed units/formats)."""
    lines: list[str] = []
    for col in df.columns:
        series = df[col]
        head = (
            f"- {col} [{series.dtype}] unique={series.nunique(dropna=True)} "
            f"nulls={int(series.isna().sum())}"
        )

        if pd.api.types.is_bool_dtype(series):
            lines.append(head)
            continue
        if pd.api.types.is_numeric_dtype(series):
            nums = series.dropna()
            if not nums.empty:
                head += f" min={nums.min()} max={nums.max()}"
            lines.append(head)
            continue

        s = series.dropna().astype(str)
        if not s.empty:
            top = s.value_counts().head(max_values)
            head += "\n    top values: " + ", ".join(f"{v!r} x{c}" for v, c in top.items())
            shapes = s.map(_shape_of).value_counts()
            if 1 < len(shapes) <= 8:
                head += "\n    format patterns: " + ", ".join(
                    f"{p!r} x{c}" for p, c in shapes.head(5).items()
                )
        lines.append(head)

    return "\n".join(lines)[:max_chars]


def build_prompt(df: pd.DataFrame, skipped_lines: int) -> str:
    buffer = io.StringIO()
    df.info(buf=buffer)

    stats = df.describe(include="all").to_string() if len(df) else "(no rows)"
    sample = df.head(5).to_markdown() if len(df) else "(no rows)"

    context = (
        f"--- DATASET SHAPE ---\nRows: {df.shape[0]}, Columns: {df.shape[1]}\n\n"
        f"--- MALFORMED LINES SKIPPED WHILE PARSING ---\n{skipped_lines}\n\n"
        f"--- COLUMNS & TYPES (df.info) ---\n{buffer.getvalue()}\n\n"
        f"--- MISSING VALUES PER COLUMN ---\n{df.isnull().sum().to_string()}\n\n"
        f"--- DUPLICATE ROWS ---\n{int(df.duplicated().sum())}\n\n"
        f"--- COLUMN VALUE PROFILE (top values and formats, all rows) ---\n{column_profile(df)}\n\n"
        f"--- STATISTICAL SUMMARY (df.describe) ---\n{stats}\n\n"
        f"--- FIRST 5 ROWS (Sample) ---\n{sample}"
    )
    return f"{EDA_INSTRUCTIONS}\n\nHere is the underlying dataset profile:\n{context}"


def hard_checks_pass(df: pd.DataFrame, skipped_lines: int) -> bool:
    if skipped_lines > 0:
        return False
    if df.isnull().any().any():
        return False
    if df.duplicated().any():
        return False
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            continue
        s = df[col].dropna().astype(str)
        if s.str.strip().eq("").any():
            return False
    return True


# ---------------------------------------------------------------------------
# Generic multi-provider, multi-model text generation (used by scan AND scrubber)
# ---------------------------------------------------------------------------
def _models_for(provider: str) -> list[str]:
    if provider == "gemini":
        return settings.gemini_models
    if provider == "groq":
        return settings.groq_models
    if provider == "openrouter":
        return settings.openrouter_models
    raise ValueError(f"Unknown provider: {provider}")


def _generate_with_model(provider: str, model: str, system: str, prompt: str, json_mode: bool) -> str:
    max_tokens = settings.max_output_tokens

    if provider == "gemini":
        cfg = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
            # per-attempt timeout (ms) so one slow model can't stall the whole chain
            "http_options": types.HttpOptions(timeout=int(settings.model_timeout * 1000)),
        }
        if json_mode:
            cfg["response_mime_type"] = "application/json"
        # thinking_budget is only valid on thinking-capable models (2.5+)
        if "2.5" in model or re.search(r"gemini-[3-9]", model):
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**cfg),
        )
        return response.text or ""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "timeout": settings.model_timeout,   # per-attempt timeout (seconds)
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    if provider == "groq":
        # reasoning_effort is only supported by the gpt-oss models
        if "gpt-oss" in model:
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        completion = groq_client.chat.completions.create(**kwargs)
    else:  # openrouter
        completion = openrouter_client.chat.completions.create(**kwargs)

    return completion.choices[0].message.content or ""


def generate_text(provider: str, system: str, prompt: str, json_mode: bool = False) -> str:
    """
    Try the models of ONE provider in order. Each attempt has its own timeout, and no new
    attempt starts once provider_budget seconds are used up. Raises if nothing answers.
    """
    models = _models_for(provider)
    started = time.time()
    last_error = "no models configured"

    for i, model in enumerate(models, start=1):
        if time.time() - started > settings.provider_budget:
            print(f"[ai] time budget used up after {time.time() - started:.0f}s, moving on", flush=True)
            break

        t0 = time.time()
        try:
            text = _generate_with_model(provider, model, system, prompt, json_mode)
            if text.strip():
                print(f"[ai] model {i}/{len(models)} answered in {time.time() - t0:.1f}s", flush=True)
                return text
            last_error = "empty response"
        except Exception as e:
            last_error = str(e)

        print(
            f"[ai] model {i}/{len(models)} failed after {time.time() - t0:.1f}s: {last_error[:200]}",
            flush=True,
        )

    raise RuntimeError(f"All {provider} models failed. Last error: {last_error}")


def call_provider_with_model_fallbacks(provider: str, prompt: str) -> str:
    return generate_text(provider, SYSTEM_PERSONA, prompt, json_mode=True)


def provider_order(preferred: str) -> list[str]:
    return [preferred] + [p for p in ALL_PROVIDERS if p != preferred]


# ---------------------------------------------------------------------------
# LLM output parsing
# ---------------------------------------------------------------------------
def parse_llm_json(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)

    try:
        data = json.loads(text, strict=False)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
        try:
            data = json.loads(text[start : end + 1], strict=False)
        except json.JSONDecodeError as e:
            raise ValueError(f"Model output was not valid JSON (possibly truncated): {e}")

    if not isinstance(data, dict) or "ok" not in data or "report" not in data:
        raise ValueError("JSON missing required keys 'ok' and 'report'")

    ok = data["ok"]
    if isinstance(ok, str):
        ok = ok.strip().lower() == "true"
    elif not isinstance(ok, bool):
        raise ValueError(f"'ok' must be a boolean, got {type(ok).__name__}")

    return {"ok": ok, "report": str(data["report"])}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.post("/analyze-csv")
def analyze_csv_data(request: CSVAnalysisRequest):
    df, skipped_lines = parse_csv(request.csv_data)
    prompt = build_prompt(df, skipped_lines)

    if hard_checks_pass(df, skipped_lines):
        prompt += (
            "\n\nAUTOMATED CHECKS PASSED: no missing values, duplicate rows, blank strings "
            "or malformed lines. Set ok=true unless you can name a specific, concrete error "
            "that remains (for example mixed currencies, mixed date formats, or an impossible value). "
            "Do NOT set ok=false for style preferences or for outliers that are plausible real data."
        )

    errors = {}
    for provider in provider_order(request.provider):
        try:
            raw = call_provider_with_model_fallbacks(provider, prompt)
            result = parse_llm_json(raw)

            if result["ok"] and not hard_checks_pass(df, skipped_lines):
                result["ok"] = False
            return result
        except Exception as e:
            errors[provider] = str(e)

    raise HTTPException(status_code=500, detail=f"All AI providers and model chains failed: {errors}")