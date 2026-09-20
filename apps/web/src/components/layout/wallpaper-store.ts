/**
 * 壁纸存储：小图走 localStorage（data URL），大视频走 IndexedDB blob。
 * 平移自 DSH-Transparent-UI-Plugin 的 wallpaper-store 思路——
 * localStorage 配额约 5MB，视频以 `idb:<id>` 标记存 IndexedDB，用时转 objectURL。
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

/** 存入视频 blob，返回 `idb:<id>` 引用。 */
export async function putVideoBlob(blob: Blob): Promise<string> {
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

/** 读取视频 blob（不存在返回 null）。 */
export async function getVideoBlob(id: string): Promise<Blob | null> {
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

/** 删除视频 blob（配额回收）。 */
export async function deleteVideoBlob(id: string): Promise<void> {
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
