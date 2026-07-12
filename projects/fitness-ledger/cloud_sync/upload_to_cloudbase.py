from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_DIR / "cloud_sync" / "out"
IMPORT_DIR = OUT_DIR / "cloudbase_import"
CONFIG_FILE = PROJECT_DIR / "cloud_sync" / "cloud_sync_config.json"

SYNCED = "SYNCED"
LOCAL_NEWER = "LOCAL_NEWER"
CLOUD_MISMATCH = "CLOUD_MISMATCH"
UPLOAD_FAILED = "UPLOAD_FAILED"
NOT_CONFIGURED = "NOT_CONFIGURED"
DRY_RUN = "DRY_RUN"
NO_CHANGES = "NO_CHANGES"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_error(exc: BaseException) -> str:
    text = str(exc)
    for key, value in os.environ.items():
        key_upper = key.upper()
        if value and any(marker in key_upper for marker in ("SECRET", "TOKEN", "KEY", "PASSWORD")):
            text = text.replace(value, "***")
    return text[:500]


def _get_env_value(name: str) -> str:
    """Read env vars from the process, then Windows user/machine scope.

    Codex/desktop terminals may not inherit environment variables that were set
    after the app started. Falling back to Windows registry-backed environment
    variables keeps secrets out of source while allowing a new Python process to
    see the configured Tencent credentials.
    """
    value = os.environ.get(name, "")
    if value or not name or os.name != "nt":
        return value
    try:
        import winreg

        for root, subkey in (
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
        ):
            try:
                with winreg.OpenKey(root, subkey) as key:
                    raw, _kind = winreg.QueryValueEx(key, name)
                if raw:
                    return str(raw)
            except OSError:
                continue
    except Exception:
        return ""
    return ""


def load_sync_config(config_path: str | Path | None = None) -> dict:
    """Load sync configuration without requiring secrets in source code."""
    path = Path(config_path) if config_path else CONFIG_FILE
    file_config = _read_json(path) if path.exists() else {}
    provider = os.environ.get("FITNESS_LEDGER_CLOUD_SYNC_PROVIDER") or file_config.get("provider") or "disabled"
    env_id = os.environ.get("FITNESS_LEDGER_CLOUD_ENV_ID") or file_config.get("environment_id") or ""
    secret_id_env = str(file_config.get("secret_id_env") or "TENCENTCLOUD_SECRET_ID")
    secret_key_env = str(file_config.get("secret_key_env") or "TENCENTCLOUD_SECRET_KEY")
    database_tag_env = str(file_config.get("database_tag_env") or "FITNESS_LEDGER_CLOUD_DATABASE_TAG")
    return {
        "provider": str(provider).strip().lower(),
        "environment_id": str(env_id).strip(),
        "region": os.environ.get("TENCENTCLOUD_REGION") or file_config.get("region") or "ap-shanghai",
        "secret_id_env": secret_id_env,
        "secret_key_env": secret_key_env,
        "secret_id": _get_env_value(secret_id_env),
        "secret_key": _get_env_value(secret_key_env),
        "database_tag": _get_env_value(database_tag_env) or str(file_config.get("database_tag") or "").strip(),
        "database_tag_env": database_tag_env,
        "batch_size": int(file_config.get("batch_size") or os.environ.get("FITNESS_LEDGER_CLOUD_BATCH_SIZE") or 20),
        "import_command": os.environ.get("FITNESS_LEDGER_CLOUD_IMPORT_COMMAND") or file_config.get("import_command") or "",
        "meta_command": os.environ.get("FITNESS_LEDGER_CLOUD_META_COMMAND") or file_config.get("meta_command") or "",
        "auto_sync_enabled": bool(
            str(os.environ.get("FITNESS_LEDGER_CLOUD_AUTO_SYNC", file_config.get("auto_sync_enabled", "false"))).lower()
            in {"1", "true", "yes", "on"}
        ),
        "config_file": str(path),
    }


