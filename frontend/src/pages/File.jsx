import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as XLSX from "xlsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getCsv, updateCsv, getHistory, saveHistory } from "../db";

const css = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@300;400;500&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #root { height: 100%; }

.cp {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  font-family: 'Poppins', sans-serif;
}

.cp-top {
  position: relative;
  background: #acbdaa;
  height: 150px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cp-top::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 100%;
  height: 50px;
  background: #fff;
  border-radius: 60% 60% 0 0 / 100% 100% 0 0;
}

.cp-brand {
  position: absolute;
  top: 22px;
  left: 24px;
  background: none;
  border: none;
  cursor: pointer;
  color: #fff;
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 18px;
}

.cp-back {
  position: absolute;
  top: 62px;
  left: 24px;
  z-index: 5;
  border: none;
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  font-family: 'Poppins', sans-serif;
  font-weight: 500;
  font-size: 13px;
  padding: 8px 16px;
  border-radius: 30px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}
.cp-back:hover { background: rgba(255, 255, 255, 0.4); transform: translateY(-2px); }

.cp-title {
  position: relative;
  z-index: 1;
  margin-top: 16px;
  max-width: 60%;
  color: #fff;
  font-family: 'Playfair Display', serif;
  font-size: 28px;
  letter-spacing: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cp-export { position: absolute; top: 16px; right: 24px; z-index: 5; }

.cp-btn {
  border: none;
  background: #fff;
  color: #5d6b5b;
  font-family: 'Poppins', sans-serif;
  font-weight: 500;
  font-size: 14px;
  padding: 10px 22px;
  border-radius: 30px;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(93, 107, 91, 0.25);
  transition: transform 0.2s ease;
}
.cp-btn:hover:not(:disabled) { transform: translateY(-2px); }
.cp-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.cp-menu {
  position: absolute;
  right: 0;
  top: 46px;
  min-width: 170px;
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 12px 30px rgba(93, 107, 91, 0.3);
}

.cp-menu button {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: #fff;
  padding: 12px 18px;
  font-family: 'Poppins', sans-serif;
  font-size: 14px;
  color: #5d6b5b;
  cursor: pointer;
}
.cp-menu button:hover { background: #eef2ed; }

.cp-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px 12px;
}

.cp-search {
  flex: 1;
  min-width: 0;
  border: 2px solid #eef2ed;
  background: #eef2ed;
  border-radius: 30px;
  padding: 10px 20px;
  font-family: 'Poppins', sans-serif;
  font-size: 14px;
  color: #5d6b5b;
  outline: none;
}
.cp-search:focus { border-color: #acbdaa; background: #fff; }

.cp-main {
  background: #acbdaa;
  color: #fff;
  box-shadow: 0 6px 16px rgba(172, 189, 170, 0.5);
}

.cp-soft {
  background: #eef2ed;
  box-shadow: none;
  padding: 10px 16px;
}

.cp-info {
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px 8px;
  font-size: 13px;
  color: #8a968a;
}

.cp-tablewrap {
  flex: 1;
  overflow: auto;
  max-width: 1100px;
  width: calc(100% - 48px);
  margin: 0 auto;
  border-radius: 20px;
  background: #eef2ed;
}

/* While cleaning: table on top, live log below, one scroll area */
.cp-split {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  max-width: 1100px;
  width: calc(100% - 48px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.cp-split .cp-tablewrap {
  flex: none;
  width: 100%;
  margin: 0;
}
.cp-split .cp-tablewrap.cp-inline-table { height: 45vh; }
.cp-split .cp-livelog { overflow: visible; min-height: 40vh; }

table { border-collapse: collapse; width: 100%; font-size: 13px; }

th {
  position: sticky;
  top: 0;
  background: #acbdaa;
  color: #fff;
  font-weight: 500;
  text-align: left;
  padding: 10px 12px;
  white-space: nowrap;
}

td { border-bottom: 1px solid #dfe6de; background: #fff; }
td.num { width: 44px; text-align: center; color: #acbdaa; background: #f6f8f5; }

td input {
  width: 100%;
  min-width: 110px;
  border: none;
  background: transparent;
  padding: 9px 12px;
  font-family: 'Poppins', sans-serif;
  font-size: 13px;
  color: #4f5b4d;
  outline: none;
}
td input:focus { background: #eef2ed; }

.cp-foot {
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.cp-working { font-size: 14px; color: #7f8f7d; }

.cp-livelog { padding: 16px 20px; }
.cp-wait { color: #7f8f7d; font-size: 13px; }
.cp-line { font-size: 13px; color: #5d6b5b; line-height: 1.6; margin-bottom: 6px; }
.cp-line.round { font-weight: 500; color: #4f7a4b; margin-top: 10px; }
.cp-line.err { color: #a65d5d; }
.cp-line.ok { color: #4f7a4b; font-weight: 500; }
.cp-line.message { color: #3f4f3d; font-style: italic; }

.cp-card {
  background: #fff;
  border-radius: 16px;
  padding: 12px 16px;
  margin: 8px 0;
}
.cp-card h4 {
  font-size: 13px;
  font-weight: 500;
  color: #7f8f7d;
  margin-bottom: 8px;
}
.cp-card pre {
  font-size: 12px;
  line-height: 1.5;
  color: #4f5b4d;
  overflow-x: auto;
}

.md { font-size: 13px; line-height: 1.7; color: #4f5b4d; }
.md h1, .md h2, .md h3, .md h4 {
  font-family: 'Playfair Display', serif;
  color: #5d6b5b;
  margin: 14px 0 6px;
  font-size: 15px;
}
.md p { margin-bottom: 8px; }
.md ul, .md ol { margin: 0 0 8px 20px; }
.md li { margin-bottom: 4px; }
.md strong { color: #3f4f3d; }
.md code {
  background: #eef2ed;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 12px;
}
.md table { margin: 8px 0; }
.md th, .md td { padding: 6px 10px; border: 1px solid #dfe6de; }

.cp-editbar {
  flex-shrink: 0;
  display: flex;
  gap: 12px;
  align-items: center;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  padding: 12px 24px 0;
}
`;

const MAX_ROWS = 500;
const MAX_SNAPSHOTS = 20;
const API = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
if (!API) console.error("VITE_API_URL is not set. Check your .env and restart Vite.");

function parse(content) {
  const wb = XLSX.read(content, { type: "string" });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const rows = sheet
    ? XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "", raw: false })
    : [];
  const width = Math.max(0, ...rows.map((r) => r.length));
  return rows.map((r) => Array.from({ length: width }, (_, i) => r[i] ?? ""));
}

function toCsv(rows) {
  return XLSX.utils.sheet_to_csv(XLSX.utils.aoa_to_sheet(rows));
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function readSse(res, onEvent) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      let event = "message";
      const dataLines = [];
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
      }
      if (dataLines.length) onEvent(event, JSON.parse(dataLines.join("\n")));
    }
  }
}

export default function CsvPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState(null);
  const [rows, setRows] = useState([]);
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [note, setNote] = useState("");
  const [cleaning, setCleaning] = useState(false);
  const [log, setLog] = useState([]);
  const [view, setView] = useState("table");
  const [histInfo, setHistInfo] = useState({ index: 0, length: 1 });
  const [instruction, setInstruction] = useState("");
  const [editing, setEditing] = useState(false);
  const hist = useRef({ snaps: [], index: 0 });
  const logEnd = useRef(null);

  useEffect(() => {
    async function load() {
      const r = await getCsv(id);
      if (!r) return;
      setRecord(r);
      setRows(parse(r.content));
      const h = await getHistory(id);
      if (h && h.snapshots.length) {
        hist.current = { snaps: h.snapshots, index: h.index };
      } else {
        hist.current = { snaps: [r.content], index: 0 };
        await saveHistory(id, hist.current.snaps, 0);
      }
      setHistInfo({ index: hist.current.index, length: hist.current.snaps.length });
    }
    load();
  }, [id]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menuOpen]);

  // Follow the live log: scrolls the log panel into view and keeps it at the latest line
  useEffect(() => {
    logEnd.current?.scrollIntoView({ block: "end" });
  }, [log]);

  if (!record) return <div style={{ padding: 32 }}>Loading...</div>;

  const baseName = record.name.replace(/\.[^.]+$/, "");
  const header = rows[0] || [];
  const q = query.trim().toLowerCase();

  const visible = [];
  for (let i = 1; i < rows.length; i++) {
    if (!q || rows[i].some((c) => String(c).toLowerCase().includes(q))) {
      visible.push(i);
    }
  }
  const shown = visible.slice(0, MAX_ROWS);

  function addLog(type, text) {
    setLog((prev) => [...prev, { type, text }].slice(-300));
  }

  async function pushSnapshot(csv) {
    const h = hist.current;
    if (h.snaps[h.index] === csv) return;
    let snaps = [...h.snaps.slice(0, h.index + 1), csv];
    if (snaps.length > MAX_SNAPSHOTS) snaps = snaps.slice(snaps.length - MAX_SNAPSHOTS);
    hist.current = { snaps, index: snaps.length - 1 };
    setHistInfo({ index: hist.current.index, length: snaps.length });
    await saveHistory(id, snaps, hist.current.index);
  }

  async function moveHistory(step) {
    const h = hist.current;
    const next = h.index + step;
    if (next < 0 || next >= h.snaps.length) return;
    hist.current = { ...h, index: next };
    setRows(parse(h.snaps[next]));
    setHistInfo({ index: next, length: h.snaps.length });
    setNote(step < 0 ? "Undone. Press Save to keep it." : "Redone. Press Save to keep it.");
    await saveHistory(id, h.snaps, next);
  }

  function editCell(r, c, value) {
    setRows((prev) =>
      prev.map((row, ri) => (ri === r ? row.map((cell, ci) => (ci === c ? value : cell)) : row))
    );
    setNote("");
  }

  async function handleSave() {
    const csv = toCsv(rows);
    await updateCsv(record.id, csv);
    await pushSnapshot(csv);
    setNote("Saved.");
  }

  function handleEvent(event, d, state) {
    if (event === "status") addLog("status", d.message);
    else if (event === "round") addLog("round", `Round ${d.round} started (${d.lines} lines)`);
    else if (event === "overview") {
      addLog("analysis", { title: `Round ${d.round} overview`, body: d.overview });
    } else if (event === "report") {
      const body = typeof d.report === "string" ? d.report : JSON.stringify(d.report, null, 2);
      addLog("analysis", {
        title: `Round ${d.round} scan ${d.ok ? "passed" : "found problems"}`,
        body,
      });
    } else if (event === "code") {
      addLog("code", { attempt: d.attempt, round: d.round, code: d.code });
    } else if (event === "csv") {
      state.csv = d.csv;
      setRows(parse(d.csv));
      addLog("status", `Round ${d.round} cleaned CSV ready (${d.lines} lines)`);
    } else if (event === "done") {
      state.csv = d.csv;
      setRows(parse(d.csv));
      addLog(d.ok ? "ok" : "err", d.reason);
    } else if (event === "error") addLog("err", d.message);
  }

  async function handleClean() {
    setCleaning(true);
    setView("log");
    setLog([]);
    setNote("");
    const state = { csv: null };

    try {
      await pushSnapshot(toCsv(rows));

      const res = await fetch(`${API}/clean-csv/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_data: toCsv(rows) }),
      });
      if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`);

      await readSse(res, (event, d) => handleEvent(event, d, state));

      if (state.csv) {
        await pushSnapshot(state.csv);
        setNote("Cleaning finished. Press Save to keep it, or Undo to go back.");
      }
    } catch (e) {
      addLog("err", `Could not clean: ${e.message}`);
      if (state.csv) await pushSnapshot(state.csv);
    } finally {
      setCleaning(false);
    }
  }

  async function handleEdit() {
    const prompt = instruction.trim();
    if (!prompt || cleaning) return;

    setCleaning(true);
    setEditing(true);
    setView("log");
    setLog([]);
    setNote("");
    const state = { csv: null, message: "" };

    try {
      await pushSnapshot(toCsv(rows));

      const res = await fetch(`${API}/edit-csv/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_data: toCsv(rows), prompt }),
      });
      if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`);

      await readSse(res, (event, d) => {
        if (event === "status") addLog("status", d.message);
        else if (event === "message") {
          state.message = d.text;
          addLog("message", d.text);
        } else if (event === "code") {
          addLog("code", { attempt: d.attempt, round: "edit", code: d.code });
        } else if (event === "csv") {
          state.csv = d.csv;
          setRows(parse(d.csv));
          addLog("status", `Edited CSV ready (${d.lines} lines)`);
        } else if (event === "done") {
          state.csv = d.csv;
          setRows(parse(d.csv));
          addLog(d.ok ? "ok" : "err", d.reason);
        } else if (event === "error") addLog("err", d.message);
      });

      if (state.csv) {
        await pushSnapshot(state.csv);
        setNote(`${state.message || "Edit applied."} Press Save to keep it, or Undo to go back.`);
        setInstruction("");
        setView("table");
      }
    } catch (e) {
      addLog("err", `Could not edit: ${e.message}`);
      if (state.csv) await pushSnapshot(state.csv);
    } finally {
      setCleaning(false);
      setEditing(false);
    }
  }

  function exportCsv() {
    download(new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" }), `${baseName}.csv`);
    setMenuOpen(false);
  }

  function exportXlsx() {
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), "Sheet1");
    XLSX.writeFile(wb, `${baseName}.xlsx`);
    setMenuOpen(false);
  }

  const tablePanel = (
    <div className={`cp-tablewrap${cleaning ? " cp-inline-table" : ""}`}>
      <table>
        <thead>
          <tr>
            <th>#</th>
            {header.map((h, c) => (
              <th key={c}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r}>
              <td className="num">{r}</td>
              {rows[r].map((cell, c) => (
                <td key={c}>
                  <input
                    value={cell}
                    disabled={cleaning}
                    onChange={(e) => editCell(r, c, e.target.value)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const logPanel = (
    <div className="cp-tablewrap cp-livelog">
      {log.length === 0 && <p className="cp-wait">Connecting...</p>}
      {log.map((l, i) => {
        if (l.type === "code") {
          return (
            <div key={i} className="cp-card">
              <h4>
                {l.text.round === "edit"
                  ? `Attempt ${l.text.attempt}: editing code`
                  : `Round ${l.text.round}, attempt ${l.text.attempt}: cleaning code`}
              </h4>
              <pre>{l.text.code}</pre>
            </div>
          );
        }
        if (l.type === "analysis") {
          return (
            <div key={i} className="cp-card">
              <h4>{l.text.title}</h4>
              <div className="md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{l.text.body}</ReactMarkdown>
              </div>
            </div>
          );
        }
        return (
          <p key={i} className={`cp-line ${l.type}`}>{l.text}</p>
        );
      })}
      <div ref={logEnd} />
    </div>
  );

  return (
    <>
      <style>{css}</style>
      <div className="cp">
        <div className="cp-top">
          <button className="cp-brand" onClick={() => navigate("/workspace")}>NOVA</button>
          <button className="cp-back" onClick={() => navigate("/")}>← Back</button>

          <div className="cp-export" onClick={(e) => e.stopPropagation()}>
            <button className="cp-btn" onClick={() => setMenuOpen((o) => !o)}>
              Download ▾
            </button>
            {menuOpen && (
              <div className="cp-menu">
                <button onClick={exportCsv}>Export as CSV</button>
                <button onClick={exportXlsx}>Export as XLSX</button>
              </div>
            )}
          </div>

          <h1 className="cp-title" title={record.name}>{record.name}</h1>
        </div>

        <div className="cp-bar">
          <input
            className="cp-search"
            placeholder="Search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            className="cp-btn cp-soft"
            onClick={() => moveHistory(-1)}
            disabled={cleaning || histInfo.index <= 0}
          >
            Undo
          </button>
          <button
            className="cp-btn cp-soft"
            onClick={() => moveHistory(1)}
            disabled={cleaning || histInfo.index >= histInfo.length - 1}
          >
            Redo
          </button>
          <button className="cp-btn cp-main" onClick={handleSave} disabled={cleaning}>Save</button>
        </div>

        <div className="cp-info">
          {note || `${visible.length} row${visible.length === 1 ? "" : "s"}${visible.length > MAX_ROWS ? `, showing the first ${MAX_ROWS}` : ""}`}
        </div>

        {cleaning ? (
          <div className="cp-split">
            {tablePanel}
            {logPanel}
          </div>
        ) : view === "log" ? (
          logPanel
        ) : (
          tablePanel
        )}

        <div className="cp-editbar">
          <input
            className="cp-search"
            placeholder='Tell me what to change, e.g. "remove rows where age is under 18"'
            value={instruction}
            disabled={cleaning}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleEdit()}
          />
          <button
            className="cp-btn cp-main"
            onClick={handleEdit}
            disabled={cleaning || !instruction.trim()}
          >
            Apply
          </button>
        </div>

        <div className="cp-foot">
          {cleaning ? (
            <span className="cp-working">
              {editing ? "Applying your instruction..." : "Cleaning in progress..."}
            </span>
          ) : (
            <>
              {log.length > 0 && (
                <button
                  className="cp-btn cp-soft"
                  onClick={() => setView(view === "log" ? "table" : "log")}
                >
                  {view === "log" ? "View table" : "View log"}
                </button>
              )}
              <button className="cp-btn cp-main" onClick={handleClean}>
                {log.length > 0 ? "Clean again" : "Clean"}
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}