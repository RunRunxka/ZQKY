/**
 * 壁纸存储：picked 的图片/视频一律存 IndexedDB blob（配额以百 MB 计，
 * 避免 localStorage 5MB 上限导致的"大图存不进"），localStorage 只存
 * `idb:<id>` 引用。兼容旧数据：历史上以 data URL 直存的壁纸仍可渲染。
 */

const DB_NAME = 'zqky-glass';
const STORE = 'wallpapers';

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** 存入壁纸 blob（图片/视频通用），返回 `idb:<id>` 引用。 */
export async function putBlob(blob: Blob): Promise<string> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    const id = `wp-${Date.now()}`;
    tx.objectStore(STORE).put(blob, id);
    tx.oncomplete = () => {
      db.close();
      resolve(`idb:${id}`);
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

/** 读取壁纸 blob（不存在返回 null）。 */
export async function getBlob(id: string): Promise<Blob | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(id);
    req.onsuccess = () => {
      db.close();
      resolve(req.result instanceof Blob ? req.result : null);
    };
    req.onerror = () => {
      db.close();
      reject(req.error);
    };
  });
}

/** 删除壁纸 blob（配额回收）。 */
export async function deleteBlob(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