def config_status(config: dict | None = None) -> dict:
    """Return a safe, UI-friendly summary of upload readiness.

    Real CloudBase command sync must be verifiable. Requiring meta_command
    prevents a partial state where collection upload succeeds but fl_meta
    cannot be read back for hash/version verification.
    """
    config = config or load_sync_config()
    provider = str(config.get("provider", "disabled")).strip().lower()
    missing: list[str] = []
    reason = ""
    if provider == "mock":
        ready = True
        can_verify = True
        real_network_provider = False
        reason = "mock provider is ready for local sync simulation."
    elif provider in {"tencentcloud", "tcb", "sdk"}:
        if not str(config.get("environment_id", "")).strip():
            missing.append("environment_id")
        if not str(config.get("secret_id", "")).strip():
            missing.append(f"env:{config.get('secret_id_env') or 'TENCENTCLOUD_SECRET_ID'}")
        if not str(config.get("secret_key", "")).strip():
            missing.append(f"env:{config.get('secret_key_env') or 'TENCENTCLOUD_SECRET_KEY'}")
        try:
            _load_tencentcloud_sdk()
        except Exception:
            missing.append("python:tencentcloud-sdk-python-tcb")
        ready = not missing
        can_verify = not missing
        real_network_provider = True
        reason = (
            "Tencent CloudBase SDK sync is ready."
            if ready
            else "Tencent CloudBase SDK sync requires env_id and Tencent Cloud SecretId/SecretKey environment variables."
        )
    elif provider == "command":
        for key in ("environment_id", "import_command", "meta_command"):
            if not str(config.get(key, "")).strip():
                missing.append(key)
        ready = not missing
        can_verify = not missing
        real_network_provider = True
        reason = (
            "CloudBase command sync is ready."
            if ready
            else "CloudBase command sync requires environment_id, import_command, and meta_command."
        )
    elif provider == "disabled":
        ready = False
        can_verify = False
        real_network_provider = False
        missing = ["provider"]
        reason = "Cloud sync provider is disabled."
    else:
        ready = False
        can_verify = False
        real_network_provider = False
        missing = ["provider"]
        reason = f"Unsupported cloud sync provider: {provider}"
    return {
        "provider": provider,
        "ready": ready,
        "missing": missing,
        "reason": reason,
        "can_verify": can_verify,
        "real_network_provider": real_network_provider,
        "upload_enabled": ready,
        "auto_sync_enabled": bool(config.get("auto_sync_enabled")),
        "environment_configured": bool(config.get("environment_id")),
    }


def is_upload_configured(config: dict | None = None) -> bool:
    return bool(config_status(config).get("ready"))


def load_manifest() -> dict:
    path = IMPORT_DIR / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Build the payload before syncing.")
    return _read_json(path)


def _base_result(status: str, config: dict, manifest: dict | None = None) -> dict:
    manifest = manifest or {}
    return {
        "status": status,
        "provider": config.get("provider", "disabled"),
        "environment_id": config.get("environment_id", ""),
        "started_at": _now(),
        "finished_at": "",
        "sync_version": manifest.get("sync_version", ""),
        "payload_hash": manifest.get("payload_hash", ""),
        "latest_record_date": manifest.get("latest_record_date", ""),
        "collection_results": {},
        "cloud_verification": {},
        "config_status": config_status(config),
        "error": "",
    }


def _verify_meta(local_manifest: dict, cloud_meta: dict) -> dict:
    cloud_meta = _normalize_cloudbase_json(cloud_meta)
    checks = {
        "schema": cloud_meta.get("schema") == local_manifest.get("schema"),
        "sync_version": cloud_meta.get("sync_version") == local_manifest.get("sync_version"),
        "payload_hash": cloud_meta.get("payload_hash") == local_manifest.get("payload_hash"),
        "latest_record_date": cloud_meta.get("latest_record_date") == local_manifest.get("latest_record_date"),
        "collection_counts": cloud_meta.get("collection_counts") == local_manifest.get("collection_counts"),
        "collection_hashes": cloud_meta.get("collection_hashes") == local_manifest.get("collection_hashes"),
    }
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "cloud_latest_record_date": cloud_meta.get("latest_record_date", ""),
        "cloud_payload_hash": cloud_meta.get("payload_hash", ""),
    }


