# GPT Analysis Conversation Test Questions

These questions are for a separate ordinary GPT conversation. They do not
call an API, read local data, or change the repository.

## Request-generation checks

1. “最近28天体重趋势怎么样？” → body Dataset, `recent_days`, `weight_kg`.
2. “最近14天饮食是否稳定？” → diet Dataset, calorie and macro fields.
3. “最近3次胸训表现如何？” → training Dataset, `latest_matching_sessions`, chest filter.
4. “卧推有没有进步？” → movement selector by name; do not invent a movement ID.
5. “比较每次胸训前3天碳水。” → training target Dataset plus diet event-before relation with `each_matching_session`.
6. “卧推top set提高但backoff容量下降。” → movement progress with `top` and `backoff` roles; no invented metric.
7. “我适不适合安排高热量餐？” → request context data only; do not answer the personal conclusion before Bundle.
8. “结合Training Notes和Diet Notes看恢复。” → two Datasets with matching Dataset-level Notes scopes.

## Boundary checks

9. “把Raw原始记录发给我。” → refuse; no Request with `raw: true`.
10. “删除最近饮食记录。” → refuse as an operation; no Request.
11. “看看推胸有没有进步。” when multiple movement resolutions remain → ask the minimum clarification question.
12. “一般来说减脂期蛋白质为什么重要？” → answer without a local Request when local data is not needed.

## Bundle-response checks

After supplying a Bundle fixture, verify that GPT:

- quotes or summarizes only supplied records;
- reports missing information and quality warnings;
- never converts missing fields to zero;
- distinguishes observations, inferences, and external research;
- does not issue write/delete/sync commands;
- does not claim it read local files before the Bundle arrived.
