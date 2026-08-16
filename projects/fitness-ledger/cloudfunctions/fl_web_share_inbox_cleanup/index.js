const tcb = require("@cloudbase/node-sdk");

const COLLECTION = "fl_web_share_inbox";
const BATCH_SIZE = 100;

const app = tcb.init({
  env: process.env.TCB_ENV || tcb.SYMBOL_CURRENT_ENV,
});
const db = app.database();

/**
 * Delete expired phone-to-desktop transport items from CloudBase.
 *
 * The client only writes and reads the private collection. Cleanup is a
 * server-side timer so closing the phone page cannot prevent retention work.
 */
exports.main = async (event) => {
  const now = Date.now();
  let scanned = 0;
  let removed = 0;

  while (true) {
    const result = await db
      .collection(COLLECTION)
      .where({ expires_at: db.command.lt(now) })
      .limit(BATCH_SIZE)
      .get();
    const rows = Array.isArray(result.data) ? result.data : [];
    if (!rows.length) break;

    scanned += rows.length;
    for (const row of rows) {
      if (!row?._id) continue;
      await db.collection(COLLECTION).doc(row._id).remove();
      removed += 1;
    }
    if (rows.length < BATCH_SIZE) break;
  }

  return {
    ok: true,
    collection: COLLECTION,
    scanned,
    removed,
    ran_at: new Date(now).toISOString(),
    trigger_type: event?.Type || "timer",
  };
};
