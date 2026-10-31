import io
import json
from typing import Iterator, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from groq import Groq
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# 1. Load configuration securely from .env
#    .env should contain:
#        GEMINI_TOKEN=your_gemini_key
#        GROQ_TOKEN=your_groq_key
class Settings(BaseSettings):
    gemini_token: str
    groq_token: str

    # Model names are overridable via .env (GEMINI_MODEL / GROQ_MODEL)
    gemini_model: str = "gemini-2.5-flash"
    groq_model: str = "openai/gpt-oss-120b"

    # Per-provider timeout in seconds, so a slow provider fails over quickly
    provider_timeout: float = 60.0

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
app = FastAPI(title="Deep CSV Data Analyst API")

# Initialize provider clients
gemini_client = genai.Client(
    api_key=settings.gemini_token,
    http_options=types.HttpOptions(timeout=int(settings.provider_timeout * 1000)),  # ms
)
groq_client = Groq(api_key=settings.groq_token, timeout=settings.provider_timeout)  # seconds


class CSVAnalysisRequest(BaseModel):
    csv_data: str
    # Preferred provider; the other one is used automatically as a fallback
    provider: Literal["gemini", "groq"] = "gemini"


SYSTEM_PERSONA = (
    "You are a meticulous, elite Senior Data Analyst with an expert eye for anomalies, "
    "data hygiene issues, statistical trends, and business insights."
)

EDA_INSTRUCTIONS = (
    "Perform a deep, rigorous Exploratory Data Analysis (EDA) on the dataset provided below. "
    "Your analysis MUST explicitly cover the following EDA phases:\n"
    "1. **Data Structure & Schema Integrity Check**: Evaluate column types, memory usage, dimensions, and structural appropriateness.\n"
    "2. **Data Hygiene & Missingness Assessment**: Quantify missing values, locate blank strings, and identify structural padding or data corruption risks.\n"
    "3. **Statistical Summary & Distribution Analysis**: Look at central tendencies (mean, median), variance, min/max bounds, and potential skewness or outliers.\n"
    "4. **Cardinality & Uniqueness Inspection**: Evaluate categorical distributions, unique value ratios, and identifier consistency.\n\n"
    "Format your final response as a professional Data Analysis Report with these exact sections:\n"
    "- **Dataset Overview & Metadata Summary**\n"
    "- **Key Observations & Patterns Noticed**\n"
    "- **Data Quality Issues & Anomalies Found**\n"
    "- **Required Data Fixes & Cleaning Steps**\n"
    "- **Actionable Recommendations**"
)


def parse_csv(csv_data: str) -> pd.DataFrame:
    try:
        return pd.read_csv(io.StringIO(csv_data))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {e}")


def build_prompt(df: pd.DataFrame) -> str:
    """Extract structural metrics with pandas and build the full LLM prompt."""
    buffer = io.StringIO()
    df.info(buf=buffer)
    df_info_str = buffer.getvalue()

    summary_stats = df.describe(include="all").to_string()
    missing_values = df.isnull().sum().to_string()
    sample_data = df.head(5).to_markdown()

    context_payload = (
        f"--- DATASET SHAPE ---\nRows: {df.shape[0]}, Columns: {df.shape[1]}\n\n"
        f"--- COLUMNS & TYPES (df.info) ---\n{df_info_str}\n\n"
        f"--- MISSING VALUES PER COLUMN ---\n{missing_values}\n\n"
        f"--- STATISTICAL SUMMARY (df.describe) ---\n{summary_stats}\n\n"
        f"--- FIRST 5 ROWS (Sample) ---\n{sample_data}"
    )
    return f"{EDA_INSTRUCTIONS}\n\nHere is the underlying dataset profile:\n{context_payload}"


# ---------------------------------------------------------------------------
# Non-streaming provider calls
# ---------------------------------------------------------------------------
def call_gemini(system_persona: str, prompt: str) -> str:
    response = gemini_client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_persona,
            max_output_tokens=4000,
            # Thinking tokens count toward max_output_tokens and can truncate the report
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return response.text