def _normalize_cloudbase_json(value: Any) -> Any:
    """Normalize Mongo Extended JSON returned by TCB RunCommands."""
    if isinstance(value, list):
        return [_normalize_cloudbase_json(item) for item in value]
    if isinstance(value, dict):
        if set(value.keys()) == {"$numberInt"}:
            try:
                return int(value["$numberInt"])
            except (TypeError, ValueError):
                return value["$numberInt"]
        if set(value.keys()) == {"$numberLong"}:
            try:
                return int(value["$numberLong"])
            except (TypeError, ValueError):
                return value["$numberLong"]
        if set(value.keys()) == {"$numberDouble"}:
            try:
                return float(value["$numberDouble"])
            except (TypeError, ValueError):
                return value["$numberDouble"]
        if set(value.keys()) == {"$oid"}:
            return value["$oid"]
        return {key: _normalize_cloudbase_json(item) for key, item in value.items()}
    return value


def _load_tencentcloud_sdk():
    from tencentcloud.common import credential  # type: ignore
    from tencentcloud.common.profile.client_profile import ClientProfile  # type: ignore
    from tencentcloud.common.profile.http_profile import HttpProfile  # type: ignore
    from tencentcloud.tcb.v20180608 import models, tcb_client  # type: ignore

    return credential, ClientProfile, HttpProfile, models, tcb_client


def _iter_import_rows(collection: str) -> list[dict]:
    path = IMPORT_DIR / f"{collection}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing import file: {path}")
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _chunks(rows: list[dict], size: int) -> list[list[dict]]:
    size = max(1, min(int(size or 20), 100))
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _make_tcb_client(config: dict):
    credential, ClientProfile, HttpProfile, _models, tcb_client = _load_tencentcloud_sdk()
    cred = credential.Credential(config["secret_id"], config["secret_key"])
    http_profile = HttpProfile()
    http_profile.endpoint = "tcb.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return tcb_client.TcbClient(cred, config.get("region") or "ap-shanghai", client_profile)


def _resolve_tcb_database_tag(client: Any, config: dict) -> str:
    """Resolve the CloudBase database instance id required by RunCommands."""
    configured = str(config.get("database_tag") or "").strip()
    if configured:
        return configured

    _credential, _ClientProfile, _HttpProfile, models, _tcb_client = _load_tencentcloud_sdk()
    request = models.DescribeEnvsRequest()
    request.EnvId = config["environment_id"]
    response = client.DescribeEnvs(request)
    for env in response.EnvList or []:
        if env.EnvId != config["environment_id"]:
            continue
        for database in env.Databases or []:
            if database.InstanceId and str(database.Status).upper() == "RUNNING":
                return database.InstanceId
        for database in env.Databases or []:
            if database.InstanceId:
                return database.InstanceId
    raise RuntimeError(
        "CloudBase database instance Tag was not found. "
        "Set FITNESS_LEDGER_CLOUD_DATABASE_TAG or cloud_sync_config.json database_tag."
    )


def _run_tcb_command(client: Any, config: dict, collection: str, command_type: str, command: dict) -> list[str]:
    _credential, _ClientProfile, _HttpProfile, models, _tcb_client = _load_tencentcloud_sdk()
    mgo_command = models.MgoCommandParam()
    mgo_command.TableName = collection
    mgo_command.CommandType = command_type
    mgo_command.Command = json.dumps(command, ensure_ascii=False, separators=(",", ":"))

    request = models.RunCommandsRequest()
    request.EnvId = config["environment_id"]
    request.Tag = _resolve_tcb_database_tag(client, config)
    request.MgoCommands = [mgo_command]
    response = client.RunCommands(request)
    return response.Data or []


