const tcb = require("@cloudbase/node-sdk");

const COLLECTION = "fl_web_share_inbox";
const BATCH_SIZE = 100;
const KEEP_PER_OWNER = 7;

const app = tcb.init({
  env: process.env.TCB_ENV || tcb.SYMBOL_CURRENT_ENV,
});
const db = app.database();

function receivedAt(row) {
  const value = Number(row?.received_at);
  return Number.isFinite(value) ? value : 0;
}

async function readAllRows() {
  const rows = [];
  let offset = 0;
  while (true) {
    const result = await db
      .collection(COLLECTION)
      .limit(BATCH_SIZE)
      .skip(offset)
      .get();
    const batch = Array.isArray(result.data) ? result.data : [];
    rows.push(...batch);
    if (batch.length < BATCH_SIZE) break;
    offset += batch.length;
  }
  return rows;
}

/**
 * Keep only the latest seven phone-to-desktop transport items per account.
 *
 * The client only writes and reads the private collection. Cleanup is a
 * server-side timer so closing the phone page cannot prevent retention work.
 */
exports.main = async (event) => {
  const rows = await readAllRows();
  const byOwner = new Map();
  const orphanIds = [];
  let orphaned = 0;
  for (const row of rows) {
    const owner = String(row?._openid || "").trim();
    if (!owner) {
      orphaned += 1;
      if (row?._id) orphanIds.push(row._id);
      continue;
    }
    const bucket = byOwner.get(owner) || [];
    bucket.push(row);
    byOwner.set(owner, bucket);
  }

  const removeIds = [...orphanIds];
  let kept = 0;
  for (const ownerRows of byOwner.values()) {
    ownerRows.sort((a, b) => receivedAt(b) - receivedAt(a) || String(b._id || "").localeCompare(String(a._id || "")));
    kept += Math.min(ownerRows.length, KEEP_PER_OWNER);
    removeIds.push(...ownerRows.slice(KEEP_PER_OWNER).map(row => row?._id).filter(Boolean));
  }

  let removed = 0;
  for (const id of removeIds) {
    await db.collection(COLLECTION).doc(id).remove();
    removed += 1;
  }

  return {
    ok: true,
    collection: COLLECTION,
    scanned: rows.length,
    owners: byOwner.size,
    kept,
    orphaned,
    removed,
    keep_per_owner: KEEP_PER_OWNER,
    ran_at: new Date().toISOString(),
    trigger_type: event?.Type || "timer",
  };
};
