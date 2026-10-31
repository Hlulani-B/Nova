import hashlib
import json
import queue
import threading
import time
from typing import Callable, Iterator, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from editor import edit_csv
from overview import generate_csv_overview
from scan import CSVAnalysisRequest, analyze_csv_data
from scrubber import clean_csv, find_problems

app = FastAPI(title="CSV Cleaning Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://disreputable-orb-g49g9pqg796ghwqxp-5173.app.github.dev",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEARTBEAT_SECONDS = 5  # how often to report "still working" during a slow AI call

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
}


class CleanRequest(BaseModel):
    csv_data: str
    provider: Literal["gemini", "groq", "openrouter"] = "gemini"
    max_rounds: int = 5  # safety cap so the loop can never run forever


class EditRequest(BaseModel):
    csv_data: str
    prompt: str
    provider: Literal["gemini", "groq", "openrouter"] = "gemini"


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def log(msg: str) -> None:
    """Timestamped progress line printed to the server console."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def csv_shape(csv_data: str) -> dict:
    lines = [l for l in csv_data.splitlines() if l.strip()]
    return {"lines": len(lines), "chars": len(csv_data)}


def fingerprint(csv_data: str) -> str:
    return hashlib.md5(csv_data.strip().encode()).hexdigest()


def run_with_heartbeat(label: str, fn: Callable) -> Iterator[str]:
    """
    Runs fn(emit) in a worker thread and, while it works, yields SSE events:
    status / code / message events the worker emits, plus a heartbeat every
    HEARTBEAT_SECONDS so you can tell it's alive. Returns fn's result
    (use with `yield from`) or re-raises its exception.
    """
    q: queue.Queue = queue.Queue()
    box: dict = {}

    def emit(kind: str, payload) -> None:
        q.put((kind, payload))

    def worker() -> None:
        try:
            box["value"] = fn(emit)
        except Exception as e:
            box["error"] = e
        finally:
            q.put(("finished", None))

    threading.Thread(target=worker, daemon=True).start()
    started = time.time()

    while True:
        try:
            kind, payload = q.get(timeout=HEARTBEAT_SECONDS)
        except queue.Empty:
            msg = f"{label}: still working... {int(time.time() - started)}s elapsed"
            log(msg)
            yield sse("status", {"message": msg})
            continue

        if kind == "finished":
            break
        if kind == "status":
            log(payload)
            yield sse("status", {"message": payload})
        elif kind == "code":
            log(f"{label}: received code (attempt {payload.get('attempt')})")
            yield sse("code", payload)
        elif kind == "message":
            log(f"{label}: AI message: {str(payload.get('text', ''))[:120]}")
            yield sse("message", payload)

    log(f"{label}: finished in {time.time() - started:.1f}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


# ---------------------------------------------------------------------------
# Auto-clean loop
# ---------------------------------------------------------------------------
@app.post("/clean-csv/stream")
def clean_csv_stream(request: CleanRequest):
    """
    Loop: overview + scan -> if ok is False, clean -> the cleaned CSV becomes the
    current CSV -> repeat until ok is True (or max_rounds is hit, or the cleaner stalls).

    Stopping is decided by deterministic pandas checks, not by the AI.

    Events emitted:
      status    - progress messages and heartbeats
      round     - a new round started
      overview  - the overview sentence for the current CSV
      report    - the scan result {ok, report} for the current CSV
      code      - a cleaning script the AI wrote (one per attempt, sent live)
      csv       - the cleaned CSV produced by a round
      done      - finished: {ok, rounds, csv, reason}
      error     - something failed (stream ends)
    """

    def event_stream() -> Iterator[str]:
        pipeline_start = time.time()
        current_csv = request.csv_data
        seen = {fingerprint(current_csv)}   # every CSV state we've been in (detects loops)

        log(f"Pipeline started ({csv_shape(current_csv)['lines']} lines, "
            f"max_rounds={request.max_rounds})")
        yield sse("status", {"message": "Starting pipeline..."})

        for round_no in range(1, request.max_rounds + 2):
            log(f"===== ROUND {round_no} =====")
            yield sse("round", {"round": round_no, **csv_shape(current_csv)})

            # 1. Overview
            overview = generate_csv_overview(current_csv)
            if overview.startswith("Error parsing CSV data"):
                log(f"ERROR: {overview}")
                yield sse("error", {"message": overview})
                return
            log(f"Round {round_no}: overview built")
            yield sse("overview", {"round": round_no, "overview": overview})

            # 2. Scan (with heartbeat while waiting on the AI)
            msg = f"Round {round_no}: scanning..."
            log(msg)
            yield sse("status", {"message": msg})
            try:
                scan = yield from run_with_heartbeat(
                    f"Round {round_no} scan",
                    lambda emit: analyze_csv_data(
                        CSVAnalysisRequest(csv_data=current_csv, provider=request.provider)
                    ),
                )
            except Exception as e:
                detail = getattr(e, "detail", e)
                log(f"ERROR: scan failed: {detail}")
                yield sse("error", {"message": f"Scan failed: {detail}"})
                return

            # 3. Send the report over SSE
            log(f"Round {round_no}: scan result ok={scan['ok']}")
            yield sse("report", {"round": round_no, "ok": scan["ok"], "report": scan["report"]})

            # 4. Clean enough? Finish.
            if scan["ok"]:
                log(f"DONE: clean after {round_no} round(s), {time.time() - pipeline_start:.1f}s total")
                yield sse("done", {
                    "ok": True,
                    "rounds": round_no,
                    "csv": current_csv,
                    "reason": "Dataset needs no further cleaning.",
                })
                return

            # 5. Out of rounds? Stop with the best CSV we have.
            if round_no > request.max_rounds:
                reason = f"Reached max_rounds ({request.max_rounds}) and data is still not fully clean."
                log(f"STOPPED: {reason}")
                yield sse("done", {
                    "ok": False,
                    "rounds": round_no,
                    "csv": current_csv,
                    "reason": reason,
                })
                return

            # 6. Clean: feed overview + scan + csv into the cleaner (runs in a worker thread
            #    so progress, code and heartbeats stream while it works)
            msg = f"Round {round_no}: cleaning..."
            log(msg)
            yield sse("status", {"message": msg})

            def do_clean(emit, _round=round_no, _scan=scan, _overview=overview, _csv=current_csv):
                counter = {"n": 0}

                def on_code(code: str) -> None:
                    counter["n"] += 1
                    emit("code", {"round": _round, "attempt": counter["n"], "code": code})

                return clean_csv(
                    _scan, _overview, _csv,
                    provider=request.provider,
                    on_code=on_code,
                    on_progress=lambda m: emit("status", m),
                )

            try:
                cleaned_csv = yield from run_with_heartbeat(f"Round {round_no} clean", do_clean)
            except Exception as e:
                log(f"ERROR: cleaning failed: {e}")
                yield sse("error", {"message": f"Cleaning failed: {e}"})
                return

            # 7. Stall / repeat detection, decided by hard checks, not by the AI
            digest = fingerprint(cleaned_csv)
            if digest in seen:   # no change, or flipped back to an earlier state
                problems = find_problems(cleaned_csv)
                if not problems:
                    reason = (
                        "Cleaner made no further changes and all automated checks pass "
                        "(no missing values, duplicates, blanks or padding). "
                        "The scan's remaining suggestions are advisory."
                    )
                    log(f"DONE (stalled but clean): {reason}")
                    yield sse("done", {
                        "ok": True,
                        "rounds": round_no,
                        "csv": cleaned_csv,
                        "reason": reason,
                    })
                else:
                    msg = "Cleaner is stuck and problems remain: " + "; ".join(problems)
                    log(f"ERROR: {msg}")
                    yield sse("error", {"message": msg})
                return
            seen.add(digest)

            shape = csv_shape(cleaned_csv)
            log(f"Round {round_no}: cleaned CSV ready ({shape['lines']} lines)")
            yield sse("csv", {"round": round_no, "csv": cleaned_csv, **shape})

            # 8. The new CSV becomes the CSV for the next round
            current_csv = cleaned_csv

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


# ---------------------------------------------------------------------------
# Human instruction -> AI writes code -> edited CSV
# ---------------------------------------------------------------------------
@app.post("/edit-csv/stream")
def edit_csv_stream(request: EditRequest):
    """
    The user types an instruction; the AI writes code that applies it to the CSV.

    Events emitted:
      status    - progress messages and heartbeats
      message   - the AI's plain-language explanation of what it did (one per attempt)
      code      - the script the AI wrote (one per attempt)
      csv       - the edited CSV string
      done      - finished: {ok, csv, reason}
      error     - something failed (stream ends)
    """

    def event_stream() -> Iterator[str]:
        instruction = request.prompt.strip()
        if not instruction:
            yield sse("error", {"message": "Please type an instruction first."})
            return
        if not request.csv_data.strip():
            yield sse("error", {"message": "There is no CSV data to edit."})
            return

        started = time.time()
        log(f"Edit started ({csv_shape(request.csv_data)['lines']} lines): {instruction[:100]}")
        yield sse("status", {"message": "Reading your instruction..."})

        def do_edit(emit):
            counters = {"message": 0, "code": 0}

            def on_message(text: str) -> None:
                counters["message"] += 1
                emit("message", {"attempt": counters["message"], "text": text})

            def on_code(code: str) -> None:
                counters["code"] += 1
                emit("code", {"attempt": counters["code"], "code": code})

            return edit_csv(
                instruction,
                request.csv_data,
                provider=request.provider,
                on_message=on_message,
                on_code=on_code,
                on_progress=lambda m: emit("status", m),
            )

        try:
            edited_csv = yield from run_with_heartbeat("Edit", do_edit)
        except Exception as e:
            log(f"ERROR: edit failed: {e}")
            yield sse("error", {"message": str(e)})
            return

        shape = csv_shape(edited_csv)
        log(f"DONE: edit applied in {time.time() - started:.1f}s ({shape['lines']} lines)")
        yield sse("csv", {"csv": edited_csv, **shape})
        yield sse("done", {"ok": True, "csv": edited_csv, "reason": "Your instruction was applied."})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)