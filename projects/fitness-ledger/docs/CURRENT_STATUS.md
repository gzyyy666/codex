# Fitness Ledger 当前状态

更新时间：2026-09-11（以 `python tools/project_status.py --write --json` 为准）

## Git 基线

- 当前分支：`main`
- `HEAD` / `main` / `origin/main`：本次正式 PWA 基线提交（完整 SHA 以 `project_status.py` 输出为准）
- 远端：`https://github.com/gzyyy666/codex.git`
- 源码工作区已封板（09-11）：PWA Training Note 首页、Movement Module 动态入口与正式缓存版本已提交并推送，工作区干净。

## 正式入口

- 正式目录：`D:\FitnessLedger\app`
- 桌面入口：桌面 `Fitness Ledger Web.lnk` → `D:\FitnessLedger\app\web_desktop\launch-desktop.vbs`
- PWA 地址：`https://cloud1-d9g35v5s1a904a8ad-1450570992.tcloudbaseapp.com`
- PWA 当前前端标记：`PWA v1.1.11 · build 2026.09.11.07`
- PWA Service Worker：`fitness-ledger-pwa-v47`，脚本资源查询版本 `20260911-07`
- CloudBase 环境：`cloud1-d9g35v5s1a904a8ad`
- Web 服务正式状态：通过 `/api/build-info` 核验；修改桌面端后必须重新写回正式目录并重启 `launcher.pyw`。

## 已交付功能

- 手机文字发送到电脑：私有 `fl_web_share_inbox`，电脑端按接收时间显示近 7 天；发送不会直接写入正式训练记录。
- 手机 Training Note：动作识别只允许动作目录名称、英文名或别名命中，未命中不显示参考动作。
- Daily Entry 自动同步：保存后重新读取 Cloud Sync 最终状态；最终 `SYNCED` 才显示成功，接口响应不完整但复核成功时显示“已复核为成功”。
- Web Body Records：体重图旁有紧凑 `7D AVG` 入口；点击后使用悬浮对话框比较两个日期各自“该日及前 6 天”的平均体重，日期 A 默认第一条体重记录，日期 B 默认最新记录。

## 继续修改前必做

1. 运行 `python tools/project_status.py --write --json`，不要依赖本文件中的旧哈希。
2. 视觉修改先读 `docs/design/STYLE_BIBLE.md`，保持暖纸张、细描边、低对比、编辑部排版和非系统默认控件风格。
3. 修改 PWA 后必须递增脚本查询版本和 Service Worker 缓存名，再执行静态预检、上传 CloudBase，并用正式 URL 检查线上版本。
4. 修改桌面端后必须写回 `D:\FitnessLedger\app`、重启正式服务，并检查 `/api/build-info`。
5. 不要把 `data/tracker.json`、`data/movement_dictionary.json` 或个人云端数据提交到 Git。

## 当前状态注意事项

`project_status.py` 会分别报告正式目录与 Git 的历史漂移；本次部署仅同步 PWA 发布范围，未主动写入正式数据。正式数据 fingerprint 以每次实时状态输出为准；完整回归若遇到历史动作词典断言失败，应单独记录，不要用改数据掩盖测试失败。
