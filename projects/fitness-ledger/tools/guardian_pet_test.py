from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fitness_ledger_core.shared_view_models import LedgerViewModels
from ledger_commands import LedgerCommandService


GUARDIAN = ROOT / "web_desktop" / "frontend" / "motion-lab" / "guardian"


def read_glb_json(path: Path) -> dict:
    payload = path.read_bytes()
    magic, version, declared_length = struct.unpack_from("<4sII", payload, 0)
    assert magic == b"glTF" and version == 2 and declared_length == len(payload), path
    chunk_length, chunk_type = struct.unpack_from("<II", payload, 12)
    assert chunk_type == 0x4E4F534A, path
    return json.loads(payload[20 : 20 + chunk_length].rstrip(b" \x00").decode("utf-8"))


def test_assets_and_config() -> None:
    config = json.loads((GUARDIAN / "config" / "pose-config.json").read_text(encoding="utf-8"))
    assert config["acceptedVisualBaseline"] == "v6.2"
    assert set(config["poses"]) == {
        "standing",
        "front_double_biceps",
        "side_chest",
        "back_double_biceps",
        "back_lat_spread",
        "crab_hands_clasped",
        "crab_hands_apart",
    }
    assert config["poses"]["side_chest"]["baseYaw"] == 270
    assert config["poses"]["back_lat_spread"]["baseScale"] == 0.0108
    assert config["poses"]["back_lat_spread"]["rigNorm"] == 100
    file_map = {
        "standing_front_relaxed.glb": "lowpoly-front-standing.glb",
        "front_double_biceps.glb": "lowpoly-front-double-biceps.glb",
        "side_chest.glb": "lowpoly-side-chest.glb",
        "back_double_biceps.glb": "lowpoly-rear-double-biceps.glb",
        "back_lat_spread.glb": "lowpoly-rear-lat-spread.glb",
        "most_muscular_hands_clasped.glb": "lowpoly-most-muscular.glb",
        "most_muscular_hands_apart.glb": "lowpoly-open-hand-crab.glb",
    }
    for pose in config["poses"].values():
        asset = GUARDIAN / "assets" / "lowpoly" / file_map[pose["file"]]
        document = read_glb_json(asset)
        assert not document.get("skins"), asset
        assert not document.get("animations"), asset
        assert document.get("meshes"), asset


