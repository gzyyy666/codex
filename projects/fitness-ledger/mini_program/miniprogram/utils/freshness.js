function formatDateTime(value) {
  const text = String(value || "");
  if (!text) return "尚未同步";
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})T?(\d{2})?:(\d{2})?/);
  if (!match) return text;
  return `${Number(match[2])}月${Number(match[3])}日${match[4] ? ` ${match[4]}:${match[5]}` : ""}`;
}

function describe(meta) {
  if (!meta) return { text: "同步状态未知", stale: true };
  const generated = String(meta.generated_at || "");
  const timestamp = Date.parse(generated);
  const ageHours = Number.isFinite(timestamp) ? (Date.now() - timestamp) / 3600000 : Infinity;
  return {
    text: `云端更新 ${formatDateTime(generated)} · 最新记录 ${String(meta.latest_record_date || "暂无")}`,
    stale: ageHours > 48
  };
}

module.exports = { describe };
