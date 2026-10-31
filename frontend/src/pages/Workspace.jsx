import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as XLSX from "xlsx";
import { saveCsv, getAllCsvs } from "../db";

const css = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@300;400;500&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #root { height: 100%; }

.ws {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  font-family: 'Poppins', sans-serif;
}

.ws-top {
  position: relative;
  background: #acbdaa;
  height: 200px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ws-top::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 100%;
  height: 60px;
  background: #fff;
  border-radius: 60% 60% 0 0 / 100% 100% 0 0;
}

.ws-brand {
  position: absolute;
  top: 24px;
  left: 24px;
  color: #fff;
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 18px;
}

.ws-heading {
  position: relative;
  z-index: 1;
  margin-top: 20px;
  color: #fff;
  font-family: 'Playfair Display', serif;
  font-size: 40px;
  letter-spacing: 2px;
}

.ws-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 32px 40px;
}

.ws-grid {
  max-width: 1000px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 20px;
}

.ws-box {
  aspect-ratio: 1 / 1;
  border: none;
  border-radius: 28px;
  background: #eef2ed;
  color: #5d6b5b;
  font-family: 'Poppins', sans-serif;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  padding: 16px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(172, 189, 170, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.ws-box:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 26px rgba(172, 189, 170, 0.55);
}

.ws-ext {
  margin: auto;
  font-family: 'Playfair Display', serif;
  font-size: 30px;
  color: #acbdaa;
}

.ws-name {
  width: 100%;
  font-size: 13px;
  font-weight: 500;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ws-add {
  background: #fff;
  border: 2px dashed #acbdaa;
  box-shadow: none;
  justify-content: center;
}

.ws-plus {
  font-size: 40px;
  font-weight: 300;
  color: #acbdaa;
  line-height: 1;
}

.ws-add-label {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 500;
}

.ws-error {
  max-width: 1000px;
  margin: 0 auto 16px;
  text-align: center;
  font-size: 14px;
  color: #a65d5d;
}
`;

async function fileToCsv(file) {
  const baseName = file.name.replace(/\.[^.]+$/, "");
  const isExcel = /\.(xlsx|xls)$/i.test(file.name);
  if (isExcel) {
    const wb = XLSX.read(await file.arrayBuffer());
    const sheet = wb.Sheets[wb.SheetNames[0]];
    return { name: `${baseName}.csv`, content: XLSX.utils.sheet_to_csv(sheet) };
  }
  return { name: `${baseName}.csv`, content: await file.text() };
}

export default function Workspace() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [csvs, setCsvs] = useState([]);
  const [error, setError] = useState("");

  async function displayCsvs() {
    const all = await getAllCsvs();
    setCsvs(all);
  }

  useEffect(() => {
    displayCsvs();
  }, []);

  async function handleFiles(e) {
    setError("");
    const files = Array.from(e.target.files || []);
    try {
      for (const file of files) {
        if (!/\.(csv|xlsx|xls)$/i.test(file.name)) {
          setError("Please choose a CSV or XLSX file.");
          continue;
        }
        const { name, content } = await fileToCsv(file);
        await saveCsv(name, content);
      }
      await displayCsvs();
    } catch {
      setError("Something went wrong reading that file.");
    }
    e.target.value = "";
  }

  return (
    <>
      <style>{css}</style>
      <div className="ws">
        <div className="ws-top">
          <span className="ws-brand">NOVA</span>
          <h1 className="ws-heading">My Workspace</h1>
        </div>

        <div className="ws-body">
          {error && <p className="ws-error">{error}</p>}
          <div className="ws-grid">
            <button className="ws-box ws-add" onClick={() => inputRef.current.click()}>
              <span className="ws-plus">+</span>
              <span className="ws-add-label">Add CSV or XLSX</span>
            </button>

            {csvs.map((csv) => (
              <button
                key={csv.id}
                className="ws-box"
                onClick={() => navigate(`/csv/${csv.id}`)}
              >
                <span className="ws-ext">CSV</span>
                <span className="ws-name" title={csv.name}>{csv.name}</span>
              </button>
            ))}
          </div>

          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            multiple
            hidden
            onChange={handleFiles}
          />
        </div>
      </div>
    </>
  );
}