def test_shader_and_wiring_contract() -> None:
    shader = (GUARDIAN / "guardian-shader-deformation.js").read_text(encoding="utf-8")
    ordered = [
        "guardianRotY(inputPosition, uGuardianBaseYaw)",
        "uGuardianUpperYaw) + waistPivot",
        "uGuardianUpperPitch) + waistPivot",
        "uGuardianHeadYaw) + neckPivot",
        "uGuardianHeadPitch) + neckPivot",
        "float breath",
    ]
    positions = [shader.index(marker) for marker in ordered]
    assert positions == sorted(positions)
    renderer = (GUARDIAN / "pet-guardian-static.js").read_text(encoding="utf-8")
    assert renderer.count("new THREE.WebGLRenderer") == 1
    assert renderer.count("requestAnimationFrame(animate)") == 1
    assert "activeRecord.group.rotation.y" in renderer
    assert "activeRecord.group.rotation.x" not in renderer
    assert "uGuardianBaseYaw" not in renderer
    assert "const presentationScale = petMode ? 1.06 : 1" in renderer
    assert "state.targetZoom = Math.min(Number(preset.zoom) || 1, 1.02)" in renderer
    assert "Math.max(Number(preset.camera?.[2]) || 2.18, 2.45)" in renderer
    assert "guardianControllerRegistry" in renderer and "record.group.visible = false" in renderer
    assert "const modelLoads = new Map()" in renderer
    assert "if (modelLoads.has(poseId)) return modelLoads.get(poseId)" in renderer
    assert "const modelRecords = new Set()" in renderer
    assert "scenePoseRoots" in renderer and "trackedRoots" in renderer
    tools = (ROOT / "web_desktop" / "frontend" / "tools-css3d-panels.js").read_text(encoding="utf-8")
    acceptance = (ROOT / "web_desktop" / "frontend" / "guardian-acceptance.html").read_text(encoding="utf-8")
    app = (ROOT / "web_desktop" / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "web_desktop" / "frontend" / "final-pass.css").read_text(encoding="utf-8")
    trophy_asset = ROOT / "web_desktop" / "frontend" / "assets" / "tools-pet" / "trophy-champion-v2.png"
    champion_audio = ROOT / "web_desktop" / "frontend" / "assets" / "tools-pet" / "champion-callout-clean.m4a"
    champion_audio_source = ROOT / "web_desktop" / "frontend" / "assets" / "tools-pet" / "champion-callout.m4a"
    for marker in ("fitness-ledger-pet:intent", "fitness-ledger-pet:body-regions", "presentationForSemanticEvent"):
        assert marker in tools
    assert "const isGuardianRoute" in tools
    assert "window.addEventListener('hashchange'" in tools
    assert "window.addEventListener('fitness-ledger-pet:route-change'" in tools
    assert "navigatorTiltX" in tools and "navigatorTiltY" in tools
    assert "Math.max(window.innerHeight / 1.8" in tools
    assert "y: -clamp((pointer.y - centerY)" in tools
    assert "const stationary" not in tools
    assert "const width = window.matchMedia?.('(max-width: 760px)').matches ? 208 : 256" in tools
    assert "Object.assign(navigator.style, { top: '0px', left: '0px' })" in tools
    assert "const removeArchivePetNodes" in tools
    assert "const archivePetRegistry" in tools and "const archivePetLease" in tools and "const disposeArchivePetInstances" in tools
    assert "archivePetCrossTabKey" in tools and "claimArchivePetCrossTab" in tools and "onArchivePetCrossTabStorage" in tools
    assert "tools-pet-cursor-trail" in tools and "cursorTrailPoints" in tools
    assert "championAudioUrl" in tools and "championCalloutText" in tools
    assert "champion-callout-clean.m4a" in tools
    assert "championAudioLeadTrimSeconds" in tools and "championEffectDelayMs" in tools
    assert "const championDisplayPose = 'crab_hands_apart'" in tools
    assert "championAudioGain.gain.value = 2.2" in tools and "championAudio.currentTime = championAudioLeadTrimSeconds" in tools
    assert "Number(window.__FitnessLedgerChampionAudioLeadTrimSeconds) || 0" in tools
    assert "Number(window.__FitnessLedgerChampionEffectDelayMs) || 850" in tools
    assert "loadedmetadata" in tools and "championAudioTrim" in tools
    assert "startChampionDisplay" in tools and "left-to-right-sweep" in tools
    assert "const duration = 5600" in tools and "const phase = progress < 0.5" in tools
    assert "championSequenceActive" in tools and "is-champion-sequence" in tools
    assert "silent-awaiting-audio-asset" in tools and "browser-voice-fallback" not in tools
    assert "championAudioCueFrame" in tools and "watchChampionAudioCue" in tools and "holdTriggered" in tools and "triggerChampionHold" in tools
    trigger_block = tools[tools.index("const triggerChampionHold"):tools.index("const viewportMax")]
    assert "stopChampionAudio" not in trigger_block
    assert "body.addEventListener('wheel', onPetWheel" in tools and "body.addEventListener('pointerdown', onPointerDown" in tools
    assert "MutationObserver" in tools and "cursorMode === 'trophy'" in tools
    assert "mountLegacyMousePet" not in tools
    assert "standaloneCanvas" not in renderer
    guardian_index = (GUARDIAN / "index.html").read_text(encoding="utf-8")
    assert "pose-deck.js" not in guardian_index and "mountGuardianPet" in guardian_index
    assert "READ-ONLY · NO DATA WRITES" in acceptance
    assert "presentationForSemanticEvent" in acceptance
    assert "/api/save" not in acceptance
    assert "body.dataset.petStatus" in tools and "body.title" not in tools[tools.index("function mountMousePet"):tools.index("const removeArchivePetNodes")]
    assert "trophy-champion-v2.png" in tools
    assert trophy_asset.is_file() and trophy_asset.stat().st_size > 100_000
    assert champion_audio.is_file() and champion_audio.stat().st_size > 1_000
    assert champion_audio_source.is_file() and champion_audio_source.stat().st_size > champion_audio.stat().st_size
    for marker in ("training-save", "movement-focus", "analysis-result", "needs-review", "sync-result"):
        assert marker in app
    assert ".guardian-pet-hotspots" in css and "prefers-reduced-motion:reduce" in css
    assert '.tools-pet-navigator{display:block;width:58px;height:78px}' in css
    assert '.tools-pet-navigator{position:fixed;top:0;left:0;' in css
    assert '.tools-pet-floating{width:256px!important;height:256px!important' in css
    assert '@media(max-width:760px){.tools-pet-floating{width:208px!important;height:208px!important}' in css
    assert '.guardian-pet-hotspot[data-region="back"]{right:74%;top:42%}' in css
    assert 'data-effect="champion_hold"' in css and '.tools-pet-floating.is-champion-hold' in css
    assert '.tools-pet-cursor-trail{position:fixed;z-index:1000002' in css
    assert '.tools-pet-floating.is-champion-display' in css
    assert '.tools-pet-floating.is-champion-sequence' in css


