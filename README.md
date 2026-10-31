# Nova CSV Cleaning Pipeline
Here is a link to demo video: [![Nova Demo Video](https://img.youtube.com/vi/0U9Ev0XFJLc/hqdefault.jpg)](https://youtu.be/0U9Ev0XFJLc)

An API that takes a messy CSV (as a string), scans it, has an AI write pandas cleaning code, runs that code in a subprocess, re-scans the result, and repeats until the data is clean. Progress, reports, and generated code are streamed live over Server-Sent Events (SSE).

It also has a second mode where a person types a plain English instruction (for example "remove rows where age is under 18") and the AI writes and runs code that applies only that change.

## How it works

```
csv string
   |
   v
+--------------------------- loop (max_rounds) ---------------------------+
|                                                                         |
|  1. overview.py   -> text summary of types, missing rows, duplicates    |
|  2. scan.py       -> pandas profile + LLM -> {ok, report}               |
|        ok == True  ------------------------------> DONE (return CSV)    |
|        ok == False                                                      |
|  3. scrubber.py   -> LLM writes cleaning code (reads data.csv,          |
|        |             writes cleaned.csv)                                |
|        v                                                                |
|     code_runner.py -> runs the code in a subprocess, returns cleaned    |
|        |              CSV string                                        |
|        v                                                                |
|     find_problems() -> hard pandas checks; failures are sent back to    |
|                        the AI for another attempt (max 3)               |
|  4. cleaned CSV becomes the current CSV -> next round                   |
+-------------------------------------------------------------------------+
```

The AI decides what to fix. **Deterministic pandas checks decide when to stop**, so the loop cannot be trapped by an opinionated model.

The instruction mode is a single pass instead of a loop:

```
instruction + csv string
   |
   v
editor.py -> LLM writes code that does ONLY what was asked
   |
   v
code_runner.py -> runs it in a subprocess, returns the edited CSV
   |
   v
check_output() -> valid CSV, has columns and rows, and is not identical
                  to the input. Failures go back to the AI (max 3 attempts)
```

## Project layout

| File | Role |
|---|---|
| `main.py` | Pipeline orchestrator and SSE endpoints `POST /clean-csv/stream` and `POST /edit-csv/stream` |
| `scan.py` | Profiles the CSV with pandas, asks the LLM for `{ok, report}`; also `POST /analyze-csv` |
| `overview.py` | `generate_csv_overview(csv)`: per-column types, missing-value rows, duplicate count |
| `scrubber.py` | `clean_csv(scan, overview, csv)`: generates, runs, and validates cleaning code with retries |
| `editor.py` | `edit_csv(prompt, csv)`: turns a human instruction into code, runs it, and validates the result |
| `code_runner.py` | `run_python_code(code, csv)`: writes `data.csv`, runs the script, returns `cleaned.csv`; also `POST /run` |
| `*_test.py` | Tests for each module (`scan_test`, `overview_test`, `code_runner_test`, `scrubber_test`, `main_test`) |
| `messy_data_*.csv` | Sample messy inputs used by `main_test.py` |

> `code_runner.py` must **not** be named `subprocess.py`. That shadows Python's built-in `subprocess` module and breaks imports.

## Setup

```bash
pip install fastapi uvicorn pandas tabulate google-genai groq pydantic-settings requests pytest httpx
```

Create a `.env` in the project folder:

```
GEMINI_TOKEN=your_gemini_key
GROQ_TOKEN=your_groq_key
```

Optional overrides: `GEMINI_MODEL`, `GROQ_MODEL`, `PROVIDER_TIMEOUT`, `MAX_OUTPUT_TOKENS`.

Run the server:

```bash
uvicorn main:app --port 8000
```

The instruction mode needs no extra packages or keys. It reuses the same providers and the same `code_runner.py`.

## Modules

### scan.py

- `parse_csv`: strict `pd.read_csv`, falling back to a tolerant parse that skips and counts malformed lines.
- `build_prompt`: pandas profile (shape, dtypes, missing values, duplicates, describe, sample) plus EDA instructions.
- Two providers (Gemini, Groq) in JSON mode, with automatic fallback to the other if one fails or returns bad JSON.
- `parse_llm_json`: strips code fences, tolerates raw newlines, validates `ok` (bool) and `report` (str).
- `hard_checks_pass`: no missing values, duplicates, blank strings, or skipped lines. The LLM can only return `ok: true` if these agree.
- Returns `{"ok": bool, "report": str}`.

### overview.py

`generate_csv_overview(csv_data)` returns one descriptive sentence: row and column counts, the data types actually present in each column, row numbers with missing values, and the duplicate count. It is fed to the cleaner as extra context.

### code_runner.py

`run_python_code(code, csv_data)`:

1. Creates a temporary folder.
2. Writes the CSV string to `data.csv` and the code to `script.py`.
3. Runs `python script.py` with the folder as the working directory (30 s timeout).
4. Reads back `cleaned.csv` and returns `{"output": stdout, "cleaned_csv": "<csv string>"}`.

Raises `HTTPException` on a crash (400), a timeout (408), or a missing `cleaned.csv` (400). The temp folder is deleted afterwards. Running from a file (not `python -c`) avoids command-line length limits on large CSVs.

### scrubber.py

`clean_csv(scan, overview, csv_data, provider, max_attempts=3, on_code=None, on_progress=None)`:

1. Builds a prompt from the scan report, the overview, and the first 30 raw lines. The prompt:
   - requires reading `data.csv` and writing `cleaned.csv`
   - states the pandas version and Copy-on-Write rules (no `inplace=True`, always assign back)
   - lists the fixes to make: missing values, duplicates, blanks, whitespace, casing, numeric types
   - keeps the original column names and never removes inner spaces
2. Asks the AI for code and extracts it from the reply, handling markdown fences.
3. Inserts a safety net into the code (`add_safety_net`) that fills any missing values the AI forgot, just before the final missing value assert.
4. Runs it through `run_python_code`.
5. Validates the output with `find_problems` (missing values, duplicates, whitespace, blank strings).
6. On a crash or remaining problems, sends the previous code and the exact problems back to the AI and retries.
7. Returns the cleaned CSV string, or raises `CleaningError` (including the last generated code).

`on_code` and `on_progress` are optional callbacks used by `main.py` for live streaming. The code passed to `on_code` is exactly the code that runs, safety net included.

### editor.py

`edit_csv(prompt, csv_data, provider, max_attempts=3, on_message=None, on_code=None, on_progress=None)`:

1. Builds a prompt from the user's instruction, the CSV shape, a column value profile (all rows), and the first 30 raw lines. The prompt:
   - tells the AI to do only what was asked and not clean, reformat, reorder or drop anything else
   - reads the CSV with `dtype=str, keep_default_na=False` so untouched columns stay exactly as they were
   - keeps original column names and row order unless the instruction says otherwise
   - pins the same pandas 3 rules as the cleaner (no `inplace=True`, always assign back)
   - asks for a reply in two tags: `<message>` (a short plain language explanation) and `<code>` (the script)
2. `parse_ai_reply` splits the reply into message and code, and tolerates missing tags and markdown fences.
3. Runs the code through `run_python_code`.
4. `check_output` validates the result: it must be a valid CSV with columns and rows. If the output is identical to the input, the AI is told the change did nothing and gets another attempt. On the last attempt an identical result is accepted, because some instructions genuinely need no change.
5. On a crash, timeout or failed check, the previous code and the exact problem go back to the AI.
6. Returns the edited CSV string, or raises `EditError` with a short message.

`on_message` is called once per attempt with the AI's explanation. `on_code` and `on_progress` work the same way as in the cleaner.

### main.py

`POST /clean-csv/stream` with body:

```json
{"csv_data": "id,name\n1,Alice\n...", "max_rounds": 5}
```

Each round runs overview, scan, and (if `ok` is false) clean. Slow AI calls run in a worker thread so progress and a "still working... Ns elapsed" heartbeat are streamed every 5 seconds. Timestamped progress is also printed to the server console. CORS is enabled for the frontend origins listed in `allow_origins`.

`POST /edit-csv/stream` with body:

```json
{"csv_data": "id,name,age\n1,Alice,25\n...", "prompt": "remove rows where age is under 18"}
```

Runs `edit_csv` in a worker thread with the same heartbeat, so the message, the code and progress stream while it works. An empty instruction or empty CSV returns an `error` event straight away.

## SSE events

Clean stream (`/clean-csv/stream`):

| Event | Payload | Meaning |
|---|---|---|
| `status` | `{message}` | Progress messages and heartbeats |
| `round` | `{round, lines, chars}` | A new round started |
| `overview` | `{round, overview}` | Overview of the current CSV |
| `report` | `{round, ok, report}` | Scan result (the analysis, written in markdown) |
| `code` | `{round, attempt, code}` | A cleaning script the AI wrote |
| `csv` | `{round, csv, lines, chars}` | Cleaned CSV produced by a round |
| `done` | `{ok, rounds, csv, reason}` | Finished; `csv` is the final result |
| `error` | `{message}` | Failure; the stream ends |

Edit stream (`/edit-csv/stream`):

| Event | Payload | Meaning |
|---|---|---|
| `status` | `{message}` | Progress messages and heartbeats |
| `message` | `{attempt, text}` | The AI's plain language explanation of what it did |
| `code` | `{attempt, code}` | The script the AI wrote for that attempt |
| `csv` | `{csv, lines, chars}` | The edited CSV |
| `done` | `{ok, csv, reason}` | Finished; `csv` is the final result |
| `error` | `{message}` | Failure; the stream ends |

The edit stream has no `round` field, because there are no rounds.

## Stopping rules

The loop ends when any of these happens:

1. **Scan says `ok: true`**: done.
2. **Cleaner stalls or flips back to a previous state** (every CSV state is fingerprinted):
   - hard checks pass: done with `ok: true`; the scan's remaining suggestions are treated as advisory
   - hard checks fail: `error` listing the exact problems
3. **`max_rounds` exceeded**: `done` with `ok: false` and the best CSV so far.
4. **Any scan or clean failure**: `error`.

The instruction mode ends after the first attempt that passes `check_output`, or with an `error` after 3 failed attempts.

## Frontend

The CSV page has two ways to change the data besides editing cells by hand.

- **Clean** button: runs the auto-clean loop and streams the overview, scan reports and code into a live log.
- **Instruction bar** (the text box above the Clean button, with an Apply button): type what you want changed and press Enter or Apply. The AI's explanation shows in the live log and then in the note line next to the row count.

Both modes share the same behavior:

- the table is locked while the request runs, and the live log shows below it
- a snapshot is taken before and after, so Undo and Redo work as normal
- nothing is written to storage until you press Save
- the SSE reading is done by one shared `readSse` helper

When an edit finishes, the page switches back to the table. If it fails, the log stays open so you can read the error.

## Testing

```bash
python scrubber_test.py     # runner tests (no AI) + one end-to-end clean
python main_test.py         # full SSE pipeline on the three messy CSVs
python -m pytest main_test.py -k one -s   # a single file
```

`main_test.py` prints every report, every generated script, and the final CSV. It asserts the stream has no errors, includes `report` and `code` events, ends with `done` and `ok: true`, and that the final CSV is non-empty, keeps its columns, and has no duplicates or missing values. The tests make real AI calls, so expect them to take minutes and to occasionally need a re-run.

Try it from the command line (`-N` disables curl buffering):

```bash
curl -N -X POST http://127.0.0.1:8000/clean-csv/stream \
  -H "Content-Type: application/json" \
  -d '{"csv_data": "id,name,age\n1,  Alice ,25\n2,Bob,N/A\n2,Bob,N/A\n", "max_rounds": 3}'
```

And the instruction mode:

```bash
curl -N -X POST http://127.0.0.1:8000/edit-csv/stream \
  -H "Content-Type: application/json" \
  -d '{"csv_data": "id,name,age\n1,Alice,25\n2,Bob,15\n3,Cara,40\n", "prompt": "remove rows where age is under 18"}'
```

## Problems faced and how they were fixed

### 1. The browser blocked the API with a CORS error (GitHub Codespaces)

**Symptom:** The React app on port 5173 could not call the API on port 8000. The browser reported that the preflight request had no `Access-Control-Allow-Origin` header.

**Causes, in the order they were found:**

- The first version of the API had no CORS middleware at all, so the browser refused every cross-origin call. When the instruction endpoint was added, the server log showed `OPTIONS /edit-csv/stream 405 Method Not Allowed`. That 405 is the preflight failing, because without the middleware nothing answers OPTIONS.
- `allow_origins` only listed `http://localhost:5173`. In Codespaces the frontend runs on a forwarded address ending in `-5173.app.github.dev`, so that origin was not allowed.
- Codespaces ports are Private by default. A private port answers the browser's preflight with a login redirect before FastAPI sees it, and that reply can never carry CORS headers.
- An old uvicorn process was still running and holding port 8000, so edits to `main.py` had no effect. A test with `curl -X OPTIONS` returned a plain `404 Not Found` instead of `200 OK`.

**Fix:** Add the exact frontend URL to `allow_origins` (no trailing slash), set port 8000 to Public in the Ports tab, stop every uvicorn process (`pkill -f uvicorn`, then check `lsof -i :8000` is empty), and start the server again. A local `curl -i -X OPTIONS` request with an `Origin` header should return `200 OK` and an `access-control-allow-origin` line before you try the browser again.

### 2. The request went to the wrong address

**Symptom:** The browser called `.../csv/undefined/clean-csv/stream` and got a 404. Later a double slash appeared in the URL.

**Cause:** `VITE_API_URL` was `undefined`, because the `.env` file is only read when the Vite dev server starts. After that, a trailing slash in the value produced `//clean-csv/stream`.

**Fix:** Keep the `.env` in the project root, restart `npm run dev` after every change, and strip trailing slashes in code: `(import.meta.env.VITE_API_URL || "").replace(/\/+$/, "")`. A console error is logged if the variable is missing.

### 3. The AI cleaning script failed its own assertion

**Symptom:** After three attempts the run failed with `AssertionError` on `assert not df.isna().any().any()`.

**Cause:** The prompt tells the AI to assert that no missing values remain, but the generated script only filled some columns. Columns such as `age` were converted with `pd.to_numeric(errors="coerce")` and never filled, and the original `billing_amount` column kept its blanks after being split into new columns.

**Fix:** `add_safety_net` in `scrubber.py` inserts a loop before the assert that fills every remaining gap: dates with a fixed default, booleans with `False`, numbers with the median, and text with `Unknown`. It is added before `on_code` runs, so the code shown in the frontend is exactly the code that executes.

### 4. Provider names leaked into progress messages

**Symptom:** The frontend showed messages such as "asking gemini to write cleaning code" and errors listing every provider that failed.

**Fix:** Progress now says "writing cleaning code...". When every provider fails, the real reasons are printed to the server console only, and the client gets a short, neutral message.

### 5. The live analysis and code did not appear in the frontend

**Symptom:** While cleaning, the page showed nothing, then everything at once at the end.

**Causes:**

- Proxies such as the Codespaces tunnel can buffer a streamed response until it ends.
- The first log panel was a small fixed box, and the code was collapsed.
- Some proxies send `\r\n` line endings, which broke splitting events on `\n\n`.

**Fix:** The stream starts with a comment line padded with 2048 spaces so the proxy begins passing data straight away. The frontend normalises `\r\n` to `\n`, and while cleaning it shows a full size live panel with every overview, scan report and cleaning script in full. A "View table" and "View log" toggle appears afterwards. If the panel is still empty, the browser's Network tab (EventStream view) shows whether events are arriving at all.

### 6. The scan report was hard to read

**Symptom:** The overview and scan report are markdown (headings, bold text, lists), but they appeared as raw text with symbols.

**Fix:** The frontend renders them with `react-markdown` and `remark-gfm`, styled to match the rest of the app. Cleaning code stays in plain code blocks.

### 7. Instructions that silently did nothing

**Symptom:** A typed instruction ran without errors but the table came back unchanged.

**Cause:** Models often write pandas 1 or 2 code (`inplace=True`, chained assignment) that does nothing under pandas 3, so the script succeeds and changes nothing.

**Fix:** The edit prompt pins the pandas 3 rules, and `check_output` compares the result with the input. An identical result counts as a failed attempt and the AI is told why. On the last attempt an identical result is accepted, since the instruction may genuinely need no change.

### 8. Smaller issues that shaped the design

- **Module name clash:** naming the runner `subprocess.py` shadows Python's built-in module, so it is called `code_runner.py`.
- **Silent pandas bugs:** models often write pandas 1 or 2 code (`inplace=True`, chained assignment) that does nothing under pandas 3. The prompt pins pandas 3 rules and tells the AI to always assign results back.
- **Endless loops:** a model can keep finding new things to improve forever. Every CSV state is fingerprinted, `max_rounds` caps the loop, and pandas checks, not the AI, decide when the data is clean.
- **Over cleaning:** early scripts removed spaces inside values (`New York` became `NewYork`). The prompt now only allows trimming the ends and collapsing repeated inner spaces to one.
- **Large files:** the first versions passed the CSV on the command line, which hits length limits. The script is written to a file and run from there.
- **Edits touching other columns:** reading everything as strings (`dtype=str, keep_default_na=False`) keeps columns the instruction did not mention exactly as they were, so numbers do not gain a trailing `.0` and blanks do not turn into NaN.

## Known limitations

- **Security:** AI-written code runs directly on the host. This applies to both modes, and the instruction mode runs code written from free text typed by a user. Run the service in a container or sandbox with no network access and limited resources before exposing it to anyone.
- **Strict definition of clean:** Any null, duplicate, or blank string means "not clean". The cleaner fills numeric nulls with the median and text nulls with `Unknown`, which is a design choice. Relax `hard_checks_pass` and `find_problems` if you want to keep nulls.
- **The AI only sees a sample:** The cleaner and the editor get the first 30 raw lines, so problems that only appear deeper in a large file may be missed. The editor also gets a value profile of every column, which helps, and the cleaner's re-scan loop usually catches the rest in the next round.
- **Instructions are interpreted, not guaranteed:** If an instruction is vague, the AI picks the most reasonable reading and says so in its message. Read that message, and use Undo if it guessed wrong.
- **Edits are not saved automatically:** Both modes only change the table on screen. Press Save to keep the result.
- **Cost and latency:** Each cleaning round makes one scan call and one or more cleaning calls. An edit makes one call per attempt, up to three. Expect 10 to 20 seconds per AI call.
- **pandas 3:** The prompts pin pandas 3 semantics because models often write pandas 1/2 code (`inplace=True`, chained assignment) that silently does nothing.
- **Size limits:** Whole CSVs are sent as JSON strings, so very large files should be uploaded or chunked instead.
- **Codespaces:** Port visibility can reset to Private when the codespace restarts. If the CORS error comes back, check the Ports tab first.