def _parse_tcb_documents(data: list[str]) -> list[dict]:
    documents: list[dict] = []
    for item in data or []:
        try:
            parsed = json.loads(item)
        except Exception:
            continue
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                continue
        if isinstance(parsed, list):
            for row in parsed:
                if isinstance(row, str):
                    try:
                        row = json.loads(row)
                    except Exception:
                        continue
                if isinstance(row, dict):
                    documents.append(_normalize_cloudbase_json(row))
        elif isinstance(parsed, dict):
            cursor = parsed.get("cursor")
            if isinstance(cursor, dict):
                batch = cursor.get("firstBatch") or cursor.get("nextBatch") or []
                for row in batch:
                    if isinstance(row, dict):
                        documents.append(_normalize_cloudbase_json(row))
            elif isinstance(parsed.get("data"), list):
                for row in parsed["data"]:
                    if isinstance(row, dict):
                        documents.append(_normalize_cloudbase_json(row))
            elif any(key in parsed for key in ("sync_version", "payload_hash", "latest_record_date")):
                documents.append(_normalize_cloudbase_json(parsed))
    return documents


def _upload_tencentcloud(manifest: dict, config: dict) -> dict:
    result = _base_result(SYNCED, config, manifest)
    client = _make_tcb_client(config)
    batch_size = int(config.get("batch_size") or 20)
    collections = manifest.get("collections") or {}

    for collection in manifest.get("upload_order") or []:
        try:
            rows = _iter_import_rows(collection)
            _run_tcb_command(
                client,
                config,
                collection,
                "DELETE",
                {"delete": collection, "deletes": [{"q": {}, "limit": 0}]},
            )
            inserted = 0
            for batch in _chunks(rows, batch_size):
                if not batch:
                    continue
                _run_tcb_command(
                    client,
                    config,
                    collection,
                    "INSERT",
                    {"insert": collection, "documents": batch},
                )
                inserted += len(batch)
            expected_count = int(collections.get(collection, len(rows)))
            result["collection_results"][collection] = {
                "status": SYNCED if inserted == expected_count else CLOUD_MISMATCH,
                "file": str(IMPORT_DIR / f"{collection}.json"),
                "count": inserted,
                "expected_count": expected_count,
                "error": "" if inserted == expected_count else f"Inserted {inserted}, expected {expected_count}.",
            }
            if inserted != expected_count:
                result["status"] = CLOUD_MISMATCH
                break
        except Exception as exc:  # noqa: BLE001
            result["collection_results"][collection] = {
                "status": UPLOAD_FAILED,
                "file": str(IMPORT_DIR / f"{collection}.json"),
                "count": 0,
                "expected_count": int(collections.get(collection, 0)),
                "error": _safe_error(exc),
            }
            result["status"] = UPLOAD_FAILED
            break

    if result["status"] != UPLOAD_FAILED:
        try:
            data = _run_tcb_command(
                client,
                config,
                "fl_meta",
                "QUERY",
                {"find": "fl_meta", "filter": {}, "limit": 1},
            )
            meta_rows = _parse_tcb_documents(data)
            cloud_meta = meta_rows[0] if meta_rows else {}
            result["cloud_verification"] = _verify_meta(manifest, cloud_meta)
            if not result["cloud_verification"].get("verified"):
                result["status"] = CLOUD_MISMATCH
        except Exception as exc:  # noqa: BLE001
            result["status"] = CLOUD_MISMATCH
            result["cloud_verification"] = {"verified": False, "error": _safe_error(exc)}
    result["finished_at"] = _now()
    return result