def test_personal_record_semantics() -> None:
    definition = {"movement_id": "bench", "display_name": "Bench Press", "active": True}
    previous = {"id": "old", "sets": [{"weight": 100, "reps": 5, "sets": 1}]}
    current = {"id": "new", "movement_id": "bench", "order": 1, "sets": [{"weight": 105, "reps": 4, "sets": 1}]}
    summary = LedgerViewModels.personal_record_summary(definition, current, [previous])
    assert summary and summary["newPr"] is True
    assert summary["previousBest"] == 100 and summary["currentBest"] == 105
    assert summary["deltaText"] == "+5 kg"
    assert LedgerViewModels.personal_record_summary(definition, current, []) is None
    assert LedgerViewModels.personal_record_summary(definition, {**current, "exclude_from_progress": True}, [previous]) is None
    variant_previous = {**previous, "variant": "paused"}
    assert LedgerViewModels.personal_record_summary(definition, {**current, "variant": "standard"}, [variant_previous]) is None
    reps = LedgerViewModels.personal_record_summary(
        {"movement_id": "pullup", "display_name": "Pull-up", "active": True},
        {"id": "new-reps", "sets": [{"weight": 0, "reps": 12, "sets": 3}]},
        [{"id": "old-reps", "sets": [{"weight": 0, "reps": 10, "sets": 3}]}],
    )
    assert reps and reps["metricType"] == "reps" and reps["deltaText"] == "+6 reps"


def test_save_result_is_authoritative() -> None:
    service = LedgerCommandService(Path("unused.json"), Path("unused-dictionary.json"), Path("unused-backups"), lambda *_: {})
    database = {
        "daily_records": [],
        "diet_records": [],
        "training_sessions": [],
        "raw_entries": [],
        "movements": {
            "bench": {
                "movement_id": "bench",
                "name": "Bench Press",
                "history": [{"id": "old", "movement_id": "bench", "date": "2026-08-01", "sets": [{"weight": 100, "reps": 5, "sets": 1}]}],
            }
        },
    }
    dictionary = {"movements": [{"movement_id": "bench", "display_name": "Bench Press", "aliases": ["bench"], "active": True}]}
    parsed = {
        "id": "raw-1",
        "date": "2026-08-07",
        "raw": "bench 105 x 4",
        "body": {},
        "diet": {},
        "training": {
            "split": "Chest",
            "movements": [{"movement_id": "bench", "name": "bench", "order": 1, "sets": [{"weight": 105, "reps": 4, "sets": 1}]}],
        },
    }
    result = service._apply_save(database, dictionary, parsed, "normal")
    assert result["record_id"] == database["training_sessions"][0]["id"]
    assert result["movement_count"] == 1 and result["split_label"] == "Chest"
    assert len(result["personal_records"]) == 1
    assert result["personal_records"][0]["recordId"] == database["movements"]["bench"]["history"][-1]["id"]


def main() -> None:
    test_assets_and_config()
    test_shader_and_wiring_contract()
    test_personal_record_semantics()
    test_save_result_is_authoritative()
    subprocess.run(["node", str(ROOT / "tools" / "guardian_pet_js_test.mjs")], cwd=ROOT, check=True)
    print("guardian_pet_test: PASS")


if __name__ == "__main__":
    main()