def call_groq(system_persona: str, prompt: str) -> str:
    completion = groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_persona},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
        extra_body={"reasoning_effort": "low"},
    )
    return completion.choices[0].message.content


PROVIDERS = {"gemini": call_gemini, "groq": call_groq}


# ---------------------------------------------------------------------------
# Streaming provider calls (yield text chunks as they are generated)
# ---------------------------------------------------------------------------
def stream_gemini(system_persona: str, prompt: str) -> Iterator[str]:
    stream = gemini_client.models.generate_content_stream(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_persona,
            max_output_tokens=4000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def stream_groq(system_persona: str, prompt: str) -> Iterator[str]:
    stream = groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_persona},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
        extra_body={"reasoning_effort": "low"},
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


STREAM_PROVIDERS = {"gemini": stream_gemini, "groq": stream_groq}


def provider_order(preferred: str) -> list[str]:
    return [preferred] + [p for p in PROVIDERS if p != preferred]


# ---------------------------------------------------------------------------
# Regular (non-streaming) endpoint
# ---------------------------------------------------------------------------
@app.post("/analyze-csv")
def analyze_csv_data(request: CSVAnalysisRequest):
    """
    Takes a raw CSV string, extracts structural metadata using Pandas,
    and prompts an AI model (Gemini or Groq) to perform a deep
    Exploratory Data Analysis (EDA) report. Returns the full report at once.
    """
    df = parse_csv(request.csv_data)
    full_prompt = build_prompt(df)

    errors = {}
    for provider in provider_order(request.provider):
        try:
            report = PROVIDERS[provider](SYSTEM_PERSONA, full_prompt)
            return {
                "status": "success",
                "provider_used": provider,
                "rows_analyzed": df.shape[0],
                "columns_analyzed": df.shape[1],
                "analysis_report": report,
            }
        except Exception as e:
            errors[provider] = str(e)

    raise HTTPException(status_code=500, detail=f"All AI providers failed: {errors}")


# ---------------------------------------------------------------------------
# Streaming (SSE) endpoint
# ---------------------------------------------------------------------------
def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/analyze-csv/stream")
def analyze_csv_stream(request: CSVAnalysisRequest):
    """
    Same analysis as /analyze-csv, but streamed as Server-Sent Events so you
    can watch progress live.

    Events emitted:
      status    - progress messages (parsing, profiling, calling provider...)
      meta      - dataset shape once the CSV is parsed
      provider  - which provider is generating the report
      token     - a chunk of the report text
      fallback  - a provider failed before producing output; trying the next
      done      - finished successfully
      error     - something failed (stream ends)
    """

    def event_stream() -> Iterator[str]:
        yield sse("status", {"message": "Parsing CSV..."})
        try:
            df = pd.read_csv(io.StringIO(request.csv_data))
        except Exception as e:
            yield sse("error", {"message": f"Invalid CSV format: {e}"})
            return

        yield sse("meta", {"rows": df.shape[0], "columns": df.shape[1]})
        yield sse("status", {"message": "Profiling dataset with pandas..."})
        full_prompt = build_prompt(df)

        errors = {}
        for provider in provider_order(request.provider):
            yield sse("provider", {"name": provider})
            yield sse("status", {"message": f"Waiting for {provider} to respond..."})

            produced_output = False
            try:
                for text in STREAM_PROVIDERS[provider](SYSTEM_PERSONA, full_prompt):
                    produced_output = True
                    yield sse("token", {"text": text})
                yield sse("done", {"provider_used": provider})
                return
            except Exception as e:
                errors[provider] = str(e)
                if produced_output:
                    # Can't cleanly fall back after partial output was sent
                    yield sse("error", {"message": f"{provider} failed mid-stream: {e}"})
                    return
                yield sse("fallback", {"failed": provider, "error": str(e)})

        yield sse("error", {"message": f"All AI providers failed: {errors}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
        },
    )