def _upload_mock(manifest: dict, config: dict) -> dict:
    result = _base_result(SYNCED, config, manifest)
    target_dir = OUT_DIR / "mock_cloudbase"
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in manifest.get("import_files", []):
        collection = filename.removesuffix(".json")
        src = IMPORT_DIR / filename
        dst = target_dir / filename
        shutil.copy2(src, dst)
        result["collection_results"][collection] = {
            "status": SYNCED,
            "file": str(dst),
            "count": int((manifest.get("collections") or {}).get(collection, 0)),
            "error": "",
        }
    shutil.copy2(IMPORT_DIR / "manifest.json", target_dir / "manifest.json")
    meta_rows = [
        json.loads(line)
        for line in (target_dir / "fl_meta.json").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result["cloud_verification"] = _verify_meta(manifest, meta_rows[0] if meta_rows else {})
    if not result["cloud_verification"].get("verified"):
        result["status"] = CLOUD_MISMATCH
    result["finished_at"] = _now()
    return result


def _upload_command(manifest: dict, config: dict) -> dict:
    result = _base_result(SYNCED, config, manifest)
    template = config.get("import_command", "")
    env_id = config.get("environment_id", "")
    for filename in manifest.get("import_files", []):
        collection = filename.removesuffix(".json")
        file_path = IMPORT_DIR / filename
        command = template.format(
            env_id=env_id,
            collection=collection,
            file=str(file_path),
            project_dir=str(PROJECT_DIR),
        )
        try:
            completed = subprocess.run(command, shell=True, cwd=str(PROJECT_DIR), text=True, capture_output=True, timeout=180)
            ok = completed.returncode == 0
            result["collection_results"][collection] = {
                "status": SYNCED if ok else UPLOAD_FAILED,
                "file": str(file_path),
                "count": int((manifest.get("collections") or {}).get(collection, 0)),
                "error": "" if ok else (completed.stderr or completed.stdout or f"exit {completed.returncode}")[:500],
            }
            if not ok:
                result["status"] = UPLOAD_FAILED
        except Exception as exc:  # noqa: BLE001
            result["collection_results"][collection] = {
                "status": UPLOAD_FAILED,
                "file": str(file_path),
                "count": int((manifest.get("collections") or {}).get(collection, 0)),
                "error": _safe_error(exc),
            }
            result["status"] = UPLOAD_FAILED
    meta_command = config.get("meta_command", "")
    if result["status"] != UPLOAD_FAILED and meta_command:
        try:
            command = meta_command.format(env_id=env_id, project_dir=str(PROJECT_DIR))
            completed = subprocess.run(command, shell=True, cwd=str(PROJECT_DIR), text=True, capture_output=True, timeout=60)
            cloud_meta = json.loads(completed.stdout)
            if isinstance(cloud_meta, list):
                cloud_meta = cloud_meta[0] if cloud_meta else {}
            result["cloud_verification"] = _verify_meta(manifest, cloud_meta)
            if not result["cloud_verification"].get("verified"):
                result["status"] = CLOUD_MISMATCH
        except Exception as exc:  # noqa: BLE001
            result["status"] = CLOUD_MISMATCH
            result["cloud_verification"] = {"verified": False, "error": _safe_error(exc)}
    elif result["status"] != UPLOAD_FAILED:
        result["cloud_verification"] = {"verified": False, "error": "meta_command is not configured."}
        result["status"] = CLOUD_MISMATCH
    result["finished_at"] = _now()
    return result


def upload_payload(config_path: str | Path | None = None) -> dict:
    config = load_sync_config(config_path)
    manifest = load_manifest()
    readiness = config_status(config)
    if not readiness.get("ready"):
        result = _base_result(NOT_CONFIGURED, config, manifest)
        missing = ", ".join(readiness.get("missing") or [])
        result["error"] = (
            f"CloudBase upload is not fully configured. Missing: {missing}. "
            "Real upload requires fl_meta verification."
            if missing
            else readiness.get("reason", "CloudBase upload is not configured.")
        )
        result["finished_at"] = _now()
        return result
    if config["provider"] == "mock":
        return _upload_mock(manifest, config)
    if config["provider"] == "command":
        return _upload_command(manifest, config)
    if config["provider"] in {"tencentcloud", "tcb", "sdk"}:
        return _upload_tencentcloud(manifest, config)
    result = _base_result(NOT_CONFIGURED, config, manifest)
    result["error"] = f"Unsupported provider: {config['provider']}"
    result["finished_at"] = _now()
    return result
