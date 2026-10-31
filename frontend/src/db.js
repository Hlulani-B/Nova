const DB_NAME = "nova-workspace";
const STORE = "csvs";
const HISTORY = "history";

export function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(HISTORY)) {
        db.createObjectStore(HISTORY, { keyPath: "csvId" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveCsv(name, content) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add({ name, content, createdAt: Date.now() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getAllCsvs() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function getCsv(id) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).get(Number(id));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function updateCsv(id, content) {
  const db = await openDb();
  const record = await getCsv(id);
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ ...record, content, updatedAt: Date.now() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getHistory(csvId) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(HISTORY, "readonly").objectStore(HISTORY).get(Number(csvId));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveHistory(csvId, snapshots, index) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(HISTORY, "readwrite");
    tx.objectStore(HISTORY).put({ csvId: Number(csvId), snapshots, index });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}