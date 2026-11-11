# Music Collection Cleaner Lightweight
# Lightweight WebView2 host retaining the analyzer core and full interactive Release Map.

from __future__ import annotations

import atexit
import errno
import hashlib
import importlib
import itertools
import json
import math
import mmap
import os
import re
import shutil
import struct
import statistics
import subprocess
import sys
import tempfile
import threading
import traceback
import time
import unicodedata
import urllib.request
import zipfile
import ctypes
from collections import Counter, OrderedDict, defaultdict
from ctypes import wintypes
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

APP_NAME = "Music Collection Cleaner"
APP_VERSION = "0.5.79"
PROGRAM_DATA_DIR_NAME = "Music Collection Cleaner"
PYWEBVIEW_VERSION = "6.2.1"
WEBVIEW_PRIVATE_MODE = True
AUDIO_EXTS = {".m4a", ".flac", ".wav", ".ape", ".wv", ".mp3", ".aac", ".ogg", ".opus"}
def _logical_cpu_count() -> int:
    return max(1, os.cpu_count() or 1)


def _windows_drive_media_kind(path: Path) -> str:
    """Query seek penalty through Windows storage APIs; unknown => HDD-safe."""
    if os.name != "nt":
        return "unknown"
    try:
        absolute = Path(path).resolve(strict=False)
        anchor = absolute.anchor
        if anchor.startswith("\\\\"):
            return "network"
        if not re.match(r"^[A-Za-z]:\\", anchor):
            return "unknown"
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        k32.GetDriveTypeW.restype = wintypes.UINT
        kind = k32.GetDriveTypeW(anchor)
        if kind == 4:
            return "network"
        if kind == 2:
            return "hdd"
        if kind != 3:
            return "unknown"
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        k32.DeviceIoControl.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        handle = k32.CreateFileW("\\\\.\\" + anchor[:2], 0, 3, None, 3, 0, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            return "unknown"
        try:
            request = ctypes.create_string_buffer(struct.pack("<II", 7, 0))
            output = ctypes.create_string_buffer(64)
            returned = wintypes.DWORD()
            success = k32.DeviceIoControl(handle, 0x002D1400, request, len(request),
                                          output, len(output), ctypes.byref(returned), None)
            if success and returned.value >= 9:
                return "hdd" if output.raw[8] else "ssd"
        finally:
            k32.CloseHandle(handle)
    except Exception:
        return "unknown"
    return "unknown"


def _io_worker_plan(existing: Optional[Path], recycle: Path, selection: str = "auto",
                    classify=None, extra_roots: Sequence[Path] = ()) -> Tuple[int, str]:
    selection = str(selection or "auto").strip().lower()
    if selection != "auto":
        if not selection.isdecimal() or not 1 <= int(selection) <= 32:
            raise ValueError("Audio I/O worker count must be 1 through 32.")
        return int(selection), "Manual override"
    classify = classify or _windows_drive_media_kind
    roots = [Path(recycle)] + ([Path(existing)] if existing is not None else [])
    roots += [Path(root) for root in extra_roots]
    kinds = [str(classify(root)).lower() for root in roots]
    if "hdd" in kinds:
        return 2, "HDD"
    if "network" in kinds:
        return 2, "Network"
    if any(x != "ssd" for x in kinds):
        return 2, "Unknown storage (HDD-safe)"
    return min(8, _logical_cpu_count()), "SSD"


def _probe_workers(io_limit: Optional[int] = None) -> int:
    return max(1, int(io_limit)) if io_limit is not None else 2


def _fingerprint_workers(io_limit: Optional[int] = None) -> int:
    return max(1, int(io_limit)) if io_limit is not None else 2


def _compare_workers() -> int:
    # Fingerprint similarity is Python CPU work. Use processes, not threads, so
    # the GIL does not leave the comparison stage pinned to one logical CPU.
    return min(32, max(2, _logical_cpu_count()))

CHROMAPRINT_VERSION = "1.6.1"
CHROMAPRINT_URL = f"https://github.com/acoustid/chromaprint/releases/download/v{CHROMAPRINT_VERSION}/chromaprint-fpcalc-{CHROMAPRINT_VERSION}-windows-x86_64.zip"
CHROMAPRINT_ZIP_SHA256 = "735d6182b38e9f364b84ce6f4ccd682c75e2851de89735711d6b762d12b92a4e"

# External CD rip log quality scorer. Installed as a dependency at runtime;
# its source is not vendored into this one-file tool.
HEYBROCHECKLOG_VERSION = "1.3.2"
HEYBROCHECKLOG_COMMIT = "d3192ad2764f2682cffce4db2abc419f8ac68c69"
HEYBROCHECKLOG_SOURCE = f"https://github.com/ligh7s/hey-bro-check-log/archive/{HEYBROCHECKLOG_COMMIT}.zip"
FFMPEG_PACKAGE_ID = "Gyan.FFmpeg"
# shortcut: FFmpeg is pinned to Gyan's 8.0 essentials build; update URL and SHA-256 together to upgrade.
FFMPEG_DIRECT_URL = "https://github.com/GyanD/codexffmpeg/releases/download/8.0/ffmpeg-8.0-essentials_build.zip"
FFMPEG_ZIP_SHA256 = "647e467caf82b9fa200a562769b5ff4d736aaf725804ed2c64ea9752106fa569"

# hey-bro-check-log by ligh7s, Apache-2.0:
# https://github.com/ligh7s/hey-bro-check-log


def _bundled_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath("bundled", *parts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _download_verified_archive(url: str, destination: Path, expected_sha256: str) -> None:
    """Download a pinned dependency archive and refuse it unless its SHA-256 matches."""
    urllib.request.urlretrieve(url, destination)
    actual_sha256 = _sha256_file(destination)
    if actual_sha256 != expected_sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {url}: got {actual_sha256}")


def _open_path_location(value: str) -> None:
    """Open a displayed filesystem path using the platform-native file manager.

    Directories open directly. Files are revealed/selected when the platform
    supports it. This is the shared implementation behind every path opener in
    the UI so the global path-control invariant cannot drift between screens.
    """
    raw = str(value or "").strip()
    if not raw:
        return

    path = Path(raw).expanduser()
    if not path.exists():
        raise RuntimeError(f"Path no longer exists:\n\n{raw}")

    try:
        if os.name == "nt":
            if path.is_file():
                subprocess.Popen(
                    ["explorer.exe", "/select,", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            os.startfile(str(path))
            return

        target = path if path.is_dir() else path.parent
        import webbrowser
        webbrowser.open(target.resolve().as_uri())
    except Exception as exc:
        raise RuntimeError(f"Could not open path location: {raw}\n\n{exc}") from exc


def _documents_dir() -> Path:
    """Resolve the user's actual Windows Documents folder, including redirection."""
    if os.name == "nt":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Personal")
            return Path(os.path.expandvars(value)).expanduser()
        except Exception:
            pass
    return Path.home() / "Documents"


def _karpuzikov_tools_dir() -> Path:
    return _documents_dir() / "Karpuzikov Tools"


def _saved_data_dir() -> Path:
    """Program-isolated persistent data root required by the development rules."""
    return _karpuzikov_tools_dir() / PROGRAM_DATA_DIR_NAME


def _dependencies_dir() -> Path:
    return _saved_data_dir() / "dependencies"


def _logs_dir() -> Path:
    return _saved_data_dir() / "logs"


def _temp_dir() -> Path:
    return _saved_data_dir() / "temp"


def _cache_dir() -> Path:
    return _saved_data_dir() / "cache"


def _cleanup_legacy_webview_profile() -> None:
    """Remove the obsolete persistent WebView2 profile used by 0.2.0-0.2.5."""
    profile = _cache_dir() / "webview2-profile"
    if not profile.exists():
        return
    try:
        shutil.rmtree(profile)
    except Exception:
        # The new private-mode session never uses this directory, so a locked
        # leftover profile must not block startup.
        pass


def _state_dir() -> Path:
    return _saved_data_dir() / "state"


def _settings_path() -> Path:
    return _saved_data_dir() / "settings.json"


def _ensure_app_data_dirs() -> None:
    for path in (
        _saved_data_dir(),
        _dependencies_dir(),
        _logs_dir(),
        _temp_dir(),
        _cache_dir(),
        _state_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _json_ui_default(value):
    """Safe JSON fallback for values crossing the Qt WebEngine bridge."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        try:
            return sorted(value)
        except Exception:
            return list(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def _json_ui_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_ui_default)


_DATA_MIGRATION_DONE = False


def _migrate_legacy_app_data() -> None:
    """Migrate older analyzer data into its required per-program Documents folder."""
    global _DATA_MIGRATION_DONE
    if _DATA_MIGRATION_DONE:
        return
    _DATA_MIGRATION_DONE = True

    try:
        _ensure_app_data_dirs()
    except Exception:
        return

    # Non-destructive first-run migration from the previous standalone analyzer.
    # Never rename/delete the old root: the production DEA may still use it.
    legacy_program_root = _karpuzikov_tools_dir() / "Duplicate Edition Analyzer"
    if legacy_program_root.is_dir() and legacy_program_root != _saved_data_dir():
        try:
            prior_settings = legacy_program_root / "settings.json"
            if prior_settings.is_file() and not _settings_path().exists():
                shutil.copy2(prior_settings, _settings_path())
            for category in ("state", "cache", "logs"):
                old_category = legacy_program_root / category
                if not old_category.is_dir():
                    continue
                for base, folders, filenames in os.walk(old_category):
                    folders[:] = [name for name in folders if name != "webview2-profile"]
                    subpath = Path(base).relative_to(old_category)
                    new_folder = _saved_data_dir() / category / subpath
                    new_folder.mkdir(parents=True, exist_ok=True)
                    for filename in filenames:
                        old_file = Path(base) / filename
                        new_file = new_folder / filename
                        if old_file.is_file() and not new_file.exists():
                            shutil.copy2(old_file, new_file)
        except Exception:
            # Original data is never modified. Any partially completed copy
            # resumes on next launch, and existing new data is not overwritten.
            pass

    tools_root = _karpuzikov_tools_dir()
    current_settings = _settings_path()

    # Older builds stored every program in one shared Documents\Karpuzikov Tools\settings.json.
    legacy_settings = tools_root / "settings.json"
    if not current_settings.exists() and legacy_settings.is_file():
        try:
            data = json.loads(legacy_settings.read_text(encoding="utf-8"))
            migrated = {}
            if isinstance(data, dict):
                apps = data.get("apps")
                if isinstance(apps, dict) and isinstance(apps.get("duplicate_edition_analyzer"), dict):
                    migrated = dict(apps["duplicate_edition_analyzer"])
                elif any(
                    key in data
                    for key in (
                        "existing_discography",
                        "recycle_update_folder",
                        "save_remixes",
                        "save_live",
                    )
                ):
                    migrated = dict(data)
            if migrated:
                _atomic_write_json(current_settings, migrated)
        except Exception:
            pass

    # Move analyzer-owned flat files out of the shared Karpuzikov Tools root.
    try:
        for old in tools_root.glob("Duplicate Edition Analyzer Comparison *.jsonl"):
            target = _logs_dir() / old.name
            if not target.exists():
                shutil.copy2(str(old), str(target))
    except Exception:
        pass

    for old_name, target in (
        ("Duplicate Edition Analyzer - Crash.log", _logs_dir() / "Duplicate Edition Analyzer - Crash.log"),
        ("Duplicate Edition Analyzer - Last Move.json", _state_dir() / "last_move.json"),
    ):
        old = tools_root / old_name
        if old.is_file() and not target.exists():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(old), str(target))
            except Exception:
                pass

    # Very old undo state lived under LocalAppData. Copy it forward without
    # removing the legacy copy, so older builds can still recover if needed.
    legacy_local = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Karpuzikov" / "Duplicate Edition Analyzer"
    legacy_manifest = legacy_local / "last_move.json"
    current_manifest = _state_dir() / "last_move.json"
    if legacy_manifest.is_file() and not current_manifest.exists():
        try:
            shutil.copy2(legacy_manifest, current_manifest)
        except Exception:
            pass


def _load_app_settings() -> dict:
    _migrate_legacy_app_data()
    path = _settings_path()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _normalize_source_folders(items) -> List[Dict[str, object]]:
    """Source folder rows: path text plus a star (= existing discography).

    At least two rows are always kept so the window shows Source folder 1 and 2.
    """
    rows: List[Dict[str, object]] = []
    if isinstance(items, (list, tuple)):
        for item in items:
            if isinstance(item, dict):
                rows.append({"path": str(item.get("path", "") or "").strip(),
                             "star": bool(item.get("star", False))})
    while len(rows) < 2:
        rows.append({"path": "", "star": False})
    return rows


def _load_source_folders(saved: Dict[str, object]) -> List[Dict[str, object]]:
    """Read saved rows; settings from before v0.5.75 become starred folder 1 + folder 2."""
    if isinstance(saved.get("source_folders_v1"), list):
        return _normalize_source_folders(saved["source_folders_v1"])
    return _normalize_source_folders([
        {"path": saved.get("existing_discography", ""), "star": True},
        {"path": saved.get("recycle_update_folder", ""), "star": False},
    ])


def _split_source_folders(rows) -> Tuple[List[Path], List[Path]]:
    """Return (starred existing roots, unstarred new/update roots) with paths filled in."""
    existing: List[Path] = []
    new: List[Path] = []
    for row in _normalize_source_folders(rows):
        text = str(row["path"]).strip()
        if text:
            (existing if row["star"] else new).append(Path(text))
    return existing, new


def _save_app_settings(
    existing_discography: str,
    recycle_update: str,
    save_remixes: bool = False,
    save_live: bool = False,
    logging_enabled: bool = False,
    pattern_preferences: Optional[Dict[str, bool]] = None,
    personal_keep_rules: Optional[List[Dict[str, str]]] = None,
    io_workers: str = "auto",
    source_folders: Optional[List[Dict[str, object]]] = None,
) -> None:
    _migrate_legacy_app_data()
    previous = _load_app_settings()
    if source_folders is not None:
        folder_rows = _normalize_source_folders(source_folders)
        starred, unstarred = _split_source_folders(folder_rows)
        existing_discography = str(starred[0]) if starred else ""
        recycle_update = str(unstarred[0]) if unstarred else ""
    else:
        folder_rows = (_normalize_source_folders(previous.get("source_folders_v1"))
                       if isinstance(previous.get("source_folders_v1"), list) else None)

    # v0.22.7: positive Unusual track pattern choices are Personal Picks.
    # The old hidden preference map is deliberately cleared so removing a
    # pattern from Personal Picks cannot silently re-add it on the next review.
    saved_patterns: Dict[str, bool] = {}

    saved_personal = previous.get("personal_keep_rules_v1", [])
    if not isinstance(saved_personal, list):
        saved_personal = []
    if personal_keep_rules is not None:
        saved_personal = []
        seen_personal: Set[Tuple[str, str]] = set()
        for item in personal_keep_rules:
            if not isinstance(item, dict):
                continue
            mode = str(item.get("mode", "contains")).strip().lower()
            value = str(item.get("value", "")).strip()
            if mode not in {"contains", "exact", "pattern"}:
                continue
            if mode == "pattern":
                key = normalize_space(str(item.get("key", "") or canonical_track_pattern(value))).casefold()
                if not key:
                    continue
                value = value or key
                dedupe = ("pattern", key)
                if dedupe in seen_personal:
                    continue
                seen_personal.add(dedupe)
                saved_personal.append({"mode": "pattern", "value": value, "key": key})
                continue
            normalized = _personal_pick_normalize(value)
            if not value or not normalized:
                continue
            dedupe = (mode, normalized)
            if dedupe in seen_personal:
                continue
            seen_personal.add(dedupe)
            saved_personal.append({"mode": mode, "value": value})

    data = {
        "existing_discography": existing_discography.strip(),
        "recycle_update_folder": recycle_update.strip(),
        **({"source_folders_v1": folder_rows} if folder_rows is not None else {}),
        "save_remixes": bool(save_remixes),
        "save_live": bool(save_live),
        "logging_enabled": bool(logging_enabled),
        "io_workers": str(io_workers) if str(io_workers) == "auto" or
                      (str(io_workers).isdecimal() and 1 <= int(io_workers) <= 32) else "auto",
        "unusual_pattern_preferences_v5": saved_patterns,
        "personal_keep_rules_v1": saved_personal,
        # Preserve legacy semantic keys for update compatibility.
        "exclude_remixes": not bool(save_remixes),
        "exclude_live": not bool(save_live),
    }

    try:
        _atomic_write_json(_settings_path(), data)
    except Exception:
        # Settings persistence must never prevent the analyzer from running.
        pass


# Worst of 16 logged Watch the Throne CD/WEB pairs: 4.014241 bits/item.
# Round upward to 0.01; both primary paths share this effective score cap.
FP_MATCH_SCORE = 4.02
FP_AUTO_SCORE = FP_MATCH_SCORE
FP_AUTO_GOOD_FRACTION = 0.90
FP_AUTO_EXCELLENT_FRACTION = 0.70
FP_AUTO_MEDIAN_MAX = 4.0
FP_AUTO_P90_MAX = 10
FP_MIN_OVERLAP = 0.85

# Alternate primary profile for a different mastering/pressing, with the same
# calibrated score cap. No later waveform or metadata veto is applied.
FP_MASTERING_SCORE = FP_MATCH_SCORE
FP_MASTERING_GOOD_FRACTION = 0.80
FP_MASTERING_MEDIAN_MAX = 7.0
FP_MASTERING_P90_MAX = 14
FP_MASTERING_MIN_OVERLAP = 0.92

# Conservative third profile for a highly aligned alternate mastering.
# Keep the calibrated 4.02-bit strict and mastering score caps unchanged.
# The October 21 SLIDE evidence has 5.819162 bits/item, 93.9721% good,
# 49.6827% excellent, a median of 6, and full fingerprint overlap.
# Every guard must pass; title, artist, release name and barcode are unused.
FP_HIGH_OVERLAP_SCORE = 6.0
FP_HIGH_OVERLAP_GOOD_FRACTION = 0.93
FP_HIGH_OVERLAP_EXCELLENT_FRACTION = 0.49
FP_HIGH_OVERLAP_MEDIAN_MAX = 6.0
FP_HIGH_OVERLAP_P90_MAX = 10
FP_HIGH_OVERLAP_MIN_OVERLAP = 0.995
FP_HIGH_OVERLAP_MIN_COVERAGE = 0.995
FP_HIGH_OVERLAP_MIN_FRAMES = 120

FP_SILENCE_MIN_FRAMES = 120

# Native Illest prefix: RMS 1.19 / peak 5.00015 in 16-bit sample units.
# Keep the strict RMS floor while tolerating quantization-scale peak noise.
PADDING_SILENCE_RMS_LSB = 2.0
PADDING_SILENCE_PEAK_LSB = 8.0

# A duration difference of 8 seconds OR LESS is not a separate Version.
# Only a strictly GREATER than 8-second gap is a duration-based Version.
# Duration never proves positive duplicate identity; acoustic evidence does.
DURATION_VERSION_MAX_SAME_SECONDS = 8.0


def _duration_version_conflict(left: float, right: float) -> bool:
    a, b = float(left or 0.0), float(right or 0.0)
    return bool(a > 0.0 and b > 0.0
                and abs(a - b) > DURATION_VERSION_MAX_SAME_SECONDS + 1e-7)


def _duration_group_union(uf: "UnionFind",
                          bounds: Union[List[Tuple[float, float]], Dict[int, Tuple[float, float]]],
                          a: int, b: int) -> bool:
    """Prevent A≈B≈C transitivity from merging differently timed versions."""
    ra, rb = uf.find(a), uf.find(b)
    if ra == rb:
        return True
    low = min(bounds[ra][0], bounds[rb][0])
    high = max(bounds[ra][1], bounds[rb][1])
    if math.isfinite(low) and high - low > DURATION_VERSION_MAX_SAME_SECONDS + 1e-7:
        return False
    uf.union(ra, rb)
    bounds[uf.find(a)] = (low, high)
    return True



def _identity_track_duration(track: "Track") -> float:
    """A verified silent boundary may shorten identity timing, never media."""
    verified = float(getattr(track, "identity_duration_seconds", 0.0) or 0.0)
    raw = float(track.duration or 0.0)
    return verified if math.isfinite(verified) and 0 < verified <= raw else raw


def _coherent_duration_audio_groups(
    tracks: List["Track"],
    eligible_indices: List[int],
    acoustic_edges: List[Tuple[int, int]],
    forbidden_pairs: Optional[Set[Tuple[int, int]]] = None,
    authoritative_edges: Optional[Set[Tuple[int, int]]] = None,
) -> "UnionFind":
    """Deterministic acoustic clustering with an 8s group-diameter limit.

    A direct acoustic match is evidence, not a promise that its transitive group
    can absorb arbitrarily timed versions. Choose the interval partition with
    the fewest groups, then the most internal verified acoustic matches and
    the most co-located recordings. This prevents worker completion order or
    an incidental bridge from splitting better-supported matching editions.
    Strong fingerprint units are resolved before weaker decoded edges, without
    overriding any direct rejection. No title/duration-only identity is inferred.
    """
    durations = [_identity_track_duration(track) for track in tracks]
    components_uf = UnionFind(len(tracks))
    adjacency: Dict[int, Set[int]] = defaultdict(set)
    vetoes: Dict[int, Set[int]] = defaultdict(set)
    for left,right in forbidden_pairs or set():
        vetoes[left].add(right)
        vetoes[right].add(left)
    eligible = set(eligible_indices)
    clean_edges: Set[Tuple[int, int]] = set()
    for left, right in acoustic_edges:
        if left == right or left not in eligible or right not in eligible:
            continue
        edge = (min(left, right), max(left, right))
        if edge in clean_edges:
            continue
        clean_edges.add(edge)
        adjacency[left].add(right)
        adjacency[right].add(left)
        components_uf.union(left, right)

    components: Dict[int, List[int]] = defaultdict(list)
    for index in eligible_indices:
        components[components_uf.find(index)].append(index)
    component_edges: Dict[int,List[Tuple[int,int]]] = defaultdict(list)
    for a,b in sorted(clean_edges):
        component_edges[components_uf.find(a)].append((a,b))

    resolved = UnionFind(len(tracks))
    strong_edges = {tuple(sorted(pair)) for pair in authoritative_edges or set()} & clean_edges
    for component_root,members in components.items():
        if len(members) <= 1:
            continue
        members = sorted(members)
        member_set = set(members)
        local_edges = component_edges[component_root]
        component_strong = [pair for pair in local_edges if pair in strong_edges]
        if component_strong:
            # First use the same coherent solver on strong evidence alone.
            # Negative evidence remains binding, including inconsistent strong
            # triangles. A weaker PCM edge cannot later split a resolved unit.
            local_index = {index:position for position,index in enumerate(members)}
            local_vetoes = {(local_index[a],local_index[b]) for a in members
                for b in vetoes[a] & member_set if a < b}
            protected = _coherent_duration_audio_groups(
                [tracks[index] for index in members],list(range(len(members))),
                [(local_index[a],local_index[b]) for a,b in component_strong],local_vetoes)
            protected_members: Dict[int,List[int]] = defaultdict(list)
            for index in members:
                protected_members[protected.find(local_index[index])].append(index)
            for unit in protected_members.values():
                for index in unit[1:]:
                    resolved.union(unit[0],index)
            group_members: Dict[int,Set[int]] = defaultdict(set)
            bounds: Dict[int,Tuple[float,float]] = {}
            for index in members:
                root = resolved.find(index)
                group_members[root].add(index)
                bounds.setdefault(root,(math.inf,-math.inf))
                if math.isfinite(durations[index]) and durations[index] > 0:
                    low,high = bounds[root]
                    bounds[root] = (min(low,durations[index]),max(high,durations[index]))
            remaining = sorted(
                local_edges,
                key=lambda pair:(abs(durations[pair[0]]-durations[pair[1]]),pair))
            for a,b in remaining:
                ra,rb = resolved.find(a),resolved.find(b)
                if ra == rb:
                    continue
                if any(vetoes[index] & group_members[rb] for index in group_members[ra]):
                    continue
                if _duration_group_union(resolved,bounds,a,b):
                    merged = group_members.pop(ra) | group_members.pop(rb)
                    group_members[resolved.find(a)] = merged
            continue
        if any(not math.isfinite(durations[index])
               or durations[index] <= 0 for index in members):
            # Unknown lengths provide no version veto. Never infer identity from
            # them; use verified edges and retain duration safety for known pairs.
            bounds = [
                (duration, duration)
                if math.isfinite(duration) and duration > 0
                else (math.inf, -math.inf)
                for duration in durations
            ]
            ordered_edges = sorted(
                local_edges,
                key=lambda pair: (
                    abs(durations[pair[0]] - durations[pair[1]]),
                    pair,
                ),
            )
            group_members = {index:{index} for index in members}
            for a, b in ordered_edges:
                ra,rb = resolved.find(a),resolved.find(b)
                if ra == rb:
                    continue
                if any(vetoes[index] & group_members[rb] for index in group_members[ra]):
                    continue
                if _duration_group_union(resolved, bounds, a, b):
                    merged = group_members.pop(ra) | group_members.pop(rb)
                    group_members[resolved.find(a)] = merged
            continue

        ordered = sorted(
            members, key=lambda index: (durations[index], index)
        )
        size = len(ordered)
        # DP state: (-group_count, internal_audio_edges, total_squared_size,
        #           -total_duration_span, partition)
        best: List[Optional[tuple]] = [None] * (size + 1)
        best[0] = (0, 0, 0, 0.0, ())
        for start in range(size):
            if best[start] is None:
                continue
            lower = durations[ordered[start]]
            direct_edges = 0
            seen: Set[int] = set()
            for stop in range(start + 1, size + 1):
                current = ordered[stop - 1]
                upper = durations[current]
                if upper - lower > DURATION_VERSION_MAX_SAME_SECONDS + 1e-7:
                    break
                if vetoes[current] & seen:
                    break
                direct_edges += len(adjacency[current] & seen)
                seen.add(current)
                # A feasible segment needs a connected acoustic-match graph.
                # Duration and shared titles alone never join independent audio.
                reachable = {ordered[start]}
                frontier = [ordered[start]]
                while frontier:
                    node = frontier.pop()
                    for adjacent in adjacency[node] & seen:
                        if adjacent not in reachable:
                            reachable.add(adjacent)
                            frontier.append(adjacent)
                if len(reachable) != len(seen):
                    continue
                prior = best[start]
                span = stop - start
                candidate = (
                    prior[0] - 1,
                    prior[1] + direct_edges,
                    prior[2] + span * span,
                    prior[3] - (upper - lower),
                    prior[4] + (tuple(ordered[start:stop]),),
                )
                if best[stop] is None or candidate[:4] > best[stop][:4]:
                    best[stop] = candidate
        if best[size] is None:
            raise RuntimeError("Unable to preserve acoustic evidence within duration versions.")
        for group in best[size][4]:
            for index in group[1:]:
                resolved.union(group[0], index)
    return resolved


# Candidate routing is deliberately much cheaper than acoustic identity.
# Duration routes candidates AND vetoes significant differences in final
# matching; duration alone never establishes positive recording identity.
# Same-base-title
# and byte-identical fingerprint vectors bypass the duration router.
FP_CANDIDATE_STRONG_SHARED_TOKENS = 64
FP_CANDIDATE_WEAK_SHARED_TOKENS = 24
FP_CANDIDATE_STRONG_CONTAINMENT_MIN = 0.06
FP_CANDIDATE_WEAK_CONTAINMENT_MIN = 0.04
FP_CANDIDATE_WEIGHTED_CONTAINMENT_MIN = 0.20
FP_CANDIDATE_STRONG_DURATION_WINDOW = 45.0
FP_CANDIDATE_WEAK_DURATION_WINDOW = 15.0
FP_CANDIDATE_COMMON_TOKEN_MAX_FRACTION = 0.02
FP_CANDIDATE_COMMON_TOKEN_MAX_TRACKS = 48
FP_CANDIDATE_FAR_RARE_TOKEN_MAX_TRACKS = 16
FP_SHADOW_SAMPLE_SIZE = 256
FP_LOG_REJECT_SAMPLE_MODULUS = 2048

# v0.21.0: small bounded batches prevent ProcessPoolExecutor.map() from hiding
# progress behind giant chunks. The queue stays deep enough to keep all workers busy.
COMPARE_BATCH_SIZE = 32
COMPARE_PENDING_BATCHES_PER_WORKER = 3

# Dynamic-range/mastering comparison is a quality tie-break only. It never
# creates duplicate identity; recording identity remains fingerprint authority.
CD_RIP_LOG_ACCEPTABLE_MIN = 80

DYNAMIC_RANGE_CACHE_VERSION = 1
DYNAMIC_RANGE_EPSILON = 1e-6
DYNAMIC_RANGE_MIN_COVERAGE = 0.80
DYNAMIC_RANGE_WORKERS = 4

MANUAL_REVIEW_SCORE_MAX = 9.0
MANUAL_REVIEW_GOOD_MIN = 0.72
MANUAL_REVIEW_OVERLAP_MIN = 0.85
MANUAL_REVIEW_MEDIAN_MAX = 8.0
MANUAL_REVIEW_P90_MAX = 16


def _new_comparison_log_path(recycle: Path) -> Path:
    """The one comparison log; every run replaces it and the old timestamped logs."""
    _migrate_legacy_app_data()
    root = _logs_dir()
    try:
        root.mkdir(parents=True, exist_ok=True)
        for old_log in (*root.glob(f"{APP_NAME} Comparison 20*.jsonl"),
                        *root.glob(f"{APP_NAME} Re-Analyze 20*.jsonl")):
            old_log.unlink(missing_ok=True)
        return root / f"{APP_NAME} Comparison.jsonl"
    except Exception as exc:
        raise RuntimeError(f"Could not create comparison log: {exc}") from exc


UNICODE_REPLACEMENTS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...", "·": ".", "•": "*", "‧": ".",
    "×": "&", "÷": "/", "⁄": "/", "＆": "&", "＋": "+", "＝": "=",
    "（": "(", "）": ")", "［": "[", "］": "]", "｛": "{", "｝": "}",
    "：": ":", "；": ";", "！": "!", "？": "?", "，": ",", "．": ".",
    "／": "/", "＼": "\\", "｜": "|", "＜": "<", "＞": ">", "＿": "_",
    "©": "(c)", "®": "(R)", "™": "TM", "№": "No.",
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
}

VERSION_WORDS = {
    "remix", "mix", "live", "acoustic", "edit", "version", "extended", "instrumental",
    "acapella", "a", "capella", "dub", "demo", "radio", "club", "remaster", "remastered",
    "clean", "explicit", "single", "alternate", "alternative", "unplugged", "session",
}

EDITION_PATTERNS = [
    r"\s*\((?:deluxe(?: edition)?|limited(?: edition)?|special(?: edition)?|expanded(?: edition)?|"
    r"anniversary(?: edition)?|bonus track version|standard edition|remaster(?:ed)?(?: edition)?)\)\s*$",
    r"\s*\[(?:deluxe|limited|special|expanded|anniversary|remastered?)\]\s*$",
]


MOJIBAKE_REPLACEMENTS = {
    "â€™": "'", "â€˜": "'", "â€œ": '"', "â€": '"', "â€�": '"',
    "â€“": "-", "â€”": "-", "â€¦": "...", "Â": "",
}


def repair_mojibake(text: str) -> str:
    value = text or ""
    # UTF-8 Cyrillic interpreted as Windows-1252 appears as Ð...Ñ...
    # (e.g. 'Лучшие Хиты' -> 'Ð›ÑƒÑ‡ÑˆÐ¸Ðµ Ð¥Ð¸Ñ‚Ñ‹').
    # Older tag-processing also NFKC-folded 0xB8 to SPACE+COMBINING CEDILLA
    # and 0xB5 to Greek mu, which must be reversed before UTF-8 recovery.
    # Only accept complete, valid UTF-8 that actually restores Cyrillic.
    if value.count("Ð") + value.count("Ñ") >= 2:
        candidate = value.replace(" \u0327", "\u00b8").replace("\u03bc", "\u00b5")
        try:
            restored = candidate.encode("cp1252").decode("utf-8")
            old_cyrillic = sum("\u0400" <= ch <= "\u052f" for ch in value)
            new_cyrillic = sum("\u0400" <= ch <= "\u052f" for ch in restored)
            if new_cyrillic >= 2 and new_cyrillic > old_cyrillic:
                value = restored
        except (UnicodeError, LookupError):
            pass
    if any(marker in value for marker in ("Ã", "Â", "â")):
        try:
            repaired = value.encode("cp1252").decode("utf-8")
            if repaired.count("Ã") + repaired.count("Â") + repaired.count("â") < value.count("Ã") + value.count("Â") + value.count("â"):
                value = repaired
        except Exception:
            pass
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        value = value.replace(bad, good)
    return value


def ascii_punctuation(text: str) -> str:
    text = repair_mojibake(text)
    for src, dst in UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def clean_metadata_text(text: str) -> str:
    """Repair common encoding damage and harmless tag-edge garbage once."""
    value = unicodedata.normalize("NFKC", repair_mojibake(str(text or "")))
    value = "".join(
        ch for ch in value
        if ch in "\t\n\r" or ord(ch) >= 32
    )
    value = normalize_space(value.replace("\x00", " "))

    # A single unmatched quote at a tag edge is almost always container/tag
    # garbage (for example: BT"). Preserve balanced/embedded quotation marks.
    if value.count('"') == 1:
        if value.startswith('"'):
            value = value[1:].lstrip()
        elif value.endswith('"'):
            value = value[:-1].rstrip()
    return value


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_track_number(name: str) -> str:
    return re.sub(r"^\s*\d{1,3}(?:\s*[-._)]\s*|\s+)", "", name).strip()


def canonical_featured_title(text: str) -> str:
    text = ascii_punctuation(text)
    feat_names: List[str] = []

    def repl(m: re.Match) -> str:
        person = normalize_space(m.group(1).strip(" ()[]"))
        if person:
            feat_names.append(person)
        return " "

    patterns = [
        r"[\[(]\s*(?:feat(?:uring)?|ft)\.?\s+([^\])]+)[\])]",
        r"\s+(?:feat(?:uring)?|ft)\.?\s+([^\[(]+)$",
    ]
    for pat in patterns:
        text = re.sub(pat, repl, text, flags=re.I)
    text = normalize_space(text)
    if feat_names:
        uniq = []
        for n in feat_names:
            if n.lower() not in {x.lower() for x in uniq}:
                uniq.append(n)
        text += " (ft. " + " & ".join(uniq) + ")"
    return text


def fold_accents_and_case(text: str) -> str:
    # Accent folding is essential: 'Sí, Mamá' and 'Si, Mama' must have
    # identical routing keys. Preserve non-Latin letters (e.g. Cyrillic).
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    ).lower()


# An artist name may contain any symbol ("!!!", "$uicideboy$", "†††", "+/-"),
# so no character is deleted for being a symbol. Only whitespace and the
# separators below are ignored when two spellings are compared: file names
# cannot hold / \ : * ? " < > |, so "AC/DC" becomes "AC_DC" on disk, and
# taggers drop or swap the rest ("R.E.M." / "REM", "Guns N' Roses" /
# "Guns N Roses", "Calvin Harris (feat. X)" / "Calvin Harris feat. X").
# shortcut: brackets are ignored and & + ! stay part of the name, so
# "Sunn O)))" equals "Sunn O" and "Florence + the Machine" differs from
# "Florence & the Machine"; upgrade if real libraries show split spellings.
ARTIST_NAME_IGNORED_CHARACTERS_RE = re.compile(r"[\s_\-.,'()\[\]/\\:*?\"<>|]+")


def artist_name_comparison_key(name: str) -> str:
    folded_name = fold_accents_and_case(canonical_featured_title(name or ""))
    key = ARTIST_NAME_IGNORED_CHARACTERS_RE.sub("", folded_name)
    # A name made only of ignored characters ("?", "...") keeps them, so it
    # never becomes an empty key that equals every other empty key.
    return key or re.sub(r"\s+", "", folded_name)


def normalize_title(text: str) -> str:
    text = fold_accents_and_case(canonical_featured_title(text))
    text = text.replace("&", " and ").replace("_", " ")
    text = re.sub(r"[^\w$+()\[\]'. -]+", " ", text)
    text = re.sub(r"\s*([()\[\]])\s*", r"\1", text)
    return normalize_space(text)


def compact_title_key(text: str) -> str:
    """Letters and digits of a title in any script, without separators or symbols."""
    return re.sub(r"[\W_]+", "", normalize_title(text))


def semantic_qualifiers(text: str) -> Set[str]:
    n = normalize_title(text)
    words = set(re.findall(r"[a-z]+", n))
    q = words & VERSION_WORDS
    # The standalone letter/word "a" is not a version qualifier. It only
    # participates in the phrase "a capella".
    if "capella" in q:
        q.discard("a")
        q.discard("capella")
        q.add("acapella")
    else:
        q.discard("a")
    return q


REMIX_TRACK_RE = re.compile(r"\b(?:remix(?:es|ed)?|rmx|dub)\b", re.I)
# "Jack Beats Re-work", "Rework" and "Reworked" are remix descriptors,
# but an unrelated song named "Rework Your Life" remains a normal song.
REWORK_REMIX_DESCRIPTOR_RE = re.compile(
    r"(?:(?:\(|\[)[^\]\)]*\bre[\s-]?work(?:ed)?\b[^\]\)]*(?:\)|\])"
    r"|\s+[-:]\s+[^\r\n]*?\bre[\s-]?work(?:ed)?\b[^\r\n]*$)",
    re.I,
)
CLUB_MIX_RE = re.compile(r"\bclub\s+mix(?:es)?\b", re.I)
CHILLOUT_MIX_RE = re.compile(r"\bchillout\s+mix(?:es)?\b", re.I)
TEMPO_EFFECT_REMIX_RE = re.compile(
    r"\b(?:sped\s*up|speed\s*up|slowed(?:\s*down)?|reverb(?:ed)?|redux)\b",
    re.I,
)

# A mix credited/named after a person, DJ, producer, or act is a remix.
# Ordinary functional/style mix labels remain non-remix unless another rule says otherwise.
STANDARD_NON_REMIX_MIX_RE = re.compile(
    r"^(?:"
    r"original|extended|vip|v\.i\.p|radio|album|single|main|vocal|instrumental|studio|full|"
    r"ambient|downtempo|garage|house|trance|dance|full continuous|"
    r"7|12|7 dance|12 dance"
    r")\s+mix(?:\s*#?\d+)?$",
    re.I,
)
GENERIC_MIX_WORDS = {
    "original", "extended", "vip", "radio", "album", "single", "main", "vocal",
    "instrumental", "studio", "full", "ambient", "downtempo",
    "garage", "house", "trance", "dance", "continuous", "club", "mix", "new", "big",
    "smooth", "roll", "evolution",
}


def _mix_descriptor_candidates(text: str, allow_bare: bool = True) -> List[str]:
    source = normalize_space(ascii_punctuation(text or ""))
    if not source:
        return []

    candidates: List[str] = []
    for part in re.findall(r"[\(\[]([^\)\]]+)[\)\]]", source):
        part = normalize_space(part)
        if re.search(r"\bmix(?:\s*#?\d+)?(?:\s+by\s+.+)?\s*$", part, re.I):
            candidates.append(part)

    trailing = re.search(r"(?:^|\s+-\s+|\s*;\s*)([^;]+?\bmix(?:\s*#?\d+)?)\s*$", source, re.I)
    if trailing:
        candidates.append(normalize_space(trailing.group(1)))

    # Also catch a bare descriptor only when explicitly allowed. Full track titles
    # such as "Club Rocker (Play & Win Mix)" must not become standalone descriptor candidates.
    if allow_bare and re.fullmatch(r".+\bmix(?:\s*#?\d+)?", source, re.I):
        candidates.append(source)

    seen: Set[str] = set()
    result: List[str] = []
    for candidate in candidates:
        key = candidate.casefold()
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _is_named_person_mix_descriptor(text: str) -> bool:
    """Detect 'Someone Mix' / 'Someone's Mix' style remix credits."""
    value = normalize_space(ascii_punctuation(text or "")).strip("()[] ")
    if re.search(r"\bmix(?:\s*#?\d+)?\s+by\s+\S.+$", value, re.I):
        return True
    if not re.search(r"\bmix(?:\s*#?\d+)?$", value, re.I):
        return False

    normalized = _normalized_pattern_text(value)
    if STANDARD_NON_REMIX_MIX_RE.fullmatch(normalized):
        return False

    prefix = re.sub(r"\s+mix(?:\s*#?\d+)?$", "", value, flags=re.I).strip()
    prefix_norm = _normalized_pattern_text(prefix)
    if not prefix_norm:
        return False

    # Explicit personal/act-credit signals.
    if re.search(r"(?:'s|’s)\b|\bby\s+|\b(?:dj|mc)\s+|\s(?:&|\+|vs\.?|versus|x)\s", prefix, re.I):
        return True

    words = re.findall(r"[A-Za-z][A-Za-z0-9.'-]*", prefix)
    if not words:
        return False

    meaningful = [w for w in words if w.lower().strip(".'-") not in GENERIC_MIX_WORDS]
    if not meaningful:
        return False

    # Proper-name/act-looking labels: "Ferry Corsten", "Tom Lord-Alge",
    # "Madlib", "Timo Maas", "The Matrix", etc.
    capitalized = [
        w for w in meaningful
        if w[:1].isupper() or (len(w) >= 2 and w.isupper())
    ]
    if len(capitalized) >= 2:
        return True
    if len(meaningful) == 1 and len(capitalized) == 1:
        return True

    # DJ/producer handles often contain digits or internal capitals:
    # "only4Erol Mix", "2manydjs Mix", etc.
    compact_prefix = re.sub(r"[^A-Za-z0-9]", "", prefix)
    if re.search(r"\d", compact_prefix):
        return True
    if re.search(r"[a-z][A-Z]", compact_prefix):
        return True

    return False


LIVE_TRACK_RE = re.compile(r"\b(?:live|sessions?|unplugged)\b", re.I)
REMIX_RELEASE_RE = re.compile(
    r"\b(?:remix(?:es|ed)?|rmx|sped\s*up|speed\s*up|slowed(?:\s*down)?|reverb(?:ed)?|redux)\b",
    re.I,
)

TRACK_PATTERN_DESCRIPTOR_RE = re.compile(
    r"\b(?:mix(?:es)?|remix(?:es|ed)?|redux|dub|version|edit|acoustic|live|instrumental|"
    r"a\s*capella|acapella|demo|radio|club|remaster(?:ed)?|clean|explicit|session|"
    r"alternate|alternative|unplugged|hook|call\s*out|callout|excerpt|tv\s+track)\b",
    re.I,
)
CALLOUT_PATTERN_RE = re.compile(
    # "Call Out My Name" is a SONG TITLE, not a callout-hook descriptor.
    # Preserve recognition of Suggested Callout, research hooks and Hook.
    r"\b(?:suggested\s+(?:call\s*out|callout)(?:\s+research)?(?:\s+hook)?|"
    r"(?:call\s*out|callout)(?:\s+research)?\s+hook|"
    r"(?:call\s*out|callout)\s+research|hook)\b",
    re.I,
)


LANGUAGE_VERSION_RE = re.compile(
    r"^(?:american|arabic|brazilian|cantonese|chinese|czech|danish|dutch|english|finnish|"
    r"french|german|greek|hebrew|hindi|hungarian|italian|japanese|korean|latin|mandarin|"
    r"norwegian|polish|portuguese|romanian|russian|spanish|swedish|thai|turkish|"
    r"ukrainian|vietnamese) version$",
    re.I,
)

STANDARD_PATTERN_TOKEN_RE = re.compile(
    r"\b(?:acoustic|instrumental|acapella|a\s+capella|demo|session|unplugged|"
    r"remaster(?:ed)?|radio|clean|explicit|edited)\b",
    re.I,
)

STANDARD_EDIT_RE = re.compile(r"\b(?:re[- ]?edit|edit)\b", re.I)

STANDARD_STYLE_MIX_SUFFIX_RE = re.compile(
    r"\b(?:original|extended|vip|v\.i\.p|radio|album|single|main|vocal|instrumental|"
    r"studio|full|full continuous|ambient|chillout|downtempo|garage|house|trance|dance|"
    r"big|new|smooth|low gain)"
    r"\s+mix(?:\s*#?\d+)?$",
    re.I,
)

STANDARD_VERSION_SUFFIX_RE = re.compile(
    r"\b(?:single|album|main|original|og|clean|explicit|edited|club|full|full length|"
    r"piano|harp|guitar|vocal|acoustic|instrumental|special|speed up|sped up|"
    r"alternate|alternative|chillout|ambient|downtempo|garage|house|trance|dance|pop|rock)"
    r"\s+version$",
    re.I,
)

STANDARD_EDITION_RE = re.compile(
    r"\b(?:clean|explicit|edited|deluxe|special|limited|standard)\s+edition$",
    re.I,
)

INSTRUMENT_VERSION_RE = re.compile(
    r"(?:^|\b)(?:piano|harp|guitar|strings?|orchestral|orchestra|vocal|instrumental|"
    r"acoustic|acapella|a\s+capella|karaoke)\s+version$",
    re.I,
)


def _normalized_pattern_text(text: str) -> str:
    raw = ascii_punctuation(text or "")
    # Normalize inch/foot marks in 7"/12" version labels before title cleanup.
    raw = re.sub(r"(?<=\d)[\"'′″]+", " ", raw)
    value = normalize_title(raw)
    value = value.replace('"', " ")
    value = re.sub(r"\s+", " ", value).strip(" .;:-")
    return value


def _is_standard_pattern(text: str) -> bool:
    """True for ordinary version structures that never need manual review."""
    value = _normalized_pattern_text(text)
    if not value:
        return True

    # Parser leftovers such as "Single Version / 2008".
    if re.fullmatch(r"(?:19|20)\d{2}", value):
        return True

    if LANGUAGE_VERSION_RE.fullmatch(value):
        return True
    if STANDARD_EDITION_RE.search(value):
        return True

    # Any prefix may precede these well-known structural families.
    if STANDARD_PATTERN_TOKEN_RE.search(value):
        return True
    if STANDARD_EDIT_RE.search(value):
        return True
    if STANDARD_STYLE_MIX_SUFFIX_RE.search(value):
        return True
    if STANDARD_VERSION_SUFFIX_RE.search(value):
        return True
    if INSTRUMENT_VERSION_RE.search(value):
        return True

    # 7-inch / 12-inch forms, with arbitrary artist/remixer prefixes.
    if re.search(r"\b(?:7|12)\s+(?:dance\s+)?(?:mix|version|edit)\b", value):
        return True
    if re.search(r"\b(?:7|12)\s+.*\b(?:mix|version|edit|instrumental)\b", value):
        return True

    # Common compound forms produced by slash/semicolon naming.
    if re.search(r"\bfull\s+continuous\s+mix$", value):
        return True
    if re.search(r"\bfull\s+version(?:\s+single)?$", value):
        return True
    if re.search(r"\bbonus\s+alt\.?\s+version$", value):
        return True
    if re.search(r"\bspecial\s+dj\s+version$", value):
        return True
    if re.fullmatch(r"(?:us|uk|eu|jp|de|fr|it|es|ca|au)\s+version", value):
        return True
    if re.search(r"\b(?:80s|90s|00s|10s|20s)\s+version$", value):
        return True
    if re.search(r"^version\s+(?:piano|voix|piano[- ]voix|vocal|instrumental)\b", value):
        return True

    # "Extended Version" remains standard even with a name/prefix before it.
    if re.search(r"\bextended\s+version$", value):
        return True

    return False


def _strip_common_review_parts(text: str) -> str:
    parts = [normalize_space(p) for p in re.split(r"\s*/\s*", text or "") if normalize_space(p)]
    if len(parts) <= 1:
        return normalize_space(text or "")
    unusual = [p for p in parts if not _is_standard_pattern(p)]
    # If every slash-separated component is standard (e.g. "Single Version / 2008"),
    # there is nothing to review.
    return " / ".join(unusual)


def _should_review_pattern(text: str) -> bool:
    value = normalize_space(text or "")
    if not value:
        return False
    if CALLOUT_PATTERN_RE.search(value):
        return True
    reduced = _strip_common_review_parts(value)
    return bool(reduced and not _is_standard_pattern(reduced))


def canonical_track_pattern(text: str) -> str:
    """Stable key used for the grouped pre-analysis included-content filter."""
    value = normalize_title(text or "")
    value = re.sub(r"\bcall\s+out\b", "callout", value)
    value = re.sub(r"\ba\s+capella\b", "acapella", value)
    words = set(re.findall(r"[a-z0-9]+", value))
    # Preserve the historical Personal Picks key while grouping all callout aliases.
    if "callout" in words or words == {"hook"}:
        return "suggested callout"
    return re.sub(r"[\W_]+", " ", value).strip()


def _looks_like_trailing_pattern(text: str) -> bool:
    """Return True only when a trailing ' - ...' / ': ...' segment looks like a version descriptor.

    This deliberately rejects normal artist-title forms such as
    'INNA - I Am The Club Rocker'. A descriptor word appearing somewhere inside
    a normal song title is not enough; the trailing segment must itself have a
    version/edit/mix/live/etc. shape.
    """
    value = normalize_space(ascii_punctuation(text or ""))
    if not value:
        return False

    normalized = _normalized_pattern_text(value)
    if not normalized:
        return False

    # Explicit callout/hook review families.
    if CALLOUT_PATTERN_RE.fullmatch(value) or CALLOUT_PATTERN_RE.search(value):
        return True

    # Named mix/remix/version families and the standard structural families.
    if re.search(
        r"\b(?:mix(?:es)?|remix(?:es|ed)?|rmx|redux|dub|version|edit|acoustic|live|"
        r"instrumental|a\s*capella|acapella|demo|radio|remaster(?:ed)?|session(?:s)?|"
        r"alternate|alternative|unplugged|excerpt|tv\s+track)\b"
        r"(?:\s*(?:[-,/]|\(|\[)?\s*(?:19|20)\d{2}\s*[\)\]]?)?$",
        normalized,
        re.I,
    ):
        return True

    # 'Clean', 'Explicit', and 'Club' are too common as ordinary title words.
    # Only accept them when they form an actual descriptor at the end.
    if re.search(r"\b(?:clean|explicit)\s+(?:version|edit|mix|edition)$", normalized, re.I):
        return True
    if re.search(r"\bclub\s+(?:mix|version|edit)$", normalized, re.I):
        return True

    return False


def extract_track_patterns(title: str) -> List[Tuple[str, str]]:
    """Extract user-reviewable version descriptors without using them as duplicate evidence."""
    source = normalize_space(ascii_punctuation(strip_track_number(title or "")))
    if not source:
        return []

    candidates: List[str] = []

    for part in re.findall(r"[\(\[]([^\)\]]+)[\)\]]", source):
        part = normalize_space(part)
        if part and TRACK_PATTERN_DESCRIPTOR_RE.search(part) and _should_review_pattern(part):
            candidates.append(_strip_common_review_parts(part))

    trailing = re.search(r"\s+(?:-|:)\s+(.+)$", source)
    if trailing:
        part = normalize_space(trailing.group(1))
        if (
            part
            and _looks_like_trailing_pattern(part)
            and TRACK_PATTERN_DESCRIPTOR_RE.search(part)
            and _should_review_pattern(part)
        ):
            candidates.append(_strip_common_review_parts(part))

    # Catch callout/hook titles even when the whole track title is the descriptor,
    # e.g. "Suggested Callout Hook".
    for match in CALLOUT_PATTERN_RE.finditer(source):
        candidates.append(normalize_space(match.group(0)))

    seen: Set[Tuple[str, str]] = set()
    result: List[Tuple[str, str]] = []
    for candidate in candidates:
        key = canonical_track_pattern(candidate)
        if not key:
            continue
        pair = (key, candidate)
        if pair not in seen:
            seen.add(pair)
            result.append(pair)
    return result


def track_pattern_keys(track: "Track") -> Set[str]:
    keys: Set[str] = set()
    texts = {track.display_title, strip_track_number(track.path.stem)}
    for text in texts:
        for key, _variant in extract_track_patterns(text):
            keys.add(key)
    keys.add("title:" + normalize_title(track.display_title))
    return keys


def collect_track_patterns(tracks: List["Track"]) -> List[Dict[str, object]]:
    """Collect only non-remix, non-live patterns for manual included-content review.

    Remix/live handling remains exclusively controlled by Save Remixes and
    Save Live recordings.
    """
    grouped: Dict[str, Dict[str, object]] = {}

    for track in tracks:
        classification_text = f"{track.display_title} {strip_track_number(track.path.stem)}"
        if is_remix_text(classification_text) or is_live_text(classification_text):
            continue

        found_for_track: Set[str] = set()
        for key, variant in extract_track_patterns(track.display_title):
            row = grouped.setdefault(
                key,
                {"key": key, "variants": Counter(), "examples": [], "count": 0},
            )
            variants = row["variants"]
            variants[variant] += 1
            examples = row["examples"]
            display_example = repair_mojibake(track.display_title)
            if display_example not in examples and len(examples) < 4:
                examples.append(display_example)
            found_for_track.add(key)

        for key in found_for_track:
            grouped[key]["count"] += 1

    result: List[Dict[str, object]] = []
    for key, row in grouped.items():
        variants: Counter = row["variants"]
        if key == "suggested callout":
            label = "Callout hook"
        else:
            label = variants.most_common(1)[0][0] if variants else key

        result.append({
            "key": key,
            "label": label,
            "count": int(row["count"]),
            "variants": [name for name, _count in variants.most_common()],
            "examples": list(row["examples"]),
        })

    return sorted(result, key=lambda row: str(row["label"]).lower())


def apply_pattern_exclusions(releases: List["Release"], excluded_pattern_keys: Set[str]) -> None:
    """Apply user pattern choices to included coverage only, never duplicate identity."""
    excluded = set(excluded_pattern_keys or set())
    for release in releases:
        for track in release.tracks:
            matched = sorted(track_pattern_keys(track) & excluded)
            if matched and not track.personal_keep_rule:
                track.exclude_from_coverage = True
                track.excluded_by_pattern = ", ".join(matched)



def refresh_heuristic_release_types(releases: List["Release"]) -> None:
    """Re-run only heuristic type detection using checkbox-visible tracks."""
    for rel in releases:
        if rel.type_source != "heuristic":
            continue
        first_tags = _release_representative_type_tags(rel.tracks)
        included_tracks = [track for track in rel.tracks if not track.exclude_from_coverage]
        rel.release_type, rel.type_source = infer_release_type(
            rel.title,
            rel.path.name,
            rel.included_track_count,
            first_tags,
            sum(max(0.0, float(track.duration or 0.0)) for track in included_tracks),
            [track.artist for track in rel.tracks],
            _discography_artist_from_release(rel),
        )


def is_remix_text(text: str) -> bool:
    if re.search(r"(?:[\[(]\s*chopped\s*(?:&|and|n)\s*screwed\s*[\])]|(?:-|:)\s*chopped\s*(?:&|and|n)\s*screwed\s*$|^chopped\s*(?:&|and|n)\s*screwed$)", ascii_punctuation(text or ""), re.I):
        return True
    # Explicit Remix/Dub, Club Mix, Redux, and tempo/effect variants such as
    # Sped Up, Slowed/Slowed Down, and Reverb are remix material.
    # In addition, a mix credited/named after a person/DJ/producer/act is a remix,
    # e.g. "Ferry Corsten Mix", "Tom Lord-Alge Mix", "Madlib's Mix".
    normalized = ascii_punctuation(text or "")
    if (
        REMIX_TRACK_RE.search(normalized)
        or REWORK_REMIX_DESCRIPTOR_RE.search(normalized)
        or CLUB_MIX_RE.search(normalized)
        or CHILLOUT_MIX_RE.search(normalized)
        or TEMPO_EFFECT_REMIX_RE.search(normalized)
    ):
        return True
    return any(_is_named_person_mix_descriptor(part) for part in _mix_descriptor_candidates(normalized))


def is_live_text(text: str) -> bool:
    return bool(LIVE_TRACK_RE.search(ascii_punctuation(text or "")))


REMIX_CHILD_EDIT_RE = re.compile(
    r"^(?P<credit>.+?)\s+(?:radio\s+(?:edit|version)|extended\s+(?:mix|version|edit)|"
    r"single\s+(?:edit|version)|club\s+(?:edit|version))$",
    re.I,
)


def _descriptor_parts(text: str) -> List[str]:
    source = normalize_space(ascii_punctuation(text or ""))
    return [
        normalize_space(part)
        for part in re.findall(r"[\(\[]([^\)\]]+)[\)\]]", source)
        if normalize_space(part)
    ]


REMIX_CREDIT_GENERIC_KEYS = {
    "original", "extended", "radio", "album", "single", "main", "vocal",
    "instrumental", "club", "edit", "version", "mix", "dub",
}


def _valid_remix_credit_key(key: str) -> bool:
    return bool(key and key not in REMIX_CREDIT_GENERIC_KEYS)


def _remix_credit_key_from_explicit_descriptor(text: str) -> str:
    value = normalize_space(ascii_punctuation(text or "")).strip("()[] ")
    match = re.match(r"^(.*?)\s+(?:remix(?:ed)?|rmx|dub)\b", value, re.I)
    if match:
        key = artist_name_comparison_key(match.group(1))
        return key if _valid_remix_credit_key(key) else ""

    if _is_named_person_mix_descriptor(value):
        prefix = re.sub(
            r"\s+mix(?:\s*#?\d+)?(?:\s+by\s+.+)?\s*$",
            "",
            value,
            flags=re.I,
        ).strip()

        # Remove functional/style qualifiers immediately before "Mix" so the
        # stable remixer credit survives: "B.B.E. Club Mix" -> "B.B.E.",
        # "Junkie XL Vocal Mix" -> "Junkie XL", etc.
        words = re.findall(r"[^\W_]+(?:['.-][^\W_]+)*", prefix)
        while words:
            token = words[-1].lower().strip(".'-")
            if token in GENERIC_MIX_WORDS or token in {"classic", "7", "12"}:
                words.pop()
                continue
            break
        key = artist_name_comparison_key(" ".join(words))
        return key if _valid_remix_credit_key(key) else ""

    return ""


def _remix_credit_key_from_child_edit(text: str) -> str:
    value = normalize_space(ascii_punctuation(text or "")).strip("()[] ")
    match = REMIX_CHILD_EDIT_RE.fullmatch(value)
    if not match:
        return ""
    key = artist_name_comparison_key(match.group("credit"))
    return key if _valid_remix_credit_key(key) else ""


def _descriptor_compact_key(text: str) -> str:
    return compact_title_key(text or "")


def _primary_artist_key(track: "Track") -> str:
    source = ascii_punctuation(track.artist or "")
    source = re.split(
        r"\b(?:feat(?:uring)?|ft)\.?\b|;|,|&|\band\b|\bx\b",
        source,
        maxsplit=1,
        flags=re.I,
    )[0]
    return artist_name_comparison_key(source)


def _confident_possessive_remix_descriptor(track: "Track", text: str) -> bool:
    """Recognize credited remixer forms that omit Mix/Remix wording.

    Examples: "Simon Hale's Orchestrata". One-word first-name/self-version
    phrases such as "Brian's First Drive" remain conservative.
    """
    value = normalize_space(ascii_punctuation(text or "")).strip("()[] ")
    match = re.match(r"^(.+?)(?:'s|’s)\s+(.+)$", value, re.I)
    if not match:
        return False

    possessor = normalize_space(match.group(1))
    payload = normalize_space(match.group(2))
    if not possessor or not payload:
        return False
    if re.search(r"\b(?:producer|artist|writer|director)'?s?\b", possessor, re.I):
        return False

    possessor_key = artist_name_comparison_key(possessor)
    if not possessor_key or possessor_key == _primary_artist_key(track):
        return False

    words = re.findall(r"[^\W\d_](?:[^\W_]|[.'-])*", possessor)
    # Require a strong name/act signal. Two-word names such as Simon Hale and
    # Sander Kleinenberg are safe; one ordinary first name is not.
    return len(words) >= 2 or bool(re.fullmatch(r"(?:[A-Z]\.?){2,}", possessor))


def _contextual_remix_track_ids(releases: List["Release"]) -> Set[int]:
    """Infer remix-family children from explicit remixer evidence collection-wide.

    Evidence is scoped by base song + primary artist so unrelated same-title songs
    cannot contaminate each other. A named remixer established anywhere in the
    analyzed collection can classify its child edit/version elsewhere.

    Examples:
      Mood II Swing Remix -> Mood II Swing Radio Edit
      Lucid 12" Club Mix -> Lucid Mix Edit
      Maor Levi Remix -> Maor Levi Radio Edit
      Mantronik Electrohippy Dub -> Mantronik Electrohippy Formula
    """
    tracks = [track for release in releases for track in release.tracks]
    explicit_by_song: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for track in tracks:
        classification_text = f"{track.display_title} {strip_track_number(track.path.stem)}"
        if not is_remix_text(classification_text):
            continue

        base_key = _base_title_identity(track.display_title)
        artist_key = _primary_artist_key(track)
        if not base_key:
            continue

        for part in _descriptor_parts(track.display_title):
            credit = _remix_credit_key_from_explicit_descriptor(part)
            # Do not let the primary artist's own generic Mix/Edit wording
            # establish an external-remixer family for the whole collection.
            if credit and credit != artist_key:
                explicit_by_song[(base_key, artist_key)].add(credit)

    result: Set[int] = set()

    # A named Radio/Club Edit in an explicitly titled remix release is a
    # remixer edit, even if no sibling has the literal word 'Remix'.
    # Require a credited remixer matching the descriptor, or a multi-word
    # named producer, so ordinary generic '(Radio Edit)' stays untouched.
    for release in releases:
        if not REMIX_RELEASE_RE.search(release.title or ""):
            continue
        for track in release.tracks:
            for part in _descriptor_parts(track.display_title):
                credit = _remix_credit_key_from_child_edit(part)
                if not credit:
                    continue
                named = re.match(
                    r"^(.+?)\s+(?:radio\s+(?:edit|version)|extended\s+(?:mix|version|edit)|"
                    r"single\s+(?:edit|version)|club\s+(?:edit|version))$",
                    part, re.I
                )
                if not named:
                    continue
                credit_words = re.findall(r"[^\W\d_](?:[^\W_]|[.'-])*", named.group(1))
                tagged_remixer = credit in _artist_tag_collaborators(track)
                if tagged_remixer or len(credit_words) >= 2:
                    result.add(id(track))
                    break

    for track in tracks:
        classification_text = f"{track.display_title} {strip_track_number(track.path.stem)}"
        if is_remix_text(classification_text):
            continue

        base_key = _base_title_identity(track.display_title)
        artist_key = _primary_artist_key(track)
        parts = _descriptor_parts(track.display_title)
        if not base_key or not parts:
            continue

        explicit_keys = explicit_by_song.get((base_key, artist_key), set())
        inherited = False
        for part in parts:
            child_key = _remix_credit_key_from_child_edit(part)
            compact = _descriptor_compact_key(part)
            if child_key and child_key in explicit_keys:
                inherited = True
                break
            if any(
                compact.startswith(key) and compact != key
                for key in explicit_keys
                if _valid_remix_credit_key(key)
            ):
                inherited = True
                break
            if _confident_possessive_remix_descriptor(track, part):
                inherited = True
                break

        if inherited:
            result.add(id(track))

    return result

def _artist_signature(text: str) -> Set[str]:
    """Normalize multi-artist credits into a comparison set."""
    source = ascii_punctuation(text or "")
    parts = re.split(r"\s*(?:;|,|&|\band\b|\bx\b)\s*", source, flags=re.I)
    result: Set[str] = set()
    for part in parts:
        key = artist_name_comparison_key(part)
        if key:
            result.add(key)
    return result


def _featured_credit_signature(text: str) -> Set[str]:
    """Return featured performers explicitly named in a track title."""
    source = ascii_punctuation(text or "")
    values: List[str] = []
    for part in re.findall(r"[\[(]([^\])]+)[\])]", source):
        match = re.match(r"\s*(?:feat(?:uring)?|ft)\.?\s+(.+)", part, re.I)
        if match:
            values.extend(
                re.split(r"\s*(?:,|&|\band\b|\bx\b)\s*", match.group(1), flags=re.I)
            )
    result: Set[str] = set()
    for value in values:
        key = artist_name_comparison_key(value)
        if key:
            result.add(key)
    return result


def _has_explicit_feature_credit(text: str) -> bool:
    """Detect an explicit featured-artist credit, never a remixer credit."""
    source = normalize_space(ascii_punctuation(text or ""))
    return bool(
        re.search(
            r"(?:^|[\s\(\[\{,;:/-])(?:feat(?:uring)?|ft)\.?\s+[^\]\)\}\n]+",
            source,
            re.I,
        )
    )


def _artist_tag_collaborators(track: "Track") -> Set[str]:
    """Secondary credited performers from a semicolon, ampersand or 'with' ARTIST tag.

    ARTIST tags such as 'The Weeknd;Ariana Grande' can encode an added remix
    feature even when the TITLE contains only '(Remix)'.
    """
    normalized = ascii_punctuation(track.artist or "")
    parts = re.split(r"\s*(?:;|&|,|\bwith\b|\bfeat(?:uring)?\.?\b|\bft\.?\b|\band\b|\bx\b)\s*", normalized, flags=re.I)
    keys = [artist_name_comparison_key(part) for part in parts]
    return {key for key in keys[1:] if key and key != keys[0]} if keys else set()


def _named_remixer_suffix(track: "Track") -> Tuple[str, str]:
    """Identify named dash-suffix remix credits, not filename artist prefixes."""
    title = normalize_space(ascii_punctuation(track.display_title or ""))
    stem = normalize_space(ascii_punctuation(strip_track_number(track.path.stem)))
    if stem and stem != title:
        prefix, separator, remainder = stem.partition(" - ")
        if (
            separator
            and artist_name_comparison_key(prefix) == _primary_artist_key(track)
        ):
            stem = remainder

    sources = [title]
    if stem and stem != title:
        sources.append(stem)
    collaborators = _artist_tag_collaborators(track)
    primary = _primary_artist_key(track)

    for value in sources:
        base, separator, descriptor = value.rpartition(" - ")
        if not separator or not base:
            continue
        if artist_name_comparison_key(base) == primary:
            continue
        credit = _remix_credit_key_from_explicit_descriptor(descriptor)
        if not credit:
            continue
        name = re.split(
            r"\s+(?:remix(?:ed)?|rmx|dub)\b", descriptor, maxsplit=1, flags=re.I
        )[0].strip()
        if credit not in collaborators and len(name.split()) < 2:
            continue
        return credit, base
    return "", ""


def _track_has_featured_artist_credit(track: "Track") -> bool:
    return bool(_artist_tag_collaborators(track)) or any(
        _has_explicit_feature_credit(value)
        for value in (track.display_title, strip_track_number(track.path.stem), track.artist)
        if value
    )


def _version_descriptors(text: str) -> Set[str]:
    """Return meaningful parenthetical/bracket version descriptors.

    Featured credits, mastering labels, and generic clean/explicit advisory
    labels are not treated as separate versions here.
    """
    source = ascii_punctuation(strip_track_number(text or ""))
    result: Set[str] = set()
    for part in re.findall(r"[\[(]([^\])]+)[\])]", source):
        value = normalize_space(part)
        if re.match(r"^(?:feat(?:uring)?|ft)\.?\s+", value, re.I):
            continue
        normalized = _normalized_pattern_text(value)
        if not normalized:
            continue
        if re.fullmatch(
            r"(?:(?:album|main|original) version(?: (?:explicit|edited|clean|dirty|censored))?|"
            r"(?:explicit|edited|clean|dirty|censored)(?: version)?)",
            normalized,
            re.I,
        ):
            continue
        if re.fullmatch(r"(?:\d{4}\s+)?remaster(?:ed)?(?:\s+version)?", normalized, re.I):
            continue
        result.add(normalized)

    trailing = re.search(r"\s+(?:-|:)\s+(.+)$", source)
    if trailing:
        value = _normalized_pattern_text(trailing.group(1))
        if value and (
            TRACK_PATTERN_DESCRIPTOR_RE.search(value)
            or LANGUAGE_VERSION_RE.fullmatch(value)
        ):
            result.add(value)
    return result


def _semantic_version_descriptors(text: str) -> Set[str]:
    """Subset of descriptors that explicitly signal a different recording/version."""
    result: Set[str] = set()
    for value in _version_descriptors(text):
        if (
            TRACK_PATTERN_DESCRIPTOR_RE.search(value)
            or LANGUAGE_VERSION_RE.fullmatch(value)
            or re.search(
                r"\b(?:slowed|sped\s*up|speed\s*up|redux|nightcore|karaoke|piano|harp|guitar|"
                r"orchestral|orchestra|vocal|mode)\b",
                value,
                re.I,
            )
        ):
            result.add(value)
    return result


def _release_level_version_families(text: str) -> Set[str]:
    """Version families explicitly declared by an album/release title.

    Ordinary album-title differences are ignored. Only explicit structural
    phrases such as "Extended Versions" or named "... Mode" editions can veto
    a cross-version acoustic merge.
    """
    value = normalize_space(ascii_punctuation(text or "").lower())
    if not value:
        return set()
    families: Set[str] = set()
    patterns = (
        ("extended", r"\bextended\s+versions?\b"),
        ("acoustic", r"\bacoustic\s+versions?\b"),
        ("instrumental", r"\binstrumental\s+versions?\b"),
        ("acapella", r"\b(?:a\s*capella|acapella|acappella)\s+versions?\b"),
        ("live", r"\blive\s+versions?\b"),
        ("radio", r"\bradio\s+(?:edits?|versions?)\b"),
        ("remix", r"\bremixes\b"),
    )
    for family, pattern in patterns:
        if re.search(pattern, value, re.I):
            families.add(family)

    for descriptor in re.findall(r"[\[(]([^\])]+)[\])]", value):
        descriptor = _normalized_pattern_text(descriptor)
        if re.search(r"\bmode\b", descriptor, re.I):
            families.add(re.sub(r"[\W_]+", " ", descriptor).strip())
    return families


def _base_title_identity(text: str) -> str:
    """Title identity with bracketed descriptors/featured credits removed."""
    source = ascii_punctuation(strip_track_number(text or ""))
    source = re.sub(r"[\[(][^\])]+[\])]", " ", source)
    source = re.sub(r"\s+(?:feat(?:uring)?|ft)\.?\s+.+$", " ", source, flags=re.I)
    source = strip_advisory_version_for_match(source)
    source = re.sub(r"\b(?:\d{4}\s+)?remaster(?:ed)?\b", " ", source, flags=re.I)
    return compact_title_key(source)


def _track_number_for_routing(track: "Track") -> int:
    """Best-effort track slot used only to route an acoustic comparison."""
    if track.virtual_from_cue and int(track.cue_track_number or 0) > 0:
        return int(track.cue_track_number)

    raw = tag_lookup(track.tags, "track", "tracknumber", "track number").strip()
    match = re.match(r"^\s*(\d{1,3})(?:\s*/\s*\d+)?\s*$", raw)
    if match:
        return int(match.group(1))

    match = re.match(
        r"^\s*(\d{1,3})(?:\s*[-._)]\s*|\s+)",
        track.path.stem,
    )
    return int(match.group(1)) if match else 0


def _album_track_slot_route_key(track: "Track") -> Optional[Tuple[str, int]]:
    # Edition wording may route extra comparisons, but never proves identity.
    album = re.sub(r"[\W_]+", "", album_family(track.album or ""))
    number = _track_number_for_routing(track)
    if not album or number <= 0:
        return None
    return (album, number)


def _descriptor_family_set(values: Set[str]) -> Set[str]:
    """Collapse wording aliases into semantic families for metadata safety.

    Metadata is only allowed to veto a proven audio match when both sides state
    genuinely incompatible version families. Wording aliases such as
    "Radio Edit" vs "Play & Win Radio Version" are the same radio family.
    """
    families: Set[str] = set()
    for value in values:
        text = normalize_space(ascii_punctuation(value or "").lower())
        if not text:
            continue
        if "radio" in text:
            families.add("radio")
        elif "acoustic" in text or "unplugged" in text:
            families.add("acoustic")
        elif "instrumental" in text:
            families.add("instrumental")
        elif "a capella" in text or "acapella" in text or "acappella" in text:
            families.add("acapella")
        elif "live" in text:
            families.add("live")
        elif "remix" in text or "dub" in text or "club mix" in text:
            families.add("remix")
        elif "extended" in text:
            families.add("extended")
        else:
            # Preserve language/named-version distinctions when both sides state them.
            families.add(re.sub(r"[\W_]+", " ", text).strip())
    return families


def _definitive_acoustic_identity(
    sim: Optional[Tuple[float, float, float, int, float, float, int]]
) -> bool:
    """Legacy near-carbon diagnostic; not an additional acceptance condition."""
    if not sim:
        return False
    score, good, overlap, _shift, excellent, median, p90 = sim
    return bool(
        overlap >= 0.995
        and 0 <= score <= 2.5
        and good >= 0.995
        and excellent >= 0.98
        and median <= 2
        and p90 <= 4
    )


def _fingerprint_acoustic_coverage(fp1, fp2, sim) -> float:
    """Fraction of the longer fingerprint aligned after the chosen time shift."""
    if not sim or not fp1 or not fp2:
        return 0.0
    shift = int(sim[3])
    a0, b0 = max(shift, 0), max(-shift, 0)
    aligned = max(0, min(len(fp1) - a0, len(fp2) - b0))
    return aligned / max(1, len(fp1), len(fp2))


def _fingerprint_high_overlap_checks(
    sim, fingerprint_items: int, acoustic_coverage: float = 0.0
) -> Dict[str, bool]:
    """Require full-track, low-distance mastering evidence, not metadata."""
    if not sim:
        return {"similarity": False}
    score, good, overlap, _shift, excellent, median, p90 = sim
    return {
        "overlap": overlap >= FP_HIGH_OVERLAP_MIN_OVERLAP,
        "whole_recording_coverage": acoustic_coverage >= FP_HIGH_OVERLAP_MIN_COVERAGE,
        "score": 0 <= score <= FP_HIGH_OVERLAP_SCORE,
        "good_fraction": good >= FP_HIGH_OVERLAP_GOOD_FRACTION,
        "excellent_fraction": excellent >= FP_HIGH_OVERLAP_EXCELLENT_FRACTION,
        "median": median <= FP_HIGH_OVERLAP_MEDIAN_MAX,
        "p90": p90 <= FP_HIGH_OVERLAP_P90_MAX,
        "minimum_fingerprint_items": fingerprint_items >= FP_HIGH_OVERLAP_MIN_FRAMES,
    }


def _fingerprint_profile_identity(sim, worst_window_score=None,
                                  advisory_conflict: bool = False,
                                  fingerprint_items: int = 0,
                                  acoustic_coverage: float = 0.0) -> bool:
    """The primary Chromaprint comparison is final; later evidence cannot veto it.

    Legacy local-score/advisory arguments remain accepted for cached profiles.
    """
    if not sim:
        return False
    score, good, overlap, _shift, excellent, median, p90 = sim
    strict = (overlap >= FP_MIN_OVERLAP and 0 <= score <= FP_AUTO_SCORE
              and good >= FP_AUTO_GOOD_FRACTION and excellent >= FP_AUTO_EXCELLENT_FRACTION
              and median <= FP_AUTO_MEDIAN_MAX and p90 <= FP_AUTO_P90_MAX)
    mastering = (overlap >= FP_MASTERING_MIN_OVERLAP and 0 <= score <= FP_MASTERING_SCORE
                 and good >= FP_MASTERING_GOOD_FRACTION and median <= FP_MASTERING_MEDIAN_MAX
                 and p90 <= FP_MASTERING_P90_MAX)
    high_overlap_mastering = all(
        _fingerprint_high_overlap_checks(
            sim, fingerprint_items, acoustic_coverage).values()
    )
    return bool(strict or mastering or high_overlap_mastering)


def _explicit_identity_disagreement(a: "Track", b: "Track") -> bool:
    return {a.explicit, b.explicit} == {"clean", "explicit"}


HARD_VERSION_FAMILIES = {
    "radio", "extended", "acoustic", "instrumental", "acapella",
    "live", "remix",
}


def _hard_semantic_version_families(track: Track) -> Set[str]:
    """Return only version families strong enough to pre-veto comparison.

    Generic/named Edit/Mix labels are intentionally weak because real releases
    frequently rename the same edit ("BT Edit" vs "Radio Edit", "Album Edit" vs
    "American Radio Edit", "Edit" vs "Single Mix"). Audio must decide those.
    """
    raw = _descriptor_family_set(_semantic_version_descriptors(track.display_title))
    raw |= _release_level_version_families(track.album)
    hard: Set[str] = set()

    for family in raw:
        text = normalize_space(ascii_punctuation(family or "").lower())
        if family in HARD_VERSION_FAMILIES:
            hard.add(family)
            continue
        if LANGUAGE_VERSION_RE.fullmatch(text):
            hard.add(text)
            continue
        if re.search(
            r"\b(?:slowed|sped\s*up|speed\s*up|redux|nightcore|karaoke|"
            r"piano|harp|guitar|orchestral|orchestra|vocal|mode)\b",
            text,
            re.I,
        ):
            hard.add(text)

    return hard


def _unique_recording_root_family(track: Track) -> str:
    """Return the non-replaceable recording root carried by this title.

    A Version is only a replaceable edit of its parent recording. Radio/Edit
    wording does not create a new root. Extended, Instrumental, Acapella,
    Acoustic, Live/Unplugged and Remix do create distinct roots. Parent-family
    precedence keeps an Extended/Edit form of a Remix or Live recording inside
    that Remix/Live root instead of creating another root.
    """
    title = normalize_space(ascii_punctuation(track.display_title or "").lower())
    raw = _descriptor_family_set(_semantic_version_descriptors(track.display_title))
    raw |= _release_level_version_families(track.album)

    if track.is_remix or "remix" in raw:
        return "remix"
    if (
        track.is_live
        or "live" in raw
        or re.search(r"\b(?:live|unplugged|sessions?)\b", title, re.I)
    ):
        return "live"
    if "instrumental" in raw or re.search(r"\binstrumental\b", title, re.I):
        return "instrumental"
    if "acapella" in raw or re.search(
        r"\b(?:a\s*capella|acapella|acappella)\b", title, re.I
    ):
        return "acapella"
    if "acoustic" in raw or re.search(r"\bacoustic\b", title, re.I):
        return "acoustic"
    if "extended" in raw or re.search(r"\bextended\b", title, re.I):
        return "extended"
    return ""


def _semantic_version_conflict(a: Track, b: Track) -> bool:
    """Keep distinct recording roots separate; compare replaceable Versions."""
    root_a = _unique_recording_root_family(a)
    root_b = _unique_recording_root_family(b)

    # An unlabeled/base or Radio/Edit recording is never replaceable with a
    # distinct recording root such as Extended, Instrumental, Acoustic, Live
    # or Remix. Two tracks inside the same unique root still go to audio.
    if root_a or root_b:
        return root_a != root_b

    # For remaining explicit families, retain the older conservative hard-veto
    # behavior only when both sides clearly state disjoint semantic families.
    va = _hard_semantic_version_families(a)
    vb = _hard_semantic_version_families(b)
    if not va or not vb:
        return False
    return va.isdisjoint(vb)


def _manual_review_audio_candidate(
    sim: Optional[Tuple[float, float, float, int, float, float, int]]
) -> bool:
    """Narrow near-match window for rare human review."""
    if not sim:
        return False
    score, good, overlap, _shift, _excellent, median, p90 = sim
    return bool(
        overlap >= MANUAL_REVIEW_OVERLAP_MIN
        and score <= MANUAL_REVIEW_SCORE_MAX
        and good >= MANUAL_REVIEW_GOOD_MIN
        and median <= MANUAL_REVIEW_MEDIAN_MAX
        and p90 <= MANUAL_REVIEW_P90_MAX
    )


FEATURE_CREDIT_RE = re.compile(
    r"(?:[\[(]\s*)?\b(?:feat(?:uring)?|ft)\.?\s+"
    r"(.+?)(?=\s+-\s+|\s+[\[(]|[\])]|$)",
    re.I,
)


def _featured_artists_from_text(text: str) -> Set[str]:
    found: Set[str] = set()
    normalized = ascii_punctuation(text or "")
    for match in FEATURE_CREDIT_RE.finditer(normalized):
        credit = match.group(1)
        credit = re.split(
            r"\b(?:remix(?:es|ed)?|dub|club\s+mix(?:es)?|live)\b",
            credit,
            maxsplit=1,
            flags=re.I,
        )[0]
        for name in re.split(r"\s*(?:,|&|;|\band\b)\s*", credit, flags=re.I):
            key = artist_name_comparison_key(name)
            if key:
                found.add(key)
    return found


def featured_artists(track: "Track") -> Set[str]:
    """Extract titled features plus secondary ARTIST-tag contributors."""
    found: Set[str] = _artist_tag_collaborators(track)
    for text in (
        track.display_title,
        strip_track_number(track.path.stem),
        track.artist,
    ):
        found |= _featured_artists_from_text(text)
    return found


def remix_specific_featured_artists(track: "Track") -> Set[str]:
    """Return features explicitly attached to the remix/version, not base artist credit.

    A filename prefix such as "B-Tribe feat. Deborah Blando - Nanita (... Remix)"
    is the song's artist credit and must not rescue the remix. Without a normal
    counterpart, only a feature written in the title AFTER remix/mix/dub wording
    is strong enough to count as remix-added.
    """
    sources = [track.display_title]
    stem = strip_track_number(track.path.stem)
    if " - " in stem:
        sources.append(stem.split(" - ", 1)[1])
    else:
        sources.append(stem)

    found: Set[str] = set()
    remix_marker_re = re.compile(
        r"\b(?:remix(?:es|ed)?|rmx|dub|mix|re[\s-]?work(?:ed)?)\b", re.I
    )
    feature_marker_re = re.compile(r"\b(?:feat(?:uring)?|ft)\.?\b", re.I)
    for source in sources:
        text = ascii_punctuation(source or "")
        remix_match = remix_marker_re.search(text)
        if not remix_match:
            continue
        for feature_match in feature_marker_re.finditer(text):
            if feature_match.start() <= remix_match.start():
                continue
            tail = text[feature_match.start():]
            found |= _featured_artists_from_text(tail)
    return found


def _personal_pick_normalize(text: str) -> str:
    value = normalize_title(ascii_punctuation(text or ""))
    return re.sub(r"[\W_]+", " ", value).strip()


def _personal_pattern_key(item: Dict[str, str]) -> str:
    if not isinstance(item, dict) or str(item.get("mode", "")).strip().lower() != "pattern":
        return ""
    raw_key = str(item.get("key", "")).strip()
    if raw_key:
        return normalize_space(raw_key).casefold()
    return normalize_space(canonical_track_pattern(str(item.get("value", "")))).casefold()


def _personal_pattern_keys(rules: List[Dict[str, str]]) -> Set[str]:
    return {
        key
        for item in rules
        if (key := _personal_pattern_key(item))
    }



def _normalize_pattern_categories(raw: object) -> Dict[str, Dict[str, str]]:
    """Allow persisted Remix/Live/Skip decisions, keyed by canonical pattern."""
    cleaned: Dict[str, Dict[str, str]] = {}
    if isinstance(raw, dict):
        source = [
            {**value, "key": key}
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, dict)
        ]
    elif isinstance(raw, list):
        source = raw
    else:
        return cleaned
    for item in source:
        if not isinstance(item, dict):
            continue
        key = normalize_space(str(item.get("key", ""))).casefold()
        kind = str(item.get("kind", "")).strip().lower()
        if not key or kind not in {"remix", "live", "skip"}:
            continue
        label = normalize_space(str(item.get("label", ""))) or key
        cleaned[key] = {"kind": kind, "label": label}
    return cleaned


def _pattern_categories_path() -> Path:
    return _state_dir() / "unusual_pattern_categories.json"


def _load_pattern_categories() -> Dict[str, Dict[str, str]]:
    try:
        payload = json.loads(_pattern_categories_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        return {}
    return _normalize_pattern_categories(payload.get("categories", {}))


def _save_pattern_categories(categories: Dict[str, Dict[str, str]]) -> None:
    """Do not swallow a failed write: the user must know if a choice was lost."""
    _atomic_write_json(_pattern_categories_path(), {
        "schema": 1,
        "categories": _normalize_pattern_categories(categories),
    })


def _pending_pattern_reviews_path() -> Path:
    return _state_dir() / "pending_pattern_reviews.json"


def _clean_pending_pattern_reviews(rows: object) -> List[Dict[str, object]]:
    """Retain only canonical grouped-pattern context, never source audio data."""
    if not isinstance(rows, list):
        return []
    cleaned: Dict[str, Dict[str, object]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        key = normalize_space(str(item.get("key", ""))).casefold()
        if not key:
            continue
        def safe_strings(value, limit):
            return [str(s)[:300] for s in value[:limit] if str(s).strip()] if isinstance(value, list) else []
        try:
            count = max(0, int(item.get("count", 0) or 0))
        except (ValueError, TypeError, OverflowError):
            count = 0
        cleaned[key] = {
            "key": key,
            "label": str(item.get("label", key))[:300],
            "count": count,
            "variants": safe_strings(item.get("variants", []), 8),
            "examples": safe_strings(item.get("examples", []), 4),
        }
    return sorted(cleaned.values(), key=lambda row: str(row["label"]).casefold())


def _load_pending_pattern_reviews() -> List[Dict[str, object]]:
    try:
        payload = json.loads(_pending_pattern_reviews_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        return []
    return _clean_pending_pattern_reviews(payload.get("patterns"))


def _save_pending_pattern_reviews(rows: List[Dict[str, object]]) -> None:
    _atomic_write_json(_pending_pattern_reviews_path(), {
        "schema": 1, "patterns": _clean_pending_pattern_reviews(rows),
    })


def _promote_pattern_choice(clicked_kind: str, saved_kind: str) -> bool:
    """Only an explicit Keep or re-click of a saved category promotes to Picks."""
    return clicked_kind == "keep" or bool(saved_kind and clicked_kind == saved_kind)


def _track_classification_patterns(track: "Track") -> List[Tuple[str, str]]:
    """Choose explicit descriptors, otherwise exact track title (never broad substring)."""
    found = extract_track_patterns(track.display_title)
    if not found:
        found = extract_track_patterns(strip_track_number(track.path.stem))
    if found:
        return found
    title = normalize_space(track.display_title)
    return [("title:" + normalize_title(title), title)] if title else []


def _classify_track_pattern(track: "Track", kind: str) -> Tuple[str, str]:
    """Return an actionable pattern; prioritize descriptive tokens over filenames."""
    options = _track_classification_patterns(track)
    if not options or kind not in {"remix", "live", "skip", "keep"}:
        raise ValueError("No usable track descriptor or category.")
    return options[0]


def _classified_track_pattern_kinds(
    track: "Track", categories: Dict[str, Dict[str, str]],
) -> Set[str]:
    if not categories:
        return set()
    return {
        categories[key]["kind"]
        for key in track_pattern_keys(track)
        if key in categories
    }


def _unresolved_track_patterns(
    patterns: List[Dict[str, object]],
    personal_keep_rules: List[Dict[str, str]],
    pattern_categories: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[Dict[str, object]]:
    """Return only unusual patterns that still need an explicit user decision.

    A Pattern rule already saved in Personal Picks is a resolved persistent keep
    decision. Re-prompting it on every analysis is redundant and makes the review
    impossible to use as a true "new/unknown pattern" gate.
    """
    resolved_keys = _personal_pattern_keys(personal_keep_rules)
    resolved_keys.update(_normalize_pattern_categories(pattern_categories).keys())
    if not resolved_keys:
        return list(patterns)

    return [
        item
        for item in patterns
        if normalize_space(str(item.get("key", ""))).casefold() not in resolved_keys
    ]


def _add_personal_pattern_rule(
    rules: List[Dict[str, str]],
    key: str,
    label: str,
) -> bool:
    normalized_key = normalize_space(str(key or "")).casefold()
    if not normalized_key:
        return False
    display = str(label or "").strip() or normalized_key
    for item in rules:
        if _personal_pattern_key(item) == normalized_key:
            item["mode"] = "pattern"
            item["key"] = normalized_key
            if not str(item.get("value", "")).strip() or str(item.get("value", "")).strip().casefold() == normalized_key:
                item["value"] = display
            return False
    rules.append({"mode": "pattern", "value": display, "key": normalized_key})
    return True


def _load_personal_keep_rules(saved: Dict[str, object]) -> List[Dict[str, str]]:
    rules: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    raw_rules = saved.get("personal_keep_rules_v1", [])
    if isinstance(raw_rules, list):
        for item in raw_rules:
            if not isinstance(item, dict):
                continue
            mode = str(item.get("mode", "contains")).strip().lower()
            value = str(item.get("value", "")).strip()
            if mode not in {"contains", "exact", "pattern"}:
                continue
            if mode == "pattern":
                key = normalize_space(str(item.get("key", "") or canonical_track_pattern(value))).casefold()
                if not key:
                    continue
                dedupe = ("pattern", key)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                rules.append({"mode": "pattern", "value": value or key, "key": key})
                continue
            normalized = _personal_pick_normalize(value)
            if not value or not normalized:
                continue
            dedupe = (mode, normalized)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            rules.append({"mode": mode, "value": value})

    legacy = saved.get("unusual_pattern_preferences_v5", {})
    if isinstance(legacy, dict):
        for raw_key, keep in legacy.items():
            if not bool(keep):
                continue
            key = normalize_space(str(raw_key or "")).casefold()
            if key and ("pattern", key) not in seen:
                seen.add(("pattern", key))
                rules.append({"mode": "pattern", "value": key, "key": key})
    return rules


def _personal_pick_match(track: "Track", rules: List[Dict[str, str]]) -> str:
    """Return the matching user rule, or an empty string.

    Personal picks are preference metadata only. They can override an unchecked
    remix/live checkbox, but they never create duplicate identity.
    """
    title_values = {
        _personal_pick_normalize(track.display_title),
        _personal_pick_normalize(strip_track_number(track.path.stem)),
    }
    title_values.discard("")

    for item in rules:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode", "contains")).strip().lower()
        if mode == "pattern":
            key = _personal_pattern_key(item)
            if key and key in track_pattern_keys(track):
                return str(item.get("value", key))
            continue
        raw = str(item.get("value", "")).strip()
        needle = _personal_pick_normalize(raw)
        if not needle:
            continue

        if mode == "exact":
            matched = needle in title_values
        else:
            matched = any(needle in value for value in title_values)

        if matched:
            return raw
    return ""


def configure_exclusions(
    releases: List["Release"],
    exclude_remixes: bool,
    exclude_live: bool,
    personal_keep_rules: Optional[List[Dict[str, str]]] = None,
    pattern_categories: Optional[Dict[str, Dict[str, str]]] = None,
) -> None:
    """Classify wanted audio before every expensive analysis stage.

    Unchecked Remix/Live categories are early eliminations unless a genuine
    remix-added feature, explicit main-artist remix, or user's Personal Pick
    provides the documented positive exception. A vocalist already credited
    on a normal version of the song is not a remix-added feature.
    """
    tracks = [track for rel in releases for track in rel.tracks]
    rules = list(personal_keep_rules or [])
    categories = _normalize_pattern_categories(pattern_categories)
    contextual_remix_ids = _contextual_remix_track_ids(releases)
    main_artist_by_track = {
        id(track): _discography_artist_from_release(rel)
        for rel in releases for track in rel.tracks
    }
    user_named_remix_ids: Set[int] = set()

    # Pass 1: classify every track before deciding the featured-remix exception.
    for track in tracks:
        classification_text = f"{track.display_title} {strip_track_number(track.path.stem)}"
        user_kinds = _classified_track_pattern_kinds(track, categories)
        if "remix" in user_kinds:
            user_named_remix_ids.add(id(track))
        track.is_remix = bool(
            is_remix_text(classification_text)
            or id(track) in contextual_remix_ids
            or "remix" in user_kinds
        )
        track.is_live = bool(is_live_text(classification_text) or "live" in user_kinds)

    # Establish the ordinary song feature set from non-remix/non-live versions
    # anywhere in the analyzed collection. This prevents "BT feat. Singer" from
    # making every remix of that already-featured song survive Save Remixes OFF.
    base_features: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    base_song_keys: Set[Tuple[str, str]] = set()
    for track in tracks:
        if track.is_remix or track.is_live:
            continue
        base_key = _base_title_identity(track.display_title)
        artist_key = _primary_artist_key(track)
        if base_key:
            song_key = (base_key, artist_key)
            base_song_keys.add(song_key)
            base_features[song_key] |= featured_artists(track)

    # Pass 2: apply the early elimination policy. Key the baseline by song +
    # primary artist so unrelated same-title songs cannot contaminate each other.
    for track in tracks:
        base_key = _base_title_identity(track.display_title)
        named_suffix_credit, named_suffix_base = _named_remixer_suffix(track)
        if track.is_remix and named_suffix_credit:
            base_key = _base_title_identity(named_suffix_base) or base_key
        artist_key = _primary_artist_key(track)
        song_key = (base_key, artist_key)
        # A named remix normally credits the REMIXER as an additional ARTIST.
        # Treating that credit as a featured vocalist incorrectly rescues whole
        # remix albums (real INNA/Gimme Gimme 11-track log, 2026-10-12).
        # For named mixes, only an explicit feat./ft. credit is feature
        # evidence. Plain (Remix) with a new collaborator remains eligible
        # when an ordinary counterpart proves the collaborator is actually new.
        named_remixer = track.is_remix and (
            id(track) in contextual_remix_ids
            or id(track) in user_named_remix_ids
            or bool(named_suffix_credit)
            or any(
                _remix_credit_key_from_explicit_descriptor(part)
                for text in (track.display_title, strip_track_number(track.path.stem))
                for part in _descriptor_parts(text)
            )
        )
        if named_remixer:
            features = set().union(*(
                _featured_artists_from_text(text)
                for text in (track.display_title, strip_track_number(track.path.stem), track.artist)
            ))
        else:
            features = featured_artists(track)
        ordinary_features = base_features.get(song_key, set())

        if song_key in base_song_keys:
            added_features = features - ordinary_features
        else:
            # Without an ordinary counterpart, unqualified secondary ARTIST
            # entries are ambiguous for named remixes, not positive evidence.
            # A feature stated AFTER Remix/Mix/Dub remains strong evidence.
            if named_remixer:
                added_features = remix_specific_featured_artists(track)
                if _has_explicit_feature_credit(track.artist):
                    added_features |= _featured_artists_from_text(track.artist)
            else:
                collaborators = _artist_tag_collaborators(track)
                # Keep existing support for generic '(Remix)' with one clearly
                # credited collaborator, but not a 3+ act ambiguous credit.
                tag_feature = collaborators if len(collaborators) == 1 else set()
                added_features = remix_specific_featured_artists(track) | tag_feature

        track.remix_feature_exception = bool(
            track.is_remix
            and _track_has_featured_artist_credit(track)
            and added_features
        )
        track.personal_keep_rule = ""
        track.excluded_by_pattern = ""
        track.group_id = -1
        track.acoustic_policy_reconciled = False
        selected_categories = _classified_track_pattern_kinds(track, categories)

        remix_eliminated = bool(
            exclude_remixes
            and track.is_remix
            and not track.remix_feature_exception
            and not _main_artist_remix(track, main_artist_by_track.get(id(track), ""))
        )
        live_eliminated = bool(exclude_live and track.is_live)
        track.explicit_category_exclusion = bool(
            (remix_eliminated and "remix" in selected_categories)
            or (live_eliminated and "live" in selected_categories)
        )

        # A genuinely remix-added feature remains wanted when Save Remixes is OFF,
        # but a track that is ALSO Live still obeys Save Live independently.
        track.exclude_from_coverage = remix_eliminated or live_eliminated

        if rules:
            matched_rule = _personal_pick_match(track, rules)
            if matched_rule:
                track.personal_keep_rule = matched_rule
                # Explicit Keep/Personal Picks overrides remix/live exclusion.
                track.exclude_from_coverage = False

        # An exclusion controls retention, never acoustic identification.
        # Preserve any fingerprint for grouping/Ignore across mislabeled editions.
        if track.exclude_from_coverage:
            track.dynamic_lufs = None
            track.dynamic_lra = None
            track.dynamic_true_peak_dbfs = None
            track.dynamic_rms_dbfs = None
            track.dynamic_crest_db = None
            track.dynamic_score = None


def normalize_artist(text: str) -> str:
    primary_credit = re.split(r"\b(?:feat(?:uring)?|ft)\.?\b", text or "", maxsplit=1, flags=re.I)[0]
    return artist_name_comparison_key(primary_credit)


def normalized_tag_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(k).lower())


def tag_lookup(tags: Dict[str, str], *names: str) -> str:
    indexed = {normalized_tag_key(k): str(v) for k, v in tags.items()}
    for name in names:
        v = indexed.get(normalized_tag_key(name))
        if v:
            return v
    return ""


def explicit_state(tags: Dict[str, str], *texts: str) -> str:
    # iTunes parental advisory: 0 = no information, 1 = explicit,
    # 2 = clean. 0 must NEVER be inferred to mean a Clean version.
    advisory = tag_lookup(tags, "itunesadvisory", "rtng", "advisory")
    if advisory:
        av = advisory.strip().lower()
        if av in {"1", "explicit", "yes", "true"}:
            return "explicit"
        if av in {"2", "clean"}:
            return "clean"
        # 0/no/false represent absence of advisory evidence. Other
        # independently affirmative tags/title descriptors may still apply.
    ex = tag_lookup(tags, "explicit")
    if ex:
        ev = ex.strip().lower()
        if ev in {"1", "yes", "true", "explicit"}:
            return "explicit"
        if ev == "clean":
            return "clean"
        # EXPLICIT=0/false merely denies an Explicit flag; it does not
        # prove that this is an intentionally edited Clean recording.
    joined = " ".join(texts).lower()
    if re.search(r"(?:\(|\[|\b)explicit(?:\)|\]|\b)", joined):
        return "explicit"
    if re.search(r"(?:\(|\[|\b)clean(?:\)|\]|\b)", joined):
        return "clean"
    return "unknown"


def release_title_from_folder(name: str) -> str:
    s = re.sub(r"^\d{4}(?:-\d{2}-\d{2})?\s*-\s*", "", name).strip()
    s = re.sub(r"\s*\[[^\]]+\]\s*$", "", s).strip()
    return s


def album_family(title: str) -> str:
    s = ascii_punctuation(title)
    changed = True
    while changed:
        old = s
        for pat in EDITION_PATTERNS:
            s = re.sub(pat, "", s, flags=re.I).strip()
        changed = old != s
    s = re.sub(r"\s+-\s+(?:deluxe|limited|special|expanded|remastered?)\s*$", "", s, flags=re.I)
    return normalize_title(s)


def _discography_artist_folder_name(rel: "Release") -> str:
    """Folder name of an explicitly named source root, not a guess from popular tracks."""
    root = Path(rel.scan_root) if rel.scan_root else None
    if not root:
        return ""
    generic = {"deemix", "music", "downloads", "download", "flac", "alac", "mp3", "lossless"}
    name = root.name
    if normalize_title(name) in generic:
        name = root.parent.name
    else:
        name = re.sub(r"(?i)(?:[ _-]+(?:deemix|music|downloads|flac|alac|mp3|lossless))+$", "", name).strip()
    return name if name and normalize_title(name) not in generic else ""


def _discography_artist_from_release(rel: "Release") -> str:
    """Comparison key of the discography artist folder."""
    return normalize_artist(_discography_artist_folder_name(rel))


def _main_artist_remix(track: "Track", artist: str) -> bool:
    if not artist or not track.is_remix:
        return False
    for text in (track.display_title, strip_track_number(track.path.stem)):
        for part in _descriptor_parts(text):
            if _remix_credit_key_from_explicit_descriptor(part) == artist:
                return True
    return False


_ARTIST_IDENTITY_ALIAS_SETS = (
    frozenset({"kanyewest", "ye"}),
)


def _artist_identity_aliases(artist: str) -> Set[str]:
    """Known name identities; joint album credits are not alias declarations."""
    for names in _ARTIST_IDENTITY_ALIAS_SETS:
        if artist in names:
            return set(names)
    return {artist}


def _classification_credit_members(value: str) -> Set[str]:
    """Treat explicit 'vs.' co-billing as separate participating artists."""
    source = re.sub(r"\s+(?:vs\.?|versus)\s+", ";", ascii_punctuation(value), flags=re.I)
    return _artist_signature(source)


def _other_artist_majority(artists: Optional[Sequence[str]], artist: str,
                          album_artist: str = "") -> bool:
    if not artists or not artist or len(artists) < 3:
        return False
    # An unrelated artist's Single/EP/Album within the requested artist's
    # discography is not thereby a Various Artists compilation. Require a
    # collection of independent primary performers, not just an absent root
    # artist. In particular, one Slum Village/Drake/Stromae track and seven
    # consistently credited KIDS SEE GHOSTS tracks are not VA releases.
    primary_groups: List[Set[str]] = []
    for value in artists:
        primary_credit = re.split(
            r"\bfeat(?:uring)?\.?\b|\bft\.?\b",
            ascii_punctuation(str(value or "")), maxsplit=1, flags=re.I,
        )[0].split(";", 1)[0]
        members = _classification_credit_members(primary_credit)
        if members:
            primary_groups.append(members)
    if len({frozenset(members) for members in primary_groups}) < 3:
        return False
    performer_counts = Counter(member for members in primary_groups for member in members)
    if performer_counts and max(performer_counts.values()) * 2 > len(primary_groups):
        return False
    # Album credit corroborates a jointly billed act/alias only when that
    # SAME credited identity actually appears in the track's primary credit.
    # A misleading ALBUMARTIST alone cannot rescue unrelated performers.
    credited = _artist_signature(album_artist) | {
        normalize_artist(part) for part in re.split(r";|,|&|\band\b", album_artist, flags=re.I)
        if part.strip()
    }
    identities = _artist_identity_aliases(artist)
    joint_credit = bool(identities & credited) and len(credited) > 1
    other = 0
    for value in artists:
        source = re.split(r"\bfeat(?:uring)?\.?\b|\bft\.?\b",
                          ascii_punctuation(str(value or "")), maxsplit=1, flags=re.I)[0]
        primary = normalize_artist(source.split(";", 1)[0])
        # & / and / comma are explicit co-billing. Semicolon-separated
        # secondary tags need corroborating joint release credit instead.
        co_primary = _classification_credit_members(source.split(";", 1)[0])
        belongs = bool(identities & co_primary) or (
            joint_credit and primary in credited
        )
        featured = _featured_artists_from_text(str(value or ""))
        if featured & identities and not identities & co_primary:
            belongs = False
        if primary and primary not in {"variousartists", "va"} and not belongs:
            other += 1
    return other * 2 > len(artists)


def _single_artist_collection(artists: Optional[Sequence[str]]) -> bool:
    if not artists or len(artists) < 3:
        return False
    keys = []
    for value in artists:
        source = re.split(r";|,|&|\band\b|\bx\b|\bfeat(?:uring)?\.?\b|\bft\.?\b",
                          ascii_punctuation(str(value or "")), maxsplit=1, flags=re.I)[0]
        key = normalize_artist(source)
        if key: keys.append(key)
    return len(keys) == len(artists) and len(set(keys)) == 1


def _release_warning(rel: "Release") -> str:
    warnings: List[str] = []
    if rel.type_source == "majority-other-artist":
        artist = _discography_artist_folder_name(rel)
        warnings.append("More than half the tracks credit other artists than " +
                        (artist or "the discography artist") + ". Review as Compilation.")
    if rel.unreadable_cue_paths:
        names = ", ".join(p.name for p in rel.unreadable_cue_paths)
        warnings.append(f"Unreadable CUE sheet ({names}): its audio image counts as one track.")
    return " ".join(warnings)


def _has_various_primary_performers(track_artists: Optional[Sequence[str]]) -> bool:
    """Strong multi-performer evidence independent of a misleading ALBUMARTIST.

    Use complete physical tracklists, BEFORE remix/live exclusions: otherwise
    an anthology can look like an artist album when excluded remixes dominate.
    This is a conservative compilation heuristic, not an acoustic identity rule.
    """
    if not track_artists or len(track_artists) < 8:
        return False
    signatures = [
        _classification_credit_members(str(value or ""))
        for value in track_artists
    ]
    known = [members for members in signatures if members]
    if len(known) < 8 or len(known) * 5 < len(signatures) * 4:
        return False
    frequency: Counter = Counter()
    for members in known:
        frequency.update(members)
    if not frequency:
        return False
    # Six distinct participating performers and six independently credited
    # track-artist combinations eliminate normal albums with two guest singers.
    # No performer may be credited on more than half the known tracklist;
    # solo and featured collaborations by the same primary artist stay albums.
    return (
        len(frequency) >= 6
        and len({frozenset(members) for members in known}) >= 6
        and max(frequency.values()) * 2 <= len(known)
    )


def infer_release_type(
    title: str,
    folder_name: str,
    track_count: int,
    tags: Dict[str, str],
    total_duration_seconds: float = 0.0,
    track_artists: Optional[Sequence[str]] = None,
    discography_artist: str = "",
) -> Tuple[str, str]:
    raw = tag_lookup(
        tags,
        "releasetype",
        "musicbrainzalbumtype",
        "albumtype",
        "primaryreleasetype",
    ).strip().lower()
    secondary = tag_lookup(tags, "secondaryreleasetype").strip().lower()
    compilation_tag = tag_lookup(tags, "compilation", "itunescompilation").strip().lower()
    album_artist = normalize_space(tag_lookup(tags, "albumartist", "album artist"))
    name_text = normalize_title(f"{title} {folder_name}")
    explicit_ep_name = bool(re.search(r"\bep\b", name_text, re.I))
    explicit_ep_tag = bool(re.search(r"\bep\b", raw, re.I))
    explicit_compilation_title = bool(
        re.search(r"\b(?:compilation|greatest hits|best of|anthology|collection)\b", name_text, re.I)
        or (track_count >= 25 and re.search(r"\btrilogy\b", name_text, re.I))
        or (track_count >= 12 and re.search(r"\bthe highlights\b", name_text, re.I))
    )
    diverse_artists = _has_various_primary_performers(track_artists)
    outside_majority = _other_artist_majority(track_artists, discography_artist, album_artist)
    same_artist_collection = _single_artist_collection(track_artists) and bool(
        re.search(r"\b(?:greatest hits|best of|anthology|collection|the highlights|trilogy)\b",
                  name_text, re.I)
        or "compilation" in raw
        or "compilation" in secondary
        or compilation_tag in {"1", "yes", "true", "compilation"}
    )

    # All tracks participate, including remix/live exclusions. The 22-track
    # Disciple 02 anthology has multiple independent acts even when its first
    # file incorrectly supplies the album/albumartist tag of one performer.
    if outside_majority:
        return "compilation", "majority-other-artist"
    if diverse_artists:
        return "compilation", "track-artists"
    if same_artist_collection:
        return "anthology", "track-artists"
    if explicit_compilation_title:
        return "compilation", "name"

    # Texx Mars EP is TWO songs credited to Datsik. An inherited iTunes
    # COMPILATION=1 or other compilation metadata must not turn this explicitly
    # titled EP into a VA anthology; same applies to explicitly tagged EPs.
    if explicit_ep_name or explicit_ep_tag:
        return "ep", "name" if explicit_ep_name else "tag"

    # For releases without contradictory strong EP evidence, honor explicitly
    # signalled VA/compilation metadata even when there are too few tracks for
    # the independent multi-performer heuristic.
    if (
        "compilation" in raw
        or "compilation" in secondary
        or compilation_tag in {"1", "yes", "true", "compilation"}
        or normalize_title(album_artist) in {"various artists", "various", "va"}
    ):
        return "compilation", "tag"

    if raw:
        if "album" in raw:
            return "album", "tag"
        if "single" in raw:
            return "single", "tag"

    x = f"{title} {folder_name}".lower()
    if re.search(r"\b(?:single)\b", x):
        return "single", "name"
    if re.search(r"remix(?:es)?|\brmx\b", x):
        # A Remix descriptor is not itself an EP. A single-track remix is
        # still a Single; retain EP fallback for multi-track remix packages.
        return ("single" if track_count == 1 else "ep"), "name"

    # Track count alone is insufficient: the 1995 BT album "今 Ima" has five
    # tracks but approximately 76.5 minutes of music.
    duration = max(0.0, float(total_duration_seconds or 0.0))
    if track_count >= 7 or duration >= 30.0 * 60.0:
        return "album", "heuristic"
    if track_count <= 2:
        return "single", "heuristic"
    return "ep", "heuristic"


def _release_representative_type_tags(tracks: Sequence["Track"]) -> Dict[str, str]:
    """Prefer a release-wide majority of explicit primary-type tags."""
    if not tracks:
        return {}
    votes = []
    for track in tracks:
        raw = tag_lookup(track.tags, "releasetype", "musicbrainzalbumtype",
                         "albumtype", "primaryreleasetype").lower()
        primary = next((kind for kind in ("ep", "album", "single", "compilation")
                        if re.search(rf"\b{kind}\b", raw)), "")
        if primary:
            votes.append((primary, track.tags))
    if votes:
        winner, count = Counter(kind for kind, _ in votes).most_common(1)[0]
        if count * 2 > len(tracks):
            return next(tags for kind, tags in votes if kind == winner)
    return tracks[0].tags


def locate_executable(name: str) -> Optional[str]:
    p = shutil.which(name)
    if p:
        return p
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Microsoft" / "WinGet" / "Links" / (name + ".exe")
        if candidate.exists():
            return str(candidate)
    return None


def _find_ffmpeg_pair_under(root: Path) -> Optional[Tuple[str, str]]:
    """Find ffmpeg.exe + ffprobe.exe under one dependency/package tree."""
    if not root.exists():
        return None

    direct_candidates = [
        root,
        root / "bin",
    ]
    for folder in direct_candidates:
        ffmpeg = folder / "ffmpeg.exe"
        ffprobe = folder / "ffprobe.exe"
        if ffmpeg.is_file() and ffprobe.is_file():
            return str(ffmpeg), str(ffprobe)

    try:
        for ffmpeg in root.rglob("ffmpeg.exe"):
            ffprobe = ffmpeg.with_name("ffprobe.exe")
            if ffprobe.is_file():
                return str(ffmpeg), str(ffprobe)
    except OSError:
        pass
    return None


def _locate_ffmpeg_pair() -> Optional[Tuple[str, str]]:
    """Locate FFmpeg in the bundled folder, app data, or system installs."""
    bundled = _find_ffmpeg_pair_under(_bundled_path("ffmpeg"))
    if bundled:
        return bundled

    ffmpeg = locate_executable("ffmpeg")
    ffprobe = locate_executable("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    # App-owned dependency is deterministic and survives PATH/WinGet-link issues.
    local_pair = _find_ffmpeg_pair_under(_dependencies_dir() / "FFmpeg")
    if local_pair:
        return local_pair

    # WinGet packages do not always create Links visible to the already-running
    # process. Search the package store directly before declaring installation
    # failure.
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        packages = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if packages.exists():
            try:
                for package_dir in packages.iterdir():
                    name = package_dir.name.casefold()
                    if "ffmpeg" not in name:
                        continue
                    pair = _find_ffmpeg_pair_under(package_dir)
                    if pair:
                        return pair
            except OSError:
                pass

    # A few common machine-wide/manual locations are cheap to check.
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if not base:
            continue
        for folder_name in ("FFmpeg", "ffmpeg"):
            pair = _find_ffmpeg_pair_under(Path(base) / folder_name)
            if pair:
                return pair

    return None


def _install_ffmpeg_app_local() -> Tuple[str, str]:
    """Install FFmpeg inside the analyzer's isolated dependencies directory."""
    if os.name != "nt":
        raise RuntimeError("Automatic app-local FFmpeg installation is supported on Windows only.")

    target = _dependencies_dir() / "FFmpeg"
    target.mkdir(parents=True, exist_ok=True)
    _temp_dir().mkdir(parents=True, exist_ok=True)
    archive_path = _temp_dir() / "ffmpeg-release-essentials.zip"

    # Clean only our own incomplete dependency directory before extracting a
    # fresh copy. Never touch a system/WinGet installation.
    try:
        for child in list(target.iterdir()):
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
    except OSError:
        pass

    try:
        _download_verified_archive(FFMPEG_DIRECT_URL, archive_path, FFMPEG_ZIP_SHA256)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(target)
    except Exception as exc:
        raise RuntimeError(f"Direct FFmpeg download/extraction failed: {exc}") from exc
    finally:
        try:
            archive_path.unlink(missing_ok=True)
        except Exception:
            pass

    pair = _find_ffmpeg_pair_under(target)
    if not pair:
        raise RuntimeError(
            "FFmpeg archive was downloaded, but ffmpeg.exe/ffprobe.exe were not found after extraction."
        )
    return pair

# Job Object: Windows terminates assigned subprocesses automatically when
# the parent exits, even if the GUI is killed. No unrelated fpcalc is touched.
_CHILD_LOCK = threading.RLock()
_CHILD_SHUTDOWN = threading.Event()
_CHILD_JOB = None
_CHILD_PROCESSES: Set[subprocess.Popen] = set()
_CHILD_JOB_FALLBACK_REASON = ""


def _windows_job():
    global _CHILD_JOB
    if _CHILD_JOB is not None:
        return _CHILD_JOB
    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]
    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
    class Limits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Counters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Limits()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.get_last_error()
        k32.CloseHandle(job)
        raise ctypes.WinError(error)
    _CHILD_JOB = job
    return job


def _end_app_children() -> None:
    global _CHILD_JOB
    _CHILD_SHUTDOWN.set()
    with _CHILD_LOCK:
        # A restricted Windows parent Job may reject our own Job Object.
        # Track these children explicitly so normal MCC shutdown still
        # terminates their exact PIDs, without touching unrelated programs.
        for process in tuple(_CHILD_PROCESSES):
            try:
                if process.poll() is None:
                    process.kill()
            except OSError:
                pass
        _CHILD_PROCESSES.clear()
        if os.name == "nt" and _CHILD_JOB is not None:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            k32.CloseHandle.restype = wintypes.BOOL
            k32.CloseHandle(_CHILD_JOB)
            _CHILD_JOB = None


atexit.register(_end_app_children)


def run_hidden(args: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Track and clean up ffprobe/fpcalc/ffmpeg processes on application exit."""
    global _CHILD_JOB_FALLBACK_REASON
    timeout = kwargs.pop("timeout", None)
    check = kwargs.pop("check", False)
    input_data = kwargs.pop("input", None)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    breakaway_flag = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0) if os.name == "nt" else 0
    if os.name == "nt":
        # An inherited, compatible parent Job can block reassignment to MCC's
        # kill-on-close Job. Start a breakaway child, then put it in OUR Job.
        # Windows allows this flag without an enclosing Job (it is then inert).
        # If an enclosing Job prohibits reassignment, supervise the launched
        # child ourselves; never mistake a cleanup restriction for decoder
        # failure. The separate decoder preflight still checks real execution.
        flags |= breakaway_flag
    with _CHILD_LOCK:
        if _CHILD_SHUTDOWN.is_set():
            raise RuntimeError("Application closing; external analysis cancelled.")
        try:
            process = subprocess.Popen(args, creationflags=flags, **kwargs)
        except OSError as exc:
            code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
            if breakaway_flag and (flags & breakaway_flag) and code in {5, 87}:
                # Certain parent Jobs disallow CREATE_BREAKAWAY_FROM_JOB.
                # Retry once within that Job, then supervise the child via
                # MCC's process registry if our own Job also rejects it.
                try:
                    process = subprocess.Popen(
                        args, creationflags=flags & ~breakaway_flag, **kwargs
                    )
                except OSError as retry_exc:
                    exc = retry_exc
                else:
                    _CHILD_JOB_FALLBACK_REASON = (
                        "Windows rejected child breakaway; audio tools started "
                        "inside the inherited Job with MCC-managed cleanup."
                    )
                    exc = None
            if exc is not None:
                raise RuntimeError(
                    f"Cannot start external audio tool {Path(str(args[0])).name}: {exc}. "
                    "Check the executable's permissions and Windows Job restrictions."
                ) from exc
        _CHILD_PROCESSES.add(process)
        if os.name == "nt":
            try:
                k32 = ctypes.WinDLL("kernel32", use_last_error=True)
                k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
                k32.AssignProcessToJobObject.restype = wintypes.BOOL
                if not k32.AssignProcessToJobObject(_windows_job(), int(process._handle)):
                    if process.poll() is None:
                        error = ctypes.get_last_error()
                        _CHILD_JOB_FALLBACK_REASON = (
                            f"Job Object assignment blocked for {Path(str(args[0])).name} "
                            f"(WinError {error}); MCC will track and stop its own child "
                            "processes on normal shutdown."
                        )
            except Exception as exc:
                _CHILD_JOB_FALLBACK_REASON = (
                    f"Windows Job Object unavailable ({exc}); MCC will track "
                    "and stop its own child processes on normal shutdown."
                )
    try:
        out, err = process.communicate(input=input_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        with _CHILD_LOCK:
            _CHILD_PROCESSES.discard(process)
    result = subprocess.CompletedProcess(args, process.returncode, out, err)
    if check:
        result.check_returncode()
    return result


def bootstrap_winget() -> Optional[str]:
    winget = locate_executable("winget")
    if winget:
        return winget
    if os.name != "nt":
        return None
    ps = locate_executable("powershell") or locate_executable("pwsh")
    if not ps:
        return None
    script = (
        "$ProgressPreference='SilentlyContinue';"
        "Install-PackageProvider -Name NuGet -Force | Out-Null;"
        "Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery | Out-Null;"
        "Import-Module Microsoft.WinGet.Client;"
        "Repair-WinGetPackageManager -Force -Latest"
    )
    try:
        run_hidden([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], check=False)
    except Exception:
        return None
    return locate_executable("winget")


def _dependency_update_cache_path() -> Path:
    return _cache_dir() / "dependency_updates.json"


def _load_dependency_update_cache() -> Dict[str, float]:
    _migrate_legacy_app_data()
    path = _dependency_update_cache_path()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _mark_dependency_checked(package_id: str) -> None:
    data = _load_dependency_update_cache()
    data[package_id] = time.time()
    try:
        _atomic_write_json(_dependency_update_cache_path(), data)
    except Exception:
        pass


def _winget_install_or_update(package_id: str, installed: bool) -> None:
    """Install missing dependencies or periodically check installed ones for updates."""
    winget = bootstrap_winget()
    if not winget:
        return

    if installed:
        last = _load_dependency_update_cache().get(package_id, 0.0)
        if time.time() - last < 7 * 24 * 60 * 60:
            return
        action = "upgrade"
    else:
        action = "install"

    args = [
        winget,
        action,
        "--id", package_id,
        "-e",
        "--source", "winget",
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--silent",
    ]
    try:
        run_hidden(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
    finally:
        _mark_dependency_checked(package_id)


def ensure_ffmpeg() -> Tuple[str, str]:
    """Ensure FFmpeg/FFprobe are usable without inflating the lightweight EXE."""
    pair = _locate_ffmpeg_pair()

    # WinGet-first dependency policy; the large FFmpeg binaries are not bundled.
    bootstrap_winget()
    installed = pair is not None

    winget_error = ""
    try:
        _winget_install_or_update(FFMPEG_PACKAGE_ID, installed=installed)
    except Exception as exc:
        winget_error = str(exc)

    # Re-scan PATH, WinGet package storage and app-local dependencies. This is
    # important because a successful WinGet install may not update the current
    # process environment or create a WinGet Links shim.
    pair = _locate_ffmpeg_pair()
    if pair:
        return pair

    # WinGet is preferred, but it is not allowed to be a single point of
    # failure. Fall back to the official Gyan Windows essentials build and keep
    # it isolated inside this program's own dependencies directory.
    try:
        return _install_ffmpeg_app_local()
    except Exception as direct_exc:
        details = []
        if winget_error:
            details.append(f"WinGet: {winget_error}")
        details.append(str(direct_exc))
        raise RuntimeError(
            "FFmpeg/FFprobe are required and automatic setup failed. "
            + " | ".join(details)
        ) from direct_exc


def ensure_heybrochecklog():
    """Return the pinned log scorer, stored under this program's dependencies folder."""
    _migrate_legacy_app_data()
    deps = _dependencies_dir() / f"heybrochecklog-{HEYBROCHECKLOG_VERSION}"

    legacy = (
        Path(os.environ.get("LOCALAPPDATA") or Path.home())
        / "Karpuzikov"
        / PROGRAM_DATA_DIR_NAME
        / "deps"
        / f"heybrochecklog-{HEYBROCHECKLOG_VERSION}"
    )
    if not deps.exists() and legacy.is_dir():
        try:
            shutil.copytree(legacy, deps, dirs_exist_ok=True)
        except Exception:
            pass

    deps_text = str(deps)
    if deps.is_dir() and deps_text not in sys.path:
        sys.path.insert(0, deps_text)

    try:
        module = importlib.import_module("heybrochecklog")
        return module.score_log
    except Exception:
        pass  # Not installed yet or broken: fall through to the installer below.

    # Source/development mode keeps the dependency isolated from normal Python.
    bootstrap_winget()
    try:
        pip_check = run_hidden(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
        if pip_check.returncode != 0:
            run_hidden(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                check=False,
            )

        deps.mkdir(parents=True, exist_ok=True)
        cp = run_hidden(
            [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "--quiet",
                "--upgrade",
                "--target", str(deps),
                HEYBROCHECKLOG_SOURCE,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or "pip install failed")

        if deps_text not in sys.path:
            sys.path.insert(0, deps_text)
        importlib.invalidate_caches()
        for module_name in [name for name in list(sys.modules) if name == "heybrochecklog" or name.startswith("heybrochecklog.")]:
            sys.modules.pop(module_name, None)
        module = importlib.import_module("heybrochecklog")
        return module.score_log
    except Exception as exc:
        raise RuntimeError(
            "hey-bro-check-log is required for CD rip log quality scoring and "
            f"could not be installed automatically: {exc}"
        ) from exc


@dataclass
class Track:
    release_id: int
    path: Path
    index: int
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    fingerprint: Tuple[int, ...] = field(default_factory=tuple)
    fingerprint_duration: float = 0.0
    fingerprint_repaired: bool = False
    integrity_checked: bool = False
    integrity_error: str = ""
    explicit: str = "unknown"
    group_id: int = -1
    # Coverage substitution is deliberately separate from actual acoustic identity:
    # version differences remain visible by the original group_id.
    coverage_group_id: int = -1
    is_remix: bool = False
    is_live: bool = False
    remix_feature_exception: bool = False
    exclude_from_coverage: bool = False
    excluded_by_pattern: str = ""
    personal_keep_rule: str = ""
    base_excluded_from_coverage: bool = False
    manual_skip_rule: str = ""
    explicit_category_exclusion: bool = False
    acoustic_policy_reconciled: bool = False
    comparison_index: int = -1
    codec_name: str = ""
    sample_rate: int = 0
    bit_depth: int = 0
    channels: int = 0
    bit_rate: int = 0
    file_size: int = 0
    dynamic_lufs: Optional[float] = None
    dynamic_lra: Optional[float] = None
    dynamic_true_peak_dbfs: Optional[float] = None
    dynamic_rms_dbfs: Optional[float] = None
    dynamic_crest_db: Optional[float] = None
    dynamic_score: Optional[float] = None
    virtual_from_cue: bool = False
    cue_path: Optional[Path] = None
    cue_track_number: int = 0
    cue_start_seconds: float = 0.0
    cue_end_seconds: float = 0.0
    cue_title: str = ""
    cue_performer: str = ""
    cue_album: str = ""
    # Per-analysis evidence only; raw duration and source files remain intact.
    identity_duration_seconds: float = 0.0

    @property
    def display_title(self) -> str:
        return self.title or strip_track_number(self.path.stem)


@dataclass
class Release:
    rid: int
    root_kind: str
    path: Path
    title: str
    paths: List[Path] = field(default_factory=list)
    scan_root: Optional[Path] = None
    tracks: List[Track] = field(default_factory=list)
    release_type: str = "unknown"
    type_source: str = ""
    family: str = ""
    source_quality: int = 0
    source_medium: str = "Unknown"
    explicit: str = "unknown"
    has_cue: bool = False
    has_rip_log: bool = False
    has_audiochecker: bool = False
    rip_log_paths: List[Path] = field(default_factory=list)
    rip_log_scores: List[int] = field(default_factory=list)
    rip_log_rippers: List[str] = field(default_factory=list)
    rip_log_flagged: int = 0
    rip_log_unrecognized: List[str] = field(default_factory=list)
    has_cd_image: bool = False
    cd_image_track_count: int = 0
    cue_paths: List[Path] = field(default_factory=list)
    unreadable_cue_paths: List[Path] = field(default_factory=list)
    validation_issues: List[str] = field(default_factory=list)

    @property
    def source_paths(self) -> List[Path]:
        return list(self.paths) if self.paths else [self.path]

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def included_track_count(self) -> int:
        """Tracks included by the active checkboxes/pattern choices."""
        return sum(1 for t in self.tracks if not t.exclude_from_coverage)

    @property
    def counted_track_count(self) -> int:
        """Tracks that actually participate in recording-group coverage."""
        return sum(
            1
            for t in self.tracks
            if not t.exclude_from_coverage and t.group_id >= 0
        )

    @property
    def ignored_track_count(self) -> int:
        """Tracks skipped by the active checkboxes/pattern choices."""
        return sum(1 for t in self.tracks if t.exclude_from_coverage)

    @property
    def groups(self) -> Set[int]:
        return {
            _track_coverage_gid(t) for t in self.tracks
            if t.group_id >= 0 and not t.exclude_from_coverage
        }

    @property
    def excluded_only(self) -> bool:
        return bool(self.tracks) and all(t.exclude_from_coverage for t in self.tracks)

    @property
    def remix_only(self) -> bool:
        return bool(self.tracks) and all(t.is_remix for t in self.tracks)


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))
        self.r = [0] * n

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.r[ra] < self.r[rb]:
            ra, rb = rb, ra
        self.p[rb] = ra
        if self.r[ra] == self.r[rb]:
            self.r[ra] += 1


def probe_track(ffprobe: str, track: Track) -> None:
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries",
        "stream=codec_name,codec_type,sample_rate,bits_per_sample,bits_per_raw_sample,channels,bit_rate:"
        "format=duration,bit_rate:format_tags",
        "-of", "json", str(track.path)
    ]
    cp = run_hidden(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", check=False)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "ffprobe failed")
    data = json.loads(cp.stdout or "{}")
    fmt = data.get("format") or {}
    full_duration = float(fmt.get("duration") or 0.0)
    track.tags = {
        str(k): clean_metadata_text(str(v))
        for k, v in (fmt.get("tags") or {}).items()
    }

    if track.virtual_from_cue:
        start = max(0.0, float(track.cue_start_seconds))
        end = float(track.cue_end_seconds)
        track.duration = (end - start) if end > start else max(0.0, full_duration - start)
        track.title = clean_metadata_text(track.cue_title or f"Track {track.cue_track_number:02d}")
        track.artist = clean_metadata_text(track.cue_performer or tag_lookup(track.tags, "artist"))
        track.album = clean_metadata_text(track.cue_album or tag_lookup(track.tags, "album"))
        if track.cue_track_number:
            track.tags["TRACKNUMBER"] = str(track.cue_track_number)
    else:
        track.duration = full_duration
        track.title = clean_metadata_text(
            tag_lookup(track.tags, "title") or strip_track_number(track.path.stem)
        )
        track.artist = clean_metadata_text(tag_lookup(track.tags, "artist"))
        track.album = clean_metadata_text(tag_lookup(track.tags, "album"))

    track.explicit = explicit_state(track.tags, track.title, track.path.name, track.album)

    audio_stream = next(
        (stream for stream in (data.get("streams") or []) if str(stream.get("codec_type") or "").lower() == "audio"),
        {},
    )
    track.codec_name = str(audio_stream.get("codec_name") or "").lower()
    try:
        track.sample_rate = int(audio_stream.get("sample_rate") or 0)
    except (TypeError, ValueError):
        track.sample_rate = 0
    try:
        track.bit_depth = int(audio_stream.get("bits_per_raw_sample") or audio_stream.get("bits_per_sample") or 0)
    except (TypeError, ValueError):
        track.bit_depth = 0
    try:
        track.channels = int(audio_stream.get("channels") or 0)
    except (TypeError, ValueError):
        track.channels = 0
    try:
        track.bit_rate = int(audio_stream.get("bit_rate") or fmt.get("bit_rate") or 0)
    except (TypeError, ValueError):
        track.bit_rate = 0
    try:
        track.file_size = track.path.stat().st_size
    except OSError:
        track.file_size = 0


def _tag_positive_number(value: str) -> Optional[int]:
    """Read positive index/total from 6, 06/06 or 6 of 6; reject nonsense."""
    match = re.match(r"^\s*([0-9]{1,5})(?:\s*(?:/|of)\s*[0-9]{1,5})?\s*$", str(value or ""), re.I)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 9999 else None


def _track_disc_identifier(track: Track) -> int:
    if track.virtual_from_cue and track.cue_track_number:
        raw = tag_lookup(track.tags, "discnumber", "disc")
    else:
        raw = tag_lookup(track.tags, "discnumber", "disc")
    number = _tag_positive_number(raw)
    if number:
        return number
    for folder in list(track.path.parents)[:3]:
        disc = re.match(r"^(?:cd|disc|disk)\s*[-_. ]*(\d+)\s*$", folder.name, re.I)
        if disc:
            return int(disc.group(1))
    return 1


_FILENAME_DISC_AND_TRACK = re.compile(
    r"^(?:(?:cd|disc|disk)\s*)?(\d{1,2}|dvd|bd|bonus)[-_.](\d{1,3})(?=[\s._-])", re.I)
BONUS_DISC_NUMBER_OFFSET = 100


def _filename_disc_and_track(track: Track) -> Optional[Tuple[int, int]]:
    """Disc and track from names like 2-03. Title.flac or DVD-12. Title.flac."""
    match = _FILENAME_DISC_AND_TRACK.match(track.path.stem)
    if not match or track.virtual_from_cue:
        return None
    disc = match.group(1)
    return (int(disc) if disc.isdigit() else BONUS_DISC_NUMBER_OFFSET, int(match.group(2)))


def _disc_label(disc: int, disc_count: int) -> str:
    if disc_count <= 1:
        return ""
    return "DVD: " if disc >= BONUS_DISC_NUMBER_OFFSET else f"Disc {disc}: "


def validate_release_track_totals(releases: List[Release]) -> int:
    """Audit declared TRACKTOTAL/TOTALTRACKS against disc or album scope.

    Some music distributors repeat the entire release track count on every
    file, even with independent 1..N numbering inside CD1/CD2. Other sources
    describe the track count separately for each disc. Never demand the
    release-wide count on *each* disc. A declared total is used as evidence,
    not as an excuse to ignore gaps or contradictory metadata.
    """
    issue_count = 0
    for rel in releases:
        rel.validation_issues.clear()
        # One folder holding several discs (1-01..., 2-01..., DVD-01...): when every
        # file name carries its disc and track, the names are the layout, even if
        # tags give every file disc 1 or number the tracks differently.
        filename_slots = {id(track): _filename_disc_and_track(track) for track in rel.tracks}
        use_filename_slots = bool(rel.tracks) and all(filename_slots.values()) and len(
            {slot[0] for slot in filename_slots.values()}) > 1
        discs: Dict[int, List[Track]] = defaultdict(list)
        for track in rel.tracks:
            disc_key = filename_slots[id(track)][0] if use_filename_slots else _track_disc_identifier(track)
            discs[disc_key].append(track)

        # Keep explicit totals and observed track numbers separate, preserving
        # the distinction between a declared TOTALTRACKS and a positional tag.
        disc_data: Dict[int, Dict[str, object]] = {}
        for disc, items in sorted(discs.items()):
            totals: Set[int] = set()
            numbers: List[int] = []
            total_conflict = False
            for track in items:
                raw_totals = [
                    tag_lookup(track.tags, "TRACKTOTAL"),
                    tag_lookup(track.tags, "TOTALTRACKS"),
                ]
                parsed = [
                    value for value in (_tag_positive_number(raw) for raw in raw_totals if raw)
                    if value is not None
                ]
                if len(set(parsed)) > 1:
                    total_conflict = True
                totals.update(parsed)
                raw_number = tag_lookup(track.tags, "TRACKNUMBER", "TRACK")
                number = _tag_positive_number(raw_number)
                if use_filename_slots:
                    number = filename_slots[id(track)][1]
                elif track.virtual_from_cue and track.cue_track_number:
                    number = track.cue_track_number
                elif number is None:
                    number = _track_number_for_routing(track) or None
                if number is not None:
                    numbers.append(number)

                if not parsed:
                    # FLAC/Vorbis often encodes 21/28 as TRACKNUMBER without
                    # any separate TRACKTOTAL. Still a declared total.
                    suffix = re.search(r"^\\s*\\d+\\s*/\\s*(\\d+)\\s*$", raw_number or "")
                    if suffix:
                        expected = _tag_positive_number(suffix.group(1))
                        if expected:
                            totals.add(expected)

            disc_data[disc] = {
                "items": items,
                "totals": totals,
                "numbers": numbers,
                "conflict": total_conflict,
            }

        declared = set().union(*(row["totals"] for row in disc_data.values())) if disc_data else set()
        album_scope_total: Optional[int] = None
        if len(discs) > 1 and len(declared) == 1:
            expected = next(iter(declared))
            # E.g. Director's Cut: CD1 1..21, CD2 1..7, both carrying
            # TRACKTOTAL=28. The one declared value exceeds every disc's
            # physical/index count, so it cannot mean 28 per disc without
            # falsely treating the current intact release as two incomplete CDs.
            max_disc_count = max(len(row["items"]) for row in disc_data.values())
            max_disc_index = max(
                (max(row["numbers"], default=0) for row in disc_data.values()),
                default=0,
            )
            numbers_all = [number for row in disc_data.values() for number in row["numbers"]]
            # Some albums number tracks continuously across disc boundaries.
            continuous_numbering = (
                len(numbers_all) == sum(len(row["items"]) for row in disc_data.values())
                and len(set(numbers_all)) == len(numbers_all)
                and set(numbers_all) == set(range(1, expected + 1))
            )
            if (
                expected > max_disc_count and expected > max_disc_index
            ) or continuous_numbering:
                album_scope_total = expected

        def validate_numbering(disc: int, numbers: List[int], items: List[Track],
                               reset_at_one: bool) -> None:
            prefix = _disc_label(disc, len(discs))
            if len(numbers) != len(items):
                rel.validation_issues.append(
                    f"{prefix}{len(items) - len(numbers)} track(s) have no usable TRACKNUMBER"
                )
            duplicates = sorted(index for index, frequency in Counter(numbers).items() if frequency > 1)
            if duplicates:
                rel.validation_issues.append(f"{prefix}duplicate track number(s): {duplicates}")
            # Album-wide numbering can continue from CD1 to CD2, rather than
            # restarting at 1. For that mode the full-release check is below.
            if reset_at_one and numbers:
                upper = max(numbers)
                internal_gaps = sorted(set(range(1, upper + 1)) - set(numbers))
                if internal_gaps:
                    preview = ", ".join(map(str, internal_gaps[:12]))
                    rel.validation_issues.append(
                        f"{prefix}missing track number(s) within this disc: {preview}"
                        + ("..." if len(internal_gaps) > 12 else "")
                    )

        if album_scope_total is not None:
            expected = album_scope_total
            all_numbers = [n for row in disc_data.values() for n in row["numbers"]]
            count = sum(len(row["items"]) for row in disc_data.values())
            numbering_continuous = (
                len(set(all_numbers)) == len(all_numbers)
                and all_numbers
                and all(
                    min(disc_data[d]["numbers"], default=0)
                    > max(disc_data[previous]["numbers"], default=0)
                    for previous, d in zip(sorted(discs)[:-1], sorted(discs)[1:])
                )
            )
            for disc, row in sorted(disc_data.items()):
                if row["conflict"] or len(row["totals"]) > 1:
                    rel.validation_issues.append(
                        f"{_disc_label(disc, len(discs))}conflicting TRACKTOTAL/TOTALTRACKS declarations: "
                        f"{sorted(row['totals'])}"
                    )
                validate_numbering(disc, row["numbers"], row["items"],
                                   reset_at_one=not numbering_continuous)

            if count != expected:
                rel.validation_issues.append(
                    f"Release-wide TRACKTOTAL/TOTALTRACKS={expected} across {len(discs)} "
                    f"discs, but found {count} physical track(s)"
                )
            if numbering_continuous:
                missing = sorted(set(range(1, expected + 1)) - set(all_numbers))
                excess = sorted(n for n in all_numbers if n > expected)
                if missing or excess:
                    rel.validation_issues.append(
                        f"Release-wide track numbering mismatch: "
                        f"missing {missing[:12]}, out of range {excess[:12]}"
                    )
        else:
            # Per-disc declarations: CD1 21/21, CD2 7/7; this must still
            # detect either disc's missing last track or internal gaps.
            for disc, row in sorted(disc_data.items()):
                items = row["items"]
                numbers = row["numbers"]
                totals = row["totals"]
                prefix = _disc_label(disc, len(discs))
                if row["conflict"] or len(totals) > 1:
                    rel.validation_issues.append(
                        f"{prefix}conflicting TRACKTOTAL/TOTALTRACKS declarations: {sorted(totals)}"
                    )
                if not totals:
                    continue  # UNKNOWN completeness is not a defect.
                expected = max(totals)
                validate_numbering(disc, numbers, items, reset_at_one=False)
                present = set(numbers)
                missing = sorted(set(range(1, expected + 1)) - present)
                if missing:
                    preview = ", ".join(str(i) for i in missing[:12])
                    rel.validation_issues.append(
                        f"{prefix}incomplete: "
                        f"{len(present & set(range(1, expected + 1)))}/{expected} "
                        f"tracks, missing number(s): {preview}"
                        + ("..." if len(missing) > 12 else "")
                    )
                excess = sorted(n for n in present if n > expected)
                if excess:
                    rel.validation_issues.append(
                        f"{prefix}track numbers exceed declared total {expected}: {excess}"
                    )

        issue_count += len(rel.validation_issues)
    return issue_count


def _verify_external_audio_tools(ffmpeg: str, ffprobe: str) -> None:
    """Fail before scanning if Windows cannot launch/supervise audio decoders."""
    for name, executable in (("FFmpeg", ffmpeg), ("FFprobe", ffprobe)):
        try:
            cp = run_hidden(
                [executable, "-version"], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, errors="replace",
                check=False, timeout=20,
            )
        except Exception as exc:
            raise RuntimeError(
                f"{name} cannot run under the current Windows process permissions. "
                f"Audio scan cancelled before reading media: {exc}"
            ) from exc
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or "").strip()[:350]
            raise RuntimeError(
                f"{name} preflight failed (exit {cp.returncode}). "
                f"Audio scan cancelled before reading media: {detail}"
            )


def _verify_audio_file(ffmpeg: str, path: Path) -> str:
    """Fully decode audio, including tails that metadata readers can miss."""
    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-v", "error",
        "-xerror", "-err_detect", "explode",
        "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-f", "null", "-",
    ]
    try:
        completed = run_hidden(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace", check=False,
        )
    except Exception as exc:
        return f"Full decode failed: {exc}"
    details = (completed.stderr or "").strip()
    if completed.returncode != 0 or details:
        return (details or f"FFmpeg exit code {completed.returncode}")[:450]
    return ""


def _short_integrity_reason(raw: str) -> str:
    """First FFmpeg message line without its [codec @ address] tags, for display."""
    for line in str(raw).splitlines():
        cleaned = re.sub(r"\[[^\]]*@[^\]]*\]", "", line).strip()
        if cleaned:
            return cleaned[:120]
    return "unreadable"


def verify_audio_integrity(
    ffmpeg: str,
    tracks: List[Track],
    io_workers: Optional[int],
    progress_cb,
) -> List[str]:
    """Verify every distinct physical file (including CUE images) exactly once."""
    by_file: Dict[str, List[Track]] = defaultdict(list)
    for track in tracks:
        track.integrity_checked = False
        track.integrity_error = ""
        by_file[os.path.normcase(str(track.path.resolve()))].append(track)
    paths = list(by_file)
    workers = min(len(paths) or 1, _probe_workers(io_workers))
    errors: List[str] = []
    label = f"Verifying audio file integrity ({workers} workers)..."
    progress_cb(label, 0, max(1, len(paths)))
    if paths:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_verify_audio_file, ffmpeg, Path(name)): name for name in paths}
            for completed, future in enumerate(as_completed(futures), 1):
                name = futures[future]
                try:
                    issue = future.result()
                except Exception as exc:
                    issue = str(exc)
                for track in by_file[name]:
                    track.integrity_checked = True
                    track.integrity_error = issue
                if issue:
                    errors.append(f"CORRUPT / unreadable audio: {name}: {issue}")
                progress_cb(label, completed, len(paths))
    if paths and len(errors) == len(paths):
        # No recording identity can be inferred if EVERY physical input fails.
        # Never proceed to an optimizer/map where missing fingerprints look like
        # genuine unique recordings. This also catches an executable that can
        # print -version but cannot decode media under Windows permissions.
        raise RuntimeError(
            f"All {len(paths)} audio files failed full decoding. "
            "The scan was stopped: no Release Map or Copy/Move plan is valid. "
            f"First error: {errors[0][:650]}"
        )
    return errors


def locate_fpcalc() -> Optional[str]:
    bundled = _bundled_path("chromaprint", "fpcalc.exe")
    if bundled.is_file():
        return str(bundled)

    _migrate_legacy_app_data()
    app_local = _dependencies_dir() / f"Chromaprint-{CHROMAPRINT_VERSION}" / "fpcalc.exe"
    if app_local.exists():
        return str(app_local)

    p = locate_executable("fpcalc")
    if p:
        return p

    candidates: List[Path] = []
    pf = os.environ.get("ProgramFiles")
    pf86 = os.environ.get("ProgramFiles(x86)")
    local = os.environ.get("LOCALAPPDATA")
    if pf:
        candidates.append(Path(pf) / "MusicBrainz Picard" / "fpcalc.exe")
    if pf86:
        candidates.append(Path(pf86) / "MusicBrainz Picard" / "fpcalc.exe")
    if local:
        candidates.extend([
            Path(local) / "Programs" / "MusicBrainz Picard" / "fpcalc.exe",
            Path(local) / "Karpuzikov" / "Discography Builder" / f"Chromaprint-{CHROMAPRINT_VERSION}" / "fpcalc.exe",
        ])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def ensure_fpcalc() -> str:
    bundled = _bundled_path("chromaprint", "fpcalc.exe")
    if bundled.is_file():
        return str(bundled)
    # Use an external app-local or system fpcalc (bootstrapped through WinGet).
    bootstrap_winget()
    _migrate_legacy_app_data()

    target = _dependencies_dir() / f"Chromaprint-{CHROMAPRINT_VERSION}"
    exe = target / "fpcalc.exe"
    if exe.exists():
        return str(exe)

    # Preserve earlier downloaded dependency without removing the old copy.
    legacy = (
        Path(os.environ.get("LOCALAPPDATA") or Path.home())
        / "Karpuzikov"
        / "Discography Builder"
        / f"Chromaprint-{CHROMAPRINT_VERSION}"
        / "fpcalc.exe"
    )
    if legacy.is_file():
        try:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, exe)
            return str(exe)
        except Exception:
            pass

    # A system/Picard copy can be used immediately, but downloads owned by this
    # program are always stored inside its own dependencies folder.
    existing = locate_fpcalc()
    if existing and Path(existing) != exe:
        return existing

    if os.name != "nt":
        raise RuntimeError("fpcalc/Chromaprint is required.")

    target.mkdir(parents=True, exist_ok=True)
    _temp_dir().mkdir(parents=True, exist_ok=True)
    zip_path = _temp_dir() / f"chromaprint-{CHROMAPRINT_VERSION}.zip"
    try:
        _download_verified_archive(CHROMAPRINT_URL, zip_path, CHROMAPRINT_ZIP_SHA256)
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(target)
        found = next(target.rglob("fpcalc.exe"), None)
        if not found:
            raise RuntimeError("fpcalc.exe was not found in the downloaded Chromaprint archive.")
        if found != exe:
            shutil.copy2(found, exe)
    finally:
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
    return str(exe)


def _chromaprint_fingerprint_incomplete(fp_length: int, duration: float) -> bool:
    """Catch physically truncated fingerprints without altering similarity policy.

    Chromaprint's standard fingerprint rate is ~11025 / 4096 frames/sec.
    Tolerance accounts for startup/silence/frame windows, and shorter inputs
    are left alone. This is a *quality gate*, not a duplicate-identity test.
    """
    duration = max(0.0, float(duration or 0.0))
    if duration < 30.0:
        return False
    minimum_expected = int(max(0.0, duration - 5.0) * (11025 / 4096) * 0.65)
    return int(fp_length) < max(20, minimum_expected)


def _read_chromaprint_json(fpcalc: str, source: Path, fallback_duration: float) -> Tuple[Tuple[int, ...], float]:
    cp = run_hidden(
        [fpcalc, "-length", "0", "-raw", "-json", str(source)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, errors="replace", check=False,
    )
    if cp.returncode not in (0, 3):
        raise RuntimeError(cp.stderr.strip() or "fpcalc failed")
    data = json.loads((cp.stdout or "{}").strip())
    fingerprint = tuple(int(value) & 0xFFFFFFFF for value in (data.get("fingerprint") or []))
    if not fingerprint:
        raise RuntimeError("fpcalc returned an empty fingerprint")
    return fingerprint, float(data.get("duration") or fallback_duration or 0.0)


def _recover_short_chromaprint(fpcalc: str, source: Path, track: Track) -> Tuple[Tuple[int, ...], float]:
    """Re-decode only suspicious files to a consistent 11025-Hz mono PCM WAV.

    Both subprocesses are children of the existing kill-on-close Job Object.
    Temporary PCM stays within this program's isolated app-data directory and
    is always deleted. Never fabricate identity from an incomplete fingerprint.
    """
    pair = _locate_ffmpeg_pair()
    if pair:
        ffmpeg = pair[0]
    else:
        ffmpeg, _ffprobe = ensure_ffmpeg()
    temp_root = _temp_dir() / "fingerprint_recovery"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fp-", dir=str(temp_root)) as work:
        wav = Path(work) / "normalized.wav"
        cmd = [
            ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
            "-i", str(source), "-map", "0:a:0", "-vn", "-sn", "-dn",
            "-c:a", "pcm_s16le", "-ar", "11025", "-ac", "1", "-f", "wav", str(wav),
        ]
        cp = run_hidden(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, errors="replace", check=False)
        if cp.returncode != 0 or not wav.is_file():
            raise RuntimeError(
                "FFmpeg full-audio decode failed: "
                + (cp.stderr.strip() or str(cp.returncode))
            )
        return _read_chromaprint_json(fpcalc, wav, track.duration)


def chromaprint_fingerprint(fpcalc: str, track: Track) -> Tuple[Tuple[int, ...], float]:
    fingerprint_source = track.path
    temporary_path: Optional[Path] = None

    if track.virtual_from_cue:
        pair = _locate_ffmpeg_pair()
        if pair:
            ffmpeg, _ffprobe = pair
        else:
            ffmpeg, _ffprobe = ensure_ffmpeg()

        _migrate_legacy_app_data()
        temp_root = _temp_dir() / "cue_segments"
        temp_root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f"cue_{track.release_id}_{track.cue_track_number:02d}_",
            suffix=".wav",
            dir=str(temp_root),
        )
        os.close(fd)
        temporary_path = Path(temp_name)

        cmd = [
            ffmpeg,
            "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{max(0.0, track.cue_start_seconds):.6f}",
            "-i", str(track.path),
        ]
        if track.duration > 0:
            cmd += ["-t", f"{track.duration:.6f}"]
        cmd += ["-map", "0:a:0", "-vn", "-acodec", "pcm_s16le", "-f", "wav", str(temporary_path)]

        cp = run_hidden(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", check=False)
        if cp.returncode != 0:
            try:
                temporary_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise RuntimeError(cp.stderr.strip() or "ffmpeg failed to extract CUE track")
        fingerprint_source = temporary_path

    try:
        fp, fp_duration = _read_chromaprint_json(fpcalc, fingerprint_source, track.duration)
        expected_duration = max(float(track.duration or 0.0), fp_duration)
        if _chromaprint_fingerprint_incomplete(len(fp), expected_duration):
            short_count = len(fp)
            try:
                repaired, repaired_duration = _recover_short_chromaprint(
                    fpcalc, fingerprint_source, track
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Incomplete Chromaprint fingerprint ({short_count} frames for "
                    f"{expected_duration:.2f}s) and FFmpeg recovery failed: {exc}"
                ) from exc
            if _chromaprint_fingerprint_incomplete(
                len(repaired), max(expected_duration, repaired_duration)
            ):
                raise RuntimeError(
                    f"Incomplete Chromaprint fingerprint ({short_count} frames); "
                    f"full FFmpeg recovery yielded only {len(repaired)} frames "
                    f"for {expected_duration:.2f}s. No speculative audio merge."
                )
            fp, fp_duration = repaired, repaired_duration
            track.fingerprint_repaired = True
        return fp, fp_duration
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except Exception:
                pass


ADVISORY_VERSION_PAREN_RE = re.compile(
    r"[\[(]\s*(?:(?:album|main|original)\s+version(?:\s+(?:explicit|edited|clean|dirty|censored))?|"
    r"(?:explicit|edited|clean|dirty|censored)\s+version|(?:explicit|clean|dirty|censored))\s*[\])]",
    re.I,
)
ADVISORY_VERSION_TRAILING_RE = re.compile(
    r"\s*(?:-|:)\s*(?:(?:album|main|original)\s+version(?:\s+(?:explicit|edited|clean|dirty|censored))?|"
    r"(?:explicit|edited|clean|dirty|censored)\s+version)\s*$",
    re.I,
)
CENSOR_MASK_RE = re.compile(r"(?:\*{2,}|_{2,})")


def strip_featured_credit_for_match(text: str) -> str:
    text = ascii_punctuation(text or "")
    text = re.sub(r"[\[(]\s*(?:feat(?:uring)?|ft)\.?\s+[^\])]+[\])]", " ", text, flags=re.I)
    text = re.sub(r"\s+(?:feat(?:uring)?|ft)\.?\s+[^\[(]+$", " ", text, flags=re.I)
    return normalize_space(text)


def strip_advisory_version_for_match(text: str) -> str:
    """Ignore explicit/clean advisory wording in the current analyzer stage.

    This intentionally strips labels such as Album Version Edited/Explicit and
    Explicit/Clean Version, while preserving semantic versions such as Radio Edit,
    Acoustic, French Version, US Version, Guitar Version, etc.
    """
    text = ADVISORY_VERSION_PAREN_RE.sub(" ", text or "")
    text = ADVISORY_VERSION_TRAILING_RE.sub(" ", text)
    return normalize_space(text)


def title_for_match(text: str) -> str:
    text = strip_featured_credit_for_match(text)
    text = strip_advisory_version_for_match(text)
    return text


def _advisory_track_policy_key(track: Track) -> Tuple[str, Tuple[str, ...]]:
    title = strip_advisory_version_for_match(
        ascii_punctuation(strip_track_number(track.display_title))
    )
    title_key = compact_title_key(title)
    artists = tuple(sorted(_artist_signature(track.artist)))
    return title_key, artists


def apply_explicit_over_clean_policy(releases: List[Release]) -> int:
    """Explicit always supersedes the corresponding Clean track.

    Clean/Explicit is a preference policy, not acoustic identity. A clean track
    loses its coverage obligation when an explicit counterpart with the same
    title/version/artist identity exists anywhere in the active collection.
    """
    return _apply_explicit_over_clean_tracks([track for rel in releases for track in rel.tracks])


def _apply_explicit_over_clean_tracks(tracks: Sequence[Track]) -> int:
    """Record advisory exclusion even if another policy already excludes it."""
    explicit_keys = {
        _advisory_track_policy_key(track)
        for track in tracks
        if not track.exclude_from_coverage
        and track.explicit == "explicit"
        and _advisory_track_policy_key(track)[0]
    }

    removed = 0
    for track in tracks:
        if track.explicit != "clean":
            continue
        key = _advisory_track_policy_key(track)
        if key[0] and key in explicit_keys:
            was_excluded = track.exclude_from_coverage
            track.exclude_from_coverage = True
            track.excluded_by_pattern = "Explicit>Clean"
            removed += not was_excluded
    return removed


def apply_compilation_policy(releases: List[Release]) -> int:
    """Keep all compilation groups reversible for manual Release Map removals.

    Compilations are last-resort providers in the exact optimizer, not a reason
    to erase track groups or permanently set base_excluded_from_coverage.
    The previous destructive early pass lost every Trilogy CD group after the
    user blocked its ordinary-album replacements.
    """
    return 0


def identity_title(text: str) -> str:
    n = normalize_title(title_for_match(text))
    # Mastering labels are not separate songs for this project's coverage goal.
    n = re.sub(r"[\[(]?\s*(?:\d{4}\s+)?remaster(?:ed)?(?:\s+version)?\s*[\])] ?", " ", n, flags=re.I)
    n = re.sub(r"\b(?:\d{4}\s+)?remaster(?:ed)?\b", " ", n, flags=re.I)
    return re.sub(r"[\W_]+", "", normalize_space(n))


def content_qualifiers(text: str) -> Set[str]:
    q = semantic_qualifiers(title_for_match(text))
    q.discard("remaster")
    q.discard("remastered")
    # Explicit/clean/edited advisory state is intentionally not an active
    # analyzer criterion until a reliable detector is implemented.
    q.discard("explicit")
    q.discard("clean")
    q.discard("version")
    return q


def masked_title_compatible(a: str, b: str) -> bool:
    """Allow censorship masks such as Ni**as / Ni__as to match the full title."""
    def pattern(text: str):
        raw = title_for_match(text or "").lower()
        if not CENSOR_MASK_RE.search(raw):
            return None
        raw = CENSOR_MASK_RE.sub(" CENSORMASK ", raw)
        raw = ascii_punctuation(raw)
        parts = re.split(r"\s*CENSORMASK\s*", raw)
        keys = [compact_title_key(x) for x in parts]
        return "^" + r"\w*".join(re.escape(k) for k in keys) + "$"

    ka = identity_title(a)
    kb = identity_title(b)
    pa = pattern(a)
    pb = pattern(b)
    return bool((pa and re.fullmatch(pa, kb)) or (pb and re.fullmatch(pb, ka)))


def fingerprint_similarity(fp1: Tuple[int, ...], fp2: Tuple[int, ...]) -> Optional[Tuple[float, float, float, int, float, float, int]]:
    """Compare Chromaprint fingerprints using audio only.

    Always evaluate zero/near-zero alignment in addition to histogram candidates.
    The previous implementation could omit the real shift when alternate
    masterings produced too few identical high-bit fingerprint words.
    """
    if not fp1 or not fp2 or min(len(fp1), len(fp2)) < 20:
        return None

    positions12 = defaultdict(list)
    positions10 = defaultdict(list)
    for i, value in enumerate(fp1):
        positions12[(value >> 20) & 0xFFF].append(i)
        positions10[(value >> 22) & 0x3FF].append(i)

    histogram = Counter()
    for j, value in enumerate(fp2):
        for i in positions12.get((value >> 20) & 0xFFF, ()):
            histogram[i - j] += 4
        for i in positions10.get((value >> 22) & 0x3FF, ()):
            histogram[i - j] += 1

    shifts: List[int] = []
    seen_shifts: Set[int] = set()

    def add_shift(value: int) -> None:
        if value not in seen_shifts:
            seen_shifts.add(value)
            shifts.append(value)

    for shift in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6):
        add_shift(shift)
    for shift, _count in histogram.most_common(24):
        add_shift(shift)

    best = None
    for shift in shifts:
        a0 = max(shift, 0)
        b0 = max(-shift, 0)
        n = min(len(fp1) - a0, len(fp2) - b0)
        if n < 20:
            continue
        overlap = n / max(1, min(len(fp1), len(fp2)))
        dists = [(fp1[a0 + k] ^ fp2[b0 + k]).bit_count() for k in range(n)]
        avg = sum(dists) / n
        good = sum(d <= 10 for d in dists) / n
        excellent = sum(d <= 5 for d in dists) / n
        ordered = sorted(dists)
        median = float(ordered[n // 2]) if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
        p90 = ordered[int(0.90 * (n - 1))]
        cand = (avg, good, overlap, shift, excellent, median, p90)
        if best is None or (avg, -good, -excellent, -overlap) < (best[0], -best[1], -best[4], -best[2]):
            best = cand
    return best

def _fingerprint_segment_is_silence(segment: Tuple[int, ...]) -> bool:
    """Recognize long Chromaprint regions produced by digital/near silence."""
    if len(segment) < FP_SILENCE_MIN_FRAMES:
        return True
    counts = Counter(segment)
    dominant = counts.most_common(1)[0][1] / len(segment)
    unique_fraction = len(counts) / len(segment)
    return dominant >= 0.90 or unique_fraction <= 0.03


def _unmatched_fingerprint_is_silence(fp1: Tuple[int, ...], fp2: Tuple[int, ...], shift: int) -> bool:
    a0 = max(shift, 0)
    b0 = max(-shift, 0)
    n = min(len(fp1) - a0, len(fp2) - b0)
    segments = (fp1[:a0], fp2[:b0], fp1[a0 + n:], fp2[b0 + n:])
    return all(_fingerprint_segment_is_silence(seg) for seg in segments)


def _fingerprint_candidate_match_values(
    fp1: Tuple[int, ...],
    duration1: float,
    fp2: Tuple[int, ...],
    duration2: float,
    sim=None,
) -> Tuple[bool, Optional[Tuple[float, float, float, int, float, float, int]]]:
    sim = sim if sim is not None else fingerprint_similarity(fp1, fp2)
    matched = bool(min(len(fp1), len(fp2)) >= 20
                   and _fingerprint_profile_identity(
                       sim, fingerprint_items=min(len(fp1), len(fp2)),
                       acoustic_coverage=_fingerprint_acoustic_coverage(fp1, fp2, sim))
                   and not _duration_version_conflict(duration1, duration2))
    return matched, sim


def _fingerprint_pcm_rescue_candidate(
    fp1: Tuple[int, ...], duration1: float,
    fp2: Tuple[int, ...], duration2: float, sim
) -> bool:
    """Route strong but inconclusive fingerprints to independent PCM proof.

    The normal authoritative fingerprint acceptance path is not affected.
    Whole-recording coverage and the 8-second limit remain mandatory.
    """
    if not sim or min(len(fp1), len(fp2)) < 120:
        return False
    score, good, overlap, _shift, excellent, median, p90 = sim
    return bool(
        not _duration_version_conflict(duration1, duration2)
        and 0 <= score <= 6.5
        and good >= 0.895
        and excellent >= 0.40
        and median <= 6
        and p90 <= 11
        and overlap >= 0.995
        and _fingerprint_acoustic_coverage(fp1, fp2, sim) >= 0.995
    )


def fingerprint_auto_match_values(fp1, duration1, fp2, duration2, advisory_conflict=False):
    """A primary fingerprint match within the agreed 8-second bound is final."""
    return _fingerprint_candidate_match_values(fp1, duration1, fp2, duration2)


def _pcm_sum_of_squares(samples) -> int:
    sumprod = getattr(math, "sumprod", None)
    return sumprod(samples, samples) if sumprod else sum(x * x for x in samples)


def _pcm_correlation(left, right) -> float:
    count = len(left)
    if not count or count != len(right):
        return 0.0
    sumprod = getattr(math, "sumprod", None)
    dot = (lambda a, b: sumprod(a, b)) if sumprod else (lambda a, b: sum(x*y for x,y in zip(a,b)))
    sx, sy = sum(left), sum(right)
    vx = max(0.0, dot(left,left)-sx*sx/count)
    vy = max(0.0, dot(right,right)-sy*sy/count)
    if vx < count*4 or vy < count*4:
        # Both effectively silent windows are neutral; one-sided audible
        # content is a difference, never a matching silent interval.
        return 1.0 if vx < count*4 and vy < count*4 else 0.0
    if count < 32:
        return 0.0
    return min(1.0, abs((dot(left,right)-sx*sy/count)/math.sqrt(vx*vy)))


def _padding_levels_are_quiet(measured) -> bool:
    # FFmpeg's printed dB values can shift the converted level by a small
    # fraction of one sample unit. Empty, non-finite or negative data fail.
    return bool(measured) and all(
        0 <= row["rms_lsb"] <= PADDING_SILENCE_RMS_LSB + .001
        and 0 <= row["peak_lsb"] <= PADDING_SILENCE_PEAK_LSB + .001
        for row in measured
    )


class _PCMIdentityVerifier:
    """Read-only, bounded FFmpeg confirmation of uncertain fingerprint pairs.

    Stereo windows cover the entire aligned recording, including internal
    sections. Per-window gain/DC/polarity normalization tolerates ordinary
    mastering without treating shared accompaniment as equal performances.
    """
    rate = 8000
    cache_limit = 256 * 1024 * 1024
    minimum_correlation = 0.985

    def __init__(self):
        self.work = None
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.ffmpeg = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.work is not None:
            self.work.cleanup()

    def _decode(self, track: Track, pinned: Set[str]):
        stat = track.path.stat()
        key = hashlib.sha256(repr((str(track.path.resolve()), stat.st_size,
             stat.st_mtime_ns, track.cue_start_seconds, track.cue_end_seconds)).encode()).hexdigest()
        pinned.add(key)
        if key in self.cache:
            path, size = self.cache.pop(key)
            self.cache[key] = (path,size)
            return path
        if self.work is None:
            root = _temp_dir()
            root.mkdir(parents=True, exist_ok=True)
            self.work = tempfile.TemporaryDirectory(prefix="identity-", dir=str(root))
            pair = _locate_ffmpeg_pair()
            if not pair:
                raise RuntimeError("FFmpeg unavailable for acoustic confirmation")
            self.ffmpeg = pair[0]
        path = Path(self.work.name) / (key + ".pcm")
        args = [self.ffmpeg, "-v", "error", "-nostdin", "-y"]
        if track.virtual_from_cue:
            args += ["-ss", str(track.cue_start_seconds)]
        args += ["-i", str(track.path)]
        if track.virtual_from_cue and track.cue_end_seconds > track.cue_start_seconds:
            args += ["-t", str(track.cue_end_seconds-track.cue_start_seconds)]
        args += ["-map", "0:a:0", "-vn", "-ac", "2", "-ar", str(self.rate),
                 "-c:a", "pcm_s16le", "-f", "s16le", str(path)]
        result = run_hidden(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            path.unlink(missing_ok=True)
            message = result.stderr.decode("utf-8", "replace").strip()[:400]
            raise RuntimeError(message or "Audio confirmation decode failed")
        size = path.stat().st_size
        if size < 128:
            raise RuntimeError("Audio confirmation has insufficient samples")
        self.cache[key] = (path,size)
        self.cache_bytes += size
        for old in list(self.cache):
            if self.cache_bytes <= self.cache_limit:
                break
            if old not in pinned:
                old_path, old_size = self.cache.pop(old)
                old_path.unlink(missing_ok=True)
                self.cache_bytes -= old_size
        return path

    @staticmethod
    def _probe(samples, start, step=4, count=256, channel=0):
        return [samples[2*(start+i*step)+channel] for i in range(count)]

    def _align(self, a, b, guess):
        na, nb = len(a)//2, len(b)//2
        available = min(na-max(guess,0), nb-max(-guess,0))
        if available < 8192:
            raise RuntimeError("Audio too short for independent alignment")
        start = max(-guess,0) + min(available//3, available-6144)
        # Search each sample offset on a bounded probe. A coarse lag grid can
        # miss the true phase and prefer another cycle of periodic music.
        probe = self._probe(b,start)
        candidates = [lag for lag in range(guess-1024,guess+1025)
                      if 0 <= start+lag and start+lag+1024 < na]
        if not candidates:
            raise RuntimeError("Audio alignment outside readable samples")
        return max(candidates,
                   key=lambda value: (_pcm_correlation(self._probe(a,start+value),probe),-abs(value-guess)))

    def verify_padding(self, first: Track, second: Track, sim) -> Dict[str, object]:
        """Measure only independently silent, unmatched recording boundaries.

        Fingerprint identity is the caller's responsibility. The stereo cache
        locates boundaries; native-rate/all-channel measurements prove silence
        so downsampling cannot conceal high-frequency or extra-channel audio.
        """
        result = {"passed": False, "method": "decoded-boundary-silence-v2",
                  "reason": "Padding confirmation unavailable", "alignment_lag_samples": 0,
                  "effective_durations_seconds": [0.0, 0.0], "padding_seconds": [0.0, 0.0],
                  "silence_rms_limit_lsb": PADDING_SILENCE_RMS_LSB,
                  "silence_peak_limit_lsb": PADDING_SILENCE_PEAK_LSB,
                  "level_rounding_tolerance_lsb": .001,
                  "boundary_spans": []}
        tolerance = max(0, int(self.rate * .002))

        def levels(samples, start, end):
            count = end - start
            measured = []
            for channel in (0, 1):
                total = squares = peak = 0
                if count:
                    channel_samples = samples[2 * start + channel:2 * end:2]
                    total = sum(channel_samples)
                    squares = _pcm_sum_of_squares(channel_samples)
                    peak = max(max(channel_samples), -min(channel_samples), 0)
                mean_square = squares / count if count else 0.0
                measured.append({"rms_lsb": math.sqrt(mean_square), "peak_lsb": peak,
                                 "centered_rms_lsb": math.sqrt(max(0.0, mean_square - (total / count) ** 2))
                                 if count else 0.0})
            return measured

        def native_levels(track, start, end):
            offset = track.cue_start_seconds if track.virtual_from_cue else 0.0
            args = [self.ffmpeg, "-hide_banner", "-nostdin", "-v", "info",
                    "-ss", str(offset + start / self.rate), "-i", str(track.path),
                    "-t", str((end - start) / self.rate), "-map", "0:a:0", "-vn", "-sn", "-dn",
                    "-af", "atrim=duration=" + str((end - start) / self.rate)
                    + ",astats=metadata=0:reset=0", "-f", "null", "-"]
            decoded = run_hidden(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
            output = decoded.stderr.decode("utf-8", "replace")
            if decoded.returncode:
                raise RuntimeError("Native boundary decode failed: " + output.strip()[-400:])
            rates = re.findall(r"Audio:[^\n]*?,\s*(\d+)\s*Hz", output)
            counts = re.findall(r"Number of samples:\s*(\d+(?:\.\d+)?)", output)
            sections = re.findall(r"Channel:\s*(\d+)\s*\n(.*?)(?=\[[^\n]*\]\s*(?:Channel:|Overall)|\Z)",
                                  output, re.S)
            if not rates or not counts or not sections:
                raise RuntimeError("Native boundary measurement is incomplete")
            rate = int(rates[0])
            channels = len(sections)
            if rate < self.rate or (track.sample_rate and track.sample_rate != rate):
                raise RuntimeError("Native boundary sample rate is insufficient or inconsistent")
            if track.channels and track.channels != channels:
                raise RuntimeError("Native boundary channel count is inconsistent")
            count = float(counts[-1])
            if count <= 0 or abs(count / rate - (end - start) / self.rate) > max(.002, 2 / rate):
                raise RuntimeError("Native boundary decode duration is inconsistent")
            measured = []
            for number, section in sections:
                row = {"channel": int(number)}
                for name, level_key in (("RMS level dB", "rms_lsb"), ("Peak level dB", "peak_lsb")):
                    values = re.findall(re.escape(name) + r":\s*(-?inf|[-+]?\d+(?:\.\d+)?)", section)
                    if len(values) != 1:
                        raise RuntimeError("Native boundary channel levels are incomplete")
                    db = float(values[0])
                    if math.isnan(db) or db == math.inf:
                        raise RuntimeError("Native boundary channel levels are invalid")
                    row[level_key] = 0.0 if db == -math.inf else 32768 * 10 ** (db / 20)
                measured.append(row)
            return {"sample_rate": rate, "channels": channels, "samples_per_channel": int(count),
                    "levels": measured}

        try:
            if sys.byteorder != "little":
                raise RuntimeError("Unsupported PCM byte order")
            tracks = (first, second)
            declared = [float(track.duration) for track in tracks]
            if any(not math.isfinite(value) or not 0 < value <= 86400 for value in declared):
                raise RuntimeError("Recording duration is missing or implausible")
            pinned: Set[str] = set()
            pa, pb = self._decode(first, pinned), self._decode(second, pinned)
            if pa.stat().st_size % 4 or pb.stat().st_size % 4:
                raise RuntimeError("Decoded stereo samples are incomplete")
            with pa.open("rb") as fa, pb.open("rb") as fb:
                with mmap.mmap(fa.fileno(), 0, access=mmap.ACCESS_READ) as ma, mmap.mmap(fb.fileno(), 0, access=mmap.ACCESS_READ) as mb:
                    a, b = memoryview(ma).cast("h"), memoryview(mb).cast("h")
                    try:
                        frames = [len(a) // 2, len(b) // 2]
                        durations = [count / self.rate for count in frames]
                        result["decoded_durations_seconds"] = durations
                        result["effective_durations_seconds"] = durations[:]
                        if any(count < max(8192, self.rate * 1.5) for count in frames):
                            raise RuntimeError("Decoded recording has insufficient samples")
                        if any(abs(actual - expected) > max(.5, expected * .001)
                               for actual, expected in zip(durations, declared)):
                            raise RuntimeError("Decoded recording duration is inconsistent")
                        # Validate both native formats, including a recording
                        # with no unmatched span to trigger a boundary probe.
                        result["native_source_formats"] = []
                        for track in tracks:
                            native = native_levels(track, 0, max(1, tolerance))
                            result["native_source_formats"].append(
                                {"sample_rate": native["sample_rate"], "channels": native["channels"]})
                        # Default Chromaprint item duration is (4096 // 3) / 11025.
                        # Total duration/count includes startup delay and drifts on long prefixes.
                        # https://github.com/acoustid/chromaprint/blob/master/src/fingerprinter_configuration.cpp
                        seconds_per_frame = 1365.0 / 11025.0
                        lag = self._align(a, b, round(int(sim[3]) * seconds_per_frame * self.rate))
                        result["alignment_lag_samples"] = lag
                        a0, b0 = max(lag, 0), max(-lag, 0)
                        length = min(frames[0] - a0, frames[1] - b0)
                        if length < max(8192, self.rate * 1.5):
                            raise RuntimeError("Aligned recording has insufficient samples")
                        result["aligned_duration_seconds"] = length / self.rate
                        activity = [levels(samples, start, start + length)
                                    for samples, start in ((a, a0), (b, b0))]
                        result["aligned_levels"] = activity
                        if any(max(row["centered_rms_lsb"] for row in measured) <= 2
                               for measured in activity):
                            raise RuntimeError("Aligned recording is entirely silent or constant")
                        removed = [0, 0]
                        retained_reasons = []
                        spans = ((0, a, "prefix", 0, a0), (0, a, "tail", a0 + length, frames[0]),
                                 (1, b, "prefix", 0, b0), (1, b, "tail", b0 + length, frames[1]))
                        for index, samples, boundary, start, end in spans:
                            boundary_samples = end - start
                            reason = "Unmatched boundary retained"
                            evidence = {"track_index": index, "boundary": boundary,
                                        "start_seconds": start / self.rate, "end_seconds": end / self.rate,
                                        "verified_samples": 0, "retained_boundary_samples": 0}
                            result["boundary_spans"].append(evidence)
                            if end == start:
                                continue
                            for attempt in (0, 1):
                                if attempt:
                                    # Unverified resampler-edge samples remain in
                                    # effective duration; only proven silence is removed.
                                    keep = min(tolerance, end - start)
                                    evidence["retained_boundary_samples"] = keep
                                    if boundary == "prefix":
                                        end -= keep
                                    else:
                                        start += keep
                                    if end == start:
                                        break
                                measured = levels(samples, start, end)
                                evidence["cache_levels"] = measured
                                if not _padding_levels_are_quiet(measured):
                                    reason = "Unmatched decoded intro/outro contains audio"
                                else:
                                    native = native_levels(tracks[index], start, end)
                                    evidence["native_measurement"] = native
                                    if _padding_levels_are_quiet(native["levels"]):
                                        removed[index] += end - start
                                        evidence["verified_samples"] = end - start
                                        evidence["retained_boundary_samples"] = boundary_samples - (end - start)
                                        evidence["verified_start_seconds"] = start / self.rate
                                        evidence["verified_end_seconds"] = end / self.rate
                                        break
                                    reason = "Unmatched native-rate intro/outro contains audio"
                            if not evidence["verified_samples"]:
                                # Audible/unverified boundaries retain their FULL
                                # length. They cannot erase another boundary's
                                # proven padding; the existing 8s rule compares
                                # the resulting durations after all measurements.
                                evidence["retained_boundary_samples"] = boundary_samples
                                evidence["retained_reason"] = reason
                                retained_reasons.append(reason)
                        result["padding_seconds"] = [count / self.rate for count in removed]
                        result["effective_durations_seconds"] = [(count - padding) / self.rate
                                                                  for count, padding in zip(frames, removed)]
                        result["remaining_duration_difference_seconds"] = abs(
                            result["effective_durations_seconds"][0] - result["effective_durations_seconds"][1])
                        result["passed"] = any(removed)
                        result["reason"] = ("Boundary padding independently verified; other samples retained"
                                            if any(removed) else retained_reasons[0]
                                            if retained_reasons else "No unmatched boundary padding")
                        return result
                    finally:
                        a.release()
                        b.release()
        except Exception as exc:
            result["reason"] = "Decoded padding confirmation unavailable: " + str(exc)
            return result

    def verify_mastering(self, first: Track, second: Track, sim) -> Dict[str, object]:
        """Positive-only, read-only waveform confirmation of borderline masters.

        Full-track samples, not title/version labels, decide. Shared backing
        tracks with different vocals must fail correlation over vocal passages.
        An unreadable or poorly aligned recording fails closed.
        """
        result = {
            "passed": False, "method": "decoded-positive-mastering-v1",
            "windows_tested": 0, "minimum_coverage": 0.995,
            "minimum_p10_correlation": 0.95,
            "minimum_median_correlation": 0.975,
            "minimum_fraction_above_0_95": 0.95,
        }
        try:
            if sys.byteorder != "little":
                raise RuntimeError("Unsupported PCM byte order")
            pinned: Set[str] = set()
            pa = self._decode(first, pinned)
            pb = self._decode(second, pinned)
            with pa.open("rb") as fa, pb.open("rb") as fb:
                with mmap.mmap(fa.fileno(), 0, access=mmap.ACCESS_READ) as ma, \
                     mmap.mmap(fb.fileno(), 0, access=mmap.ACCESS_READ) as mb:
                    a, b = memoryview(ma).cast("h"), memoryview(mb).cast("h")
                    try:
                        na, nb = len(a) // 2, len(b) // 2
                        guess = round(int(sim[3]) * (1365.0 / 11025.0) * self.rate)
                        lag = self._align(a, b, guess)
                        a0, b0 = max(lag, 0), max(-lag, 0)
                        length = min(na - a0, nb - b0)
                        coverage = length / max(1, na, nb)
                        result["aligned_coverage"] = round(coverage, 6)
                        result["alignment_lag_samples"] = lag
                        if coverage < 0.995 or length < self.rate * 5:
                            result["reason"] = "Insufficient full recording overlap"
                            return result
                        window = self.rate // 2
                        hop = self.rate
                        starts = list(range(0, length - window + 1, hop))
                        if starts[-1] != length - window:
                            starts.append(length - window)
                        values = []
                        for offset in starts:
                            channel_quality = []
                            informative = False
                            for channel in (0, 1):
                                x = self._probe(a, a0 + offset, 8, 500, channel)
                                y = self._probe(b, b0 + offset, 8, 500, channel)
                                if max(x) - min(x) > 16 or max(y) - min(y) > 16:
                                    informative = True
                                channel_quality.append(_pcm_correlation(x, y))
                            if informative:
                                values.append(min(channel_quality))
                        result["windows_tested"] = len(values)
                        if len(values) < 10:
                            result["reason"] = "Insufficient informative PCM windows"
                            return result
                        values.sort()
                        p10 = values[int(0.1 * (len(values) - 1))]
                        median = values[len(values) // 2]
                        fraction = sum(x >= 0.95 for x in values) / len(values)
                        result["p10_correlation"] = round(p10, 6)
                        result["median_correlation"] = round(median, 6)
                        result["fraction_above_0_95"] = round(fraction, 6)
                        result["passed"] = (
                            p10 >= 0.95 and median >= 0.975 and fraction >= 0.95
                        )
                        result["reason"] = (
                            "Waveform consistency confirmed" if result["passed"]
                            else "Waveform consistency below confirmation requirements"
                        )
                        return result
                    finally:
                        a.release()
                        b.release()
        except Exception as exc:
            result["reason"] = "Decoded mastering confirmation unavailable: " + str(exc)
            return result

    def verify(self, first: Track, second: Track, sim) -> Dict[str, object]:
        result = {"passed": False, "method": "decoded-stereo-window-correlation-v1",
                  "minimum_required": self.minimum_correlation, "windows_tested": 0}
        try:
            if sys.byteorder != "little":
                raise RuntimeError("Unsupported PCM byte order")
            pinned: Set[str] = set()
            pa, pb = self._decode(first,pinned), self._decode(second,pinned)
            with pa.open("rb") as fa, pb.open("rb") as fb:
                with mmap.mmap(fa.fileno(),0,access=mmap.ACCESS_READ) as ma, mmap.mmap(fb.fileno(),0,access=mmap.ACCESS_READ) as mb:
                    a, b = memoryview(ma).cast("h"), memoryview(mb).cast("h")
                    try:
                        seconds_per_frame = min(
                            first.duration/max(1,len(first.fingerprint)),
                            second.duration/max(1,len(second.fingerprint)))
                        guess = round(int(sim[3])*seconds_per_frame*self.rate)
                        lag = self._align(a,b,guess)
                        a0,b0 = max(lag,0),max(-lag,0)
                        length = min(len(a)//2-a0,len(b)//2-b0)
                        coverage = length/max(len(a)//2,len(b)//2)
                        result["aligned_coverage"] = round(coverage,6)
                        result["alignment_lag_samples"] = lag
                        # Never crop away an audible intro/outro just because
                        # it is a small percentage of a long recording.
                        unmatched_silent = True
                        for samples,start,end in ((a,0,a0),(a,a0+length,len(a)//2),
                                                   (b,0,b0),(b,b0+length,len(b)//2)):
                            count = end-start
                            if count <= 16:  # <=2 ms resampler boundary tolerance
                                continue
                            for channel in (0,1):
                                values = self._probe(samples,start,1,count,channel)
                                if _pcm_correlation(values,[0]*count) < 1.0:
                                    unmatched_silent = False
                                    break
                            if not unmatched_silent:
                                break
                        result["unmatched_is_silence"] = unmatched_silent
                        if not unmatched_silent:
                            result["reason"] = "Unmatched decoded intro/outro contains audio"
                            return result
                        worst = 1.0
                        window = self.rate//2
                        count = min(window,length)
                        starts = list(range(0,max(1,length-count+1),window))
                        if starts[-1] != length-count:
                            starts.append(length-count)
                        for offset in starts:
                            step = max(1,count//512)
                            take = count//step
                            values = [_pcm_correlation(
                                self._probe(a,a0+offset,step,take,channel),
                                self._probe(b,b0+offset,step,take,channel)) for channel in (0,1)]
                            quality = min(values)
                            result["windows_tested"] += 1
                            worst = min(worst,quality)
                            result["worst_correlation"] = round(worst,6)
                            if quality < self.minimum_correlation:
                                result["reason"] = "Decoded audio differs inside aligned recording"
                                result["different_at_seconds"] = round(offset/self.rate,3)
                                return result
                        result["passed"] = result["windows_tested"] >= 3
                        result["reason"] = "Decoded audio verified" if result["passed"] else "Insufficient verification windows"
                        return result
                    finally:
                        a.release()
                        b.release()
        except Exception as exc:
            result["reason"] = "Acoustic confirmation unavailable: " + str(exc)
            return result


def fingerprint_auto_match(a: Track, b: Track) -> Tuple[bool, Optional[Tuple[float, float, float, int, float, float, int]]]:
    """High-confidence audio-only identity test."""
    return fingerprint_auto_match_values(
        a.fingerprint, _identity_track_duration(a), b.fingerprint, _identity_track_duration(b),
        _explicit_identity_disagreement(a, b),
    )


_COMPARE_TRACK_DATA: List[Tuple[Tuple[int, ...], float]] = []


def _init_compare_worker(track_data: List[Tuple[Tuple[int, ...], float]]) -> None:
    global _COMPARE_TRACK_DATA
    _COMPARE_TRACK_DATA = track_data


def _compare_pair_batch_worker(batch: List[Tuple[int, int, int]]):
    """Compare a small batch and return it as soon as the batch finishes."""
    result = []
    for pair_index, a, b in batch:
        fp1, d1 = _COMPARE_TRACK_DATA[a]
        fp2, d2 = _COMPARE_TRACK_DATA[b]
        matched, sim = fingerprint_auto_match_values(fp1, d1, fp2, d2)
        result.append((pair_index, a, b, matched, sim))
    return result

def _release_tree_files(folder: Path) -> Tuple[List[Path], List[Path]]:
    """Return audio files and all files for one release container recursively."""
    audio: List[Path] = []
    all_files: List[Path] = []
    for current, dirs, files in os.walk(folder):
        dirs.sort(key=str.lower)
        files.sort(key=str.lower)
        base = Path(current)
        for name in files:
            fp = base / name
            all_files.append(fp)
            if fp.suffix.lower() in AUDIO_EXTS:
                audio.append(fp)
    return audio, all_files


DISC_FOLDER_RE = re.compile(r"^(?:cd|disc|disk)\s*[-_. ]*\d+\b|^bonus\s+(?:cd|disc|disk)\b", re.I)
SIBLING_DISC_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)\s+(?:cd|disc|disk)\s*[-_. ]*(?P<num>\d+)\s*$",
    re.I,
)


def _direct_audio_files(folder: Path) -> List[Path]:
    try:
        return sorted(
            (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS),
            key=lambda p: p.name.lower(),
        )
    except OSError:
        return []


def _audio_child_dirs(folder: Path) -> List[Path]:
    children: List[Path] = []
    try:
        dirs = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
    except OSError:
        return children
    for child in dirs:
        audio, _ = _release_tree_files(child)
        if audio:
            children.append(child)
    return children


def _is_multidisc_release_container(folder: Path, audio_children: List[Path]) -> bool:
    """Parent release with internal CD1/CD2/Disc 1 subfolders."""
    if not audio_children:
        return False
    return all(DISC_FOLDER_RE.search(child.name.strip()) for child in audio_children)


def _sibling_disc_parts(name: str) -> Optional[Tuple[str, int]]:
    match = SIBLING_DISC_SUFFIX_RE.match(name.strip())
    if not match:
        return None
    return match.group("base").strip(), int(match.group("num"))


def _discover_release_groups(root: Path) -> List[List[Path]]:
    """Return logical releases, each as one or more physical folders.

    Handles both layouts:
      Release/CD1 + Release/CD2
      Release CD 1 + Release CD 2   (sibling folders)
    Organizational folders such as Albums/Other/Singles are traversed.
    """
    groups: List[List[Path]] = []

    def walk(folder: Path) -> None:
        direct_audio = _direct_audio_files(folder)
        audio_children = _audio_child_dirs(folder)

        if direct_audio:
            groups.append([folder])
            return

        if _is_multidisc_release_container(folder, audio_children):
            groups.append([folder])
            return

        try:
            children = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
        except OSError:
            return

        sibling_discs: Dict[str, List[Tuple[int, Path]]] = defaultdict(list)
        for child in children:
            parts = _sibling_disc_parts(child.name)
            if parts and _direct_audio_files(child):
                base, number = parts
                sibling_discs[os.path.normcase(base)].append((number, child))

        consumed: Set[Path] = set()
        for entries in sibling_discs.values():
            if len(entries) < 2:
                continue
            ordered = [p for _n, p in sorted(entries, key=lambda x: (x[0], x[1].name.lower()))]
            groups.append(ordered)
            consumed.update(ordered)

        for child in children:
            if child in consumed:
                continue
            audio, _ = _release_tree_files(child)
            if audio:
                walk(child)

    walk(root)
    groups.sort(key=lambda paths: str(paths[0]).lower())
    return groups


def _read_cue_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _cue_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _cue_time_seconds(value: str) -> float:
    match = re.fullmatch(r"\s*(\d+):(\d+):(\d+)\s*", value or "")
    if not match:
        return 0.0
    minutes, seconds, frames = (int(x) for x in match.groups())
    return minutes * 60.0 + seconds + frames / 75.0


def _resolve_cue_audio_path(cue_path: Path, raw_name: str, audio_files: List[Path]) -> Optional[Path]:
    raw_name = _cue_unquote(raw_name).replace("\\", os.sep).replace("/", os.sep)
    candidate = (cue_path.parent / raw_name).resolve(strict=False)

    for path in audio_files:
        try:
            if path.resolve(strict=False) == candidate:
                return path
        except Exception:
            pass

    wanted_name = Path(raw_name).name.casefold()
    same_dir = [
        p for p in audio_files
        if p.parent.resolve() == cue_path.parent.resolve() and p.name.casefold() == wanted_name
    ]
    if same_dir:
        return same_dir[0]

    by_name = [p for p in audio_files if p.name.casefold() == wanted_name]
    return by_name[0] if len(by_name) == 1 else None


def _parse_cue_tracks(cue_path: Path, audio_files: List[Path]) -> List[Dict[str, object]]:
    text = _read_cue_text(cue_path)

    global_title = ""
    global_performer = ""
    current_file: Optional[Path] = None
    current: Optional[Dict[str, object]] = None
    tracks: List[Dict[str, object]] = []

    file_re = re.compile(r'^\s*FILE\s+(.+?)\s+(?:WAVE|MP3|AIFF|BINARY|MOTOROLA)\s*$', re.I)
    track_re = re.compile(r'^\s*TRACK\s+(\d+)\s+AUDIO\s*$', re.I)
    title_re = re.compile(r'^\s*TITLE\s+(.+?)\s*$', re.I)
    performer_re = re.compile(r'^\s*PERFORMER\s+(.+?)\s*$', re.I)
    index_re = re.compile(r'^\s*INDEX\s+01\s+(\d+:\d+:\d+)\s*$', re.I)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = file_re.match(line)
        if match:
            current_file = _resolve_cue_audio_path(cue_path, match.group(1), audio_files)
            current = None
            continue

        match = track_re.match(line)
        if match:
            if current_file is None:
                current = None
                continue
            current = {
                "cue_path": cue_path,
                "path": current_file,
                "track_number": int(match.group(1)),
                "title": "",
                "performer": "",
                "album": global_title,
                "album_performer": global_performer,
                "start": None,
                "end": 0.0,
            }
            tracks.append(current)
            continue

        match = title_re.match(line)
        if match:
            value = _cue_unquote(match.group(1))
            if current is None:
                global_title = value
            else:
                current["title"] = value
            continue

        match = performer_re.match(line)
        if match:
            value = _cue_unquote(match.group(1))
            if current is None:
                global_performer = value
            else:
                current["performer"] = value
            continue

        if current is None:
            continue

        match = index_re.match(line)
        if match and current.get("start") is None:
            current["start"] = _cue_time_seconds(match.group(1))

    tracks = [t for t in tracks if isinstance(t.get("path"), Path) and t.get("start") is not None]

    for track in tracks:
        if not track.get("album"):
            track["album"] = global_title
        if not track.get("album_performer"):
            track["album_performer"] = global_performer

    for i, track in enumerate(tracks):
        for later in tracks[i + 1:]:
            if later["path"] == track["path"]:
                track["end"] = float(later["start"])
                break

    return tracks


def _cue_image_track_specs(
    cue_files: List[Path],
    audio_files: List[Path],
) -> Tuple[List[Dict[str, object]], Set[Path], List[Path]]:
    unreadable_cues: List[Path] = []
    chosen_by_image: Dict[Path, Tuple[Path, List[Dict[str, object]]]] = {}

    for cue_path in sorted(cue_files, key=lambda p: str(p).lower()):
        try:
            parsed = _parse_cue_tracks(cue_path, audio_files)
        except OSError:
            unreadable_cues.append(cue_path)
            continue
        by_image: Dict[Path, List[Dict[str, object]]] = defaultdict(list)
        for item in parsed:
            by_image[item["path"]].append(item)

        for image_path, specs in by_image.items():
            if len(specs) < 2:
                continue
            previous = chosen_by_image.get(image_path)
            if previous is None or len(specs) > len(previous[1]):
                chosen_by_image[image_path] = (cue_path, specs)

    virtual_specs: List[Dict[str, object]] = []
    image_files: Set[Path] = set()
    for image_path, (_cue, specs) in sorted(chosen_by_image.items(), key=lambda item: str(item[0]).lower()):
        image_files.add(image_path)
        virtual_specs.extend(specs)

    return virtual_specs, image_files, unreadable_cues


def discover_releases(root: Path, root_kind: str, start_id: int) -> List[Release]:
    """Discover logical releases recursively, including CUE-based CD images."""
    releases: List[Release] = []
    rid = start_id

    for physical_paths in _discover_release_groups(root):
        audio: List[Path] = []
        all_files: List[Path] = []
        for p in physical_paths:
            part_audio, part_files = _release_tree_files(p)
            audio.extend(part_audio)
            all_files.extend(part_files)
        if not audio:
            continue

        primary = physical_paths[0]
        sibling = _sibling_disc_parts(primary.name) if len(physical_paths) > 1 else None
        logical_name = sibling[0] if sibling else primary.name
        title = release_title_from_folder(logical_name)

        cue_files = [f for f in all_files if f.suffix.lower() == ".cue"]
        cue = bool(cue_files)
        image_specs, image_files, unreadable_cues = _cue_image_track_specs(cue_files, audio)

        logs = [f for f in all_files if f.suffix.lower() == ".log"]
        audiochecker = any(f.name.lower() == "audiochecker.log" for f in logs)
        rip_logs = [f for f in logs if f.name.lower() != "audiochecker.log"]
        rip_log = bool(rip_logs)
        quality = 100 if cue and rip_log else 75 if cue else 50 if audiochecker else 40

        rel = Release(
            rid=rid,
            root_kind=root_kind,
            path=primary,
            title=title,
            paths=list(physical_paths),
            scan_root=root,
            source_quality=quality,
            has_cue=cue,
            has_rip_log=rip_log,
            has_audiochecker=audiochecker,
            rip_log_paths=list(rip_logs),
            has_cd_image=bool(image_specs),
            cd_image_track_count=len(image_specs),
            cue_paths=list(cue_files),
            unreadable_cue_paths=unreadable_cues,
        )

        track_index = 1
        for ap in audio:
            if ap in image_files:
                continue
            rel.tracks.append(Track(release_id=rid, path=ap, index=track_index))
            track_index += 1

        for spec in image_specs:
            rel.tracks.append(
                Track(
                    release_id=rid,
                    path=spec["path"],
                    index=track_index,
                    virtual_from_cue=True,
                    cue_path=spec["cue_path"],
                    cue_track_number=int(spec["track_number"]),
                    cue_start_seconds=float(spec["start"]),
                    cue_end_seconds=float(spec.get("end") or 0.0),
                    cue_title=str(spec.get("title") or ""),
                    cue_performer=str(spec.get("performer") or spec.get("album_performer") or ""),
                    cue_album=str(spec.get("album") or title),
                )
            )
            track_index += 1

        releases.append(rel)
        rid += 1
    return releases


def _fingerprint_tokens(fp: Tuple[int, ...]) -> Set[int]:
    """Cheap title-independent prefilter for full Chromaprint comparison."""
    if len(fp) < 2:
        return set()
    # Consecutive high-12-bit pairs are stable enough to find likely candidates
    # while making random collisions uncommon. Position is intentionally ignored
    # so small leading/trailing offsets still become candidates.
    return {
        (((fp[i] >> 20) & 0xFFF) << 12) | ((fp[i + 1] >> 20) & 0xFFF)
        for i in range(0, len(fp) - 1, 2)
    }


def _comparison_decision_details(
    fp1: Tuple[int, ...],
    duration1: float,
    fp2: Tuple[int, ...],
    duration2: float,
    matched: bool,
    sim: Optional[Tuple[float, float, float, int, float, float, int]],
    pcm_verification: Optional[Dict[str, object]] = None,
    advisory_conflict: bool = False,
    padding_verification: Optional[Dict[str, object]] = None,
    effective_durations: Optional[Tuple[float, float]] = None,
) -> Dict[str, object]:
    """Explain every acoustic threshold involved in one fingerprint decision."""
    raw_delta = abs(duration1 - duration2)
    if effective_durations is not None:
        duration1, duration2 = effective_durations
    duration_delta = abs(duration1 - duration2)
    duration_version = _duration_version_conflict(duration1, duration2)
    details: Dict[str, object] = {
        "worker_matched": bool(matched),
        "duration_delta_seconds_diagnostic_only": round(duration_delta, 6),
        "duration_difference_seconds": round(duration_delta, 6),
        "raw_duration_difference_seconds": round(raw_delta, 6),
        "effective_durations_seconds": [round(duration1, 6), round(duration2, 6)],
        "decoded_padding_verification": padding_verification,
        "duration_version_threshold_seconds": DURATION_VERSION_MAX_SAME_SECONDS,
        "duration_version_conflict": duration_version,
    }
    if not sim:
        details.update({
            "similarity_available": False,
            "accepted_by": [],
            "strict_pass": False,
            "mastering_pass": False,
            "high_overlap_mastering_pass": False,
            "content_gate_triggered": False,
            "content_gate_pass": False,
            "rejection_reasons": ["fingerprint_similarity returned no comparable result"],
        })
        return details

    score, good, overlap, shift, excellent, median, p90 = sim
    strict_checks = {
        "overlap": overlap >= FP_MIN_OVERLAP,
        "score": score <= FP_AUTO_SCORE,
        "good_fraction": good >= FP_AUTO_GOOD_FRACTION,
        "excellent_fraction": excellent >= FP_AUTO_EXCELLENT_FRACTION,
        "median": median <= FP_AUTO_MEDIAN_MAX,
        "p90": p90 <= FP_AUTO_P90_MAX,
    }
    mastering_checks = {
        "overlap": overlap >= FP_MASTERING_MIN_OVERLAP,
        "score": score <= FP_MASTERING_SCORE,
        "good_fraction": good >= FP_MASTERING_GOOD_FRACTION,
        "median": median <= FP_MASTERING_MEDIAN_MAX,
        "p90": p90 <= FP_MASTERING_P90_MAX,
    }
    sufficient_items = min(len(fp1), len(fp2)) >= 20
    strict_checks["minimum_fingerprint_items"] = sufficient_items
    mastering_checks["minimum_fingerprint_items"] = sufficient_items
    strict_pass = all(strict_checks.values())
    mastering_pass = all(mastering_checks.values())
    high_overlap_checks = _fingerprint_high_overlap_checks(
        sim, min(len(fp1), len(fp2)),
        _fingerprint_acoustic_coverage(fp1, fp2, sim)
    )
    high_overlap_pass = all(high_overlap_checks.values())
    preliminary_pass = strict_pass or mastering_pass or high_overlap_pass
    # A decoded confirmation can ADD a match, never veto a passing fingerprint.
    pcm_pass = bool(
        isinstance(pcm_verification, dict)
        and pcm_verification.get("passed")
        and pcm_verification.get("method") == "decoded-positive-mastering-v1"
    )
    trusted_fingerprint = preliminary_pass
    identity_confirmed = bool(preliminary_pass or pcm_pass)

    a0 = max(shift, 0)
    b0 = max(-shift, 0)
    aligned_frames = max(0, min(len(fp1) - a0, len(fp2) - b0))
    acoustic_coverage = aligned_frames / max(1, len(fp1), len(fp2))
    content_gate_triggered = False
    unmatched_is_silence = None
    content_gate_pass = True

    rejection_reasons: List[str] = []
    if duration_version:
        rejection_reasons.append(
            f"separate version: length differs by {duration_delta:.2f}s "
            f"(threshold {DURATION_VERSION_MAX_SAME_SECONDS:g}s)"
        )
    if not identity_confirmed:
        strict_failed = [name for name, passed in strict_checks.items() if not passed]
        mastering_failed = [name for name, passed in mastering_checks.items() if not passed]
        rejection_reasons.append("strict failed: " + ", ".join(strict_failed))
        rejection_reasons.append("mastering failed: " + ", ".join(mastering_failed))
        high_overlap_failed = [name for name, passed in high_overlap_checks.items() if not passed]
        rejection_reasons.append("high-overlap mastering failed: " + ", ".join(high_overlap_failed))
        if pcm_verification:
            rejection_reasons.append(
                "decoded mastering confirmation failed: "
                + str(pcm_verification.get("reason", "unknown"))
            )
    accepted_by: List[str] = []
    if strict_pass:
        accepted_by.append("strict")
    if mastering_pass:
        accepted_by.append("mastering")
    if high_overlap_pass:
        accepted_by.append("high_overlap_mastering")
    if pcm_pass:
        accepted_by.append("decoded_pcm_mastering")
    if trusted_fingerprint and not duration_version:
        accepted_by.append("authoritative_fingerprint")

    derived_final_match = bool(identity_confirmed and content_gate_pass and not duration_version)
    details.update({
        "similarity_available": True,
        "score": round(score, 6),
        "good_fraction": round(good, 6),
        "excellent_fraction": round(excellent, 6),
        "overlap": round(overlap, 6),
        "acoustic_coverage": round(acoustic_coverage, 6),
        "median": round(median, 6),
        "p90": int(p90),
        "shift": int(shift),
        "strict_checks": strict_checks,
        "strict_pass": strict_pass,
        "mastering_checks": mastering_checks,
        "mastering_pass": mastering_pass,
        "high_overlap_mastering_checks": high_overlap_checks,
        "high_overlap_mastering_pass": high_overlap_pass,
        "decoded_mastering_confirmed": pcm_pass,
        "decoded_mastering_attempted": bool(pcm_verification),
        "accepted_by": accepted_by,
        "content_gate_triggered": content_gate_triggered,
        "unmatched_is_silence": unmatched_is_silence,
        "content_gate_pass": content_gate_pass,
        "definitive_acoustic_identity": _definitive_acoustic_identity(sim),
        "local_fingerprint_identity": None,
        "identity_confirmed": identity_confirmed,
        "fingerprint_identity_authoritative": bool(trusted_fingerprint and not duration_version),
        "explicit_advisory_disagreement": bool(advisory_conflict),
        "decoded_audio_verification": pcm_verification,
        "secondary_identity_checks_applied": bool(pcm_verification),
        "derived_final_match": derived_final_match,
        "decision_consistent": bool(matched) == derived_final_match,
        "rejection_reasons": rejection_reasons,
    })
    return details


def _comparison_track_log_data(track: Track) -> Dict[str, object]:
    # Keep the original per-track classification evidence. A single first-track
    # tag can be wrong, and a normalized/merged value would hide disagreements.
    classification_keys = {
        "releasetype", "musicbrainzalbumtype", "albumtype",
        "primaryreleasetype", "secondaryreleasetype",
        "compilation", "itunescompilation", "albumartist",
    }
    classification_tags = {
        str(key): str(value)
        for key, value in sorted(track.tags.items(), key=lambda item: str(item[0]).casefold())
        if normalized_tag_key(str(key)) in classification_keys
    }
    # Preserve original field names and values so a later comparison log
    # can prove exactly why a file received E, C or Unknown classification.
    advisory_tags = {
        str(key): str(value)
        for key, value in sorted(track.tags.items(), key=lambda item: str(item[0]).casefold())
        if normalized_tag_key(str(key)) in {"itunesadvisory", "rtng", "advisory", "explicit"}
    }
    return {
        "release_classification_tags": classification_tags,
        "explicit_advisory_tags": advisory_tags,
        "release_id": track.release_id,
        "path": str(track.path),
        "file": track.path.name,
        "title": track.display_title,
        "artist": track.artist,
        "album": track.album,
        "duration_seconds": round(track.duration, 6),
        "identity_duration_seconds": round(_identity_track_duration(track), 6),
        "fingerprint_duration_seconds": round(track.fingerprint_duration, 6),
        "fingerprint_frames": len(track.fingerprint),
        "fingerprint_repaired": bool(track.fingerprint_repaired),
        "integrity_checked": bool(track.integrity_checked),
        "integrity_error": str(track.integrity_error),
        "fingerprint_incomplete": _chromaprint_fingerprint_incomplete(
            len(track.fingerprint), max(track.duration, track.fingerprint_duration)
        ) if track.fingerprint else False,
        "identity_title": identity_title(track.display_title),
        "base_title_identity": _base_title_identity(track.display_title),
        "content_qualifiers": sorted(content_qualifiers(track.display_title)),
        "version_descriptors": sorted(_version_descriptors(track.display_title)),
        "semantic_version_descriptors": sorted(_semantic_version_descriptors(track.display_title)),
        "featured_credit_signature": sorted(_featured_credit_signature(track.display_title)),
        "artist_signature": sorted(_artist_signature(track.artist)),
        "is_remix": track.is_remix,
        "is_live": track.is_live,
        "remix_feature_exception": track.remix_feature_exception,
        "explicit_state": track.explicit,
        "excluded_from_coverage": track.exclude_from_coverage,
        "excluded_by_pattern": track.excluded_by_pattern,
        "personal_keep_rule": track.personal_keep_rule,
        "explicit_category_exclusion": track.explicit_category_exclusion,
        "acoustic_policy_reconciled": track.acoustic_policy_reconciled,
        "virtual_from_cue": track.virtual_from_cue,
        "cue_path": str(track.cue_path) if track.cue_path else "",
        "cue_track_number": track.cue_track_number,
        "cue_start_seconds": round(track.cue_start_seconds, 6),
        "cue_end_seconds": round(track.cue_end_seconds, 6),
        "dynamic_lufs": track.dynamic_lufs,
        "dynamic_lra": track.dynamic_lra,
        "dynamic_true_peak_dbfs": track.dynamic_true_peak_dbfs,
        "dynamic_rms_dbfs": track.dynamic_rms_dbfs,
        "dynamic_crest_db": track.dynamic_crest_db,
        "dynamic_score": track.dynamic_score,
    }


def _candidate_semantic_profiles(
    tracks: List[Track], indices: List[int],
) -> Tuple[Dict[int, str], Dict[int, frozenset]]:
    """Cache version roots and semantic families once per audio track."""
    roots: Dict[int, str] = {}
    hard: Dict[int, frozenset] = {}
    for i in indices:
        root = _unique_recording_root_family(tracks[i])
        roots[i] = root
        hard[i] = frozenset() if root else frozenset(
            _hard_semantic_version_families(tracks[i])
        )
    return roots, hard


def _candidate_semantic_conflict(
    a: int, b: int, roots: Dict[int, str], hard: Dict[int, frozenset],
) -> bool:
    """Equivalent to _semantic_version_conflict for cached metadata."""
    ra, rb = roots[a], roots[b]
    if ra or rb:
        return ra != rb
    va, vb = hard[a], hard[b]
    return bool(va and vb and va.isdisjoint(vb))


def _fingerprint_identity_candidates(tracks: List[Track]) -> List[Track]:
    """Identify every readable file, independent of the retention policy.

    A track excluded by Remix/Live/Skip/Explicit>Clean remains useful evidence
    about recording identity, even when it must not satisfy wanted coverage.
    """
    return [track for track in tracks if not track.integrity_error]


def merge_equivalent_tracks(
    tracks: List[Track],
    progress_cb=None,
    comparison_log_path: Optional[Path] = None,
) -> Tuple[Dict[int, List[int]], List[str], List[Dict[str, object]]]:
    """Group acoustic matches automatically with a bounded candidate router.

    Fingerprints establish positive identity; a meaningful duration difference
    vetoes grouping and denotes a separate Version. Titles/tokens route pairs.
    """
    uf = UnionFind(len(tracks))
    for index, track in enumerate(tracks):
        track.comparison_index = index
        track.identity_duration_seconds = 0.0
    notes: List[str] = []
    reviews: List[Dict[str, object]] = []
    pcm_verdicts: Dict[Tuple[int, int], Dict[str, object]] = {}
    padding_verdicts: Dict[Tuple[int, int], Dict[str, object]] = {}

    eligible_indices = [
        i for i, track in enumerate(tracks)
        if not track.exclude_from_coverage
    ]
    # Identity is independent of retention: include all fingerprinted tracks.
    # The coverage optimizer still sees only tracks allowed by current policy.
    analysis_indices = [
        i for i, track in enumerate(tracks)
        if track.fingerprint
    ]
    analysis_index_set = set(analysis_indices)
    tokens: List[Set[int]] = [
        _fingerprint_tokens(track.fingerprint)
        if i in analysis_index_set
        else set()
        for i, track in enumerate(tracks)
    ]
    indexed = len(analysis_indices)
    total_possible = indexed * (indexed - 1) // 2
    candidate_route_started = time.monotonic()
    semantic_roots, semantic_hard = _candidate_semantic_profiles(
        tracks, analysis_indices,
    )

    token_tracks: Dict[int, List[int]] = defaultdict(list)
    if progress_cb:
        progress_cb("Indexing fingerprints...", 0, max(1, indexed))
    for done, i in enumerate(analysis_indices, 1):
        for token in tokens[i]:
            token_tracks[token].append(i)
        if progress_cb and (done % 25 == 0 or done == indexed):
            progress_cb("Indexing fingerprints...", done, max(1, indexed))

    token_df = {token: len(set(ids)) for token, ids in token_tracks.items()}
    common_cutoff = max(
        8,
        min(
            FP_CANDIDATE_COMMON_TOKEN_MAX_TRACKS,
            int(math.ceil(max(1, indexed) * FP_CANDIDATE_COMMON_TOKEN_MAX_FRACTION)),
        ),
    )
    token_weight = {
        token: math.log((indexed + 1.0) / (df + 1.0)) + 1.0
        for token, df in token_df.items()
    }
    track_weight_total = [0.0] * len(tracks)
    for i in analysis_indices:
        track_weight_total[i] = sum(token_weight.get(token, 0.0) for token in tokens[i])

    common_token_buckets_suppressed = sum(
        1 for df in token_df.values() if df > common_cutoff
    )
    common_token_pair_expansions_suppressed = sum(
        df * (df - 1) // 2
        for df in token_df.values()
        if df > common_cutoff
    )

    candidate_reasons: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
    candidate_stats: Dict[Tuple[int, int], Dict[str, object]] = {}
    funnel: Counter = Counter()
    # Duration-neighbor visitation is already implied by the fixed 45-second
    # gate in the far-rare route. Do not allocate ~846k rejected tuple keys.

    def pair_metrics(
        a: int, b: int,
        common: Optional[Set[int]] = None,
        remember: bool = True,
    ) -> Dict[str, object]:
        pair = (a, b) if a < b else (b, a)
        cached = candidate_stats.get(pair)
        if cached is not None:
            return cached
        if common is None:
            common = tokens[a] & tokens[b]
        shared = len(common)
        denom = max(1, min(len(tokens[a]), len(tokens[b])))
        containment = shared / denom
        weighted_shared = sum(token_weight.get(token, 0.0) for token in common)
        weighted_denom = max(
            1e-12,
            min(track_weight_total[a], track_weight_total[b]),
        )
        weighted_containment = weighted_shared / weighted_denom
        metrics = {
            "shared_token_buckets": shared,
            "token_containment": round(containment, 6),
            "weighted_token_containment": round(weighted_containment, 6),
            "duration_delta_seconds_diagnostic_only": round(
                abs(tracks[a].duration - tracks[b].duration),
                6,
            ),
        }
        if remember:
            candidate_stats[pair] = metrics
        return metrics

    minimum_route_shared = min(
        FP_CANDIDATE_STRONG_SHARED_TOKENS,
        FP_CANDIDATE_WEAK_SHARED_TOKENS,
        max(12, FP_CANDIDATE_WEAK_SHARED_TOKENS // 2),
    )

    def route_pair(a: int, b: int, allow_weak: bool) -> None:
        pair = (a, b) if a < b else (b, a)
        fp_a = tracks[pair[0]].fingerprint
        fp_b = tracks[pair[1]].fingerprint

        # Exact Chromaprint identity is stronger than title/version wording.
        # Metadata must never veto a byte-identical acoustic fingerprint.
        if fp_a and fp_a == fp_b:
            candidate_reasons[pair].add("exact_fingerprint")
            if _candidate_semantic_conflict(
                pair[0], pair[1], semantic_roots, semantic_hard
            ):
                funnel["exact_fingerprint_semantic_override"] += 1
            else:
                funnel["routed_exact_fingerprint"] += 1
            return

        # Metadata is untrusted. Never veto an audio candidate because one
        # release says Live, Remix, or another conflicting version descriptor.
        # Keep the disagreement only as a diagnostic after acoustic matching.
        common = tokens[pair[0]] & tokens[pair[1]]
        if len(common) < minimum_route_shared:
            funnel["token_evidence_rejected"] += 1
            funnel["fast_token_pairs_rejected"] += 1
            return
        metrics = pair_metrics(*pair, common=common, remember=False)
        shared = int(metrics["shared_token_buckets"])
        containment = float(metrics["token_containment"])
        weighted_containment = float(metrics["weighted_token_containment"])

        strong = bool(
            shared >= FP_CANDIDATE_STRONG_SHARED_TOKENS
            and containment >= FP_CANDIDATE_STRONG_CONTAINMENT_MIN
        )
        weighted = bool(
            shared >= max(12, FP_CANDIDATE_WEAK_SHARED_TOKENS // 2)
            and weighted_containment >= FP_CANDIDATE_WEIGHTED_CONTAINMENT_MIN
        )
        weak = bool(
            allow_weak
            and shared >= FP_CANDIDATE_WEAK_SHARED_TOKENS
            and containment >= FP_CANDIDATE_WEAK_CONTAINMENT_MIN
        )

        if strong:
            candidate_reasons[pair].add("fingerprint_tokens_strong")
            funnel["routed_strong"] += 1
        elif weighted:
            candidate_reasons[pair].add("fingerprint_tokens_weighted")
            funnel["routed_weighted"] += 1
        elif weak:
            candidate_reasons[pair].add("fingerprint_tokens_weak")
            funnel["routed_weak"] += 1
        else:
            funnel["token_evidence_rejected"] += 1
            return
        candidate_stats[pair] = metrics

    # Bounded duration-neighbour scan. Duration is routing only: every accepted
    # candidate still goes through the same acoustic identity function.
    ordered = sorted(
        analysis_indices,
        key=lambda i: (float(tracks[i].duration or 0.0), i),
    )
    if progress_cb:
        progress_cb("Finding audio candidates...", 0, max(1, len(ordered)))

    for pos, a in enumerate(ordered):
        da = float(tracks[a].duration or 0.0)
        for next_pos in range(pos + 1, len(ordered)):
            b = ordered[next_pos]
            db = float(tracks[b].duration or 0.0)
            delta = abs(db - da)
            if delta > FP_CANDIDATE_STRONG_DURATION_WINDOW:
                break
            funnel["duration_window_pairs_examined"] += 1
            route_pair(
                a,
                b,
                allow_weak=(delta <= FP_CANDIDATE_WEAK_DURATION_WINDOW),
            )
        if progress_cb and ((pos + 1) % 25 == 0 or pos + 1 == len(ordered)):
            progress_cb(
                "Finding audio candidates...",
                pos + 1,
                max(1, len(ordered)),
            )

    # Same-base-title tracks are always acoustically tested, regardless of
    # reported/tagged duration. Semantic-version conflicts still stay unique.
    title_index: Dict[str, List[int]] = defaultdict(list)
    for i in analysis_indices:
        key = _base_title_identity(tracks[i].display_title)
        if key:
            title_index[key].append(i)
    for ids in title_index.values():
        for a, b in itertools.combinations(sorted(set(ids)), 2):
            pair = (a, b)
            if pair not in candidate_reasons:
                funnel["same_title_safety_route"] += 1
            candidate_reasons[pair].add("same_base_title")
            pair_metrics(a, b)

    # Censorship masks defeat compact-title equality (Motherf***** versus
    # Motherfucker). Use the existing mask comparison only as a safety route,
    # including long silent prefixes and files without album/slot metadata.
    raw_title_index: Dict[str, List[int]] = defaultdict(list)
    masked_titles: Set[str] = set()
    for i in analysis_indices:
        title = tracks[i].display_title
        # A fully masked/empty title supplies no routing evidence.
        if not _base_title_identity(title):
            continue
        raw_title_index[title].append(i)
        if CENSOR_MASK_RE.search(title):
            masked_titles.add(title)
    for masked_title in sorted(masked_titles):
        for title, ids in raw_title_index.items():
            if not masked_title_compatible(masked_title, title):
                continue
            for a, b in itertools.product(raw_title_index[masked_title], ids):
                if a == b:
                    continue
                pair = (min(a, b), max(a, b))
                if pair not in candidate_reasons:
                    funnel["masked_title_safety_route"] += 1
                candidate_reasons[pair].add("masked_title")
                pair_metrics(*pair)

    # Same album + same track slot is a routing safety net only. It catches
    # provider naming differences (for example "ft." vs "with") that may defeat
    # title/token routing on short tracks. Chromaprint still decides identity.
    slot_index: Dict[Tuple[str, int], List[int]] = defaultdict(list)
    for i in analysis_indices:
        key = _album_track_slot_route_key(tracks[i])
        if key is not None:
            slot_index[key].append(i)
    for ids in slot_index.values():
        for a, b in itertools.combinations(sorted(set(ids)), 2):
            if tracks[a].release_id == tracks[b].release_id:
                continue
            pair = (a, b)
            if pair not in candidate_reasons:
                funnel["same_album_track_slot_safety_route"] += 1
            candidate_reasons[pair].add("same_album_track_slot")
            pair_metrics(a, b)

    # Exact fingerprint vectors are definitive candidate evidence even when bad
    # tags report nonsensical duration.
    exact_index: Dict[Tuple[int, ...], List[int]] = defaultdict(list)
    for i in analysis_indices:
        exact_index[tracks[i].fingerprint].append(i)
    for ids in exact_index.values():
        if len(ids) < 2:
            continue
        for a, b in itertools.combinations(sorted(ids), 2):
            pair = (a, b)
            already_exact = "exact_fingerprint" in candidate_reasons.get(pair, set())
            if not already_exact and _candidate_semantic_conflict(
                a, b, semantic_roots, semantic_hard
            ):
                funnel["exact_fingerprint_semantic_override"] += 1
            candidate_reasons[pair].add("exact_fingerprint")
            pair_metrics(a, b)

    # Very rare fingerprint tokens may rescue a genuine different-title pair
    # outside the 45-second routing window. Common buckets are intentionally not
    # expanded; this is the key guard against the old near-all-pairs explosion.
    far_weight: Dict[Tuple[int, int], float] = defaultdict(float)
    rare_bucket_count = 0
    rare_far_cutoff = max(
        4,
        min(
            FP_CANDIDATE_FAR_RARE_TOKEN_MAX_TRACKS,
            max(4, int(math.ceil(max(1, indexed) * 0.005))),
        ),
    )
    for token, ids in token_tracks.items():
        unique_ids = sorted(set(ids))
        if not (2 <= len(unique_ids) <= rare_far_cutoff):
            continue
        rare_bucket_count += 1
        weight = token_weight.get(token, 0.0)
        for a, b in itertools.combinations(unique_ids, 2):
            pair = (a, b)
            if pair in candidate_reasons:
                continue
            # This is the same condition as the former considered_pairs
            # membership: every visited duration-neighbor pair is inside
            # this strong window. It is O(1) without storing 846k tuples.
            if abs(tracks[a].duration - tracks[b].duration) <= FP_CANDIDATE_STRONG_DURATION_WINDOW:
                continue
            far_weight[pair] += weight

    for pair, _weight in far_weight.items():
        a, b = pair
        metrics = pair_metrics(a, b, remember=False)
        shared = int(metrics["shared_token_buckets"])
        containment = float(metrics["token_containment"])
        weighted_containment = float(metrics["weighted_token_containment"])
        if (
            shared >= FP_CANDIDATE_STRONG_SHARED_TOKENS
            and containment >= 0.20
            and weighted_containment >= 0.55
        ):
            candidate_reasons[pair].add("fingerprint_tokens_far_rare")
            candidate_stats[pair] = metrics
            funnel["routed_far_rare"] += 1
        else:
            funnel["far_rare_rejected"] += 1

    routed_candidate_count = len(candidate_reasons)
    prefilter_rejected = max(0, total_possible - routed_candidate_count)

    # Deterministic shadow validation samples pairs rejected by the router. It
    # never hides a discovered match: a sampled false negative is recovered into
    # the acoustic UnionFind and is called out explicitly in the log.
    shadow_pairs: List[Tuple[int, int]] = []
    shadow_seen: Set[Tuple[int, int]] = set()
    n = len(analysis_indices)
    state = 0x5EED221
    attempts = 0
    max_attempts = max(1000, FP_SHADOW_SAMPLE_SIZE * 80)
    while n >= 2 and len(shadow_pairs) < FP_SHADOW_SAMPLE_SIZE and attempts < max_attempts:
        attempts += 1
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        apos = state % n
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        bpos = state % n
        if apos == bpos:
            continue
        a = analysis_indices[min(apos, bpos)]
        b = analysis_indices[max(apos, bpos)]
        pair = (a, b) if a < b else (b, a)
        if pair in candidate_reasons or pair in shadow_seen:
            continue
        shadow_seen.add(pair)
        shadow_pairs.append(pair)
        candidate_reasons[pair].add("shadow_validation")
        pair_metrics(*pair)

    funnel["shadow_pairs"] = len(shadow_pairs)
    funnel["common_token_buckets_suppressed"] = common_token_buckets_suppressed
    funnel["common_token_pair_expansions_suppressed"] = common_token_pair_expansions_suppressed
    funnel["rare_token_buckets_used"] = rare_bucket_count
    funnel["possible_pairs_not_routed"] = prefilter_rejected

    def candidate_priority(pair: Tuple[int, int]) -> Tuple[object, ...]:
        reasons = candidate_reasons[pair]
        metrics = candidate_stats.get(pair, {})
        if "exact_fingerprint" in reasons:
            tier = 0
        elif "same_base_title" in reasons and "fingerprint_tokens_strong" in reasons:
            tier = 1
        elif "same_base_title" in reasons or "masked_title" in reasons:
            tier = 2
        elif "same_album_track_slot" in reasons:
            tier = 3
        elif "fingerprint_tokens_strong" in reasons:
            tier = 4
        elif "fingerprint_tokens_weighted" in reasons:
            tier = 5
        elif "fingerprint_tokens_far_rare" in reasons:
            tier = 6
        elif "fingerprint_tokens_weak" in reasons:
            tier = 7
        else:
            tier = 9
        return (
            tier,
            -float(metrics.get("weighted_token_containment", 0.0) or 0.0),
            -float(metrics.get("token_containment", 0.0) or 0.0),
            -int(metrics.get("shared_token_buckets", 0) or 0),
            pair[0],
            pair[1],
        )

    work_pairs = sorted(candidate_reasons, key=candidate_priority)
    total_work_pairs = len(work_pairs)
    routing_seconds = round(time.monotonic() - candidate_route_started, 3)
    funnel["semantic_profiles_cached"] = indexed
    funnel["rejected_pair_metrics_not_cached"] = funnel["token_evidence_rejected"]

    # Store individual acoustic verdicts until a deterministic, global duration
    # partition is selected. Completion order of parallel workers must not
    # determine whether an edition is retained.
    acoustic_edges: List[Tuple[int, int]] = []
    comparison_results: List[Tuple[int, int, int, bool, object]] = []
    log_handle = None
    log_counts: Counter = Counter()
    route_outcomes: Counter = Counter()
    duration_outcomes: Counter = Counter()
    processed_pair_count = 0
    detailed_pair_count = 0

    def duration_bin(delta: float) -> str:
        for limit in (1, 2, 3, 5, 7, 10, 15, 20, 30, 45, 60, 120):
            if delta < limit:
                return f"<{limit}s"
        return ">=120s"

    if comparison_log_path is not None:
        try:
            comparison_log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = comparison_log_path.open("w", encoding="utf-8", newline="\n")
            route_counts = Counter(
                reason
                for pair, reasons in candidate_reasons.items()
                if "shadow_validation" not in reasons
                for reason in reasons
            )
            eliminated = Counter()
            for track in tracks:
                if not track.exclude_from_coverage:
                    continue
                if track.excluded_by_pattern:
                    eliminated[f"pattern:{track.excluded_by_pattern}"] += 1
                elif track.is_remix:
                    eliminated["remix"] += 1
                elif track.is_live:
                    eliminated["live"] += 1
                else:
                    eliminated["other"] += 1

            header = {
                "record_type": "run",
                "logging_schema_version": 3,
                "app": APP_NAME,
                "version": APP_VERSION,
                "generated": datetime.now().isoformat(timespec="seconds"),
                "tracks_total": len(tracks),
                "tracks_eligible_for_analysis": len(eligible_indices),
                "tracks_with_fingerprints": indexed,
                "tracks_without_fingerprints": sum(not t.fingerprint for t in tracks),
                "excluded_tracks_with_fingerprints": sum(
                    t.exclude_from_coverage and bool(t.fingerprint) for t in tracks
                ),
                "tracks_eliminated_from_coverage": len(tracks) - len(eligible_indices),
                "track_elimination_reasons": dict(sorted(eliminated.items())),
                "featured_remix_exceptions": sum(
                    1 for track in tracks
                    if track.remix_feature_exception and not track.exclude_from_coverage
                ),
                "possible_pairs": total_possible,
                "candidate_pairs": routed_candidate_count,
                "candidate_routing_seconds": routing_seconds,
                "candidate_diagnostic_pairs_cached": len(candidate_stats),
                "shadow_validation_pairs": len(shadow_pairs),
                "prefilter_rejected_pairs": prefilter_rejected,
                "candidate_routes": dict(sorted(route_counts.items())),
                "candidate_funnel": dict(sorted(funnel.items())),
                "thresholds": {
                    "candidate_router": {
                        "strong_shared_token_min": FP_CANDIDATE_STRONG_SHARED_TOKENS,
                        "weak_shared_token_min": FP_CANDIDATE_WEAK_SHARED_TOKENS,
                        "strong_token_containment_min": FP_CANDIDATE_STRONG_CONTAINMENT_MIN,
                        "weak_token_containment_min": FP_CANDIDATE_WEAK_CONTAINMENT_MIN,
                        "weighted_token_containment_min": FP_CANDIDATE_WEIGHTED_CONTAINMENT_MIN,
                        "strong_duration_window_seconds": FP_CANDIDATE_STRONG_DURATION_WINDOW,
                        "weak_duration_window_seconds": FP_CANDIDATE_WEAK_DURATION_WINDOW,
                        "common_token_track_cutoff": common_cutoff,
                        "same_base_title_bypasses_duration": True,
                        "masked_title_bypasses_duration": True,
                        "metadata_can_veto_acoustic_candidates": False,
                        "excluded_audio_still_fingerprinted": True,
                        "same_album_track_slot_bypasses_duration": True,
                        "same_album_track_slot_uses_album_family": True,
                        "exact_fingerprint_bypasses_duration": True,
                        "duration_used_for_identity": True,
                        "duration_version_threshold_seconds": DURATION_VERSION_MAX_SAME_SECONDS,
                    },
                    "strict": {
                        "score_max": FP_AUTO_SCORE,
                        "good_fraction_min": FP_AUTO_GOOD_FRACTION,
                        "excellent_fraction_min": FP_AUTO_EXCELLENT_FRACTION,
                        "median_max": FP_AUTO_MEDIAN_MAX,
                        "p90_max": FP_AUTO_P90_MAX,
                        "overlap_min": FP_MIN_OVERLAP,
                    },
                    "mastering": {
                        "score_max": FP_MASTERING_SCORE,
                        "good_fraction_min": FP_MASTERING_GOOD_FRACTION,
                        "median_max": FP_MASTERING_MEDIAN_MAX,
                        "p90_max": FP_MASTERING_P90_MAX,
                        "overlap_min": FP_MASTERING_MIN_OVERLAP,
                    },
                    "high_overlap_mastering": {
                        "score_max": FP_HIGH_OVERLAP_SCORE,
                        "good_fraction_min": FP_HIGH_OVERLAP_GOOD_FRACTION,
                        "excellent_fraction_min": FP_HIGH_OVERLAP_EXCELLENT_FRACTION,
                        "median_max": FP_HIGH_OVERLAP_MEDIAN_MAX,
                        "p90_max": FP_HIGH_OVERLAP_P90_MAX,
                        "overlap_min": FP_HIGH_OVERLAP_MIN_OVERLAP,
                        "whole_recording_coverage_min": FP_HIGH_OVERLAP_MIN_COVERAGE,
                        "minimum_frames": FP_HIGH_OVERLAP_MIN_FRAMES,
                        "evidence": "2026-10-21 SLIDE pair + conservative multi-metric bounds; native audio regression pending",
                    },
                    "authoritative_fingerprint": {
                        "rule": "a passing strict, mastering or high-overlap mastering fingerprint comparison within the effective 8-second length bound is final",
                        "baseline_score_max": FP_MATCH_SCORE,
                        "high_overlap_score_max": FP_HIGH_OVERLAP_SCORE,
                        "calibration": "Baseline: 16 logged Watch the Throne CD/WEB comparisons; maximum 4.014241 rounded upward to 0.01",
                        "duration_difference_max_seconds": DURATION_VERSION_MAX_SAME_SECONDS,
                        "silent_padding_requires_native_rate_all_channel_verification": True,
                        "local_windows_can_veto": False,
                        "known_clean_explicit_tags_can_veto": False,
                        "unmatched_end_frames_can_veto": False,
                        "decoded_audio_can_veto": False,
                        "secondary_identity_checks_enabled": False,
                        "decoded_pcm_positive_confirmation_enabled": True,
                        "decoded_pcm_rescue_score_max": 6.5,
                        "decoded_pcm_confirmation_not_a_veto": True,
                    },
                },
            }
            log_handle.write(json.dumps(header, ensure_ascii=False) + "\n")
            for i, track in enumerate(tracks):
                log_handle.write(
                    json.dumps(
                        {
                            "record_type": "track",
                            "track_index": i,
                            **_comparison_track_log_data(track),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception as exc:
            notes.append(f"Comparison log unavailable: {exc}")
            log_handle = None

    def log_comparison(
        pair_index: int,
        a: int,
        b: int,
        audio_matched: bool,
        final_matched: bool,
        sim,
        group_duration_veto: bool = False,
        group_acoustic_veto: bool = False,
    ) -> None:
        nonlocal processed_pair_count, detailed_pair_count
        pair = (a, b)
        processed_pair_count += 1
        reasons = sorted(candidate_reasons.get(pair, set()))
        is_shadow = "shadow_validation" in reasons
        metrics = candidate_stats.get(pair) or pair_metrics(a, b)
        delta = float(metrics.get("duration_delta_seconds_diagnostic_only", 0.0) or 0.0)
        route_key = "+".join(reasons) or "unknown"
        outcome = "MATCH" if final_matched else "REJECT"
        route_outcomes[f"{route_key}|{outcome}"] += 1
        duration_outcomes[f"{duration_bin(delta)}|{outcome}"] += 1

        details = _comparison_decision_details(
            tracks[a].fingerprint,
            tracks[a].duration,
            tracks[b].fingerprint,
            tracks[b].duration,
            audio_matched,
            sim,
            pcm_verdicts.get((a,b)),
            _explicit_identity_disagreement(tracks[a],tracks[b]),
            padding_verdicts.get((a,b)),
            (_identity_track_duration(tracks[a]),_identity_track_duration(tracks[b])),
        )
        details["audio_match"] = bool(audio_matched)
        details["metadata_version_disagreement"] = _candidate_semantic_conflict(
            a, b, semantic_roots, semantic_hard
        )
        details["final_match"] = bool(final_matched)
        details["transitive_duration_version_conflict"] = bool(group_duration_veto)
        details["transitive_acoustic_conflict"] = bool(group_acoustic_veto)
        if group_duration_veto:
            details["rejection_reasons"].append(
                "transitive acoustic group would contain differently timed versions"
            )
            details["derived_final_match"] = False
            details["decision_consistent"] = not bool(final_matched)
        if group_acoustic_veto:
            details["rejection_reasons"].append(
                "transitive acoustic group conflicts with rejected pair evidence"
            )
            details["derived_final_match"] = False
            details["decision_consistent"] = not bool(final_matched)

        if is_shadow:
            log_counts["shadow_tested"] += 1
            if final_matched:
                log_counts["shadow_false_negative_recovered"] += 1
        elif final_matched:
            log_counts["matched"] += 1
            for route in details.get("accepted_by", []):
                log_counts[f"matched_{route}"] += 1
        else:
            log_counts["rejected_audio"] += 1
            if not details.get("similarity_available"):
                log_counts["rejected_no_similarity"] += 1
            elif details.get("duration_version_conflict") or group_duration_veto:
                log_counts["rejected_length_version"] += 1
            elif group_acoustic_veto:
                log_counts["rejected_transitive_acoustic_conflict"] += 1
            elif not details.get("identity_confirmed"):
                log_counts["rejected_unconfirmed_audio_identity"] += 1
            elif (details.get("strict_pass") or details.get("mastering_pass")
                  or details.get("high_overlap_mastering_pass")):
                log_counts["rejected_acoustic_content_gate"] += 1
            else:
                log_counts["rejected_thresholds"] += 1

        if log_handle is None:
            return

        near_threshold = _manual_review_audio_candidate(sim)
        sampled_reject = (
            not final_matched
            and ((a * 1000003 + b * 9176) % FP_LOG_REJECT_SAMPLE_MODULUS == 0)
        )
        # A different-length pair with no acoustic pass is only counted in the
        # summary; logging each one made 94% of a 300 MB log.
        detailed = bool(
            final_matched
            or is_shadow and final_matched
            or details.get("content_gate_triggered")
            or (details.get("duration_version_conflict")
                and (details.get("strict_pass") or details.get("mastering_pass")
                     or details.get("high_overlap_mastering_pass")))
            or group_duration_veto
            or group_acoustic_veto
            or near_threshold
            or sampled_reject
            or bool(pcm_verdicts.get(pair))
            or bool(padding_verdicts.get(pair))
        )
        if not detailed:
            return

        detailed_pair_count += 1
        row = {
            "record_type": "comparison",
            "pair_index": pair_index,
            "pair_total": total_work_pairs,
            "track_a_index": a,
            "track_b_index": b,
            "candidate": {
                "reasons": reasons,
                **metrics,
            },
            "decision": outcome,
            "near_threshold": bool(near_threshold),
            "sampled_reject": bool(sampled_reject),
            "details": details,
        }
        log_handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def handle_result(done: int, a: int, b: int, audio_matched: bool, sim) -> None:
        # The worker's acoustic verdict is independent of previous grouping.
        # The entire grouping is resolved after all workers have completed.
        comparison_results.append((done, a, b, audio_matched, sim))

    if total_work_pairs:
        workers = min(total_work_pairs, _compare_workers())
        base_label = f"Comparing audio ({workers} workers)"
        if progress_cb:
            progress_cb(base_label + "...", 0, total_work_pairs)

        track_data = [(t.fingerprint, t.duration) for t in tracks]
        completed = bytearray(total_work_pairs)
        done_count = 0
        compare_started = time.monotonic()
        batch_size = COMPARE_BATCH_SIZE
        max_pending = max(1, workers * COMPARE_PENDING_BATCHES_PER_WORKER)

        def report_compare_progress(force: bool = False) -> None:
            if not progress_cb:
                return
            elapsed = max(0.001, time.monotonic() - compare_started)
            rate = done_count / elapsed
            remaining = max(0, total_work_pairs - done_count)
            if rate > 0:
                eta_seconds = int(remaining / rate)
                hours, rem = divmod(eta_seconds, 3600)
                minutes, seconds = divmod(rem, 60)
                eta = f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
                label = f"{base_label} | {rate:,.0f}/s | ETA {eta}"
            else:
                label = base_label
            if force or done_count == total_work_pairs or done_count % max(25, batch_size) == 0:
                progress_cb(label, done_count, total_work_pairs)

        pair_iter = iter(enumerate(work_pairs, 1))

        def next_compare_batch() -> List[Tuple[int, int, int]]:
            nonlocal done_count
            batch: List[Tuple[int, int, int]] = []
            while len(batch) < batch_size:
                try:
                    pair_index, (a, b) = next(pair_iter)
                except StopIteration:
                    break

                fp_a = tracks[a].fingerprint
                fp_b = tracks[b].fingerprint
                if fp_a and fp_a == fp_b:
                    sim = (0.0, 1.0, 1.0, 0, 1.0, 0.0, 0)
                    trusted, _ = _fingerprint_candidate_match_values(
                        fp_a, tracks[a].duration, fp_b, tracks[b].duration, sim)
                    handle_result(pair_index, a, b, trusted, sim)
                    completed[pair_index - 1] = 1
                    done_count += 1
                    log_counts["fast_exact_fingerprint"] += 1
                    continue

                batch.append((pair_index, a, b))
            return batch

        parallel_failed = None
        try:
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_init_compare_worker,
                initargs=(track_data,),
            ) as ex:
                pending = {}
                while len(pending) < max_pending:
                    batch = next_compare_batch()
                    if not batch:
                        break
                    pending[ex.submit(_compare_pair_batch_worker, batch)] = batch

                while pending:
                    finished, _not_done = wait(tuple(pending), return_when=FIRST_COMPLETED)
                    for fut in finished:
                        pending.pop(fut, None)
                        for pair_index, a, b, audio_matched, sim in fut.result():
                            handle_result(pair_index, a, b, audio_matched, sim)
                            completed[pair_index - 1] = 1
                            done_count += 1
                        report_compare_progress(force=True)

                    while len(pending) < max_pending:
                        batch = next_compare_batch()
                        if not batch:
                            break
                        pending[ex.submit(_compare_pair_batch_worker, batch)] = batch
        except Exception as exc:
            parallel_failed = exc

        if parallel_failed is not None:
            notes.append(f"Parallel comparison unavailable; serial fallback: {parallel_failed}")
            base_label = "Comparing audio (serial fallback)"
            for pair_index, (a, b) in enumerate(work_pairs, 1):
                if completed[pair_index - 1]:
                    continue
                fp_a = tracks[a].fingerprint
                fp_b = tracks[b].fingerprint
                if fp_a and fp_a == fp_b:
                    sim = (0.0, 1.0, 1.0, 0, 1.0, 0.0, 0)
                    trusted, _ = _fingerprint_candidate_match_values(
                        fp_a, tracks[a].duration, fp_b, tracks[b].duration, sim)
                    handle_result(pair_index, a, b, trusted, sim)
                    log_counts["fast_exact_fingerprint"] += 1
                else:
                    audio_matched, sim = fingerprint_auto_match(tracks[a], tracks[b])
                    handle_result(pair_index, a, b, audio_matched, sim)
                completed[pair_index - 1] = 1
                done_count += 1
                if done_count % 25 == 0 or done_count == total_work_pairs:
                    report_compare_progress(force=True)

        report_compare_progress(force=True)
    elif progress_cb:
        progress_cb("Comparing audio...", 1, 1)

    # Passing fingerprints remain authoritative. Borderline near-complete
    # comparisons may additionally be confirmed by independent decoded PCM.
    # Neither PCM failure nor metadata can veto an existing accepted match.
    verification_started = time.monotonic()
    with _PCMIdentityVerifier() as verifier:
        padding_candidates = []
        for _pair_index,a,b,_matched,sim in sorted(comparison_results):
            if (not _duration_version_conflict(tracks[a].duration,tracks[b].duration)
                    or not _fingerprint_profile_identity(
                        sim, fingerprint_items=min(len(tracks[a].fingerprint),
                                                   len(tracks[b].fingerprint)),
                        acoustic_coverage=_fingerprint_acoustic_coverage(
                            tracks[a].fingerprint, tracks[b].fingerprint, sim))):
                continue
            if not _unmatched_fingerprint_is_silence(
                    tracks[a].fingerprint,tracks[b].fingerprint,int(sim[3])):
                continue
            padding_candidates.append((a,b,sim))

        def measure_padding_pair(candidate):
            # Each pair decodes into its own temporary folder, so pairs can run
            # at the same time; FFmpeg decoding, not Python, dominates the time.
            a,b,sim = candidate
            with _PCMIdentityVerifier() as pair_verifier:
                return pair_verifier.verify_padding(tracks[a],tracks[b],sim)

        if padding_candidates:
            padding_label = "Measuring silent boundary padding..."
            if progress_cb:
                progress_cb(padding_label,0,len(padding_candidates))
            with ThreadPoolExecutor(max_workers=min(8,max(2,_logical_cpu_count()))) as padding_pool:
                padding_futures = {padding_pool.submit(measure_padding_pair,candidate):candidate
                                   for candidate in padding_candidates}
                for finished_count,future in enumerate(as_completed(padding_futures),1):
                    a,b,_sim = padding_futures[future]
                    padding_verdicts[(a,b)] = future.result()
                    if progress_cb:
                        progress_cb(padding_label,finished_count,len(padding_candidates))
        for a,b,_sim in padding_candidates:
            verdict = padding_verdicts[(a,b)]
            effective = verdict.get("effective_durations_seconds")
            if verdict.get("passed") and isinstance(effective,(list,tuple)) and len(effective)==2:
                valid = all(math.isfinite(float(value)) and 0 < float(value)
                            <= track.duration + max(.5,track.duration*.001)
                            for track,value in zip((tracks[a],tracks[b]),effective))
                if valid:
                    for track,value in zip((tracks[a],tracks[b]),effective):
                        track.identity_duration_seconds = min(_identity_track_duration(track),float(value))

        # Only previously rejected, very-near full-length fingerprint pairs
        # enter the more expensive decoded positive-confirmation path.
        for _pair_index, a, b, _matched, sim in sorted(comparison_results):
            if _matched or not _fingerprint_pcm_rescue_candidate(
                    tracks[a].fingerprint, _identity_track_duration(tracks[a]),
                    tracks[b].fingerprint, _identity_track_duration(tracks[b]), sim):
                continue
            if progress_cb:
                progress_cb("Confirming alternate masterings...", len(pcm_verdicts), 0)
            pcm_verdicts[(a, b)] = verifier.verify_mastering(tracks[a], tracks[b], sim)
            if pcm_verdicts[(a, b)]["passed"]:
                notes.append(
                    f"DECODED MASTERING MATCH: {tracks[a].path.name} <-> "
                    f"{tracks[b].path.name}; independent waveform verification"
                )
    comparison_results = [
        (pair_index,a,b,_fingerprint_candidate_match_values(
            tracks[a].fingerprint,_identity_track_duration(tracks[a]),
            tracks[b].fingerprint,_identity_track_duration(tracks[b]),sim)[0]
            or bool(pcm_verdicts.get((a,b), {}).get("passed")),sim)
        for pair_index,a,b,_matched,sim in comparison_results
    ]
    verification_seconds = time.monotonic()-verification_started
    acoustic_edges = [(a,b) for _,a,b,matched,sim in comparison_results
        if matched and not _duration_version_conflict(_identity_track_duration(tracks[a]),_identity_track_duration(tracks[b]))]

    # Resolve overlapping 8-second windows using fingerprint-match links.
    # Worker completion order must not decide which release is retained.
    identity_members = sorted(set(analysis_indices) | set(eligible_indices))
    # Successful fingerprint links are final. Negative pairwise similarity
    # cannot veto an accepted link through another copy. Duration coherence
    # remains the previously agreed protection against >8-second versions.
    forbidden_pairs: Set[Tuple[int, int]] = set()
    authoritative_edges = set(acoustic_edges)
    uf = _coherent_duration_audio_groups(
        tracks,identity_members,acoustic_edges,forbidden_pairs,authoritative_edges)
    resolved_members: Dict[int,List[int]] = defaultdict(list)
    for index in identity_members:
        resolved_members[uf.find(index)].append(index)
    for pair_index, a, b, audio_matched, sim in sorted(comparison_results):
        length_or_version_conflict = (
            _duration_version_conflict(_identity_track_duration(tracks[a]),_identity_track_duration(tracks[b]))
        )
        accepted = bool(
            audio_matched and not length_or_version_conflict
            and uf.find(a) == uf.find(b)
        )
        grouping_veto = bool(
            audio_matched and not length_or_version_conflict and not accepted
        )
        combined_durations = [_identity_track_duration(tracks[index]) for index in
            resolved_members[uf.find(a)]+resolved_members[uf.find(b)]
            if math.isfinite(_identity_track_duration(tracks[index])) and _identity_track_duration(tracks[index])>0]
        duration_group_veto = bool(grouping_veto and combined_durations
            and max(combined_durations)-min(combined_durations)>DURATION_VERSION_MAX_SAME_SECONDS+1e-7)
        acoustic_group_veto = grouping_veto and not duration_group_veto
        log_comparison(
            pair_index, a, b, audio_matched, accepted, sim, duration_group_veto,acoustic_group_veto
        )
        if accepted and sim and "shadow_validation" not in candidate_reasons.get((a, b), set()):
            score, good, overlap, shift, excellent, median, p90 = sim
            notes.append(
                f"AUDIO MATCH: {tracks[a].path.name} <-> {tracks[b].path.name}; "
                f"score={score:.2f}, good={good:.0%}, excellent={excellent:.0%}, "
                f"overlap={overlap:.0%}, median={median:.1f}, p90={p90}, shift={shift}"
            )
    # Identify the final grouping method in the same original comparison log.
    if log_handle is not None:
        log_handle.write(json.dumps({
            "record_type": "grouping_policy",
            "name": "deterministic-duration-bounded-fingerprint-v4",
            "duration_version_threshold_seconds": DURATION_VERSION_MAX_SAME_SECONDS,
            "silent_padding_requires_full_band_decoded_verification": True,
            "verified_padding_pairs": sum(bool(v.get("passed")) for v in padding_verdicts.values()),
            "positive_acoustic_edges": len(acoustic_edges),
            "authoritative_fingerprint_edges": len(authoritative_edges),
            "successful_fingerprint_links_are_final": True,
            "rejected_pairs_cannot_share_group": False,
            "rejected_pairs": len(forbidden_pairs),
            "worker_completion_order_affects_groups": False,
            "titles_or_duration_alone_create_matches": False,
        }, ensure_ascii=False) + "\n")

    roots: Dict[int, List[int]] = {}
    # Wanted tracks without fingerprints remain conservative singletons.
    # Excluded but fingerprinted tracks also receive acoustic group IDs, so
    # Release Map / recording-wide Ignore can identify matching editions.
    # They NEVER become wanted obligations or eligible optimizer providers.
    for i in identity_members:
        roots.setdefault(uf.find(i), []).append(i)
    remap = {root: gid for gid, root in enumerate(sorted(roots))}
    groups: Dict[int, List[int]] = {}
    for root, ids in roots.items():
        gid = remap[root]
        for i in ids:
            tracks[i].group_id = gid
        wanted = [i for i in ids if not tracks[i].exclude_from_coverage]
        if wanted:
            groups[gid] = wanted

    # Default Live/Remix wording cannot make a verified CD copy ineligible
    # while the very same recording is allowed under another edition's tags.
    # Explicit saved classifications, pattern skips and advisory preference
    # remain authoritative inclusion decisions. Saved recording Ignore is
    # applied later to every acoustic member, including any restored copy.
    for root, ids in roots.items():
        if not any(not tracks[i].exclude_from_coverage for i in ids):
            continue
        for i in ids:
            track = tracks[i]
            if (track.exclude_from_coverage and (track.is_live or track.is_remix)
                    and not track.excluded_by_pattern and not track.explicit_category_exclusion
                    and not track.manual_skip_rule):
                track.exclude_from_coverage = False
                track.base_excluded_from_coverage = False
                track.acoustic_policy_reconciled = True

    # Restoring an automatically mislabeled explicit edition can introduce an
    # eligible counterpart which was absent from the pre-comparison policy pass.
    _apply_explicit_over_clean_tracks(tracks)
    for track in tracks:
        if track.excluded_by_pattern == "Explicit>Clean":
            track.base_excluded_from_coverage = True
    for root, ids in roots.items():
        wanted = [i for i in ids if not tracks[i].exclude_from_coverage]
        if wanted:
            groups[remap[root]] = wanted
        else:
            groups.pop(remap[root],None)

    version_substitutions = _assign_replaceable_version_coverage(
        tracks, comparison_results
    )
    if log_handle is not None:
        for evidence in version_substitutions:
            log_handle.write(json.dumps({
                "record_type": "replaceable_version_coverage",
                **evidence,
            }, ensure_ascii=False) + "\n")
        try:
            summary = {
                "record_type": "summary",
                "logging_schema_version": 3,
                "generated": datetime.now().isoformat(timespec="seconds"),
                "possible_pairs": total_possible,
                "candidate_pairs": routed_candidate_count,
                "candidate_routing_seconds": routing_seconds,
                "candidate_diagnostic_pairs_cached": len(candidate_stats),
                "shadow_validation_pairs": len(shadow_pairs),
                "prefilter_rejected_pairs": prefilter_rejected,
                "work_pairs": total_work_pairs,
                "comparisons_evaluated_or_skipped": processed_pair_count,
                "detailed_comparison_rows": detailed_pair_count,
                "recording_groups": len(groups),
                "replaceable_version_substitutions": len(version_substitutions),
                "distinct_versions_mandatory": True,
                "identity_verification": {
                    "padding_candidates": len(padding_verdicts),
                    "verified_silent_padding": sum(bool(v.get("passed")) for v in padding_verdicts.values()),
                    "decoded_candidates": len(pcm_verdicts),
                    "decoded_matches": sum(bool(v["passed"]) for v in pcm_verdicts.values()),
                    "unavailable": sum(str(v.get("reason", "")).startswith("Acoustic confirmation unavailable")
                                       for v in pcm_verdicts.values()),
                    "seconds": round(verification_seconds,3),
                    "secondary_identity_checks_enabled": False,
                    "decoded_pcm_positive_confirmation_enabled": True,
                },
                "manual_review_pairs": 0,
                "counts": dict(sorted(log_counts.items())),
                "candidate_funnel": dict(sorted(funnel.items())),
                "route_outcomes": dict(sorted(route_outcomes.items())),
                "duration_outcomes": dict(sorted(duration_outcomes.items())),
            }
            log_handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
            log_handle.close()
            notes.append(f"COMPARISON LOG: {comparison_log_path}")
        except Exception as exc:
            notes.append(f"Comparison log finalization error: {exc}")
            try:
                log_handle.close()
            except Exception:
                pass

    return groups, notes, reviews

def apply_manual_review_merges(
    tracks: List[Track],
    groups: Dict[int, List[int]],
    reviews: List[Dict[str, object]],
    accepted_keys: Set[str],
) -> Dict[int, List[int]]:
    """Apply reviewed pairs without ever collapsing differently timed Versions."""
    uf = UnionFind(len(tracks))
    bounds = [
        (float(track.duration), float(track.duration))
        if float(track.duration or 0) > 0 else (math.inf, -math.inf)
        for track in tracks
    ]
    active_indices: Set[int] = set()

    for ids in groups.values():
        clean_ids = [
            int(i) for i in ids
            if 0 <= int(i) < len(tracks)
            and not tracks[int(i)].exclude_from_coverage
        ]
        if not clean_ids:
            continue
        active_indices.update(clean_ids)
        root = clean_ids[0]
        for other in clean_ids[1:]:
            _duration_group_union(uf, bounds, root, other)

    for row in reviews:
        key = str(row.get("key", ""))
        if key not in accepted_keys:
            continue
        try:
            a = int(row.get("track_a_index"))
            b = int(row.get("track_b_index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= a < len(tracks) and 0 <= b < len(tracks)):
            continue
        if tracks[a].exclude_from_coverage or tracks[b].exclude_from_coverage:
            continue
        active_indices.add(a)
        active_indices.add(b)
        _duration_group_union(uf, bounds, a, b)

    # Active singleton tracks must remain represented too.
    for i, track in enumerate(tracks):
        if not track.exclude_from_coverage and track.group_id >= 0:
            active_indices.add(i)

    roots: Dict[int, List[int]] = defaultdict(list)
    for i in sorted(active_indices):
        roots[uf.find(i)].append(i)

    rebuilt: Dict[int, List[int]] = {}
    for gid, root in enumerate(sorted(roots)):
        ids = roots[root]
        rebuilt[gid] = ids
        for i in ids:
            tracks[i].group_id = gid

    return rebuilt


def release_explicit_state(rel: Release) -> str:
    states = {t.explicit for t in rel.tracks}
    if "explicit" in states:
        return "explicit"
    if states == {"clean"}:
        return "clean"
    if "clean" in states and "unknown" not in states:
        return "clean"
    return "unknown"


def finalize_release_metadata(releases: List[Release]) -> None:
    for rel in releases:
        first_tags = _release_representative_type_tags(rel.tracks)
        album_tag = rel.tracks[0].album if rel.tracks else ""
        if album_tag:
            rel.title = album_tag
        rel.release_type, rel.type_source = infer_release_type(
            rel.title,
            rel.path.name,
            rel.track_count,
            first_tags,
            sum(max(0.0, float(track.duration or 0.0)) for track in rel.tracks),
            [track.artist for track in rel.tracks],
            _discography_artist_from_release(rel),
        )
        rel.family = album_family(rel.title)
        rel.explicit = release_explicit_state(rel)

        # Prefer explicit medium metadata when present, but CUE + rip LOG is
        # authoritative enough to classify an existing lossless rip as CD.
        medium_tag = tag_lookup(first_tags, "media", "medium", "format").strip()
        medium_norm = normalize_title(medium_tag)
        if rel.has_cue and rel.has_rip_log:
            rel.source_medium = "CD"
            rel.source_quality = max(rel.source_quality, 100)
        elif rel.has_rip_log:
            rel.source_medium = "CD"
            rel.source_quality = max(rel.source_quality, 95)
        elif "cd" in medium_norm and "digital" not in medium_norm:
            rel.source_medium = medium_tag or "CD"
            rel.source_quality = max(rel.source_quality, 95)
        elif "digital" in medium_norm or "web" in medium_norm:
            rel.source_medium = medium_tag or "WEB"
            rel.source_quality = min(rel.source_quality, 50) if rel.source_quality else 40
        elif rel.has_audiochecker:
            rel.source_medium = "WEB"
        elif rel.has_cue:
            rel.source_medium = "CD/CUE"
        else:
            rel.source_medium = "WEB/Unknown"


def source_rank(rel: Release) -> int:
    """Rank source medium using structural evidence first.

    A CUE plus any real rip LOG (everything except audiochecker.log) is
    authoritative CD evidence for this project.
    """
    if rel.has_cue and rel.has_rip_log:
        return 3
    medium = normalize_title(rel.source_medium)
    if "cd" in medium and "web" not in medium and "digital" not in medium:
        return 2
    return 1


def score_cd_rip_logs(releases: List[Release], progress_cb, errors: List[str]) -> None:
    """Score EAC/XLD rip logs with hey-bro-check-log.

    Unrecognized logs are kept neutral rather than treated as bad rips. A release
    receives a usable quality key only when every non-AudioChecker .log belonging
    to that release was recognized by the upstream scorer.
    """
    jobs = [(rel, path) for rel in releases for path in rel.rip_log_paths]
    if not jobs:
        return

    score_log = ensure_heybrochecklog()
    progress_cb("Scoring CD rip logs...", 0, len(jobs))

    for index, (rel, path) in enumerate(jobs, 1):
        try:
            result = score_log(path)
            unrecognized = result.get("unrecognized")
            if unrecognized:
                message = str(unrecognized)
                rel.rip_log_unrecognized.append(f"{path.name}: {message}")
                errors.append(f"Rip log unrecognized: {path}: {message}")
            else:
                try:
                    score = int(result.get("score"))
                except (TypeError, ValueError):
                    raise RuntimeError("log checker returned no numeric score")
                rel.rip_log_scores.append(score)
                rel.rip_log_rippers.append(str(result.get("ripper") or ""))
                if bool(result.get("flagged")):
                    rel.rip_log_flagged += 1
        except Exception as exc:
            message = str(exc)
            rel.rip_log_unrecognized.append(f"{path.name}: {message}")
            errors.append(f"Rip log scoring error: {path}: {message}")

        progress_cb("Scoring CD rip logs...", index, len(jobs))


def cd_rip_log_quality_key(rel: Release) -> Optional[Tuple[int, float, int]]:
    """Comparable hey-bro-check-log quality for a fully scored CD rip.

    Higher is better. The worst disc score comes first so one bad disc cannot be
    hidden by several perfect discs; average score breaks ties, then an unflagged
    set wins over an otherwise equal flagged one.
    """
    if source_rank(rel) < 2:
        return None
    if not rel.rip_log_paths:
        return None
    if len(rel.rip_log_scores) != len(rel.rip_log_paths):
        return None

    scores = rel.rip_log_scores
    return (
        min(scores),
        sum(scores) / len(scores),
        -rel.rip_log_flagged,
    )


def cd_rip_log_quality_text(rel: Release) -> str:
    key = cd_rip_log_quality_key(rel)
    if key is None:
        if rel.rip_log_paths:
            return f"unavailable ({len(rel.rip_log_scores)}/{len(rel.rip_log_paths)} log(s) recognized)"
        return "not available"
    minimum, average, _flagged = key
    flagged = f", flagged: {rel.rip_log_flagged}" if rel.rip_log_flagged else ""
    rippers = sorted({r for r in rel.rip_log_rippers if r})
    ripper_text = f", {'/'.join(rippers)}" if rippers else ""
    return (
        f"min {minimum}/100, avg {average:.1f}/100 "
        f"({len(rel.rip_log_scores)}/{len(rel.rip_log_paths)} log(s){ripper_text}{flagged})"
    )


def cd_rip_quality_key(rel: Release) -> Optional[Tuple[int, int, float, int]]:
    """hey-bro-check-log quality only.  is not used."""
    log_key = cd_rip_log_quality_key(rel)
    if log_key is None:
        return None
    log_min, log_avg, log_flagged = log_key
    return (
        1 if log_min >= CD_RIP_LOG_ACCEPTABLE_MIN else 0,
        int(log_min),
        float(log_avg),
        int(log_flagged),
    )


def cd_rip_quality_class(rel: Release) -> int:
    """0=no comparable log, 1=below 80, 2=80 or higher."""
    key = cd_rip_quality_key(rel)
    if key is None:
        return 0
    return 2 if key[0] else 1


def _same_release_exact_cd_content(a: Release, b: Release) -> bool:
    """Strict identity gate for comparing CD rip log quality.

    The log score never proves duplicates. Audio groups, order, release identity,
    type, source class, and track counts must already prove the two releases are
    otherwise interchangeable.
    """
    if source_rank(a) < 2 or source_rank(b) < 2:
        return False
    if source_rank(a) != source_rank(b):
        return False
    if a.release_type != b.release_type:
        return False
    if a.included_track_count != b.included_track_count or a.track_count != b.track_count:
        return False

    if a.release_type == "album":
        if not a.family or not b.family or a.family != b.family:
            return False
    elif normalize_title(a.title) != normalize_title(b.title):
        return False

    seq_a = _included_group_sequence(a)
    seq_b = _included_group_sequence(b)
    if not seq_a or seq_a != seq_b:
        return False
    return _included_group_counter(a) == _included_group_counter(b)


def prefer_better_cd_rips(releases: List[Release], selected: Set[int]) -> Set[int]:
    """Among exact-equivalent CD rips, keep the strongest verified/quality copy."""
    selected = set(selected)

    changed = True
    while changed:
        changed = False
        for current in [r for r in releases if r.rid in selected]:
            current_quality = cd_rip_quality_key(current)
            if current_quality is None:
                continue

            better = [
                candidate for candidate in releases
                if candidate.rid != current.rid
                and _same_release_exact_cd_content(current, candidate)
                and cd_rip_quality_key(candidate) is not None
                and cd_rip_quality_key(candidate) > current_quality
            ]
            if not better:
                continue

            best = max(
                better,
                key=lambda r: (
                    cd_rip_quality_key(r),
                    1 if r.root_kind == "existing" else 0,
                    -r.rid,
                ),
            )
            selected.discard(current.rid)
            selected.add(best.rid)
            changed = True
            break

    selected_rels = [r for r in releases if r.rid in selected]
    for a, b in itertools.combinations(selected_rels, 2):
        if not _same_release_exact_cd_content(a, b):
            continue
        qa = cd_rip_quality_key(a)
        qb = cd_rip_quality_key(b)
        if qa is None or qb is None or qa == qb:
            continue
        if qa > qb:
            selected.discard(b.rid)
        else:
            selected.discard(a.rid)

    return selected


def _dynamic_range_cache_path() -> Path:
    return _cache_dir() / "dynamic-range-v1.json"


def _dynamic_range_cache_key(track: Track) -> str:
    try:
        st = track.path.stat()
        size = int(st.st_size)
        mtime_ns = int(st.st_mtime_ns)
    except OSError:
        size = int(track.file_size or 0)
        mtime_ns = 0
    payload = "|".join(
        [
            str(track.path.resolve()),
            str(size),
            str(mtime_ns),
            f"{float(track.cue_start_seconds):.6f}",
            f"{float(track.cue_end_seconds):.6f}",
            str(int(track.cue_track_number or 0)),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _load_dynamic_range_cache() -> Dict[str, Dict[str, object]]:
    path = _dynamic_range_cache_path()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                isinstance(data, dict)
                and int(data.get("version", 0) or 0) == DYNAMIC_RANGE_CACHE_VERSION
                and isinstance(data.get("entries"), dict)
            ):
                return {
                    str(k): dict(v)
                    for k, v in data["entries"].items()
                    if isinstance(v, dict)
                }
    except Exception:
        pass
    return {}


def _save_dynamic_range_cache(entries: Dict[str, Dict[str, object]]) -> None:
    # Keep the cache bounded while preserving the newest insertion order.
    if len(entries) > 200000:
        entries = dict(list(entries.items())[-200000:])
    _atomic_write_json(
        _dynamic_range_cache_path(),
        {"version": DYNAMIC_RANGE_CACHE_VERSION, "entries": entries},
    )


def _last_float(pattern: str, text: str) -> Optional[float]:
    matches = re.findall(pattern, text, re.I | re.M)
    if not matches:
        return None
    try:
        value = float(matches[-1])
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _measure_track_dynamic_range(ffmpeg: str, track: Track) -> Dict[str, object]:
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-loglevel", "info"]
    if track.virtual_from_cue and track.cue_start_seconds > 0:
        cmd += ["-ss", f"{max(0.0, track.cue_start_seconds):.6f}"]
    cmd += ["-i", str(track.path)]
    if track.virtual_from_cue and track.duration > 0:
        cmd += ["-t", f"{track.duration:.6f}"]
    cmd += [
        "-map", "0:a:0",
        "-vn",
        "-af", "ebur128=peak=true,astats=metadata=0:reset=0",
        "-f", "null",
        os.devnull,
    ]
    cp = run_hidden(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
        timeout=900,
    )
    output = (cp.stdout or "") + "\n" + (cp.stderr or "")
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or "FFmpeg dynamics analysis failed")

    lufs = _last_float(r"\bI:\s*(-?\d+(?:\.\d+)?)\s+LUFS", output)
    lra = _last_float(r"\bLRA:\s*(-?\d+(?:\.\d+)?)\s+LU", output)
    true_peak = _last_float(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", output)
    rms = _last_float(r"RMS level dB:\s*(-?\d+(?:\.\d+)?)", output)
    crest_ratio = _last_float(r"Crest factor:\s*(\d+(?:\.\d+)?)", output)

    crest_db = None
    if true_peak is not None and rms is not None:
        crest_db = true_peak - rms
    elif crest_ratio is not None and crest_ratio > 0:
        crest_db = 20.0 * math.log10(crest_ratio)

    score = None
    if crest_db is not None:
        score = crest_db + 0.35 * max(0.0, lra or 0.0)

    return {
        "lufs": lufs,
        "lra": lra,
        "true_peak_dbfs": true_peak,
        "rms_dbfs": rms,
        "crest_db": crest_db,
        "score": score,
    }


def _apply_dynamic_metrics(track: Track, metrics: Dict[str, object]) -> None:
    def value(name: str) -> Optional[float]:
        raw = metrics.get(name)
        try:
            number = float(raw)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None

    track.dynamic_lufs = value("lufs")
    track.dynamic_lra = value("lra")
    track.dynamic_true_peak_dbfs = value("true_peak_dbfs")
    track.dynamic_rms_dbfs = value("rms_dbfs")
    track.dynamic_crest_db = value("crest_db")
    track.dynamic_score = value("score")


def _median_track_metric(rel: Release, attr: str) -> Optional[float]:
    values = [
        float(value)
        for track in rel.tracks
        if not track.exclude_from_coverage
        and track.group_id >= 0
        and (value := getattr(track, attr, None)) is not None
        and math.isfinite(float(value))
    ]
    return float(statistics.median(values)) if values else None


def release_dynamic_summary(rel: Release) -> Dict[str, object]:
    scores = [
        float(t.dynamic_score)
        for t in rel.tracks
        if not t.exclude_from_coverage
        and t.group_id >= 0
        and t.dynamic_score is not None
        and math.isfinite(float(t.dynamic_score))
    ]
    return {
        "count": len(scores),
        "score": float(statistics.median(scores)) if scores else None,
        "lufs": _median_track_metric(rel, "dynamic_lufs"),
        "lra": _median_track_metric(rel, "dynamic_lra"),
        "true_peak_dbfs": _median_track_metric(rel, "dynamic_true_peak_dbfs"),
        "rms_dbfs": _median_track_metric(rel, "dynamic_rms_dbfs"),
        "crest_db": _median_track_metric(rel, "dynamic_crest_db"),
    }


def _dynamic_scores_comparable(a: Release, b: Release) -> bool:
    sa = release_dynamic_summary(a)
    sb = release_dynamic_summary(b)
    minimum_tracks = min(a.counted_track_count, b.counted_track_count)
    required = max(1, int(math.ceil(minimum_tracks * DYNAMIC_RANGE_MIN_COVERAGE)))
    return bool(
        sa["score"] is not None
        and sb["score"] is not None
        and int(sa["count"]) >= required
        and int(sb["count"]) >= required
    )


def _release_explicit_preference(rel: Release) -> int:
    return {"clean": 0, "unknown": 1, "explicit": 2}.get(
        release_explicit_state(rel),
        1,
    )



def equivalent_release_preference_key(rel: Release):
    """Preference for exact-equivalent editions after coverage is identical.

    Total retained track count is the first optimization criterion after album
    representation, so an exact-equivalent larger container must not beat a
    smaller one merely because of source metadata.
    """
    rip = cd_rip_quality_key(rel) or (0, 0, 0.0, 0)
    return (
        -rel.track_count,
        source_rank(rel),
        rip,
        1 if rel.root_kind == "existing" else 0,
        _release_explicit_preference(rel),
    )
def _dynamic_final_tie_signature(rel: Release):
    """Return a signature only for releases equal on every pre-DR criterion."""
    if rel.excluded_only:
        return None
    seq = _included_group_sequence(rel)
    if not seq:
        return None

    if rel.release_type == "album" and rel.family:
        identity = ("album", rel.family)
    else:
        identity = ("release", normalize_title(rel.title))

    # Included tracks are already proven by acoustic group IDs. Excluded tracks
    # were intentionally not fingerprinted, so retain their normalized semantic
    # identity in the signature instead of assuming they are interchangeable.
    full_track_shape = []
    for track in rel.tracks:
        if not track.exclude_from_coverage and track.group_id >= 0:
            full_track_shape.append(("included", int(track.group_id)))
        else:
            full_track_shape.append(
                (
                    "excluded",
                    _base_title_identity(track.display_title),
                    tuple(sorted(
                        _descriptor_family_set(
                            _semantic_version_descriptors(track.display_title)
                        )
                    )),
                    bool(track.is_remix),
                    bool(track.is_live),
                )
            )

    return (
        source_rank(rel),
        cd_rip_quality_key(rel),
        rel.release_type,
        identity,
        rel.track_count,
        rel.included_track_count,
        tuple(seq),
        tuple(sorted(_included_group_counter(rel).items())),
        tuple(full_track_shape),
        rel.root_kind,
        release_explicit_state(rel),
    )


def _append_dynamic_range_log(
    path: Optional[Path],
    payload: Dict[str, object],
) -> None:
    if path is None:
        return
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    {
                        "record_type": "dynamic_range",
                        "generated": datetime.now().isoformat(timespec="seconds"),
                        "mode": "final-unresolved-tie-only",
                        **payload,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:
        pass


def apply_dynamic_range_final_ties(
    releases: List[Release],
    selected: Set[int],
    progress_cb=None,
    errors: Optional[List[str]] = None,
    comparison_log_path: Optional[Path] = None,
    blocked_release_ids: Optional[Set[int]] = None,
) -> Set[int]:
    """Measure DR only when every higher-priority criterion is already tied."""
    selected = set(selected)
    blocked = set(blocked_release_ids or set())
    errors = errors if errors is not None else []
    progress = progress_cb or (lambda _label, _done, _total: None)

    by_signature: Dict[object, List[Release]] = defaultdict(list)
    for rel in releases:
        if rel.rid in blocked:
            continue
        signature = _dynamic_final_tie_signature(rel)
        if signature is not None:
            by_signature[signature].append(rel)

    tie_groups: List[List[Release]] = []
    for rels in by_signature.values():
        if len(rels) < 2:
            continue
        selected_rels = [rel for rel in rels if rel.rid in selected]
        alternatives = [rel for rel in rels if rel.rid not in selected]
        if len(selected_rels) == 1 and alternatives:
            tie_groups.append(rels)

    if not tie_groups:
        progress("Final DR tie-break...", 1, 1)
        _append_dynamic_range_log(
            comparison_log_path,
            {
                "tie_group_count": 0,
                "candidate_release_count": 0,
                "tracks_considered": 0,
                "cache_hits": 0,
                "tracks_newly_measured": 0,
                "replacements": [],
            },
        )
        return selected

    picked: Dict[int, Track] = {}
    for rels in tie_groups:
        for rel in rels:
            for track in rel.tracks:
                if not track.exclude_from_coverage and track.group_id >= 0:
                    picked[id(track)] = track
    candidates = list(picked.values())

    cache = _load_dynamic_range_cache()
    pending: List[Tuple[Track, str]] = []
    cache_hits = 0
    done = 0
    label = f"Final DR tie-break ({min(DYNAMIC_RANGE_WORKERS, max(1, len(candidates)))} workers)..."
    progress(label, 0, max(1, len(candidates)))

    for track in candidates:
        key = _dynamic_range_cache_key(track)
        cached = cache.get(key)
        if isinstance(cached, dict):
            _apply_dynamic_metrics(track, cached)
            cache_hits += 1
            done += 1
            progress(label, done, len(candidates))
        else:
            pending.append((track, key))

    newly_measured = 0
    if pending:
        try:
            ffmpeg, _ffprobe = ensure_ffmpeg()
            workers = min(DYNAMIC_RANGE_WORKERS, len(pending))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {
                    ex.submit(_measure_track_dynamic_range, ffmpeg, track): (track, key)
                    for track, key in pending
                }
                for fut in as_completed(futures):
                    track, key = futures[fut]
                    try:
                        metrics = fut.result()
                        _apply_dynamic_metrics(track, metrics)
                        cache[key] = metrics
                        newly_measured += 1
                    except Exception as exc:
                        errors.append(f"Dynamic range error: {track.path}: {exc}")
                    done += 1
                    progress(label, done, len(candidates))
        except Exception as exc:
            errors.append(f"Dynamic range setup error: {exc}")

    try:
        _save_dynamic_range_cache(cache)
    except Exception as exc:
        errors.append(f"Dynamic range cache error: {exc}")

    replacements: List[Dict[str, object]] = []
    for rels in tie_groups:
        current = next((rel for rel in rels if rel.rid in selected), None)
        if current is None:
            continue
        comparable = [
            rel for rel in rels
            if _dynamic_scores_comparable(current, rel)
        ]
        if len(comparable) < 2:
            continue

        best = max(
            comparable,
            key=lambda rel: (
                float(release_dynamic_summary(rel)["score"]),
                -rel.rid,
            ),
        )
        current_score = float(release_dynamic_summary(current)["score"])
        best_score = float(release_dynamic_summary(best)["score"])
        if best.rid != current.rid and best_score > current_score + DYNAMIC_RANGE_EPSILON:
            selected.discard(current.rid)
            selected.add(best.rid)
            replacements.append(
                {
                    "from_release_id": current.rid,
                    "from_release": current.path.name,
                    "from_score": current_score,
                    "to_release_id": best.rid,
                    "to_release": best.path.name,
                    "to_score": best_score,
                }
            )

    _append_dynamic_range_log(
        comparison_log_path,
        {
            "tie_group_count": len(tie_groups),
            "candidate_release_count": sum(len(group) for group in tie_groups),
            "tracks_considered": len(candidates),
            "cache_hits": cache_hits,
            "tracks_newly_measured": newly_measured,
            "replacements": replacements,
            "release_scores": [
                {
                    "release_id": rel.rid,
                    "name": rel.path.name,
                    **release_dynamic_summary(rel),
                }
                for group in tie_groups
                for rel in group
            ],
        },
    )
    return selected

def quality_key(rel: Release) -> Tuple[int, int, int]:
    return (
        source_rank(rel),
        cd_rip_quality_class(rel),
        1 if rel.root_kind == "existing" else 0,
    )


def greedy_cover(target: Set[int], releases: List[Release], selected: Set[int]) -> Tuple[Set[int], Set[int]]:
    covered: Set[int] = set()
    for r in releases:
        if r.rid in selected:
            covered |= r.groups
    missing = set(target) - covered
    chosen: Set[int] = set()
    while missing:
        best = None
        best_key = None
        for r in releases:
            if r.rid in selected or r.rid in chosen or not r.groups:
                continue
            new = r.groups & missing
            if not new:
                continue
            # Price every carried track, including early-eliminated extras.
            # Lower total track number is preferred once source/log quality is valid.
            cost_per = max(1, r.track_count) / len(new)
            source_q, log_class, existing = quality_key(r)
            key = (
                -source_q,
                -log_class,
                cost_per,
                -len(new),
                0 if r.root_kind == "existing" else 1,
                r.track_count,
                r.title.lower(),
            )
            if best_key is None or key < best_key:
                best_key = key
                best = r
        if best is None:
            break
        chosen.add(best.rid)
        missing -= best.groups
    return chosen, missing


def _explicit_rank(rel: Release) -> int:
    """Legacy neutral rank; Explicit>Clean is enforced before fingerprinting."""
    return 1


def _included_group_sequence(rel: Release) -> List[int]:
    return [
        _track_coverage_gid(t) for t in rel.tracks
        if t.group_id >= 0 and not t.exclude_from_coverage
    ]


ALBUM_OVERLAP_THRESHOLD = 0.80


def _manual_album_group_path_key(value: Path) -> str:
    """Stable across sessions and source pools; not a temporary release ID."""
    return os.path.normcase(str(Path(value).resolve(strict=False))).replace("\\", "/").casefold()


_MANUAL_ALBUM_GROUP_LINKS: Optional[Dict[str, str]] = None


def _manual_album_group_links() -> Dict[str, str]:
    global _MANUAL_ALBUM_GROUP_LINKS
    if _MANUAL_ALBUM_GROUP_LINKS is None:
        try:
            payload = json.loads((_state_dir() / "manual_album_groups.json").read_text(encoding="utf-8"))
            raw = payload.get("links", {}) if isinstance(payload, dict) else {}
            _MANUAL_ALBUM_GROUP_LINKS = {
                str(src): str(dst) for src, dst in raw.items()
                if isinstance(src, str) and isinstance(dst, str) and src and dst and src != dst
            } if isinstance(raw, dict) else {}
        except (OSError, ValueError, TypeError):
            _MANUAL_ALBUM_GROUP_LINKS = {}
    return dict(_MANUAL_ALBUM_GROUP_LINKS)


def _save_manual_album_group_links(links: Dict[str, str]) -> None:
    """Atomic persistent override; changing the map never moves audio files."""
    global _MANUAL_ALBUM_GROUP_LINKS
    normalized = {str(a): str(b) for a, b in links.items() if a and b and a != b}
    _atomic_write_json(_state_dir() / "manual_album_groups.json",
                       {"schema": 1, "links": normalized})
    _MANUAL_ALBUM_GROUP_LINKS = normalized



def _manual_ignored_releases_path() -> Path:
    return _state_dir() / "manual_ignored_releases.json"


def _load_manual_ignored_release_paths() -> Set[str]:
    """Committed Ignore choices survive rescans; never persist temporary release IDs."""
    try:
        data = json.loads(_manual_ignored_releases_path().read_text(encoding="utf-8"))
        items = data.get("paths", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            return set()
        return {str(item).casefold() for item in items if isinstance(item, str) and item}
    except (OSError, ValueError, TypeError):
        return set()


def _save_manual_ignored_release_paths(paths: Set[str]) -> None:
    _atomic_write_json(
        _manual_ignored_releases_path(),
        {
            "app": APP_NAME,
            "version": APP_VERSION,
            "schema_version": 1,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "paths": sorted(str(path).casefold() for path in paths if path),
        },
    )


def _manual_kept_releases_path() -> Path:
    return _state_dir() / "manual_kept_releases.json"


def _load_manual_kept_release_paths() -> Set[str]:
    try:
        data = json.loads(_manual_kept_releases_path().read_text(encoding="utf-8"))
        return {str(p).casefold() for p in data.get("paths", []) if isinstance(p, str) and p}
    except (OSError, ValueError, TypeError, AttributeError):
        return set()


def _save_manual_kept_release_paths(paths: Set[str]) -> None:
    _atomic_write_json(_manual_kept_releases_path(), {
        "schema_version": 1, "paths": sorted(str(p).casefold() for p in paths if p),
    })


def _committed_kept_paths_for_plan(releases: List[Release], kept_ids: Set[int]) -> Set[str]:
    known = {_manual_album_group_path_key(rel.path) for rel in releases}
    other = _load_manual_kept_release_paths() - known
    return other | {_manual_album_group_path_key(rel.path) for rel in releases
                    if rel.rid in kept_ids}


def _committed_ignore_paths_for_plan(
    releases: List[Release], blocked_ids: Set[int]
) -> Set[str]:
    """Replace current scanned paths, while preserving ignores from other pools."""
    known_paths = {_manual_album_group_path_key(rel.path) for rel in releases}
    stored = _load_manual_ignored_release_paths() - known_paths
    return stored | {
        _manual_album_group_path_key(rel.path)
        for rel in releases if rel.rid in blocked_ids
    }


def _album_main_artist(rel: Release) -> str:
    """Refuse automatic cross-artist album merges from shared compilation audio."""
    credits = Counter(
        _primary_artist_key(track)
        for track in rel.tracks
        if not track.exclude_from_coverage and _primary_artist_key(track)
    )
    return credits.most_common(1)[0][0] if credits else ""


def _album_editions_related_by_audio(a: Release, b: Release) -> bool:
    """Recognize Album/EP edition families through >=80% PROVEN audio overlap.

    Denominator is the smaller album's wanted acoustic-group set: an expanded
    deluxe edition may contain many additional unique bonus songs. This rule
    establishes album-family membership, NEVER duplicate recording identity.
    """
    if a.release_type not in {"album", "ep"} or b.release_type not in {"album", "ep"}:
        return False
    groups_a, groups_b = set(_included_group_sequence(a)), set(_included_group_sequence(b))
    smaller = min(len(groups_a), len(groups_b))
    if smaller < 4:
        return False
    common = len(groups_a & groups_b)
    if common < 4 or common / smaller < ALBUM_OVERLAP_THRESHOLD:
        return False
    artist_a, artist_b = _album_main_artist(a), _album_main_artist(b)
    if artist_a and artist_b and not (_artist_identity_aliases(artist_a) & _artist_identity_aliases(artist_b)):
        return False
    return True


def _album_clusters(albums: List[Release]) -> List[List[Release]]:
    if not albums:
        return []
    uf = UnionFind(len(albums))
    links = _manual_album_group_links()
    paths = [_manual_album_group_path_key(rel.path) for rel in albums]
    positions = {key: i for i, key in enumerate(paths)}
    # Detach only when both endpoints exist in the current clustering set.
    # Album-only optimizer checks must not split an album family merely
    # because a map assignment points to an EP outside that set.
    overridden = {
        source for source, target in links.items()
        if source in positions and target in positions
    }

    # Resolve paths only once: re-resolving them for every candidate pair can
    # saturate slow disks on large music libraries.
    # Explicit assignments detach a release from its previous automatic family.
    for i, j in itertools.combinations(range(len(albums)), 2):
        if paths[i] in overridden or paths[j] in overridden:
            continue
        if _album_editions_related_by_audio(albums[i], albums[j]):
            uf.union(i, j)

    # Links are directed in storage, but album-family membership is symmetric.
    # Targets may themselves point to another group; chains collapse safely.
    for source, target in links.items():
        if source in positions and target in positions:
            uf.union(positions[source], positions[target])

    grouped: Dict[int, List[Release]] = defaultdict(list)
    for i, rel in enumerate(albums):
        grouped[uf.find(i)].append(rel)
    return [grouped[k] for k in sorted(grouped)]



def choose_album_families(releases: List[Release]) -> Set[int]:
    """Pick a valid warm-start seed, NOT a maximum-completeness constraint.

    The global solver may discard this edition and choose any other full
    album from its family as long as every wanted audio group stays covered.
    """
    selected: Set[int] = set()
    albums = [r for r in releases if r.release_type == "album" and not r.excluded_only]

    for candidates in _album_clusters(albums):
        if not candidates:
            continue
        complete_ids = _max_complete_album_ids(candidates)
        complete = [r for r in candidates if r.rid in complete_ids]
        chosen = min(
            complete,
            key=lambda r: (
                r.track_count,
                -source_rank(r),
                -cd_rip_quality_class(r),
                0 if r.root_kind == "existing" else 1,
                r.rid,
            ),
        )
        selected.add(chosen.rid)

    return selected

def _track_coverage_gid(track: Track) -> int:
    """Every true acoustic version is a mandatory planning obligation."""
    return int(track.group_id)


def _assign_replaceable_version_coverage(
    tracks: List[Track],
    acoustic_verdicts: List[Tuple[int, int, int, bool, object]],
) -> List[Dict[str, object]]:
    """Distinct acoustic versions remain distinct mandatory requirements.

    October 15 preservation rule supersedes the old edit-substitution policy.
    Keep the compatibility hook, but erase stale substitutions on every scan.
    """
    for track in tracks:
        track.coverage_group_id = -1
    return []


def _included_group_counter(rel: Release) -> Counter:
    return Counter(_track_coverage_gid(t) for t in rel.tracks if t.group_id >= 0 and not t.exclude_from_coverage)


def _release_covers(covering: Release, target: Release) -> bool:
    """Audio-only included-content coverage using fingerprint groups."""
    need = _included_group_counter(target)
    have = _included_group_counter(covering)
    return all(have[gid] >= count for gid, count in need.items())


def _release_barcodes(rel: Release) -> Set[str]:
    values: Set[str] = set()
    if rel.tracks:
        tag = tag_lookup(rel.tracks[0].tags, "barcode", "upc", "ean")
        digits = re.sub(r"\D", "", tag)
        if 8 <= len(digits) <= 14:
            values.add(digits)
    return values


def _related_album_releases(a: Release, b: Release) -> bool:
    """Album-edition relation from audio overlap/order, with barcode fallback."""
    if a.release_type != "album" or b.release_type != "album":
        return False
    if _album_editions_related_by_audio(a, b):
        return True
    return bool(_release_barcodes(a) & _release_barcodes(b))


def _album_unique_track_count(rel: Release) -> int:
    """Distinct included wanted recordings carried by one album edition."""
    return len(rel.groups)


def _max_complete_album_ids(cluster: List[Release]) -> Set[int]:
    """Album editions eligible to represent the album itself."""
    if not cluster:
        return set()
    maximum = max(_album_unique_track_count(rel) for rel in cluster)
    return {
        rel.rid
        for rel in cluster
        if _album_unique_track_count(rel) == maximum
    }


def _album_requirement_provider_ids(
    cluster: List[Release],
    releases: List[Release],
) -> Set[int]:
    """Any full album edition can represent its family.

    The global wanted-group requirements independently preserve every song.
    Having more tracks than another edition is NOT grounds for mandatory
    retention. The user may keep shorter WEB/CD versions for unique tracks
    and remove a redundant Japanese album in that very same family.
    Exact audio-identical album/EP/single aliases remain supported.
    A complete CD has first claim on the family anchor, without losing any
    missing bonus or additional featured version from the global group cover.
    """
    complete_ids = _max_complete_album_ids(cluster)
    anchors = [rel for rel in cluster if rel.rid in complete_ids]
    providers = {
        rel.rid for rel in cluster
        if rel.release_type == "album" and not rel.excluded_only and rel.groups
    }

    # CD-first album anchor: a CD can supersede the largest WEB album
    # when fingerprint groups prove that it is fully covered, even if the
    # CD physically carries more tracks. Alternatively a smaller CD is a
    # valid anchor only when every larger edition's missing wanted group
    # has an independent eligible carrier OUTSIDE the album family.
    # An unrelated larger Japanese CD with different album-only material
    # is not a mandatory anchor merely because it has the most songs.
    album_ids = {rel.rid for rel in cluster}
    maximal = [rel for rel in cluster if rel.rid in complete_ids]
    web_editions = [
        rel for rel in cluster
        if rel.rid in providers and source_rank(rel) < 2
    ]
    largest_web_count = max((len(rel.groups) for rel in web_editions), default=0)
    major_web_editions = [
        rel for rel in web_editions if len(rel.groups) == largest_web_count
    ]
    qualified_cds: Set[int] = set()
    for cd in cluster:
        if cd.rid not in providers or source_rank(cd) < 2 or not cd.groups:
            continue
        covers_largest_web = any(
            _release_covers(cd, web) for web in major_web_editions
        )
        can_source_all_deluxe_extras = (
            cd.rid not in complete_ids
            and all(
                _release_covers(full, cd)
                and all(
                    any(
                        other.rid not in album_ids
                        and other.release_type in {"album", "ep", "single"}
                        and not other.excluded_only
                        and gid in other.groups
                        for other in releases
                    )
                    for gid in full.groups - cd.groups
                )
                for full in maximal
            )
        )
        if covers_largest_web or can_source_all_deluxe_extras:
            qualified_cds.add(cd.rid)
    if qualified_cds:
        providers = qualified_cds

    normalized_anchors = [
        (
            anchor,
            normalize_title(_release_map_family_base(anchor.title, anchor.release_type)),
        )
        for anchor in anchors
    ]
    for rel in releases:
        # Even two-track Album-tagged editions may fall into separate audio
        # clusters (the broader overlap heuristic requires at least 5 groups).
        # A fully identical physical container can still fulfill either.
        if rel.rid in providers or rel.release_type not in {"album", "ep", "single"} or rel.excluded_only:
            continue
        normalized_rel = normalize_title(_release_map_family_base(rel.title, rel.release_type))
        if not normalized_rel:
            continue
        for anchor, normalized_anchor in normalized_anchors:
            if (
                normalized_rel == normalized_anchor
                and _exact_equivalent_release_content(rel, anchor)
                and (not qualified_cds or source_rank(rel) >= 2)
            ):
                providers.add(rel.rid)
                break
    return providers


def find_dominated_releases(releases: List[Release],
                            details: Optional[Dict[int, List[Dict[str, object]]]] = None) -> Set[int]:
    """Eliminate only genuinely dominated editions before global optimization.

    For ordinary tracks, complete supersets dominate subsets regardless of source rank.
    A smaller album that is missing only independently issued featured-remix
    bonuses must remain eligible for the exact minimum-track solver.
    """
    dominated: Set[int] = set()
    def mark(loser: Release, winner: Release, reason: str) -> None:
        dominated.add(loser.rid)
        if details is not None:
            details.setdefault(loser.rid, []).append({"by_release_id": winner.rid, "reason": reason})
    albums = [r for r in releases if r.release_type == "album" and not r.excluded_only]
    manual_links = _manual_album_group_links()
    # Dominance must never silently undo an explicit "Move to group". Exact
    # acoustic duplicates can be in different user-assigned album families.
    cluster_membership = _selected_album_cluster_map(releases) if manual_links else {}

    for a, b in itertools.combinations(albums, 2):
        if not _related_album_releases(a, b):
            continue
        if manual_links and (
            _manual_album_group_path_key(a.path) in manual_links
            or _manual_album_group_path_key(b.path) in manual_links
        ) and cluster_membership.get(a.rid) != cluster_membership.get(b.rid):
            continue

        a_covers_b = _release_covers(a, b)
        b_covers_a = _release_covers(b, a)

        if a_covers_b and not b_covers_a:
            # A strict subset is dominated only if the superset is required
            # by a bonus recording unavailable on any OTHER regular release.
            # Otherwise both editions remain choices for the global solver.
            extra = a.groups - b.groups
            if any(
                not any(
                    other.rid not in {a.rid, b.rid}
                    and other.release_type != "compilation"
                    and gid in other.groups
                    for other in releases
                )
                for gid in extra
            ):
                mark(b,a,"Required strict superset preserves every wanted version")
            continue
        if b_covers_a and not a_covers_b:
            extra = b.groups - a.groups
            if any(
                not any(
                    other.rid not in {a.rid, b.rid}
                    and other.release_type != "compilation"
                    and gid in other.groups
                    for other in releases
                )
                for gid in extra
            ):
                mark(a,b,"Required strict superset preserves every wanted version")
            continue
        if not (a_covers_b and b_covers_a):
            continue

        # Never eliminate a better-source equivalent before source constraints.
        quality_a = _optimizer_quality_floor(a)
        quality_b = _optimizer_quality_floor(b)
        if quality_a != quality_b:
            loser,winner = (b,a) if quality_a > quality_b else (a,b)
            mark(loser,winner,"Equivalent audio; better source or CD rip quality")
            continue

        a_pref = equivalent_release_preference_key(a)
        b_pref = equivalent_release_preference_key(b)
        if a_pref > b_pref:
            mark(b,a,"Equivalent audio; preferred edition")
        elif b_pref > a_pref:
            mark(a,b,"Equivalent audio; preferred edition")

    return dominated
def _selected_album_cluster_map(releases: List[Release]) -> Dict[int, int]:
    albums = [r for r in releases if r.release_type == "album" and not r.excluded_only]
    result: Dict[int, int] = {}
    for cluster_id, cluster in enumerate(_album_clusters(albums)):
        for rel in cluster:
            result[rel.rid] = cluster_id
    return result




def prune_redundant_selected(releases: List[Release], selected: Set[int]) -> Set[int]:
    """Remove fully-covered editions but keep at least one album per family."""
    selected = set(selected)
    by_id = {r.rid: r for r in releases}
    album_cluster = _selected_album_cluster_map(releases)

    changed = True
    while changed:
        changed = False
        ordered = sorted(
            (by_id[rid] for rid in selected),
            key=lambda r: (
                0 if r.release_type != "album" else 1,
                -r.track_count,
                r.rid,
            ),
        )

        for rel in ordered:
            others = [by_id[rid] for rid in selected if rid != rel.rid]
            if not others:
                continue

            if rel.release_type == "album":
                cid = album_cluster.get(rel.rid)
                if cid is None:
                    continue
                same_family = [
                    other
                    for other in others
                    if other.release_type == "album"
                    and album_cluster.get(other.rid) == cid
                ]
                if not same_family:
                    continue

                # Presence of another retained album fulfills the only album
                # family requirement, regardless of which is larger. The
                # acoustic coverage check below protects all unique tracks.

            need = _included_group_counter(rel)
            have = Counter()
            carriers: Dict[int, List[Release]] = defaultdict(list)
            for other in others:
                counter = _included_group_counter(other)
                have.update(counter)
                for gid in counter:
                    carriers[gid].append(other)

            if any(have[gid] < count for gid, count in need.items()):
                continue

            # No hard source-quality veto on removing redundant copies.
            selected.remove(rel.rid)
            changed = True
            break

    return selected
def _optimizer_quality_floor(rel: Release) -> Tuple[int, int]:
    """Source + CD-log threshold floor. Existing is only a late tie-break."""
    return (source_rank(rel), cd_rip_quality_class(rel))




def _optimizer_cost(by_id: Dict[int, Release], selected: Set[int]) -> Tuple[object, ...]:
    """Exact objective after wanted coverage and album completeness are fixed."""
    rels = [by_id[rid] for rid in selected]
    below_threshold_cd = sum(
        1 for rel in rels
        if source_rank(rel) >= 2 and cd_rip_quality_class(rel) == 1
    )
    return (
        # User-defined hard ordering:
        # 1) every album/wanted recording is already a requirement,
        # 2) lower total retained track count,
        # 3) lower retained release count.
        sum(rel.track_count for rel in rels),
        len(rels),
        # Remaining quality/existing rules are tie-breaks only.
        below_threshold_cd,
        -sum(source_rank(rel) for rel in rels),
        -sum(cd_rip_quality_class(rel) for rel in rels),
        sum(1 for rel in rels if rel.root_kind == "recycle"),
        tuple(sorted(selected)),
    )

def _exact_component_cover(
    by_id: Dict[int, Release],
    requirements: Set[Tuple[str, int]],
    requirement_providers: Dict[Tuple[str, int], Set[int]],
    release_requirements: Dict[int, Set[Tuple[str, int]]],
    seed_selected: Set[int],
) -> Tuple[Set[int], int]:
    """Solve one independent coverage component exactly with branch-and-bound."""
    component_release_ids: Set[int] = set()
    for req in requirements:
        component_release_ids |= requirement_providers.get(req, set())

    seed = set(seed_selected) & component_release_ids

    def satisfied(selected: Set[int]) -> Set[Tuple[str, int]]:
        out: Set[Tuple[str, int]] = set()
        for rid in selected:
            out |= release_requirements.get(rid, set())
        return out

    best: Optional[Set[int]] = None
    best_cost: Optional[Tuple[object, ...]] = None
    if requirements <= satisfied(seed):
        best = set(seed)
        best_cost = _optimizer_cost(by_id, best)

    mandatory: Set[int] = set()
    changed = True
    while changed:
        changed = False
        already = satisfied(mandatory)
        for req in sorted(requirements - already):
            providers = requirement_providers.get(req, set())
            if not providers:
                raise RuntimeError(f"No eligible provider for optimizer requirement {req!r}")
            if len(providers) == 1:
                rid = next(iter(providers))
                if rid not in mandatory:
                    mandatory.add(rid)
                    changed = True

    mandatory_satisfied = satisfied(mandatory)
    unsatisfied_start = frozenset(requirements - mandatory_satisfied)
    states = 0
    memo: Dict[frozenset, Tuple[int, int, int]] = {}

    def partial_key(selected: Set[int]) -> Tuple[int, int, int]:
        rels = [by_id[rid] for rid in selected]
        return (
            sum(rel.track_count for rel in rels),
            len(rels),
            sum(
                1 for rel in rels
                if source_rank(rel) >= 2 and cd_rip_quality_class(rel) == 1
            ),
        )

    def branch_key(rid: int, unsatisfied: frozenset) -> Tuple[object, ...]:
        rel = by_id[rid]
        newly = len(release_requirements.get(rid, set()) & set(unsatisfied))
        return (
            rel.track_count,
            -newly,
            1 if source_rank(rel) >= 2 and cd_rip_quality_class(rel) == 1 else 0,
            -source_rank(rel),
            -cd_rip_quality_class(rel),
            0 if rel.root_kind == "existing" else 1,
            rel.rid,
        )

    def dfs(selected: Set[int], unsatisfied: frozenset) -> None:
        nonlocal best, best_cost, states
        states += 1

        part = partial_key(selected)
        prior = memo.get(unsatisfied)
        if prior is not None and prior < part:
            return
        if prior is None or part < prior:
            memo[unsatisfied] = part

        if best_cost is not None:
            # Only compare the monotonic cost prefix. Source quality and
            # Existing/Recycle are later tie-breaks and cannot safely prune.
            best_prefix = tuple(best_cost[:3])
            if part > best_prefix:
                return

        if not unsatisfied:
            cost = _optimizer_cost(by_id, selected)
            if best_cost is None or cost < best_cost:
                best = set(selected)
                best_cost = cost
            return

        req = min(
            unsatisfied,
            key=lambda item: (
                len(requirement_providers.get(item, set())),
                item[0],
                item[1],
            ),
        )
        providers = sorted(
            requirement_providers.get(req, set()),
            key=lambda rid: branch_key(rid, unsatisfied),
        )

        for rid in providers:
            if rid in selected:
                continue
            new_selected = set(selected)
            new_selected.add(rid)
            newly_satisfied = release_requirements.get(rid, set())
            dfs(new_selected, frozenset(set(unsatisfied) - newly_satisfied))

    dfs(set(mandatory), unsatisfied_start)

    if best is None:
        raise RuntimeError("Exact global optimizer could not satisfy a coverage component")

    return best, states
def exact_global_collection_minimize(
    releases: List[Release],
    seed_selected: Set[int],
    progress_cb=None,
) -> Tuple[Set[int], Dict[str, object]]:
    """Coverage Atlas-style exact global minimization for DEA.

    DEA keeps its own fingerprint identity, album rules, source precedence,
    early Remix/Live policy, and Apply workflow. This solver only replaces the old
    greedy/local collection minimization stage.

    The exact search keeps every active wanted recording group and requires
    one eligible album-family representative, preferring a complete CD where
    it can be the anchor without losing album-only content. Every wanted
    recording remains a separate mandatory requirement. After that, minimize
    physical tracks and releases; source quality ranks remaining ties.
    """
    by_id = {r.rid: r for r in releases}
    seed_selected = set(seed_selected)

    all_groups: Set[int] = set()
    for rel in releases:
        if not rel.excluded_only:
            all_groups |= rel.groups

    requirement_providers: Dict[Tuple[str, int], Set[int]] = {}
    release_requirements: Dict[int, Set[Tuple[str, int]]] = defaultdict(set)

    for gid in sorted(all_groups):
        req = ("group", gid)
        carriers = [rel for rel in releases if gid in rel.groups]
        # A compilation becomes eligible only when there is NO remaining
        # non-compilation carrier in this re-optimization's unblocked pool.
        # Never let a CD compilation's source score displace a regular release
        # or permanently remove its own emergency fallback coverage.
        regular_carriers = [r for r in carriers if r.release_type != "compilation"]
        preferred_carriers = regular_carriers or carriers
        # All regular carriers can provide this wanted recording; a better-source
        # original cannot force retention beside its strict deluxe superset.
        providers = {rel.rid for rel in preferred_carriers}
        requirement_providers[req] = providers
        for rid in providers:
            release_requirements[rid].add(req)

    album_clusters = _album_clusters(
        [r for r in releases if r.release_type == "album" and not r.excluded_only]
    )
    for cluster_id, cluster in enumerate(album_clusters):
        # Prefer a complete CD for the family; missing featured recordings
        # remain independently mandatory and may require another edition.
        # Unique wanted acoustic groups are independently mandatory.
        req = ("album", cluster_id)
        providers = _album_requirement_provider_ids(cluster, releases)
        requirement_providers[req] = providers
        for rid in providers:
            release_requirements[rid].add(req)

    requirements = set(requirement_providers)
    if not requirements:
        stats = {
            "components": 0,
            "states": 0,
            "requirements": 0,
            "recording_groups": 0,
            "source_floor_requirements": 0,
            "album_families": 0,
            "seed_releases": len(seed_selected),
            "selected_releases": 0,
            "seed_tracks": sum(
                by_id[rid].track_count
                for rid in seed_selected
                if rid in by_id
            ),
            "selected_tracks": 0,
        }
        return set(), stats

    unvisited = set(requirements)
    components: List[Set[Tuple[str, int]]] = []
    while unvisited:
        start = min(unvisited)
        stack = [start]
        component: Set[Tuple[str, int]] = set()
        while stack:
            req = stack.pop()
            if req in component:
                continue
            component.add(req)
            unvisited.discard(req)
            for rid in requirement_providers.get(req, set()):
                for linked in release_requirements.get(rid, set()):
                    if linked not in component:
                        stack.append(linked)
        components.append(component)

    selected: Set[int] = set()
    total_states = 0
    total_components = len(components)

    for index, component in enumerate(
        sorted(components, key=lambda comp: min(comp)),
        start=1,
    ):
        if progress_cb:
            progress_cb(
                f"Exact global optimization ({index}/{total_components})...",
                index - 1,
                total_components,
            )
        solved, states = _exact_component_cover(
            by_id,
            component,
            requirement_providers,
            release_requirements,
            seed_selected,
        )
        selected |= solved
        total_states += states

    if progress_cb:
        progress_cb(
            f"Exact global optimization ({total_components}/{total_components})...",
            total_components,
            max(1, total_components),
        )

    stats = {
        "components": total_components,
        "states": total_states,
        "requirements": len(requirements),
        "recording_groups": len(all_groups),
        "source_floor_requirements": 0,
        "album_families": len(album_clusters),
        "seed_releases": len(seed_selected),
        "selected_releases": len(selected),
        "seed_tracks": sum(
            by_id[rid].track_count
            for rid in seed_selected
            if rid in by_id
        ),
        "selected_tracks": sum(
            by_id[rid].track_count
            for rid in selected
            if rid in by_id
        ),
    }
    return selected, stats


def _exact_equivalent_release_content(a: Release, b: Release) -> bool:
    """True when two containers carry the same included recordings in the same order.

    Provider Album/EP/Single metadata is not allowed to create pointless churn.
    Full physical track count still must match so a remix-heavy package is not
    treated as the same container as a compact replacement.
    """
    if a.track_count != b.track_count or a.included_track_count != b.included_track_count:
        return False
    seq_a = _included_group_sequence(a)
    seq_b = _included_group_sequence(b)
    return bool(
        seq_a
        and seq_a == seq_b
        and _included_group_counter(a) == _included_group_counter(b)
    )


def prefer_existing_equivalent_releases(
    releases: List[Release],
    selected: Set[int],
) -> Set[int]:
    """Avoid churn: same content + same source quality keeps the Existing copy.

    A New/Update release may replace Existing only when there is an objective
    improvement such as a higher source class or a better comparable CD rip log.
    """
    selected = set(selected)
    existing = [r for r in releases if r.root_kind == "existing"]
    album_requirements = [
        _album_requirement_provider_ids(cluster, releases)
        for cluster in _album_clusters([
            r for r in releases if r.release_type == "album" and not r.excluded_only
        ])
    ]

    for new in [r for r in releases if r.root_kind == "recycle" and r.rid in selected]:
        candidates = [
            old for old in existing
            if old.rid not in selected
            and _exact_equivalent_release_content(old, new)
            and source_rank(old) == source_rank(new)
        ]
        if not candidates:
            continue

        new_rip = cd_rip_quality_key(new)
        safe: List[Release] = []
        for old in candidates:
            old_rip = cd_rip_quality_key(old)
            # A genuinely better comparable CD log is allowed to replace Existing.
            if new_rip is not None and (old_rip is None or new_rip > old_rip):
                continue
            if _optimizer_quality_floor(old) < _optimizer_quality_floor(new):
                continue
            proposed = (selected - {new.rid}) | {old.rid}
            # Preserve every album representative, including true identical
            # EP/Album metadata aliases. Never swap a real album for a
            # different release merely because their tracks overlap.
            if any(not (providers & proposed) for providers in album_requirements):
                continue
            safe.append(old)
        if not safe:
            continue

        best_old = max(
            safe,
            key=lambda old: (
                cd_rip_quality_key(old) or (0, 0, 0.0, 0),
                -old.rid,
            ),
        )
        selected.discard(new.rid)
        selected.add(best_old.rid)

    return selected


def _release_upgrade_reason(new: Release, old: Release) -> str:
    """Describe a real improvement; empty means replacement is not an upgrade."""
    old_rank = source_rank(old)
    new_rank = source_rank(new)
    if new_rank > old_rank:
        return f"Source {old.source_medium or 'Unknown'} -> {new.source_medium or 'Unknown'}"

    old_rip = cd_rip_quality_key(old)
    new_rip = cd_rip_quality_key(new)
    if (
        new_rank >= 2
        and new_rip is not None
        and (old_rip is None or new_rip > old_rip)
    ):
        return "Better CD rip log"

    if old.groups and old.groups < new.groups:
        delta = len(new.groups - old.groups)
        return f"More complete: +{delta} recording(s)"

    return ""


def _append_optimizer_log(path: Optional[Path], stats: Dict[str, object]) -> None:
    if path is None:
        return
    try:
        payload = {
            "record_type": "optimizer",
            "generated": datetime.now().isoformat(timespec="seconds"),
            "algorithm": "exact-global-component-cover-v1",
            **stats,
        }
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass



def _write_reanalysis_audit(
    payload: Dict[str, object], comparison_log_path: Optional[Path] = None
) -> Path:
    """Record a planning rerun, never falsely describe it as new acoustic analysis."""
    entry = {
        "record_type": "reanalysis",
        "app": APP_NAME,
        "version": APP_VERSION,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "acoustic_comparisons_repeated": False,
        **payload,
    }
    _atomic_write_json(_state_dir() / "last_reanalysis_audit.json", entry)
    destination = _logs_dir() / f"{APP_NAME} Re-Analyze.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    row = json.dumps(entry, ensure_ascii=False) + "\n"
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(row)
    if comparison_log_path is not None:
        try:
            with Path(comparison_log_path).open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(row)
        except OSError as exc:
            # The independent per-run audit exists even if an old comparison
            # log was moved, deleted or made read-only after initial analysis.
            entry["comparison_log_append_warning"] = str(exc)
            _atomic_write_json(_state_dir() / "last_reanalysis_audit.json", entry)
            with destination.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return destination


def _append_final_track_state(path: Optional[Path], releases: List[Release],
                              selected: Set[int], blocked: Set[int]) -> None:
    """Log the state AFTER persistent Ignore and acoustic policy reconciliation."""
    if path is None:
        return
    states = []
    for rel in releases:
        for track in rel.tracks:
            states.append({
                "record_type": "final_track_state", "logging_schema_version": 3,
                "track_index": track.comparison_index if track.comparison_index >= 0 else len(states),
                "release_id": rel.rid, "path": str(track.path),
                "duration_seconds": round(track.duration,6),
                "identity_duration_seconds": round(_identity_track_duration(track),6),
                "acoustic_group_id": track.group_id,
                "coverage_group_id": _track_coverage_gid(track),
                "excluded_from_coverage": track.exclude_from_coverage,
                "base_excluded_from_coverage": track.base_excluded_from_coverage,
                "excluded_by_pattern": track.excluded_by_pattern,
                "explicit_category_exclusion": track.explicit_category_exclusion,
                "manual_skip_rule": track.manual_skip_rule,
                "personal_keep_rule": track.personal_keep_rule,
                "acoustic_policy_reconciled": track.acoustic_policy_reconciled,
                "release_blocked": rel.rid in blocked,
                "release_selected": rel.rid in selected,
            })
    wanted = set().union(*(rel.groups for rel in releases if rel.rid not in blocked))
    retained = set().union(*(rel.groups for rel in releases if rel.rid in selected))
    try:
        with path.open("a",encoding="utf-8") as handle:
            for state in states:
                handle.write(json.dumps(state,ensure_ascii=False)+"\n")
            handle.write(json.dumps({
                "record_type": "final_state_summary", "logging_schema_version": 3,
                "generated": datetime.now().isoformat(timespec="seconds"),
                "tracks_total": len(states),
                "tracks_excluded": sum(bool(row["excluded_from_coverage"]) for row in states),
                "tracks_manually_ignored": sum(bool(row["manual_skip_rule"]) for row in states),
                "acoustic_policy_reconciliations": sum(bool(row["acoustic_policy_reconciled"]) for row in states),
                "wanted_recording_groups": len(wanted),
                "retained_recording_groups": len(retained),
                "uncovered_wanted_group_ids": sorted(wanted-retained),
                "distinct_versions_mandatory": True,
            },ensure_ascii=False)+"\n")
    except OSError as exc:
        raise RuntimeError(f"Final comparison audit log unavailable: {exc}") from exc


def optimize_collection(
    releases: List[Release],
    groups: Dict[int, List[int]],
    blocked_release_ids: Optional[Set[int]] = None,
    progress_cb=None,
    comparison_log_path: Optional[Path] = None,
    errors: Optional[List[str]] = None,
    forced_release_ids: Optional[Set[int]] = None,
) -> Set[int]:
    """Optimize the retained set with exact whole-collection coverage.

    Manual Release Map removals are planning constraints only. Fingerprints and
    recording groups are reused; the expensive audio-analysis stage is not rerun.

    The established DEA passes first produce a valid seed. A Coverage
    Atlas-style exact component solver then enforces wanted coverage plus the
    album requirement (including the separate featured-remix single exception),
    minimizes total retained tracks, then retained releases. Per-group source
    and log quality are late tie-breaks.
    """
    blocked = set(blocked_release_ids or set())
    if forced_release_ids is None:
        pinned_paths = _load_manual_kept_release_paths()
        forced = {rel.rid for rel in releases
                  if _manual_album_group_path_key(rel.path) in pinned_paths}
    else:
        forced = set(forced_release_ids)
    forced &= {rel.rid for rel in releases}
    if forced & blocked:
        raise ValueError("A release cannot be both kept and ignored.")
    eligible = [r for r in releases if r.rid not in blocked]

    required_groups = set().union(*(rel.groups for rel in eligible))
    dominance_details: Dict[int, List[Dict[str, object]]] = {}
    dominated = find_dominated_releases(eligible, dominance_details)
    active = [r for r in eligible if r.rid not in dominated]
    if required_groups - set().union(*(rel.groups for rel in active)):
        raise RuntimeError("Dominance would lose a wanted acoustic version; no plan produced.")

    selected = choose_album_families(active)

    all_groups: Set[int] = set()
    for rel in active:
        all_groups |= rel.groups

    extra, missing = greedy_cover(all_groups, active, selected)
    selected |= extra
    if missing:
        for gid in sorted(missing):
            containing = [r for r in active if gid in r.groups]
            if containing:
                chosen = min(
                    containing,
                    key=lambda r: (
                        -source_rank(r),
                        -cd_rip_quality_class(r),
                        r.track_count,
                        0 if r.root_kind == "existing" else 1,
                        r.rid,
                    ),
                )
                selected.add(chosen.rid)

    selected = prune_redundant_selected(active, selected)

    selected, optimizer_stats = exact_global_collection_minimize(
        active,
        selected,
        progress_cb,
    )
    exact_selected = set(selected)

    # Quality is solved directly rather than adding extra copies afterward.
    selected = prefer_better_cd_rips(active, selected)
    selected = prefer_existing_equivalent_releases(active, selected)

    # DR is the true last unresolved quality tie-break. Nothing is decoded for
    # DR until coverage, source, rip-log quality, file count, release count,
    # Existing/Recycle preference and explicit state have already tied.
    selected = apply_dynamic_range_final_ties(
        active,
        selected,
        progress_cb,
        errors,
        comparison_log_path,
        blocked,
    )

    selected |= forced
    selected -= blocked

    # Late equivalence preferences cannot override the exact solver's
    # requirements. If any later choice violates them, keep the proven
    # exact plan rather than crashing or silently losing wanted material.
    def verify_plan(candidate: Set[int]) -> None:
        wanted_groups = required_groups
        retained = [rel for rel in releases if rel.rid in candidate]
        retained_groups = set().union(*(rel.groups for rel in retained)) if retained else set()
        if not wanted_groups <= retained_groups:
            raise RuntimeError("Optimizer lost wanted recording coverage after quality tie-breaks.")
        for gid in wanted_groups:
            available = [rel for rel in active if gid in rel.groups]
            regular = [rel for rel in available if rel.release_type != "compilation"]
            eligible_providers = regular or available
            sources = [rel for rel in retained if gid in rel.groups and rel in eligible_providers]
            if not sources:
                raise RuntimeError(f"Optimizer lost an eligible regular recording carrier for group {gid}.")
        for family in _album_clusters([
            rel for rel in active if rel.release_type == "album" and not rel.excluded_only
        ]):
            allowed = _album_requirement_provider_ids(family, active)
            if not allowed.intersection(candidate):
                examples = ", ".join(rel.path.name for rel in family[:3])
                raise RuntimeError(
                    "Optimizer lost valid full-album/core representation after "
                    f"quality tie-breaks: {examples}"
                )

    late_tiebreak_reverted = ""
    try:
        verify_plan(selected)
    except RuntimeError as exc:
        late_tiebreak_reverted = str(exc)
        if errors is not None:
            errors.append(
                "Rejected an unsafe late quality tie-break and restored the "
                f"exact optimized plan. Reason: {late_tiebreak_reverted}"
            )
        # Quality-tie fallback must retain user-pinned releases as well.
        selected = set(exact_selected) | forced
        verify_plan(selected)

    optimizer_stats.update(
        {
            "blocked_releases": len(blocked),
            "dominated_releases": len(dominated),
            "active_releases": len(active),
            "final_releases": len(selected),
            "final_tracks": sum(
                r.track_count
                for r in releases
                if r.rid in selected
            ),
            "source_quality_floor_added_release_ids": [],
            "source_floor_enforced_in_exact_solver": False,
            "source_quality_tie_break_only": True,
            "cd_first_complete_album_anchor": True,
            "equivalent_release_type_album_aliases": True,
            "late_tiebreak_reverted": late_tiebreak_reverted,
            "selected_release_ids": sorted(selected),
            "release_source_catalog": [
                {
                    "release_id": rel.rid,
                    "name": rel.path.name,
                    "root_kind": rel.root_kind,
                    "release_type": rel.release_type,
                    "release_type_source": rel.type_source,
                    "type_warning": _release_warning(rel),
                    "source_medium": rel.source_medium,
                    "source_rank": source_rank(rel),
                    "cd_rip_quality_class": cd_rip_quality_class(rel),
                    "cd_rip_quality": list(cd_rip_quality_key(rel) or ()),
                    "track_count": rel.track_count,
                    "included_track_count": rel.included_track_count,
                    "selected": rel.rid in selected,
                    "active": rel.rid not in dominated and rel.rid not in blocked,
                    "dominated": rel.rid in dominated,
                    "dominance_evidence": dominance_details.get(rel.rid, []),
                    "blocked": rel.rid in blocked,
                    "forced_keep": rel.rid in forced,
                }
                for rel in releases
            ],
        }
    )
    _append_final_track_state(comparison_log_path, releases, selected, blocked)
    _append_optimizer_log(comparison_log_path, optimizer_stats)
    return selected


def prepare_analysis(
    existing: Optional[Path],
    recycle: Path,
    progress_cb,
    io_workers: Optional[int] = None,
    extra_existing: Sequence[Path] = (),
    extra_recycle: Sequence[Path] = (),
) -> Tuple[List[Release], List[Track]]:
    """Run the common stages needed before the pattern review."""
    progress_cb("Checking dependencies...", 0, 1)
    _migrate_legacy_app_data()
    _ensure_app_data_dirs()
    bootstrap_winget()
    _ffmpeg, ffprobe = ensure_ffmpeg()
    _verify_external_audio_tools(_ffmpeg, ffprobe)
    if _CHILD_JOB_FALLBACK_REASON:
        progress_cb(_CHILD_JOB_FALLBACK_REASON, 1, 1)
    progress_cb("Checking dependencies...", 1, 1)

    progress_cb("Scanning release folders...", 0, 1)
    releases: List[Release] = []
    if existing is not None:
        releases = discover_releases(existing, "existing", 0)
    for root in extra_existing:
        releases += discover_releases(root, "existing", len(releases))
    releases += discover_releases(recycle, "recycle", len(releases))
    for root in extra_recycle:
        releases += discover_releases(root, "recycle", len(releases))
    progress_cb("Scanning release folders...", 1, 1)

    tracks = [t for r in releases for t in r.tracks]
    errors: List[str] = []
    probe_workers = min(len(tracks) or 1, _probe_workers(io_workers))
    progress_cb(f"Reading tags and durations ({probe_workers} workers)...", 0, max(1, len(tracks)))
    with ThreadPoolExecutor(max_workers=probe_workers) as ex:
        futures = {ex.submit(probe_track, ffprobe, t): t for t in tracks}
        done = 0
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                fut.result()
            except Exception as e:
                errors.append(f"Probe error: {t.path}: {e}")
            done += 1
            progress_cb(f"Reading tags and durations ({probe_workers} workers)...", done, len(tracks))

    finalize_release_metadata(releases)
    bad_totals = validate_release_track_totals(releases)
    if bad_totals:
        for rel in releases:
            for issue in rel.validation_issues:
                errors.append(f"INCOMPLETE / inconsistent release: {rel.path}: {issue}")
    # FFprobe only verifies headers and tags. The full FFmpeg pass catches
    # decoding faults far into a file, such as the user's corrupted Privilege FLAC.
    ffmpeg, _ffprobe_again = ensure_ffmpeg()
    errors.extend(verify_audio_integrity(ffmpeg, tracks, io_workers, progress_cb))

    # Remix/Live classification happens in analyze_prepared(). CD-log work is
    # deliberately deferred until then so completely eliminated releases take
    # no further part.
    #
    # Store probe failures for the continuation stage.
    if errors and tracks:
        tracks[0].tags["__ANALYZER_PREPARE_ERRORS__"] = json.dumps(errors, ensure_ascii=False)
    return releases, tracks


def analyze_prepared(
    releases: List[Release],
    tracks: List[Track],
    use_fingerprint: bool,
    progress_cb,
    exclude_remixes: bool = True,
    exclude_live: bool = True,
    excluded_pattern_keys: Optional[Set[str]] = None,
    comparison_log_path: Optional[Path] = None,
    personal_keep_rules: Optional[List[Dict[str, str]]] = None,
    io_workers: Optional[int] = None,
    pattern_categories: Optional[Dict[str, Dict[str, str]]] = None,
) -> Tuple[List[Release], List[Track], Dict[int, List[int]], Set[int], List[Dict[str, object]], List[str]]:
    errors: List[str] = []
    if tracks:
        packed_errors = tracks[0].tags.pop("__ANALYZER_PREPARE_ERRORS__", "")
        if packed_errors:
            try:
                errors.extend(json.loads(packed_errors))
            except Exception:
                pass

    # Step 1: classify Remix/Live and eliminate globally unwanted material
    # before any expensive quality/fingerprint/comparison stage.
    progress_cb("Classifying wanted audio...", 0, max(1, len(tracks)))
    configure_exclusions(
        releases, exclude_remixes, exclude_live, personal_keep_rules,
        _load_pattern_categories() if pattern_categories is None else pattern_categories,
    )
    active_categories = _load_pattern_categories() if pattern_categories is None else pattern_categories
    permanent_skips = {key for key, item in _normalize_pattern_categories(active_categories).items()
                       if item["kind"] == "skip"}
    apply_pattern_exclusions(releases, set(excluded_pattern_keys or set()) | permanent_skips)
    explicit_clean_removed = apply_explicit_over_clean_policy(releases)
    if explicit_clean_removed:
        errors.append(
            f"Explicit>Clean policy removed {explicit_clean_removed} clean track(s) from coverage."
        )
    for index, track in enumerate(tracks, 1):
        track.base_excluded_from_coverage = bool(track.exclude_from_coverage)
        track.manual_skip_rule = ""
        # Do not erase excluded audio identities: the same recording may
        # appear under a different title, release, or Live/Remix descriptor.
        if index % 100 == 0 or index == len(tracks):
            progress_cb("Classifying wanted audio...", index, max(1, len(tracks)))
    if not tracks:
        progress_cb("Classifying wanted audio...", 1, 1)

    refresh_heuristic_release_types(releases)

    # Entirely eliminated releases are retained only as filesystem bookkeeping
    # for the final Apply/move stage. They do not receive quality analysis.
    active_releases = [rel for rel in releases if not rel.excluded_only]
    score_cd_rip_logs(active_releases, progress_cb, errors)

    fpcalc = ensure_fpcalc() if use_fingerprint else None
    if use_fingerprint and fpcalc:
        fingerprint_tracks = _fingerprint_identity_candidates(tracks)
        fp_workers = min(len(fingerprint_tracks) or 1, _fingerprint_workers(io_workers))
        label = f"Generating Chromaprint fingerprints ({fp_workers} workers)..."
        progress_cb(label, 0, max(1, len(fingerprint_tracks)))
        if fingerprint_tracks:
            with ThreadPoolExecutor(max_workers=fp_workers) as ex:
                futures = {ex.submit(chromaprint_fingerprint, fpcalc, t): t for t in fingerprint_tracks}
                done = 0
                for fut in as_completed(futures):
                    t = futures[fut]
                    try:
                        t.fingerprint, t.fingerprint_duration = fut.result()
                        if t.fingerprint_repaired:
                            errors.append(
                                f"Recovered incomplete fingerprint via FFmpeg PCM: {t.path}"
                            )
                    except Exception as e:
                        errors.append(f"Fingerprint error: {t.path}: {e}")
                    done += 1
                    progress_cb(label, done, len(fingerprint_tracks))
        else:
            progress_cb(label, 1, 1)

    groups, merge_notes, reviews = merge_equivalent_tracks(
        tracks,
        progress_cb,
        comparison_log_path,
    )
    errors.extend(merge_notes)

    compilation_removed = apply_compilation_policy(releases)
    if compilation_removed:
        errors.append(
            f"Compilation policy removed {compilation_removed} non-unique compilation track(s) from coverage."
        )

    progress_cb("Applying saved track skips...", 0, 1)
    apply_persistent_track_skips(tracks)
    progress_cb("Applying saved track skips...", 1, 1)

    progress_cb("Optimizing release set...", 0, 1)
    committed_blocked_ids = {
        rel.rid for rel in releases
        if _manual_album_group_path_key(rel.path) in _load_manual_ignored_release_paths()
    }
    selected = optimize_collection(
        releases,
        groups,
        blocked_release_ids=committed_blocked_ids,
        progress_cb=progress_cb,
        comparison_log_path=comparison_log_path,
        errors=errors,
    )
    progress_cb("Optimizing release set...", 1, 1)
    progress_cb("Building automatic action plan...", 1, 1)
    return releases, tracks, groups, selected, reviews, errors


def analyze(
    existing: Optional[Path],
    recycle: Path,
    use_fingerprint: bool,
    progress_cb,
    exclude_remixes: bool = True,
    exclude_live: bool = True,
    excluded_pattern_keys: Optional[Set[str]] = None,
    logging_enabled: bool = False,
    personal_keep_rules: Optional[List[Dict[str, str]]] = None,
) -> Tuple[List[Release], List[Track], Dict[int, List[int]], Set[int], List[Tuple[int, int, str]], List[str]]:
    releases, tracks = prepare_analysis(existing, recycle, progress_cb)
    comparison_log_path = _new_comparison_log_path(recycle) if (use_fingerprint and logging_enabled) else None
    return analyze_prepared(
        releases,
        tracks,
        use_fingerprint,
        progress_cb,
        exclude_remixes,
        exclude_live,
        excluded_pattern_keys,
        comparison_log_path,
        personal_keep_rules,
    )


@dataclass
class ReleaseDecision:
    release_id: int
    action: str
    reason: str
    essential_tracks: List[str] = field(default_factory=list)
    related_release_ids: List[int] = field(default_factory=list)
    decision_factors: List[str] = field(default_factory=list)


def _selected_group_union(releases: List[Release], selected: Set[int], exclude: Optional[int] = None) -> Set[int]:
    out: Set[int] = set()
    for r in releases:
        if r.rid in selected and r.rid != exclude:
            out |= r.groups
    return out



def _related_replacement_release(new: Release, old: Release) -> bool:
    """Link a removed OLD edition to a selected NEW edition using proven audio.

    Keep earlier album-title/family and single/EP compatibility paths, but
    recognize an acoustically verified expanded album even when provider titles
    and folder-derived album-family names differ.
    """
    same_title = normalize_title(new.title) == normalize_title(old.title)
    if new.release_type == "album" and old.release_type == "album":
        return bool(
            same_title
            or (new.family and new.family == old.family)
            or _album_editions_related_by_audio(new, old)
        )
    return same_title


def build_release_decisions(
    releases: List[Release],
    tracks: List[Track],
    selected: Set[int],
    reviews,
    blocked_release_ids: Optional[Set[int]] = None,
) -> List[ReleaseDecision]:
    selected_rels = [r for r in releases if r.rid in selected]
    selected_groups = _selected_group_union(releases, selected)
    blocked = set(blocked_release_ids or set())
    active = [r for r in releases if r.rid not in blocked]
    cd_anchor_ids: Set[int] = set()
    for family in _album_clusters([
        r for r in active if r.release_type == "album" and not r.excluded_only
    ]):
        allowed = _album_requirement_provider_ids(family, active)
        if allowed and all(source_rank(next(r for r in active if r.rid == rid)) >= 2 for rid in allowed):
            cd_anchor_ids.update(allowed)

    existing_groups: Set[int] = set()
    for r in releases:
        if r.root_kind == "existing":
            existing_groups |= r.groups

    decisions: List[ReleaseDecision] = []
    blocked = set(blocked_release_ids or set())

    for rel in releases:
        if rel.rid in blocked:
            covered_groups = rel.groups & selected_groups
            uncovered_groups = rel.groups - selected_groups

            orphan_titles: List[str] = []
            seen_orphans: Set[str] = set()
            for track in rel.tracks:
                if track.exclude_from_coverage or _track_coverage_gid(track) not in uncovered_groups:
                    continue
                key = normalize_title(track.display_title)
                if key not in seen_orphans:
                    seen_orphans.add(key)
                    orphan_titles.append(track.display_title)

            selected_by_id = {other.rid: other for other in selected_rels}
            cover_ids = sorted(
                (
                    other.rid
                    for other in selected_rels
                    if other.rid != rel.rid and bool(rel.groups & other.groups)
                ),
                key=lambda rid: (
                    -len(rel.groups & selected_by_id[rid].groups),
                    selected_by_id[rid].path.name.casefold(),
                ),
            )

            action = "REMOVE" if rel.root_kind == "existing" else "SKIP"
            if uncovered_groups:
                reason = (
                    "Manually removed in Decision Map and collection re-optimized. "
                    f"WARNING: {len(uncovered_groups)} recording group(s) are not available "
                    "from any other retained release."
                )
            else:
                reason = (
                    "Manually removed in Decision Map and collection re-optimized. "
                    "All included recordings were reassigned to other retained releases."
                )

            decisions.append(
                ReleaseDecision(
                    release_id=rel.rid,
                    action=action,
                    reason=reason,
                    essential_tracks=orphan_titles,
                    related_release_ids=cover_ids,
                    decision_factors=[
                        "Manual Decision Map removal is an explicit user constraint.",
                        f"Recording groups reassigned elsewhere: {len(covered_groups)}.",
                        f"Recording groups with no retained replacement: {len(uncovered_groups)}.",
                    ],
                )
            )
            continue

        # A release containing only tracks excluded by the active checkboxes is
        # automatically removed/skipped. Mixed releases can still be retained for
        # unique included audio.
        if rel.excluded_only and rel.rid not in selected:
            action = "REMOVE" if rel.root_kind == "existing" else "SKIP"
            kinds = []
            if any(t.is_remix for t in rel.tracks):
                kinds.append("remix")
            if any(t.is_live for t in rel.tracks):
                kinds.append("live")
            if any(t.manual_skip_rule for t in rel.tracks):
                kinds.append("saved track skip")
            pattern_keys = sorted({t.excluded_by_pattern for t in rel.tracks if t.excluded_by_pattern})
            if pattern_keys:
                kinds.append("pattern: " + "; ".join(pattern_keys))
            label = "/".join(kinds) if kinds else "excluded"
            excluded_count = rel.ignored_track_count
            if (
                rel.remix_only
                and all(
                    not track.is_live
                    and not track.manual_skip_rule
                    and not track.excluded_by_pattern
                    and not track.remix_feature_exception
                    for track in rel.tracks
                )
            ):
                exclusion_reason = f"All {excluded_count} tracks excluded (Save Remixes OFF)."
            elif all(track.is_live for track in rel.tracks):
                exclusion_reason = f"All {excluded_count} tracks excluded (Save Live OFF)."
            else:
                exclusion_reason = (
                    f"All {excluded_count} tracks excluded by current options ({label})."
                )
            decisions.append(
                ReleaseDecision(
                    release_id=rel.rid,
                    action=action,
                    reason=exclusion_reason,
                    essential_tracks=[],
                    decision_factors=[
                        f"Included tracks after options: {rel.included_track_count}",
                        f"Skipped tracks by options/patterns: {rel.ignored_track_count}",
                    ],
                )
            )
            continue

        other_selected_groups = _selected_group_union(releases, selected, exclude=rel.rid)
        essential_groups = rel.groups - other_selected_groups if rel.rid in selected else set()

        essential_tracks: List[str] = []
        seen_titles: Set[str] = set()
        for t in rel.tracks:
            if _track_coverage_gid(t) in essential_groups:
                key = normalize_title(t.display_title)
                if key not in seen_titles:
                    seen_titles.add(key)
                    essential_tracks.append(t.display_title)

        if rel.rid in selected:
            if rel.root_kind == "existing":
                action = "KEEP"
                if rel.rid in cd_anchor_ids:
                    reason = (
                        "Keep: CD-priority album anchor."
                        + (f" {len(essential_tracks)} recording(s) also depend on this release."
                           if essential_tracks else
                           " Distinct bonus/featured recordings remain separately protected.")
                    )
                elif essential_tracks:
                    reason = f"Keep: {len(essential_tracks)} recording(s) are not covered by any other retained release."
                elif rel.release_type == "album":
                    reason = "Keep: required album representation in the minimum-track solution."
                else:
                    reason = "Keep: selected by the automatic minimum-track coverage solution."
            else:
                replaced = [
                    r for r in releases
                    if r.root_kind == "existing"
                    and r.rid not in selected
                    and r.groups
                    and r.groups <= rel.groups
                    and _related_replacement_release(rel, r)
                ]
                if replaced:
                    action = "REPLACE"
                    upgrade_bits = [
                        bit for bit in (_release_upgrade_reason(rel, old) for old in replaced)
                        if bit
                    ]
                    if upgrade_bits:
                        reason = (
                            "Upgrade existing release: "
                            + "; ".join(dict.fromkeys(upgrade_bits))
                            + ". Replaces: "
                            + "; ".join(r.path.name for r in replaced[:4])
                        )
                    else:
                        reason = "Replace existing edition with: " + rel.path.name
                else:
                    action = "ADD"
                    if essential_tracks:
                        preview = ", ".join(essential_tracks[:4])
                        if len(essential_tracks) > 4:
                            preview += f", +{len(essential_tracks)-4} more"
                        reason = (
                            f"Add: {len(essential_tracks)} recording(s) are supplied only by this "
                            "retained release in the current plan"
                        )
                        if preview:
                            reason += f": {preview}"
                    elif rel.release_type == "album":
                        reason = (
                            "Add: this is the selected edition representing the album after "
                            "collection-wide optimization; its included recordings are covered "
                            "elsewhere in the retained set."
                        )
                    else:
                        reason = "Add: selected by the global minimum-track coverage solution."
        else:
            covered = (bool(rel.groups) and rel.groups <= selected_groups) or (not rel.groups and rel.excluded_only)
            if covered:
                action = "REMOVE" if rel.root_kind == "existing" else "SKIP"
                covers: List[str] = []
                for gid in sorted(rel.groups):
                    candidates = [r for r in selected_rels if gid in r.groups]
                    if candidates:
                        best = min(
                            candidates,
                            key=lambda r: (r.included_track_count, -_explicit_rank(r), -source_rank(r), 0 if r.root_kind == "existing" else 1),
                        )
                        if best.path.name not in covers:
                            covers.append(best.path.name)
                reason = "All recordings are covered by retained releases."
                if covers:
                    reason += " Covered by: " + "; ".join(covers[:5])
            else:
                # Defensive fail-safe. If the optimizer ever produces a non-selected
                # release with uncovered groups, do not ask the user to investigate;
                # retain it automatically so unique material cannot be lost.
                action = "KEEP" if rel.root_kind == "existing" else "ADD"
                reason = "Conservative fallback: contains material not proven covered elsewhere, so it is retained automatically."

        related_release_ids: List[int] = []
        factors: List[str] = []

        if rel.rid in selected:
            if rel.rid in cd_anchor_ids:
                factors.append("CD-priority full-album anchor: preferred over smaller WEB editions; unique bonus/featured recordings still require verified providers.")
            if essential_tracks:
                factors.append(f"{len(essential_tracks)} eligible recording(s) depend on this release in the retained set.")
            elif rel.release_type == "album":
                factors.append(
                    f"Album representation requires a most-complete edition; this edition carries "
                    f"{_album_unique_track_count(rel)} distinct included wanted recording group(s)."
                )
            else:
                factors.append("Chosen by the global minimum-track/minimum-release coverage solution.")

            personal_matches = [
                t.display_title for t in rel.tracks
                if t.personal_keep_rule and not t.exclude_from_coverage
            ]
            if personal_matches:
                factors.append(f"Personal Picks matched {len(personal_matches)} currently included track(s).")

            new_groups_for_factor = rel.groups - existing_groups
            if rel.root_kind == "recycle" and new_groups_for_factor:
                factors.append(
                    f"{len(new_groups_for_factor)} included recording group(s) are not present in the pre-analysis existing discography."
                )

            if action == "REPLACE":
                related_release_ids = [
                    r.rid for r in releases
                    if r.root_kind == "existing"
                    and r.rid not in selected
                    and r.groups
                    and r.groups <= rel.groups
                    and _related_replacement_release(rel, r)
                ]
        else:
            if covered:
                cover_ids: List[int] = []
                for gid in sorted(rel.groups):
                    candidates = [r for r in selected_rels if gid in r.groups]
                    if not candidates:
                        continue
                    best = min(
                        candidates,
                        key=lambda r: (
                            r.included_track_count,
                            -_explicit_rank(r),
                            -source_rank(r),
                            0 if r.root_kind == "existing" else 1,
                        ),
                    )
                    if best.rid not in cover_ids:
                        cover_ids.append(best.rid)
                related_release_ids = cover_ids
                factors.append(f"All {len(rel.groups)} included recording group(s) are covered by retained releases.")
            else:
                factors.append("Conservative safety fallback: at least one recording group was not proven covered.")

        factors.append(
            f"Included tracks: {rel.included_track_count}; skipped by remix/live/pattern options: {rel.ignored_track_count}."
        )

        decisions.append(
            ReleaseDecision(
                release_id=rel.rid,
                action=action,
                reason=reason,
                essential_tracks=essential_tracks,
                related_release_ids=related_release_ids,
                decision_factors=factors,
            )
        )

    return decisions

def action_summary(decisions: List[ReleaseDecision]) -> Dict[str, int]:
    counts = Counter(d.action for d in decisions)
    return {k: counts.get(k, 0) for k in ("ADD", "REPLACE", "REMOVE", "SKIP", "KEEP")}


def _release_source_description(rel: Release) -> str:
    if rel.has_cd_image and rel.has_rip_log:
        return "CD image + CUE + rip log"
    if rel.has_cd_image:
        return "CD image + CUE"
    if rel.has_cue and rel.has_rip_log:
        return "CD + CUE + rip log"
    if rel.has_cue:
        return "CUE-based CD"
    if rel.has_audiochecker:
        return "WEB / AudioChecker"
    return "WEB / unknown"


def _manual_track_skips_path() -> Path:
    _migrate_legacy_app_data()
    return _state_dir() / "manual_track_skips.json"


def _track_fingerprint_hash(track: Track) -> str:
    if not track.fingerprint:
        return ""
    digest = hashlib.sha256()
    for value in track.fingerprint:
        digest.update(struct.pack("<I", int(value) & 0xFFFFFFFF))
    return digest.hexdigest()


def _load_manual_track_skip_rules() -> List[Dict[str, object]]:
    path = _manual_track_skips_path()
    try:
        if not path.is_file():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("rules", []) if isinstance(data, dict) else []
        return [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _save_manual_track_skip_rules(rules: List[Dict[str, object]]) -> None:
    _atomic_write_json(
        _manual_track_skips_path(),
        {
            "app": APP_NAME,
            "version": APP_VERSION,
            "schema_version": 3,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "rules": rules,
        },
    )


def _track_instance_key(track: Track) -> str:
    """Stable identity for one physical track instance, never its audio group."""
    raw_path = os.path.normcase(os.path.normpath(str(track.path or "")))
    cue_path = os.path.normcase(os.path.normpath(str(track.cue_path or "")))
    return "|".join(
        (
            raw_path,
            cue_path,
            str(int(track.cue_track_number or 0)),
            f"{float(track.cue_start_seconds or 0.0):.6f}",
            str(int(track.index or 0)),
        )
    )


def _manual_skip_rule_matches_track(rule: Dict[str, object], track: Track) -> bool:
    """Match original instance evidence OR verified fingerprint evidence.

    A shared song title is never sufficient. Fingerprint evidence is
    duration-checked to avoid claiming a different-length Version is the
    same recording if a fingerprint vector happens to be identical.
    """
    key = _track_instance_key(track)
    if key and key in (rule.get("instance_keys") or []):
        return True
    fingerprint_evidence = rule.get("fingerprint_evidence", [])
    if not track.fingerprint or not isinstance(fingerprint_evidence, list):
        return False
    digest = _track_fingerprint_hash(track)
    for item in fingerprint_evidence:
        if not isinstance(item, dict) or item.get("sha256") != digest:
            continue
        try:
            saved_duration = float(item.get("duration_seconds", 0.0) or 0.0)
        except (ValueError, TypeError, OverflowError):
            continue
        if (
            math.isfinite(saved_duration) and saved_duration > 0
            and math.isfinite(track.duration) and track.duration > 0
            and not _duration_version_conflict(saved_duration, track.duration)
        ):
            return True
    return False


def _manual_track_group_members(track: Track, tracks: List[Track]) -> List[Track]:
    """All acoustically proved copies, never the same-title other versions."""
    gid = int(track.group_id)
    if gid >= 0:
        return [candidate for candidate in tracks if candidate.group_id == gid]
    return [track]


def apply_persistent_track_skips(tracks: List[Track]) -> int:
    """Exclude ALL verified copies of each manually ignored audio recording.

    Legacy schema-2 exact-instance rules are promoted to acoustic-group
    scope when their saved instance is still present. New schema-3 rules
    can also find the group in future scans by saved member fingerprints.
    """
    for track in tracks:
        track.manual_skip_rule = ""
        track.exclude_from_coverage = bool(track.base_excluded_from_coverage)

    rules = _load_manual_track_skip_rules()
    if not rules:
        return 0

    groups: Dict[int, List[int]] = defaultdict(list)
    instance_index: Dict[str, List[int]] = defaultdict(list)
    fingerprint_index: Dict[str, List[int]] = defaultdict(list)
    has_audio_rules = any(rule.get("fingerprint_evidence") for rule in rules)
    for i, track in enumerate(tracks):
        instance_index[_track_instance_key(track)].append(i)
        if track.group_id >= 0:
            groups[int(track.group_id)].append(i)
        if has_audio_rules and track.fingerprint:
            fingerprint_index[_track_fingerprint_hash(track)].append(i)

    # Index lookup avoids rehashing every fingerprint for each saved rule.
    # Expand only positively matched instances/recordings to their verified
    # acoustic group; never use title, performer, or replaceable-version ID.
    for rule in rules:
        rule_id = str(rule.get("id", "")).strip()
        if not rule_id:
            continue
        direct: Set[int] = set()
        for key in (rule.get("instance_keys") or []):
            direct.update(instance_index.get(str(key), []))
        for evidence in (rule.get("fingerprint_evidence") or []):
            if not isinstance(evidence, dict):
                continue
            raw_hash = str(evidence.get("sha256", ""))
            try:
                saved_duration = float(evidence.get("duration_seconds", 0) or 0)
            except (ValueError, TypeError, OverflowError):
                continue
            if not math.isfinite(saved_duration) or saved_duration <= 0:
                continue
            for i in fingerprint_index.get(raw_hash, []):
                current = tracks[i].duration
                if (
                    math.isfinite(current) and current > 0
                    and not _duration_version_conflict(saved_duration, current)
                ):
                    direct.add(i)
        matched: Set[int] = set()
        for i in direct:
            gid = int(tracks[i].group_id)
            if gid >= 0:
                matched.update(groups[gid])
            else:
                matched.add(i)
        for i in matched:
            track = tracks[i]
            if not track.manual_skip_rule:
                track.manual_skip_rule = rule_id
            track.exclude_from_coverage = True
    return sum(bool(track.manual_skip_rule) for track in tracks)


def add_persistent_track_skip(track: Track, tracks: List[Track]) -> str:
    """One user Ignore applies to every matched source for the recording."""
    peers = _manual_track_group_members(track, tracks)
    instance_keys = sorted({_track_instance_key(peer) for peer in peers})
    evidence = [
        {"sha256": _track_fingerprint_hash(peer),
         "duration_seconds": round(float(peer.duration or 0.0), 6)}
        for peer in peers if peer.fingerprint
    ]
    # Store all known acoustic members so re-scans can recognize copies even
    # when source paths or encoded fingerprints differ among masterings.
    evidence = sorted(
        {(_entry["sha256"], _entry["duration_seconds"]) for _entry in evidence}
    )
    fingerprint_evidence = [
        {"sha256": digest, "duration_seconds": seconds}
        for digest, seconds in evidence
    ]
    seed = (
        _track_fingerprint_hash(track) + "|" + f"{float(track.duration):.6f}"
        if track.group_id >= 0 and track.fingerprint
        else _track_instance_key(track)
    )
    rule_id = "skip-recording-" + hashlib.sha256(
        seed.encode("utf-8")
    ).hexdigest()[:20]
    rules = _load_manual_track_skip_rules()
    if not any(str(row.get("id", "")) == rule_id for row in rules):
        rules.append({
            "id": rule_id,
            "schema": 3,
            "scope": "recording" if track.group_id >= 0 else "instance",
            "label": track.display_title,
            "artist": track.artist,
            "created": datetime.now().isoformat(timespec="seconds"),
            "instance_keys": instance_keys,
            "fingerprint_evidence": fingerprint_evidence,
        })
        _save_manual_track_skip_rules(rules)
    # Apply through the same path used by a new scan so UI and saved state
    # always agree, even if the user had older overlapping instance rules.
    apply_persistent_track_skips(tracks)
    return rule_id


def remove_persistent_track_skip(rule_id: str, tracks: List[Track]) -> None:
    """Restore the acoustic group, including overlapping legacy rules."""
    targeted = [
        track for track in tracks
        if str(track.manual_skip_rule or "") == str(rule_id or "")
    ]
    group_ids = {
        track.group_id for track in targeted if track.group_id >= 0
    }
    targeted_ids = {id(track) for track in targeted}
    peer_keys = {
        _track_instance_key(track) for track in tracks
        if (track.group_id >= 0 and track.group_id in group_ids)
        or id(track) in targeted_ids
    }
    ids_to_remove = {str(rule_id or "")}
    group_peers = [
        track for track in tracks
        if track.group_id >= 0 and track.group_id in group_ids
    ]
    for rule in _load_manual_track_skip_rules():
        if any(key in peer_keys for key in (rule.get("instance_keys") or [])):
            ids_to_remove.add(str(rule.get("id", "")))
        elif any(
            _manual_skip_rule_matches_track(rule, track) for track in group_peers
        ):
            ids_to_remove.add(str(rule.get("id", "")))
    rules = [
        rule for rule in _load_manual_track_skip_rules()
        if str(rule.get("id", "")) not in ids_to_remove
    ]
    _save_manual_track_skip_rules(rules)
    apply_persistent_track_skips(tracks)


def _decision_snapshot_path() -> Path:
    _migrate_legacy_app_data()
    return _state_dir() / "last_decision_map.json"


def _save_decision_snapshot(items: List[Dict[str, object]]) -> None:
    try:
        _atomic_write_json(
            _decision_snapshot_path(),
            {
                "app": APP_NAME,
                "version": APP_VERSION,
                "generated": datetime.now().isoformat(timespec="seconds"),
                "releases": items,
            },
        )
    except Exception:
        pass


def _load_decision_snapshot() -> List[Dict[str, object]]:
    path = _decision_snapshot_path()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            releases = data.get("releases", []) if isinstance(data, dict) else []
            if isinstance(releases, list):
                return [item for item in releases if isinstance(item, dict)]
    except Exception:
        pass
    return []


def _duration_display(seconds: float) -> str:
    if seconds <= 0:
        return "?:??"
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _track_distinction_summary(
    track: Track,
    candidates: List[Track],
    by_release_id: Dict[int, Release],
) -> str:
    """Explain why same/similar titled tracks remain separate recording groups."""
    choices = [
        other
        for other in candidates
        if other is not track
        and other.release_id != track.release_id
        and other.group_id >= 0
        and other.group_id != track.group_id
    ]
    if not choices:
        return ""

    choices.sort(
        key=lambda other: (
            0 if identity_title(other.display_title) == identity_title(track.display_title) else 1,
            abs((track.duration or 0.0) - (other.duration or 0.0)),
            other.display_title.casefold(),
        )
    )
    other = choices[0]
    other_release = by_release_id.get(other.release_id)
    other_name = other_release.path.name if other_release is not None else other.album or "another release"
    audio_match, _sim = fingerprint_auto_match(track, other)
    semantic_conflict = _semantic_version_conflict(track, other)

    if audio_match and semantic_conflict:
        return (
            f"Acoustically matched '{other.display_title}' on {other_name}; "
            "metadata labels disagree. If groups differ, inspect duration "
            "coherence or other audio-group constraints, not track titles."
        )

    if _duration_version_conflict(track.duration, other.duration):
        delta = abs(track.duration - other.duration)
        substitution = (
            "Distinct audio edit but replaceable for collection coverage."
            if track.group_id >= 0
            and _track_coverage_gid(track) == _track_coverage_gid(other)
            else "Kept as a distinct wanted version."
        )
        return (
            f"Different-length version of '{other.display_title}' on {other_name}: "
            f"{_duration_display(track.duration)} vs {_duration_display(other.duration)} "
            f"(difference {delta:.1f}s). {substitution}"
        )

    if not audio_match:
        return (
            f"Different acoustic recording from '{other.display_title}' on {other_name}; "
            "Chromaprint did not meet the duplicate threshold."
        )

    # Under the automatic acoustic-identity policy, a non-semantic accepted
    # acoustic match should already belong to the same recording group.
    return ""


def build_decision_snapshot(
    releases: List[Release],
    tracks: List[Track],
    selected: Set[int],
    decisions: List[ReleaseDecision],
    blocked_release_ids: Optional[Set[int]] = None,
) -> List[Dict[str, object]]:
    """Build a compact explanation model for the visual Decision Map."""
    by_id = {r.rid: r for r in releases}
    by_decision = {d.release_id: d for d in decisions}
    selected_rels = [r for r in releases if r.rid in selected]
    selected_groups = _selected_group_union(releases, selected)
    blocked = set(blocked_release_ids or set())

    all_group_carriers: Dict[int, Set[int]] = defaultdict(set)
    eligible_group_carriers: Dict[int, Set[int]] = defaultdict(set)
    for carrier in releases:
        for gid in carrier.groups:
            all_group_carriers[gid].add(carrier.rid)
            if carrier.rid not in blocked:
                eligible_group_carriers[gid].add(carrier.rid)

    track_global_index = {id(track): index for index, track in enumerate(tracks)}
    same_title_index: Dict[str, List[Track]] = defaultdict(list)
    for candidate in tracks:
        key = _base_title_identity(candidate.display_title)
        if key:
            same_title_index[key].append(candidate)

    # Retained-but-excluded files may still be physically present in another
    # selected release. This metadata index informs the UI ONLY; it never
    # establishes acoustic identity or contributes to optimizer coverage.
    excluded_selected_by_title: Dict[str, List[Tuple[int, Track]]] = defaultdict(list)
    for other in selected_rels:
        for candidate in other.tracks:
            if candidate.exclude_from_coverage:
                title_key = identity_title(candidate.display_title)
                if title_key:
                    excluded_selected_by_title[title_key].append((other.rid, candidate))

    # Full-scan physical edition evidence differs from selected-plan
    # coverage and from acoustically verified duplicate groups.
    # Excluded files are metadata only: never promote to audio matches.
    physical_editions_by_key: Dict[Tuple[str, Tuple[str, ...]], List[Track]] = defaultdict(list)
    for candidate in tracks:
        if candidate.duration <= 0:
            continue
        candidate_title = identity_title(candidate.display_title)
        candidate_artists = tuple(sorted(_artist_signature(candidate.artist)))
        if candidate_title and candidate_artists:
            physical_editions_by_key[(candidate_title, candidate_artists)].append(candidate)

    snapshots: List[Dict[str, object]] = []

    for rel in releases:
        decision = by_decision[rel.rid]
        retained = decision.action in {"KEEP", "ADD", "REPLACE"}
        manual_removed = rel.rid in blocked

        track_titles_by_group: Dict[int, List[str]] = defaultdict(list)
        for track in rel.tracks:
            if track.exclude_from_coverage or track.group_id < 0:
                continue
            title = track.display_title
            coverage_gid = _track_coverage_gid(track)
            if title not in track_titles_by_group[coverage_gid]:
                track_titles_by_group[coverage_gid].append(title)

        coverage_rows: List[Dict[str, object]] = []
        if not retained and rel.groups:
            coverage_by_release: Dict[int, Set[int]] = defaultdict(set)
            for gid in sorted(rel.groups):
                candidates = [r for r in selected_rels if gid in r.groups]
                if not candidates:
                    continue
                best = min(
                    candidates,
                    key=lambda r: (
                        r.included_track_count,
                        -_explicit_rank(r),
                        -source_rank(r),
                        0 if r.root_kind == "existing" else 1,
                    ),
                )
                coverage_by_release[best.rid].add(gid)

            for cover_id, gids in sorted(
                coverage_by_release.items(),
                key=lambda item: (-len(item[1]), by_id[item[0]].path.name.casefold()),
            ):
                cover = by_id[cover_id]
                examples: List[str] = []
                for gid in sorted(gids):
                    for title in track_titles_by_group.get(gid, []):
                        if title not in examples:
                            examples.append(title)
                        if len(examples) >= 5:
                            break
                    if len(examples) >= 5:
                        break
                coverage_rows.append(
                    {
                        "release_id": cover_id,
                        "name": cover.path.name,
                        "action": by_decision.get(cover_id).action if cover_id in by_decision else "KEEP",
                        "groups": len(gids),
                        "examples": examples,
                    }
                )

        essential_groups = set()
        if retained:
            essential_groups = rel.groups - _selected_group_union(releases, selected, exclude=rel.rid)

        essential_examples: List[str] = []
        for gid in sorted(essential_groups):
            for title in track_titles_by_group.get(gid, []):
                if title not in essential_examples:
                    essential_examples.append(title)
                if len(essential_examples) >= 12:
                    break
            if len(essential_examples) >= 12:
                break

        personal_matches = [
            {
                "title": t.display_title,
                "rule": t.personal_keep_rule,
            }
            for t in rel.tracks
            if t.personal_keep_rule and not t.exclude_from_coverage
        ]

        ignored_counts = {
            "remix": sum(1 for t in rel.tracks if t.exclude_from_coverage and t.is_remix),
            "live": sum(1 for t in rel.tracks if t.exclude_from_coverage and t.is_live),
            "pattern": sum(1 for t in rel.tracks if t.exclude_from_coverage and bool(t.excluded_by_pattern)),
            "manual": sum(1 for t in rel.tracks if bool(t.manual_skip_rule)),
        }

        quality_bits: List[str] = []
        if rel.rip_log_paths:
            quality_bits.append(f"Rip log: {cd_rip_log_quality_text(rel)}")
        dynamic_summary = release_dynamic_summary(rel)
        if dynamic_summary.get("score") is not None:
            dyn_parts = [f"Dynamics score {float(dynamic_summary['score']):.2f}"]
            if dynamic_summary.get("lufs") is not None:
                dyn_parts.append(f"{float(dynamic_summary['lufs']):.1f} LUFS")
            if dynamic_summary.get("lra") is not None:
                dyn_parts.append(f"LRA {float(dynamic_summary['lra']):.1f}")
            if dynamic_summary.get("crest_db") is not None:
                dyn_parts.append(f"crest {float(dynamic_summary['crest_db']):.1f} dB")
            quality_bits.append("Mastering: " + " | ".join(dyn_parts))

        related: List[Dict[str, object]] = []
        for related_id in decision.related_release_ids:
            other = by_id.get(related_id)
            if other is None:
                continue
            related.append(
                {
                    "release_id": other.rid,
                    "name": other.path.name,
                    "action": by_decision.get(other.rid).action if other.rid in by_decision else "",
                    "source": _release_source_description(other),
                    "source_medium": other.source_medium,
                    "source_rank": source_rank(other),
                    "root_kind": other.root_kind,
                    "scan_root": str(other.scan_root or ""),
                    "included_tracks": other.counted_track_count,
                    "upgrade_reason": _release_upgrade_reason(rel, other),
                }
            )

        tracklist: List[Dict[str, object]] = []
        for fallback_number, track in enumerate(rel.tracks, start=1):
            included = not track.exclude_from_coverage and track.group_id >= 0
            coverage_gid = _track_coverage_gid(track)
            eligible_carriers = eligible_group_carriers.get(coverage_gid, set())
            available_elsewhere = bool(
                included and any(rid != rel.rid for rid in eligible_carriers)
            )
            covering_releases = [
                other
                for other in selected_rels
                if other.rid != rel.rid and track.group_id >= 0 and coverage_gid in other.groups
            ]
            covering_releases.sort(
                key=lambda other: (
                    other.included_track_count,
                    -_explicit_rank(other),
                    -source_rank(other),
                    0 if other.root_kind == "existing" else 1,
                    other.path.name.casefold(),
                )
            )
            covered_by_other_retained = bool(covering_releases)
            # A replaceable edit can satisfy coverage while its true acoustic
            # group ID and length badge remain distinct.
            covered_by_alternate_version = bool(
                covering_releases
                and not any(
                    candidate.group_id == track.group_id
                    and not candidate.exclude_from_coverage
                    for cover in covering_releases for candidate in cover.tracks
                )
            )
            orphaned = bool(
                manual_removed
                and included
                and not available_elsewhere
            )
            unique_to_release = bool(
                retained and included and coverage_gid in essential_groups
            )
            excluded_counterparts: List[str] = []
            if unique_to_release and track.duration > 0:
                artist_key = _artist_signature(track.artist)
                for other_id, candidate in excluded_selected_by_title.get(
                    identity_title(track.display_title), []
                ):
                    if (
                        other_id != rel.rid
                        and artist_key
                        and artist_key == _artist_signature(candidate.artist)
                        and candidate.duration > 0
                        and abs(float(track.duration) - float(candidate.duration)) <= 1.0
                    ):
                        other_name = by_id[other_id].path.name
                        if other_name not in excluded_counterparts:
                            excluded_counterparts.append(other_name)
            # Search ALL scanned editions, not only optimizer selections.
            # Only equal real acoustic groups establish verified audio copies.
            audio_edition_ids: Set[int] = set()
            unverified_edition_ids: Set[int] = set()
            if included and track.duration > 0:
                physical_key = (
                    identity_title(track.display_title),
                    tuple(sorted(_artist_signature(track.artist))),
                )
                for counterpart in physical_editions_by_key.get(physical_key, []):
                    if (
                        counterpart.release_id == rel.rid
                        or abs(float(track.duration) - float(counterpart.duration)) > 1.0
                    ):
                        continue
                    if (
                        not counterpart.exclude_from_coverage
                        and counterpart.group_id >= 0
                        and counterpart.group_id == track.group_id
                    ):
                        audio_edition_ids.add(counterpart.release_id)
                    else:
                        unverified_edition_ids.add(counterpart.release_id)
            unverified_edition_ids.difference_update(audio_edition_ids)
            base_key = _base_title_identity(track.display_title)
            distinction = ""
            if included and not covered_by_other_retained and base_key:
                distinction = _track_distinction_summary(
                    track,
                    same_title_index.get(base_key, []),
                    by_id,
                )
            track_number = _track_number_key(track)
            tracklist.append(
                {
                    "number": track_number if track_number is not None else fallback_number,
                    "title": track.display_title,
                    "artist": track.artist,
                    "album": track.album,
                    "duration": _duration_display(track.duration),
                    "duration_seconds": round(track.duration, 3),
                    "path": str(track.path),
                    "track_global_index": track_global_index.get(id(track), -1),
                    "group_id": track.group_id,
                    "coverage_group_id": coverage_gid,
                    "version_substitution": bool(track.group_id >= 0 and coverage_gid != track.group_id),
                    "included": included,
                    "integrity_error": str(track.integrity_error),
                    "excluded": bool(track.exclude_from_coverage),
                    "exclusion_reason": str(track.excluded_by_pattern or ""),
                    "explicit_state": str(track.explicit or "unknown"),
                    "manual_skip": bool(track.manual_skip_rule),
                    "manual_skip_rule": track.manual_skip_rule,
                    "available_elsewhere": available_elsewhere,
                    "covered_by_other_retained": covered_by_other_retained,
                    "covered_by_alternate_version": covered_by_alternate_version,
                    "covered_by_names": [other.path.name for other in covering_releases[:8]],
                    "replacement_source": (
                        covering_releases[0].path.name
                        if manual_removed and included and covering_releases
                        else ""
                    ),
                    "replacement_alternates": (
                        [other.path.name for other in covering_releases[1:8]]
                        if manual_removed and included
                        else []
                    ),
                    "unique_to_release": unique_to_release,
                    "excluded_counterparts": excluded_counterparts[:6],
                    "audio_match_editions": len(audio_edition_ids),
                    "unverified_editions": len(unverified_edition_ids),
                    "orphaned": orphaned,
                    "distinction": distinction,
                    "base_title_key": base_key,
                    "is_remix": bool(track.is_remix),
                    "is_live": bool(track.is_live),
                    "dynamic_lufs": track.dynamic_lufs,
                    "dynamic_lra": track.dynamic_lra,
                    "dynamic_true_peak_dbfs": track.dynamic_true_peak_dbfs,
                    "dynamic_rms_dbfs": track.dynamic_rms_dbfs,
                    "dynamic_crest_db": track.dynamic_crest_db,
                    "dynamic_score": track.dynamic_score,
                }
            )

        affected_ids: Set[int] = set()
        for gid in rel.groups:
            affected_ids |= all_group_carriers.get(gid, set())
        affected_ids.discard(rel.rid)

        affected: List[Dict[str, object]] = []
        for other_id in affected_ids:
            other = by_id.get(other_id)
            if other is None:
                continue
            overlap = rel.groups & other.groups
            if not overlap:
                continue
            examples: List[str] = []
            for gid in sorted(overlap):
                for title in track_titles_by_group.get(gid, []):
                    if title not in examples:
                        examples.append(title)
                    if len(examples) >= 5:
                        break
                if len(examples) >= 5:
                    break
            other_decision = by_decision.get(other.rid)
            affected.append(
                {
                    "release_id": other.rid,
                    "name": other.path.name,
                    "action": other_decision.action if other_decision is not None else "",
                    "outcome": (
                        "RETAINED"
                        if other_decision is not None
                        and other_decision.action in {"KEEP", "ADD", "REPLACE"}
                        else "MANUALLY REMOVED"
                        if other.rid in blocked
                        else "DUPLICATE"
                    ),
                    "shared_groups": len(overlap),
                    "examples": examples,
                    "manual_removed": other.rid in blocked,
                }
            )
        affected.sort(
            key=lambda row: (
                -int(row.get("shared_groups", 0)),
                str(row.get("name", "")).casefold(),
            )
        )

        # Show exact/same-coverage alternatives as supporting context without
        # pretending that metadata alone created the duplicate relationship.
        alternatives: List[Dict[str, object]] = []
        for other in releases:
            if other.rid == rel.rid or not rel.groups or not other.groups:
                continue
            same_family = (
                (rel.release_type == "album" and other.release_type == "album" and rel.family and rel.family == other.family)
                or normalize_title(rel.title) == normalize_title(other.title)
            )
            if not same_family:
                continue
            if rel.groups == other.groups:
                alternatives.append(
                    {
                        "release_id": other.rid,
                        "name": other.path.name,
                        "action": by_decision.get(other.rid).action if other.rid in by_decision else "",
                        "source": _release_source_description(other),
                        "included_tracks": other.counted_track_count,
                        "root_kind": other.root_kind,
                    }
                )
        alternatives = alternatives[:8]

        outcome = "MANUALLY REMOVED" if manual_removed else ("RETAINED" if retained else "DUPLICATE")
        audit_issues = list(rel.validation_issues)
        audit_issues.extend(
            f"Corrupt/unreadable {track.path.name}: {_short_integrity_reason(track.integrity_error)}"
            for track in rel.tracks if track.integrity_error
        )
        snapshots.append(
            {
                "release_id": rel.rid,
                "name": rel.path.name,
                "path": str(rel.path),
                "root_kind": rel.root_kind,
                "scan_root": str(rel.scan_root or ""),
                "source_medium": rel.source_medium,
                "source_rank": source_rank(rel),
                "action": decision.action,
                "outcome": outcome,
                "reason": decision.reason,
                "audit_issues": audit_issues,
                "type_warning": _release_warning(rel),
                "release_type": rel.release_type,
                "family": rel.family,
                "source": _release_source_description(rel),
                "included_tracks": rel.counted_track_count,
                "ignored_tracks": rel.ignored_track_count,
                "total_tracks": rel.track_count,
                "recording_groups": len(rel.groups),
                "decision_factors": list(decision.decision_factors),
                "essential_tracks": list(decision.essential_tracks),
                "essential_examples": essential_examples,
                "personal_matches": personal_matches[:12],
                "ignored_counts": ignored_counts,
                "quality": quality_bits,
                "coverage": coverage_rows,
                "related": related,
                "alternatives": alternatives,
                "selected_group_coverage_complete": bool(rel.groups and rel.groups <= selected_groups),
                "manual_removed": manual_removed,
                "orphan_count": sum(1 for row in tracklist if bool(row.get("orphaned"))),
                "tracklist": tracklist,
                "affected": affected,
            }
        )

    return sorted(
        snapshots,
        key=lambda item: (
            0 if item.get("manual_removed") else 1 if item.get("outcome") == "DUPLICATE" else 2,
            str(item.get("name", "")).casefold(),
        ),
    )



LOSSLESS_CODECS = {"flac", "alac", "wavpack", "ape", "tta", "tak"}
LOSSLESS_EXTS = {".flac", ".wav", ".ape", ".wv"}


@dataclass
class IntraReleaseDuplicate:
    release_id: int
    redundant: Path
    keep: Path
    reason: str


def _track_number_key(track: Track) -> Optional[int]:
    if track.virtual_from_cue and track.cue_track_number:
        return track.cue_track_number
    raw = tag_lookup(track.tags, "tracknumber", "track", "trackno")
    match = re.search(r"\d+", raw or "")
    if match:
        return int(match.group())
    match = re.match(r"^\s*(\d{1,3})(?:\s*[-._)]\s*|\s+)", track.path.name)
    return int(match.group(1)) if match else None


def _track_codec_quality(track: Track) -> Tuple[int, int, int, int, int, int, int]:
    codec = (track.codec_name or "").lower()
    ext = track.path.suffix.lower()
    lossless = codec in LOSSLESS_CODECS or codec.startswith("pcm_") or (not codec and ext in LOSSLESS_EXTS)

    # FLAC/ALAC/WavPack/APE/PCM are equivalent lossless families here; the
    # technical stream parameters decide first, then a deterministic container
    # preference keeps FLAC when everything else is equal.
    codec_preference = {
        "flac": 60,
        "alac": 55,
        "wavpack": 50,
        "ape": 45,
        "tta": 44,
        "tak": 43,
        "pcm_s24le": 42,
        "pcm_s16le": 41,
        "opus": 35,
        "aac": 30,
        "vorbis": 25,
        "mp3": 20,
    }.get(codec, 10)
    ext_preference = {
        ".flac": 9, ".m4a": 8, ".wv": 7, ".ape": 6, ".wav": 5,
        ".opus": 4, ".ogg": 3, ".mp3": 2, ".aac": 1,
    }.get(ext, 0)

    return (
        1 if lossless else 0,
        track.sample_rate,
        track.bit_depth,
        track.channels,
        track.bit_rate if not lossless else 0,
        codec_preference,
        ext_preference,
    )


def _logical_title_keys(track: Track) -> Set[str]:
    """Possible logical-title identities used only as an intra-release safety gate.

    Duplicate identity is still the audio group. Using both tags and filename
    prevents a bad TITLE tag from blocking cleanup of obvious duplicate files.
    """
    keys: Set[str] = set()
    for value in (
        track.display_title,
        strip_track_number(track.path.stem),
        track.title,
    ):
        key = identity_title(value or "")
        if key:
            keys.add(key)
    return keys


def _same_logical_track(a: Track, b: Track) -> bool:
    if a.path.parent.resolve() != b.path.parent.resolve():
        return False
    if a.group_id < 0 or a.group_id != b.group_id:
        return False

    number_a = _track_number_key(a)
    number_b = _track_number_key(b)
    # Track position remains a hard safety gate. If one side has a number and
    # the other does not, keep both instead of guessing.
    if number_a is not None and number_b is not None:
        if number_a != number_b:
            return False
    elif number_a is not None or number_b is not None:
        return False

    # Accept when any reliable title source agrees: embedded TITLE, normalized
    # display title, or filename stem. This catches cases such as
    # "01 - Mask Off (...).flac" vs "01 Mask Off (...).flac" even when one
    # embedded tag is inconsistent.
    keys_a = _logical_title_keys(a)
    keys_b = _logical_title_keys(b)
    return bool(keys_a and keys_b and (keys_a & keys_b))


def plan_intra_release_duplicates(
    releases: List[Release],
    decisions: List["ReleaseDecision"],
) -> List[IntraReleaseDuplicate]:
    """Plan redundant audio files inside retained releases.

    Duplicate identity still comes exclusively from the existing audio group.
    Title/track number are only safety gates preventing intentional repeated
    recordings from being removed from different track positions.
    """
    action_by_id = {d.release_id: d.action for d in decisions}
    retained_actions = {"KEEP", "ADD", "REPLACE"}
    planned: List[IntraReleaseDuplicate] = []

    for rel in releases:
        if action_by_id.get(rel.rid) not in retained_actions:
            continue

        # Never remove files from a CUE-based rip automatically because a CUE
        # sheet may reference an exact filename.
        if rel.has_cue:
            continue

        candidates = [t for t in rel.tracks if t.group_id >= 0 and t.path.exists()]
        consumed: Set[Path] = set()

        for i, first in enumerate(candidates):
            if first.path in consumed:
                continue
            same = [first]
            for second in candidates[i + 1:]:
                if second.path in consumed:
                    continue
                if _same_logical_track(first, second):
                    same.append(second)

            if len(same) < 2:
                continue

            keep = max(
                same,
                key=lambda t: (
                    _track_codec_quality(t),
                    t.file_size,
                    -len(t.path.name),
                    str(t.path).lower(),
                ),
            )
            for duplicate in same:
                if duplicate.path == keep.path:
                    continue
                consumed.add(duplicate.path)
                planned.append(
                    IntraReleaseDuplicate(
                        release_id=rel.rid,
                        redundant=duplicate.path,
                        keep=keep.path,
                        reason=(
                            "Same retained release, same logical track position/title "
                            "(tag and/or filename), and same high-confidence audio group. "
                            f"Kept {keep.path.name} ({keep.codec_name or keep.path.suffix.lower()}); "
                            f"moved {duplicate.path.name} ({duplicate.codec_name or duplicate.path.suffix.lower()})."
                        ),
                    )
                )

    return planned


def _last_manifest_path() -> Path:
    _migrate_legacy_app_data()
    path = _state_dir() / "last_move.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _is_ancestor(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return parent.resolve() != child.resolve()
    except Exception:
        return False


def _release_paths(rel: Release) -> List[Path]:
    return rel.source_paths


def _remove_empty_dirs(root: Optional[Path]) -> None:
    if root is None or not root.is_dir():
        return
    for current, dirs, files in os.walk(root, topdown=False):
        path = Path(current)
        if path == root:
            continue
        try:
            if not any(path.iterdir()):
                path.rmdir()
        except OSError:
            pass


def default_updated_destination(recycle: Path) -> Path:
    """Put the improved collection next to (never inside) the NEW source."""
    recycle = Path(recycle).expanduser()
    if not recycle.name or recycle.name in {".", ".."}:
        raise RuntimeError("Select a specific New / update releases folder.")
    return recycle.parent / (recycle.name + " - UPDATED")


def _reject_overlapping_destination_folders(planned) -> None:
    """Two exports must never nest a complete release inside another release."""
    targets = [row[3] for row in planned]
    for index, target in enumerate(targets):
        for other in targets[index + 1:]:
            if _is_ancestor(target, other) or _is_ancestor(other, target):
                raise RuntimeError(
                    "Overlapping destination release folders; export was not started:\n"
                    f"{target}\n{other}"
                )


def copy_retained_plan(
    existing: Optional[Path],
    recycle: Path,
    destination: Path,
    releases: List[Release],
    decisions: List[ReleaseDecision],
    mode: str,
    progress_cb=None,
    extra_roots: Sequence[Path] = (),
) -> Dict[str, object]:
    """Copy the retained plan without modifying either source collection.

    mode="all" copies the final improved discography: retained Existing + retained
    New/Update releases. mode="new" copies only retained releases originating
    from the New/Update source (ADD/REPLACE).
    """
    mode = str(mode or "").strip().lower()
    if mode not in {"all", "new"}:
        raise RuntimeError(f"Unknown copy mode: {mode!r}")

    destination = Path(destination).expanduser()
    by_id = {release.rid: release for release in releases}
    retained_actions = {"KEEP", "ADD", "REPLACE"}
    chosen: List[Tuple[Release, ReleaseDecision]] = []

    for decision in decisions:
        if decision.action not in retained_actions:
            continue
        release = by_id.get(decision.release_id)
        if release is None:
            continue
        if mode == "new" and release.root_kind != "recycle":
            continue
        chosen.append((release, decision))

    if not chosen:
        label = "new/update" if mode == "new" else "retained"
        raise RuntimeError(f"No {label} releases are selected for copying.")

    resolved_destination = destination.resolve(strict=False)
    source_roots: Set[Path] = set()
    for root in (existing, recycle, *extra_roots):
        if root is not None:
            source_roots.add(Path(root).resolve(strict=False))
    for source_root in source_roots:
        if resolved_destination == source_root or _is_ancestor(source_root, resolved_destination):
            raise RuntimeError(
                "Destination must be outside the source collection folders:\n\n"
                f"Destination: {destination}\nSource: {source_root}"
            )

    chosen_releases = [release for release, _decision in chosen]
    chosen_decisions = [decision for _release, decision in chosen]
    intra_duplicates = plan_intra_release_duplicates(chosen_releases, chosen_decisions)
    redundant_files = {item.redundant.resolve(strict=False) for item in intra_duplicates}

    planned: List[Tuple[Release, ReleaseDecision, Path, Path]] = []
    target_sources: Dict[str, Path] = {}

    for release, decision in chosen:
        root = release.scan_root or (existing if release.root_kind == "existing" else recycle)
        if root is None:
            raise RuntimeError(f"Missing source root for: {release.path}")
        root = Path(root)
        for source in _release_paths(release):
            try:
                relative = source.relative_to(root)
            except ValueError:
                raise RuntimeError(
                    "Release is outside its source root:\n\n"
                    f"Release: {source}\nRoot: {root}"
                )
            target = destination / relative
            key = os.path.normcase(str(target.resolve(strict=False)))
            previous = target_sources.get(key)
            if previous is not None and previous.resolve(strict=False) != source.resolve(strict=False):
                raise RuntimeError(
                    "Two retained releases would copy to the same destination:\n\n"
                    f"{previous}\n{source}\n\nDestination: {target}"
                )
            target_sources[key] = source
            if target.exists():
                raise RuntimeError(
                    "Destination release folder already exists:\n\n"
                    f"{target}\n\nChoose an empty/new destination or remove the conflict first."
                )
            planned.append((release, decision, source, target))

    _reject_overlapping_destination_folders(planned)
    destination.mkdir(parents=True, exist_ok=True)

    def _ignore_redundant(current: str, names: List[str]) -> Set[str]:
        current_path = Path(current)
        ignored: Set[str] = set()
        for name in names:
            candidate = (current_path / name).resolve(strict=False)
            if candidate in redundant_files:
                ignored.add(name)
        return ignored

    old_ids = {release.rid for release, _decision in chosen if release.root_kind == "existing"}
    new_ids = {release.rid for release, _decision in chosen if release.root_kind == "recycle"}
    upgrade_ids = {
        release.rid
        for release, decision in chosen
        if release.root_kind == "recycle" and decision.action == "REPLACE"
    }
    addition_ids = {
        release.rid
        for release, decision in chosen
        if release.root_kind == "recycle" and decision.action == "ADD"
    }

    completed_targets: List[Path] = []
    leftover_items: List[str] = []
    total = max(1, len(planned))
    if progress_cb:
        progress_cb(
            "Copying final discography..." if mode == "all" else "Copying new/update releases...",
            0,
            total,
        )

    try:
        for index, (_release, _decision, source, target) in enumerate(planned, 1):
            if not source.exists():
                raise RuntimeError(f"Copy source is missing:\n\n{source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            staging_parent = Path(tempfile.mkdtemp(prefix=".dea-copy-", dir=str(target.parent)))
            staged = staging_parent / target.name
            try:
                if source.is_dir():
                    shutil.copytree(
                        source,
                        staged,
                        copy_function=shutil.copy2,
                        ignore=_ignore_redundant,
                    )
                else:
                    shutil.copy2(source, staged)
                if target.exists() or target.is_symlink():
                    raise RuntimeError(f"Destination appeared during copy; refusing overwrite:\n{target}")
                os.rename(str(staged), str(target))
                completed_targets.append(target)
            finally:
                shutil.rmtree(staging_parent, ignore_errors=True)
                if staging_parent.exists():
                    leftover_items.append(str(staging_parent))

            if progress_cb:
                progress_cb(
                    "Copying final discography..." if mode == "all" else "Copying new/update releases...",
                    index,
                    total,
                )
    except Exception as copy_error:
        for target in reversed(completed_targets):
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
            except Exception as cleanup_error:
                leftover_items.append(f"{target} ({cleanup_error})")
        if leftover_items:
            raise RuntimeError(
                f"{copy_error}\n\nCleanup after the failed copy was incomplete. "
                "Delete these leftover items manually:\n" + "\n".join(leftover_items)
            ) from copy_error
        raise

    logical_release_ids = {release.rid for release, _decision in chosen}
    return {
        "mode": mode,
        "destination": str(destination),
        "logical_releases": len(logical_release_ids),
        "physical_folders": len(planned),
        "existing_releases": len(old_ids),
        "new_releases": len(new_ids),
        "upgrades": len(upgrade_ids),
        "additions": len(addition_ids),
        "duplicate_files_omitted": len(redundant_files),
        "source_folders_modified": False,
    }


def _verified_release_directory_move(source: Path, target: Path) -> None:
    """Atomic same-volume folder rename; NEVER copy-then-delete across volumes.

    Cross-volume moves require a separately tested write-ahead recovery
    protocol; until that exists use the non-destructive Copy action.
    """
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Move destination already exists; refusing overwrite:\n{target}")
    if source.drive.casefold() != target.drive.casefold():
        raise RuntimeError(
            "Cross-volume Move is disabled to protect original music. "
            "Use Copy old + new, or choose a destination on the same drive.\n"
            f"Source: {source}\nDestination: {target}"
        )
    try:
        os.rename(str(source), str(target))
    except OSError as exc:
        if exc.errno == errno.EXDEV or getattr(exc, "winerror", None) == 17:
            raise RuntimeError(
                "Cross-volume Move is disabled to protect original music. "
                "Use Copy old + new instead; originals were not deleted.\n"
                f"Source: {source}\nDestination: {target}"
            ) from exc
        raise


def move_retained_plan(
    existing: Optional[Path],
    recycle: Path,
    destination: Path,
    releases: List[Release],
    decisions: List[ReleaseDecision],
    progress_cb=None,
    extra_roots: Sequence[Path] = (),
) -> Dict[str, object]:
    """Move retained OLD+NEW release folders, journal their moves for Undo.

    Unlike Copy this transfers every original file in selected release
    folders, not a filtered set. Rejected releases remain at their sources.
    """
    destination = Path(destination).expanduser().resolve(strict=False)
    old_root = Path(existing).resolve(strict=False) if existing is not None else None
    new_root = Path(recycle).resolve(strict=False)
    for root in (old_root, new_root, *[Path(r).resolve(strict=False) for r in extra_roots]):
        if root is not None and (
            destination == root
            or _is_ancestor(root, destination)
            or _is_ancestor(destination, root)
        ):
            raise RuntimeError(
                "Move destination must be outside both source folder trees:\n"
                f"Destination: {destination}\nSource: {root}"
            )
    by_id = {release.rid: release for release in releases}
    planned: List[Tuple[Release, ReleaseDecision, Path, Path]] = []
    target_sources: Dict[str, Path] = {}
    for decision in decisions:
        if decision.action not in {"KEEP", "ADD", "REPLACE"}:
            continue
        release = by_id.get(decision.release_id)
        if release is None:
            continue
        root = release.scan_root or (existing if release.root_kind == "existing" else recycle)
        if root is None:
            raise RuntimeError(f"Missing source root for: {release.path}")
        root = Path(root).resolve(strict=False)
        for original in _release_paths(release):
            source = Path(original).resolve(strict=False)
            if source == root or not _is_ancestor(root, source):
                raise RuntimeError(f"Release is outside selected root:\n{source}\n{root}")
            target = destination / source.relative_to(root)
            key = os.path.normcase(str(target))
            earlier = target_sources.get(key)
            if earlier is not None and earlier != source:
                raise RuntimeError(
                    "Retained OLD and NEW releases have the same target folder:\n"
                    f"{earlier}\n{source}\nTarget: {target}"
                )
            if key in target_sources:
                continue
            if target.exists():
                raise RuntimeError(f"Target folder already exists; refusing overwrite:\n{target}")
            if not source.is_dir():
                raise RuntimeError(f"Missing source release folder:\n{source}")
            target_sources[key] = source
            planned.append((release, decision, source, target))

    _reject_overlapping_destination_folders(planned)
    if not planned:
        raise RuntimeError("No retained OLD/NEW releases to move.")
    cross_volume = [
        (source, target) for _r, _d, source, target in planned
        if source.drive.casefold() != target.drive.casefold()
    ]
    if cross_volume:
        source, target = cross_volume[0]
        raise RuntimeError(
            "Cross-volume Move is disabled for source safety. "
            "Use Copy old + new or choose a destination on the same drive.\n"
            f"Source: {source}\nDestination: {target}"
        )
    sources = [source for _r, _d, source, _target in planned]
    for i, source in enumerate(sources):
        for other in sources[i + 1:]:
            if _is_ancestor(source, other) or _is_ancestor(other, source):
                raise RuntimeError(
                    f"Overlapping release folders cannot be moved independently:\n"
                    f"{source}\n{other}"
                )

    manifest_path = _last_manifest_path()
    previous_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None
    if previous_manifest is not None:
        backup_path = manifest_path.with_name(
            "last_move_backup_" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f") + ".json"
        )
        backup_path.write_bytes(previous_manifest)
    completed: List[Tuple[Path, Path]] = []
    manifest = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "action": "move_retained",
        "duplicates_root": "",
        "existing_root": str(existing) if existing else "",
        "recycle_root": str(recycle),
        "extra_roots": [str(r) for r in extra_roots],
        "destination": str(destination),
        "moves": [],
    }
    if progress_cb:
        progress_cb("Moving retained OLD + NEW releases...", 0, len(planned))
    try:
        for index, (release, decision, source, target) in enumerate(planned, 1):
            if not source.is_dir() or target.exists():
                raise RuntimeError(
                    f"Source changed or destination appeared during move:\n"
                    f"{source}\n{target}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            # Journal BEFORE rename. If interrupted, Undo can identify
            # both a completed rename and an unexecuted pending entry.
            manifest["moves"].append({
                "move_type": "retained_release",
                "release_id": release.rid,
                "action": decision.action,
                "original": str(source),
                "moved_to": str(target),
                "reason": decision.reason,
            })
            _atomic_write_json(manifest_path, manifest)
            _verified_release_directory_move(source, target)
            completed.append((source, target))
            if source.exists() or not target.is_dir():
                raise RuntimeError(f"Release move verification failed:\n{source}\n{target}")
            if progress_cb:
                progress_cb("Moving retained OLD + NEW releases...", index, len(planned))
        _remove_empty_dirs(existing)
        _remove_empty_dirs(recycle)
        for extra in extra_roots:
            _remove_empty_dirs(Path(extra))
    except Exception:
        conflicts = []
        # The last rename might succeed and then raise BEFORE it enters
        # 'completed'. Use the pre-journaled moves, not the success list.
        for item in reversed(manifest["moves"]):
            original = Path(item["original"])
            target = Path(item["moved_to"])
            try:
                if target.exists() and not original.exists():
                    original.parent.mkdir(parents=True, exist_ok=True)
                    _verified_release_directory_move(target, original)
                elif target.exists() and original.exists():
                    conflicts.append(f"Both original and target exist: {original} / {target}")
                elif not original.exists():
                    conflicts.append(f"Both original and target missing: {original} / {target}")
            except Exception as exc:
                conflicts.append(f"{target}: {exc}")
        if not conflicts:
            if previous_manifest is not None:
                manifest_path.write_bytes(previous_manifest)
            else:
                manifest_path.unlink(missing_ok=True)
        if conflicts:
            raise RuntimeError(
                "Move failed and rollback needs manual recovery; use Undo:\n"
                + "\n".join(conflicts)
            )
        raise

    return {
        "mode": "move_all",
        "destination": str(destination),
        "logical_releases": len({r.rid for r, _d, _s, _t in planned}),
        "physical_folders": len(planned),
        "existing_releases": len({r.rid for r, _d, _s, _t in planned if r.root_kind == "existing"}),
        "new_releases": len({r.rid for r, _d, _s, _t in planned if r.root_kind == "recycle"}),
        "source_folders_modified": True,
        "undo_available": True,
    }


def undo_last_run() -> Tuple[int, List[str]]:
    manifest_path = _last_manifest_path()
    if not manifest_path.is_file():
        raise RuntimeError("No undo manifest found.")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    moves = data.get("moves") or []
    restored = 0
    conflicts: List[str] = []
    for item in reversed(moves):
        original = Path(item["original"])
        saved = Path(item["moved_to"])
        if not saved.exists():
            if not original.exists():
                conflicts.append(f"Both the moved folder and its original are missing: {saved} -> {original}")
            continue
        if original.exists():
            conflicts.append(f"Original path is occupied; cannot restore: {original}")
            continue
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            if str(item.get("move_type", "")) == "retained_release":
                _verified_release_directory_move(saved, original)
            else:
                shutil.move(str(saved), str(original))
            restored += 1
        except Exception as exc:
            conflicts.append(f"Undo failed for {saved} -> {original}: {exc}")

    # Remove now-empty mirrored helper folders, but preserve any older content.
    raw_dup_root = str(data.get("duplicates_root") or "").strip()
    if raw_dup_root:
        dup_root = Path(raw_dup_root)
        _remove_empty_dirs(dup_root)
        try:
            if dup_root.is_dir() and not any(dup_root.iterdir()):
                dup_root.rmdir()
        except Exception:
            pass
    if not conflicts:
        try:
            manifest_path.unlink(missing_ok=True)
        except Exception:
            pass
    return restored, conflicts



def _light_ui_dependency_dir() -> Path:
    return _dependencies_dir() / f"pywebview-{PYWEBVIEW_VERSION}"


def ensure_light_ui_dependencies():
    """Load pywebview from the isolated program dependency directory."""
    deps = _light_ui_dependency_dir()
    deps_text = str(deps)
    if deps.is_dir() and deps_text not in sys.path:
        sys.path.insert(0, deps_text)

    try:
        return importlib.import_module("webview")
    except Exception:
        pass  # Not installed yet or broken: fall through to the installer below.

    bootstrap_winget()
    pip_check = run_hidden(
        [sys.executable, "-m", "pip", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )
    if pip_check.returncode != 0:
        run_hidden(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )

    deps.mkdir(parents=True, exist_ok=True)
    cp = run_hidden(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--quiet",
            "--upgrade",
            "--target",
            str(deps),
            f"pywebview=={PYWEBVIEW_VERSION}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError(
            "pywebview could not be installed automatically: "
            + (cp.stderr.strip() or cp.stdout.strip() or "pip install failed")
        )

    if deps_text not in sys.path:
        sys.path.insert(0, deps_text)
    importlib.invalidate_caches()
    return importlib.import_module("webview")


def _webview2_runtime_version() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg
    except Exception:
        return ""

    key_id = r"{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    checks = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{key_id}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{key_id}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{key_id}"),
    ]
    for root, key_path in checks:
        try:
            with winreg.OpenKey(root, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "pv")
            version = str(value or "").strip()
            if version and version != "0.0.0.0":
                return version
        except Exception:
            pass
    return ""


def _ensure_webview2_runtime() -> str:
    if os.name != "nt":
        return ""
    current = _webview2_runtime_version()
    if current:
        return current

    winget = bootstrap_winget()
    if winget:
        cp = run_hidden(
            [
                winget,
                "install",
                "--id", "Microsoft.EdgeWebView2Runtime",
                "-e",
                "--source", "winget",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
        if cp.returncode == 0:
            current = _webview2_runtime_version()
            if current:
                return current

    raise RuntimeError(
        "Microsoft Edge WebView2 Runtime is required and automatic setup did not complete."
    )


def _copy_text_to_clipboard(value: str) -> None:
    """Copy text without importing Tk; the lightweight build is Windows/WebView2-only."""
    if os.name != "nt":
        raise RuntimeError("Clipboard support is available on Windows only.")

    text = str(value or "")
    last_error: Optional[BaseException] = None
    for _attempt in range(8):
        hmem = None
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p

            data = ctypes.create_unicode_buffer(text)
            size = ctypes.sizeof(data)
            hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not hmem:
                raise OSError("GlobalAlloc failed")
            ptr = kernel32.GlobalLock(hmem)
            if not ptr:
                raise OSError("GlobalLock failed")
            ctypes.memmove(ptr, ctypes.addressof(data), size)
            kernel32.GlobalUnlock(hmem)

            if not user32.OpenClipboard(None):
                raise OSError("OpenClipboard failed")
            try:
                user32.EmptyClipboard()
                if not user32.SetClipboardData(CF_UNICODETEXT, hmem):
                    raise OSError("SetClipboardData failed")
                hmem = None  # Clipboard now owns the memory.
            finally:
                user32.CloseClipboard()
            return
        except Exception as exc:
            last_error = exc
            if hmem:
                try:
                    kernel32.GlobalFree(hmem)
                except Exception:
                    pass
            time.sleep(0.03)
    raise RuntimeError(f"Could not copy text to the Windows clipboard: {last_error}")


def _light_emit(window, function_name: str, payload: str) -> None:
    if window is None:
        return
    try:
        js_payload = json.dumps(str(payload or ""), ensure_ascii=False)
        window.run_js(
            f"window.{function_name} && window.{function_name}({js_payload});"
        )
    except Exception:
        pass


def _expose_bridge_methods(window, bridge, required: Iterable[str]) -> Tuple[str, ...]:
    required_names = tuple(str(name) for name in required)
    functions = []
    exposed_names = []

    for name in required_names:
        value = getattr(bridge, name, None)
        if not callable(value):
            raise RuntimeError(f"Desktop bridge method is missing in Python: {name}")
        functions.append(value)
        exposed_names.append(name)

    if not functions:
        raise RuntimeError("Desktop bridge has no methods to expose.")

    # Explicit function exposure avoids relying on js_api object's reflective
    # method discovery. It is supported before load and at runtime by pywebview.
    window.expose(*functions)
    return tuple(exposed_names)


def _webview_release_map_html() -> str:
    html = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Collection map</title>
<style>
:root{
  color-scheme:dark;
  --bg:#0a0a0a;--surface:#101010;--raised:#171717;--line:rgba(255,255,255,.11);--line2:rgba(255,255,255,.06);
  --t1:#ededed;--t2:#a1a1a1;--t3:#6f6f6f;--hover:rgba(255,255,255,.05);--sel:rgba(255,255,255,.09);
  --amber:#f5a623;--green:#4ade80;--blue:#7aa7ff;--red:#ff6369;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden;background:var(--bg);color:var(--t1);
  font:14px/1.4 "Segoe UI Variable","Segoe UI",system-ui,sans-serif}
body{display:flex;flex-direction:column}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--t1);outline-offset:2px}
svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* top */
#top{display:flex;align-items:center;gap:12px;padding:14px 20px 10px}
#back{display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 10px 0 6px;border:0;border-radius:6px;background:transparent;color:var(--t2)}
#back:hover{background:var(--hover);color:var(--t1)}
#find{flex:0 1 280px;height:34px;padding:0 12px;border:1px solid var(--line);border-radius:6px;background:var(--surface);outline:none}
#find:focus{border-color:var(--t2)}
#find::placeholder{color:var(--t3)}
#summary{flex:1;min-width:0;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-left:6px}
#summary b{color:var(--t1);font-weight:500}
.btn{height:34px;padding:0 14px;border:1px solid var(--line);border-radius:6px;background:transparent;white-space:nowrap}
.btn:hover{background:var(--hover);border-color:rgba(255,255,255,.28)}
.btn.main{background:var(--t1);border-color:var(--t1);color:var(--bg);font-weight:600}
.btn.main:hover{background:#fff}
.btn.warn{border-color:rgba(245,166,35,.6);color:var(--amber)}
.btn.quiet{border-color:transparent;color:var(--t2)}
.btn.quiet:hover{color:var(--t1)}

/* filters */
#filters{display:flex;align-items:center;gap:6px;padding:0 20px 12px;flex-wrap:wrap}
.tabs{display:flex;gap:2px;padding:2px;border:1px solid var(--line);border-radius:8px;margin-right:10px}
.tab{height:28px;padding:0 12px;border:0;border-radius:6px;background:transparent;color:var(--t2)}
.tab:hover{color:var(--t1)}
.tab[aria-pressed="true"]{background:var(--sel);color:var(--t1)}
.tab .n{margin-left:6px;color:var(--t3);font-variant-numeric:tabular-nums}
.tab.alert .n{color:var(--amber)}
.chip{height:26px;padding:0 11px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--t2);font-size:13px}
.chip:hover{color:var(--t1);border-color:rgba(255,255,255,.28)}
.chip[aria-pressed="true"]{color:var(--t1);border-color:var(--t1)}
.chip.focusTrack{border-color:rgba(122,167,255,.6);color:var(--blue);display:inline-flex;align-items:center;gap:6px}

/* body */
#body{flex:1;min-height:0;display:flex;border-top:1px solid var(--line2)}
#listWrap{flex:1;min-width:0;position:relative}
#list{position:absolute;inset:0;overflow-y:auto;overflow-x:hidden}
#spacer{position:relative}
.item{position:absolute;left:0;right:0}
.h1{display:flex;align-items:flex-end;padding:0 20px 6px;color:var(--t2);font-size:12px;letter-spacing:.02em}
.h1 b{color:var(--t1);font-weight:500;font-size:13px;margin-right:8px}
.grp{display:flex;align-items:flex-end;padding:0 20px 4px;color:var(--t1);font-weight:500;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rel{display:flex;align-items:center;gap:12px;padding:0 20px;border:0;border-top:1px solid var(--line2);background:transparent;text-align:left;width:100%}
.rel:hover{background:var(--hover)}
.rel.sel{background:var(--sel)}
.rel.dim{color:var(--t3)}
.rel.indent{padding-left:44px}
.rel.indent .nm{font-size:13px}
.rel.gainedRow{box-shadow:inset 3px 0 var(--green)}
.rel.lostRow{box-shadow:inset 3px 0 var(--red)}
.dot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--t3)}
.dot.added{background:var(--green)}.dot.upgraded,.dot.replaced{background:var(--blue)}
.dot.ignored{background:var(--red)}.dot.look{background:var(--amber)}
.rel .main{flex:1;min-width:0}
.rel .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rel .why{color:var(--t3);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rel.dim .nm{color:var(--t2)}
.rel .where{flex:none;color:var(--t3);font-size:12px;width:62px;text-align:right}
.rel .out{flex:none;width:112px;text-align:right;font-size:13px;color:var(--t2)}
.rel .out.look{color:var(--amber)}
.rel .out.added{color:var(--green)}.rel .out.upgraded,.rel .out.replaced{color:var(--blue)}.rel .out.ignored{color:var(--red)}
.empty{padding:64px 20px;text-align:center;color:var(--t2)}

/* details */
#details{display:none;flex:0 0 min(46%,640px);min-width:0;border-left:1px solid var(--line);flex-direction:column;background:var(--bg)}
#details.open{display:flex}
#dHead{padding:16px 20px 12px;border-bottom:1px solid var(--line2);position:relative}
#dClose{position:absolute;top:10px;right:12px;width:32px;height:32px;display:flex;align-items:center;justify-content:center;border:0;border-radius:6px;background:transparent;color:var(--t2)}
#dClose:hover{background:var(--hover);color:var(--t1)}
#dName{font-size:16px;font-weight:600;line-height:1.3;padding-right:36px;overflow-wrap:anywhere}
#dSub{margin-top:4px;color:var(--t2);font-size:13px}
#dScroll{flex:1;min-height:0;overflow-y:auto}
.sec{padding:14px 20px;border-bottom:1px solid var(--line2)}
.sec h4{margin:0 0 8px;font-size:12px;font-weight:500;color:var(--t2);letter-spacing:.02em}
.note{padding:10px 12px;border:1px solid var(--line);border-radius:8px;color:var(--t1);font-size:13px;white-space:pre-wrap;margin-bottom:8px}
.note.amber{border-color:rgba(245,166,35,.5);color:#ffd9a0}
.acts{display:flex;flex-wrap:wrap;gap:8px}
.path{margin-top:10px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--t2);
  font:12px/1.45 "Cascadia Mono",Consolas,monospace;overflow-wrap:anywhere;user-select:text}
.why2{color:var(--t2);font-size:13px;margin-top:10px}
.link{display:flex;align-items:center;gap:10px;width:100%;padding:7px 8px;margin:0 -8px;border:0;border-radius:6px;background:transparent;text-align:left}
.link:hover{background:var(--hover)}
.link .k{flex:none;width:76px;color:var(--t3);font-size:12px}
.link .v{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px}
.trk{display:grid;grid-template-columns:28px minmax(0,1fr) auto auto;gap:4px 10px;align-items:start;padding:10px 20px;border-bottom:1px solid var(--line2)}
.trk:hover{background:var(--hover)}
.trk.focus{background:rgba(122,167,255,.10)}
.trk .no{color:var(--t3);font-size:12px;padding-top:2px;text-align:right}
.trk .tt{min-width:0;overflow-wrap:anywhere}
.trk .tt .ttl{cursor:pointer}
.trk .tt .ttl:hover{text-decoration:underline;text-underline-offset:3px}
.trk.off .ttl{color:var(--t3)}
.trk .st{grid-column:2/-1;color:var(--t3);font-size:12px;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.trk .st.look{color:var(--amber)}
.trk .st.good{color:var(--green)}
.trk .dur{color:var(--t2);font-size:12px;font-variant-numeric:tabular-nums;padding-top:2px;text-align:right;white-space:nowrap}
.trk .dur i{display:block;font-style:normal;color:var(--amber);font-size:11px}
.badge{display:inline-flex;align-items:center;justify-content:center;min-width:16px;height:16px;margin-left:6px;padding:0 4px;border:1px solid var(--line);border-radius:3px;font-size:10px;color:var(--t2);vertical-align:1px}
.pill{height:22px;padding:0 9px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--t2);font-size:12px}
.pill:hover{color:var(--t1);border-color:rgba(255,255,255,.28)}
.pill[aria-expanded="true"]{color:var(--t1);border-color:var(--t1)}
.kebab{width:30px;height:30px;display:flex;align-items:center;justify-content:center;border:0;border-radius:6px;background:transparent;color:var(--t2)}
.kebab:hover{background:var(--sel);color:var(--t1)}
.alts{grid-column:2/-1;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:4px 0 2px}
.alt{display:grid;grid-template-columns:minmax(0,1fr) 64px 80px;gap:10px;align-items:center;width:100%;padding:8px 10px;border:0;border-top:1px solid var(--line2);background:transparent;text-align:left;font-size:13px}
.alt:first-child{border-top:0}
.alt:hover{background:var(--hover)}
.alt .a1{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.alt .a2{color:var(--t2);font-size:12px}
.alt .a3{color:var(--t3);font-size:12px;text-align:right}
.alt .a3.kept{color:var(--green)}

/* menus, dialogs */
#menu{display:none;position:fixed;z-index:60;min-width:220px;padding:6px;border:1px solid var(--line);border-radius:10px;background:var(--raised);box-shadow:0 12px 32px rgba(0,0,0,.6)}
#menu.open{display:block}
#menu button{display:block;width:100%;min-height:34px;padding:6px 10px;border:0;border-radius:6px;background:transparent;text-align:left}
#menu button:hover{background:var(--hover)}
#scrim{display:none;position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.68);align-items:center;justify-content:center;padding:24px}
#scrim.open{display:flex}
#dlg{width:min(520px,100%);max-height:90vh;overflow:auto;padding:22px;border:1px solid var(--line);border-radius:12px;background:var(--raised)}
#dlg h2{margin:0 0 6px;font-size:18px;font-weight:600}
#dlg p{margin:0 0 12px;color:var(--t2)}
#dlg .dest{display:flex;align-items:center;gap:8px;margin:14px 0 6px}
#dlg .dest .path{flex:1;margin:0;min-width:0}
#dlg .foot{display:flex;justify-content:flex-end;gap:8px;margin-top:20px}
#toast{position:fixed;left:50%;bottom:76px;transform:translateX(-50%);max-width:min(560px,90vw);padding:9px 16px;border-radius:8px;background:var(--t1);color:var(--bg);font-weight:500;opacity:0;pointer-events:none;transition:opacity .18s;z-index:90}
#toast.on{opacity:1}

/* bottom */
#bar{display:flex;align-items:center;gap:10px;padding:12px 20px;border-top:1px solid var(--line)}
#barMsg{flex:1;min-width:0;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#barMsg.dirty{color:var(--amber)}
@media (max-width:1100px){#details.open{flex-basis:50%}.rel .where{display:none}}
</style>
</head>
<body>
<header id="top">
  <button id="back" aria-label="Back to the main window"><svg viewBox="0 0 16 16"><path d="M10 3 5 8l5 5"/></svg>Back</button>
  <input id="find" type="search" placeholder="Search releases and tracks" aria-label="Search releases and tracks">
  <div id="summary" aria-live="polite"></div>
</header>
<div id="filters"></div>
<div id="body">
  <div id="listWrap"><div id="list" tabindex="-1"><div id="spacer"></div></div></div>
  <aside id="details" aria-label="Release details">
    <div id="dHead"><div id="dName"></div><div id="dSub"></div>
      <button id="dClose" aria-label="Close details"><svg viewBox="0 0 16 16"><path d="m4 4 8 8M12 4l-8 8"/></svg></button></div>
    <div id="dScroll"></div>
  </aside>
</div>
<footer id="bar">
  <div id="barMsg" aria-live="polite"></div>
  <button class="btn" id="reBtn">Update plan</button>
  <button class="btn" id="moveBtn">Move</button>
  <button class="btn main" id="copyBtn">Copy</button>
</footer>
<div id="menu" role="menu"></div>
<div id="scrim"><div id="dlg" role="dialog" aria-modal="true"></div></div>
<div id="toast" role="status"></div>
<script type="module">
let bridge=null,state=null;
let selectedId=null,view="changes",kindFilter="all",typeFilter="all",query="";
let focusTrack=null;
const openAlts=new Set();
const exportPaths={all:"",new:""};
const HIGHLIGHT_MS=15000;
let lastToken="",hlTimer=null;
const gained=new Set(),lost=new Set();
const $=id=>document.getElementById(id);
const esc=v=>String(v==null?"":v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
const ICON={
  back:'<svg viewBox="0 0 16 16"><path d="M10 3 5 8l5 5"/></svg>',
  more:'<svg viewBox="0 0 16 16"><circle cx="3.5" cy="8" r=".6"/><circle cx="8" cy="8" r=".6"/><circle cx="12.5" cy="8" r=".6"/></svg>',
  x:'<svg viewBox="0 0 16 16"><path d="m4 4 8 8M12 4l-8 8"/></svg>'
};

/* ---------- plan logic ---------- */
const act=n=>String(n.action||"").toUpperCase();
const getNode=id=>(state.nodes||[]).find(n=>Number(n.id)===Number(id));
let replCache=null;
function replacementMap(){
  if(replCache)return replCache;
  const nodes=state.nodes||[];
  const byId=new Map(nodes.map(n=>[Number(n.id),n]));
  const groupSets=new Map(nodes.map(n=>[Number(n.id),new Set((n.tracks||[]).filter(t=>t.included&&!t.excluded&&!t.manualSkip&&Number(t.groupId)>=0).map(t=>Number(t.groupId)))]));
  const candidateTargets=new Map(),targetToOld=new Map(),oldToTarget=new Map();
  const covers=(a,b)=>a&&a.size&&b&&[...a].every(g=>b.has(g));
  nodes.forEach(target=>{
    if(String(target.rootKind||"")!=="recycle"||act(target)!=="REPLACE"||target.manualRemoved)return;
    (target.upgradeFrom||[]).forEach(ref=>{
      const old=byId.get(Number(ref.releaseId));
      if(!old||String(old.rootKind||"")!=="existing"||old.kind!=="duplicate"||old.manualRemoved||oldToTarget.has(Number(old.id)))return;
      if(!covers(groupSets.get(Number(old.id)),groupSets.get(Number(target.id))))return;
      oldToTarget.set(Number(old.id),target);
      if(!targetToOld.has(Number(target.id)))targetToOld.set(Number(target.id),[]);
      targetToOld.get(Number(target.id)).push(old);
    });
  });
  (state.duplicateLinks||[]).forEach(link=>{
    const old=byId.get(Number(link.duplicate)),target=byId.get(Number(link.retained));
    if(!old||!target)return;
    const oldRemoved=String(old.rootKind||"")==="existing"&&old.kind==="duplicate"&&!old.manualRemoved;
    const targetNew=String(target.rootKind||"")==="recycle"&&["ADD","REPLACE"].includes(act(target))&&!target.manualRemoved;
    if(!oldRemoved||!targetNew)return;
    if(!covers(groupSets.get(Number(old.id)),groupSets.get(Number(target.id))))return;
    const lc=s=>String(s||"").trim().toLowerCase();
    if(!((lc(old.displayGroupKey)&&lc(old.displayGroupKey)===lc(target.displayGroupKey))||(lc(old.family)&&lc(old.family)===lc(target.family))))return;
    if(!candidateTargets.has(Number(old.id)))candidateTargets.set(Number(old.id),[]);
    candidateTargets.get(Number(old.id)).push(target);
  });
  candidateTargets.forEach((options,oldId)=>{
    if(oldToTarget.has(oldId))return;
    const oldGroups=groupSets.get(oldId);
    options.sort((a,b)=>((act(a)==="REPLACE"?0:1)-(act(b)==="REPLACE"?0:1))
      ||((groupSets.get(Number(a.id)).size-oldGroups.size)-(groupSets.get(Number(b.id)).size-oldGroups.size))
      ||((a.tracks||[]).length-(b.tracks||[]).length)||(Number(a.id)-Number(b.id)));
    const target=options[0];
    oldToTarget.set(oldId,target);
    if(!targetToOld.has(Number(target.id)))targetToOld.set(Number(target.id),[]);
    targetToOld.get(Number(target.id)).push(byId.get(oldId));
  });
  replCache={targetToOld,oldToTarget};
  return replCache;
}
const isRealUpgrade=n=>act(n)==="REPLACE"&&(n.upgradeFrom||[]).some(o=>!!String(o.upgradeReason||"").trim());
function changeKind(n){
  if(n.manualRemoved||n.pendingReleaseIgnore||n.pendingReleaseRestore)return "ignored";
  if(state.standaloneMode)return "";
  const p=replacementMap();
  if(p.oldToTarget.has(Number(n.id)))return "replacementSource";
  if(p.targetToOld.has(Number(n.id)))return isRealUpgrade(n)?"upgraded":"replaced";
  const root=String(n.rootKind||"");
  if(root==="recycle"&&act(n)==="ADD")return "added";
  if(root==="recycle"&&act(n)==="REPLACE")return isRealUpgrade(n)?"upgraded":"replaced";
  if(root==="existing"&&act(n)!=="KEEP"&&n.kind==="duplicate")return "removed";
  return "";
}
const issuesOf=n=>(n.auditIssues||[]).map(x=>String(x||"").trim()).filter(Boolean);
const lookNodes=()=>(state.nodes||[]).filter(n=>issuesOf(n).length);
const changedNodes=()=>(state.nodes||[]).filter(n=>{const k=changeKind(n);return !!k&&k!=="replacementSource";});
const KIND_LABEL={added:"Added",upgraded:"Upgraded",replaced:"Replaced",removed:"Removed",ignored:"Ignored"};
const KIND_ORDER=["added","upgraded","replaced","removed","ignored"];
function outcome(n){
  if(issuesOf(n).length)return {key:"look",label:"Needs a look"};
  if(n.pendingReleaseIgnore)return {key:"ignored",label:"Will be ignored"};
  if(n.pendingReleaseRestore)return {key:"added",label:"Will be restored"};
  const k=changeKind(n);
  if(k==="added")return {key:"added",label:"Added"};
  if(k==="upgraded")return {key:"upgraded",label:"Upgrade"};
  if(k==="replaced")return {key:"replaced",label:"Replaces older"};
  if(k==="replacementSource")return {key:"muted",label:"Replaced"};
  if(k==="removed")return {key:"muted",label:"Removed"};
  if(k==="ignored")return {key:"ignored",label:"Ignored"};
  if(n.kind==="duplicate")return {key:"muted",label:"Duplicate"};
  return {key:"",label:state.standaloneMode?"Kept":"Kept"};
}
function whyShort(n){
  const iss=issuesOf(n);
  if(iss.length)return iss.join("; ");
  const p=replacementMap(),k=changeKind(n);
  if(k==="added"){
    const u=(n.tracks||[]).filter(t=>t.unique&&!t.excluded&&!t.manualSkip).map(t=>String(t.title||"")).filter(Boolean);
    return u.length?"Only copy of "+u.slice(0,2).join(", ")+(u.length>2?" and "+(u.length-2)+" more":""):"Not in your library yet";
  }
  if(k==="upgraded"||k==="replaced"){
    const names=(p.targetToOld.get(Number(n.id))||[]).map(o=>String(o.name||"")).filter(Boolean);
    const why=(n.upgradeFrom||[]).map(o=>String(o.upgradeReason||"").trim()).find(Boolean)||"";
    return (k==="upgraded"?"Better than ":"Takes the place of ")+(names.join(", ")||"your older copy")+(why?" ("+why+")":"");
  }
  if(k==="replacementSource"){const t=p.oldToTarget.get(Number(n.id));return "Replaced by "+String(t&&t.name||"a newer copy");}
  if(k==="removed"||(n.kind==="duplicate"&&!k)){
    const kept=(state.duplicateLinks||[]).filter(l=>Number(l.duplicate)===Number(n.id)).map(l=>getNode(l.retained)).filter(Boolean);
    if(kept.length)return "Same as "+cleanLabel(kept[0].name)+(kept.length>1?" and "+(kept.length-1)+" more":"");
    return "Another copy is kept";
  }
  if(k==="ignored"){
    if(n.pendingReleaseIgnore)return "Will be ignored when you update the plan";
    if(n.pendingReleaseRestore)return "Will be restored when you update the plan";
    return "Ignored by you";
  }
  return "";
}
function typeKind(n){
  const t=String(n.displayGroupKind||n.releaseType||"").toLowerCase();
  return ["compilation","anthology","ep","single"].includes(t)?t:"album";
}
const TYPE_LABEL={album:"Albums",ep:"EPs",single:"Singles",anthology:"Anthologies",compilation:"Compilations"};
const TYPE_ORDER=["album","ep","single","anthology","compilation"];
const cleanLabel=name=>{const s=String(name||"").trim().replace(/^\s*\d{4}(?:-\d{2}-\d{2})?\s*-\s*/,"");return s||String(name||"").trim();};
function groupKey(n){
  return String(n.displayGroupKey||"").trim().toLowerCase()||String(n.family||"").trim().toLowerCase()
    ||cleanLabel(n.name).toLowerCase().replace(/[^\p{L}\p{N}]+/gu," ").trim()||String(n.id);
}
function groupTitle(items){
  const pre=items.map(n=>String(n.displayGroupTitle||"").trim()).filter(Boolean);
  const pool=pre.length?pre:items.map(n=>cleanLabel(n.name)).filter(Boolean);
  if(!pool.length)return "Other";
  pool.sort((a,b)=>a.length-b.length||a.localeCompare(b,undefined,{sensitivity:"base"}));
  return pool[0];
}
const carriersOf=gid=>(Number(gid)<0?[]:(state.nodes||[]).filter(n=>(n.tracks||[]).some(t=>Number(t.groupId)===Number(gid))));
function baseRelations(id){
  const src=getNode(id),out={versions:[],remixes:[],live:[]};
  if(!src)return out;
  (state.nodes||[]).forEach(o=>{
    if(Number(o.id)===Number(src.id))return;
    let v=false,r=false,l=false;
    (src.tracks||[]).forEach(a=>{
      if(a.excluded||Number(a.groupId)<0||!a.baseKey)return;
      (o.tracks||[]).forEach(b=>{
        if(b.excluded||Number(b.groupId)<0||!b.baseKey)return;
        if(a.baseKey!==b.baseKey||Number(a.groupId)===Number(b.groupId))return;
        const af=String(a.family||"version"),bf=String(b.family||"version");
        if(af==="live"||bf==="live")l=true;else if(af==="remix"||bf==="remix")r=true;else v=true;
      });
    });
    if(v)out.versions.push(o);else if(r)out.remixes.push(o);else if(l)out.live.push(o);
  });
  return out;
}
function altsFor(t,fam){
  if(!state.versionFamilies||!t||!t.baseKey)return [];
  return (state.versionFamilies[t.baseKey]||[]).filter(v=>Number(v.groupId)!==Number(t.groupId)&&String(v.family||"version")===fam);
}
function lengthGap(t,o){
  const a=Number(t&&t.durationSeconds),b=Number(o&&o.durationSeconds);
  if(!Number.isFinite(a)||!Number.isFinite(b)||a<=0||b<=0)return null;
  const d=Math.abs(a-b);return d>8.0000001?d:null;
}
const gapText=s=>"Δ "+(Math.round(s*10)/10).toFixed(1)+"s";
function trackStatus(t,n){
  const everywhere=Number(t.groupId)>=0;
  if(t.pendingIgnore)return {text:(everywhere?"Will be ignored everywhere":"Will be ignored")+" after the plan is updated",tone:"look"};
  if(t.pendingRestore)return {text:(everywhere?"Will be restored everywhere":"Will be restored")+" after the plan is updated",tone:"look"};
  if(t.manualSkip)return {text:everywhere?"Ignored everywhere":"Ignored",tone:""};
  const excl=()=>{
    const r=String(t.exclusionReason||"").trim();
    if(r==="Explicit>Clean")return "Skipped: a clean copy exists";
    if(r)return "Skipped: "+r;
    if(t.isRemix&&t.isLive)return "Skipped: remix and live";
    if(t.isRemix)return "Skipped: remix";
    if(t.isLive)return "Skipped: live";
    return "Skipped";
  };
  if(n&&n.manualRemoved){
    if(t.excluded)return {text:excl(),tone:""};
    if(t.orphaned||!t.replacementSource)return {text:"Nothing replaces this track",tone:"look"};
    const more=(t.replacementAlternates||[]).length;
    return {text:(t.coveredByAlternateVersion?"Another version is kept on ":"Kept on ")+t.replacementSource+(more?" and "+more+" more":""),tone:"good"};
  }
  if(t.excluded)return {text:excl(),tone:""};
  if(t.orphaned)return {text:"Removing this release would lose this track",tone:"look"};
  if(t.coveredBy&&t.coveredBy.length)return {text:(t.coveredByAlternateVersion?"Another version is on ":"Also on ")+t.coveredBy.slice(0,2).join(", "),tone:""};
  const m=Math.max(0,Number(t.audioMatchEditions)||0),u=Math.max(0,Number(t.unverifiedEditions)||0);
  if(m||u){
    const parts=[];
    if(m)parts.push("Same audio on "+m+" other release"+(m===1?"":"s"));
    if(u)parts.push("listed on "+u+" more (audio not compared)");
    return {text:parts.join(", "),tone:""};
  }
  if(t.unique)return {text:"Only copy",tone:"good"};
  if(t.isGem)return {text:"Only copy, no other versions",tone:"good"};
  return {text:t.distinction||"",tone:""};
}

/* ---------- list ---------- */
const H={h1:38,grp:28,rel:50};
let items=[],offsets=[],totalH=0;
function matchesQuery(n){
  const q=query.trim().toLowerCase();
  if(!q)return true;
  if(String(n.name||"").toLowerCase().includes(q))return true;
  return (n.tracks||[]).some(t=>String(t.title||"").toLowerCase().includes(q));
}
function buildItems(){
  const out=[];
  const nodes=state.nodes||[];
  let pool;
  if(focusTrack)pool=carriersOf(focusTrack.groupId);
  else if(view==="look")pool=lookNodes();
  else if(view==="changes")pool=changedNodes();
  else pool=nodes;
  pool=pool.filter(matchesQuery);
  if(view==="changes"&&!focusTrack){
    KIND_ORDER.forEach(k=>{
      if(kindFilter!=="all"&&kindFilter!==k)return;
      const rows=pool.filter(n=>changeKind(n)===k);
      if(!rows.length)return;
      out.push({t:"h1",text:KIND_LABEL[k],count:rows.length});
      rows.forEach(n=>out.push({t:"rel",n}));
    });
  }else if(view==="look"&&!focusTrack){
    if(pool.length)out.push({t:"h1",text:"Needs a look",count:pool.length});
    pool.forEach(n=>out.push({t:"rel",n}));
  }else{
    TYPE_ORDER.forEach(type=>{
      if(typeFilter!=="all"&&typeFilter!==type)return;
      const typed=pool.filter(n=>typeKind(n)===type);
      if(!typed.length)return;
      out.push({t:"h1",text:TYPE_LABEL[type],count:typed.length});
      const groups=new Map();
      typed.forEach(n=>{const k=groupKey(n);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(n);});
      Array.from(groups.values()).sort((a,b)=>nodes.indexOf(a[0])-nodes.indexOf(b[0])).forEach(g=>{
        if(g.length>1||typed.length<=400)out.push({t:"grp",text:groupTitle(g)});
        g.forEach(n=>out.push({t:"rel",n}));
      });
    });
  }
  items=out;offsets=[];totalH=0;
  out.forEach(it=>{offsets.push(totalH);totalH+=H[it.t];});
  $("spacer").style.height=totalH+"px";
}
function relHtml(it,top){
  const n=it.n,o=outcome(n),k=changeKind(n);
  const dotKind=o.key==="look"?"look":(o.key==="muted"?"":o.key);
  const cls=["rel","item"];
  if(o.key==="muted")cls.push("dim");
  if(Number(n.id)===Number(selectedId))cls.push("sel");
  if(n.kind==="duplicate"&&view==="all")cls.push("indent");
  if(gained.has(String(n.id)))cls.push("gainedRow");
  if(lost.has(String(n.id)))cls.push("lostRow");
  const where=state.standaloneMode?"":(String(n.rootKind||"")==="existing"?"Library":"Incoming");
  return `<button class="${cls.join(" ")}" style="top:${top}px;height:${H.rel}px" data-id="${esc(n.id)}" aria-label="${esc(n.name)}. ${esc(o.label)}.${where?" "+where+".":""}">`
    +`<span class="dot ${dotKind}"></span><span class="main"><span class="nm" style="display:block">${esc(n.name)}</span><span class="why" style="display:block">${esc(whyShort(n))}</span></span>`
    +`<span class="where">${where}</span><span class="out ${o.key}">${esc(o.label)}</span></button>`;
}
let paintQueued=false;
function paintList(){
  if(paintQueued)return;
  paintQueued=true;
  requestAnimationFrame(()=>{paintQueued=false;paintListNow();});
}
function paintListNow(){
  const list=$("list"),sp=$("spacer");
  if(!items.length){
    sp.style.height="auto";
    sp.innerHTML=`<div class="empty">${esc(emptyText())}</div>`;
    return;
  }
  const top=list.scrollTop,bottom=top+list.clientHeight;
  let lo=0,hi=items.length-1;
  while(lo<hi){const mid=(lo+hi)>>1;if(offsets[mid]+H[items[mid].t]<top)lo=mid+1;else hi=mid;}
  let html="";
  for(let i=Math.max(0,lo-4);i<items.length&&offsets[i]<bottom+200;i++){
    const it=items[i],y=offsets[i];
    if(it.t==="rel")html+=relHtml(it,y);
    else if(it.t==="h1")html+=`<div class="item h1" style="top:${y}px;height:${H.h1}px"><b>${esc(it.text)}</b>${it.count}</div>`;
    else html+=`<div class="item grp" style="top:${y}px;height:${H.grp}px">${esc(it.text)}</div>`;
  }
  sp.innerHTML=html;
}
function emptyText(){
  if(query.trim())return "Nothing matches your search.";
  if(focusTrack)return "No releases carry this track.";
  if(view==="look")return "Nothing needs a look.";
  if(view==="changes")return state.standaloneMode?"Only one folder was scanned, so there is nothing to compare. Open Everything to review it.":"No changes. Your collection already matches the plan.";
  return "No releases.";
}
function scrollToItem(id){
  const idx=items.findIndex(it=>it.t==="rel"&&Number(it.n.id)===Number(id));
  if(idx<0)return;
  const list=$("list"),y=offsets[idx];
  if(y<list.scrollTop||y+H.rel>list.scrollTop+list.clientHeight)list.scrollTop=Math.max(0,y-list.clientHeight/2);
  paintListNow();
}

/* ---------- top, filters, bar ---------- */
const plural=(n,w)=>n+" "+w+(n===1?"":"s");
function renderSummary(){
  if(!state)return;
  const pc=state.planCounts||{},res=pc.result||pc.initial||{releases:0,tracks:0},delta=pc.delta||{releases:0};
  const scanned=state.scannedCounts||{};
  const kept=Number(res.releases||0),look=lookNodes().length||Number(state.auditIssueCount||0);
  let html=state.standaloneMode?`<b>${kept}</b> of ${Number(scanned.releases||0)} releases kept`:`<b>${plural(kept,"release")}</b> kept`+(Number(delta.releases||0)?` (${delta.releases>0?"+":""}${delta.releases})`:"");
  html+=` · ${plural(Number(res.tracks||0),"track")}`;
  if(look)html+=` · <span style="color:var(--amber)">${look} need a look</span>`;
  $("summary").innerHTML=html;
  $("summary").title=$("summary").textContent;
}
function renderFilters(){
  const changes=changedNodes().length,look=lookNodes().length||Number(state.auditIssueCount||0),all=(state.nodes||[]).length;
  const tab=(key,label,n,alert)=>`<button class="tab${alert&&n?" alert":""}" data-view="${key}" aria-pressed="${view===key}">${label}<span class="n">${n}</span></button>`;
  let html=`<div class="tabs">${state.standaloneMode?"":tab("changes","Changes",changes)}${tab("all","Everything",all)}${look?tab("look","Needs a look",look,true):""}</div>`;
  if(view==="changes"&&!focusTrack){
    const counts={};changedNodes().forEach(n=>{const k=changeKind(n);counts[k]=(counts[k]||0)+1;});
    html+=`<button class="chip" data-kind="all" aria-pressed="${kindFilter==="all"}">All</button>`;
    KIND_ORDER.forEach(k=>{if(counts[k])html+=`<button class="chip" data-kind="${k}" aria-pressed="${kindFilter===k}">${KIND_LABEL[k]} ${counts[k]}</button>`;});
  }else if(view==="all"&&!focusTrack){
    const present=new Set((state.nodes||[]).map(typeKind));
    if(present.size>1){
      html+=`<button class="chip" data-type="all" aria-pressed="${typeFilter==="all"}">All types</button>`;
      TYPE_ORDER.forEach(t=>{if(present.has(t))html+=`<button class="chip" data-type="${t}" aria-pressed="${typeFilter===t}">${TYPE_LABEL[t]}</button>`;});
    }
  }
  if(focusTrack)html+=`<button class="chip focusTrack" data-clearfocus="1">Releases with “${esc(focusTrack.title)}” · ${carriersOf(focusTrack.groupId).length}${ICON.x}</button>`;
  $("filters").innerHTML=html;
}
function exportBlockReason(){
  if(!state.editable)return "This map is read only.";
  if(state.dirty)return "Update the plan first, your changes are not applied yet.";
  if(lookNodes().length||Number(state.auditIssueCount||0))return "Fix the releases that need a look first.";
  if(!state.applyEnabled)return "The plan is not ready yet.";
  return "";
}
function renderBar(){
  const msg=$("barMsg"),re=$("reBtn");
  re.style.display=state.editable&&state.dirty&&!state.requiresFreshScan?"":"none";
  re.classList.toggle("warn",true);
  $("copyBtn").style.display=$("moveBtn").style.display=state.editable?"":"none";
  if(state.requiresFreshScan){msg.textContent="Run Analyze again from the main window to use your new labels.";msg.className="dirty";}
  else if(state.dirty){msg.textContent="You changed things. Update the plan to see the result.";msg.className="dirty";}
  else{msg.textContent=state.editable?"":"Read only";msg.className="";}
}
function renderAll(){
  if(!state)return;
  replCache=null;
  renderSummary();renderFilters();renderBar();
  buildItems();paintListNow();
  if(selectedId!=null&&getNode(selectedId))renderDetails();else closeDetails(true);
}
function toast(text){
  const t=$("toast");t.textContent=text;t.classList.add("on");
  clearTimeout(toast.h);toast.h=setTimeout(()=>t.classList.remove("on"),2600);
}

/* ---------- details ---------- */
function closeDetails(silent){
  selectedId=null;
  $("details").classList.remove("open");
  if(!silent)paintListNow();
}
function select(id,opts){
  selectedId=Number(id);
  if(!(opts&&opts.keepFocus))focusTrack=focusTrack&&opts&&opts.focus?focusTrack:null;
  renderFilters();buildItems();
  renderDetails();scrollToItem(id);
}
function relatedHtml(n){
  const rows=[],p=replacementMap();
  const add=(k,node)=>rows.push(`<button class="link" data-go="${esc(node.id)}"><span class="k">${k}</span><span class="v">${esc(node.name)}</span></button>`);
  (p.targetToOld.get(Number(n.id))||[]).forEach(o=>add("Replaces",o));
  const t=p.oldToTarget.get(Number(n.id));if(t)add("Replaced by",t);
  const seen=new Set();
  (state.duplicateLinks||[]).forEach(l=>{
    let other=null,k="";
    if(Number(l.duplicate)===Number(n.id)){other=getNode(l.retained);k="Kept instead";}
    else if(Number(l.retained)===Number(n.id)){other=getNode(l.duplicate);k="Duplicate";}
    if(other&&!seen.has(other.id)&&!(t&&Number(t.id)===Number(other.id))&&!(p.targetToOld.get(Number(n.id))||[]).some(o=>Number(o.id)===Number(other.id))){seen.add(other.id);add(k,other);}
  });
  const b=baseRelations(n.id);
  b.versions.slice(0,8).forEach(o=>add("Other version",o));
  b.remixes.slice(0,8).forEach(o=>add("Remix of",o));
  b.live.slice(0,8).forEach(o=>add("Live of",o));
  return rows.length?`<div class="sec"><h4>Related releases</h4>${rows.join("")}</div>`:"";
}
function albumGroupHtml(n){
  if(!state.editable||!["album","ep"].includes(String(n.releaseType||"").toLowerCase()))return "";
  const choices=new Map();
  (state.nodes||[]).forEach(o=>{
    if(Number(o.id)===Number(n.id)||!["album","ep"].includes(String(o.releaseType||"").toLowerCase()))return;
    const k=groupKey(o);if(k===groupKey(n))return;
    const cur=choices.get(k);if(!cur||(!o.manualGroupAssigned&&cur.manualGroupAssigned))choices.set(k,o);
  });
  const targets=Array.from(choices.values()).sort((a,b)=>groupTitle([a]).localeCompare(groupTitle([b])));
  return `<div class="sec"><h4>Album family</h4><div class="acts"><select id="groupSel" aria-label="Move to another album family" class="btn" style="max-width:100%"${targets.length?"":" disabled"}>`
    +(targets.length?targets.map(o=>`<option value="${Number(o.id)}">${esc(groupTitle([o]))}</option>`).join(""):"<option>No other family</option>")
    +`</select><button class="btn" data-act="regroup"${targets.length?"":" disabled"}>Move here</button>`
    +(n.manualGroupAssigned?`<button class="btn quiet" data-act="regroupReset">Back to automatic</button>`:"")
    +`</div></div>`;
}
function trackHtml(t,n){
  const st=trackStatus(t,n);
  const vers=altsFor(t,"version"),rmx=altsFor(t,"remix"),liv=altsFor(t,"live");
  const gaps=vers.map(v=>lengthGap(t,v)).filter(v=>v!==null);
  const gap=gaps.length?Math.min(...gaps):null;
  const adv=String(t.explicitState||"").toLowerCase();
  const badge=adv==="explicit"?`<span class="badge" title="Explicit">E</span>`:(adv==="clean"?`<span class="badge" title="Clean">C</span>`:"");
  const gem=t.isGem?`<span class="badge" title="Only copy, no other versions" style="color:var(--green)">◆</span>`:"";
  const patt=t.patternKind?`<button class="pill" data-act="keepPattern" data-track="${t.index}" title="Always keep tracks like this">${({remix:"Remix",live:"Live",skip:"Ignored"})[t.patternKind]||"Pattern"} · always keep</button>`:"";
  const pill=(kind,label,n)=>n?`<button class="pill" data-act="alts" data-kind="${kind}" data-track="${t.index}" aria-expanded="${openAlts.has(t.index+":"+kind)}">${label} ${n}</button>`:"";
  const off=t.excluded||t.manualSkip||t.pendingIgnore;
  const focus=focusTrack&&Number(focusTrack.groupId)===Number(t.groupId);
  let html=`<div class="trk${off?" off":""}${focus?" focus":""}" data-index="${t.index}">`
    +`<div class="no">${esc(t.number)}</div>`
    +`<div class="tt"><span class="ttl" data-act="focus" data-track="${t.index}" title="Show every release with this track">${esc(t.title)}</span>${badge}${gem}</div>`
    +`<div class="dur">${esc(t.duration)}${gap!==null?`<i>${gapText(gap)}</i>`:""}</div>`
    +(state.editable&&(!t.excluded||t.manualSkip||t.pendingRestore||true)?`<button class="kebab" data-act="menu" data-track="${t.index}" aria-label="Actions for ${esc(t.title)}" aria-haspopup="menu">${ICON.more}</button>`:"<span></span>")
    +`<div class="st ${st.tone}">${st.text?`<span>${esc(st.text)}</span>`:""}${pill("version","Other versions",vers.length)}${pill("remix","Remixes",rmx.length)}${pill("live","Live",liv.length)}${patt}</div>`;
  [["version",vers],["remix",rmx],["live",liv]].forEach(([kind,arr])=>{
    if(!arr.length||!openAlts.has(t.index+":"+kind))return;
    html+=`<div class="alts">`+arr.map(v=>{
      const g=lengthGap(t,v),where=(v.retainedReleaseNames&&v.retainedReleaseNames.length?v.retainedReleaseNames:v.releaseNames||[]).slice(0,2).join(", ");
      return `<button class="alt" data-act="altgo" data-kind="${kind}" data-track="${t.index}" data-group="${esc(v.groupId)}" title="${esc(where)}"><span class="a1">${esc(v.title)}<br><span class="a2">${esc(where)}</span></span>`
        +`<span class="a2">${esc(v.duration||"")}${g!==null?"<br>"+gapText(g):""}</span><span class="a3${v.retained?" kept":""}">${v.retained?"Kept":(v.available?"Not kept":"Ignored")}</span></button>`;
    }).join("")+`</div>`;
  });
  return html+"</div>";
}
function renderDetails(){
  const n=getNode(selectedId);
  if(!n){closeDetails(true);return;}
  const scroller=$("dScroll"),keep=scroller.scrollTop,same=scroller.dataset.id===String(n.id);
  const o=outcome(n);
  $("dName").textContent=n.name;
  const where=state.standaloneMode?"":(String(n.rootKind||"")==="existing"?"Library":"Incoming");
  const inc=Number(n.includedTracks)>0?plural(Number(n.includedTracks),"track")+" kept":"";
  const uniq=Number(n.uniqueCount)>0?Number(n.uniqueCount)+" only here":"";
  $("dSub").textContent=[o.label,where,String(n.sourceMedium||n.sourceDescription||""),inc,uniq].filter(Boolean).join(" · ");
  let html="";
  const notes=[];
  if(n.typeWarning)notes.push(`<div class="note amber">${esc(n.typeWarning)}</div>`);
  const iss=issuesOf(n);
  if(iss.length)notes.push(`<div class="note amber">This release has problems:\n${esc(iss.join("\n"))}</div>`);
  if(n.pendingReleaseIgnore)notes.push(`<div class="note amber">Will be ignored. Update the plan to see where its tracks come from instead. No files were touched.</div>`);
  else if(n.pendingReleaseRestore)notes.push(`<div class="note amber">Will be restored. Update the plan to include it again. No files were touched.</div>`);
  else if(n.manualRemoved)notes.push(`<div class="note">You ignored this release. It stays on the map so you can see what covers its tracks. Restore it, then update the plan to undo.</div>`);
  const acts=[];
  if(state.editable){
    acts.push(`<button class="btn${n.forceKeep?" main":""}" data-act="forceKeep">${n.forceKeep?"Stop force keeping":"Always keep this release"}</button>`);
    if(n.kind==="retained"||n.manualRemoved||n.pendingReleaseChange)acts.push(`<button class="btn" data-act="toggleRelease">${n.releaseBlocked?"Restore release":"Ignore release"}</button>`);
  }
  acts.push(`<button class="btn quiet" data-act="openFolder">Show in Explorer</button>`);
  html+=`<div class="sec">${notes.join("")}<div class="acts">${acts.join("")}</div><div class="path" tabindex="0" aria-label="Folder path">${esc(n.path)}</div>`
    +(n.pendingReleaseIgnore||n.pendingReleaseRestore||!n.reason?"":`<div class="why2">${esc(n.reason)}</div>`)+`</div>`;
  html+=albumGroupHtml(n)+relatedHtml(n);
  html+=`<div class="sec" style="padding-bottom:6px"><h4>Tracks · ${(n.tracks||[]).length}</h4></div>`+(n.tracks||[]).map(t=>trackHtml(t,n)).join("");
  scroller.innerHTML=html;scroller.dataset.id=String(n.id);
  scroller.scrollTop=same?keep:0;
  $("details").classList.add("open");
}

/* ---------- menus and dialogs ---------- */
function closeMenu(){$("menu").classList.remove("open");}
function openTrackMenu(btn,t){
  const m=$("menu"),everywhere=Number(t.groupId)>=0;
  const restoring=!!(t.manualSkip||t.pendingIgnore);
  let html=`<button role="menuitem" data-m="toggleTrack" data-track="${t.index}">${restoring?"Restore this "+(everywhere?"recording everywhere":"track"):"Ignore this "+(everywhere?"recording everywhere":"track")}</button>`;
  ["remix","live"].forEach(k=>{if(k!==t.patternKind)html+=`<button role="menuitem" data-m="mark" data-kind="${k}" data-track="${t.index}">Treat tracks like this as ${k==="remix"?"remixes":"live"}</button>`;});
  if(t.patternKind)html+=`<button role="menuitem" data-m="keepPattern" data-track="${t.index}">Always keep tracks like this</button>`;
  m.innerHTML=html;m.classList.add("open");
  const r=btn.getBoundingClientRect(),w=m.offsetWidth,h=m.offsetHeight;
  m.style.left=Math.max(8,Math.min(innerWidth-w-8,r.right-w))+"px";
  m.style.top=(r.bottom+h+8>innerHeight?Math.max(8,r.top-h-4):r.bottom+4)+"px";
  const first=m.querySelector("button");if(first)first.focus();
}
function closeDialog(){$("scrim").classList.remove("open");$("dlg").innerHTML="";}
function exportDialog(mode){
  const reason=exportBlockReason();
  if(reason){toast(reason);return;}
  const key=mode==="copy"?"all":"new";
  const path=String(exportPaths[key]||defaultExportPath()).trim();
  if(!path){chooseDestination(key,()=>exportDialog(mode));return;}
  const kept=(state.nodes||[]).filter(n=>["KEEP","ADD","REPLACE"].includes(act(n))&&!n.manualRemoved);
  const lib=kept.filter(n=>String(n.rootKind||"")==="existing").length,inc=kept.filter(n=>String(n.rootKind||"")==="recycle").length;
  const ups=kept.filter(n=>changeKind(n)==="upgraded").length;
  const sum=state.standaloneMode?plural(kept.length,"release"):`${plural(lib,"library release")} and ${plural(inc,"incoming release")}`+(ups?`, ${plural(ups,"upgrade")}`:"");
  const copy=mode==="copy";
  $("dlg").innerHTML=`<h2>${copy?"Copy the final collection":"Move the final collection"}</h2>`
    +`<p>${esc(sum)} will go to this folder.</p>`
    +`<div class="dest"><div class="path">${esc(path)}</div><button class="btn" data-d="choose">Change</button></div>`
    +`<p style="margin-top:12px">${copy?"Your original folders are not touched.":"Original folders are moved, not copied. This only works on the same drive, nothing is overwritten, and you can undo it from the main window."}</p>`
    +`<div class="foot"><button class="btn quiet" data-d="cancel">Cancel</button><button class="btn main" data-d="go">${copy?"Copy":"Move"}</button></div>`;
  $("scrim").classList.add("open");
  $("dlg").dataset.mode=mode;$("dlg").dataset.key=key;$("dlg").dataset.path=path;
  $("dlg").querySelector('[data-d="go"]').focus();
}
function defaultExportPath(){
  const s=String(state.defaultExportDestination||"").trim();
  if(s)return s;
  let src=String((state.sourceRoots||{}).recycle||"").trim();
  if(!src){const n=(state.nodes||[]).find(r=>String(r.rootKind||"").toLowerCase()==="recycle"&&String(r.sourceRoot||"").trim());src=n?String(n.sourceRoot).trim():"";}
  src=src.replace(/[\\/]+$/,"");
  if(!src||/^[a-z]:$/i.test(src))return "";
  return src+" - UPDATED";
}
function chooseDestination(key,then){
  bridge.chooseDestination(key,p=>{
    p=String(p||"").trim();
    if(!p)return;
    exportPaths[key]=p;
    if(then)then();
  });
}

/* ---------- bridge events ---------- */
function startHighlights(){
  const r=state.result;
  if(!r||!r.show||!r.highlightToken)return false;
  const tok=String(r.highlightToken);
  if(tok===lastToken)return false;
  lastToken=tok;
  gained.clear();lost.clear();
  (r.addedReleaseIds||[]).forEach(i=>gained.add(String(i)));
  (r.removedReleaseIds||[]).forEach(i=>lost.add(String(i)));
  if(!gained.size&&!lost.size)return false;
  view="all";typeFilter="all";kindFilter="all";focusTrack=null;
  clearTimeout(hlTimer);
  hlTimer=setTimeout(()=>{gained.clear();lost.clear();buildItems();paintListNow();},HIGHLIGHT_MS);
  return true;
}
function receiveState(raw){
  state=JSON.parse(raw);
  const hl=startHighlights();
  if(state.standaloneMode&&view==="changes")view="all";
  renderAll();
  if(hl){
    const first=(state.nodes||[]).find(n=>gained.has(String(n.id))||lost.has(String(n.id)));
    if(first)scrollToItem(first.id);
    toast("The update changed "+plural(gained.size+lost.size,"release")+".");
  }
}
function applyRootPatch(p){
  if(!state)return;
  state.dirty=!!p.dirty;
  state.applyEnabled=!!p.applyEnabled&&!Number(state.auditIssueCount||0);
  state.applyHighlighted=!!p.applyHighlighted;
  if(p.result)state.result=p.result;
}
function receiveTrackToggle(raw){
  const p=JSON.parse(raw);
  if(!p||p.kind!=="trackToggle"){receiveState(raw);return;}
  const updated=Array.isArray(p.tracks)&&p.tracks.length?p.tracks:[{index:p.trackIndex,manualSkip:p.manualSkip,pendingIgnore:p.pendingIgnore,pendingRestore:p.pendingRestore}];
  const upd=new Map(updated.map(r=>[Number(r.index),r]));
  const rels=new Map((p.releases||[]).map(r=>[Number(r.id),r]));
  (state.nodes||[]).forEach(n=>{
    (n.tracks||[]).forEach(t=>{
      const r=upd.get(Number(t.index));if(!r)return;
      t.manualSkip=!!r.manualSkip;t.pendingIgnore=!!r.pendingIgnore;t.pendingRestore=!!r.pendingRestore;
      if("unique" in r)t.unique=!!r.unique;
      if("isGem" in r)t.isGem=!!r.isGem;
    });
    const r=rels.get(Number(n.id));
    if(r){n.uniqueCount=Number(r.uniqueCount)||0;n.isGem=!!r.isGem;n.gemTitles=r.gemTitles||[];}
  });
  applyRootPatch(p);renderAll();
}
function receiveReleaseToggle(raw){
  const p=JSON.parse(raw);
  if(!p||p.kind!=="releaseToggle"){receiveState(raw);return;}
  const n=getNode(p.releaseId);
  if(n){
    n.releaseBlocked=!!p.releaseBlocked;n.pendingReleaseChange=!!p.pendingReleaseChange;
    n.pendingReleaseIgnore=!!p.pendingReleaseIgnore;n.pendingReleaseRestore=!!p.pendingReleaseRestore;
  }
  applyRootPatch(p);renderAll();
}
function receivePattern(raw){
  const u=JSON.parse(raw);
  if(!u||u.kind!=="patternToggle"){receiveState(raw);return;}
  const patches=new Map((u.tracks||[]).map(p=>[Number(p.index),p]));
  (state.nodes||[]).forEach(n=>(n.tracks||[]).forEach(t=>{
    const p=patches.get(Number(t.index));
    if(p){t.patternKind=p.patternKind;t.patternKey=p.patternKey;}
  }));
  state.requiresFreshScan=!!u.requiresFreshScan;state.applyEnabled=false;state.dirty=true;
  renderAll();
  toast("Saved. Run Analyze again from the main window to use it.");
}

/* ---------- events ---------- */
const trackByIndex=i=>{const n=getNode(selectedId);return n?(n.tracks||[]).find(t=>Number(t.index)===Number(i)):null;};
$("dScroll").addEventListener("click",ev=>{
  const el=ev.target.closest("[data-act],[data-go]");
  if(!el)return;
  const n=getNode(selectedId);if(!n)return;
  if(el.dataset.go){select(el.dataset.go);return;}
  const a=el.dataset.act,ti=Number(el.dataset.track);
  if(a==="forceKeep")bridge.toggleReleaseKeep(Number(n.id),receiveState);
  else if(a==="toggleRelease")bridge.toggleRelease(Number(n.id),receiveReleaseToggle);
  else if(a==="openFolder")bridge.openFolder(n.path);
  else if(a==="regroup"){const v=Number($("groupSel").value);if(Number.isFinite(v))bridge.setAlbumGroup(Number(n.id),v,receiveState);}
  else if(a==="regroupReset")bridge.setAlbumGroup(Number(n.id),-1,receiveState);
  else if(a==="keepPattern")bridge.markTrackPattern(ti,"keep",receivePattern);
  else if(a==="menu"){ev.stopPropagation();const t=trackByIndex(ti);if(t)openTrackMenu(el,t);}
  else if(a==="alts"){const k=ti+":"+el.dataset.kind;if(openAlts.has(k))openAlts.delete(k);else openAlts.add(k);renderDetails();}
  else if(a==="focus"){
    const t=trackByIndex(ti);
    if(t&&Number(t.groupId)>=0){focusTrack={groupId:Number(t.groupId),title:String(t.title||"")};view="all";typeFilter="all";renderFilters();buildItems();paintListNow();renderDetails();}
  }else if(a==="altgo"){
    const t=trackByIndex(ti);if(!t)return;
    const pool=altsFor(t,el.dataset.kind),v=pool.find(x=>Number(x.groupId)===Number(el.dataset.group));
    if(v&&Number(v.releaseId)>=0){focusTrack={groupId:Number(v.groupId),title:String(v.title||"")};view="all";typeFilter="all";selectedId=Number(v.releaseId);renderFilters();buildItems();renderDetails();scrollToItem(v.releaseId);}
  }
});
$("menu").addEventListener("click",ev=>{
  const b=ev.target.closest("[data-m]");if(!b)return;
  const ti=Number(b.dataset.track);closeMenu();
  if(b.dataset.m==="toggleTrack")bridge.toggleTrack(ti,receiveTrackToggle);
  else if(b.dataset.m==="mark")bridge.markTrackPattern(ti,b.dataset.kind||"",receivePattern);
  else if(b.dataset.m==="keepPattern")bridge.markTrackPattern(ti,"keep",receivePattern);
});
document.addEventListener("click",ev=>{if(!ev.target.closest("#menu")&&!ev.target.closest('[data-act="menu"]'))closeMenu();});
$("list").addEventListener("scroll",paintList);
$("list").addEventListener("click",ev=>{const b=ev.target.closest(".rel");if(b){selectedId=Number(b.dataset.id);paintListNow();renderDetails();}});
$("list").addEventListener("keydown",ev=>{
  if(ev.key!=="ArrowDown"&&ev.key!=="ArrowUp")return;
  const rels=items.filter(i=>i.t==="rel");if(!rels.length)return;
  ev.preventDefault();
  let i=rels.findIndex(r=>Number(r.n.id)===Number(selectedId));
  i=ev.key==="ArrowDown"?Math.min(rels.length-1,i+1):Math.max(0,i<0?0:i-1);
  selectedId=Number(rels[i].n.id);renderDetails();scrollToItem(selectedId);
  const b=$("spacer").querySelector(`.rel[data-id="${selectedId}"]`);if(b)b.focus();
});
$("filters").addEventListener("click",ev=>{
  const b=ev.target.closest("button");if(!b)return;
  if(b.dataset.view){view=b.dataset.view;focusTrack=null;if(view!=="changes")kindFilter="all";}
  else if(b.dataset.kind)kindFilter=b.dataset.kind;
  else if(b.dataset.type)typeFilter=b.dataset.type;
  else if(b.dataset.clearfocus){focusTrack=null;}
  else return;
  $("list").scrollTop=0;renderFilters();buildItems();paintListNow();if(selectedId!=null)renderDetails();
});
$("find").addEventListener("input",ev=>{query=ev.target.value;focusTrack=focusTrack;$("list").scrollTop=0;buildItems();paintListNow();});
$("dClose").onclick=()=>closeDetails();
$("back").onclick=()=>bridge.closeMap();
$("reBtn").onclick=()=>bridge.reanalyze(receiveState);
$("copyBtn").onclick=()=>exportDialog("copy");
$("moveBtn").onclick=()=>exportDialog("move");
$("dlg").addEventListener("click",ev=>{
  const b=ev.target.closest("[data-d]");if(!b)return;
  const d=$("dlg"),mode=d.dataset.mode,key=d.dataset.key,path=d.dataset.path;
  if(b.dataset.d==="cancel")closeDialog();
  else if(b.dataset.d==="choose"){chooseDestination(key,()=>exportDialog(mode));}
  else if(b.dataset.d==="go"){closeDialog();bridge.copyPlan(key,path);}
});
document.addEventListener("keydown",ev=>{
  if(ev.key!=="Escape")return;
  if($("scrim").classList.contains("open")){closeDialog();return;}
  if($("menu").classList.contains("open")){closeMenu();return;}
  if(selectedId!=null)closeDetails();
});
$("scrim").addEventListener("click",ev=>{if(ev.target===$("scrim"))closeDialog();});
window.addEventListener("resize",paintList);

/* ---------- bridge ---------- */
function waitForMethod(name,ms){
  const limit=Number(ms||30000);
  return new Promise((resolve,reject)=>{
    const t0=Date.now();
    (function probe(){
      const api=window.pywebview&&window.pywebview.api,fn=api&&api[name];
      if(typeof fn==="function"){resolve({api,fn});return;}
      if(Date.now()-t0>=limit){reject(new Error("Desktop bridge method did not become ready: "+String(name)));return;}
      setTimeout(probe,25);
    })();
  });
}
function bridgeCall(name,args,cb){
  return waitForMethod(name,30000).then(e=>e.fn.apply(e.api,args)).then(r=>{
    if(cb)cb(typeof r==="string"?r:JSON.stringify(r));
    return r;
  }).catch(e=>{console.error(e);toast("Desktop bridge error: "+String(e&&e.message||e));throw e;});
}
bridge=new Proxy({},{get:(_t,name)=>function(){
  const args=Array.from(arguments);
  const cb=(args.length&&typeof args[args.length-1]==="function")?args.pop():null;
  return bridgeCall(name,args,cb);
}});
bridge.getState(receiveState).catch(()=>{});
window.addEventListener("pywebviewready",()=>{bridge.getState(receiveState).catch(()=>{});});
</script>
</body>
</html>"""
    return html


def _release_date_sort_key_for_map(name: str) -> Tuple[int, int, int, str]:
    text = normalize_space(name)
    match = re.match(r"^\s*(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", text)
    if not match:
        return (9999, 12, 31, text.casefold())
    return (
        int(match.group(1)),
        int(match.group(2) or 0),
        int(match.group(3) or 0),
        text.casefold(),
    )


def _release_map_plan_counts(
    snapshots: List[Dict[str, object]],
) -> Dict[str, int]:
    """Count the current proposed plan, not every row visible on the map."""
    retained = [
        item
        for item in snapshots
        if str(item.get("action", "")) in {"KEEP", "ADD", "REPLACE"}
        and not bool(item.get("manual_removed"))
    ]
    return {
        "releases": len(retained),
        "tracks": sum(
            max(0, int(item.get("included_tracks", 0) or 0))
            for item in retained
        ),
    }


def _release_map_visual_title(name: str) -> str:
    """Fallback human title when embedded ALBUM metadata is unavailable."""
    value = normalize_space(str(name or ""))

    # Common folder prefixes: "2010 - Title", "[2010] Artist - Title",
    # and "Artist - Title (2010)" style scene/rip folders.
    value = re.sub(r"^\s*\[?\d{4}(?:-\d{2}-\d{2})?\]?\s*-?\s*", "", value).strip()

    previous = None
    while value != previous:
        previous = value
        value = re.sub(
            r"\s*(?:-\s*)?(?:clean|explicit)(?:\s*-)?\s*$",
            "",
            value,
            flags=re.I,
        ).strip()
        value = re.sub(
            r"\s+(?:\d+\s*)?(?:cd|disc|disk)\s*\d*(?:\s*(?:of|/)\s*\d+)?\s*$",
            "",
            value,
            flags=re.I,
        ).strip()
        value = re.sub(r"\s+(?:web|flac|mp3|lossless)\s*$", "", value, flags=re.I).strip()
        value = re.sub(r"\s*\{[^{}]+\}\s*$", "", value).strip()
        value = re.sub(r"\s*\[[^\]]+\]\s*$", "", value).strip()
        value = re.sub(r"\s*\(\d{4}\)\s*$", "", value).strip()

    # Last-resort scene/rip artist prefix. Metadata is preferred, so this only
    # matters when ALBUM tags are missing.
    value = re.sub(r"^\s*[^-]{1,80}\s+-\s+(?=\S)", "", value).strip()
    return value


_RELEASE_MAP_EDITION_SUFFIX_RE = re.compile(
    r"\s*\((?:[^)]*\b(?:deluxe|limited|special|expanded|bonus|exclusive|tour|"
    r"edition|version|remaster(?:ed)?|anniversary)\b[^)]*)\)\s*$",
    re.I,
)


_RELEASE_MAP_DISC_SUFFIX_RE = re.compile(
    r"\s*(?:(?:[:\-–—]\s*)|\()?(?:cd|disc|disk)\s*\d+"
    r"(?:\s*(?:of|/)\s*\d+)?\)?\s*$",
    re.I,
)

_RELEASE_MAP_FEATURE_CREDIT_SUFFIX_RE = re.compile(
    r"\s*\((?:feat(?:uring)?|ft)\.?\s+[^()]*\)\s*$",
    re.I,
)

_RELEASE_MAP_TYPE_SUFFIX_RE = re.compile(
    r"\s*(?:[-–—:]\s*)?(?:ep|single)\s*$",
    re.I,
)


def _release_map_known_edition_base(title: str) -> str:
    value = normalize_space(title)
    previous = None
    while value != previous:
        previous = value
        value = _RELEASE_MAP_DISC_SUFFIX_RE.sub("", value).strip()
        value = _RELEASE_MAP_EDITION_SUFFIX_RE.sub("", value).strip()
    return value


def _release_map_family_base(title: str, release_type: str) -> str:
    """Canonical display-family title, independent of provider naming style."""
    value = _release_map_known_edition_base(title)
    previous = None
    while value != previous:
        previous = value
        value = _RELEASE_MAP_FEATURE_CREDIT_SUFFIX_RE.sub("", value).strip()
        if str(release_type or "").lower() in {"ep", "single"}:
            value = _RELEASE_MAP_TYPE_SUFFIX_RE.sub("", value).strip()
        value = _RELEASE_MAP_EDITION_SUFFIX_RE.sub("", value).strip()
    return value or normalize_space(title)


def _release_map_metadata_title(node: Dict[str, object]) -> str:
    """Choose one stable release title from embedded ALBUM tags."""
    raw_values = node.get("albumTitles", []) or []
    if isinstance(raw_values, str):
        raw_values = [raw_values]

    candidates: List[str] = []
    for raw in raw_values:
        value = normalize_space(clean_metadata_text(str(raw or "")))
        if not value:
            continue
        value = _RELEASE_MAP_DISC_SUFFIX_RE.sub("", value).strip()
        if value:
            candidates.append(value)

    if not candidates:
        return ""

    # After CD1/CD2 normalization, prefer the most frequent title. Shortest
    # wins ties so "Album" is preferred over a verbose edition label.
    counts = Counter(normalize_title(value) for value in candidates if normalize_title(value))
    if not counts:
        return candidates[0]
    best_key = min(
        counts,
        key=lambda key: (
            -counts[key],
            min(len(value) for value in candidates if normalize_title(value) == key),
            key,
        ),
    )
    matching = [value for value in candidates if normalize_title(value) == best_key]
    matching.sort(key=lambda value: (len(value), value.casefold()))
    return matching[0]


def _assign_release_map_display_groups(nodes: List[Dict[str, object]], releases: Optional[List[Release]] = None) -> None:
    """Assign display-only families, preferring embedded ALBUM metadata."""
    by_kind: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for node in nodes:
        release_type = str(node.get("releaseType", "") or "").lower()
        if release_type in {"compilation", "anthology"}:
            kind = release_type
        elif release_type == "ep":
            kind = "ep"
        elif release_type == "single":
            kind = "single"
        else:
            kind = "album"
        by_kind[kind].append(node)

    for rows in by_kind.values():
        source_titles: Dict[int, str] = {}
        for row in rows:
            rid = int(row.get("id", -1))
            metadata_title = _release_map_metadata_title(row)
            source_titles[rid] = metadata_title or _release_map_visual_title(str(row.get("name", "")))

        canonical_titles: Dict[int, str] = {}
        for row in rows:
            rid = int(row.get("id", -1))
            title = source_titles.get(rid, "")
            canonical_titles[rid] = _release_map_family_base(
                title,
                str(row.get("releaseType", "") or ""),
            )

        known_bases = {
            normalize_title(value)
            for value in canonical_titles.values()
            if normalize_title(value)
        }
        exact_titles = {
            normalize_title(title)
            for title in source_titles.values()
            if normalize_title(title)
        }

        for row in rows:
            rid = int(row.get("id", -1))
            title = source_titles.get(rid, "")
            base = canonical_titles.get(rid, "") or title

            # Unknown parenthetical labels (Instrumentals, Sketch Book, etc.)
            # join a plain base only when that plain title is actually present.
            if base == title:
                match = re.match(r"^(.*?)\s*\([^()]+\)\s*$", title)
                if match:
                    candidate = normalize_space(match.group(1))
                    candidate = _release_map_family_base(
                        candidate,
                        str(row.get("releaseType", "") or ""),
                    )
                    candidate_key = normalize_title(candidate)
                    if candidate_key in exact_titles or candidate_key in known_bases:
                        base = candidate

            group_key = normalize_title(base) or normalize_title(title) or str(rid)
            row["displayGroupKey"] = group_key
            row["displayGroupTitle"] = base or title or str(row.get("name", ""))

    # Render acoustic album families AND user assignments using the same
    # grouping function as the optimizer. Display labels never alter audio IDs.
    links = _manual_album_group_links()
    for row in nodes:
        row["manualGroupAssigned"] = (
            _manual_album_group_path_key(Path(str(row.get("path", "") or ""))) in links
            if row.get("path") else False
        )
    if isinstance(releases, list):
        node_by_id = {int(row.get("id", -1)): row for row in nodes}
        # Release Map families can cross Album/EP tags. The optimizer's
        # album-completeness requirements remain album-only by design.
        for family in _album_clusters([rel for rel in releases if rel.release_type in {"album", "ep"}]):
            matches = [node_by_id[r.rid] for r in family if r.rid in node_by_id]
            if len(matches) < 2:
                continue
            group_id = min(int(row["id"]) for row in matches)
            # Use a short human-readable title; never expose path IDs as names.
            titles = [
                str(row.get("displayGroupTitle", "") or "").strip()
                for row in matches
                if str(row.get("displayGroupTitle", "") or "").strip()
            ]
            title = min(titles, key=lambda value: (len(value), value.casefold())) if titles else str(group_id)
            home_kind = "album" if any(rel.release_type == "album" for rel in family) else "ep"
            for row in matches:
                row["displayGroupKey"] = "mcc-acoustic-" + str(group_id)
                row["displayGroupTitle"] = title
                row["displayGroupKind"] = home_kind


def _release_map_group_id(row: Dict[str, object]) -> int:
    """Preserve valid zero-based acoustic group IDs."""
    value = row.get("group_id", -1)
    if value is None:
        return -1
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return -1


def _release_map_song_key(row: Dict[str, object]) -> Optional[Tuple[str, str, str]]:
    """Display-only song presence; never acoustic identity or coverage."""
    title = str(row.get("title", "") or "")
    artist = re.split(r"\b(?:feat(?:uring)?|ft)\.?\b|;|,|&|\band\b|\bx\b",
        ascii_punctuation(str(row.get("artist", "") or "")),maxsplit=1,flags=re.I)[0]
    artist = artist_name_comparison_key(artist)
    family = ("live" if row.get("is_live") or is_live_text(title) else
              "remix" if row.get("is_remix") or is_remix_text(title) else "version")
    song = _base_title_identity(title) if family == "version" else identity_title(title)
    if not song or not artist:
        return None
    return song,min(_artist_identity_aliases(artist)),family


def _release_map_state_for_ui(
    snapshots: List[Dict[str, object]],
    tracks: Optional[List[Track]],
    pending_track_indices: Set[int],
    pending_release_ids: Set[int],
    blocked_release_ids: Set[int],
    editable: bool,
    dirty: bool,
    apply_enabled: bool,
    apply_highlighted: bool,
    initial_plan_counts: Optional[Dict[str, int]] = None,
    result: Optional[Dict[str, object]] = None,
    releases: Optional[List[Release]] = None,
    pinned_release_ids: Optional[Set[int]] = None,
) -> Dict[str, object]:
    # Full Map includes every analyzed release. Previously a lack of wanted
    # acoustic groups hid correctly removed remix-only OLD releases from both
    # Full Map and Changes > Removed. NEW SKIP rows remain inspectable but
    # do not count as additions/removals in Changes.
    visible = list(snapshots)
    visible.sort(key=lambda item: _release_date_sort_key_for_map(str(item.get("name", ""))))
    visible_ids = {int(item.get("release_id", -1)) for item in visible}

    # Build a display-only catalog of distinct recording groups that share the
    # same base song title. This intentionally does NOT merge those groups.
    # It only lets the Release Map show "other versions" (radio edit, album
    # version, remix, etc.) next to the currently selected track.
    version_group_catalog: Dict[str, Dict[int, Dict[str, object]]] = defaultdict(dict)
    for item in visible:
        rid = int(item.get("release_id", -1))
        release_name = str(item.get("name", ""))
        action = str(item.get("action", ""))
        release_retained = action in {"KEEP", "ADD", "REPLACE"}
        for row in item.get("tracklist", []) or []:
            base_key = (
                str(row.get("base_title_key", "") or "").strip()
                or _base_title_identity(str(row.get("title", "")))
            )
            group_id = _release_map_group_id(row)
            if not base_key or group_id < 0:
                continue
            group = version_group_catalog[base_key].setdefault(
                group_id,
                {
                    "aliases": set(),
                    "durations": [],
                    "duration_seconds": [],
                    "families": set(),
                    "carriers": {},
                },
            )
            title = str(row.get("title", "") or "").strip()
            if title:
                group["aliases"].add(title)
            duration = str(row.get("duration", "") or "").strip()
            if duration and duration not in group["durations"]:
                group["durations"].append(duration)
            try:
                seconds = float(row.get("duration_seconds", 0) or 0)
            except (ValueError, TypeError):
                seconds = 0.0
            if seconds > 0:
                group["duration_seconds"].append(seconds)
            row_is_live = bool(
                row.get("is_live")
                or is_live_text(str(row.get("title", "")))
            )
            row_is_remix = bool(
                row.get("is_remix")
                or is_remix_text(str(row.get("title", "")))
            )
            if row_is_live:
                group["families"].add("live")
            elif row_is_remix:
                group["families"].add("remix")
            else:
                group["families"].add("version")
            included = bool(row.get("included")) and not bool(row.get("excluded"))
            carrier = group["carriers"].setdefault(
                rid,
                {
                    "id": rid,
                    "name": release_name,
                    "retained": False,
                    "included": False,
                },
            )
            carrier["retained"] = bool(carrier["retained"] or (release_retained and included))
            carrier["included"] = bool(carrier["included"] or included)

    version_families: Dict[str, List[Dict[str, object]]] = {}
    for base_key, groups in version_group_catalog.items():
        if len(groups) <= 1:
            continue
        family_rows: List[Dict[str, object]] = []
        for group_id, raw in groups.items():
            aliases = sorted(
                list(raw.get("aliases", set()) or set()),
                key=lambda value: (len(str(value)), str(value).casefold()),
            )
            carriers = sorted(
                list((raw.get("carriers", {}) or {}).values()),
                key=lambda row: (
                    0 if bool(row.get("retained")) else 1,
                    0 if bool(row.get("included")) else 1,
                    str(row.get("name", "")).casefold(),
                ),
            )
            retained_carriers = [row for row in carriers if bool(row.get("retained"))]
            available_carriers = [row for row in carriers if bool(row.get("included"))]
            preferred = retained_carriers or available_carriers or carriers
            raw_families = set(raw.get("families", set()) or set())
            # If the same exact audio has conflicting labels, prefer a normal
            # Version identity over a special-family alias; exact audio remains
            # one group either way.
            if "version" in raw_families:
                semantic_family = "version"
            elif "live" in raw_families:
                semantic_family = "live"
            else:
                semantic_family = "remix"
            family_rows.append(
                {
                    "groupId": int(group_id),
                    "title": aliases[0] if aliases else "Unknown version",
                    "family": semantic_family,
                    "isRemix": semantic_family == "remix",
                    "isLive": semantic_family == "live",
                    "aliases": aliases[:6],
                    "duration": (raw.get("durations", []) or [""])[0],
                    "durationSeconds": round(
                        min(raw.get("duration_seconds", []) or [0.0]), 3
                    ),
                    "releaseId": int(preferred[0].get("id", -1)) if preferred else -1,
                    "releaseIds": [int(row.get("id", -1)) for row in carriers],
                    "releaseNames": [str(row.get("name", "")) for row in carriers[:6]],
                    "retainedReleaseNames": [
                        str(row.get("name", "")) for row in retained_carriers[:6]
                    ],
                    "retained": bool(retained_carriers),
                    "available": bool(available_carriers),
                }
            )
        family_rows.sort(
            key=lambda row: (
                0 if bool(row.get("retained")) else 1,
                0 if bool(row.get("available")) else 1,
                str(row.get("title", "")).casefold(),
                int(row.get("groupId", -1)),
            )
        )
        version_families[base_key] = family_rows

    # Track-level Gem is the single source of truth for both track and release
    # Gem badges. Only Version-family alternatives disqualify it. Remixes and
    # Live recordings are separate families and therefore do not.
    all_version_groups_by_base: Dict[str, Set[int]] = defaultdict(set)
    all_release_carriers_by_group: Dict[int, Set[int]] = defaultdict(set)
    all_song_carriers: Dict[Tuple[str,str,str],Set[int]] = defaultdict(set)

    for item in snapshots:
        source_rid = int(item.get("release_id", -1))
        for row in item.get("tracklist", []) or []:
            song_key = _release_map_song_key(row)
            if song_key is not None:
                all_song_carriers[song_key].add(source_rid)
            base_key = (
                str(row.get("base_title_key", "") or "").strip()
                or _base_title_identity(str(row.get("title", "")))
            )
            group_id = _release_map_group_id(row)
            row_is_remix = bool(
                row.get("is_remix")
                or is_remix_text(str(row.get("title", "")))
            )
            row_is_live = bool(
                row.get("is_live")
                or is_live_text(str(row.get("title", "")))
            )
            if group_id >= 0:
                all_release_carriers_by_group[group_id].add(source_rid)
            if base_key and group_id >= 0 and not row_is_remix and not row_is_live:
                all_version_groups_by_base[base_key].add(group_id)
    saved_pattern_kinds = _load_pattern_categories()
    personal_pattern_keys = _personal_pattern_keys(_load_personal_keep_rules(_load_app_settings()))
    nodes: List[Dict[str, object]] = []
    for item in visible:
        rid = int(item.get("release_id", -1))
        action = str(item.get("action", ""))
        retained = action in {"KEEP", "ADD", "REPLACE"}
        manual_removed = bool(item.get("manual_removed"))
        release_blocked = rid in blocked_release_ids
        pending_release_change = rid in pending_release_ids
        ui_tracks: List[Dict[str, object]] = []
        unique_count = 0
        gem_titles: List[str] = []
        for row in item.get("tracklist", []) or []:
            track_index = int(row.get("track_global_index", -1))
            track_album = str(row.get("album", "") or "")
            manual_skip = bool(row.get("manual_skip"))
            is_remix = bool(
                row.get("is_remix")
                or is_remix_text(str(row.get("title", "")))
            )
            is_live = bool(
                row.get("is_live")
                or is_live_text(str(row.get("title", "")))
            )
            if tracks is not None and 0 <= track_index < len(tracks):
                manual_skip = bool(tracks[track_index].manual_skip_rule)
                is_remix = bool(tracks[track_index].is_remix)
                is_live = bool(tracks[track_index].is_live)
                track_album = str(tracks[track_index].album or track_album)
            semantic_family = "live" if is_live else ("remix" if is_remix else "version")
            base_key = (
                str(row.get("base_title_key", "") or "").strip()
                or _base_title_identity(str(row.get("title", "")))
            )
            group_id = _release_map_group_id(row)
            included = bool(row.get("included")) and not bool(row.get("excluded"))
            matched_editions = (all_release_carriers_by_group.get(group_id,set()) - {rid}
                                if group_id >= 0 else set())
            listed_editions = all_song_carriers.get(_release_map_song_key(row),set()) - {rid}
            unverified_editions = listed_editions - matched_editions
            # Highlight the recordings that require this release to be retained.
            # Copies on discarded releases and unverified title listings do not
            # supply coverage in the retained plan.
            unique = bool(retained and included and not manual_skip
                and not manual_removed and row.get("unique_to_release")
                and not row.get("covered_by_other_retained")
                and not row.get("covered_by_names"))
            if unique:
                unique_count += 1
            track_is_gem = bool(
                unique
                and not matched_editions
                and not listed_editions
                and included
                and group_id >= 0
                and base_key
                and semantic_family == "version"
                and len(all_release_carriers_by_group.get(group_id, set())) == 1
                and len(all_version_groups_by_base.get(base_key, set())) == 1
            )
            if track_is_gem:
                title = str(row.get("title", "") or "").strip()
                if title and title not in gem_titles:
                    gem_titles.append(title)

            pattern_kind = ""
            pattern_key = ""
            if tracks is not None and 0 <= track_index < len(tracks):
                current_track = tracks[track_index]
                for key in sorted(track_pattern_keys(current_track)):
                    if key in saved_pattern_kinds:
                        pattern_kind = saved_pattern_kinds[key]["kind"]
                        pattern_key = key
                        break
                if not pattern_kind and not current_track.personal_keep_rule and not (
                    track_pattern_keys(current_track) & personal_pattern_keys
                ):
                    if current_track.is_live:
                        pattern_kind = "live"
                    elif current_track.is_remix:
                        pattern_kind = "remix"
                    elif current_track.excluded_by_pattern:
                        pattern_kind = "skip"
                    patterns = _track_classification_patterns(current_track)
                    if patterns:
                        pattern_key = patterns[0][0]
            ui_tracks.append(
                {
                    "patternKind": pattern_kind,
                    "patternKey": pattern_key,
                    "index": track_index,
                    "number": row.get("number", ""),
                    "title": str(row.get("title", "")),
                    "album": track_album,
                    "duration": str(row.get("duration", "")),
                    "durationSeconds": float(row.get("duration_seconds", 0) or 0),
                    "groupId": group_id,
                    "included": included,
                    "excluded": bool(row.get("excluded")),
                    "exclusionReason": str(row.get("exclusion_reason", "") or ""),
                    "explicitState": str(row.get("explicit_state", "unknown") or "unknown"),
                    "isRemix": is_remix,
                    "isLive": is_live,
                    "family": semantic_family,
                    "isGem": track_is_gem,
                    "manualSkip": manual_skip,
                    "integrityError": str(row.get("integrity_error", "") or ""),
                    "pendingIgnore": bool(track_index in pending_track_indices and manual_skip),
                    "pendingRestore": bool(track_index in pending_track_indices and not manual_skip),
                    "unique": unique,
                    "excludedCounterparts": list(row.get("excluded_counterparts", []) or []),
                    "audioMatchEditions": len(matched_editions),
                    "unverifiedEditions": len(unverified_editions),
                    "orphaned": bool(row.get("orphaned")),
                    "coveredBy": list(row.get("covered_by_names", []) or []),
                    "coveredByAlternateVersion": bool(row.get("covered_by_alternate_version")),
                    "replacementSource": str(row.get("replacement_source", "") or ""),
                    "replacementAlternates": list(row.get("replacement_alternates", []) or []),
                    "distinction": str(row.get("distinction", "")),
                    "baseKey": base_key,
                }
            )
        nodes.append(
            {
                "id": rid,
                "name": str(item.get("name", "")),
                "path": str(item.get("path", "")),
                "action": action,
                "kind": "retained" if retained else "duplicate",
                "outcome": str(item.get("outcome", "")),
                "manualRemoved": manual_removed,
                "typeWarning": str(item.get("type_warning", "") or ""),
                "releaseBlocked": release_blocked,
                "forceKeep": rid in (pinned_release_ids or set()),
                "pendingReleaseChange": pending_release_change,
                "pendingReleaseIgnore": bool(pending_release_change and release_blocked),
                "pendingReleaseRestore": bool(pending_release_change and not release_blocked),
                "reason": str(item.get("reason", "")),
                "auditIssues": list(item.get("audit_issues", []) or []),
                "releaseType": str(item.get("release_type", "") or "").lower(),
                "family": str(item.get("family", "") or ""),
                "rootKind": str(item.get("root_kind", "") or ""),
                "sourceRoot": str(item.get("scan_root", "") or ""),
                "sourceMedium": str(item.get("source_medium", "") or ""),
                "sourceRank": int(item.get("source_rank", 0) or 0),
                "sourceDescription": str(item.get("source", "") or ""),
                "upgradeFrom": [
                    {
                        "releaseId": int(row.get("release_id", -1)),
                        "name": str(row.get("name", "") or ""),
                        "sourceMedium": str(row.get("source_medium", "") or ""),
                        "source": str(row.get("source", "") or ""),
                        "sourceRoot": str(row.get("scan_root", "") or ""),
                        "sourceRank": int(row.get("source_rank", 0) or 0),
                        "includedTracks": int(row.get("included_tracks", 0) or 0),
                        "upgradeReason": str(row.get("upgrade_reason", "") or ""),
                    }
                    for row in (item.get("related", []) or [])
                    if action == "REPLACE"
                    and str(row.get("root_kind", "") or "") == "existing"
                ],
                "albumTitles": sorted({
                    str(track.get("album", "") or "").strip()
                    for track in ui_tracks
                    if str(track.get("album", "") or "").strip()
                }),
                "displayGroupKey": "",
                "displayGroupTitle": "",
                "includedTracks": int(item.get("included_tracks", 0) or 0),
                "uniqueCount": unique_count,
                "isGem": bool(gem_titles),
                "gemTitles": gem_titles[:6],
                "tracks": ui_tracks,
            }
        )

    _assign_release_map_display_groups(nodes, releases)

    duplicate_links: List[Dict[str, int]] = []
    seen_links: Set[Tuple[int, int]] = set()
    snapshot_by_id = {int(item.get("release_id", -1)): item for item in visible}
    for item in visible:
        duplicate_id = int(item.get("release_id", -1))
        if str(item.get("action", "")) in {"KEEP", "ADD", "REPLACE"}:
            continue

        targets: List[int] = []
        for row in item.get("coverage", []) or []:
            target = int(row.get("release_id", -1))
            if target in visible_ids:
                targets.append(target)

        if not targets:
            for row in item.get("related", []) or []:
                target = int(row.get("release_id", -1))
                target_item = snapshot_by_id.get(target)
                if (
                    target_item is not None
                    and str(target_item.get("action", "")) in {"KEEP", "ADD", "REPLACE"}
                ):
                    targets.append(target)

        for target in targets:
            key = (duplicate_id, target)
            if key in seen_links or duplicate_id == target:
                continue
            seen_links.add(key)
            duplicate_links.append({"duplicate": duplicate_id, "retained": target})

    current_plan_counts = _release_map_plan_counts(snapshots)
    baseline = dict(initial_plan_counts or current_plan_counts)
    initial_releases = max(0, int(baseline.get("releases", 0) or 0))
    initial_tracks = max(0, int(baseline.get("tracks", 0) or 0))
    current_releases = max(0, int(current_plan_counts.get("releases", 0) or 0))
    current_tracks = max(0, int(current_plan_counts.get("tracks", 0) or 0))

    return {
        "standaloneMode": not any(str(n.get("rootKind", "")) == "existing" for n in nodes),
        "auditIssueCount": sum(len(item.get("audit_issues", []) or []) for item in snapshots),
        "auditReleaseCount": sum(bool(item.get("audit_issues", [])) for item in snapshots),
        "scannedCounts": {
            "releases": len(snapshots),
            "tracks": sum(max(0, len(item.get("tracklist", []) or [])) for item in snapshots),
        },
        "editable": bool(editable),
        "dirty": bool(dirty),
        "applyEnabled": bool(apply_enabled),
        "applyHighlighted": bool(apply_highlighted),
        "planCounts": {
            "initial": {
                "releases": initial_releases,
                "tracks": initial_tracks,
            },
            "result": {
                "releases": current_releases,
                "tracks": current_tracks,
            },
            "delta": {
                "releases": current_releases - initial_releases,
                "tracks": current_tracks - initial_tracks,
            },
        },
        "sourceRoots": {
            "existing": next(
                (
                    str(node.get("sourceRoot", "") or "")
                    for node in nodes
                    if str(node.get("rootKind", "") or "") == "existing"
                    and str(node.get("sourceRoot", "") or "")
                ),
                "",
            ),
            "recycle": next(
                (
                    str(node.get("sourceRoot", "") or "")
                    for node in nodes
                    if str(node.get("rootKind", "") or "") == "recycle"
                    and str(node.get("sourceRoot", "") or "")
                ),
                "",
            ),
        },
        "nodes": nodes,
        "versionFamilies": version_families,
        "duplicateLinks": duplicate_links,
        "result": result or {"show": False, "causes": [], "added": [], "removed": [], "replacementSources": []},
    }


def launch_webview_release_map(session: Dict[str, object]) -> Dict[str, object]:
    """Open the full regular Release Map in a lightweight WebView2 host."""
    webview = ensure_light_ui_dependencies()
    _ensure_webview2_runtime()

    class ReleaseMapBridge:

        def __init__(self):
            self.window = None
            self.done_event = threading.Event()
            self.result_payload: Optional[Dict[str, object]] = None
            self.snapshots = list(session.get("snapshots", []) or [])
            self.releases = session.get("releases")
            self.tracks = session.get("tracks")
            self.groups = session.get("groups")
            self.selected = set(session.get("selected", set()) or set())
            self.reviews = list(session.get("reviews", []) or [])
            self.decisions = list(session.get("decisions", []) or [])
            self.blocked_release_ids = set(session.get("blocked_release_ids", set()) or set())
            self.comparison_log_path = session.get("comparison_log_path")
            self.editable = bool(
                session.get("allow_apply")
                and isinstance(self.releases, list)
                and isinstance(self.tracks, list)
                and isinstance(self.groups, dict)
            )
            self.dirty = False
            self.integrity_blockers = [
                (str(snapshot.get("name", "")), list(snapshot.get("audit_issues", []) or []))
                for snapshot in self.snapshots if snapshot.get("audit_issues")
            ]
            self.apply_enabled = bool(self.editable) and not self.integrity_blockers
            self.apply_highlighted = False
            self.pending_track_indices: Set[int] = set()
            self.pending_release_ids: Set[int] = set()
            self.pending_causes: List[str] = []
            self.result = {"show": False, "causes": [], "added": [], "removed": [], "replacementSources": []}
            self.initial_track_skip_state = {
                index: bool(track.manual_skip_rule)
                for index, track in enumerate(self.tracks or [])
            }
            self.initial_blocked_release_ids = set(self.blocked_release_ids)
            stored_kept = _load_manual_kept_release_paths()
            self.pinned_release_ids = {rel.rid for rel in (self.releases or [])
                if _manual_album_group_path_key(rel.path) in stored_kept}
            self.initial_pinned_release_ids = set(self.pinned_release_ids)
            self.requires_fresh_scan = False
            self.initial_manual_album_group_links = _manual_album_group_links()
            supplied_initial = session.get("initial_plan_counts")
            if isinstance(supplied_initial, dict):
                self.initial_plan_counts = {
                    "releases": max(0, int(supplied_initial.get("releases", 0) or 0)),
                    "tracks": max(0, int(supplied_initial.get("tracks", 0) or 0)),
                }
            else:
                self.initial_plan_counts = _release_map_plan_counts(self.snapshots)
            self._ui_state: Dict[str, object] = {}
            self._rebuild_ui_state()

        def _rebuild_ui_state(self) -> None:
            self._ui_state = _release_map_state_for_ui(
                self.snapshots,
                self.tracks if isinstance(self.tracks, list) else None,
                self.pending_track_indices,
                self.pending_release_ids,
                self.blocked_release_ids,
                self.editable,
                self.dirty,
                self.apply_enabled and not self.integrity_blockers,
                self.apply_highlighted,
                self.initial_plan_counts,
                self.result,
                self.releases if isinstance(self.releases, list) else None,
                self.pinned_release_ids,
            )
            new_root = session.get("recycle")
            if not new_root:
                new_root = self._ui_state.get("sourceRoots", {}).get("recycle", "")
            if not new_root:
                new_root = next(
                    (
                        str(row.get("scan_root", "") or "").strip()
                        for row in self.snapshots
                        if str(row.get("root_kind", "")).lower() == "recycle"
                        and str(row.get("scan_root", "") or "").strip()
                    ),
                    "",
                )
            self._ui_state["defaultExportDestination"] = (
                str(default_updated_destination(Path(new_root))) if new_root else ""
            )

        def _sync_ui_root(self) -> None:
            if not self._ui_state:
                self._rebuild_ui_state()
            self._ui_state["editable"] = bool(self.editable)
            self._ui_state["dirty"] = bool(self.dirty)
            self._ui_state["applyEnabled"] = bool(self.apply_enabled and not self.integrity_blockers)
            self._ui_state["applyHighlighted"] = bool(self.apply_highlighted)
            self._ui_state["requiresFreshScan"] = bool(self.requires_fresh_scan)
            self._ui_state["result"] = self.result

        def _state(self) -> str:
            self._sync_ui_root()
            return _json_ui_dumps(self._ui_state)

        def _toggle_delta_base(self) -> Dict[str, object]:
            return {
                "dirty": bool(self.dirty),
                "applyEnabled": bool(self.apply_enabled),
                "applyHighlighted": bool(self.apply_highlighted),
                "result": self.result,
            }

        def _refresh_pending_state(self) -> None:
            has_pending = bool(
                self.pending_track_indices or self.pending_release_ids
                or self.pinned_release_ids != self.initial_pinned_release_ids
                or self.requires_fresh_scan
                or _manual_album_group_links() != self.initial_manual_album_group_links
            )
            self.dirty = has_pending
            self.apply_enabled = bool(self.editable and not has_pending and not self.requires_fresh_scan)
            self.apply_highlighted = False
            if not has_pending:
                self.pending_causes.clear()
                self.result = {
                    "show": False,
                    "causes": [],
                    "added": [],
                    "removed": [],
                    "replacementSources": [],
                }
            self._sync_ui_root()

        def _patch_cached_release_state(self, release_id: int) -> None:
            if not self._ui_state:
                return
            blocked = release_id in self.blocked_release_ids
            pending = release_id in self.pending_release_ids
            for node in self._ui_state.get("nodes", []) or []:
                if int(node.get("id", -1)) != int(release_id):
                    continue
                node["releaseBlocked"] = bool(blocked)
                node["pendingReleaseChange"] = bool(pending)
                node["pendingReleaseIgnore"] = bool(pending and blocked)
                node["pendingReleaseRestore"] = bool(pending and not blocked)
                return

        def _mark_dirty(self, cause: str) -> None:
            self.dirty = True
            self.apply_enabled = False
            self.apply_highlighted = False
            self.result = {"show": False, "causes": [], "added": [], "removed": [], "replacementSources": []}
            if cause:
                self.pending_causes.append(cause)

        def getState(self):
            return self._state()

        def toggleTrack(self, track_index: int):
            if not self.editable or not isinstance(self.tracks, list):
                return self._state()
            if not (0 <= track_index < len(self.tracks)):
                return self._state()

            track = self.tracks[track_index]
            label = track.display_title
            before = [bool(row.manual_skip_rule) for row in self.tracks]
            if track.manual_skip_rule:
                remove_persistent_track_skip(track.manual_skip_rule, self.tracks)
                self._mark_dirty(f'IF recording everywhere: "{label}" restored')
            else:
                add_persistent_track_skip(track, self.tracks)
                self._mark_dirty(f'IF recording everywhere: "{label}" ignored')

            changed = [
                i for i, row in enumerate(self.tracks)
                if before[i] != bool(row.manual_skip_rule)
            ]
            if not changed:
                return self._state()
            for i in changed:
                initial = bool(self.initial_track_skip_state.get(i, False))
                if bool(self.tracks[i].manual_skip_rule) == initial:
                    self.pending_track_indices.discard(i)
                else:
                    self.pending_track_indices.add(i)

            self._refresh_pending_state()
            # Reuse the full display policy for Ignore/Restore, including
            # retention and global Gem guards. Only deltas reach the DOM.
            self._rebuild_ui_state()
            ui_tracks = {
                int(row.get("index", -1)): row
                for node in self._ui_state.get("nodes", []) or []
                for row in node.get("tracks", []) or []
            }
            patched = [
                {
                    "index": int(i),
                    "manualSkip": bool(self.tracks[i].manual_skip_rule),
                    "pendingIgnore": bool(
                        i in self.pending_track_indices
                        and self.tracks[i].manual_skip_rule
                    ),
                    "pendingRestore": bool(
                        i in self.pending_track_indices
                        and not self.tracks[i].manual_skip_rule
                    ),
                    "unique": bool(ui_tracks.get(i, {}).get("unique")),
                    "isGem": bool(ui_tracks.get(i, {}).get("isGem")),
                }
                for i in changed
            ]
            clicked = next(row for row in patched if row["index"] == track_index)
            changed_release_ids = {self.tracks[i].release_id for i in changed}
            payload = {
                "kind": "trackToggle",
                "trackIndex": int(track_index),
                "tracks": patched,
                "releases": [
                    {key: node.get(key) for key in ("id", "uniqueCount", "isGem", "gemTitles")}
                    for node in self._ui_state.get("nodes", []) or []
                    if node.get("id") in changed_release_ids
                ],
                "affectedCopies": len(changed),
                "scope": "acoustic-recording" if track.group_id >= 0 else "instance",
                **{key: clicked[key] for key in ("manualSkip", "pendingIgnore", "pendingRestore")},
                **self._toggle_delta_base(),
            }
            return _json_ui_dumps(payload)

        def markTrackPattern(self, track_index: int, kind: str):
            if not self.editable or not (0 <= track_index < len(self.tracks)):
                return self._state()
            if kind not in {"remix", "live", "skip", "keep"}:
                raise ValueError("Unknown track classification.")
            track = self.tracks[track_index]
            categories = _load_pattern_categories()
            matches = [key for key in sorted(track_pattern_keys(track)) if key in categories]
            if kind == "keep" and matches:
                key = matches[0]
                label = categories[key]["label"]
            else:
                key, label = _classify_track_pattern(track, kind)
            # Clicking the current classification reverses it into Personal Picks.
            previous = categories.get(key, {}).get("kind", "")
            # Existing automatic Remix/Live detection is only a display hint:
            # clicking 🇷/🇱 must SAVE the chosen category on the first click,
            # not silently turn that recording into a Personal Pick.
            promote = _promote_pattern_choice(kind, previous)
            if promote:
                categories.pop(key, None)
                settings = _load_app_settings()
                picks = _load_personal_keep_rules(settings)
                _add_personal_pattern_rule(picks, key, label)
                _save_app_settings(
                    str(settings.get("existing_discography", "") or ""),
                    str(settings.get("recycle_update_folder", "") or ""),
                    bool(settings.get("save_remixes", False)),
                    bool(settings.get("save_live", False)),
                    bool(settings.get("logging_enabled", False)),
                    personal_keep_rules=picks,
                    io_workers=str(settings.get("io_workers", "auto") or "auto"),
                )
                if key not in _personal_pattern_keys(_load_personal_keep_rules(_load_app_settings())):
                    raise OSError("Could not persist Personal Picks; classification not changed.")
            else:
                # Categories and explicit pattern Keeps are mutually exclusive.
                settings = _load_app_settings()
                picks = _load_personal_keep_rules(settings)
                filtered = [item for item in picks if _personal_pattern_key(item) != key]
                if len(filtered) != len(picks):
                    _save_app_settings(
                        str(settings.get("existing_discography", "") or ""),
                        str(settings.get("recycle_update_folder", "") or ""),
                        bool(settings.get("save_remixes", False)),
                        bool(settings.get("save_live", False)),
                        bool(settings.get("logging_enabled", False)),
                        personal_keep_rules=filtered,
                        io_workers=str(settings.get("io_workers", "auto") or "auto"),
                    )
                    if key in _personal_pattern_keys(_load_personal_keep_rules(_load_app_settings())):
                        raise OSError("Could not clear conflicting Personal Pick.")
                categories[key] = {"kind": kind, "label": label}
            _save_pattern_categories(categories)
            # A new inclusion choice may need fingerprints that an earlier scan
            # never computed. Never silently re-optimize the stale acoustic groups.
            self.requires_fresh_scan = True
            self._mark_dirty(f'Pattern "{label}": {"Personal Picks" if promote else kind}')
            self._refresh_pending_state()
            patches = []
            for i, item in enumerate(self.tracks):
                candidate_keys = track_pattern_keys(item)
                if key not in candidate_keys:
                    continue
                matched = [k for k in sorted(candidate_keys) if k in categories]
                if matched:
                    cat_key = matched[0]
                    status = categories[cat_key]["kind"]
                else:
                    cat_key = key
                    status = "" if promote else kind
                    if not promote:
                        status = kind
                patches.append({"index": i, "patternKey": cat_key, "patternKind": status})
                for node in self._ui_state.get("nodes", []):
                    for row in node.get("tracks", []):
                        if row.get("index") == i:
                            row["patternKey"] = cat_key
                            row["patternKind"] = status
            return _json_ui_dumps({
                "kind": "patternToggle", "tracks": patches,
                "requiresFreshScan": True, **self._toggle_delta_base(),
            })

        def toggleReleaseKeep(self, release_id: int):
            if not self.editable:
                return self._state()
            rel = next((row for row in self.releases if row.rid == release_id), None)
            if rel is None:
                return self._state()
            if release_id in self.pinned_release_ids:
                self.pinned_release_ids.remove(release_id)
                note = f'Keep reverted to automatic: "{rel.path.name}"'
            else:
                was_ignored = release_id in self.blocked_release_ids
                self.blocked_release_ids.discard(release_id)
                self.pinned_release_ids.add(release_id)
                if was_ignored:
                    # Keep supersedes an old committed Ignore immediately,
                    # including when the user closes before Re-Analyze.
                    _save_manual_ignored_release_paths(
                        _committed_ignore_paths_for_plan(self.releases, self.blocked_release_ids)
                    )
                note = f'Keep release: "{rel.path.name}"'
            _save_manual_kept_release_paths(
                _committed_kept_paths_for_plan(self.releases, self.pinned_release_ids)
            )
            self._mark_dirty(note)
            self._refresh_pending_state()
            self._rebuild_ui_state()
            return self._state()

        def toggleRelease(self, release_id: int):
            if not self.editable:
                return self._state()
            release = next((r for r in self.releases if r.rid == release_id), None)
            if release is None:
                return self._state()

            if release_id in self.blocked_release_ids:
                self.blocked_release_ids.remove(release_id)
                self._mark_dirty(f'IF release: "{release.path.name}" restored')
            else:
                self.pinned_release_ids.discard(release_id)
                self.blocked_release_ids.add(release_id)
                self._mark_dirty(f'IF release: "{release.path.name}" ignored')

            if (release_id in self.blocked_release_ids) == (
                release_id in self.initial_blocked_release_ids
            ):
                self.pending_release_ids.discard(release_id)
            else:
                self.pending_release_ids.add(release_id)

            self._refresh_pending_state()
            self._patch_cached_release_state(release_id)
            blocked = release_id in self.blocked_release_ids
            payload = {
                "kind": "releaseToggle",
                "releaseId": int(release_id),
                "releaseBlocked": bool(blocked),
                "pendingReleaseChange": bool(release_id in self.pending_release_ids),
                "pendingReleaseIgnore": bool(
                    release_id in self.pending_release_ids and blocked
                ),
                "pendingReleaseRestore": bool(
                    release_id in self.pending_release_ids and not blocked
                ),
                **self._toggle_delta_base(),
            }
            return _json_ui_dumps(payload)

        def setAlbumGroup(self, release_id: int, target_release_id: int):
            """Move an Album/EP into another family; -1 restores automatic."""
            if not self.editable:
                return self._state()
            source = next((rel for rel in self.releases if rel.rid == int(release_id)), None)
            if source is None or source.release_type not in {"album", "ep"}:
                raise ValueError("Only Album/EP releases can be assigned to these families.")
            source_key = _manual_album_group_path_key(source.path)
            links = _manual_album_group_links()
            target_id = int(target_release_id)
            if target_id < 0:
                if source_key not in links:
                    return self._state()
                del links[source_key]
                note = f'Manual album group restored automatically: "{source.path.name}"'
            else:
                target = next((rel for rel in self.releases if rel.rid == target_id), None)
                if target is None or target.release_type not in {"album", "ep"} or target.rid == source.rid:
                    raise ValueError("Select another Album/EP family from the current analysis.")
                target_key = _manual_album_group_path_key(target.path)
                # A directed cycle would make override maintenance confusing.
                seen = {source_key}
                cursor = target_key
                while cursor in links:
                    if cursor in seen:
                        raise ValueError("Album group move would create a circular assignment.")
                    seen.add(cursor)
                    cursor = links[cursor]
                if cursor == source_key:
                    raise ValueError("Album group move would create a circular assignment.")
                if links.get(source_key) == target_key:
                    return self._state()
                links[source_key] = target_key
                note = f'Manual album family: "{source.path.name}" -> "{target.path.name}"'
            _save_manual_album_group_links(links)
            self._mark_dirty(note)
            self._refresh_pending_state()
            # Show the new visual grouping immediately but never apply file
            # actions until the user explicitly clicks Re-Analyze.
            self._rebuild_ui_state()
            return self._state()

        def reanalyze(self):
            if not self.editable or not self.dirty:
                return self._state()
            old_selected = set(self.selected)
            apply_persistent_track_skips(self.tracks)
            # Reuse verified acoustic groups; recalculate the entire selection
            # against the current Ignore/Restore and album-family constraints.
            if self.requires_fresh_scan:
                raise RuntimeError("Pattern classifications changed. Close Release Map and run Analyze again.")
            new_selected = optimize_collection(
                self.releases,
                self.groups,
                self.blocked_release_ids,
                comparison_log_path=self.comparison_log_path,
                forced_release_ids=self.pinned_release_ids,
            )
            if new_selected & self.blocked_release_ids:
                raise RuntimeError("Re-Analyze retained an explicitly ignored release.")
            new_decisions = build_release_decisions(
                self.releases,
                self.tracks,
                new_selected,
                self.reviews,
                self.blocked_release_ids,
            )
            new_snapshots = build_decision_snapshot(
                self.releases,
                self.tracks,
                new_selected,
                new_decisions,
                self.blocked_release_ids,
            )
            by_id = {r.rid: r for r in self.releases}
            added_ids = sorted(new_selected - old_selected)
            removed_ids = sorted(old_selected - new_selected)
            added = [by_id[rid].path.name for rid in added_ids if rid in by_id]
            removed = [by_id[rid].path.name for rid in removed_ids if rid in by_id]
            replacement_rows: List[Dict[str, object]] = []
            snapshot_by_id = {
                int(item.get("release_id", -1)): item for item in new_snapshots
            }
            for release_id in sorted(self.blocked_release_ids):
                snap = snapshot_by_id.get(release_id)
                if not snap or not bool(snap.get("manual_removed")):
                    continue
                rows: List[Dict[str, object]] = []
                for row in snap.get("tracklist", []) or []:
                    if not bool(row.get("included")) or bool(row.get("excluded")):
                        continue
                    source = str(row.get("replacement_source", "") or "")
                    alternates = list(row.get("replacement_alternates", []) or [])
                    rows.append({
                        "title": str(row.get("title", "")),
                        "source": source,
                        "alternates": alternates,
                        "missing": not bool(source),
                    })
                replacement_rows.append({
                    "release": str(snap.get("name", "")),
                    "tracks": rows,
                })
            # Record the new actual decisions, including unchanged selections.
            # The old comparison log's fingerprint verdicts remain intact.
            audit = {
                "causes": list(self.pending_causes) or ["Manual planning changes"],
                "blocked_release_ids": sorted(self.blocked_release_ids),
                "blocked_releases": [
                    by_id[rid].path.name for rid in sorted(self.blocked_release_ids)
                    if rid in by_id
                ],
                "previous_selected_release_ids": sorted(old_selected),
                "selected_release_ids": sorted(new_selected),
                "added_release_ids": added_ids,
                "removed_release_ids": removed_ids,
                "releases": [
                    {
                        "release_id": int(snapshot.get("release_id", -1)),
                        "name": str(snapshot.get("name", "")),
                        "action": str(snapshot.get("action", "")),
                        "reason": str(snapshot.get("reason", "")),
                        "manual_removed": bool(snapshot.get("manual_removed", False)),
                        "essential_tracks": list(snapshot.get("essential_tracks", []) or []),
                    }
                    for snapshot in new_snapshots
                ],
                "replacement_sources": replacement_rows,
            }
            # Commit Ignore choices only after a successful re-optimization;
            # a pending Ignore never silently becomes permanent.
            _save_manual_ignored_release_paths(
                _committed_ignore_paths_for_plan(self.releases, self.blocked_release_ids)
            )
            _save_manual_kept_release_paths(
                _committed_kept_paths_for_plan(self.releases, self.pinned_release_ids)
            )
            self.initial_pinned_release_ids = set(self.pinned_release_ids)
            _save_decision_snapshot(new_snapshots)
            audit_path = _write_reanalysis_audit(audit, self.comparison_log_path)
            self.selected = new_selected
            self.decisions = new_decisions
            self.snapshots = new_snapshots
            self.result = {
                "show": True,
                "causes": audit["causes"],
                "added": added,
                "removed": removed,
                "addedReleaseIds": added_ids,
                "removedReleaseIds": removed_ids,
                "highlightToken": str(time.time_ns()),
                "replacementSources": replacement_rows,
                "auditLogPath": str(audit_path),
            }
            self.pending_causes.clear()
            self.pending_track_indices.clear()
            self.pending_release_ids.clear()
            self.dirty = False
            self.apply_enabled = not bool(self.integrity_blockers)
            self.apply_highlighted = bool(added or removed)
            self.initial_track_skip_state = {
                index: bool(track.manual_skip_rule)
                for index, track in enumerate(self.tracks or [])
            }
            self.initial_blocked_release_ids = set(self.blocked_release_ids)
            self.initial_manual_album_group_links = _manual_album_group_links()
            self._rebuild_ui_state()
            return self._state()

        def openFolder(self, value: str):
            try:
                _open_path_location(value)
            except Exception:
                if self.window is not None:
                    try:
                        self.window.run_js(
                            'window.alert("This release path could not be opened. The displayed path remains unchanged.");'
                        )
                    except Exception:
                        pass

        def copyPath(self, value: str):
            _copy_text_to_clipboard(value or "")

        def chooseDestination(self, mode: str):
            if self.window is None:
                return ""
            roots = [
                str(item.get("scan_root", "") or "").strip()
                for item in self.snapshots
                if str(item.get("scan_root", "") or "").strip()
            ]
            start = ""
            if roots:
                try:
                    start = str(Path(roots[0]).parent)
                except Exception:
                    start = ""
            if not start or not Path(start).is_dir():
                start = str(Path.home())
            chosen_items = self.window.create_file_dialog(
                webview.FileDialog.FOLDER,
                directory=start,
            )
            return chosen_items[0] if chosen_items else ""

        def copyPlan(self, mode: str, destination: str):
            mode = str(mode or "").strip().lower()
            destination = str(destination or "").strip()
            if (
                not self.editable
                or self.dirty
                or not self.apply_enabled
                or self.integrity_blockers
                or mode not in {"all", "new"}
            ):
                return
            if not destination:
                source = session.get("recycle")
                if not source:
                    return
                destination = str(default_updated_destination(Path(source)))
            self.result_payload = {
                "action": "copy_all" if mode == "all" else "move_all",
                "destination": destination,
                "snapshots": self.snapshots,
                "selected": self.selected,
                "decisions": self.decisions,
                "blocked_release_ids": self.blocked_release_ids,
                "initial_plan_counts": self.initial_plan_counts,
            }
            self.done_event.set()
            if self.window is not None:
                self.window.destroy()

        def closeMap(self):
            self.result_payload = {
                "action": "close",
                "snapshots": self.snapshots,
                "selected": self.selected,
                "decisions": self.decisions,
                "blocked_release_ids": self.blocked_release_ids,
                "initial_plan_counts": self.initial_plan_counts,
                "requires_fresh_scan": bool(self.requires_fresh_scan),
                "pending_plan": bool(self.dirty),
            }
            self.done_event.set()
            if self.window is not None:
                self.window.destroy()


    bridge = ReleaseMapBridge()
    window = webview.create_window(
        f"{APP_NAME} {APP_VERSION} - Under construction ⚠️ - Release Map",
        html=_webview_release_map_html(),
        width=1500,
        height=920,
        min_size=(1050, 680),
        background_color="#0b0c0f",
        text_select=True,
        zoomable=True,
    )
    bridge.window = window
    _expose_bridge_methods(
        window,
        bridge,
        (
            "getState",
            "toggleTrack",
            "toggleRelease",
            "toggleReleaseKeep",
            "markTrackPattern",
            "setAlbumGroup",
            "reanalyze",
            "openFolder",
            "copyPath",
            "chooseDestination",
            "copyPlan",
            "closeMap",
        ),
    )

    def _closed():
        if bridge.result_payload is None:
            bridge.result_payload = {
                "action": "close",
                "snapshots": bridge.snapshots,
                "selected": bridge.selected,
                "decisions": bridge.decisions,
                "blocked_release_ids": bridge.blocked_release_ids,
                "initial_plan_counts": bridge.initial_plan_counts,
                "requires_fresh_scan": bool(bridge.requires_fresh_scan),
                "pending_plan": bool(bridge.dirty),
            }
        bridge.done_event.set()

    window.events.closed += _closed
    bridge.done_event.wait()
    return bridge.result_payload or {"action": "close"}


def _startup_crash_log_path() -> Path:
    _migrate_legacy_app_data()
    return _logs_dir() / "Music Collection Cleaner - Crash.log"


def _report_startup_crash(exc: BaseException) -> None:
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    path = _startup_crash_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"{APP_NAME} {APP_VERSION}\n"
            f"Startup failed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{details}",
            encoding="utf-8",
        )
    except Exception:
        pass

    message = (
        f"Startup failed.\n\n{type(exc).__name__}: {exc}\n\n"
        f"Crash log:\n{path}"
    )
    try:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        else:
            sys.stderr.write(message + "\n")
    except Exception:
        pass


def _webview_main_html() -> str:
    html = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Music Collection Cleaner</title>
<style>
:root{
  color-scheme:dark;
  --bg:#0a0a0a;--surface:#101010;--raised:#171717;--line:rgba(255,255,255,.11);--line2:rgba(255,255,255,.06);
  --t1:#ededed;--t2:#a1a1a1;--t3:#6f6f6f;--hover:rgba(255,255,255,.05);--sel:rgba(255,255,255,.09);
  --amber:#f5a623;--green:#4ade80;--red:#ff6369;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--t1);font:14px/1.45 "Segoe UI Variable","Segoe UI",system-ui,sans-serif}
body{display:flex;flex-direction:column;overflow:hidden}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer}
button:disabled,input:disabled,select:disabled{opacity:.4;cursor:default}
:focus-visible{outline:2px solid var(--t1);outline-offset:2px}
svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;flex:none}

#scroll{flex:1;min-height:0;overflow-y:auto}
#col{width:min(680px,100%);margin:0 auto;padding:36px 24px 24px}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
h1{margin:0;font-size:26px;font-weight:600;letter-spacing:-.02em}
.iconBtn{width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:6px;background:transparent;color:var(--t2);position:relative}
.iconBtn:hover:not(:disabled){background:var(--hover);color:var(--t1)}
.dotOn::after{content:"";position:absolute;top:6px;right:6px;width:7px;height:7px;border-radius:50%;background:var(--amber)}

.lbl{margin:0 0 8px;font-size:12px;color:var(--t2);letter-spacing:.02em}
.folder{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto auto;gap:6px;align-items:center;margin-bottom:8px}
.seg{display:inline-flex;padding:2px;border:1px solid var(--line);border-radius:8px}
.seg button{height:28px;padding:0 11px;border:0;border-radius:6px;background:transparent;color:var(--t2);font-size:13px}
.seg button:hover:not(:disabled){color:var(--t1)}
.seg button[aria-pressed="true"]{background:var(--sel);color:var(--t1)}
.path{height:34px;min-width:0;padding:0 12px;border:1px solid var(--line);border-radius:6px;background:var(--surface);outline:none}
.path:focus{border-color:var(--t2)}
.path::placeholder{color:var(--t3)}
.btn{height:34px;padding:0 14px;border:1px solid var(--line);border-radius:6px;background:transparent;white-space:nowrap}
.btn:hover:not(:disabled){background:var(--hover);border-color:rgba(255,255,255,.28)}
.btn.main{background:var(--t1);border-color:var(--t1);color:var(--bg);font-weight:600}
.btn.main:hover:not(:disabled){background:#fff}
.btn.quiet{border-color:transparent;color:var(--t2)}
.btn.quiet:hover:not(:disabled){color:var(--t1)}
.btn.danger{color:var(--red);border-color:rgba(255,99,105,.4)}
.btn.small{height:28px;padding:0 10px;font-size:13px}
#addFolder{margin:2px 0 28px 0}

.switch{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 0;border-top:1px solid var(--line2);cursor:pointer}
.switch:last-of-type{border-bottom:1px solid var(--line2)}
.switch .name{font-size:14px}
.switch .hint{color:var(--t3);font-size:12px}
.switch input{appearance:none;width:34px;height:20px;border-radius:999px;background:#2a2a2a;position:relative;flex:none;cursor:pointer;margin:0;transition:background .15s}
.switch input::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:var(--t2);transition:transform .15s,background .15s}
.switch input:checked{background:var(--t1)}
.switch input:checked::after{transform:translateX(14px);background:var(--bg)}

#work{display:none;margin-top:28px}
#work.on{display:block}
#statusRow{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px}
#status{font-weight:500}
#pct{color:var(--t2);font-variant-numeric:tabular-nums}
#bar{height:3px;border-radius:2px;background:#262626;overflow:hidden}
#fill{height:100%;width:0;background:var(--t1);transition:width .3s}
#detail{margin-top:8px;color:var(--t2);font-size:13px;min-height:19px}
#logToggle{margin-top:10px;padding:0;border:0;background:transparent;color:var(--t2);font-size:13px}
#logToggle:hover{color:var(--t1)}
#log{display:none;margin-top:8px;max-height:220px;overflow:auto;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);
  color:var(--t2);font:12px/1.55 "Cascadia Mono",Consolas,monospace;white-space:pre-wrap;word-break:break-word;user-select:text}
#log.on{display:block}

#foot{padding:14px 0;border-top:1px solid var(--line);background:var(--bg)}
#footIn{width:min(680px,100%);margin:0 auto;padding:0 24px;display:flex;align-items:center;gap:10px}
#footIn .sp{flex:1}
#analyze{height:38px;padding:0 24px}

/* menu */
#menu{display:none;position:fixed;top:64px;right:max(24px,calc(50% - 316px));z-index:50;width:280px;padding:6px;border:1px solid var(--line);border-radius:10px;background:var(--raised);box-shadow:0 12px 32px rgba(0,0,0,.6)}
#menu.on{display:block}
#menu .it{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:36px;padding:6px 10px;border:0;border-radius:6px;background:transparent;text-align:left}
#menu .it:hover:not(:disabled){background:var(--hover)}
#menu .n{color:var(--t3);font-size:12px}
#menu .n.warn{color:var(--amber)}
#menu hr{border:0;border-top:1px solid var(--line2);margin:6px 0}
#menu select{height:28px;border:1px solid var(--line);border-radius:6px;background:var(--surface);padding:0 6px}
#menu input[type=checkbox]{accent-color:#ededed;width:16px;height:16px}

/* dialog */
#scrim{display:none;position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.7);align-items:center;justify-content:center;padding:24px}
#scrim.on{display:flex}
#dlg{width:min(600px,100%);max-height:calc(100vh - 48px);display:flex;flex-direction:column;border:1px solid var(--line);border-radius:12px;background:var(--raised)}
#dHead{padding:20px 22px 4px}
#dHead h2{margin:0;font-size:18px;font-weight:600}
#dHead p{margin:6px 0 0;color:var(--t2);font-size:13px}
#dBody{padding:14px 22px;overflow-y:auto;min-height:0}
#dFoot{display:flex;align-items:center;gap:8px;padding:14px 22px 20px}
#dFoot .sp{flex:1}
.msgLine{padding:2px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.msgPath{display:flex;align-items:flex-start;gap:6px}
.msgPath .p{flex:1;min-width:0;font:12px/1.5 "Cascadia Mono",Consolas,monospace;color:var(--t2);padding-top:5px;overflow-wrap:anywhere}
.group{margin:0 0 4px;padding:14px 0 6px;color:var(--t2);font-size:12px;letter-spacing:.02em}
.row{display:flex;align-items:center;gap:10px;padding:10px 0;border-top:1px solid var(--line2)}
.row .v{flex:1;min-width:0;overflow-wrap:anywhere}
.row .tag{flex:none;color:var(--t3);font-size:12px;width:64px}
.row .sub{color:var(--t3);font-size:12px;margin-top:2px;overflow-wrap:anywhere}
.row.col{flex-direction:column;align-items:stretch;gap:8px}
.choices{display:flex;gap:6px;flex-wrap:wrap}
.choices button{height:30px;padding:0 12px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--t2);font-size:13px}
.choices button:hover{color:var(--t1);border-color:rgba(255,255,255,.28)}
.choices button[aria-pressed="true"]{background:var(--t1);border-color:var(--t1);color:var(--bg);font-weight:600}
.pair{padding:12px 0;border-top:1px solid var(--line2)}
.pair .side{display:flex;align-items:center;gap:8px;padding:3px 0}
.pair .side b{flex:none;width:16px;color:var(--t3);font-weight:500}
.pair .side span{flex:1;min-width:0;overflow-wrap:anywhere}
.pair .why{color:var(--t3);font-size:12px;margin:6px 0 8px}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--line);margin-bottom:14px}
.stat{padding:14px 16px;background:var(--raised)}
.stat b{display:block;font-size:24px;font-weight:600;font-variant-numeric:tabular-nums}
.stat span{color:var(--t2);font-size:13px}
.destLine{display:flex;align-items:flex-start;gap:6px}
.destLine .p{flex:1;min-width:0;font:12px/1.5 "Cascadia Mono",Consolas,monospace;color:var(--t2);padding-top:5px;overflow-wrap:anywhere}
.add{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.add .path{flex:1;min-width:160px}
.empty{padding:28px 0;text-align:center;color:var(--t3)}
.editInput{flex:1;min-width:0}
@media (max-width:760px){.folder{grid-template-columns:minmax(0,1fr) auto auto auto}.folder .seg{grid-column:1/-1}}
</style>
</head>
<body>
<div id="scroll"><main id="col">
  <header>
    <h1>Clean up your music</h1>
    <button class="iconBtn" id="gear" aria-label="Settings" aria-haspopup="menu" aria-expanded="false"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="2.2"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3"/></svg></button>
  </header>
  <p class="lbl">Folders</p>
  <div id="folders"></div>
  <button class="btn quiet" id="addFolder">+ Add folder</button>
  <label class="switch"><span><span class="name">Include remixes</span><br><span class="hint">Keep remix versions in the result</span></span><input type="checkbox" id="remixes"></label>
  <label class="switch"><span><span class="name">Include live recordings</span><br><span class="hint">Keep live versions in the result</span></span><input type="checkbox" id="live"></label>
  <section id="work" aria-live="polite">
    <div id="statusRow"><span id="status">Ready</span><span id="pct"></span></div>
    <div id="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="fill"></div></div>
    <div id="detail"></div>
    <button id="logToggle" aria-expanded="false">Show log</button>
    <div id="log" tabindex="0"></div>
  </section>
</main></div>
<footer id="foot"><div id="footIn">
  <button class="btn main" id="analyze">Analyze</button>
  <button class="btn" id="map">Open map</button>
  <span class="sp"></span>
  <button class="btn quiet" id="undo">Undo last run</button>
</div></footer>

<div id="menu" role="menu">
  <button class="it" id="mAlways" role="menuitem"><span>Always keep</span><span class="n" id="mAlwaysN"></span></button>
  <button class="it" id="mUnusual" role="menuitem"><span>Unusual titles</span><span class="n" id="mUnusualN"></span></button>
  <hr>
  <label class="it"><span>Write logs</span><input type="checkbox" id="mLogs"></label>
  <button class="it" id="mLogsOpen" role="menuitem"><span>Open logs folder</span></button>
  <label class="it"><span>Parallel reads</span><select id="mWorkers" aria-label="Parallel reads"></select></label>
</div>
<div id="scrim"><div id="dlg" role="dialog" aria-modal="true" aria-labelledby="dTitle">
  <div id="dHead"><h2 id="dTitle"></h2><p id="dSub"></p></div>
  <div id="dBody"></div>
  <div id="dFoot"></div>
</div></div>

<script>
let bridge=null,state=null,dlgKind="",dlgReturn=null,laterAction=null,picks=[],foldersShown="";
const $=id=>document.getElementById(id);
const esc=v=>String(v==null?"":v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
const ICON={
  folder:'<svg viewBox="0 0 16 16"><path d="M1.5 4.5a1 1 0 0 1 1-1h3.2l1.3 1.5h6.5a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z"/></svg>',
  x:'<svg viewBox="0 0 16 16"><path d="m4 4 8 8M12 4l-8 8"/></svg>'
};
const busy=()=>!!(state&&(state.running||state.reviewPending||state.mapOpen));
const elapsed=ms=>{let s=Math.max(0,Math.floor(ms/1000));const h=Math.floor(s/3600);s%=3600;const m=Math.floor(s/60),c=s%60;
  return (h?h+":"+String(m).padStart(2,"0"):String(m))+":"+String(c).padStart(2,"0");};

/* ---------- folders ---------- */
const rowsNow=()=>Array.from(document.querySelectorAll("#folders .folder")).map(r=>({path:r.querySelector(".path").value,star:r.querySelector('[data-role="library"]').getAttribute("aria-pressed")==="true"}));
const pushFolders=rows=>bridge.setFolders(rows,render);
function renderFolders(){
  const host=$("folders"),b=busy();
  const sig=JSON.stringify([state.folders||[],b]);
  if(sig===foldersShown)return;
  if(!b&&host.contains(document.activeElement)&&document.activeElement.classList.contains("path"))return;
  foldersShown=sig;
  host.innerHTML=(state.folders||[]).map((f,i)=>{
    const lib=!!f.star;
    return `<div class="folder" data-i="${i}">`
      +`<div class="seg" role="group" aria-label="Folder ${i+1} type"><button data-role="library" aria-pressed="${lib}"${b?" disabled":""}>Library</button><button data-role="incoming" aria-pressed="${!lib}"${b?" disabled":""}>Incoming</button></div>`
      +`<input class="path" value="${esc(f.path||"")}" aria-label="Folder ${i+1} path" placeholder="${lib?"Music you already organised":"Music you want to add or clean"}"${b?" disabled":""}>`
      +`<button class="iconBtn" data-act="show" aria-label="Show in Explorer" title="Show in Explorer"${b||!String(f.path||"").trim()?" disabled":""}>${ICON.folder}</button>`
      +`<button class="btn small" data-act="browse"${b?" disabled":""}>Browse</button>`
      +`<button class="iconBtn" data-act="remove" aria-label="${i<2?"Clear folder":"Remove folder"}" title="${i<2?"Clear":"Remove"}"${b?" disabled":""}>${ICON.x}</button></div>`;
  }).join("");
}
$("folders").addEventListener("click",ev=>{
  const row=ev.target.closest(".folder");if(!row)return;
  const i=Number(row.dataset.i),btn=ev.target.closest("button");if(!btn)return;
  if(btn.dataset.role){const rows=rowsNow();rows[i].star=btn.dataset.role==="library";pushFolders(rows);}
  else if(btn.dataset.act==="show")bridge.openPath(row.querySelector(".path").value);
  else if(btn.dataset.act==="browse")bridge.browseFolder(i,render);
  else if(btn.dataset.act==="remove"){const rows=rowsNow();if(i<2)rows[i].path="";else rows.splice(i,1);pushFolders(rows);}
});
$("folders").addEventListener("change",ev=>{if(ev.target.classList.contains("path"))pushFolders(rowsNow());});
$("addFolder").onclick=()=>{const r=rowsNow();r.push({path:"",star:false});pushFolders(r);};

/* ---------- state ---------- */
function detailText(){
  let t=String(state.progressCount||"");
  if(state.running&&state.runStartedEpochMs)t+=(t?" · ":"")+elapsed(Date.now()-Number(state.runStartedEpochMs))+" elapsed";
  return t;
}
function render(raw){
  state=typeof raw==="string"?JSON.parse(raw):raw;
  renderFolders();
  $("remixes").checked=!!state.saveRemixes;$("live").checked=!!state.saveLive;$("mLogs").checked=!!state.logging;
  $("mWorkers").value=String(state.ioWorkers||"auto");
  $("mAlwaysN").textContent=state.personalCount?String(state.personalCount):"";
  const pend=Number(state.pendingPatternCount||0);
  $("mUnusualN").textContent=pend?pend+" waiting":"";$("mUnusualN").classList.toggle("warn",pend>0);
  $("gear").classList.toggle("dotOn",pend>0);
  const pct=Math.max(0,Math.min(100,Number(state.progressPct||0)));
  const act=(state.activity||[]).join("\n");
  const show=!!state.running||pct>0||!!act.trim()||String(state.status||"Ready")!=="Ready";
  $("work").classList.toggle("on",show);
  $("status").textContent=state.status||"Ready";
  $("pct").textContent=state.running||pct>0?Math.round(pct)+"%":"";
  $("fill").style.width=pct+"%";$("bar").setAttribute("aria-valuenow",String(Math.round(pct)));
  $("detail").textContent=detailText();
  const log=$("log"),atEnd=log.scrollHeight-log.scrollTop-log.clientHeight<30;
  log.textContent=act;if(atEnd)log.scrollTop=log.scrollHeight;
  const b=busy();
  $("analyze").disabled=b;$("undo").disabled=b;
  $("map").style.display=state.mapAvailable?"":"none";$("map").disabled=b;
  ["addFolder","remixes","live","mAlways","mUnusual","mLogs","mLogsOpen","mWorkers"].forEach(id=>$(id).disabled=b);
}
setInterval(()=>{if(state&&state.running)$("detail").textContent=detailText();},1000);
$("logToggle").onclick=function(){const on=$("log").classList.toggle("on");this.textContent=on?"Hide log":"Show log";this.setAttribute("aria-expanded",String(on));};
for(let n=1;n<=32;n++){const o=document.createElement("option");o.value=String(n);o.textContent=String(n);$("mWorkers").appendChild(o);}
{const o=document.createElement("option");o.value="auto";o.textContent="Auto";$("mWorkers").insertBefore(o,$("mWorkers").firstChild);}
$("remixes").onchange=function(){bridge.setOption("saveRemixes",this.checked,render);};
$("live").onchange=function(){bridge.setOption("saveLive",this.checked,render);};
$("mLogs").onchange=function(){bridge.setOption("logging",this.checked,render);};
$("mWorkers").onchange=function(){bridge.setIoWorkers(this.value,render);};
$("mLogsOpen").onclick=()=>{closeMenu();bridge.openLogsFolder();};
$("mAlways").onclick=()=>{closeMenu();bridge.getPersonalPicks(alwaysKeepDialog);};
$("mUnusual").onclick=()=>{closeMenu();bridge.getPatternManager(unusualManager);};
$("analyze").onclick=()=>bridge.startAnalyze(rowsNow(),$("remixes").checked,$("live").checked,$("mLogs").checked,render);
$("map").onclick=()=>bridge.openReleaseMap();
$("undo").onclick=()=>undoConfirm();
function undoConfirm(){
  confirmDialog("Undo the last run?","Files moved by the last run go back to where they were.","Undo",()=>bridge.undoLastRun());
}

/* ---------- menu ---------- */
function closeMenu(){$("menu").classList.remove("on");$("gear").setAttribute("aria-expanded","false");}
$("gear").onclick=ev=>{ev.stopPropagation();const on=$("menu").classList.toggle("on");$("gear").setAttribute("aria-expanded",String(on));};
document.addEventListener("click",ev=>{if(!ev.target.closest("#menu")&&!ev.target.closest("#gear"))closeMenu();});

/* ---------- dialog shell ---------- */
function openDlg(kind,title,sub,body,foot){
  dlgKind=kind;
  if(!$("scrim").classList.contains("on"))dlgReturn=document.activeElement;
  $("dTitle").textContent=title||"";$("dSub").textContent=sub||"";$("dSub").style.display=sub?"":"none";
  $("dBody").innerHTML=body||"";$("dFoot").innerHTML=foot||"";
  $("scrim").classList.add("on");
  requestAnimationFrame(()=>{const f=$("dlg").querySelector("#dFoot .main,#dBody input,#dFoot button");if(f)f.focus();});
}
function closeDlg(){
  dlgKind="";laterAction=null;
  $("scrim").classList.remove("on");
  if(dlgReturn&&dlgReturn.focus)dlgReturn.focus();
  dlgReturn=null;
}
document.addEventListener("keydown",ev=>{
  if(ev.key==="Escape"){
    if($("scrim").classList.contains("on")){
      ev.preventDefault();
      const later=dlgKind==="unusualReview"?laterAction:null,cancel=dlgKind==="samesong";
      closeDlg();
      if(later)later();else if(cancel)bridge.cancelReview();
    }else if($("menu").classList.contains("on")){closeMenu();$("gear").focus();}
  }
});
const okFoot='<span class="sp"></span><button class="btn main" id="ok">OK</button>';
function pathLines(message){
  return String(message==null?"":message).split("\n").map(line=>{
    let pos=line.search(/[A-Za-z]:[\\/]/);
    if(pos<0){const u=line.indexOf("\\\\");if(u>=0)pos=u;}
    const path=pos<0?"":line.slice(pos).trim();
    if(!path)return `<div class="msgLine">${line?esc(line):"&nbsp;"}</div>`;
    const pre=line.slice(0,pos).trim();
    return (pre?`<div class="msgLine">${esc(pre)}</div>`:"")+`<div class="msgPath"><button class="iconBtn" data-open="${esc(path)}" aria-label="Show in Explorer" title="Show in Explorer">${ICON.folder}</button><span class="p">${esc(path)}</span></div>`;
  }).join("");
}
function bindOpen(){document.querySelectorAll("#dBody [data-open]").forEach(b=>{b.onclick=()=>bridge.openPath(b.dataset.open||"");});}
function messageDialog(title,message){
  openDlg("message",title,"",pathLines(message),okFoot);bindOpen();$("ok").onclick=closeDlg;
}
function confirmDialog(title,message,yes,onYes){
  openDlg("confirm",title,"",`<div class="msgLine">${esc(message)}</div>`,
    `<span class="sp"></span><button class="btn quiet" id="no">Cancel</button><button class="btn main" id="yes">${esc(yes||"Continue")}</button>`);
  $("no").onclick=closeDlg;$("yes").onclick=()=>{closeDlg();onYes();};
}

/* ---------- unusual titles: manager ---------- */
function unusualManager(raw){
  const data=typeof raw==="string"?JSON.parse(raw):raw;
  const cat=(data.categories||[]).map(x=>({...x})),pending=data.pending||[];
  let body="";
  [["remix","Always treated as remixes"],["live","Always treated as live"],["skip","Always ignored"]].forEach(([kind,label])=>{
    const rows=cat.filter(x=>x.kind===kind);
    if(!rows.length)return;
    body+=`<div class="group">${label} · ${rows.length}</div>`+rows.map(x=>`<div class="row"><span class="v">${esc(x.label||x.key)}</span>`
      +`<button class="btn small" data-act="keep" data-key="${esc(x.key)}">Always keep</button><button class="btn small quiet" data-act="forget" data-key="${esc(x.key)}">Forget</button></div>`).join("");
  });
  if(pending.length)body+=`<div class="group">Waiting for your decision · ${pending.length}</div><div class="msgLine" style="color:var(--t2)">${pending.map(p=>esc(p.label||p.key)).join(" · ")}</div>`;
  if(!body)body='<div class="empty">Nothing saved yet.</div>';
  openDlg("unusualManager","Unusual titles","Titles like “(Live at …)” or “(Remix)” that you labelled before.",body,
    (pending.length?'<button class="btn main" id="review">Decide now</button>':"")+'<span class="sp"></span><button class="btn" id="close">Close</button>');
  const update=(action,key)=>{
    const at=cat.findIndex(x=>x.key===key);if(at<0)return;
    const entry=cat.splice(at,1)[0];
    bridge.savePatternManager(JSON.stringify({categories:cat,promote:action==="keep"?[entry]:[]}),()=>bridge.getPatternManager(unusualManager));
  };
  document.querySelectorAll("#dBody [data-act]").forEach(b=>{b.onclick=()=>update(b.dataset.act,b.dataset.key);});
  if($("review"))$("review").onclick=()=>{closeDlg();bridge.openPendingPatterns();};
  $("close").onclick=closeDlg;
}

/* ---------- unusual titles: review ---------- */
function unusualReview(data){
  const patterns=data.patterns||[],chosen=Object.create(null);
  let submitting=false;
  const choices=[["remix","Remix"],["live","Live"],["keep","Always keep"],["skip","Ignore"]];
  const err=data.saveError?"Could not save: "+String(data.saveError):"";
  const body=patterns.map((p,i)=>{
    const variants=(p.variants||[]).filter(v=>String(v).trim().toLowerCase()!==String(p.label).trim().toLowerCase()).slice(0,4);
    const details=[...new Set((p.examples||[]).slice(0,3).concat(variants).map(String).filter(Boolean))];
    return `<div class="row col" data-i="${i}"><div><span class="v">${esc(p.label)}</span> <span style="color:var(--t3)">· ${esc(p.count)} track${Number(p.count)===1?"":"s"}</span>`
      +(details.length?`<div class="sub">${esc(details.join(" · "))}</div>`:"")+`</div>`
      +`<div class="choices" role="group" aria-label="${esc(p.label)}">${choices.map(c=>`<button data-i="${i}" data-c="${c[0]}" aria-pressed="false">${c[1]}</button>`).join("")}</div></div>`;
  }).join("")||'<div class="empty">Nothing unusual found.</div>';
  openDlg("unusualReview","Unusual titles",(err?err+" · ":"")+"Choose what each one is. The last choice finishes the review.",body,
    (data.deferred?"":'<button class="btn quiet" id="cancelScan">Cancel scan</button>')+'<span class="sp"></span><button class="btn main" id="later">Decide later</button>');
  laterAction=()=>bridge.deferPatternReview(JSON.stringify(chosen));
  $("later").onclick=()=>{const l=laterAction;closeDlg();if(l)l();};
  if($("cancelScan"))$("cancelScan").onclick=()=>{closeDlg();bridge.cancelReview();};
  document.querySelectorAll("#dBody .choices button").forEach(btn=>{
    btn.onclick=()=>{
      if(submitting)return;
      const p=patterns[Number(btn.dataset.i)],c=btn.dataset.c;
      if(!p||!["remix","live","keep","skip"].includes(c))return;
      chosen[p.key]=c;
      btn.parentElement.querySelectorAll("button").forEach(o=>o.setAttribute("aria-pressed",String(o===btn)));
      const n=Object.keys(chosen).length;
      if(n<patterns.length){$("dSub").textContent=(err?err+" · ":"")+n+" of "+patterns.length+" decided";return;}
      submitting=true;
      document.querySelectorAll("#dBody .choices button").forEach(o=>{o.disabled=true;});
      closeDlg();bridge.submitPatternReview(JSON.stringify(chosen));
    };
  });
}

/* ---------- same song? ---------- */
function sameSong(data){
  const list=data.candidates||[];
  const body=list.map((p,i)=>{
    const why=p.reason==="different_titles_same_audio"?"The audio matches closely but the titles differ.":"Same title and almost the same audio.";
    const m=p.score!==undefined?` · match ${esc(p.score)}, overlap ${esc(Math.round((p.overlap||0)*100))}%`:"";
    return `<div class="pair"><div class="side"><b>A</b><span>${esc(p.title_a||"")}${p.artist_a?" — "+esc(p.artist_a):""}</span><button class="btn small quiet" data-open-a="${i}">Play</button></div>`
      +`<div class="side"><b>B</b><span>${esc(p.title_b||"")}${p.artist_b?" — "+esc(p.artist_b):""}</span><button class="btn small quiet" data-open-b="${i}">Play</button></div>`
      +`<div class="why">${esc(why)}${m}</div>`
      +`<div class="choices" role="group" aria-label="Pair ${i+1}"><button data-i="${i}" data-s="0" aria-pressed="true">Different songs</button><button data-i="${i}" data-s="1" aria-pressed="false">Same song</button></div></div>`;
  }).join("")||'<div class="empty">Nothing to compare.</div>';
  openDlg("samesong","Same song?","Only a few pairs need your ear. Anything you leave as different stays in your collection twice.",body,
    '<button class="btn quiet" id="allDiff">All different</button><span class="sp"></span><button class="btn quiet" id="cancel">Cancel scan</button><button class="btn main" id="go">Continue</button>');
  document.querySelectorAll("#dBody [data-open-a]").forEach(b=>{b.onclick=()=>bridge.openPath(list[Number(b.dataset.openA)].path_a||"");});
  document.querySelectorAll("#dBody [data-open-b]").forEach(b=>{b.onclick=()=>bridge.openPath(list[Number(b.dataset.openB)].path_b||"");});
  document.querySelectorAll("#dBody .choices button").forEach(b=>{
    b.onclick=()=>b.parentElement.querySelectorAll("button").forEach(o=>o.setAttribute("aria-pressed",String(o===b)));
  });
  $("allDiff").onclick=()=>document.querySelectorAll('#dBody .choices button[data-s="0"]').forEach(b=>b.click());
  $("cancel").onclick=()=>{closeDlg();bridge.cancelReview();};
  $("go").onclick=()=>{
    const accepted=[];
    document.querySelectorAll('#dBody .choices button[data-s="1"][aria-pressed="true"]').forEach(b=>accepted.push(list[Number(b.dataset.i)].key));
    closeDlg();bridge.submitManualReview(JSON.stringify(accepted));
  };
}

/* ---------- always keep ---------- */
const MODE_LABEL={contains:"Phrase",exact:"Exact title",pattern:"Pattern"};
function renderPicks(){
  const host=$("pickList");if(!host)return;
  const q=String($("pickSearch").value||"").trim().toLocaleLowerCase();
  const rows=picks.map((p,i)=>({p,i})).filter(x=>String(x.p.value).toLocaleLowerCase().includes(q));
  host.innerHTML=rows.length?rows.map(x=>`<div class="row"><span class="tag">${MODE_LABEL[x.p.mode]}</span><span class="v" title="${esc(x.p.value)}">${esc(x.p.value)}</span>`
    +(x.p.mode==="pattern"?"":`<button class="btn small quiet" data-edit="${x.i}">Edit</button>`)
    +`<button class="btn small quiet" data-del="${x.i}" aria-label="Remove ${esc(x.p.value)}">Remove</button></div>`).join("")
    :`<div class="empty">${q?"No match.":"Nothing here yet."}</div>`;
  host.querySelectorAll("[data-del]").forEach(b=>{b.onclick=()=>{picks.splice(Number(b.dataset.del),1);renderPicks();};});
  host.querySelectorAll("[data-edit]").forEach(b=>{
    b.onclick=()=>{
      const i=Number(b.dataset.edit),span=b.parentElement.querySelector(".v");
      const inp=document.createElement("input");inp.className="path editInput";inp.value=picks[i].value;inp.setAttribute("aria-label","Edit entry");
      span.replaceWith(inp);b.textContent="Done";b.disabled=true;
      let done=false;
      const finish=commit=>{
        if(done)return;done=true;
        const next=inp.value.trim();
        if(commit&&next&&!picks.some((p,j)=>j!==i&&p.mode===picks[i].mode&&p.value.toLocaleLowerCase()===next.toLocaleLowerCase()))picks[i].value=next;
        renderPicks();
      };
      inp.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();finish(true);}if(e.key==="Escape"){e.preventDefault();e.stopPropagation();finish(false);}});
      inp.addEventListener("blur",()=>finish(true),{once:true});
      inp.focus();inp.select();
    };
  });
}
function alwaysKeepDialog(raw){
  const data=typeof raw==="string"?JSON.parse(raw):raw;
  picks=(data.rules||[]).map(x=>{
    const mode=x.mode==="pattern"?"pattern":(x.mode==="exact"?"exact":"contains");
    const it={mode,value:String(x.value||"")};if(mode==="pattern")it.key=String(x.key||"");return it;
  });
  openDlg("always","Always keep","Tracks that match these are never filtered out.",
    '<div class="add"><input class="path" id="pickIn" placeholder="A word, phrase or full track title" aria-label="New entry"><button class="btn" id="addPhrase">Add phrase</button><button class="btn" id="addExact">Add exact title</button></div>'
    +'<input class="path" id="pickSearch" type="search" style="width:100%" placeholder="Search your list" aria-label="Search your list"><div id="pickList"></div>',
    '<button class="btn quiet" id="copyList">Copy list</button><button class="btn danger" id="clearList">Clear all</button><span class="sp"></span><button class="btn quiet" id="cancel">Cancel</button><button class="btn main" id="save">Save</button>');
  renderPicks();
  $("pickSearch").oninput=renderPicks;
  const norm=s=>s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,"");
  const add=mode=>{
    const v=$("pickIn").value.trim();if(!v)return;
    if(!picks.some(p=>p.mode===mode&&norm(p.value)===norm(v))){picks.push({mode,value:v});renderPicks();}
    $("pickIn").value="";$("pickIn").focus();
  };
  $("addPhrase").onclick=()=>add("contains");$("addExact").onclick=()=>add("exact");
  $("pickIn").onkeydown=e=>{if(e.key==="Enter")add("contains");};
  $("copyList").onclick=()=>bridge.copyText(picks.map(p=>MODE_LABEL[p.mode]+": "+p.value).join("\n"));
  $("clearList").onclick=()=>{picks=[];renderPicks();};
  $("cancel").onclick=closeDlg;
  $("save").onclick=()=>{closeDlg();bridge.savePersonalPicks(JSON.stringify({rules:picks}),render);};
  $("pickIn").focus();
}

/* ---------- results ---------- */
const stat=(n,label)=>`<div class="stat"><b>${esc(n||0)}</b><span>${esc(label)}</span></div>`;
const destLine=(label,path,id)=>`<div class="destLine"><button class="iconBtn" id="${id}" aria-label="Show in Explorer" title="Show in Explorer">${ICON.folder}</button><span class="p">${esc(label)}${esc(path||"")}</span></div>`;
function finished(data){
  const r=data.result||{};
  openDlg("done","Finished","Your files have been tidied.",
    `<div class="stats">${stat(r.remaining_recycle,"Incoming releases kept")}${stat(r.moved,"Extra releases moved aside")}${stat(r.intra_duplicate_files,"Duplicate files removed")}${stat(r.remix_moved,"Moved to !Remixes")}</div>`
    +`<div class="msgLine" style="color:var(--t2)">Added ${esc(r.add||0)} · Replaced ${esc(r.replace||0)} · Skipped ${esc(r.skipped_recycle||0)} · Library releases removed ${esc(r.removed_current||0)}</div>`
    +`<div style="margin-top:12px">${destLine("Duplicates: ",data.duplicates,"openDup")}</div>`,
    '<button class="btn" id="openInc">Open incoming</button><button class="btn" id="mapBtn">Open map</button><button class="btn quiet" id="undoBtn">Undo</button><span class="sp"></span><button class="btn main" id="close">Close</button>');
  $("openDup").onclick=()=>bridge.openPath(data.duplicates||"");
  $("openInc").onclick=()=>bridge.openPath(data.recycle||"");
  $("undoBtn").onclick=undoConfirm;
  $("mapBtn").onclick=()=>{closeDlg();bridge.openReleaseMap();};
  $("close").onclick=closeDlg;
}
function copied(data){
  const r=data.result||{},moved=!!r.source_folders_modified;
  openDlg("done",moved?"Moved":"Copied",moved?"The final collection is in the new folder. Your originals were moved into it.":"The final collection is in the new folder. Your originals were not touched.",
    `<div class="stats">${stat(r.logical_releases,"Releases in the final collection")}${stat(r.physical_folders,"Folders")}${stat(r.existing_releases,"From your library")}${stat(r.new_releases,"From incoming")}</div>`
    +destLine("",data.destination,"openDest"),
    (moved?'<button class="btn quiet" id="undoMove">Undo move</button>':'<button class="btn" id="mapBtn">Open map</button>')+'<span class="sp"></span><button class="btn main" id="close">Close</button>');
  $("openDest").onclick=()=>bridge.openPath(data.destination||"");
  if(moved)$("undoMove").onclick=()=>confirmDialog("Undo the move?","Everything goes back to its original folder.","Undo move",()=>bridge.undoLastRun());
  else $("mapBtn").onclick=()=>{closeDlg();bridge.openReleaseMap();};
  $("close").onclick=closeDlg;
}
function handleEvent(raw){
  const e=typeof raw==="string"?JSON.parse(raw):raw;
  if(e.type==="error"||e.type==="info")messageDialog(e.title||"Music Collection Cleaner",e.message||"");
  else if(e.type==="patternReview")unusualReview(e);
  else if(e.type==="manualReview")sameSong(e);
  else if(e.type==="copyDone")copied(e);
  else if(e.type==="done")finished(e);
}

/* ---------- bridge ---------- */
let stateCb=null,eventCb=null,failShown=false;
window.__deaStateChanged=raw=>{if(stateCb)stateCb(raw);};
window.__deaEventRaised=raw=>{if(eventCb)eventCb(raw);};
function waitForMethod(name,ms){
  const limit=Number(ms||30000);
  return new Promise((resolve,reject)=>{
    const t0=Date.now();
    (function probe(){
      const api=window.pywebview&&window.pywebview.api,fn=api&&api[name];
      if(typeof fn==="function"){resolve({api,fn});return;}
      if(Date.now()-t0>=limit){reject(new Error("Desktop bridge method did not become ready: "+String(name)));return;}
      setTimeout(probe,25);
    })();
  });
}
function bridgeFailed(error){
  console.error(error);
  if(failShown)return;failShown=true;
  const msg=String(error&&error.message||error||"Unknown desktop bridge error");
  try{$("status").textContent="Desktop bridge failed";$("work").classList.add("on");messageDialog("Music Collection Cleaner","The desktop bridge failed:\n"+msg);}catch(_e){}
}
function bridgeCall(name,args,cb){
  return waitForMethod(name,30000).then(e=>e.fn.apply(e.api,args)).then(r=>{
    if(cb)cb(typeof r==="string"?r:JSON.stringify(r));
    return r;
  }).catch(e=>{bridgeFailed(e);throw e;});
}
bridge=new Proxy({stateChanged:{connect:fn=>{stateCb=fn;}},eventRaised:{connect:fn=>{eventCb=fn;}}},{
  get:(obj,name)=>{
    if(name in obj)return obj[name];
    return function(){
      const args=Array.from(arguments);
      const cb=(args.length&&typeof args[args.length-1]==="function")?args.pop():null;
      return bridgeCall(name,args,cb);
    };
  }
});
bridge.stateChanged.connect(render);
bridge.eventRaised.connect(handleEvent);
bridge.getState(render).catch(()=>{});
window.addEventListener("pywebviewready",()=>{bridge.getState(render).catch(()=>{});});
</script>
</body>
</html>'''
    return html


def _webview_main_app() -> int:
    """Run the regular DEA feature set in a lightweight WebView2/pywebview shell."""
    webview = ensure_light_ui_dependencies()
    _ensure_webview2_runtime()

    class MainBridge:

        def __init__(self):
            self.window = None
            self.webview = None
            saved = _load_app_settings()
            self.folders = _load_source_folders(saved)
            if "save_remixes" in saved:
                self.save_remixes = bool(saved.get("save_remixes"))
            else:
                self.save_remixes = not bool(saved.get("exclude_remixes", True))
            if "save_live" in saved:
                self.save_live = bool(saved.get("save_live"))
            else:
                self.save_live = not bool(saved.get("exclude_live", True))
            self.logging_enabled = bool(saved.get("logging_enabled", False))
            self.io_workers = str(saved.get("io_workers", "auto") or "auto")
            if self.io_workers != "auto" and (not self.io_workers.isdecimal() or not 1 <= int(self.io_workers) <= 32):
                self.io_workers = "auto"
            self.pattern_preferences: Dict[str, bool] = {}
            self.personal_keep_rules = _load_personal_keep_rules(saved)
            self.pattern_categories = _load_pattern_categories()
            self.pending_pattern_reviews = _load_pending_pattern_reviews()

            self.status = "Ready"
            self.progress_pct = 0.0
            self.progress_count = ""
            self.activity: List[str] = []
            self.running = False
            self.review_pending = False
            self.map_open = False
            self.run_started_epoch_ms = 0
            self._last_progress_stage = ""
            self._last_emit = 0.0
            self._lock = threading.RLock()
            self._decision_snapshot: List[Dict[str, object]] = _load_decision_snapshot()
            self._live_release_map_session: Optional[Dict[str, object]] = None
            self._pending_analysis: Optional[Dict[str, object]] = None
            self._pattern_review_mode = ""
            self._review_visible_rows: List[Dict[str, object]] = []

        def _invalidate_live_analysis_after_preferences(self) -> None:
            if self._live_release_map_session is not None:
                self._live_release_map_session = None
                self.status = "Preferences changed - Analyze again"
                self._append_activity("Preferences changed; previous Release Map is read-only until next analysis.")

        def _save_settings(self) -> None:
            _save_app_settings(
                "", "",
                self.save_remixes,
                self.save_live,
                self.logging_enabled,
                self.pattern_preferences,
                self.personal_keep_rules,
                self.io_workers,
                source_folders=self.folders,
            )

        def _state_payload(self) -> Dict[str, object]:
            with self._lock:
                return {
                    "folders": [dict(row) for row in self.folders],
                    "saveRemixes": self.save_remixes,
                    "saveLive": self.save_live,
                    "logging": self.logging_enabled,
                    "ioWorkers": self.io_workers,
                    "personalCount": len(self.personal_keep_rules),
                    "pendingPatternCount": len(_unresolved_track_patterns(
                        self.pending_pattern_reviews, self.personal_keep_rules, self.pattern_categories)),
                    "status": self.status,
                    "progressPct": round(self.progress_pct, 3),
                    "progressCount": self.progress_count,
                    "activity": list(self.activity[-600:]),
                    "running": self.running,
                    "reviewPending": self.review_pending,
                    "mapOpen": self.map_open,
                    "runStartedEpochMs": self.run_started_epoch_ms,
                    "mapAvailable": bool(self._decision_snapshot),
                }

        def _state_json(self) -> str:
            return _json_ui_dumps(self._state_payload())

        def _emit_state(self, force: bool = True) -> None:
            now = time.monotonic()
            if not force and now - self._last_emit < 0.05:
                return
            self._last_emit = now
            _light_emit(self.window, "__deaStateChanged", self._state_json())

        def _event(self, payload: Dict[str, object]) -> None:
            _light_emit(self.window, "__deaEventRaised", _json_ui_dumps(payload))

        def _append_activity(self, text: str) -> None:
            if not text:
                return
            with self._lock:
                stamp = datetime.now().strftime("%H:%M:%S")
                self.activity.append(f"{stamp}  {text}")
                if len(self.activity) > 600:
                    self.activity = self.activity[-600:]

        def _clear_activity(self) -> None:
            with self._lock:
                self.activity.clear()

        def _set_running(self, running: bool) -> None:
            with self._lock:
                self.running = bool(running)
                if running:
                    self.run_started_epoch_ms = int(time.time() * 1000)
                else:
                    self.run_started_epoch_ms = 0
            self._emit_state()

        def _error(self, message: str, title: str = APP_NAME) -> None:
            with self._lock:
                self.running = False
                self.review_pending = False
                self.map_open = False
                self.status = "Failed"
                self.run_started_epoch_ms = 0
            self._append_activity(f"Failed: {message}")
            self._emit_state()
            self._event({"type": "error", "title": title, "message": message})

        def _info(self, message: str, title: str = APP_NAME) -> None:
            self._event({"type": "info", "title": title, "message": message})

        def _progress(self, text: str, current: int, total: int) -> None:
            pct = 0.0 if total <= 0 else (current / total) * 100.0
            stage = text.rstrip(".")
            stage_key = stage.split(" | ", 1)[0]
            with self._lock:
                if stage_key != self._last_progress_stage:
                    self._last_progress_stage = stage_key
                    self._append_activity(stage_key)
                self.status = stage
                self.progress_pct = pct
                self.progress_count = f"{current:,} / {total:,} ({pct:.0f}%)" if total > 0 else ""
            self._emit_state(force=(current >= total or current == 0))

        def getState(self):
            return self._state_json()

        def setFolders(self, folders):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            self.folders = _normalize_source_folders(folders)
            self._save_settings()
            return self._state_json()

        def browseFolder(self, index: int):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            try:
                index = int(index)
            except (TypeError, ValueError):
                return self._state_json()
            if not 0 <= index < len(self.folders):
                return self._state_json()
            current = str(self.folders[index]["path"])
            start = current if current and Path(current).is_dir() else str(Path.home())
            chosen_items = (
                self.window.create_file_dialog(self.webview.FileDialog.FOLDER, directory=start)
                if self.window is not None and self.webview is not None
                else None
            )
            chosen = chosen_items[0] if chosen_items else ""
            if chosen:
                self.folders[index]["path"] = chosen
                self._save_settings()
            return self._state_json()

        def setOption(self, name: str, value: bool):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            if name == "saveRemixes":
                self.save_remixes = bool(value)
            elif name == "saveLive":
                self.save_live = bool(value)
            elif name == "logging":
                self.logging_enabled = bool(value)
            self._save_settings()
            return self._state_json()

        def setIoWorkers(self, value: str):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            value = str(value or "").strip()
            if value == "auto" or (value.isdecimal() and 1 <= int(value) <= 32):
                self.io_workers = value
                self._save_settings()
            return self._state_json()

        def _reload_classifications(self) -> None:
            self.pattern_categories = _load_pattern_categories()
            self.personal_keep_rules = _load_personal_keep_rules(_load_app_settings())
            self.pending_pattern_reviews = _load_pending_pattern_reviews()

        def getPersonalPicks(self):
            self._reload_classifications()
            return _json_ui_dumps({
                "rules": self.personal_keep_rules,
                "categories": [
                    {"key": key, **value}
                    for key, value in sorted(self.pattern_categories.items())
                ],
            })

        def savePersonalPicks(self, raw: str):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            try:
                incoming = json.loads(raw or "[]")
            except Exception:
                incoming = []
            requested_categories = None
            if isinstance(incoming, dict):
                requested_categories = incoming.get("categories", [])
                incoming = incoming.get("rules", [])
            cleaned: List[Dict[str, str]] = []
            seen: Set[Tuple[str, str]] = set()
            if isinstance(incoming, list):
                for item in incoming:
                    if not isinstance(item, dict):
                        continue
                    raw_mode = str(item.get("mode", "")).strip().lower()
                    mode = "pattern" if raw_mode == "pattern" else ("exact" if raw_mode == "exact" else "contains")
                    value = str(item.get("value", "")).strip()
                    if mode == "pattern":
                        pattern_key = normalize_space(
                            str(item.get("key", "") or canonical_track_pattern(value))
                        ).casefold()
                        dedupe = ("pattern", pattern_key)
                        if pattern_key and dedupe not in seen:
                            seen.add(dedupe)
                            cleaned.append({
                                "mode": "pattern",
                                "value": value or pattern_key,
                                "key": pattern_key,
                            })
                        continue
                    normalized = _personal_pick_normalize(value)
                    dedupe = (mode, normalized)
                    if value and normalized and dedupe not in seen:
                        seen.add(dedupe)
                        cleaned.append({"mode": mode, "value": value})
            if requested_categories is not None:
                try:
                    new_categories = _normalize_pattern_categories(requested_categories)
                    _save_pattern_categories(new_categories)
                except Exception as exc:
                    self._event({"type": "error", "title": APP_NAME,
                                 "message": f"Could not save pattern categories: {exc}"})
                    return self._state_json()
                self.pattern_categories = new_categories
            self.personal_keep_rules = cleaned
            self._save_settings()
            self._invalidate_live_analysis_after_preferences()
            return self._state_json()

        def copyText(self, value: str):
            _copy_text_to_clipboard(value or "")

        def openLogsFolder(self):
            try:
                _migrate_legacy_app_data()
                path = _logs_dir()
                path.mkdir(parents=True, exist_ok=True)
                _open_path_location(str(path))
            except Exception as exc:
                self._event({"type": "error", "title": APP_NAME, "message": f"Could not open logs folder:\n\n{exc}"})

        def openPath(self, value: str):
            try:
                _open_path_location(value)
            except Exception as exc:
                self._event({"type": "error", "title": APP_NAME, "message": str(exc)})

        def closeApp(self):
            self._save_settings()
            _end_app_children()
            if self.window is not None:
                self.window.destroy()

        def startAnalyze(
            self,
            folders,
            save_remixes: bool,
            save_live: bool,
            logging_enabled: bool,
        ):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            # Map actions can change categories and Personal Picks externally.
            self.pattern_categories = _load_pattern_categories()
            self.personal_keep_rules = _load_personal_keep_rules(_load_app_settings())
            self.pending_pattern_reviews = _load_pending_pattern_reviews()

            self.folders = _normalize_source_folders(folders)
            self.save_remixes = bool(save_remixes)
            self.save_live = bool(save_live)
            self.logging_enabled = bool(logging_enabled)
            self._save_settings()

            filled = [(index + 1, row) for index, row in enumerate(self.folders) if str(row["path"]).strip()]
            for number, row in filled:
                if not Path(str(row["path"])).is_dir():
                    self._event({"type": "error", "title": APP_NAME, "message": f"Invalid Source folder {number}."})
                    return self._state_json()
            starred, unstarred = _split_source_folders(self.folders)
            if not unstarred:
                self._event({
                    "type": "error",
                    "title": APP_NAME,
                    "message": "Choose at least one source folder without a star (the releases to analyze).",
                })
                return self._state_json()
            try:
                for i, (first_no, first) in enumerate(filled):
                    for second_no, second in filled[i + 1:]:
                        a_path, b_path = Path(str(first["path"])), Path(str(second["path"]))
                        if (
                            a_path.resolve() == b_path.resolve()
                            or _is_ancestor(a_path, b_path)
                            or _is_ancestor(b_path, a_path)
                        ):
                            self._event({
                                "type": "error",
                                "title": APP_NAME,
                                "message": f"Source folder {first_no} and Source folder {second_no} must be separate and non-nested.",
                            })
                            return self._state_json()
            except Exception:
                pass
            existing = starred[0] if starred else None
            recycle = unstarred[0]
            extra_existing = starred[1:]
            extra_recycle = unstarred[1:]

            self._live_release_map_session = None
            self._pending_analysis = None
            self._pattern_review_mode = ""
            self._review_visible_rows = []
            self.review_pending = False
            self.progress_pct = 0.0
            self.progress_count = ""
            self.status = "Scanning track patterns"
            self._last_progress_stage = ""
            self._clear_activity()
            self._append_activity("Started")
            io_limit, io_media = _io_worker_plan(
                existing, recycle, self.io_workers, extra_roots=[*extra_existing, *extra_recycle],
            )
            self._append_activity(f"Audio I/O workers: {io_limit} ({io_media})")
            if self.logging_enabled:
                self._append_activity("Logging enabled")
            if self.personal_keep_rules:
                self._append_activity(f"Personal Picks: {len(self.personal_keep_rules)} rule(s)")
            self._set_running(True)

            threading.Thread(
                target=self._preflight_worker,
                args=(existing, recycle, self.save_remixes, self.save_live, self.logging_enabled, io_limit,
                      extra_existing, extra_recycle),
                daemon=True,
            ).start()
            return self._state_json()

        def _preflight_worker(
            self,
            existing: Optional[Path],
            recycle: Path,
            save_remixes: bool,
            save_live: bool,
            logging_enabled: bool,
            io_limit: int,
            extra_existing: Sequence[Path] = (),
            extra_recycle: Sequence[Path] = (),
        ) -> None:
            try:
                releases, tracks = prepare_analysis(
                    existing, recycle, self._progress, io_limit, extra_existing, extra_recycle,
                )
                patterns = collect_track_patterns(tracks)
                self._pending_analysis = {
                    "existing": existing,
                    "recycle": recycle,
                    "extra_roots": [*extra_existing, *extra_recycle],
                    "save_remixes": save_remixes,
                    "save_live": save_live,
                    "logging_enabled": logging_enabled,
                    "io_limit": io_limit,
                    "releases": releases,
                    "tracks": tracks,
                    "patterns": patterns,
                    "pattern_categories": dict(self.pattern_categories),
                }
                self.running = False
                self.run_started_epoch_ms = 0
                self.review_pending = bool(patterns)
                self._emit_state()
                self._show_pattern_review_or_continue()
            except Exception as exc:
                self._error(str(exc))

        def _show_pattern_review_or_continue(self, save_error: str = "") -> None:
            ctx = self._pending_analysis or {}
            all_patterns = list(ctx.get("patterns", []) or [])
            patterns = _unresolved_track_patterns(
                all_patterns, self.personal_keep_rules, self.pattern_categories,
            )
            resolved_count = len(all_patterns) - len(patterns)
            pending_keys = {
                str(row.get("key", "")) for row in self.pending_pattern_reviews
            }
            deferred_count = sum(1 for row in patterns if str(row.get("key", "")) in pending_keys)
            patterns = [row for row in patterns if str(row.get("key", "")) not in pending_keys]

            if deferred_count:
                self._append_activity(f"{deferred_count} pending pattern(s) deferred from review")
            if resolved_count:
                self._append_activity(
                    f"Saved choices: {resolved_count} unusual pattern(s) already resolved"
                )

            if patterns:
                self._pattern_review_mode = "scan"
                self._review_visible_rows = list(patterns)
                self.review_pending = True
                self._emit_state()
                rows = []
                for item in patterns:
                    key = str(item.get("key", ""))
                    label = str(item.get("label", key))
                    rows.append({
                        "key": key,
                        "label": label,
                        "count": int(item.get("count", 0) or 0),
                        "variants": [str(x) for x in item.get("variants", [])],
                        "examples": [str(x) for x in item.get("examples", [])],
                        "keep": False,
                        "existing": False,
                    })
                self._event({"type": "patternReview", "patterns": rows,
                             "saveError": save_error})
                return

            if all_patterns:
                self._append_activity("No unresolved unusual track patterns")
            else:
                self._append_activity("No version-style track patterns detected")
            self._begin_prepared_analysis(set())

        def getPatternManager(self):
            self._reload_classifications()
            return _json_ui_dumps({
                "categories": [
                    {"key": key, **value}
                    for key, value in sorted(self.pattern_categories.items())
                ],
                "pending": _unresolved_track_patterns(
                    self.pending_pattern_reviews, self.personal_keep_rules, self.pattern_categories),
            })

        def savePatternManager(self, raw: str):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            self._reload_classifications()
            try:
                data = json.loads(raw or "{}")
                if not isinstance(data, dict):
                    raise ValueError("Invalid pattern-manager data.")
                categories = _normalize_pattern_categories(data.get("categories", []))
                promote = data.get("promote", [])
                if not isinstance(promote, list):
                    raise ValueError("Invalid Personal Picks.")
                picks = [dict(item) for item in self.personal_keep_rules]
                for entry in promote:
                    if not isinstance(entry, dict):
                        continue
                    key = normalize_space(str(entry.get("key", ""))).casefold()
                    label = normalize_space(str(entry.get("label", ""))) or key
                    if key:
                        categories.pop(key, None)
                        _add_personal_pattern_rule(picks, key, label)
                remaining = _unresolved_track_patterns(self.pending_pattern_reviews, picks, categories)
                _save_pattern_categories(categories)
                _save_pending_pattern_reviews(remaining)
                self.pattern_categories = categories
                self.pending_pattern_reviews = remaining
                self.personal_keep_rules = picks
                self._save_settings()
                self._invalidate_live_analysis_after_preferences()
                self._emit_state()
            except Exception as exc:
                self._event({"type":"error","title":APP_NAME,
                             "message":f"Could not save classifications: {exc}"})
            return self._state_json()

        def openPendingPatterns(self):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            rows = _unresolved_track_patterns(
                self.pending_pattern_reviews, self.personal_keep_rules, self.pattern_categories,
            )
            if not rows:
                return self._state_json()
            self._pattern_review_mode = "deferred"
            self._review_visible_rows = list(rows)
            self.review_pending = True
            self._emit_state()
            self._event({"type": "patternReview", "deferred": True, "patterns": rows})
            return self._state_json()

        def submitPatternReview(self, raw: str):
            self._complete_pattern_review(raw, postpone=False)

        def deferPatternReview(self, raw: str):
            self._complete_pattern_review(raw, postpone=True)

        def _complete_pattern_review(self, raw: str, postpone: bool) -> None:
            if not self.review_pending or self._pattern_review_mode not in {"scan", "deferred"}:
                return
            mode = self._pattern_review_mode
            if mode == "scan" and not self._pending_analysis:
                return
            try:
                result = json.loads(raw or "{}")
            except (ValueError, TypeError):
                result = None
            if not isinstance(result, dict):
                self._append_activity("Invalid pattern classifications; no changes saved")
                self._event({"type": "patternReview", "patterns": self._review_visible_rows,
                             "deferred": mode == "deferred", "saveError": "Invalid choices"})
                return

            visible = {
                str(row.get("key", "")): row for row in self._review_visible_rows
                if isinstance(row, dict)
            }
            selections: Dict[str, str] = {}
            for key, value in result.items():
                key = str(key)
                choice = ("keep" if value else "skip") if isinstance(value, bool) else str(value).lower()
                if key not in visible or choice not in {"skip", "keep", "remix", "live"}:
                    self._append_activity("Pattern review rejected an invalid choice")
                    self._event({"type": "patternReview", "patterns": self._review_visible_rows,
                                 "deferred": mode == "deferred", "saveError": "Invalid choices"})
                    return
                selections[key] = choice
            if not postpone and set(selections) != set(visible):
                self._append_activity("Pattern review incomplete; no classifications saved")
                self._event({"type": "patternReview", "patterns": self._review_visible_rows,
                             "deferred": mode == "deferred", "saveError": "Incomplete choices"})
                return

            updated_categories = dict(self.pattern_categories)
            updated_picks = [dict(item) for item in self.personal_keep_rules]
            excluded: Set[str] = set()
            added = 0
            categorized = 0
            for key, choice in selections.items():
                label = str(visible[key].get("label", key))
                if choice == "keep":
                    if _add_personal_pattern_rule(updated_picks, key, label):
                        added += 1
                elif choice in {"remix", "live", "skip"}:
                    updated_categories[normalize_space(key).casefold()] = {
                        "kind": choice, "label": label,
                    }
                    categorized += 1
                if choice == "skip" and mode == "scan":
                    excluded.add(key)

            # Save the remainder before analysis resumes. Deferred items from older
            # runs survive new scans; selected items are removed only on decision.
            pending = {
                str(row.get("key", "")): row for row in self.pending_pattern_reviews
            }
            for key in selections:
                pending.pop(key, None)
            if mode == "scan" and postpone:
                for key, row in visible.items():
                    if key not in selections:
                        pending[key] = row
            remaining = _unresolved_track_patterns(
                list(pending.values()), updated_picks, updated_categories,
            )
            try:
                if categorized:
                    _save_pattern_categories(updated_categories)
                if added:
                    _save_app_settings(
                        "", "", self.save_remixes, self.save_live,
                        self.logging_enabled, self.pattern_preferences, updated_picks, self.io_workers,
                        source_folders=self.folders,
                    )
                    saved_picks = _load_personal_keep_rules(_load_app_settings())
                    if any(key not in _personal_pattern_keys(saved_picks)
                           for key, choice in selections.items() if choice == "keep"):
                        raise OSError("Personal Picks were not persisted")
                _save_pending_pattern_reviews(remaining)
            except Exception as exc:
                self._append_activity(f"ERROR: Pattern choices could not be saved: {exc}")
                self._event({"type": "patternReview", "patterns": self._review_visible_rows,
                             "deferred": mode == "deferred", "saveError": str(exc)})
                return

            self.pattern_categories = updated_categories
            self.personal_keep_rules = updated_picks
            self.pending_pattern_reviews = remaining
            if categorized:
                self._append_activity(f"Remembered {categorized} Remix/Live/Skip classification(s)")
            if added:
                self._append_activity(f"Personal Picks: added {added} unusual pattern(s)")
            if mode == "scan":
                if postpone:
                    self._append_activity(
                        f"Pattern review postponed: {len(visible) - len(selections)} pending; "
                        "unclassified tracks remain included"
                    )
                else:
                    self._append_activity(
                        f"Pattern review complete: {len(selections)} choice(s); "
                        f"{len(excluded)} saved Skip classification(s)"
                    )
                if self._pending_analysis:
                    self._pending_analysis["pattern_categories"] = dict(updated_categories)
                self._begin_prepared_analysis(excluded)
            else:
                self._pattern_review_mode = ""
                self._review_visible_rows = []
                self.review_pending = False
                self._append_activity(
                    f"Pending pattern review: {len(selections)} decided, "
                    f"{len(remaining)} remaining; future analyses use saved classifications"
                )
                self._emit_state()

        def cancelReview(self):
            if not self.review_pending:
                return
            if self._pattern_review_mode == "deferred":
                self._pattern_review_mode = ""
                self._review_visible_rows = []
                self.review_pending = False
                self._emit_state()
                return
            self._pattern_review_mode = ""
            self._review_visible_rows = []
            self._pending_analysis = None
            self.review_pending = False
            self.running = False
            self.status = "Cancelled"
            self.progress_count = ""
            self._append_activity("Cancelled before audio comparison")
            self._emit_state()

        def _begin_prepared_analysis(self, excluded_pattern_keys: Set[str]) -> None:
            ctx = self._pending_analysis
            if not ctx:
                return
            self._pattern_review_mode = ""
            self._review_visible_rows = []
            self.review_pending = False
            self.status = "Continuing analysis"
            self.progress_pct = 0.0
            self.progress_count = ""
            self._last_progress_stage = ""
            self._set_running(True)
            threading.Thread(
                target=self._prepared_worker,
                args=(ctx, set(excluded_pattern_keys)),
                daemon=True,
            ).start()

        def _prepared_worker(self, ctx: Dict[str, object], excluded_pattern_keys: Set[str]) -> None:
            try:
                recycle = ctx["recycle"]
                assert isinstance(recycle, Path)
                logging_enabled = bool(ctx.get("logging_enabled"))
                comparison_log_path = _new_comparison_log_path(recycle) if logging_enabled else None
                ctx["comparison_log_path"] = comparison_log_path
                result = analyze_prepared(
                    ctx["releases"],
                    ctx["tracks"],
                    True,
                    self._progress,
                    not bool(ctx.get("save_remixes")),
                    not bool(ctx.get("save_live")),
                    excluded_pattern_keys,
                    comparison_log_path,
                    [dict(item) for item in self.personal_keep_rules],
                    int(ctx.get("io_limit", 2)),
                    dict(ctx.get("pattern_categories", {})),
                )
                self._analysis_done(ctx, result)
            except Exception as exc:
                self._error(str(exc))

        def _analysis_done(self, ctx: Dict[str, object], result) -> None:
            self.running = False
            self.run_started_epoch_ms = 0

            releases, tracks, groups, selected, reviews, notes = result

            if reviews:
                self.review_pending = True
                self.progress_pct = 100.0
                self.progress_count = f"{len(reviews):,} case(s)"
                self.status = "Manual acoustic review"
                ctx["manual_review_state"] = {
                    "releases": releases,
                    "tracks": tracks,
                    "groups": groups,
                    "reviews": reviews,
                    "notes": notes,
                }
                self._append_activity(
                    f"Manual acoustic review required: {len(reviews)} rare case(s)"
                )
                self._emit_state()
                self._event({
                    "type": "manualReview",
                    "candidates": reviews,
                })
                return

            self.review_pending = False
            self.progress_pct = 100.0
            self.progress_count = "100%"
            self._append_activity("Analysis complete")
            audit_releases = [rel for rel in releases if rel.validation_issues or any(t.integrity_error for t in rel.tracks)]
            if audit_releases:
                self._append_activity(
                    f"WARNING: {len(audit_releases)} release(s) have corrupt files or incomplete track numbering; Copy/Move blocked."
                )

            comparison_log = next(
                (
                    n.split("COMPARISON LOG:", 1)[1].strip()
                    for n in notes
                    if n.startswith("COMPARISON LOG:")
                ),
                "",
            )
            if comparison_log:
                self._append_activity(f"Comparison log: {comparison_log}")

            stored_ignored_paths = _load_manual_ignored_release_paths()
            blocked_release_ids: Set[int] = {
                rel.rid for rel in releases
                if _manual_album_group_path_key(rel.path) in stored_ignored_paths
            }
            if selected & blocked_release_ids:
                raise RuntimeError("Fresh analysis selected a persistently ignored release.")
            if blocked_release_ids:
                self._append_activity(
                    f"Applied {len(blocked_release_ids)} saved ignored release(s) during optimization"
                )
            decisions = build_release_decisions(
                releases,
                tracks,
                selected,
                reviews,
                blocked_release_ids,
            )
            counts = action_summary(decisions)
            recycle_kept = sum(
                1
                for d in decisions
                if next(r for r in releases if r.rid == d.release_id).root_kind == "recycle"
                and d.action in {"ADD", "REPLACE", "KEEP"}
            )
            initial_intra_duplicates = plan_intra_release_duplicates(releases, decisions)

            self._decision_snapshot = build_decision_snapshot(
                releases,
                tracks,
                selected,
                decisions,
                blocked_release_ids,
            )
            _save_decision_snapshot(self._decision_snapshot)
            self.status = "Analysis complete - review Release Map"
            retained_count = sum(
                1 for d in decisions if d.action in {"KEEP", "ADD", "REPLACE"}
            )
            self._append_activity(f"Release Map ready: {retained_count} retained release(s)")

            summary_parts = [
                f"Retained recycle releases: {recycle_kept}",
                f"Hidden duplicate recycle releases: {counts['SKIP']}",
            ]
            existing = ctx.get("existing")
            if existing is not None:
                summary_parts.append(f"Hidden duplicate existing releases: {counts['REMOVE']}")
            if initial_intra_duplicates:
                summary_parts.append(
                    f"Duplicate files inside retained releases: {len(initial_intra_duplicates)}"
                )
            if comparison_log:
                summary_parts.append("Detailed comparison logging is enabled.")

            session: Dict[str, object] = {
                "snapshots": list(self._decision_snapshot),
                "initial_plan_counts": _release_map_plan_counts(self._decision_snapshot),
                "allow_apply": True,
                "summary_text": " | ".join(summary_parts),
                "existing": existing,
                "recycle": ctx.get("recycle"),
                "extra_roots": list(ctx.get("extra_roots", []) or []),
                "releases": releases,
                "tracks": tracks,
                "groups": groups,
                "selected": set(selected),
                "reviews": list(reviews),
                "decisions": list(decisions),
                "blocked_release_ids": set(blocked_release_ids),
                "comparison_log_path": ctx.get("comparison_log_path"),
            }
            self._live_release_map_session = session
            self._pending_analysis = None
            self._emit_state()
            self._launch_release_map()

        def submitManualReview(self, raw: str):
            ctx = self._pending_analysis
            if not ctx:
                return
            state = ctx.get("manual_review_state")
            if not isinstance(state, dict):
                self._error("Manual acoustic review state is no longer available.")
                return
            try:
                incoming = json.loads(raw or "[]")
            except Exception:
                incoming = []
            accepted = {
                str(value)
                for value in incoming
                if str(value).strip()
            } if isinstance(incoming, list) else set()

            self.review_pending = False
            self.status = "Applying manual acoustic review"
            self.progress_pct = 0.0
            self.progress_count = ""
            self._last_progress_stage = ""
            self._append_activity(
                f"Manual review complete: {len(accepted)} pair(s) confirmed same recording"
            )
            self._set_running(True)
            threading.Thread(
                target=self._manual_review_worker,
                args=(ctx, accepted),
                daemon=True,
            ).start()

        def _manual_review_worker(
            self,
            ctx: Dict[str, object],
            accepted_keys: Set[str],
        ) -> None:
            try:
                state = ctx.get("manual_review_state")
                if not isinstance(state, dict):
                    raise RuntimeError("Manual review state is missing.")

                releases = state.get("releases")
                tracks = state.get("tracks")
                groups = state.get("groups")
                reviews = state.get("reviews")
                notes = list(state.get("notes", []) or [])
                if not isinstance(releases, list) or not isinstance(tracks, list) or not isinstance(groups, dict) or not isinstance(reviews, list):
                    raise RuntimeError("Manual review state is invalid.")

                progress_total = max(1, len(reviews))
                self._progress("Applying manual acoustic decisions...", 0, progress_total)
                groups = apply_manual_review_merges(
                    tracks,
                    groups,
                    reviews,
                    accepted_keys,
                )
                self._progress(
                    "Applying manual acoustic decisions...",
                    progress_total,
                    progress_total,
                )

                compilation_removed = apply_compilation_policy(releases)
                if compilation_removed:
                    notes.append(
                        f"Compilation policy removed {compilation_removed} non-unique compilation track(s) from coverage."
                    )

                self._progress("Applying saved track skips...", 0, 1)
                apply_persistent_track_skips(tracks)
                self._progress("Applying saved track skips...", 1, 1)

                comparison_log_path = ctx.get("comparison_log_path")
                if not isinstance(comparison_log_path, Path):
                    comparison_log_path = None

                if comparison_log_path is not None:
                    try:
                        with comparison_log_path.open("a", encoding="utf-8", newline="\n") as handle:
                            handle.write(
                                json.dumps(
                                    {
                                        "record_type": "manual_review",
                                        "generated": datetime.now().isoformat(timespec="seconds"),
                                        "cases": len(reviews),
                                        "accepted_same_recording": sorted(accepted_keys),
                                        "rejected_as_different": sorted(
                                            str(row.get("key", ""))
                                            for row in reviews
                                            if str(row.get("key", "")) not in accepted_keys
                                        ),
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                    except Exception as exc:
                        notes.append(f"Manual review log write error: {exc}")

                self._progress("Optimizing release set...", 0, 1)
                selected = optimize_collection(
                    releases,
                    groups,
                    blocked_release_ids={
                        rel.rid for rel in releases
                        if _manual_album_group_path_key(rel.path)
                        in _load_manual_ignored_release_paths()
                    },
                    progress_cb=self._progress,
                    comparison_log_path=comparison_log_path,
                    errors=notes,
                )
                self._progress("Optimizing release set...", 1, 1)
                self._progress("Building automatic action plan...", 1, 1)

                ctx.pop("manual_review_state", None)
                self._analysis_done(
                    ctx,
                    (releases, tracks, groups, selected, [], notes),
                )
            except Exception as exc:
                self._error(str(exc))

        def _update_live_release_map_session(
            self,
            session: Dict[str, object],
            map_result: Dict[str, object],
        ) -> None:
            session["snapshots"] = list(
                map_result.get("snapshots", session.get("snapshots", [])) or []
            )
            session["selected"] = set(
                map_result.get("selected", session.get("selected", set())) or set()
            )
            session["decisions"] = list(
                map_result.get("decisions", session.get("decisions", [])) or []
            )
            session["blocked_release_ids"] = set(
                map_result.get(
                    "blocked_release_ids",
                    session.get("blocked_release_ids", set()),
                )
                or set()
            )
            incoming_initial = map_result.get("initial_plan_counts")
            if isinstance(incoming_initial, dict):
                session["initial_plan_counts"] = {
                    "releases": max(0, int(incoming_initial.get("releases", 0) or 0)),
                    "tracks": max(0, int(incoming_initial.get("tracks", 0) or 0)),
                }
            self._decision_snapshot = list(session["snapshots"])
            _save_decision_snapshot(self._decision_snapshot)

        def openReleaseMap(self):
            if self.running or self.review_pending or self.map_open:
                return
            self._launch_release_map()

        def _launch_release_map(self) -> None:
            if self.map_open:
                return
            session = self._live_release_map_session
            if session is None:
                snapshots = self._decision_snapshot or _load_decision_snapshot()
                if not snapshots:
                    self._info("No analyzed release decisions are available yet.")
                    return
                session = {
                    "snapshots": snapshots,
                    "allow_apply": False,
                }
            self.map_open = True
            self.status = "Opening Release Map"
            self._emit_state()
            threading.Thread(
                target=self._release_map_worker,
                args=(session, self._live_release_map_session is not None),
                daemon=True,
            ).start()

        def _release_map_worker(self, session: Dict[str, object], live: bool) -> None:
            try:
                map_result = launch_webview_release_map(dict(session))
                if live and self._live_release_map_session is not None:
                    self._handle_live_map_result(self._live_release_map_session, map_result)
                else:
                    self.map_open = False
                    self.status = "Ready"
                    self._emit_state()
            except Exception as exc:
                self.map_open = False
                self._error(f"Release Map failed:\n\n{exc}")

        def _handle_live_map_result(
            self,
            session: Dict[str, object],
            map_result: Dict[str, object],
        ) -> None:
            self._update_live_release_map_session(session, map_result)
            self.map_open = False
            if map_result.get("requires_fresh_scan") or map_result.get("pending_plan"):
                session["allow_apply"] = False
                self.status = "Pending changes - Analyze again"
                self._append_activity("Release Map decisions are not applied. Analyze again before Copy/Move.")
                self._emit_state()
                return
            action = str(map_result.get("action", "") or "")
            if action not in {"copy_all", "move_all"}:
                self.status = "Analysis complete - no copy performed."
                self._emit_state()
                return

            existing = session.get("existing")
            recycle = session.get("recycle")
            releases = session.get("releases")
            decisions = list(session.get("decisions", []) or [])
            destination_text = str(map_result.get("destination", "") or "").strip()
            if not isinstance(recycle, Path) or not isinstance(releases, list):
                self._error("The live analysis context is no longer available.")
                return
            if not destination_text:
                destination_text = str(default_updated_destination(recycle))
            is_move = action == "move_all"
            destination = Path(destination_text)
            self.progress_pct = 0.0
            self.progress_count = ""
            self.status = "Moving retained OLD + NEW releases" if is_move else "Copying final discography"
            self._last_progress_stage = ""
            self._append_activity(self.status)
            self._set_running(True)

            try:
                if is_move:
                    result = move_retained_plan(
                        existing if isinstance(existing, Path) else None,
                        recycle, destination, releases, decisions, self._progress,
                        extra_roots=list(session.get("extra_roots", []) or []),
                    )
                else:
                    result = copy_retained_plan(
                        existing if isinstance(existing, Path) else None,
                        recycle, destination, releases, decisions, "all", self._progress,
                        extra_roots=list(session.get("extra_roots", []) or []),
                    )
                self._live_release_map_session = None
                if is_move:
                    # Release paths point to old locations after a move.
                    # Require a fresh scan rather than opening a stale map.
                    self._decision_snapshot = []
                    _save_decision_snapshot([])
                self._copy_done(destination, result)
            except Exception as exc:
                self.running = False
                self.run_started_epoch_ms = 0
                self.status = "Analysis complete - export failed."
                self._error(str(exc))

        def _copy_done(self, destination: Path, result: Dict[str, object]) -> None:
            self.running = False
            self.run_started_epoch_ms = 0
            self.progress_pct = 100.0
            self.progress_count = "100%"
            moved = bool(result.get("source_folders_modified"))
            self.status = "Move complete - Undo available" if moved else "Copy complete"
            self._append_activity(
                f"{'Move' if moved else 'Copy'} complete: "
                f"{result.get('logical_releases', 0)} retained release(s)"
            )
            self._emit_state()
            self._event({
                "type": "copyDone",
                "destination": str(destination),
                "result": result,
            })


        def undoLastRun(self):
            if self.running or self.review_pending or self.map_open:
                return
            self.status = "Undoing last run"
            self.progress_pct = 0.0
            self.progress_count = ""
            self._append_activity("Undo last run")
            self._set_running(True)
            threading.Thread(target=self._undo_worker, daemon=True).start()

        def _undo_worker(self) -> None:
            try:
                restored, conflicts = undo_last_run()
                self.running = False
                self.run_started_epoch_ms = 0
                self.status = "Ready"
                self.progress_pct = 0.0
                self.progress_count = ""
                self._append_activity(
                    f"Undo complete: restored {restored}, conflicts {len(conflicts)}"
                )
                self._emit_state()
                if conflicts:
                    self._info(
                        f"Restored: {restored}\nConflicts: {len(conflicts)}",
                        "Undo complete",
                    )
                else:
                    self._info(f"Restored: {restored}", "Undo complete")
            except Exception as exc:
                self._error(str(exc))


    bridge = MainBridge()
    window = webview.create_window(
        f"{APP_NAME} {APP_VERSION} - Under construction ⚠️",
        html=_webview_main_html(),
        width=1040,
        height=760,
        min_size=(880, 640),
        background_color="#0b0c0f",
        text_select=True,
        zoomable=True,
    )
    bridge.window = window
    bridge.webview = webview
    _expose_bridge_methods(
        window,
        bridge,
        (
            "getState",
            "setFolders",
            "browseFolder",
            "setOption",
            "setIoWorkers",
            "getPersonalPicks",
            "savePersonalPicks",
            "copyText",
            "openLogsFolder",
            "openPath",
            "closeApp",
            "startAnalyze",
            "openPendingPatterns",
            "getPatternManager",
            "savePatternManager",
            "submitPatternReview",
            "deferPatternReview",
            "cancelReview",
            "submitManualReview",
            "openReleaseMap",
            "undoLastRun",
        ),
    )

    def _closed():
        try:
            bridge._save_settings()
        except Exception:
            pass
        _end_app_children()

    window.events.closed += _closed

    # pywebview's documented default is private mode. DEA has no browser-side
    # persistence requirement; all real settings/state live in the app data
    # directory. A persistent WebView2 profile caused later launches to show a
    # window while window.pywebview.api never received methods such as getState.
    _cleanup_legacy_webview_profile()
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=WEBVIEW_PRIVATE_MODE,
    )
    return 0


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--version":
        print(f"{APP_NAME} {APP_VERSION}")
        raise SystemExit(0)
    try:
        raise SystemExit(_webview_main_app())
    except SystemExit:
        raise
    except Exception as exc:
        _report_startup_crash(exc)
        raise


if __name__ == "__main__":
    main()
