# Music Collection Cleaner Lightweight
# Lightweight WebView2 host retaining the analyzer core and full interactive Release Map.

from __future__ import annotations

import atexit
import base64
import concurrent.futures
import difflib
import io
import lzma
import urllib.error
import urllib.parse
import uuid
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
APP_VERSION = "0.5.130"
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
    """Source folder rows: path text plus a star (= main folder).

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


ORGANIZER_OPTION_DEFAULTS: Dict[str, object] = {
    "format": "ALAC", "enable_encoding": True, "enable_checker": True, "enable_splitting": True,
}


def _organizer_options(settings: Optional[dict] = None) -> Dict[str, object]:
    """Saved Copy/Move organizer options; unknown or missing values fall back to defaults."""
    saved = (settings if settings is not None else _load_app_settings()).get("organizer_options")
    saved = saved if isinstance(saved, dict) else {}
    options = dict(ORGANIZER_OPTION_DEFAULTS)
    if saved.get("format") in ("ALAC", "FLAC"):
        options["format"] = saved["format"]
    for key in ("enable_encoding", "enable_checker", "enable_splitting"):
        if isinstance(saved.get(key), bool):
            options[key] = saved[key]
    return options


def _save_organizer_option(name: str, value) -> None:
    if name not in ORGANIZER_OPTION_DEFAULTS:
        raise ValueError(f"Unknown organizer option: {name!r}")
    settings = _load_app_settings()
    options = _organizer_options(settings)
    options[name] = value if name == "format" else bool(value)
    if options["format"] not in ("ALAC", "FLAC"):
        raise ValueError(f"Unknown format: {value!r}")
    settings["organizer_options"] = options
    _atomic_write_json(_settings_path(), settings)


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
        "organizer_options": _organizer_options(previous),
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

# Same title in the same album track slot (alternate masters); calibrated on the
# five logged Re-TROS Cut Off! pairs, worst pair 9.56 / 0.619 / 10 / 13.
FP_ALBUM_CONTEXT_SCORE_MAX = 10.0
FP_ALBUM_CONTEXT_GOOD_MIN = 0.60
FP_ALBUM_CONTEXT_MEDIAN_MAX = 10
FP_ALBUM_CONTEXT_P90_MAX = 16
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



def _harmonize_heuristic_album_types(releases: List["Release"]) -> None:
    """Editions of one album (same album tag, >=80% shared titles) get one type.

    The track-count guess (7+ tracks is an Album, fewer an EP) otherwise splits
    a 6-track and a 7-track edition of the same release into two types.
    """
    guessed = [rel for rel in releases
               if rel.type_source == "heuristic" and rel.release_type in {"album", "ep"}]
    for i, first in enumerate(guessed):
        for second in guessed[i + 1:]:
            if first.release_type != second.release_type and _album_editions_share_titles(first, second):
                first.release_type = second.release_type = "album"


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
    _harmonize_heuristic_album_types(releases)


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
        elif track.is_remix:
            # An extra ARTIST entry on a remix is the remixer; only a stated
            # feat./ft. credit is a feature.
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
                # An extra ARTIST entry on a plain '(Remix)' is the remixer, not a
                # featured vocalist; only a feature stated after Remix/Mix counts.
                added_features = remix_specific_featured_artists(track)

        track.remix_feature_exception = bool(
            track.is_remix
            and any(
                _has_explicit_feature_credit(value)
                for value in (track.display_title, strip_track_number(track.path.stem), track.artist)
                if value
            )
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
    rip_log_results: List[str] = field(default_factory=list)  # one display line per checked log
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
    # ffprobe writes UTF-8; decoding with the Windows code page turned CJK tags into mojibake.
    cp = run_hidden(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    encoding="utf-8", errors="replace", check=False)
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


def _fingerprint_album_context_match(
    fp1: Tuple[int, ...], duration1: float,
    fp2: Tuple[int, ...], duration2: float, sim
) -> bool:
    """Looser fingerprint bounds for the same title in the same album track slot.

    Only used with that routing context (the title and slot already agree), for
    alternate masters of one album. Whole-recording overlap and the 8-second
    length bound remain mandatory.
    """
    if not sim or min(len(fp1), len(fp2)) < 120:
        return False
    score, good, overlap, _shift, _excellent, median, p90 = sim
    return bool(
        not _duration_version_conflict(duration1, duration2)
        and 0 <= score <= FP_ALBUM_CONTEXT_SCORE_MAX
        and good >= FP_ALBUM_CONTEXT_GOOD_MIN
        and median <= FP_ALBUM_CONTEXT_MEDIAN_MAX
        and p90 <= FP_ALBUM_CONTEXT_P90_MAX
        and overlap >= 0.995
        and _fingerprint_acoustic_coverage(fp1, fp2, sim) >= 0.985
    )


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
            and 0 <= score <= 9.0
            and good >= 0.80
            and median <= 9
            and p90 <= 13
            and overlap >= 0.995
            and _fingerprint_acoustic_coverage(fp1, fp2, sim) >= 0.98
        )
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
    album_context_matches: Set[Tuple[int, int]] = set()
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
        if pair in album_context_matches:
            details["accepted_by"].append("album_context_fingerprint")
            details["derived_final_match"] = not details["duration_version_conflict"]
            details["decision_consistent"] = bool(audio_matched) == details["derived_final_match"]
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
            or {"same_base_title", "same_album_track_slot"} <= set(reasons)
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
            if (not _matched
                    and {"same_base_title", "same_album_track_slot"} <= candidate_reasons.get((a, b), set())
                    and _fingerprint_album_context_match(
                        tracks[a].fingerprint, _identity_track_duration(tracks[a]),
                        tracks[b].fingerprint, _identity_track_duration(tracks[b]), sim)):
                album_context_matches.add((a, b))
                continue
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
            or bool(pcm_verdicts.get((a,b), {}).get("passed"))
            or (a,b) in album_context_matches,sim)
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

    # Default Live wording cannot make a verified CD copy ineligible while the
    # very same recording is allowed under another edition's tags. A Remix stays
    # excluded: it is not restored by an identical copy elsewhere.
    # Explicit saved classifications, pattern skips and advisory preference
    # remain authoritative inclusion decisions. Saved recording Ignore is
    # applied later to every acoustic member, including any restored copy.
    for root, ids in roots.items():
        if not any(not tracks[i].exclude_from_coverage for i in ids):
            continue
        for i in ids:
            track = tracks[i]
            if (track.exclude_from_coverage and track.is_live and not track.is_remix
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


def score_rip_log_file(score_log, path: Path) -> dict:
    """Score one rip log, re-encoding legacy ANSI logs the checker cannot decode.

    hey-bro-check-log guesses the encoding with chardet and falls back to UTF-8 when
    unsure, so an old EAC log saved in a Windows code page fails with "Could not decode
    log file". Retry from a UTF-8 copy decoded as Windows-1252, then Windows-1251
    (Russian logs), then Latin-1, and keep the first result that is recognised.
    shortcut: the first code page that matches wins, upgrade if a log is scored wrongly.
    """
    result = score_log(path)
    if not result.get("unrecognized"):
        return result
    raw = path.read_bytes()
    for code_page in ("cp1252", "cp1251", "latin-1"):
        with tempfile.TemporaryDirectory() as temp_dir:
            copy = Path(temp_dir) / "rip.log"
            copy.write_bytes(b"\xef\xbb\xbf" + raw.decode(code_page, errors="replace").encode("utf-8"))
            retry = score_log(copy)
        if not retry.get("unrecognized"):
            return retry
    return result


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
            result = score_rip_log_file(score_log, path)
            unrecognized = result.get("unrecognized")
            if unrecognized:
                message = str(unrecognized)
                rel.rip_log_results.append(f"{path.name}: not recognized - {message}")
                rel.rip_log_unrecognized.append(f"{path.name}: {message}")
                errors.append(f"Rip log unrecognized: {path}: {message}")
            else:
                try:
                    score = int(result.get("score"))
                except (TypeError, ValueError):
                    raise RuntimeError("log checker returned no numeric score")
                rel.rip_log_scores.append(score)
                rel.rip_log_rippers.append(str(result.get("ripper") or ""))
                flagged = bool(result.get("flagged"))
                if flagged:
                    rel.rip_log_flagged += 1
                rel.rip_log_results.append(
                    f"{path.name}: {score}%" + (f" ({result.get('ripper')})" if result.get("ripper") else "")
                    + (" - flagged" if flagged else ""))
        except Exception as exc:
            message = str(exc)
            rel.rip_log_results.append(f"{path.name}: scoring failed - {message}")
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


def _release_album_title_key(rel: Release) -> str:
    """Most common album tag of the included tracks, else the release title."""
    counts = Counter(
        normalize_title(t.album) for t in rel.tracks
        if t.album and not t.exclude_from_coverage
    )
    counts.pop("", None)
    return counts.most_common(1)[0][0] if counts else normalize_title(rel.title)


def _album_editions_related_by_titles(a: Release, b: Release) -> bool:
    return a.release_type == b.release_type and _album_editions_share_titles(a, b)


def _album_editions_share_titles(a: Release, b: Release) -> bool:
    """Same album tag and >=80% shared track titles, for editions whose audio never matches.

    Different masters of one album share no fingerprint group, so the audio rule
    cannot see them. This relation only places them in one album family (display
    grouping, never mixing Albums with EPs); it never makes two recordings the same recording.
    """
    if a.release_type not in {"album", "ep"} or b.release_type not in {"album", "ep"}:
        return False
    key_a = _release_album_title_key(a)
    if not key_a or key_a != _release_album_title_key(b):
        return False
    titles_a = {normalize_title(t.title) for t in a.tracks if not t.exclude_from_coverage} - {""}
    titles_b = {normalize_title(t.title) for t in b.tracks if not t.exclude_from_coverage} - {""}
    smaller = min(len(titles_a), len(titles_b))
    common = len(titles_a & titles_b)
    return smaller >= 4 and common >= 4 and common / smaller >= ALBUM_OVERLAP_THRESHOLD


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
        if _album_editions_related_by_audio(albums[i], albums[j]) or _album_editions_related_by_titles(albums[i], albums[j]):
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



def _recordings_that_require_release(releases: List[Release], selected: Set[int], rel: Release,
                                     blocked: Optional[Set[int]] = None) -> Set[int]:
    """Recording groups that no other release carries, kept or not.

    A recording with the same audio on any other (even unselected) edition is not
    why this release is kept; the source or the rest of the album is.
    """
    other_groups: Set[int] = set()
    for other in releases:
        if other.rid != rel.rid and other.rid not in (blocked or set()):
            other_groups |= other.groups
    return rel.groups - other_groups


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

        essential_groups = _recordings_that_require_release(releases, selected, rel) if rel.rid in selected else set()

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
            essential_groups = _recordings_that_require_release(releases, selected, rel, blocked)

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
                "has_cue": rel.has_cue,
                "has_rip_log": rel.has_rip_log,
                "rip_log_percent": min(rel.rip_log_scores) if rel.rip_log_scores else None,
                "rip_log_problems": list(rel.rip_log_unrecognized),
                "rip_log_results": list(rel.rip_log_results),
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


# ======================================================================
# Library organizer engine (merged from Music Library Organizer v0.3.23).
# Copy / Move run every retained release through it: standard folder name,
# tags, ALAC/FLAC encoding, CUE split, AudioChecker log, artwork.
# ======================================================================

AUDIO = {".flac", ".ape", ".wv", ".wav", ".m4a", ".aiff", ".aif"}
LOSSY = {".mp3", ".aac", ".ogg", ".opus", ".wma", ".mp4"}
DISC = re.compile(r"^(?:CD|Disc)\s*\d+(?:\b|$)", re.I)
RELEASE = re.compile(r"^\d{4}(?:-\d\d){0,2} - .+ \[[^\[\]]+\]$")
TRACK = re.compile(r"^\s*(\d{1,3})[\s._-]+(.+?)\s*$")
FILE = re.compile(r'^\s*FILE\s+"([^"]+)"\s+\w+\s*$', re.I)
INDEX = re.compile(r"^\s*INDEX\s+(\d\d)\s+(\d\d):(\d\d):(\d\d)\s*$", re.I)
QTITLE = re.compile(r'^\s*TITLE\s+"(.*)"\s*$', re.I)

DATA = _saved_data_dir()
UNDO = DATA / "organizer-undo.json"
HISTORY = DATA / "organizer-undo-history"
REPORT = DATA / "organizer-last-run.json"
DEPS = _dependencies_dir()
IS_WIN = os.name == "nt"
VERSION = APP_VERSION


def ensure_data():
    DATA.mkdir(parents=True, exist_ok=True)


def _new_log(kind):
    """Create a collision-proof, isolated log for one launch/job/undo."""
    log_dir = DATA / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(8):
        name = f"{kind}-{datetime.now():%Y-%m-%d-%H-%M-%S}-{uuid.uuid4().hex[:12]}.log"
        path = log_dir / name
        try:
            with path.open("x", encoding="utf-8"):
                pass
            return path
        except FileExistsError:
            continue
    raise OSError("Cannot allocate a unique log filename in " + str(log_dir))



def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def hidden():
    return subprocess.CREATE_NO_WINDOW if IS_WIN else 0


def cmd(args, timeout=3600):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, errors="replace", timeout=timeout,
                          creationflags=hidden(), check=False)



def metadata(path: Path):
    try:
        from mutagen import File as MutagenFile
        tag = MutagenFile(str(path), easy=True)
        if tag:
            def first(k):
                v = tag.get(k, [])
                return str(v[0]).strip() if v else ""
            return first("tracknumber"), first("title"), first("artist")
    except Exception:
        pass
    return "", "", ""


_TITLE_GROUP = re.compile(r"(?<!\w)([\(\[\{])([^()\[\]{}]+)([\)\]\}])")
_FT_PREFIX = re.compile(r"(?i)^(?:ft\.?|feat\.?|featuring)\s+(.+)$")
_FT_JOINT = re.compile(r"(?i)^(.+?)\s+(?:ft\.?|feat\.?|featuring)\s+(.+)$")
_EDIT_KEYWORD = re.compile(
    r"(?i)\b(?:radio|edit|extended|version|remix|mix|club|stadium|instrumental|acoustic|dub|original|vip)\b")
_VERSION_HINT = re.compile(
    r"(?i)\b(?:remix|mix|radio|edit|extended|version|club|stadium|instrumental|acoustic|dub|vip|live)\b")



# English minor-word exceptions derived from the user's Picard script.
_PICARD_MINOR_WORDS = frozenset(
    "a an the and but or nor for yet so as at by in of on to from versus".split())
_PICARD_PHRASAL = frozenset((
    "Bun Up", "Break In", "Check In", "Come In", "Drop In", "Fill In",
    "Get In", "Give In", "Join In", "Let In", "Move In", "Tune In",
    "Turn In", "Walk In", "Bring On", "Carry On", "Come On", "Get On",
    "Go On", "Hold On", "Keep On", "Move On", "Pass On", "Put On",
    "Take On", "Turn On", "Try On", "Come By", "Drop By", "Get By",
    "Go By", "Pass By", "Stand By", "Stop By", "Swing By", "Walk By"))
_BARE_TRACK_FEATURE = re.compile(
    r"(?i)\s+(?:ft\.?|feat\.?|featuring)\s+(?P<credit>[\w][\w .&,'’\-]*)$")
_WIN_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


_TITLE_ACRONYMS = frozenset((
    "DJ", "CD", "DVD", "EP", "LP", "EU", "UK", "USA", "US", "EDM",
    "FIFA", "GIMS", "INNA", "VIP", "OST", "TV", "HD", "NBA", "UFC",
    "BBC", "NASA", "AI", "ISRC", "ALAC", "FLAC", "WAV", "MP3", "ID", "OK",
))
_PROTECTED_TITLE_NAMES = re.compile(r"(?i)(?<!\w)(?:G-DRAGON|3OH!3)(?!\w)")


_TITLE_SEGMENT_START = re.compile(r"(?:[:!?(\[{\"“]|\s[-–—])\s*$")
_TITLE_SEGMENT_END = re.compile(r"^\s*(?:[:!?)\]}\"”]|[-–—]\s)")


def picard_small_word_case(text):
    """Normalize words to title case, not merely lowercase English minor words.

    Leave intentional mixed-case names and protected artist names intact;
    preserve known acronyms, digits and accents. Ordinary ALL CAPS are not
    evidence of an acronym (e.g. SIN TI, JOE PESCI).
    """
    value = str(text or "")
    words = list(re.finditer(r"(?u)\b[^\W\d_]+(?:['’][^\W\d_]+)*\b", value))
    protected = [(m.start(), m.end()) for m in _PROTECTED_TITLE_NAMES.finditer(value)]
    output = []
    previous = 0
    for index, match in enumerate(words):
        word = match.group(0)
        before = words[index - 1] if index else None
        phrase = (before.group(0) + " " + word).title() if before else ""
        # RULES.md: colons, ?/!, brackets, quotes and " - " dashes start a new segment,
        # whose first and last words are capitalized.
        first = not index or bool(_TITLE_SEGMENT_START.search(value[:match.start()]))
        last = (index == len(words) - 1 or
                bool(_TITLE_SEGMENT_END.match(value[match.end():])))
        inside_name = any(start <= match.start() and match.end() <= end
                          for start, end in protected)
        if inside_name:
            normalized = word
        elif word.upper() in _TITLE_ACRONYMS:
            normalized = word.upper()
        elif word.casefold() in {"ft", "feat", "featuring", "vs"}:
            normalized = word.lower()
        elif (word.casefold() in _PICARD_MINOR_WORDS and not first and not last
              and phrase not in _PICARD_PHRASAL):
            normalized = word.lower()
        elif word != word.upper() and word != word.lower():
            # Keep intentional CamelCase (iPhone, eBay, McDonald).
            normalized = word
        else:
            normalized = word[:1].upper() + word[1:].lower()
        output.append(value[previous:match.start()] + normalized)
        previous = match.end()
    output.append(value[previous:])
    return "".join(output)


def _normalize_feature_credit(name):
    return re.sub(r"(?<=\w)\s*&\s*(?=\w)", " & ", " ".join(str(name or "").split()))


def _sanitize_windows_name(text):
    return re.sub(r"\s+", " ", _WIN_UNSAFE.sub(" - ", str(text))).strip(" .-")


def _clean_group_spelling(text):
    text = " ".join(str(text).split())
    if _FT_PREFIX.match(text):
        return "ft. " + _normalize_feature_credit(_FT_PREFIX.match(text).group(1))
    # Case only established descriptor words, not proper names or acronyms.
    text = _EDIT_KEYWORD.sub(lambda match: match.group(0) if match.group(0).isupper() else
                             match.group(0)[0].upper() + match.group(0)[1:].lower(), text)
    return picard_small_word_case(text)


def _song_parts(value):
    """Return base, meaningful ordered groups, and original individual credits."""
    value = " ".join(str(value or "").split())
    trailing = _BARE_TRACK_FEATURE.search(value)
    if trailing and not _FT_PREFIX.match(value):
        name = _normalize_feature_credit(trailing.group("credit"))
        value = value[:trailing.start()] + " (ft. " + name + ")"
    matches = list(_TITLE_GROUP.finditer(value))
    base = value[:matches[0].start()].strip() if matches else value
    groups = []
    feature = ""
    named_main = ""
    for match in matches:
        component = match.group(2).strip()
        feat = _FT_PREFIX.match(component)
        split = _FT_JOINT.match(component)
        if feat and not feature:
            feature = feat.group(1).strip()
            groups.append(("feature", "ft. " + feature))
        elif split and not feature:
            named_main, feature = split.group(1).strip(), split.group(2).strip()
            groups.append(("feature", "ft. " + feature))
        else:
            groups.append(("version", _clean_group_spelling(component)))
    if matches and value[matches[-1].end():].strip():
        # Unparsed trailing text is significant; preserve rather than guessing.
        tail = value[matches[-1].end():].strip()
        groups.append(("unparsed", tail))
    return base, groups, named_main, feature


def _song_key(value):
    import unicodedata
    base = _song_parts(value)[0]
    plain = "".join(c for c in unicodedata.normalize("NFKD", base)
                    if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", plain.casefold())


def normalize_artist_title(value, artist="", main_artist="", consensus=None):
    """Render artist/TITLE separately; never put an artist prefix in TITLE."""
    value = " ".join(str(value or "").strip().split())
    artist = " ".join(str(artist or "").strip().split())
    base, groups, named_main, feature = _song_parts(value)
    tagged_main = _FT_JOINT.match(artist)
    if tagged_main and not named_main:
        named_main, feature = tagged_main.group(1).strip(), tagged_main.group(2).strip()
        artist = named_main
        if not any(role == "feature" for role, _ in groups):
            groups.append(("feature", "ft. " + feature))
    if named_main:
        artist = named_main
    if feature and main_artist and artist:
        # A track explicitly crediting (ft. X) should not redundantly store
        # the same performer in a combined ARTIST tag. Limit the removal to
        # exact two-person spellings; do not erase genuine co-headliners.
        main = str(main_artist).strip()
        credited = feature.strip()
        joined = (
            main + " & " + credited, main + ", " + credited,
            main + " ft. " + credited, main + " feat. " + credited,
            main + " featuring " + credited,
        )
        if artist.casefold() in {x.casefold() for x in joined}:
            artist = main
    if feature and consensus:
        pair = frozenset((artist.casefold(), feature.casefold()))
        preferred = consensus.get((_song_key(value), pair))
        if preferred and preferred.casefold() == feature.casefold():
            artist, feature = feature, artist
            groups = [(role, "ft. " + feature if role == "feature" else component)
                      for role, component in groups]
    # Feature already on the ordinary recording is prior to Radio/Edit/Version.
    # Unknown remix-added credits remain after a genuine Remix component.
    feat_at = next((i for i, (role, _) in enumerate(groups) if role == "feature"), -1)
    if feat_at > 0 and all(
            not re.search(r"(?i)\bremix\b", text)
            for role, text in groups[:feat_at] if role == "version"):
        credited = groups.pop(feat_at)
        # Preserve an intrinsic parenthetical title (no edit/version keywords).
        pos = 0
        while pos < len(groups) and groups[pos][0] == "version" and not _VERSION_HINT.search(groups[pos][1]):
            pos += 1
        groups.insert(pos, credited)
    if not groups:
        return picard_small_word_case(value), artist
    brackets = ("()", "[]", "{}")
    if len(groups) > 3 or any(role == "unparsed" for role, _ in groups):
        # Never discard fourth-level descriptors.
        return value, artist
    rendered = picard_small_word_case(base)
    for i, (role, text) in enumerate(groups):
        item = _clean_group_spelling(text)
        rendered += " " + brackets[i][0] + item + brackets[i][1]
    return rendered, artist


def normalized_title(value: str) -> str:
    title, _ = normalize_artist_title(value)
    return title


def track_filename(number: int, title: str, ext: str) -> str:
    title = normalized_title(title)
    title = _sanitize_windows_name(title)
    if not title or number <= 0:
        raise ValueError("Missing valid title/track number")
    return f"{number:02d} {title}{ext}"


def extract_number_title(path: Path, main_artist="", consensus=None):
    tag_num, tag_title, artist = metadata(path)
    number = 0
    if tag_num:
        m = re.match(r"\s*(\d+)", tag_num)
        if m:
            number = int(m.group(1))
    old = TRACK.match(path.stem)
    if not number and old:
        number = int(old.group(1))
    file_title = old.group(2).strip() if old else ""
    title = (tag_title or "").strip()
    # A richer filename must not lose a version solely because its tag is short.
    if file_title and (not title or (
        file_title.casefold().startswith(title.casefold()) and
        len(file_title) > len(title) and
        (_VERSION_HINT.search(file_title[len(title):]) or
         (_song_parts(file_title)[3] and not _song_parts(title)[3]))
    )):
        title = file_title
    title, artist = normalize_artist_title(title, artist, main_artist, consensus)
    return number, title, artist


def collection_credit_consensus(releases, main_artist):
    """Learn majority orientation from actual collection metadata, not a preset."""
    from collections import Counter
    votes = {}
    main = str(main_artist or "").casefold()
    for release in releases:
        try:
            files = collect_files(release)
        except (OSError, ValueError):
            continue
        for file in files:
            if file.suffix.lower() not in AUDIO:
                continue
            _, title, artist = metadata(file)
            if not title:
                matched = TRACK.match(file.stem)
                title = matched.group(2) if matched else ""
            filematch = TRACK.match(file.stem)
            if filematch:
                filetitle = filematch.group(2)
                _, _, _, filefeat = _song_parts(filetitle)
                if filefeat and not _song_parts(title)[3]:
                    title = filetitle
            if not title:
                continue
            base, _, named_main, feature = _song_parts(title)
            if named_main:
                artist = named_main
            else:
                join = _FT_JOINT.match(artist or "")
                if join:
                    artist, feature = join.group(1).strip(), join.group(2).strip()
            if not (artist and feature and
                    main in (artist.casefold(), feature.casefold())):
                continue
            key = (_song_key(title),
                   frozenset((artist.casefold(), feature.casefold())))
            votes.setdefault(key, Counter())[artist] += 1
    decided = {}
    for key, counts in votes.items():
        ordered = counts.most_common(2)
        if len(ordered) == 1 or ordered[0][1] > ordered[1][1]:
            decided[key] = ordered[0][0]
    return decided



def cue_read(path: Path):
    blob = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1251", "cp1252"):
        try:
            text = blob.decode(encoding)
            break
        except UnicodeError:
            continue
    lines = text.splitlines()
    current_file, records = None, []
    for line in lines:
        f = FILE.match(line)
        if f:
            current_file = f.group(1)
            continue
        m = re.match(r"^\s*TRACK\s+(\d\d)\s+AUDIO\b", line, re.I)
        if m:
            records.append({"number": int(m.group(1)), "file": current_file,
                            "title": "", "index": {}, "index_files": {},
                            "lines": [line]})
            continue
        if records:
            records[-1]["lines"].append(line)
            q = QTITLE.match(line)
            if q and not records[-1]["title"]:
                records[-1]["title"] = q.group(1)
            z = INDEX.match(line)
            if z:
                index_no = int(z.group(1))
                records[-1]["index"][index_no] = (
                    (int(z.group(2)) * 60 + int(z.group(3))) * 75 + int(z.group(4)))
                records[-1]["index_files"][index_no] = current_file
                if index_no == 1:
                    # The TRACK and INDEX 00 can belong to the *previous*
                    # file, while INDEX 01 belongs to a new FILE directive.
                    # Associate the track with its actual INDEX 01 audio.
                    records[-1]["file"] = current_file
    return {"lines": lines, "records": records, "encoding": encoding}


def cue_image_plan(cue_path: Path, cue):
    """Detect real whole-album images; use INDEX00 boundaries where present."""
    groups = {}
    for rec in cue["records"]:
        if rec["file"]:
            groups.setdefault(rec["file"].casefold(), []).append(rec)
    images = []
    for group in groups.values():
        if len(group) < 2:
            continue
        src = cue_path.parent / group[0]["file"].replace("\\", os.sep)
        if not src.is_file():
            # Legacy CUE references an absent WAV; do not misclassify the
            # already split lossless tracks as a missing whole-album image.
            continue
        if src.is_symlink() or src.suffix.lower() not in AUDIO:
            raise ValueError("Unsafe or unsupported CUE album image: " + str(src))
        ticks = []
        for rec in group:
            idx = rec["index"]
            if 1 not in idx or not rec["title"]:
                raise ValueError("Image CUE lacks INDEX 01 or TITLE.")
            if not cue_index_source_consistent(rec):
                raise ValueError("INDEX00 occurs after INDEX01 in the same audio file.")
            if any(value < idx[1] for num, value in idx.items() if num > 1):
                raise ValueError("Invalid additional CUE index.")
            ticks.append(idx.get(0, idx[1]))
        if ticks[0] > 0 and 0 not in group[0]["index"]:
            # First-track hidden audio before INDEX01 is kept with track 01.
            ticks[0] = 0
        if ticks[0] != 0 or ticks != sorted(set(ticks)):
            raise ValueError("CUE image has an unsafe or overlapping index layout.")
        images.append((src, group, ticks))
    return images



def cue_index_source_consistent(record):
    """INDEX 00 > INDEX 01 is invalid only in the *same* audio file."""
    idx = record.get("index") or {}
    files = record.get("index_files") or {}
    if 0 not in idx or 1 not in idx:
        return True
    prev_file = str(files.get(0) or record.get("file") or "")
    next_file = str(files.get(1) or record.get("file") or "")
    if prev_file.casefold() == next_file.casefold():
        return idx[0] <= idx[1]
    return True


def image_cue_text(cue, new_names):
    """Write a separated-image CUE, keeping INDEX 00/01 and other indexes."""
    def stamp(frames):
        if frames < 0:
            raise ValueError("Negative CUE position.")
        minute, other = divmod(frames, 75 * 60)
        second, frame = divmod(other, 75)
        return f"{minute:02d}:{second:02d}:{frame:02d}"

    out = []
    for line in cue["lines"]:
        if FILE.match(line) or re.match(r"^\s*TRACK\b", line, re.I):
            break
        out.append(line)
    for rec in cue["records"]:
        if rec["number"] not in new_names:
            raise ValueError("Unmapped audio image CUE track.")
        name, start, end = new_names[rec["number"]]
        out.append('FILE "' + name + '" WAVE')
        first = rec["lines"][0] if rec["lines"] else "  TRACK %02d AUDIO" % rec["number"]
        out.append(first)
        idx = rec["index"]
        if rec["number"] == cue["records"][0]["number"] and start == 0 and idx[1] > 0 and 0 not in idx:
            out.append("    INDEX 00 00:00:00")
        for line in rec["lines"][1:]:
            if FILE.match(line):
                continue
            m = INDEX.match(line)
            if m:
                index_no = int(m.group(1))
                relative = idx[index_no] - start
                if relative < 0 or (end is not None and idx[index_no] >= end):
                    raise ValueError("CUE index lies outside generated track.")
                out.append("    INDEX %02d " % index_no + stamp(relative))
            else:
                out.append(line)
    return "\n".join(out).rstrip() + "\n"




def reconstruct_missing_image_cue(cue, cue_path, mapping):
    """Build a playable track-per-file CUE only after exact sector verification.

    This is separate from DiscID edition matching. A 16-track match never
    establishes how an obsolete shared-image CUE represented index-00 audio.
    If per-file PCM lengths agree with original INDEX 01 sector deltas and
    there are no hidden/pregap indexes, the remap is sample-exact.
    """
    records = cue.get("records") or []
    tracks = {}
    for original, output in mapping.items():
        if original.parent != cue_path.parent:
            continue
        parsed = TRACK.match(original.stem)
        if not parsed:
            continue
        number = int(parsed.group(1))
        if number in tracks:
            return None, "Multiple audio files have the same track number"
        tracks[number] = (original, output)
    if not records or len(tracks) != len(records):
        return None, (f"Original CUE lists {len(records)} tracks but only "
                      f"{len(tracks)} separately numbered audio tracks were mapped")
    if any(not rec.get("file") or 1 not in rec.get("index", {})
           for rec in records):
        return None, "Original CUE has missing FILE or INDEX 01 entries"
    names = [rec["number"] for rec in records]
    if sorted(names) != sorted(tracks):
        return None, "CUE and surviving audio track numbers do not match"
    refs = {str(rec["file"]).casefold() for rec in records}
    if len(refs) != 1:
        return None, "Original CUE does not describe one shared image"
    if any(0 in rec["index"] or len(rec["index"]) != 1 or
           any(re.match(r"(?i)^\s*(?:PREGAP|POSTGAP)\b", line)
               for line in rec["lines"]) for rec in records):
        return None, "INDEX 00, hidden audio or explicit pregap requires original image evidence"
    starts = [rec["index"][1] for rec in records]
    if starts[0] != 0 or starts != sorted(set(starts)):
        return None, "Original CUE has a nonzero initial index or non-monotonic INDEX 01 positions"
    try:
        for index, rec in enumerate(records[:-1]):
            expected = starts[index + 1] - starts[index]
            actual = _exact_cd_sectors(tracks[rec["number"]][0])
            if actual != expected:
                return None, (f"Track {rec['number']:02d} has {actual} sectors "
                              f"but original CUE specifies {expected}; pregap alignment unproven")
        _exact_cd_sectors(tracks[records[-1]["number"]][0])
    except (ValueError, OSError, KeyError) as exc:
        return None, "Sample-exact verification unavailable: " + str(exc)
    output = []
    for line in cue["lines"]:
        if FILE.match(line) or re.match(r"^\s*TRACK\b", line, re.I):
            break
        output.append(line)
    for rec in records:
        new_audio = tracks[rec["number"]][1]
        target = os.path.relpath(new_audio, new_audio.parent)
        output.append('FILE "' + target + '" WAVE')
        output.extend(rec["lines"][:1])
        for line in rec["lines"][1:]:
            if INDEX.match(line):
                output.append("    INDEX 01 00:00:00")
            else:
                output.append(line)
    return "\n".join(output).rstrip() + "\n", ""


def normal_cue_text(cue, names):
    out = []
    for line in cue["lines"]:
        f = FILE.match(line)
        if not f:
            out.append(line)
            continue
        key = f.group(1).replace("\\", "/").casefold()
        if key not in names:
            raise ValueError("CUE FILE reference could not be mapped: " + f.group(1))
        out.append('FILE "' + names[key] + '" WAVE')
    return "\n".join(out).rstrip() + "\n"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(2 * 1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def pcm_hash(ff, path, start=None, end=None):
    filt = []
    if start is not None:
        val = "atrim=start_sample=" + str(start)
        if end is not None:
            val += ":end_sample=" + str(end)
        filt.extend(["-af", val])
    p = cmd([ff, "-v", "error", "-i", str(path), "-map", "0:a:0"] + filt +
            ["-c:a", "pcm_s32le", "-f", "hash", "-hash", "sha256", "-"], timeout=7200)
    if p.returncode:
        raise RuntimeError("Decoded PCM verification failed: " + p.stderr[-450:])
    if "SHA256=" not in p.stdout:
        raise RuntimeError("Missing decoded PCM verification hash.")
    return p.stdout.split("SHA256=")[-1].strip()


# Mandatory encoder backends. FFmpeg is used ONLY for decoding WAV intermediates,
# probing and decoded-PCM verification; NEVER for ALAC/FLAC encoding.
_ENCODER_LOCK = threading.RLock()
_ENCODER_CACHE = {}
_FLAC_VERSION = "1.5.0"
_FLAC_ZIP_URL = "https://ftp.osuosl.org/pub/xiph/releases/flac/flac-1.5.0-win.zip"
_FLAC_ZIP_SHA256 = "53f1500f0d6e7c61379d7fee50d4a9f7f504c650009506d9ba015530d76c0dde"
# shortcut: qaac is pinned to 3.07; update the URL and SHA-256 together to upgrade.
_QAAC_ZIP_URL = "https://github.com/nu774/qaac/releases/download/v3.07/qaac_3.07.zip"
_QAAC_ZIP_SHA256 = "1fb3ab4aa81725e2607ac1b31afa0e13d2617ee6eb5900f5070c092f5271cbb3"


def _safe_zip_extract(content, output):
    import io
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.infolist()
        if len(names) > 1000:
            raise RuntimeError("Unexpected encoder archive file count.")
        expanded = 0
        for entry in names:
            if entry.is_dir():
                continue
            rel = Path(entry.filename.replace("\\", "/"))
            if rel.is_absolute() or ".." in rel.parts:
                raise RuntimeError("Unsafe encoder archive entry.")
            # ZIP Symlinks and non-regular file attributes are not followed.
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("Unexpected encoder archive symlink.")
            expanded += entry.file_size
            if expanded > 200 * 1024 * 1024:
                raise RuntimeError("Unreasonably large encoder archive.")
            location = output.joinpath(*rel.parts)
            if output.resolve() not in location.resolve().parents:
                raise RuntimeError("Encoder ZIP attempted path traversal.")
            location.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as src, location.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _fetch_official_archive(url, expected_sha):
    if not url.startswith(("https://github.com/nu774/qaac/releases/download/",
                           "https://ftp.osuosl.org/pub/xiph/releases/flac/")):
        raise RuntimeError("Untrusted encoder download URL.")
    request = urllib.request.Request(url, headers={
        "User-Agent": "Music-Library-Organizer/" + VERSION})
    with urllib.request.urlopen(request, timeout=70) as response:
        data = response.read(40 * 1024 * 1024 + 1)
    if not data or len(data) > 40 * 1024 * 1024:
        raise RuntimeError("Encoder archive empty or too large.")
    if hashlib.sha256(data).hexdigest().lower() != expected_sha.lower():
        raise RuntimeError("Encoder archive SHA-256 verification failed: " + url)
    return data


def _find_encoder_in(root, filename):
    possibilities = [x for x in root.rglob(filename) if x.is_file()]
    if not possibilities:
        raise RuntimeError("Official encoder ZIP did not include " + filename)
    # Prefer x64 architecture when archives contain both executables.
    possibilities.sort(key=lambda p: (
        not any(c in str(p.parent).lower() for c in ("win64", "x64", "64-bit", "64bit")),
        len(p.parts), str(p).lower()))
    return str(possibilities[0])


def ensure_encoder(fmt):
    """Use only refalac64.exe or Xiph flac.exe, isolated from other programs."""
    name = "refalac64.exe" if fmt == "ALAC" else "flac.exe"
    if fmt not in ("ALAC", "FLAC"):
        raise RuntimeError("Only ALAC and FLAC outputs are supported.")
    with _ENCODER_LOCK:
        cached = _ENCODER_CACHE.get(fmt)
        if cached and Path(cached).is_file():
            return cached
        location = DEPS / "encoders" / fmt.lower()
        if location.is_dir():
            try:
                path = _find_encoder_in(location, name)
                _ENCODER_CACHE[fmt] = path
                return path
            except RuntimeError:
                pass
        # Install only official checksum-validated encoders in this tool's
        # isolated directory; an unrelated PATH executable is not trusted.
        if not IS_WIN:
            raise RuntimeError(name + " is required; auto-bootstrap supports Windows.")
        ensure_data()
        url = _QAAC_ZIP_URL if fmt == "ALAC" else _FLAC_ZIP_URL
        try:
            binary = _fetch_official_archive(
                url, _QAAC_ZIP_SHA256 if fmt == "ALAC" else _FLAC_ZIP_SHA256)
            # Atomically publish a complete extracted encoder set.
            location.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="encoder_", dir=str(location.parent)) as d:
                staging = Path(d) / "files"
                _safe_zip_extract(binary, staging)
                candidate = _find_encoder_in(staging, name)
                if location.exists():
                    shutil.rmtree(location)
                os.replace(staging, location)
                installed = location / Path(candidate).relative_to(staging)
        except Exception as exc:
            raise RuntimeError(
                f"Required {name} could not be installed from its official source: {exc}") from exc
        _ENCODER_CACHE[fmt] = str(installed)
        return str(installed)


def probe(probe_exe, path):
    proc = cmd([probe_exe, "-v", "error", "-select_streams", "a:0",
                "-show_entries",
                "stream=sample_rate,codec_name,sample_fmt,bits_per_raw_sample,bits_per_sample,channels",
                "-of", "json", str(path)], 100)
    if proc.returncode:
        raise RuntimeError("Audio probe failed: " + proc.stderr[-400:])
    streams = json.loads(proc.stdout).get("streams", [])
    if not streams:
        raise RuntimeError("No decodable audio: " + str(path))
    return streams[0]


def _lossless_pcm_format(ffprobe, input_path):
    details = probe(ffprobe, input_path)
    codec = str(details.get("codec_name", "")).lower()
    if codec not in _MB_LOSSLESS:
        raise RuntimeError("Lossy source cannot be relabeled as lossless: " + codec)
    if str(details.get("sample_fmt", "")).startswith(("flt", "dbl")) or codec.startswith("pcm_f"):
        raise RuntimeError("Floating-point PCM cannot be converted bit-perfectly to integer ALAC/FLAC.")
    raw_bits = details.get("bits_per_raw_sample") or details.get("bits_per_sample") or 0
    try:
        bits = int(raw_bits)
    except (ValueError, TypeError):
        bits = 0
    if not bits and codec == "flac":
        try:
            from mutagen.flac import FLAC
            bits = int(FLAC(str(input_path)).info.bits_per_sample)
        except Exception:
            pass
    if not bits:
        match = re.search(r"(?:s|u)(8|16|24|32)(?:le|be)", codec)
        bits = int(match.group(1)) if match else 0
    if not bits and details.get("sample_fmt") == "s16":
        bits = 16
    if bits not in (16, 24, 32):
        raise RuntimeError(f"Unsupported/unknown lossless source bit depth: {bits or 'unknown'}")
    rate = int(details.get("sample_rate") or 0)
    if rate <= 0:
        raise RuntimeError("Source sample rate is unknown.")
    return "pcm_s" + str(bits) + "le", bits, rate


def _update_copied_track_tags(path, title, artist, number):
    """Change staged COPY only. Never mutate source, never re-encode audio."""
    from mutagen import File as MutagenFile
    tags = MutagenFile(str(path), easy=True)
    if tags is None:
        raise RuntimeError("Cannot update tags in organized audio: " + str(path))
    if tags.tags is None:
        tags.add_tags()
    tags["title"] = [title]
    if artist:
        tags["artist"] = [artist]
    tags["tracknumber"] = [str(number)]
    tags.save()
    check = MutagenFile(str(path), easy=True)
    if str(check.get("title", [""])[0]) != title:
        raise RuntimeError("Track TITLE was not saved correctly.")
    if artist and str(check.get("artist", [""])[0]) != artist:
        raise RuntimeError("Track ARTIST was not saved correctly.")


def _copy_audio_metadata(src_path, dst_path, fmt, title, number, artist=""):
    """Carry standard and custom metadata through an untagged WAV intermediate."""
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC, Picture
    from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
    try:
        source = MutagenFile(str(src_path), easy=True)
        metadata = dict(source.tags or {}) if source else {}
        raw = MutagenFile(str(src_path))
    except Exception as exc:
        raise RuntimeError("Cannot inspect source metadata: " + str(exc))
    if title:
        metadata["title"] = [title]
    if artist:
        metadata["artist"] = [artist]
    if number:
        metadata["tracknumber"] = [str(number)]
    destination = MutagenFile(str(dst_path), easy=True)
    if destination is None:
        raise RuntimeError("Native encoder output not recognized.")
    if destination.tags is None:
        destination.add_tags()

    # Any Vorbis comment can be represented as a FLAC tag. EasyMP4 supports
    # standard iTunes fields; additional source keys use MP4 freeform atoms
    # rather than being silently dropped.
    additional = {}
    for key, values in metadata.items():
        key = str(key).lower()
        if not values:
            continue
        items = [str(v) for v in values] if isinstance(values, (list, tuple)) else [str(values)]
        try:
            destination[key] = items
        except (ValueError, KeyError, TypeError):
            if fmt != "ALAC":
                raise RuntimeError("Cannot preserve FLAC metadata field: " + key)
            additional[key] = items
    destination.save()

    artworks = []
    if isinstance(raw, FLAC):
        artworks = [(pic.data, pic.mime, pic.type, pic.desc) for pic in raw.pictures]
    elif isinstance(raw, MP4) and raw.tags:
        for cover in raw.tags.get("covr", []):
            mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
            artworks.append((bytes(cover), mime, 3, "Front cover"))

    if fmt == "ALAC":
        target = MP4(str(dst_path))
        if target.tags is None:
            target.add_tags()
        for key, values in additional.items():
            tag = "----:com.apple.iTunes:" + key
            target.tags[tag] = [MP4FreeForm(v.encode("utf-8")) for v in values]
        if artworks:
            target.tags["covr"] = [
                MP4Cover(data, imageformat=(
                    MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG))
                for data, mime, _, _ in artworks]
        target.save()
    elif artworks:
        target = FLAC(str(dst_path))
        target.clear_pictures()
        for data, mime, role, description in artworks:
            picture = Picture()
            picture.data = data
            picture.mime = mime
            picture.type = role
            picture.desc = description
            target.add_picture(picture)
        target.save()
    # Verify tags survived. Audio parity is checked separately.
    check = MutagenFile(str(dst_path), easy=True)
    if title and (not check or str(check.get("title", [""])[0]) != title):
        raise RuntimeError("Output title tag verification failed.")
    if number and (not check or
                   str(check.get("tracknumber", [""])[0]).split("/")[0] != str(number)):
        raise RuntimeError("Output track-number tag verification failed.")
    if artist and (not check or str(check.get("artist", [""])[0]) != artist):
        raise RuntimeError("Output artist tag verification failed.")
    if artworks:
        output_raw = MutagenFile(str(dst_path))
        stored = ([p.data for p in output_raw.pictures]
                  if isinstance(output_raw, FLAC)
                  else [bytes(p) for p in output_raw.tags.get("covr", [])]
                  if isinstance(output_raw, MP4) and output_raw.tags else [])
        if [data for data, _, _, _ in artworks] != stored:
            raise RuntimeError("Album artwork changed during transcoding.")



def convert(ff, input_path, output_path, fmt, start=None, end=None,
            title="", number=0, artist="", ffprobe=None):
    """Decode to PCM WAV, encode *only* with refalac64 or official FLAC CLI."""
    if fmt not in ("ALAC", "FLAC"):
        raise ValueError("ALAC or FLAC format required.")
    input_path, output_path = Path(input_path), Path(output_path)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite output: " + str(output_path))
    ensure_data()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffprobe = ffprobe or shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe required for lossless source precision check.")
    pcm_codec, bits, sample_rate = _lossless_pcm_format(ffprobe, input_path)
    encoder = ensure_encoder(fmt)
    with tempfile.TemporaryDirectory(prefix="MLO_PCM_", dir=str(DATA)) as td:
        wav = Path(td) / "input.wav"
        args = [ff, "-hide_banner", "-v", "error", "-nostdin", "-i", str(input_path),
                "-map", "0:a:0", "-vn", "-sn", "-dn"]
        if start is not None:
            trim = "atrim=start_sample=" + str(start)
            if end is not None:
                trim += ":end_sample=" + str(end)
            args += ["-af", trim + ",asetpts=PTS-STARTPTS"]
        args += ["-c:a", pcm_codec, "-ar", str(sample_rate), "-rf64", "auto",
                 "-f", "wav", str(wav)]
        decoded = cmd(args, timeout=7200)
        if decoded.returncode or not wav.is_file():
            raise RuntimeError("Lossless PCM decoding failed: " + decoded.stderr[-600:])
        if fmt == "ALAC":
            # refalac64.exe is the ONLY encoder allowed for ALAC.
            command = [encoder, "-o", str(output_path), str(wav)]
        else:
            # Official Xiph flac.exe is the ONLY encoder allowed for FLAC.
            command = [encoder, "--best", "--verify", "-o", str(output_path), str(wav)]
        try:
            encoded = cmd(command, timeout=7200)
            if encoded.returncode or not output_path.is_file():
                raise RuntimeError(
                    f"{Path(encoder).name} encoding failed: " + encoded.stderr[-600:])
            output_info = probe(ffprobe, output_path)
            expected_codec = "alac" if fmt == "ALAC" else "flac"
            if output_info.get("codec_name") != expected_codec:
                raise RuntimeError("Native encoder produced incorrect audio codec.")
            if int(output_info.get("sample_rate") or 0) != sample_rate:
                raise RuntimeError("Native encoder changed sample rate.")
            actual_bits = output_info.get("bits_per_raw_sample") or output_info.get("bits_per_sample")
            try:
                actual_bits = int(actual_bits)
            except (ValueError, TypeError):
                actual_bits = 0
            if actual_bits and actual_bits != bits:
                raise RuntimeError(f"Native encoder changed bit depth: {bits} -> {actual_bits}.")
            if pcm_hash(ff, input_path, start, end) != pcm_hash(ff, output_path):
                raise RuntimeError("Source and encoded decoded-PCM SHA-256 differ.")
            _copy_audio_metadata(input_path, output_path, fmt, title, number, artist)
            return output_path
        except Exception:
            output_path.unlink(missing_ok=True)
            raise



def discover(root: Path):
    folders = set()
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [x for x in dirs if not (Path(base) / x).is_symlink()]
        if not any(Path(x).suffix.lower() in AUDIO | LOSSY for x in files):
            continue
        here = Path(base)
        cur = here
        release = None
        while cur != root and root in cur.parents:
            if RELEASE.fullmatch(cur.name):
                release = cur
                break
            cur = cur.parent
        if release is None:
            release = here.parent if DISC.fullmatch(here.name) else here
        folders.add(release)
    return sorted(folders, key=lambda p: str(p).casefold())


def group_disc_releases(releases):
    """One operation for an unambiguous consecutive set of sibling CD folders."""
    releases = list(releases)
    families = {}
    for folder in releases:
        match = re.fullmatch(r"(?i)(.+?)\s+CD\s*(\d+)", folder.name)
        if match:
            key = (folder.parent, match.group(1).casefold())
            families.setdefault(key, []).append((int(match.group(2)), folder))
    group_for = {}
    for family in families.values():
        numbers = [number for number, _ in family]
        if (len(numbers) < 2 or len(set(numbers)) != len(numbers) or
                sorted(numbers) != list(range(1, len(numbers) + 1))):
            continue
        ordered = tuple(folder for _, folder in sorted(family))
        name = re.sub(r"(?i)\s+CD\s*1$", "", ordered[0].name)
        for folder in ordered:
            group_for[folder] = (name, ordered)
    result, emitted = [], set()
    for folder in releases:
        if folder in emitted:
            continue
        name, members = group_for.get(folder, (folder.name, (folder,)))
        result.append((name, members))
        emitted.update(members)
    return result


def source_disc_counts(disc_folders):
    counts = []
    for folder in disc_folders:
        files = collect_files(folder)
        audios = [p for p in files if p.suffix.lower() in AUDIO]
        cues = [p for p in files if p.suffix.lower() == ".cue"]
        parsed, observed = _source_medium_track_counts(cues, audios)
        if len(parsed) > 1:
            raise ValueError("One numbered CD folder contains multiple CUE discs.")
        counts.append(observed)
    return tuple(counts)


def collect_files(path: Path):
    out = []
    for here, dirs, files in os.walk(path, followlinks=False):
        if any((Path(here) / x).is_symlink() for x in dirs):
            raise ValueError("Symlink directory is not supported: " + str(here))
        dirs[:] = [x for x in dirs if not (Path(here) / x).is_symlink()]
        for fn in files:
            p = Path(here) / fn
            if p.is_symlink() or not p.is_file():
                raise ValueError("Symlink/unreadable file in release: " + str(p))
            out.append(p)
    return sorted(out, key=lambda p: str(p).casefold())


def catalog(name):
    m = re.search(r"\[([^\[\]]+)\]\s*$", name)
    if not m:
        return "", False
    value = m.group(1)
    match = re.match(r"^(?:[A-Z]{2}|EU|UK|XE|XW)\s+-\s+(.+?)(?:\s+-\s+\d{4})?$", value)
    return (match.group(1) if match else value), bool(match)


def suggested_output(source):
    raw = str(source or "").strip().strip('"')
    if not raw:
        return ""
    name = Path(raw).name
    if not name:
        return ""
    if name.casefold().endswith(" - sorted"):
        name += " - Organized"
    else:
        name += " - Sorted"
    return str(Path(raw).parent / name)


def worker_limit():
    return max(1, min(64, int(os.cpu_count() or 1)))


def worker_defaults():
    logical = worker_limit()
    return min(4, logical), min(4, logical)


def check_paths(src_text, dst_text, fmt):
    source = Path(src_text.strip().strip('"')).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Source must be an existing folder.")
    if not dst_text.strip():
        raise ValueError("Choose an explicit, separate destination folder.")
    dest = Path(dst_text.strip().strip('"')).expanduser().resolve(strict=False)
    if dest == source or source in dest.parents or dest in source.parents:
        raise ValueError("Source and destination must be separate, non-nested roots.")
    if fmt not in ("ALAC", "FLAC"):
        raise ValueError("Only ALAC and FLAC lossless output formats are supported.")
    if fmt == "FLAC" and dest.name.lower().endswith(" alac"):
        raise ValueError("FLAC output cannot go into a folder named ALAC.")
    if fmt == "ALAC" and dest.name.lower().endswith(" flac"):
        raise ValueError("ALAC output cannot go into a folder named FLAC.")
    return source, dest



# --- Release enrichment. All lookups are read-only; cache under this app only. ---

_MB_WAIT = [0.0]
_MB_UNAVAILABLE_UNTIL = [0.0]
_BARCODE = re.compile(r"^\d{8,14}$")
_DATE = re.compile(r"^\d{4}(?:-\d{2}){0,2}$")
_RELEASE_PARTS = re.compile(r"^(?P<date>\d{4}(?:-\d{2}){0,2}) - (?P<title>.*?) \[(?P<id>[^\[\]]+)\]$")
_ALT_RELEASE = re.compile(r"(?i)^(?:inna|.+?)\s+-\s+(?P<title>.+?)\s+\(?(?P<year>(?:19|20)\d\d)\)?$")
_LEGACY_DATE_TITLE = re.compile(
    r"^(?P<year>(?:19|20)\d{2})(?:[.-](?P<month>\d{2}))?"
    r"(?:[.-](?P<day>\d{2}))?\s+-\s+(?P<title>.+)$")
_MB_CACHE = DATA / "metadata-cache"
_MB_USER_AGENT = "MusicCollectionCleaner/"+APP_VERSION+" (https://github.com/karpuzikov/MCC)"
_MB_LOSSLESS = {"flac", "alac", "ape", "wavpack", "pcm_s16le", "pcm_s24le",
                "pcm_s32le", "pcm_f32le", "pcm_f64le", "pcm_s16be", "pcm_s24be", "pcm_s32be"}


def mb_json(path, ttl_seconds=86400 * 14):
    """Rate-limited MusicBrainz WS2 JSON. Failure never invents metadata."""
    cache_key = hashlib.sha256(path.encode("utf-8")).hexdigest()
    stored = _MB_CACHE / (cache_key + ".json")
    if stored.is_file() and time.time() - stored.stat().st_mtime < ttl_seconds:
        return json.loads(stored.read_text(encoding="utf-8"))
    if time.monotonic() < _MB_UNAVAILABLE_UNTIL[0]:
        raise RuntimeError("MusicBrainz currently unreachable; preserving original release metadata.")
    wait = max(0.0, 1.1 - (time.monotonic() - _MB_WAIT[0]))
    if wait:
        time.sleep(wait)
    url = "https://musicbrainz.org/ws/2/" + path
    last = None
    for retry in range(3):
        _MB_WAIT[0] = time.monotonic()
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": _MB_USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.load(resp)
            _MB_CACHE.mkdir(parents=True, exist_ok=True)
            write_json(stored, data)
            return data
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last = exc
            if retry < 2:
                time.sleep(1.5 * (retry + 1))
    _MB_UNAVAILABLE_UNTIL[0] = time.monotonic() + 180
    raise RuntimeError("MusicBrainz lookup unavailable: " + str(last))


def _key(s):
    s = str(s or "").lower().replace("’", "'")
    s = re.sub(r"(?i)\s*(?:-|[\[(])\s*(?:single|ep|album)\s*[\])]?\s*$", "", s)
    return re.sub(r"[^\w]+", "", s)


_RELEASE_FEATURE = re.compile(
    r"(?i)\s*[\(\[]\s*(?:ft\.?|feat\.?|featuring)\s+[^()\[\]]+[\)\]]")
_RELEASE_FEATURE_BARE = re.compile(
    r"(?i)\s+(?:ft\.?|feat\.?|featuring)\s+[\w .&,'’\-]+$")
_RELEASE_FORMAT_NOTE = re.compile(r"(?i)\s*\((?:Promo|FLAC|ALAC|MP3|WAV)\)\s*$")
_RELEASE_MEDIA_NOTE = re.compile(r"(?i)\s*\((?:Maxi\s+CD\s+Single|CD\s+Single)\)")
_RELEASE_YEAR_NOTE = re.compile(r"\s*\((?:19|20)\d{2}\)\s*$")


def release_feature_credit(value):
    """Return a real featured-credit token from a release heading if present."""
    found = re.search(
        r"(?i)[\(\[]\s*(?:ft\.?|feat\.?|featuring)\s+([^()\[\]]+)[\)\]]",
        str(value or ""))
    return found.group(1).strip() if found else ""


def clean_release_title(value, root_artist=""):
    """Featured artists exist on TRACKS, not on release/folder TITLE."""
    original = " ".join(str(value or "").split())
    if root_artist:
        original = re.sub(
            r"(?i)^" + re.escape(str(root_artist).strip()) + r"\s+-\s+",
            "", original, count=1)
    # Old release source folders may include the barcode/catalog as a final
    # bracket but that is not part of the musical release TITLE.
    last_id = re.search(r"\s+\[([^\[\]]+)\]$", original)
    if last_id:
        candidate_id = last_id.group(1)
        if (re.fullmatch(r"\d{8,14}", candidate_id) or
                re.fullmatch(r"(?i)[A-Z]{0,8}\s*-?\s*[A-Z]*\d[\w .-]*", candidate_id)):
            original = original[:last_id.start()]
    original = _RELEASE_YEAR_NOTE.sub("", original).strip()
    # "Déjá" (acute á) is always a misspelling of "Déjà"; plain "Deja Vu" is left alone.
    original = re.sub(r"(?i)\bDéjá Vu\b", "Déjà Vu", original)
    original = re.sub(r"(?i)\bDeluxe\s+Editon\b", "Deluxe Edition", original)
    original = _RELEASE_FORMAT_NOTE.sub("", original).strip()
    # Digital storefronts use [Music from ...] for the release subtitle,
    # whereas MusicBrainz represents the same note with parentheses.
    original = re.sub(r"(?i)\s*\[\s*(music from the [^\[\]]+)\]\s*$",
                      r" (\1)", original)
    original = _RELEASE_MEDIA_NOTE.sub("", original).strip()
    original = _RELEASE_FORMAT_NOTE.sub("", original).strip()
    original = _RELEASE_FEATURE.sub("", original)
    original = _RELEASE_FEATURE_BARE.sub("", original)
    # Case-correct musical version labels only; keep named artist capitalization.
    original = re.sub(
        r"(?i)(?<=\()(extended\s+mix|radio\s+edit|remix|club\s+mix|extended\s+version)(?=\))",
        lambda x: " ".join(w[0].upper() + w[1:].lower() for w in x.group(1).split()),
        original)
    return picard_small_word_case(" ".join(original.split()).strip(" -"))


def release_title_normalize(title, release_type=None, inferred_single=False):
    """Single/EP designation always lives at the end, except plural Remixes."""
    value = clean_release_title(title)
    if not value:
        return value
    # A plural Remixes release never gets an EP/Single suffix, even if
    # the source says "The Remixes EP" or "Remixes (Single)".
    plural = re.search(
        r"(?i)^(.*?)\s*(?:-|\s)\s*((?:The\s+|Club\s+)?Remixes)"
        r"(?:\s+(?:-|\()?\s*(?:EP|Single)\)?)?$", value)
    if plural:
        prefix, label = plural.group(1).strip(" -()"), plural.group(2)
        return ((prefix + " ") if prefix else "") + "(" + label + ")"
    enclosed_plural = re.search(r"(?i)\((?:The\s+|Club\s+)?Remixes\)", value)
    if enclosed_plural:
        return re.sub(r"(?i)\s*(?:-|\()\s*(?:EP|Single)\)?\s*$", "", value).strip()

    kind = str(release_type or "").lower()
    designated = re.findall(r"(?i)\((Single|EP)\)|\s+-\s+(Single|EP)(?=\s|$)", value)
    explicit = next((x or y for x, y in designated if x or y), "")
    if not kind and explicit:
        kind = explicit.lower()

    value = re.sub(r"(?i)\s*\(\s*(?:Single|EP)\s*\)", "", value)
    value = re.sub(r"(?i)\s+-\s+(?:Single|EP)(?=\s|$)", "", value)
    value = re.sub(r"(?i)\s+(?:Single|EP)\s*$", "", value)
    # "Maxi CD Single" is an edition descriptor plus a release-type
    # designation; retain "Maxi CD" and put only "Single" in the suffix.
    value = re.sub(r"(?i)\((Maxi\s+CD)\s+Single\)", r"(\1)", value)
    value = " ".join(value.split())
    if re.search(r"(?i)\s+Remix$", value):
        value = re.sub(r"(?i)\s+Remix$", " (Remix)", value)
    value = re.sub(r"(?i)\b(?:feat|featuring)\.\s+", "ft. ", value)
    if kind == "single" or (not kind and inferred_single):
        return value + " - Single"
    if kind == "ep":
        return value + " - EP"
    return value




# Reused MusicBrainz DiscID/TOC algorithm and EAC rip-log precedence from
# the project's CUE Corrector - MusicBrainz DiscID 1.3.1.pyw.
_EAC_TOC_RE = re.compile(
    r"^\s*(\d+)\s*\|\s*\d+:\d{2}\.\d{2}\s*\|\s*\d+:\d{2}\.\d{2}\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*$",
    re.M)


def _disc_identity(starts, leadout):
    count = len(starts)
    if not (1 <= count <= 99 and leadout > starts[-1] and
            all(y > x for x, y in zip(starts, starts[1:]))):
        raise ValueError("Not a valid physical CD track table.")
    toc = " ".join(["1", str(count), str(leadout + 150)] +
                   [str(value + 150) for value in starts])
    payload = f"{1:02X}{count:02X}{leadout + 150:08X}"
    payload += "".join(f"{value + 150:08X}" for value in starts)
    payload += "0" * (8 * (99 - count))
    token = base64.b64encode(hashlib.sha1(payload.encode("ascii")).digest()).decode("ascii")
    discid = token.replace("+", ".").replace("/", "_").replace("=", "-")
    return {"discid": discid, "toc": toc, "tracks": count}


def _exact_cd_sectors(audio):
    """Use exact decoded sample counts; never estimate TOC from rounded seconds."""
    try:
        from mutagen import FLAC
        if audio.suffix.casefold() == ".flac":
            obj = FLAC(str(audio))
            samples = getattr(obj.info, "total_samples", None)
            if samples is not None:
                rate = obj.info.sample_rate
                if rate == 44100 and samples % 588 == 0:
                    return samples // 588
    except Exception:
        pass
    probe_exe = shutil.which("ffprobe")
    if not probe_exe:
        raise ValueError("Need FFprobe to calculate exact CD TOC from audio.")
    result = cmd([probe_exe, "-v", "error", "-select_streams", "a:0",
                  "-show_entries", "stream=sample_rate,duration_ts,time_base",
                  "-of", "json", str(audio)], timeout=90)
    if result.returncode:
        raise ValueError("Cannot obtain sample-exact CD audio duration.")
    from fractions import Fraction
    stream = (json.loads(result.stdout).get("streams") or [{}])[0]
    if int(stream.get("sample_rate") or 0) != 44100:
        raise ValueError("CD DiscID requires native 44100-Hz source.")
    samples = Fraction(int(stream["duration_ts"])) * Fraction(str(stream["time_base"])) * 44100
    if samples.denominator != 1 or samples.numerator % 588:
        raise ValueError("CD audio duration does not resolve to exact 75-Hz frames.")
    return samples.numerator // 588


def toc_from_cd_release(folder, files):
    """Prefer authoritative EAC TOC; derive CUE/audio exact TOC only if complete."""
    by_folder = {}
    for file in files:
        if file.suffix.lower() == ".cue":
            by_folder.setdefault(file.parent, []).append(file)
    if not by_folder:
        return []
    found = []
    for disc_folder, cues in sorted(by_folder.items(), key=lambda x: str(x[0])):
        if len(cues) != 1:
            continue  # Multiple disc CUEs in one folder require edition review.
        parsed = cue_read(cues[0])
        records = parsed.get("records", [])
        if not records or any(1 not in row["index"] for row in records):
            continue
        expected = len(records)
        used = None
        for log in sorted(disc_folder.glob("*.log")):
            if log.name.casefold() == "audiochecker.log":
                continue
            try:
                blob = log.read_bytes()
                text = blob.decode("utf-8-sig", errors="replace")
                if not _EAC_TOC_RE.search(text):
                    text = blob.decode("cp1252", errors="replace")
                rows = [(int(a), int(b), int(c))
                        for a, b, c in _EAC_TOC_RE.findall(text)]
                rows.sort()
                if (len(rows) >= expected and
                        [r[0] for r in rows[:expected]] == list(range(1, expected+1))):
                    starts = [r[1] for r in rows[:expected]]
                    leadout = rows[expected-1][2] + 1
                    if starts and starts[0] == 0 and leadout > starts[-1]:
                        used = _disc_identity(starts, leadout)
                        used["source"] = "EAC ripping log " + log.name
                        break
            except (OSError, ValueError):
                continue
        if used is not None:
            found.append(used)
            continue
        # CUE sector timeline, allowing image or one file per track.
        parts, offsets = [], {}
        for row in records:
            name = row.get("file")
            if not name:
                parts = []
                break
            original = (disc_folder / name.replace("\\", os.sep)).resolve()
            if not original.is_file():
                # Historical WAV references may have become FLAC/ALAC files.
                guesses = [x for x in files if x.parent == disc_folder and
                           x.suffix.lower() in AUDIO and
                           extract_number_title(x)[0] == row["number"]]
                if len(guesses) != 1:
                    parts = []
                    break
                original = guesses[0]
            if original not in offsets:
                offsets[original] = 0
                parts.append(original)
        if not parts:
            continue
        try:
            base = {}
            cursor = 0
            for path in parts:
                base[path] = cursor
                cursor += _exact_cd_sectors(path)
            starts = []
            for row in records:
                name = row["file"]
                path = (disc_folder / name.replace("\\", os.sep)).resolve()
                if not path.is_file():
                    options = [x for x in parts if
                               extract_number_title(x)[0] == row["number"]]
                    if len(options) != 1:
                        raise ValueError("Ambiguous historical CUE track.")
                    path = options[0]
                starts.append(base[path] + row["index"][1])
            used = _disc_identity(starts, cursor)
            used["source"] = "CUE with sample-exact audio duration"
            found.append(used)
        except (OSError, ValueError, KeyError):
            pass
    return found


def discid_release_candidates(folder, files, barcode=""):
    toc_data = toc_from_cd_release(folder, files)
    if not toc_data:
        return [], []
    # Matching multiple discs is intersection of release IDs; not union.
    lists = []
    details = []
    for toc in toc_data:
        params = urllib.parse.urlencode({"toc": toc["toc"], "cdstubs": "no", "fmt": "json"})
        page = mb_json("discid/" + urllib.parse.quote(toc["discid"], safe="") + "?" + params)
        ids = {str(r["id"]) for r in page.get("releases", []) if r.get("id")}
        lists.append(ids)
        details.append(toc)
    intersection = set.intersection(*lists) if lists else set()
    # All matching candidates are retained; never silently choose one
    # from several physical editions with the same DiscID.
    return sorted(intersection), details


def _disc_editions_by_medium(candidates, toc_data):
    """DiscID must match the actual count/order/track-count of CD media."""
    if not toc_data:
        return list(candidates), []
    accepted = []
    rejected = []
    for rid in candidates:
        details = mb_json("release/" + str(rid) +
                          "?inc=recordings+discids+release-groups+labels+artists&fmt=json")
        media = details.get("media", [])
        if len(media) != len(toc_data):
            rejected.append((rid, f"medium count {len(media)} != {len(toc_data)}"))
            continue
        compatible = True
        for physical, expected in zip(media, toc_data):
            if "cd" not in str(physical.get("format") or "").lower():
                compatible = False
                break
            count = physical.get("track-count")
            if count is None:
                count = len(physical.get("tracks", []))
            if int(count or 0) != expected["tracks"]:
                compatible = False
                break
            listed_discids = {
                str(row.get("id") or "") for row in physical.get("discs", [])
            }
            # When MB exposes the disc IDs on the selected medium, require
            # the actual local DiscID among them, never a neighbouring disc.
            if listed_discids and expected["discid"] not in listed_discids:
                compatible = False
                break
        if compatible:
            accepted.append(details)
        else:
            rejected.append((rid, "CD format, per-medium track-count or DiscID mismatch"))
    return accepted, rejected



def _valid_gtin(value):
    """Check 8/12/13/14-digit GTIN check digit; numeric catalog != UPC."""
    value = str(value or "").strip()
    if not value.isascii() or not value.isdecimal() or len(value) not in (8, 12, 13, 14):
        return False
    digits = [int(ch) for ch in value]
    total = sum(d * (3 if i % 2 == 0 else 1)
                for i, d in enumerate(reversed(digits[:-1])))
    return ((10 - total % 10) % 10) == digits[-1]


def _source_medium_track_counts(cues, audios):
    """A two-image CD rip is not a two-track release: count CUE tracks."""
    if not cues:
        return (), len(audios)
    counts = []
    try:
        for cue_path in sorted(cues, key=lambda p: str(p).casefold()):
            records = cue_read(cue_path)["records"]
            numbers = [int(record["number"]) for record in records]
            if not numbers or numbers != list(range(1, len(numbers) + 1)):
                return (), len(audios)
            counts.append(len(numbers))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return (), len(audios)
    return tuple(counts), sum(counts)


def _catalog_key(value):
    """MusicBrainz displays e.g. BETA 021 while source may use BETA021."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _source_cd_region(release_name):
    """Return source-supplied CD region, not a substituted MB release country."""
    matched = re.search(
        r"\[(?P<region>EU|UK|XE|XW|[A-Z]{2})\s+-\s+[^\[\]]+\]\s*$",
        str(release_name or ""))
    return matched.group("region") if matched else ""


def _legacy_date_and_title(value):
    match = _LEGACY_DATE_TITLE.fullmatch(str(value or ""))
    if not match:
        return "", ""
    year, month, day = match.group("year", "month", "day")
    if day and not month:
        return "", ""
    if month and not 1 <= int(month) <= 12:
        return "", ""
    if day:
        try:
            datetime(int(year), int(month), int(day))
        except ValueError:
            return "", ""
    date = year + (("-" + month) if month else "") + (("-" + day) if day else "")
    return date, match.group("title")


def _is_genuine_rip_log(path):
    """A generic analysis .log is not proof of a physical CD."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(8192)
    except OSError:
        return False
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        beginning = raw.decode("utf-16", errors="replace").casefold()
    elif raw.count(b"\x00") > len(raw) // 4:
        beginning = raw.decode("utf-16-le", errors="replace").casefold()
    else:
        beginning = raw.decode("utf-8-sig", errors="replace").casefold()
    return any(marker in beginning for marker in (
        "exact audio copy", "eac extraction logfile",
        "x lossless decoder", "dbpoweramp cd ripper", "dbpoweramp release"))


def _release_catalog(detail):
    return [str(row.get("catalog-number") or "") for row in
            detail.get("label-info", [])]


def _matches_catalog(detail, catalog_number):
    token = _catalog_key(catalog_number)
    return bool(token and any(_catalog_key(v) == token
                              for v in _release_catalog(detail)))


def _release_medium_matches(detail, physical, expected_audio_count, source_medium_counts=()):
    media = detail.get("media") or []
    if not media:
        return False
    if physical:
        formats_ok = all("cd" in str(m.get("format") or "").casefold()
                         for m in media)
    else:
        formats_ok = all("digital media" in str(m.get("format") or "").casefold()
                         for m in media)
    if not formats_ok:
        return False
    observed = []
    for medium in media:
        count = medium.get("track-count")
        if count is None:
            count = len(medium.get("tracks") or [])
        observed.append(int(count or 0))
    # Never claim a specific digital edition when the 2-track candidate
    # actually has 3 or more tracks, or when the count was not supplied.
    if sum(observed) != int(expected_audio_count) or not all(n > 0 for n in observed):
        return False
    if physical and source_medium_counts:
        return observed == list(source_medium_counts)
    return True



def _known_search_medium_conflict(entry, physical, expected_audio_count, source_medium_counts=()):
    """Fast negative filter ONLY when search response has complete evidence.

    Search entries sometimes omit media track counts and label details;
    those unknowns require a full release lookup, not early rejection.
    """
    media = entry.get("media") or []
    if not media:
        return False
    formats = [str(m.get("format") or "").casefold() for m in media]
    if all(formats):
        valid = all(("cd" in f if physical else "digital media" in f)
                    for f in formats)
        if not valid:
            return True
    counts = []
    for medium in media:
        count = medium.get("track-count")
        if count is None and medium.get("tracks"):
            count = len(medium["tracks"])
        if count is None:
            return False
        try:
            counts.append(int(count))
        except (ValueError, TypeError):
            return False
    if sum(counts) != int(expected_audio_count):
        return True
    return bool(physical and source_medium_counts and
                counts != list(source_medium_counts))


def _mb_catalog_search(catalog_number, physical=None, audio_count=None, source_medium_counts=()):
    """Try indexed exact catalog, then spaced prefix-number equivalent.

    Search results are always verified against concrete labels/medium later.
    """
    lookup = str(catalog_number or "").strip()
    queries = [lookup]
    spaced = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", lookup)
    if spaced.casefold() != lookup.casefold():
        queries.append(spaced)
    unique = {}
    for index, query in enumerate(queries):
        url = "release/?" + urllib.parse.urlencode({
            "query": 'catno:"' + query.replace('"', "") + '"',
            "fmt": "json", "limit": "100"})
        matches = mb_json(url).get("releases", [])
        for entry in matches:
            rid = str(entry.get("id") or "")
            if rid:
                unique[rid] = entry
        # A catalog may have a Vinyl entry without the Digital one until
        # the spaced form (e.g. BETA 021) is searched. Continue only when
        # available search metadata disproves every existing candidate.
        if unique and (physical is None or audio_count is None or
                       any(not _known_search_medium_conflict(
                           row, physical, audio_count, source_medium_counts)
                           for row in unique.values())):
            break
    return list(unique.values())


def _release_title_similarity(source_title, candidate_title):
    """Compare title variants without ignoring real remix/edition qualifiers.

    An optional 'music from the ...' soundtrack note is editorial metadata,
    not a separate recording. A matching base title with one such note
    absent may be considered a strong match, but differing notes are not.
    """
    source_text, candidate_text = str(source_title or ""), str(candidate_title or "")
    direct = difflib.SequenceMatcher(
        None, _key(source_text), _key(candidate_text)).ratio()
    soundtrack_note = re.compile(
        r"(?i)\s*[\[(]\s*music from the [^\[\]()]+[\])]\s*$")
    base_source = soundtrack_note.sub("", source_text)
    base_candidate = soundtrack_note.sub("", candidate_text)
    if ((base_source != source_text) != (base_candidate != candidate_text)
            and _key(base_source) and _key(base_source) == _key(base_candidate)):
        return max(direct, 0.95)
    return direct


def _deluxe_title_base_match(source_title, candidate_title):
    """An explicit Deluxe Edition may be indexed under its base album name."""
    match = re.fullmatch(r"(?i)(.+?)\s*\(Deluxe(?: Edition)?\)", str(source_title or ""))
    return bool(match and _key(match.group(1)) == _key(candidate_title))


def release_identity(folder, files, default_artist="", allow_network=True,
                     source_name=None, disc_folders=()):
    """Physical DiscID + barcode corroboration, then actual edition metadata."""
    current = source_name or folder.name
    source = _RELEASE_PARTS.fullmatch(current)
    date = source.group("date") if source else ""
    title = source.group("title") if source else ""
    ident, bracket_cd = catalog(current)
    source_region = _source_cd_region(current)
    audios = [p for p in files if p.suffix.lower() in AUDIO]
    cue_files = [p for p in files if p.suffix.lower() == ".cue"]
    source_medium_counts, expected_track_count = _source_medium_track_counts(
        cue_files, audios)
    rip_logs = [p for p in files if p.suffix.lower() == ".log" and
                p.name.casefold() != "audiochecker.log" and _is_genuine_rip_log(p)]
    # A physical rip may lack either CUE or LOG. Do not misclassify a CD as
    # WEB merely because one rip-document is missing.
    is_cd = bool(bracket_cd or cue_files or rip_logs or disc_folders)
    album, artist, tagged_barcode = "", default_artist, ""
    if audios:
        try:
            from mutagen import File as MutagenFile
            meta = MutagenFile(str(audios[0]), easy=True)
            if meta:
                album = str((meta.get("album") or [""])[0])
                artist = str((meta.get("albumartist") or meta.get("artist") or [artist])[0])
                tagged_barcode = str((meta.get("barcode") or meta.get("upc") or [""])[0])
        except Exception:
            pass
    if not title:
        alt = _ALT_RELEASE.fullmatch(current)
        title = str(album or (alt.group("title") if alt else current)).strip()
        title = re.sub(r"\s+\(?\d{4}\)?$", "", title).strip()
        if alt:
            date = alt.group("year")
    legacy_date, legacy_title = _legacy_date_and_title(current)
    if legacy_date and not date:
        date = legacy_date
    if disc_folders and legacy_title:
        title = legacy_title
    elif legacy_title and not album and not source:
        title = legacy_title
    if disc_folders:
        source_medium_counts = source_disc_counts(disc_folders)
        expected_track_count = sum(source_medium_counts)
    title = title or album or current
    # An 11-digit numeric catalog like 88883792232 is not the UPC
    # 888837922326: validate the GS1 check digit before barcode lookup.
    source_catalog = ident if ident and not _valid_gtin(ident) else ""
    barcode = (tagged_barcode if _valid_gtin(tagged_barcode) else
               ident if _valid_gtin(ident) else "")
    title = clean_release_title(title, default_artist)
    feature_hint = release_feature_credit(current) or release_feature_credit(album)
    # Source explicitly labels a Maxi CD Single/CD Single. This is reliable
    # release-type evidence even if an exact online pressing is unresolved.
    declared_type = ("Single" if re.search(
        r"(?i)\((?:Maxi\s+CD\s+Single|CD\s+Single)\)", current) else "")
    result = {"folder": current, "title": title, "date": date,
              "feature_hint": feature_hint,
              "root_artist": default_artist,
              "catalog": source_catalog, "barcode": barcode,
              "source_identifier": ident, "physical": is_cd, "country": source_region,
              "source_region": source_region, "musicbrainz_region": "",
              "country_provenance": ("source-supplied-region" if source_region else ""),
              "release_type": declared_type,
              "selected_release": "", "metadata_verified": False,
              "edition_date": "",
              "notes": [], "track_count": expected_track_count,
              "source_medium_counts": list(source_medium_counts),
              "discids": [], "lookup_sources": []}
    if not allow_network:
        result["notes"].append("Metadata lookup not attempted.")
        return result
    try:
        disc_candidates = []
        disc_data = []
        if is_cd and cue_files:
            try:
                disc_candidates, disc_data = discid_release_candidates(folder, files, barcode)
                result["discids"] = [x["discid"] for x in disc_data]
                if disc_data:
                    result["lookup_sources"].append("MusicBrainz DiscID/TOC")
            except Exception as exc:
                result["notes"].append("MusicBrainz DiscID could not resolve: " + str(exc))
        # Barcode lookup is always attempted where known, independently
        # of DiscID. Leading zeroes are tolerated only in identity checks.
        barcode_entries = []
        if barcode:
            url = "release/?" + urllib.parse.urlencode(
                {"query": "barcode:" + barcode, "fmt": "json", "limit": "100"})
            barcode_entries = [x for x in mb_json(url).get("releases", [])
                               if str(x.get("barcode") or "").lstrip("0") == barcode.lstrip("0")]
            result["lookup_sources"].append("MusicBrainz barcode")
        chosen = None
        if disc_candidates:
            # Discard mismatching 2-CD / 1-CD editions *before* reporting
            # ambiguity. The local TOC is the authoritative disc structure.
            filtered, rejected = _disc_editions_by_medium(disc_candidates, disc_data)
            if rejected:
                result["notes"].append(
                    f"Discarded {len(rejected)} incompatible DiscID edition(s) by medium/track counts.")
            possible = filtered
            if barcode:
                confirmed = {str(x.get("id")) for x in barcode_entries}
                possible = [r for r in possible if str(r.get("id")) in confirmed]
                if not possible:
                    result["notes"].append("No DiscID edition also matches the source barcode.")
                    return result
            if len(possible) > 1 and result.get("catalog"):
                cat_matches = [entry for entry in possible if
                               _matches_catalog(entry, result["catalog"])]
                if cat_matches:
                    possible = cat_matches
                    result["lookup_sources"].append("Exact DiscID + catalog")
            if len(possible) > 1 and source_region:
                country_matches = [entry for entry in possible
                                   if str(entry.get("country") or "") == source_region]
                if len(country_matches) == 1:
                    possible = country_matches
                    result["lookup_sources"].append("Source region + DiscID")
            if len(possible) != 1:
                result["notes"].append(
                    f"{len(possible)} structurally matching DiscID edition(s) remain "
                    "after catalog and source-region checks; no arbitrary selection.")
                return result
            chosen = possible[0]
        else:
            # Known exact catalog is authoritative for BOTH digital and CD.
            # Previous builds searched catno only for physical CDs and then
            # wrongly reported existing digital releases as nonexistent.
            entries = barcode_entries
            using_catalog = bool(not barcode and result.get("catalog"))
            if using_catalog:
                result["lookup_sources"].append("MusicBrainz exact catalog")
                entries = _mb_catalog_search(result["catalog"], is_cd,
                                             expected_track_count, source_medium_counts)
            elif not barcode:
                if not (title and artist):
                    result["notes"].append(
                        "No DiscID/barcode/catalog and artist/title pair for lookup.")
                    return result
                search_title = clean_release_title(album or title, default_artist)
                # EP/Single is a release-group type, not necessarily part
                # of the concrete MusicBrainz release title.
                search_title = re.sub(
                    r"(?i)(?:\s+-\s+(?:EP|Single)|\s*\((?:EP|Single)\))$",
                    "", search_title).strip()
                query = 'release:"' + search_title.replace('"', "") + \
                        '" AND artist:"' + str(artist).replace('"', "") + '"'
                result["lookup_sources"].append("MusicBrainz artist/title")
                url = "release/?" + urllib.parse.urlencode(
                    {"query": query, "fmt": "json", "limit": "100"})
                entries = mb_json(url).get("releases", [])
            # Search results are cheap; full release detail requests are
            # slow/rate-limited. Compare likely titles *before* fetching
            # details. Exact catalog tolerates mix/EP spelling differences.
            preliminary = []
            seen_ids = set()
            for entry in entries:
                rid = str(entry.get("id") or "")
                if not rid or rid in seen_ids:
                    continue
                seen_ids.add(rid)
                similarity = _release_title_similarity(
                    title, entry.get("title") or "")
                if disc_folders and _deluxe_title_base_match(
                        title, entry.get("title") or ""):
                    similarity = max(similarity, 0.95)
                threshold = 0.60 if using_catalog else 0.82
                if similarity < threshold:
                    continue
                # MusicBrainz release search can already include per-medium
                # format/track count and label fields. Reject incompatible
                # vinyl/CD candidates here to avoid unnecessary full
                # release lookups; verify again after retrieving the chosen
                # concrete edition.
                if _known_search_medium_conflict(entry, is_cd, expected_track_count,
                                                  source_medium_counts):
                    continue
                # An incomplete search label is UNKNOWN, not a mismatch;
                # the full concrete edition will supply authoritative labels.
                indexed_catalogs = [x for x in _release_catalog(entry)
                                    if _catalog_key(x)]
                if using_catalog and indexed_catalogs and not _matches_catalog(
                        entry, result["catalog"]):
                    continue
                preliminary.append((similarity, rid))
            preliminary.sort(key=lambda pair: (-pair[0], pair[1]))
            compatible = []
            rejected_media = 0
            rejected_catalog = 0
            rejected_count = 0
            for similarity, rid in preliminary:
                # Correct MusicBrainz release lookup includes. Detailed
                # lookup is only used on preliminary candidates.
                detail = mb_json("release/" + rid +
                                 "?inc=release-groups+labels+media+artists&fmt=json")
                if using_catalog and not _matches_catalog(
                        detail, result["catalog"]):
                    rejected_catalog += 1
                    continue
                if barcode and detail.get("barcode") and (
                        str(detail["barcode"]).lstrip("0") != barcode.lstrip("0")):
                    continue
                media = detail.get("media") or []
                formats = [str(m.get("format") or "").casefold() for m in media]
                format_ok = (any("cd" in f for f in formats) if is_cd
                             else any("digital media" in f for f in formats))
                if not format_ok:
                    rejected_media += 1
                    continue
                # A source with N separate tracks must match an N-track
                # concrete digital release (not just album title/catno).
                if not _release_medium_matches(detail, is_cd, expected_track_count,
                                               source_medium_counts):
                    rejected_count += 1
                    continue
                compatible.append((similarity, detail))
            if not compatible:
                reasons = []
                if using_catalog and not entries:
                    reasons.append("No MusicBrainz catalog search results")
                if rejected_media:
                    reasons.append(f"{rejected_media} candidate(s) have the wrong physical/digital medium")
                if rejected_count:
                    reasons.append(f"{rejected_count} candidate(s) have a different track count")
                if rejected_catalog:
                    reasons.append(f"{rejected_catalog} candidate(s) fail exact catalog matching")
                if not preliminary and entries:
                    reasons.append(("Catalog" if using_catalog else "Barcode" if barcode else "Artist/title") +
                                   " candidates did not pass title, media and identifier checks")
                result["notes"].append(
                    "No compatible concrete MusicBrainz edition: " +
                    ("; ".join(reasons) if reasons else "no candidates passed the identity checks"))
                return result
            if len(compatible) > 1 and abs(compatible[0][0] - compatible[1][0]) < .015:
                result["notes"].append(
                    f"{len(compatible)} compatible MusicBrainz editions are "
                    "indistinguishable by catalog/title/media/track count; no guess.")
                return result
            chosen = compatible[0][1]
        rid = str(chosen.get("id") or "")
        if not rid:
            return result
        details = chosen if "label-info" in chosen else mb_json(
            "release/" + rid + "?inc=release-groups+labels+media+artists&fmt=json")
        physical_media = [str(x.get("format") or "").casefold() for x in details.get("media", [])]
        if is_cd and not any("cd" in x for x in physical_media):
            result["notes"].append("DiscID candidate is not a CD concrete edition.")
            return result
        if not is_cd and not any("digital media" in x for x in physical_media):
            result["notes"].append("Barcode/title candidate is not a WEB concrete edition.")
            return result
        actual_barcode = str(details.get("barcode") or "")
        if barcode and actual_barcode and actual_barcode.lstrip("0") != barcode.lstrip("0"):
            result["notes"].append("MusicBrainz barcode conflicts with source barcode.")
            return result
        concrete_date = str(details.get("date") or "")
        if _DATE.fullmatch(concrete_date):
            result["edition_date"] = concrete_date
        labels = [str(row.get("catalog-number") or "").strip()
                  for row in details.get("label-info", [])]
        cats = [x for x in labels if x.casefold() not in ("", "none", "n/a", "[none]")]
        if len(set(cats)) > 1:
            result["notes"].append("Multiple catalog numbers attached to exact edition.")
        catalog_number = cats[0] if len(set(cats)) == 1 else ""
        release_group = details.get("release-group") or {}
        first_date = str(release_group.get("first-release-date") or "")
        if _DATE.fullmatch(first_date):
            result["date"] = first_date
        else:
            result["notes"].append("Earliest worldwide release date missing.")
        result["feature_hint"] = (result["feature_hint"] or
                                  release_feature_credit(details.get("title")))
        concrete_title = clean_release_title(details.get("title") or title, default_artist)
        # A valid two-disc structure proves the matching deluxe edition,
        # even when MB labels that concrete release simply "Arc".
        result["title"] = (title if disc_folders and _deluxe_title_base_match(
            title, concrete_title) else concrete_title)
        result["catalog"] = catalog_number or result["catalog"]
        result["barcode"] = actual_barcode or barcode
        result["release_type"] = str(release_group.get("primary-type") or "")
        if is_cd:
            country = str(details.get("country") or "")
            if re.fullmatch(r"[A-Z]{2}|EU|XW|XE", country):
                result["musicbrainz_region"] = country
                if source_region:
                    # MB release country is NOT proof of pressing country.
                    # A source-labelled EU edition must stay EU, never GB.
                    result["country"] = source_region
                    result["country_provenance"] = "source-supplied-region"
                else:
                    result["country"] = country
                    result["country_provenance"] = "verified-release-territory"
            elif not source_region:
                result["notes"].append("No documented CD release region.")
        result["selected_release"] = rid
        result["metadata_verified"] = True
    except Exception as exc:
        result["notes"].append("MusicBrainz metadata lookup failed: " + str(exc))
    return result



def digital_date_precision(date, physical=False):
    """A January 1 date on DIGITAL is only a year placeholder."""
    date = str(date or "")
    if not physical and re.fullmatch(r"\d{4}-01-01", date):
        return date[:4]
    return date


def release_folder_target(info):
    title = release_title_normalize(
        clean_release_title(info["title"], info.get("root_artist", "")), info.get("release_type"),
        inferred_single=(not info.get("release_type") and not info.get("physical")
                         and info.get("track_count") == 1
                         and not re.search(r"(?i)\b(?:album|remixes|the remixes)\b",
                                           info.get("title", ""))))
    date = digital_date_precision(info.get("date"), info.get("physical"))
    ident = info.get("catalog") or info.get("barcode") or ""
    if not date or not _DATE.fullmatch(date):
        info["notes"].append("Original release date unverified; cleaned fallback used instead of legacy folder name.")
        return _sanitize_windows_name(title or clean_release_title(info["folder"], info.get("root_artist", "")))
    if not ident:
        info["notes"].append("Release identifier unverified; cleaned fallback used instead of legacy folder name.")
        return _sanitize_windows_name(date + " - " + title)
    if info.get("physical"):
        # MusicBrainz stores Europe as XE; TRRNT folder names use EU.
        country = "EU" if info.get("country") == "XE" else info.get("country")
        if not country:
            info["notes"].append("CD pressing country not verified; cleaned provisional folder used.")
            return _sanitize_windows_name(date + " - " + title + " [" + ident + "]")
        suffix = country + " - " + ident
    else:
        suffix = ident
    edition_date = str(info.get("edition_date") or "")
    if (_DATE.fullmatch(edition_date) and edition_date[:4] != date[:4]):
        # Keep the initial worldwide date first and the concrete CD/WEB
        # reissue year last, without changing the actual edition metadata.
        suffix += " - " + edition_date[:4]
    candidate = date + " - " + title + " [" + suffix + "]"
    clean = _sanitize_windows_name(candidate)
    if clean != candidate:
        info["notes"].append("Windows-disallowed punctuation normalized in destination title.")
    return clean


# --- Genuine auCDtect engine, embedded and hash-verified. ---
# Original 2004 auCDtect v0.8: Oleg Berngardt, Alexander Djourik.
# Original bundled Readme: "This program is free software; you may redistribute
# it freely as long as you do not charge for it." This project is free of charge.
# Keep upstream Readme next to the extracted executable for attribution.
# Binary was recovered from the user's earlier Audio Checker v1.2.0.pyw and
# statically examined as a PE32/x86 console executable. No approximations.
# The archive contains ONLY the original executable and Readme; both
# are allowlisted and SHA-256 verified before extraction and execution.
_AC_NATIVE_RESULT = re.compile(
    r"This track looks like\s+(CDDA|MPEG)\s+with probability\s+(\d{1,3})%", re.I)

_AUCDTECT_ALLOWED = {
    "Codecs/Analyzer/aucdtect.exe": "efe47eec21c33431e7fceea4b171b8a15a729e3adcda967ee0fc165a6a41adba",
    "Codecs/Analyzer/Readme": "6dfebdef58614151cf3ff009fb2ad6212affc643325637c46d379188a5d499fd",
}
_AUCDTECT_REFERENCE_ARCHIVE = (
    '{Wp48S^xk9=GL@E0stWa8~^|S5YJf50q_1$O9KQH000080Pq1$UBYPF-z^*g002M&02}}S07GwNWn*(ML2hAed3t4XFJ'
    'X0KWOQX?bS`ChW$e8TSX9;aKYoA_Mjf3|vCycdnv9gX7^oPSgP~ATf}&EPVo_09Q9;)V4H^)pVU%0mvNE-@u9X#)*NbH'
    '~AUgO?Y6&`HSX5(J`7XXB|FzcM=d2mR`+NT1=lgs9|DGqF$8*+R`)%!g_RIQw&OYO9cUCDOilXS?Uq^?c)F|T5s{Eh-n'
    '&4mW%RlR_tm?k)ikhIbZC7OGJ@AA%|M5rfe|+Y{=6hy7^2nnF=DY7TKVJBV`GH5w$rC1-AAU6V-s^ky>S2*(?3{J}+n0'
    'J(RjU7HUE5eWpYD~FzvKOSd*zE1_m9f2NbjtiNB0jZUxxd{2kyzke4TAeAFC*7K_SXZvnM5~x)#M4)H5hdQL2L!rBO$^'
    'XTm@>f#3=ftwz}-`a@Cpu2hAJIQR>pt4W4Un%?ABf2%22NmTwX{DGb3pbJM|UvTg20=PH4C)-sW6lfUynH44H`p0u;7R'
    '*$X)Ty%VIcgv9AM}RxdXY@YodrE%4yMd>4@~D${`&jt@2|hV{{H&=>+i3>zyALE`|IzozrX(e`uqR&-;}A2(<L4GgT^S'
    '1qXotXgQiUNeRoh%Z1sj2)7O`rN4WR+)hAO7=EBRT=3(f;puA;qV-(*mpP~#oY^yhkL{IE1J6X_Y>J&A4l@ALsIZ_NWY'
    '%S*L>#OA76vvUWlZBVRVXjS5?sN3A!0oM?f@I}Bd#|-{t3i4C`m&vceILx8;`{JtEJa`DDhRQ*1v@t8b%4ovm?piWe+1'
    '-}>8rFq+o8BgQyk4@`y5B7+6ycud$z?;IPyzu;M50$oXHl;gO+sPMPS|YDTYtYU}EX|g8V#FU6PVl1&Mr#hp5U2gM3HZ'
    'pe_SMO!CbEI~?t3Nk?JLgV~dO{R0hK{|CcJ&O21A7W+dRbt)A58b~EYmdJ^>j2mYxTNOkh%haSPV~u6+h)~ph4;Pq?Ws'
    '4x>NVY^LBwNhJ^5-FRpRLGpgJLY5E9IL^#<IsjwzZp{?BPs5?AYNOa=xQuGB!2MVt!Dc;T!T3JqWOL*cXW9N6xZD6bvq'
    '%VKA1}gUyaiOC;nv@q0%HX3E4&6MZLtl$i<}jsKZt8SY54n2aC&>d3Z4#_p{Bp;zolUo6y<p0`MApstO&6xz4~jM@c7w'
    '}m)wQRJWr7NcT`TCTD5W2`*Q67P%~XZ%mHWq97Qf-y>Z2B<PAi^%XnFY1DDFh9=mH5i%(hJsnwICc&BCgJBNE)6-+c1h'
    'lB&5F4{t4}WuAK9_8lQ;<WC0k5$LOtE`Azj%%7!m=R{ii*>^5E{Phb-xN=~!4b7B=)}zb2L5(9zK`ZN~JwZ1r(<Iwdbk'
    'tFwnzrweAz)~bNNNmKK5K{#t1dmX2Jd(>f5I3O=Z8*-Ztss%g?(i8_g#v!Mi%ZVa;zE4GX@1)Y5g(uy`ilk?33D|R{>4'
    'n|xK{M<jcY!&MJ~QmkVZ1#EgIs@JO}$#p-B5U5j24`P!Eh~@j6vUeH8>1|yS3mT4AyJGi!o@`f_f@S3!bLAZ_PWdweTk'
    '&mZk-pFqp;dr}PmID!ylZojdT2l`xOWT(E2yOE=(<8K-mfPS41TcB{D^kjF8_;25W$n4WiTqpB`I_3e?4DG?bH^BOhvG'
    '*pkXIBqvXA<H%OI4UI0F)juShjI$Em}n{|(J>_+%1PDK{Xy*=m+E=a3YL2#EqT#e)R~_!D$Da^Iy_X2GHFrYipiMQxIx'
    'uy1C3)I(q}X-=7y!(Dde5E0<NA*8zAMkEhp=fpT15c^OkO`z!))P`}lCkF4T&fOBEQ}COarU478CY>sHdJIXt@XI>&rb'
    '#CE?Tw*Q1h<Y+}C$RhgY#b~-~NT<(>)-?TvCf4P@_`=_V9eL|MOHy**AQCp$el^}p4xI~8lu47POw9}5l%&L-q%z#emP'
    'kFs!VHb_ZTJzVe1ls2Y7Dw24N!bVv>u1sA#uV+`zlMgPEiVsjt1Wt5F9=`EN5+@P(*~|SI1gQBq%?}X_9c(T}o+T)^-@'
    '@|B6fLF-R5(wGtgF=a-|@V#b1W)y47G72a!Hml|ZN-DNv{%im*+tL-ZXT9poqa}nI0PYt%Yf=f3Q^h)=APm8$@Yzl`(I'
    '6TTY{~0LXS9PwV<KSaB39~KcgLx=iS`EYZ;4~6(Bp;jzVqOSb(qXNQo9K&#6~S3*NhD30B{4$`#U^O7?QBP3H(vr23Q4'
    '0M%%135`n|e*ggR$gqTBkyeg+ZgzIoqcUqIAYC@UGt+Bg;zjj;YcueX+NDm?8hvP2K5o8ahpenL<RDB2wjwFiS8M~}Vj'
    'Xs{g!Ikr4+1z7jla=3sMF}|^9J33(9H90FSF;HBFbrLi-!uPySH6UO1-~Up5U!RfnEu{J;%K8SX^%cB4$@d<N33$ZxxC'
    '$(0$1F=EJOp~$;}TBcvo%&;2fGqRwsrFb%O*hP?%<om_>MpwAY9|v<{KVNJ74(Z*iF98r=WvNEvcYNhp0<n$2oY9*m-H'
    'AdId+xFtoJnq_MOLL!%T|lH#}&_j&YE^xs|BOW8$tDBlD#Ag>Arc)HL21I;k#TLUOFI`%-d%Y&pvj_tm9v}hq&G!dfg2'
    'I%HW3i^J*ep-zSJ$O+zXk{cQ-l(QE(pZYKI#1Ci(PLt`pwojb3xc_5^C<;GQwuImExavntG0xuiiB+=y^vHc3;+3^Ru)'
    'Lp*56OPjMUj$)?Sp=;I}fI6}|BW^%(Shx-Ywxrpp^EG|jC-<A5H3r#WN#v{=_&x%OVPR@Cc3wSMx&R%JT;yB7XE0RP6r'
    'KSlRH`U_HpU{wg=^~zBjyK@aLj`pe=SZ?eUYw=oDP4X(Z1}<+^j;|)g?z6vIH38yZEv4%+x-O>cBDhYO>ik5fbW>_@WZ'
    'Ivr#E9oA@OqhhoDS=Xbvfti*PI`%D97GjGaF~oXAKa4?EN+9`8Yo-oe<#{*g=6DTqr)%DWM!FeYd+`%%om^G3QKvG4F&'
    '!V8(R&t1hy!o~|`?T}#($x~`(@3c9WoEyG@Tbva!Z(RDFhtLVCrt`&5xr0WW}x}RGKS4FW{@4~K|>^Nj=ZO`y_!;Nf`x'
    'J_{s8XV12V_j>MVi@)3kG=00Yl`iN-IU<Ae~$fVoWB&O*<`(=V`Spy!kbEpHbcL)SPP68{2K;c9pAbNuTI!es263nb@%'
    'Evd#=uc?Zq3p*<r&6VYSoE6TR6{Tic=wIqbd2e?yH(*fBSJ<mdQg3Je`KthmF54>MtheXia<*8nBX?coh=b~SC<zuwyf'
    'MuOo<2@S@|`(RUX*zn1En-bgwBR&1qVv`D^9k-bhb~rOS?3oq=_?d?Nr<>1sMx}#gb4`wo%`ThEbc-kTus7>);Zgfd-X'
    '{B89k`W_AEwnAl&XwL;A9&n!{Qb(CDv8;%hb71jxBB7)!nMY(Z?RXp{6idab)N~S__iZR%=SwQ1rutL6h?^#@BuYq&)G'
    '}d6<{69k%m2W90|J(~tNZUtKzNCtQ%sR%db=POJdQn`E-B*Lke%Hn+~^GTRQCJ-u?kTw9$rVZZmzYOl4)Gc!i$ym!`kl'
    'cGG<7B%Sdf;=-y4K{d_%pR*x4K{i~o@rKtO<wC^Pf~;$Y{B46E$A~=K878eZHY)YKWB`?4G+y}xG7{kc*BNm*feMO3A}'
    'k>kJfvFZ9nUwFK?IGvkrTc+C6vc)nI#JlVigxL+Tudp(oA<&5dzvt39A|-fVKF4LIza(&2oKdNkfX(lJ|Se@f@I>YH1j'
    'JntQP+d<Q<g+IjZjCCdaJohrkmK8w-dT&s3i+4bq-kSu;AdT$x)`X)D0CV>6Q})bLI(X!fbDw~nBf{}b?RPq7TJT}#tl'
    '!$5*{9m=;IYI02v5P}=wUl#a@5=Pj$3v1RGs5iy<?)mo~pN}8+?&wf%&|VZbwi1ZHi-(&OTWOxe%&aZ9kiAZF<`;dT@o'
    'nA%f~mMIXReF+&5<ox&Ao?xO$>BAnySJ0r0JLu%0i+)W9Ok!>cdf2+NZBVA|D&^gle4y(bQp|>X)e2Xu?K>bl&*B?>z0'
    'W9Bl-GO7bN}KPtL)n1Bk2r2K)ZikP&@dIO!#Bt1^wCH*mc`<ZcUySbCQyZwYF-ag=^b+-oYQsCVG&S?$uTw@(GEh>iHK'
    'GwrDsg^ZMd4e!gS|69c+f_lVI0;0rq=Bj;PZqY81q*02ivP!&qt)kTX2iReQi7XB4<H>IxE3=E6q7l#NuOp=T5>C}l2B'
    '<wh*i86M;f-{a}F43y1>nm08cX?A%^H{x>bT}(GzD^RmTXz<ol7}_xpcM9t$d=dY+6Y(sz2q&cV791DQ4Ys=Agj#ecu}'
    '_W9g~2>1S%*u~G9x_F{*HOLOu^>aGu9;+i*QBQt@f-IvdDhUk@sBk)8-j|3Rc!EfFAb3M295^=3etL*x7TM4vG~H*0^j'
    '-PGL)P?f%Wpo0<-KdM(0sp7Az&yH$bIw8{78K1ErBFaL)$%pPDnec7CFz!JE1dAiZcyI2JLR>N^#ifKCHnTNZEcL`nR;'
    'm#uSEI}Fiab5+*({<h=zj%_hB9ou#?|BI~8Vq!MTJK$gfwo|86F%?|g?3FZ>?=Wv&85FZ6w>?)J}g`leu&-YoEO&-f<A'
    'gA{0m1m;L8pe^*BXfeTD9aK8u%qmniR6c~6%2RC!O6_jGyBl=m!o&+h73z&%RdqvbtD-sA8dyQyrG_qhg;3VOi<if?Kb'
    'ZPj@*E%9ZWNNE+yq{2{mXjW`K<O!yzDF5_PGJTAH`WTrW>If2bWclaGl6i9c^W>;`6g5w(f1XsCC*40!I_62jW%_ik@w'
    'sbYOrv?8TuV&z0c;pZR&Tco8e7eE`_-If`wD{{-+H?hi-=9ln=#7Ugpmf}mKW;mMHUkp0cE69X;~oUc)QK+RGLB1N0cG'
    'l+b#bBWk$**k!AY|OcFNeW!4B>P$$?9>PtErU<TvDWL&TdiKu<B*B9L2w4MA7K;}oawZ2{e&(TLy=K}=*%kvajg0ie&X'
    't#ij=+9{xG2oq7?U%7yWDNgfM)du-MhJN4)%azs5g8-9s1f``t`P#>c`m<<D9@Nqeym(_<oaHdd@@w=Dd79#GC$QZM-R'
    '^2P)K&{eH_HWVld~+L0us4v*o==EJ(OiticK9?Q*6bbgo;L0fxKRB*--Fw|Mlh9A)VXkHqeD&ToYLRk-JCK3$Tr^eapo'
    '6rlPis*>~px>C}a{B#9RdBHL93qOLMj9>U3^n3imS>B`=|L|?zq<H`E7;lo*KRm)#*TYtuZab4`tQ-eZq3zl+ZG&LhZ@'
    'a=)7t$7KtJAezY^&?m*4I`S+Sbcf7X}+`oxUx^R@WW&gm~%&M~64ezfAotw%_z+o8}yZF=<`X1J@3hbFHNco|tp7B|SV'
    'C9>{0iFymQxKp0=L-WsYXw;p@H@DL0MD>AU)&@MQRYkIA7A+6t5bxVPIvuIg_*#+C8*`WuI0kA9<j7tL4ng?lSshkR=O'
    '~rL1wgdT9U(Nvqlcj@0m)aI8{H-!v0&-xYMM07%b)WSOgQT7`OL~fJz24T*4a7Xp&F$X1+8^JJiwe#c)WPbUYAvb5CfM'
    '336?zC@LaL{<z5@5Q#dI@P7NR2w=0gL`=<`5VCZ$q)K!I&CmJNa=4|W4&y*mt0H~{X5-T=6vdD+msbl(e`6@{V^nq#yt'
    'OhiZbMy{sPk`Ku;eD7~3*E$<Ie%%TfuY~6S(G*#7ZS|IfJ;ntN(KBXe={J~Q$Qi6YMfxAut+D$$?+DbnurWEPx2QAwwL'
    'lM5dhpTSY&+Y{1354Sq>L)sOI}@?B?=6Q2DcKL2s6r_elBSO)`d+jd<iVFLVP^<)kErR?Yg38op**fE5E4*n{XE0aTv!'
    '`P@xF}14tGw6HKQ&+C`iJWj)CS58<2==?Z(He1}OyOvH&LQ(+7QB1B9)zzi7Ywpw$-w?&SGJ#(&s`ms+gP=$UB`1uKYi'
    'duwkv*td3H^&s<^n?e5vI0Wc9KyBRIWIaSROSB!PBY_UaAurG(U}nhotlRld<^@r1Hmb9W&~qjb1(#gW)A8gn99L!5RB'
    '&_?a~|!^Deejh^J2)oFyp3Jp!M&C$)WlEeLrYJ>8=`sX{P&QcWbJdQu}ui1(zLNw9iSqd+L7f<37*q)hju#*+}?Nww~;'
    'ZQcYZ&!c#(dXLrQu|{~T0M-D_#dxgo9;>x^6IEU@``r))yg{tLqF9xqJQWqHZ1z-CsdB2PVv#Dxdn%Txvei?uLdepjif'
    'T0~-BVGc$`PIl7s<_AJjGbCr?{A|6?Cnl>ms@?qw5N~R@1eHu9&}hi!i-?VwkdjgD_p0BxNvNugYM$NtMC$2vr8t&8iH'
    'hM+sRqJw}ZJ)8kbcOt-3XmZuo2_7r2Ko?<;+O>~W*tC_A*bd8~FJYBH_c<foS=g;*}_HUFuugci-s*F9a%GmR&j6JW)*'
    'z+LUYJ0$twz<+v&cqZd7^Su*M@<Q>$x~%qCZI+6YS;wUf(+KuHJ+|kx~9@KovvAQ&7o@^U9kjck;z!O6o6OrHt-Iu&0E'
    'oTZQhKYB59(Uw>EEU-VE1TzYVQW-*g0L8TyUhrmmt=MHKb8Ut|wY0dyfuIf_Q(J4KpQH+jvy_^##jy~eU@gK@hA|8Ah;'
    'B?Gu=_LrjH4Obj5nMjTSxvd}gNEqdrhf&@ocy*=+mF+BybS&H$&Y2c&j0nsX{)b$_GFPO3E^}b6$Uo!?k-04XxuODdS^'
    'khqCv!#n=ZXo;75#@?-DIvf|6K8bx#IqiD^%u6^v`7t%$4|uTwyX-vVX4Bz+B0H$fcLL()@F!2j)uqL$2;JSEhfitiW8'
    'EopRY+Jw_n{Gd{Nu9R0RPz`5t%4p%(Ow|mZYQ#_^HBVi8#yo=;&QpxG91?Y6V4N0|KCjb)ST>I>P;Zj97=f|O4<PUi=X'
    'x~eEx-S6OG3UKa=qb?N1G{h^5!DByI{c!7JQ;cs)e|QJ?HsTHXPEqo3ZnE8BF^N=i13RG_K%D3WSITpLj2>*o{T8JIGu'
    'l7lqVy`FRq(^T#P3p-Y+iHKQ0~|T4<@QHgy#C8u1;KC(c990fHyS1Xi{+3QSG_bWs59GGP-Y0>$RC-r}ioJqt+};Z<lo'
    'vt8aSmy~N7D7L{bw!xd#pvE>*Y@=Unqc^KjjcuaXCcoGwZ&s5U+d{D|ez7gytQIxaN3lM?Sf4k`r^X(p*u#FYNdKy_?G'
    ')SY7uya1$XFH%4ytp0_*W6=wwP6y2Yun#j@W(nwYuupgA}-}61VEt6%nFa^`#<osSJsfaD)72@Eo(i2aotnk5$}y-gf$'
    'iIXBu)Z!a2VI~_9T4%_M9=Vl^B<t<i<J32h21}yDn?_#=p6;cE#6b@3_t_@5I)}&w*+(pvY6-o*>=dB%BRRUHu9ILtut'
    'C}M6>$|859F@Sj1_!3~uS=xm%4}z_rZZU68La7yR+Fi#noM2SWa_FWQ|D#{UAS2hT~!v*b!8D<RTj~?vfv9>X6~vobJv'
    'xbyQ<9Gxw4Q8R~FS(Wl>#M7S&Z{QJpK(UAVHCt}2V^y0VzADvRk{S+@&U7T;B6@m*II-&JMtohu8yaAnr6DzkQ7nYF9R'
    'teq<hyKrTxT~(Iab!DktRhHUmlGXLV^#h#D(`RtIto-n7M+Yt~`vh-*2k^20dYT254zSeb){nA2469NR0dZ5a%TuXafn'
    '_hI8-)}RB7~GBvWj$<ikM3kN_VNq1vg`5>zR&@z_$z*7u+N80LYrgFnJ!$Te>xUVUXbISAwW0&1XEl8lilTh(Ra@n<@k'
    'VQmV<qgS2G(4>A{x^mCKg@MQ+i;;pH06MpB_tjyAsCL&1>0uqD!{?l!u1Sq)VG#XhL=3Pi$x=?ynQDFZj4<J+N%_8nZU'
    '!BO+lGD3;W4Bw7@0g>fUe6@T1K-#~2}ldrU#=D}0HeK2@dHnL`6{uIq<UwV>_&tSkSq=9So>6b*%NP1LGm*ZcHbFM_6Y'
    '`vg_sEM)EJ0Nwx>keCz$P1EslA}z1vgb9rN*}uYE$I<0X23Jk{!$N3W1mk{$Eu?ec_F$4m5rd1{)2$Vq!jx??`Qex8u&'
    'c!}OjPt9`7qnFbu*^)B#bK-kTGITXYw1vuEpOGV}&cKvJVy><UNSQ|j3ATB$r9tfuD$`zRp~F^GG<Jl&)KV=vC=udTiP'
    'uI}(5^+18V&nzr3DXD$)+!~tQ2L&L$XHf<As(Qp-Bc2k6J>8-S}V^Tbk&A7aM6`>Jkwx;^Y^;@VL~qNgZU55H`HDMpI0'
    ')FGYjxOR-LOIgXI~;LlxNNz$*Qp<P%;uWCUY(<_x4(zpa8j3zH#M!A=Z(_vrA*Gf8Nl5?SDu_CxGtOmI*?1K#7mqwzd;'
    'vqqmOi(EkpbdC<GZk}V=i$4$G$+hnd|mhCDw@f;j&gC*Eyha?06<zr4R>R9N2R40ZwoD@!efpS$?Xf!Q2Wcvi5PR|I~K'
    'Ua!--2uSZ}9*vGhL*9<l^O&~jw!R!9TU@^oJ})$&TJ5ffC(1Xwi^jH#5pTDBw2nQ6(In4aPL{8MTA%Uzqkr$U?}D;6!#'
    'On+IJzMQ7pGBSNnSEd(UPpICHoG!Z(kBd<)?(&uL6I<=+jJ&MyTF8;_nNN>ZJltf<Y|s1}3gcBv{9rINaIt(uD`dm5M<'
    ')7?^^!dz8iENbWr7O%_);l*wd|iXXPPA|V`94R-A`nXEa<vNcE}zn6%Vsm?GZ|Dr}1WgS@g(`e16QHOIN_ywA#fpry|8'
    '@H>kaEcywD2?h)*S8J&8ez`qyNP6#}|lWEbp>GNgx82Yx`TS61V<$0xAd#N};C}Ulo5}HSAsQ7_UmRBesb&Zxfj9!qmS'
    '!JBx36m&UxSy(jK;<<UfMV$`6U!=V)G7ndA3-Axo-~UA?mD>Z_SZI_@js#@-p`aAI*zZ>#~LP0iQQ>y51Kl+zvMf|tV3'
    'fRn|J+~aJcBGqtN7-rZ;}H(a~W0E-2QOa0K93oc%U~<NTbPzB&!NOj?@`XG3glSwmq@*gwBIjbcH2Li^lshhe=}ch+t='
    '>quL#v!|Wac_Y_5ZZm|OPdHt)*|FKNaaW5oalO+}M(+mFEa8p@^bDMdZl}%-TYqA#>#NfVjR<RvWyq3`9BVMnFAJjceT'
    'j}8;5I}IIW}a=kh6~Ube6x!64}-pk6S>zN#JKd7?v=vF3h8NbwM5r@~lxP=|Y=pn+|v*gPLl+5kv_^H68RuhT`Es3e<W'
    'd!=R|}kW;lk0p<;HClnf>5_8eggNo?8GM90FyI8^#9jC~cU0@Cv<1}o+qZfYmWct~21>keACf;KiDXfY2=thz?*_Ir5U'
    'bTp8$p+}Yp&ng~NEPF;4E6MCLQjV*9||T80LyiKJUWwCXYyG3$mlwZ?$f-vsm>cY(%Vc$Vc}MMDIhY($YwXu)`72CBk{'
    'aJI0ch27>`a_$eG&jLPF|7HYdz6pg(4;yk5LFiNld`n_(n8G@~;O#;S8n5FU<b3&98wY_4EiT`;N~8(}oH;J8t}FK66('
    'XW~ZnxffaT;fZUHKhZJA@YU(E4#*mh;|q`O8t3Ep0$@-+_BHhKS?FQMdKjA6%|nj0p-*D+DvoSRxW^KMeI+^=S-m{$8('
    'q9;cf9tv^YC$-NPtHj13DNUL$SkyuuG{YMedRQy*^U*x-6g%I#U=3+0|4_ZwJD?1j45o;0a;RQG%v~UB=2R?7C@s>OJ('
    'RpkZY@i{fDVMAjY%sXZ9H&UN(|#ktmkYu~ZA{q!cGPY)tJo@KtxlmLCBy;n=KWE-8hNH`O>Lm$RFPM`V~hV77Ar*0#J@'
    'hw=EJkJDKtg$Co;L|b{_NyA_*iOsSt`_v^%W4aLb<_>n2up&avL5Yltg6Qa*}0ZNP!Vhd^=Jq@mrTb{Bpw{M=pbMPF?s'
    'G}oOzDTLmF(g!JkpN-<5q+U_xz@7A`zYeQ<Qh5pU`7Wx{(hds5n+x(zv&F^Wg;y&NL25>HY)ga#mI4TfjKf@XzLmmuC;'
    'fGxN*>_15JLujlX7tSIg#UVt)8PY+T#g;{Kqd|p?u<oyg2;6~;&hcVhiJ<9RMDNS8@Hq|n2DJG@PC3pFK`lDhMV5lLP)'
    'JiC-oJUeQ?cR=Ob!@~q3%#8+GOZWjJqLJzHc#vig0g;FD08ihG4Jo4?Kn*^oFKb(=L))Y@?Ybws<iFQ#;!-8$E+2Y+99'
    'Qni&S?UR)Bwn!cCYEe`Hr&vKC>qIt7N7lz&dt#u^eI)_<|O$PwYeD96yK?}zKZ?i{dly3wub#GOM3`SZQzm*GP$c}_*2'
    '4m%+^KxaFhR`4zhA8w~9;D0)sSP;~ay*RYkRu7;DZpdPhEB|aVH0nxeBgJ;IMy&S8P<}@F9042_eAVk@Dy}VoZcCpl(2'
    'a!*6VOTan+<L_@qKkIy#JB4#3x(A=?2tCTzwxq28?a#}7gYfPlO~L)_xnKy7=-4DW#T`2CjwPf$kU3CbueB?>mcvpOu<'
    '0`nIvSSQYQo1Kf>X+~9T1;vmJ2o>pcq_dUg!|y)v+ScT?r9uNdgFLtEJ-3?x{Aq4@4;8w#_4oA8+N8axKs5$&E_#<D0C'
    'hy`?bkZq3kT8uz&TvH{s+Z*FLwmnOVBLGm~-|LG}CLt(*H+=Ev15<qgIwQVxK(MN-}nbH{^fR-dV80EEQ$p)n0-f?09Y'
    '~$*Y2?-y>`rbaqIH&&TG{mAIEdub0%(wU(~y@tUxKUeZ_2#Zd>(4w57G42NeM1&gh7iCk73bq~0(4bDn^i&(&-oRv}75'
    '=Y%bu1iDQ&Y}(UxQAeYrXhRVbo5yMXODokq01e*9`+yyI<6*r#<^}-eTkc{wRjy56-5=kg2y6l^@dL8$6<Wp_8B-v%~N'
    'ALV36XGCS&Cw>_1oyoNJHK_<WJZrx(wvVdFcE(^V(1N^d!iQS5(@xnyJK9`&T^MK^m=P2MH5@w<qX*XEpqvG^`t9q$z&'
    'XY+3MIZ=eS^m<f#%#e?Ah(sa-)$?99$;tS-qa4fQv?3m__IG3O*}a!cax@bB<$>jjc)Z%*rCIV`G|4zkZ19kDcnTVZOF'
    '|od<zuY8sDnQ45Mu%QD&g#$0wOzhJg|wzz`{N);uTAjW6wi7FAc$!-8|%kv+`Q%tIV&JA>Vp+7nRguYUn9?T+*6X$%3`'
    'L@n&B`fg&j9Z^9h$e8=OtmBKIlpKJ!MERkg$#`!M`R}s0AaD2Ss_;}4zU>p3(S%P*sqYp~2F{({3-SH~N=k40zgtCsg5'
    'za{wj_u-na}Qgce!~9R!Xr59_T6kM*+64#BVK9HHEr^~PKH(nlhqXzxc!{B$zBnOv=>Z<!X;qrj62qM#s}wu@$A;rJS-'
    '=#qMxGp5&+gc81bOqF23mT4H4l;7|qeX%Ra#`OYlR+a7Vk(^a)MAxY&J;!;Z1xwtDlB_3os+u{jy5-ATDEyBe+bJ96xI'
    'WZCZkA<BM-$^Hs%E%rO|-AS{4F<&y;Sh`}EqNEy2ue}m(H3;q8NtxI5?G3l|?hTK&xRcV_b~aeuNvRWSE-SMqW!saI?M'
    'c!0q;Pu)0mxU#T`57xYELS#m#iga4RHZa_6C3zw4m-plsidx=*zF582#Hnth(2oWN6rYB~%gl_i5WeX@2<2VTtY}i|va'
    '6pp5%TzY~=4=F_j8b|)p?{U)ZI{rczA{^m|9x~<Q#(e4u5w>Rz>_ME!}vF*+K_ks>L-o+uG{opQH2vYOD??6YpdT!<bc'
    'L`$ejnj^U4)N^Sw6JsT5(KbAP8<LoLhG6-&osG95R>=pc6{__%kxL|uxCWrGh#kdlt`C5G^k%qp?jQe#DWB?dz}7MQ0l'
    '|(afa_&he61M4wri#4j}rDZhC}!TqMXY`*gE=9E`7ct9^Qudt9`lB!Mo*JuXgB#(^&0JuVR`ANzDDB^kgz#HQM(q}ivZ'
    'yT@fJN}Sa_4<Gi4>z??`JrBQMjlMk*bb64k^__gdJ<ovOe5HdC^Uw%sN078*NkkBa=`^|$?XoX1Q`myxVyo4@B#Oe(6r'
    'Tw3F%*uY@EC}X#|>jiB3-Q%mrTFT26iq<MeR#z6qinMnUwEFv>66<#rXLNU^7T>zn_3MgJjrNI1p?G>48mTbFgM}ux4{'
    'GmK%xJCHVVhU~jN$PZWitDV&7%Qkaf8QhVYlS0Y`l6qihC$zBSlQ8*mJ=@ibS@F=ty*5%7CDVYs6gEZ}B>SvI8KC|}#*'
    'bLG~N66+7&E^oz<`C-V5VdSGg)J0LM!P8-jp5>((QXRIg=qau;Y9I!b`Wo+a59A_q3sk-qp%rmr*I~PN2Bck4A<@d{Rr'
    '3&(sVDj2fyCBYxOr5gY6)7zikBCuG4JSX}0UgcA`NBqwN&7V7QoUr*JgIk4D=m9H-OzoWhAZ&2|bW>$Gt~;WUcB5^bk&'
    'rcUekZi<q<X}%L|2g#aDV+Ewzjwzpj?I7Lr%y6{5n`V1A&Gv3&dpEUgGleY_PD0x$9NkT`ox*Vxz6osy$v!W!8;uu=OQ'
    'yICw41_d6gHvV6wZ`+!R}B+X*6C{3U-5(@&wrp($d7}-C#FJug=H$YYNru4%O@qCA&khtU+iug)J1Oc}d}D3>VWlr*Is'
    '_k3+jDoERzyIIx|<$ryIgc%g6_#p}^_3TILn?Nq`P<>xB~dck&(lAuno9i-GR=UfW5gA{L!N87_R+ru>5!^rk9EGq(Sr'
    '?4eVj76}W!qH(`pHnyv!^Je#DV!Ll_N$e`$zfW*Q#dV5o2L}c4AX4aYqo=w6i59Il52KoFR&e?-xFw_>NVT-n(cbB9Rr'
    'F5ZKtqBuh~xFXuY-`QaDbp*-qg^z1pu<3MXUOMYii{P1MtxNO75zb|l)}9jtxsJ2%)3(xQH3H%Qr|uK5D&2I<jRWOsMX'
    '?(Ul1-O29mSXLC;O<_xSZC#{rba%~e3deQV<|u^|yK8n+IJvuKH-*!>Ykf}P%<kG)?*Tqnb^Kzm9i-F$Cfh->+<mJBYz'
    'OJ9ePnwN&GsIe?LBBc??LN%53;+5*54G4?m>2<-4u?a_?yvg%9Ti0E5#-E(AE_Sr}farIE6ENXnRmkMR~V8uK;WYDJ+B'
    '5M3BB~om&nzgY;%9tt&k>n|o?D_oV*rsg6-Ig)Kd4KBC<ej;8ozw41_lJ=Jw5p2CSDKh94IC->C)yC;p4o-|G<F0-e$9'
    'vWcwl@1;Tc7ycHVcLg4YOl+E59|ghC!G4)pxJHE>^6|y25oLq*kaK7o5IlsZ6Bg=oIzVxD4a-PJ=#s-WP`S@P&myXUQ~'
    'hY6wWkgbF-JC3|(z%1=~SdR!r*(NUx1*>;bleWVnLXm0p_dy)@f<(KzWv<D?ha-Ah}?DIDEP8z&TwqcGV`c@rtGmEw{y'
    '&Pp~@IIWj9wke!RVeDH4oYc=>``3+NGf1uDaJ=h5`g!yHPl3%KUAB^J?ycF}TeG=0^>=S=->0ypx8`3_IGW<AzbPEoTl'
    'EX#d(-%)tCixCDKCu?3a9nf_Du?BQW&4VVpNn>)&GL^S_jhky*TFeMtoP(^F^>5q<3GSabnc$HfnYo$!?>zo>16gRM)v'
    'E3P&5Y{-$sog=t<=IMJw%11p7-joLV&aGFuGox+($ZJd}CW%Zh&qri5MX8wcbCP=5Fci6yokUn2e{)$Pn-K5!WqH$uPa'
    'bhC7P2yRC-4u>CQ9ICX3dfnW{-$sug~M@tQ#jeA*-d4qQQ7Gfmub@0lRk<v@U6m3uo<Lb2WXstH0a#K(O@%3kG@LlNgv'
    'JTKAO#asK5JYehP&xeMH${H-)47X#Gv$IEud&?WS;IA8pU1a59FilhN)zWOpC3o8mJ2X!}lIMR{z~WB&rXK`JPqISJAN'
    'r*$pZ4bq2GF`cQeW_MrB?!IJqUv0mnu%)lo-xQ9f@F=vK!f}1I^}8>PZ@OA3F1fEZzA2p6SDTj<&ZIE*qXJm?r5#5T!E'
    'TUh&eHe>Nx$&6HDEVLb(hfi?kDX|wje}N4&FKpQRjy#2c8Dhx%_g(lKNk7J-7r==f#m%1D1@Scl1e-^M2oo;InLgXb^z'
    'U$}a~(T+I3tQQ3e&jkgm9J@d|qL4ZNu9BDxe`tJkPaezS&-=kvCt(FC80)s~XQ^la$w*MX@FzD+as~B{DaQEj02EF_(6'
    '@v~<h`Cx|&=J3>7_|Gw+P4J;y{Gr_(QB|dpW%~mhi)BPbPb@-`@SB5=yS2>Hvou+@WTKsZ#UUrYG>5xx<f;q;C)HdIoY'
    'bB&YLyVd8JiFoe3bNy2qu_nkA9vV2M26erV9Q0(s7QC|)AZ3DZtT3*@;YVWibQ-$Y2TJ*X4nbY%r1PVxr*5hqv`fH-fK'
    'h!aLSg(Iv1s1xlZ)Cr?TL$LnHGfE=Q2`_y3ia?%4Z6hS|yzKelIRbfJ`CB~NOenKGSVf#*Ga^CPU9LdXd6O#ubrzG&ey'
    'DSdM4e!Bu(sR#Ay2ZIk*BcP4|zsQ<oRLA2Ym(djD9ChBF~vEYfcH|ng1B|a|qcS(g|_8vO6J8L=1k2(>lc(fH(=&`6Eu'
    'U*$;8zj_Zdwsg3@KbErg|3tEp}E)eI=J;Np9tll*6gg~68!cl0mj%?O-LYl=>J0ne30MabZv<4te;hp#)%}8qi(j?U6h'
    'ct!Fen@k$M4DTF-LzgH%`szDq*--e^s54CZht8eZSF=kck6^Oi?cc*Od8LOFkLh@7-5RBaRG#htEV5rB(KsRVGfoEv*_'
    '#15@F65GeRQFuMd?>5ePG91&xbPvNyC7vJ~UO4_V@l=#MNXSp$*f*iOhYG7wo3V)jFpqL2NM<@FL--ZQq>I|5nGRAMEv'
    '%(%~%CXnR~KPRBgVPtbyCq!91JrGfnm+FTotu!wD5M@dyL`iFgAEHDX{SYO2FaC%!Mk31F*VKJ35M_3DtVEPYtJ5D6i1'
    'JnAXtbHoUAw*$lC<8{2}#Dg0+A$*3qK^8)CozFC&EY)c5Q(q!DhYM@BV0VkVKQW!!{t$Wcs-qB$|BS#)JU^O-A+~fi`z'
    '1o4a>Lk=dP4B<|jRD6*K=3_lb(rW1-Jn;Aulb&gS_7|(tva<D{^O(%LjDNyA4%Z5u7`C+bmoIsK0B{ZH1F}C+m(IePQ2'
    '=Pu=0D>e>$sa*ZwRVjl!R8(sqG1#%#xtWxF`oTUWQ;_S*Vx`_6)5uSkvB>d`OSuh;{=K<{)omiA-eXSozSCedLVifYcr'
    '!qSB5nJJqk4AhaSy==uxb56i(C7s6T=nED_{&pS=E?K#>1>X^2FSYqyLo5(x5|U&&?z*=*>999`1_kt2E1{>YK~nUSN|'
    'PyCQ$WFT?`R2zUC#T@iQjxiEBZhJu)CXnO5bt5Hm{N(r>Jq2?7c|EPog!I~bsfZD5?xn5Gey9;y5I@xDqVdeAk@_*7!i'
    'l{!n;AJGV;_JVsh|Cj<6wy#3xD`DQ6NX-J2y(?m=W&lCy?V)KhqrSO*Z%Lgc!wI$B0oG<_bWJVtw{QjH4uC1e<$nV}nt'
    'nGQt{&8WHjPqsAK~YTP?H^|U~Zw`_=(s8O)>h#KF%nQS(a&Bjh>QS2#<7KMN0hZf1^|AH22eP*;M_CZFA!awpui-RRvd'
    '}zqYmjzn%ejg*z;^loNT`AC_U91~~-r7wnN(7rtn$3(9#k#>r(M5a8e?f{$AW{_LnZju%ZEX0V#b}8Z*M2yoTA;;CP7a'
    'l5@#=%GZW3s5#FiV;W<qZ5eLA5;v2OUGMCxZoiB{TE7$u5+_CtxZ)-g&H>js6>`l$P&KT^CwBE?<(UYaeCqV<iT5-Hwy'
    '`^y^yQmns^=3rm4xo>BLIK2}>B%2u_T4`+fA;hr~A%e{UVOj%FB8^`^lqklAA4-gtDA7KB+{XeXdR`qWQR2+?yM_pqcy'
    'D)F>-v$+{mABiWOG04=R4453S0WoK87|^IJ%$ahf+AMpT?&4BcG1SvQk`fKWz`Ba9TfY{!uuypY)Hy2*;%e9G9YBeyHv'
    'icZ%Vup=G1(GfeiBaCb@sA+D52f?Fx(elL7_n>)oa=Wa|9WlxEAr^FDxNr@wHlM=sg@^j1GDT%wjFNG9VdrGo9C6&-bN'
    '*Y0ll=S__?z`Qcl6mvS=O9IvJtf<nl0&|GN-jC>DS2y_^tsWUGV989Hb{|gPbqMx%qCAcrHI_*as<1p&y*Lt%Mt9B)k9'
    'rN=}j`7ba$5{@FiEZ9Dy&ns^tiLPaVJc26s6E-)=ua*>uufoIG}yBM2r}kxmkmt5}X8_?_r4zjxDz5#y$U#qvXmwUh^s'
    'B$KOFjtBY4RV&AD2*&NGTH-F>3R261^B@l${4d{4dGL@wxk}|8MY>Amcnsk4&%GbJ%ke<MwU1zX=mbvrA<A=Dk*-QP{v'
    'ZdrD&+{Wum3C+Y&!>1>h0Jb`la7;gvai3gvR75lp{1ISD_rC@rX^Pr`+Y?cz7fg>xrN|k(3AFF>Tf52$5;4E=P#`%HZd'
    'Jc9$beUb_<eAcpe9Q67ZIv{jZPOs1`}9AWY&>vt}7mm^dzDS^?llwQ!5r%@h+$+T6KBUGlXsyqu{9WVd#Wp{ZtNOd;sw'
    ';aloOL_2jQ)#OxpA{sxit>Dro*LoFbC(x@R5TpxnN4|$C{J;aT&l}UgXB_Oj=uxa(qrc?cX=g917~0#;IC)k`3!scLdu'
    '7~uuaQl`QjkCT$V2bX?>Kn!Cj6&{4r`0_V)^^YbE8u|4@sTt8)D9Zd$I&@rdQ&eh$66d@V=|%dsvO<*BDU4MB3bD96J*'
    'v|N<q390yZ*Wc?d-wjg!Z`h_L%Hs(VzX`Q;!42Qh&*_+sj>g}l>YhGn3;rh6Hv=vB6D?Le;vs&6YP3syXq@B{KX(yr6~'
    '8qVf#F$1QP9uu#9GDA?+kUh#rb^nsNLc#4$4((S*VD&y>9X0038M>wTO>I%qXtpw5#N&BX03!41IA`O5eKRJ6#aBl6V7'
    '(yF~)b=266!3}P#ZBj`gd+1yBI?w5F!_}-Z}8Sz7|<w@_2K6v#t|CiXc)E;}@%6BKFjVi$7Ch0ev`S6fCDYNL2UdX&%z'
    'tMH0JE>^?<tp>$T(hxGFmDeXRhhT9e*WZ`VBY@m(E-W4)eboKyI|h#e)8mKaau+2Z%^Jk^A*9rHB9+V@^3G`pLI^~Z|~'
    '$E8!e8p(4iPS?}DdZlIa9YfjsXbPQcKS7k{p9WY1^zy2t4bEWH}Jx~<d3H@L?c!n}q*aCNvNO0G_?adi{46CxIn;_cHD'
    'Ri4i5k~|&ml#-_#EqS_uXRfIcJY81Ob&{uRy}mA7@N_>s-s8XUbm&XqLS!eNE`XyWrq-XMi*a@0=v;vuoyirz(ILwiz|'
    'oDB99`AWzh5Ufx+@l3D>=HNo^2ZiNB4QG>B1Zx;SYa~4&OldadfWCz>^{LhQptu(|6+NuIzL=Br1@j15743x;xG^b`u='
    'kiBUJGr$fHFB42QH7Hhu?b9Cevn@MY-s~<myPdwm6$PKPQeoo)%M2Mx+iI72o{2bsh!OxxgXl0z>=dLZhUh;G8`@dZ#_'
    '_;66^tv!VM?8xkKPURw?<7b@;7JfVT@+8HB+}KNn=^Mh1rim=%@vQ8+}yqI<zxzOZsO<|$<4i4^Zjjto12?px-d8AqW<'
    ';c=JbK5KV0dZPJhI?1UKg<Zcd(D@#E*hJDmU-)QO+FMe=j~H(vCd;O8PUqa{DL<?98v34ZSA`aT!t=g7A-lh#64KW@&N'
    '-s#i_%{xDCj^>>oH>dA(>SItRZf>mP<_^F4ky&ta+g3zLZmvi8#}$H`oB1!}g}FKM-_4}8(AEE>$ArL>9!jh$ke5?Bo%'
    'AqwI_WVuke3r<0+!Q9b1yqBcsX0ib&{70z0Q&&c)5Z*j2GtR2-o@Za{9m%9-@z#ms5tj0(rTJz!M%6_UGlI0(rUORLRR'
    'ZCIrO@UT#T7wB+T+-n;%)!OLx)*yqB$9Pw^u(pu>1f3jm@;K>fr$9|lg5_qyhtZRNJJEA*ra<@oM?xjx*j|on0<@g&UC'
    '#U~mPNd-EwjJqnVNT9E(JDAOJ8^P>eB5oFPIS;1?)pRrojmhD(Q#!U7gwAlxj6H0lZOZ{uHT1$lU&@O;g|0bT-?0Dh6{'
    '6X#bm1=7Z(wDl0%FKzmpu)zf?*hUHy5ua902iC+uY&t~f>Va3e;%bB*BPqTd)SdAOa*{$Rnwb$`Ckg?Tv9w|*x$Or1_}'
    '+}`N~$52-w4@Yn2{dl;jPA53bfjnIC&60;}9`#g~;NezmxK8qLZ7VNo5<J{J!N&i>!_oNl<KdLR(;Ia9#h-^GoBen=8p'
    'D1(+@MY;IIir(!zD`|u3wKn`GSYjZ;O#U+*>zox>WFR!-w|yFFYKr6Qs4!)sKS{W5SPv!*S}*!QnXY=itnpPi_QqaC9O'
    'DIXFY&smlZhcYX7<l7q__|HKf%!Il2ocwr8XxF3HGP6<4*Va*6Uu_5+mKMs!k2|o_b(&@xTWG4=8jO5_@-}uqTf`c0$c'
    'b(+m8h7@eB{;aN)|vhb2bX0P931p9UH$pDNu5q=(7f~G-)J2B@o$4%f&5!^C;lx}@^2%fX1*i%w_je4mHb=DjH_-D{F~'
    '`~-wX3^qL2OfH}Zd&e^b&sozl4870ACu1fJ3m`?DYaW(nlq#QN43e4x6&oe=!nvCt^Vzpc^@2on5T|M`Xs^KVw_V?X|l'
    'Z1(5hI-Ss<anbb&4Ka@WPG}4Y<lcn6{S;;S0LMFmd;4^JjO5-t&*t7JxVM5E`&^iNvyvZAT$+XA{CGEoe0b*F#NI*S#D'
    '3a3;m5tv{^7^HSpvB?+?&G)m!$|?mZIPHRamP##ZdUzKbU(X6qOQ55Guty>Dh%hyHhL~wNB>V2)Crf5ok$?|204NQ+G<'
    '@v|>ARZ-f$3(g-4?q#qdAkm^p!j9E3Gxi|95Q*y~EPsw}zhELydr_5@-+sWJ;dBQ10<OUP>R{n(jjNslD^sVfIdm}fLx'
    'Hob`iF=#T`tUlzy%mHl=z@DASCF_jas`Qd+uv9jEx5PgBj<O)y^%Xc+#9)L#Jvr<VL)HOy_uUFU2t#Y4iWc8?htWr-Sh'
    'A0F1WYQx1aBVdn1>GxHoc1h<m$ecXmI)z5RV=RTtbFxdz0&k!wKQ+o_uSlLhw{I@Z|*_eR?@ac{Ie6Zh7C(!)7|d$T^U'
    'pbPGewnyULXnQ2??X{sNDg^h|^Kxew+#79A#J%D6gg+9D?3du+77RUmui)S|yjRr)2S-~4ad5O%5C>;E-}7q0!5J@E&;'
    '<uaOEqzDv{VxZ_tuZ^w+asKp1<2A2j|bf(Q--r8!eZ_zvcD1^K!wzCH<$W3;vCkE8^d1xg!4Ush-Pz6Z~7V;_QNdqa}m'
    '*H(D}?e_Ok8c%9(iy4_~~1OK*Y-5wM2Z;^Y5kcxlWQGN>fx5z~oSq1MFV->vHFv+_qF2TDEw-WDGJVx?vBURqbs_|}d%'
    ')7-g?{*{eZiAV38|Kn@w<wp!yAc~Fc(;*OjdvSn)p)mX=G_LlG~P|=%)7~EM#^TI+eZv~5qY;+O)ri<_(8w_wQs5DQ!e'
    'epF8P_4{OId{>pLrdrtSaywblO{rp@omEJ3>cA3o2r-){Q<_R}muy#0AT%M!%fpXZY-LAw3<KF1Q|+n?`KEJ4Ekxjw@Z'
    'B;23x6D&c-{rNt>5~SRp>(eVi%KiC1yAtHwpXZY+LD2oVKDQDi-JkDMD?!x#c|NleB;B9u6DvW~{rNtx5@g+<=hG@d*8'
    'RCYs}f}0pX-w<N!Y0z#XKbLr0q=J(fS{7aLyWda4xA6fj7<?NZ^?Q2|TgC5K)*$WT5}Sxe?aS$mIwlke4DrUW$H>uD{c'
    'rVt8QaTxReHj-^Br7E3W_^_$$?onpxepUVs$0icvPLO&_-na}6m?M_MD@%|iU@Cb6Gq!HdoNsqFgz22RY+5Y4+%;1r8p'
    'OQ<SeM(;L!>@00r_4$Xo5KtqxzQ;_<U<pK_v9;2-Xs{jQ%^qI1%pREEHQZG!xDq%e7AL|VDLs+p9x^_>@V}Ll9KO8?A<'
    'f36eS7vZuZ-A1K2w|{R*mJ?#O2&=5Fe`>NA45Yj@1;g1IA~iI_X`nTWYN`_Pang1PI_V{RAB9r-K7+>yUR%w6TJ32B14'
    'i~Yx(E|@#=8Hl+fpMjXW2mZ0JUNCp3UZ2wib4PnNF?Y0Q6LXgnyYdRb+#NMO(*<)!`z0}Vv|kc)_v@we_e<vP_|si5ce'
    'G~_b4Pm?F?MfdTjvSJ?!|BBbivrso<WQq?HR<__3AgUNHBIs7e3PkV@K;XF?O_G6Jz)2N6u4%u^T$Cs0+r9)=XmTXw4+'
    'XF5dZBy<qIlwmsDaV@GQiF?O_O5o34Ds>WV|vD<#fvt2NDv}O=vM{5Q#c7r26zE&`HBd?tE2gYvi4|iRTjNLbv5EB=_='
    'dJuv$k_ELPY{fqVB|8<UlWYoP<c}B2Fci^NX9NwGImyG?2?$VyWXWSc6zJE*bR4SjNK?cDK~-{yJ%+YBABtel26J-Fk?'
    'rj>OAsyZ#Bk_%#M)FjFinZzjyD(;mFwOt}Mr-I3~jb|DVeAPX8~Z`u|bpDS`i0pZG8O#4i*|v4X`a78kL&jKvi!R<l^c'
    'qKm}_78_Y?VzEUP1O9Wg!=v%{0AZUji2u(P1p4*WQVUMCbjMhI#)Cl<(|yN2qW}KgBL3^#aI38@!q%>r|6QD+$W5gb(9'
    'd<@51JYt48os2Mp|hi{uVOM#|+<Ps{#utslzqI)*h~vgAWW@BJ6J}vIq?8q5kJ$^#AQr6;L+XH!)q*gLKtI--NDg<g(X'
    '47&Hmmg*K%-(=3UY5$&4joA)XGpY^z0U`z}&8RC%Vnl#b(%EwS@sRh@GbYIJT;>XJ~eBXdH)z=8uDZb73(eFuSdD1NTj'
    '>!hcSd*<jzS%XSxn;U{;9cGbZ>a^BGwoLz|M>gD$TMIzpJFU+xrBbp%VWY@+0IMoQ7Kz;<Cnl)x1)GFo?g|<uwh5>It-'
    'g+I9$d@wA@oo$3HV4+Js^A$-ASj!9l%uay^ElWcp~CKSqY*WH?@i6J>eU4{yElEdGzJ<}F`gIQ5}>4wd2>@N&yH7*4-x'
    '{Eu0<7VMwA8^c*Lf40n@Bg45eoG0y@CGE?X<rT>CW>3j2pf#iK$$g{c45A{$@<FAD$wUQ-m4wO?^NP$BiwapRrkE^YF_'
    '*B6(=O+<IPspp>GFH!s#9OqGFr|-YNl9#_D^mdEvIA3)Pujuwdlszei$uh=5tfGye^leS6Y4?Ehni=yOq=8e0@6q@88J'
    '9>XC$BM$4(Y<<=J`%5|&p;iIGFEM9iQ`8je4+gL`c8E)UB^Z$7bh`5KFPPU=;FqeCr%f+pHNzv1@K*YU#OYyI$#fjKll'
    'zj=#Kin5K{)SrI)?c1-Gxjg;>z8dgf?C|zGav1RCE(8f&z6&@#jSn%_=YeLaep86+6mN}xm*jEi%TjENHH<?PCky>7%m'
    '}>ONeJ164?ga^uHc-JN6{*`hSliEl%f(d!~8ZVlt1jokDFo+ndSuq6^S*)Ax05F}F)h$55NYCFF7m=nh<x`@%m!M1SDZ'
    '>NBWChv272$6Ns-dIZ6}NsBJQxT0(B0}=g#FBYAn@e5+#iajTA{Gyj~@+^&CF1M1)t>Ux`Iqf1YcQKcX&cc!Lzpusdi#'
    '}LGJB?ouW8n|SFN&X1+p4+TRa`E*4)fx_*?{90#E0YPjh2g_TRlCu4jR9Bw0_~*8*%)ik5GJ`#xMSwK-PCbIDYYM;v_1'
    '!iOcnHxh<@1Wv!1(IK(9!=I3^tpBuh_d0}+KY#hJn`Hdniz7$zI^@B7VzaX|>P5pqcMdTC0_agEM;foPjTX?Wm8@?WqP'
    'afZq$S034N(N7z{W6YU{KeIF8mYL4$T5lUOyrovT}aMNd~+h_CcZk6^BCWs$a##Li+n=(CPhA>RBlBYw*p_N$a#TpRph'
    '+L3f7)bcCa?Ha#)+o+B~**7TcT8_7<?cvxBvjt0-7oxr&3em8&#ZTe&KNdHoH>_4go+Ul4WqpW+i*2;#@pKhyXP*4C)S'
    '!P*+NjO|^{_O4*dR<dQ)!P?4&zkVxMF8ozj->tg$aQuS!tm%7Ne_314+6HdhR&HA(w{17KtqH_;?%9q{$OGcZt9`Woa='
    'EQsu8;fS5cNYdjo)BxZ#f>U?Jf91PVOT3tD$li!IxyR&(QyoeTJ{eWV!gBOqPo;%H&QK9-{4J__|D%i|@>6ABOP@B5kc'
    'OenF(&6~=FfW*NRela|GBxp7=>JZlqKYvmG>xr9`<H;wI0XB#rvhO7{656BL|J)oY(FNn9T9`qcJUl6^MSJC)o?JU;jv'
    '$lY>v)SGvvUeSgUrt-fX)8dixvZ=W$1jK(HA`sxg7|w_P9%<B5WmcQgT^n2ON)OWgX0&($q&Cp<Cj~poLjMiZCJ@RRC8'
    '^sxV9SBu4S!@Ypdtl8o1o8Ty7)VyPNH8;&MG)ZVPK$S?go%A=Vyd?Qzz&v-TWo@nxyB0pFHN8}zI-uohpK$`ZnLS_u)X'
    'jbyEvwHDS!ak<f4ZVYSVSR2nJBytH>)+Vzym9=TCO=oQ;YqMCJ&DtE+=CU@AwX;~8&)Ndk&Sq^9Yl~T1%GwInR<gE=wF'
    '_Chh_#DZyNtEVS-XOJawYd<HEUO~wuVbs%O$v2ThH1C)^25OBWriFwu!YK*0!*=m9;+B9%Aib)*feVJ8RFe7GIi6Ext9'
    'ET0LtGtTnMVoV5|GjbyEvwHDS!u{N5uF|3VaZ9HoeS!-o&GHX*=o5tF7)@HIci?!LT&0%dWYx7t;i?#WzEnw|z))uk0n'
    '6;&>tzc~>YpYnhkhP0gyO_1hSi79HD_FadwbiU$#o8Lyu4S!@we_rRVC`1cHnMg%Ynxc>VQmX*TUqO4?IG44X6<p-wzK'
    'veYw-YuI(|cW{Ib@-S`%x-SsTIHNY<KJYhi5^Yol2k!`e93#<Mn2Y7cIcq{gO|`wt+g@nl{jks2~=kYUr&r(>=~QsbtZ'
    'h$M*kVAkbFk<@tU{aPY52EF&6P$V^0-%6xHRN`A7+=`^em1p-5sqxK?kBvl9V|vM6A~oi189WO~jnEn*8LZEi&P2v9`G'
    'xldsWE-<@E?)XD6HQ?q{e{At3N_gWBX7+YAla1e}$xmuEzl)HLh8!`xlZLH&uO4q=qbS)(h`be7;OyAk)v5@kJCbNDXS'
    'TAT^%MYf(uJN+?JTnHEWn{V$f6NmAp^U9Bpqaec`4iIUX#WU)^rHRx4~AT^Q>{i>208=QA-m88ZF=Wi;hVO-txizGEZz'
    '4cd>)Q}~t<r0w8c=eNAMoDV?d}W(TYRD3{atTOk1T7!_m?SkGAAL+EHSRq8=0}p$FyE$;8grG2uSrrPevL+ItV%TgDoK'
    's)cOFqmjmgXFnk1<)rs|kVYP{L==es1S@ngXWmDG^6A*ms2LsH|?DK$SxQsb(3e^E(|#r5WDNoqWvcUUDg&Q6{3sw6cQ'
    'K6hLtHEw?5^>LEaxbwYJDyboDKvF~6fTV_O8<HBbZSh=NBG-nb#_Uy()k{+2&T|^6@zQK-vm`YZzJEj|HKaC^wMc4|rd'
    '*ODNsW~oPN<~DkdrTaC8_aZ*zYQ-q5si$M3NfMymnqCHCp$k50#|G_HR$Cq=sx;5w{IVjS(%!)=N@Df8dx(YK*$(i$^7'
    '?QS?i@N@~0nx+_MK8b$RQsUhuM%=Rv0?Q+&4sd39^_Z^j_#<tbxR8m7~SFyH+Td|f~fuzQYiJyi^Qsd5&Gb*VewOd)+$'
    'lBekZQ@pVxD_p2TPxS*<32mYeTJlloEJ!H$a&GuJ$a6M5=o6`&)%3XNsaCLQ!1$u*47azNsS-Jx2vQ^Q_8<Sl%z({MJH'
    '8K<E}PGsU$U4FK$;!jWrd&)k{)i<;6t8AgLk81CknYJRqqdX8@8Kat0u&AxA2b8gir}sUhbkk{WVuBB>!~A(9$$79y#k'
    'j^AJ&zros^M^Z!1`5aE0%W09+kTVNO4LP%r)R3zYk{WU~LQ-SQ&rhC|q{ctPeo;vc+7bk*5nA)3N@~16<6w~_HD+J*qe'
    '^PXau;&Bi&(puwMc4I_C0>FBsHF{Z&OK)`{xb|lca|JzC$XhA=9qnv^A_<%UUEgW{#M3mn1b7-tm)4YS2a_NDbO+1gX('
    'pdwRDdH9o#|ze;M*rYJ}a+7|_>F+96<i6k{X{B@^FYRG*ENe$W~1*sv^9_O@3YRH`oNe$Y+1*suRKvF}NfTV`(btE-tF'
    'BYVRv<yiNX;}noBUy{2hO_}m4QT_C8ss1dQiFU1L25jF^z9%?YHS<2N+UIz6W)@f#s{~qQ%Mb3LNb?tq{fovAAKW9jnO'
    'x)QArJ1ZYGzT#oBDv=5V>WTrQFt<X{L=WBbs0mDG5;IQ|YvYOK2TLzUE!@9~OQEM~Ek#R?WHS*&7lA&ZMxT+HG!7MHWQ'
    'g2k0AR<pQ@#TpjZvgl&5p2Y?hx3bvC;%*k3SoE;i!eT3nJ{AwLc$mfGEVi?FjzvYMi8>bbEE-reu^7%`1dEYUJcuVe(f'
    'J*^)3Fzw-`@w5Gpd(igAALdZhImbo!@oicaZaY_udisy-eiP1-r=kz2%z&K6HKud&xPCdhxsO`=Rsu$uV-CV`O=8vb^|'
    ';uP>j8&TmAuhn(LxnhPIA=XdPg`^fo~>C<HTbXi}ftS>A7t4$Np`EC2%OU|#1&z-tJIKQ&~S)UwhA?H`xU$Accx8(emx'
    '71Xk^ZVMXn)6Fpg!4<eg!4-k3FnvU63(woyO7hO^Bc5x%BRx#-9Gy#)%k7w>b;kw^IH)9v+Deg+P!+FbbiB2e^8y@rLD'
    'bRlg@8LT8rxZO6^+KqVqd&|H@kF{GJ`Gz0s@LmRTX4-;}%CROeUPu$ygY;u1Vu0y@9cmBRU@-W1NS)E;8(VJ_h~mw?Xi'
    'Bc8kGO6T_x-*>9>OOISQzx33F^DEP$^DEQR|2iak5}jY!lM$?qWGy<svc>59$`+&ZTf6y<vC{cneeAI6{66>7{`J!Ny*'
    'lNH>imx1lKO>oe*bm!H`V!-eTL4j>@#$Jr!*PzrSqFKyj696rDd6HSr(U@&E=x=YjbUWLpr}>haXp+U#XqN+I+URfbB)'
    '+cg4o>Bc$_dPdchPzYnf0cu_jP5v3<o=XXf+$9<&pTe0Va>io*u7IJNixZK5DE;_$2x_2Fw&Tq)nUsUIJ+t#gHrSrQr?'
    'Xc?ng4d{*&hLS*PO8qYv|%mV;NsfqxwZxdBIx`+?mMbFzp^KHb5El4yL8j}r=;^cu=<ed{K~eqa@%}t!y&c-onQL+O*p'
    '^V3pD3f_WC*Qb##6YeyzMMo!>V$`c&t)x2NPr>HPli)sL$4D@PwXzjE}U^ZUz*Ul&N{_tfB%s`GpKo_Wtp=l8L>C)GE4'
    '>EGV)FX{Yl`R<tN{Ho(On8z<`6IqMSuWTDSzp`!U{K`>+&aWIL=={<Txe4dj_^amp$~6j|U%5u*ur`;q=={FF<=P<W{0'
    '{AYNOgYY*g@x4jvaJ<<<msxS3XU2esgy$*&?0a-OGPfo!{~eD;|>0?=QdqqB_5F^r7=BM;|)Bw8#tRcis5kROeULww!B'
    'Q!L_aA+R*uxYY95PaxJOha@TUXF1DebZD`<fw{p3S+=|`Y3Uq$u3WLtCTw&1pt>5viQ98fVKmS>Eer4K2oEDv5xf-GKD'
    '_5g-9;xSeq@wdHTY=86Yy~>MGA%m4GA%m4a#W-9D@Qdtzw#NQ^DCb*I=|8~bbh5}QCvbamw?W%+(pp&mAeQ!zvMg!=Xb'
    'ETRds&lvq0xpJ_~eyPwW{IEuG(*%YCZzD|cyhe&sHW&ad2Y(D{`+4m!WG&(QgmeTL4jch}dKO6S+{@Ilr2mAzBIy@Ss0'
    ')BBy>r1M*r^qu-fk6akx{E`<VoZrv9TjogT_wn$(>Ki?&UC3H`qbK%xbbjSNkIt|3HPHE$z6LtK<RA&>mwY7Q{K^)uq8'
    '4ve-{{E_)=~+L>Ki?2Lp|Hjz&*K@d$N(s-OWAO#99w)$@$&<?HAJdeQRTr`bJOMaENU<%-Z9uZRfU~<F=vmD|;QC-?F5'
    'g>Ki@T3Uq!S58tf5(Tn``s{csmcaXPUeWMq0>gW;a{C+w9BlV4*bcro2MzI*pVhoFMEXK2#$fA|SWEN9dOk**f#Y`5nS'
    'j=WIhs9hL^H`k4Vm^xnEY4=Jh{a+SOIfU7v696q78kO(h{eS$E@N>yiz`@M$znB&t5~dIaV?837VBATU~wypjV$hFv57'
    '?wi!Cg+vgl*+5Q~RdJkDY}i|1HWx-ocTQO}}*MH7qREJm;x$)cG>3yV=KMza{hVjPR{EGDvOWigq>R2I`%OlL8Z#Vi)H'
    'S<GQEm&H65XR(;iVgZY@SuA3)n8i{SD_E>#v5LioEG}YkF^kJsT+ZSO7FV)Z&EhH+Ygk;%qKn0P78_XH%3>pnyIE{v(Z'
    'ga3i>)mBSUkkyVHS_G*v{fP7L`yQzbxumG_Yu5F`UH+79&|SvuI&4ip6LaV_1x1F`h;F<+S1*s~7)syr)+STzw7kuw%I'
    '9^oVtNlk4f=^C(2hbGy~xP1XJ3{ImF2Am9l7tWHPkb2}Zm&+c>-KeN*j{WK-;=zg-iTjf1b-s9yxPTphqjC{bEd5gT8<'
    'vmi~Bji0?-c9mukaxYj>*QS<9ehIH$6{+2=k~Q<9O-nhe|MKB|F?GeX+V9K-wv$p^5cS4U4DJAvdhmCmUsF6!s0GJa9G'
    '&o7Z8<Qej-uIVljWeP}J%3irgSx?O4oaF^k1a7SmZwV=<M*WEQO~CbAgMVjPPxEJm{!#iE5pGmDWdMo7`-QzRv$PIMLx'
    'Eb3X*v8b?kj=Qm)#p5g<W^op0%afw9v}z!IlYpNGry9$i8z^=Qh~Cp&^{iw|?lbLE*^-YPZ-z;><feJQsBFoJ`$tcdY)'
    'P`vB3m-_<;;gATQZ{dSCuVU`omNCk}diBH%C;q<b9oEy<|&XnQ=;GOWxf-ut~BdgKN*LY{}eVVS34y{OHqO71GC6f-M;'
    ')(jr?@|H_PQk}V0U3suiQ=eIqwM6xA6o5HM;E&2G(&|Q)(i8<GyvL&Yu&fY5766@8$R>_tmp1SOM$(D@#FibuFT=zh&L'
    '$W37>Vnnt&nb_eHcGbS;E2;ITM~cW?5`wSGSzfeWlO&P=Z>S2ElG?&t+FLMqPwR{wq(-yb1GXRTa0XpY%#JWzpU=LO|m'
    '70uePgf$^OTlpD)>x*2mANY>8|!vL&*`$d=g7yfjj>CDXnMvP!l@whh@5**0WL<`+J8iDXN9<%C!zTO!L%=5moO$=y0_'
    'yktun%BkFReg#Rd3PridmdIX5wnX+ivL#o%Sh-lTC1t-;ZFy|NEVcpJ63?}lu9R#^#}ib-Y__b3Ekm|MJ_}?^<g=*Yo~'
    '-1aM79Km&d-u9sd|lGuP)*~Tg-iiYzh6)kYGzTijlg4OIXPzAY0=4sl1P5OX{vVud*fmjwbDpY{`9JpH|tDTZ&)3Q?ez'
    'izd5b4CDz&v&r7ysVA^q&ExBmeqIr@nIdIiUl`Z-DlYg(1Y)Pu`xXP9cQaTn&wq$U|A(btWXWS3b8Tap0w&dR<+Uq1+k'
    '}KJ2{HdZR*RPgr$=Fv8t8B^0-#WgRY)Ps87nLp9*Z)k8WJ?CTrm-bYkGLpYvL&HEw5n{$)agWDB3p7g;eg7P$Pz4ELKJ'
    'JGS&M8*&0Q~qNVeq3VFy&UWWbG2rc1WO-lnl7_ow#XAlZ`lSAMUuCG}Tak}BDfi(hL}*^+C!d8bRZWM{-al`WAaWK#*d'
    'G`3_&zqyhvd3Wi0l`WCw&Z2S~RJP>r_g-v}Y{`df)~jrZ)E2Q8*^<8dFDsR7NpaCOl`WArRI&}omc&L})mO45WiM@0*%'
    'Dd8Vk+Sal`Xky!Aol-Tk_GGPgS-=wqhl>qMBQ=id#{`C9LHVT&%5UZ3Ek|m2GHb?QU*c6W8Y9+FH2WRxa1a+C!{8%-Z9'
    'uZD;K{)*@T-Kyl=L$(DTa%Udd2;(gupPsx_NQTCR~mPl<lYa_UXNG`$5X)T;Kiql4O+89n7M`=G*&p%6hku8z-TDgQ|E'
    '+LgmNaNblS)0k)EG{9NOZeY8|14`O;@XP2wo<OGg40%V+A41GLT>RQPP>@XUikd8dVZ9()ojBmwxNd0UCZVEb^iIU^Ur'
    '^sfBx(IbJype=P-a$={6Q;vslDpF^i=vR<KyfVik)ESzN^8ViuRNxSYimEUsj+n#ENt*08viMHh?pEH<#XmBmIDceB{U'
    'qKCy67F${Lv3Q8Z!z><WvE2_B`=RAv#?UP4Sv0U{VlkY>2o@t*G_z=7F^a`#7Gqe9V=<n^L>8?qCbO8zVj7F-EM~Hp#b'
    'P##IV|R~n8)HQ7V}vwU~x8!MJyJxSju7ri<K-^vAB@MMJz66aT$xtSzN*5N*1eGT*V@twcHXsLISA8H@~j}D6b{7L;|R'
    'P-u$@=pzhyL@`eOZSv9Lw0QK@eOQuTz)$h7bQ~-7Jmx@6GsQ%ZzsRAfjLMxYm0BX?VwF4x8I`?~n3ZVM^rc96k>du;tD'
    'u9YVQPL^_)ay5IQ2~@piva3QajFsl)b2HJE|dVuv~s@+pyI!r`KAO=N#evP0w`H70;tz--lqa6X&C~jbH6vK0IKQuvSk'
    'uLg<tob3ZP`#I7;hN0hBy=LIA4vunM4#Tz~Nq37}qIbW8<M|DNE!M*^tO!N*kqCDUedS_Dvls&=Zco3A^n0;q_b%U_oO'
    '>a)j>s{rcb(>22-fXb{qs{$zfoh4UD0QLTB1j!LVU6&L59|@p-9Yll>0;pe_^z{-zwVml<l>ln{q)Q){04g@JmsJ9&2?'
    'uk2mjG(%%{{FWKs8vdx?cjQnG3pGC4iz|uoM95(Q~9l09Aa%Fi--hGxt*o^t$==YYQZRnto4js{~LnxrOgb0QFNY*?<5'
    'lswOK#0w~)9WN!mowv{bw<W}tFRv>`txNFmV380)-(zdW=t!$Z(+jfZCh5*Vrc2~0mP@BwTLp%56IqpdWP~M#nrb+<ix'
    'r%-X2mw@5?^_p10QJD<I;#XwZ(a80R}w&7s_SNz0P69JPOg#wYW=sA76DYXd0UnQP;sw|v+f{1-%$O$1W+SBIimt7NrW'
    'JPI&f9H3ZUeOLI5R46auK|-uKUy0BTs+F%>`+{C4043822;{+kM*em`@?a0#HY#5r>WP*1F>O_u<w{GUIl07`0eS)0e&'
    'S*%3>ReQ<K6%s(XZuv<CQ1N>oTQ33BZ-ahR0o2UlLGvVl`eDNNDu9wJ0Rkww5+HzD95XXc0;nPT_NV|#t}qCo<Z6TfDr'
    'lCqR061)$Lm!9HSKKh(-J@(*uFyrP*S^!wKZJAS}p+rlw2q4b=o?K07|a32%zLjivUWl;0U1P3XT9uU4M1F{<5}}wLaD'
    '!BJB$*fRftdtZirQIo2Y8l3D~%QmbdJfwd;qhO;(;wUMkfv)01eDAq=^Hiorvtc_=FB5SRzO=fK>YtvYp&e}}YX0bM#w'
    'K=TKWo;g7XR$V)wFRu5&DtW?7PGdLwH2(bWNj5|7qWH{YZtS28Ecobb_Hu!vbLJFt5{pZ+O@28v9_MI4XoYD+D6vyW^E'
    'H|J*;hEZ7XYitUbiq!>m2d+IH5SV=V$Gb^M0%_+_nuwI<evvo?aYk*qbd*23B-)<&~7hP835jc0A5)E>lNul)-^{iy*|'
    '%?H;dN&xk@{x7O;pbqUBGfV=g%}ZCRZ=h_ee{52Jf#;KI?G2RBMza<H)ZAGk?vns&?%w~X=XI-pRB9!FiX8QsdR}*7Y4'
    'TnPpf)aDtG<C+FtFd<5<p%5?nd>z?(b!n4V3`u=|{Gx=XGV;Y)*>+>b;^JsS-eyj;mMC>&g;laR~^ZR=0<%0P6bzjp}*'
    'b0lvK#O90i_bCdc8>h<xDO_l(v`R^OlH&D`sO11$3)Kgbh9FqVlKln@aysqq>#oRjxpf>Jz{7nL=z2DcWZ=mE8T1ii6y'
    '?S0(_Sq`#GXzk%dsZHl04k>crz(JwPpF=sPy?sk%4r)p?QTws0BYx$ni>h9iuV3X1yEAk%32?naEMDd%-Z9uZRc@zj>j'
    '1SsQ-tzw*il;x)z4d%$!M1k_l&kAW?$^859j@bifjazyvZO2!n$m6Cx(qUdWB9_EI<p#b#jQ$+S7yj?#PUS9`TTTx>sj'
    '+uM4pRs5;WWFS94C4kjL5)2mgj1ysyG?_rmdDq(KOeR?SKKFgTpX8bIv-aL=uf6u#Yp=Ecj@7W>$GQV`=ZyVH2Wnj29M'
    'c`BJ7!2p2TI3)4wQ}|HwDd0LGx2kTMCK})a?UXzppz`!9RqO4wPOO=s@Xpfew^j7wACgb>U1wOH)vEpmZrg2TGR`bfB_'
    'cZM5kQ)V$&&NeAktYm2gU2kLttbR-?9r2Lvv@@tx?d32!knnwppZ&~O-=`HKAR4E!$rSPXHYfe$tlA`R%6lHr;&>y9s&'
    '!*^oK1DA&P(P^n<P+V2y8gtUlQU3{{O;dB)g7po#*@hzD7{^v1GUX~JUIiUL*Gn6(SiEc;{`v{9jM1&=uOT*<qm%T5#5'
    '0ze;7#4K)rbP_7{>4RN+U-8K{4bj}YB~>iySq$r&j9+&OfhnyjBBXP}C+b8Wf<<@?~%<P6la@{KR(4%Bx(y^x%N(m6Rs'
    'Ir+Eb4AeL76+3kY>d*1f<P6kP$L8+Q9jL-WW72^dylj3$cc8wxDJ$tfovpd;Bi(^={BU~Gf%^Dh#of9CweiF2k`9#n(o'
    '+?>10^)iaq14#QESKRx&w9a&-0wR1NEO5Pr7vn>RW~Low@_H`PsEIbO-9mBR4s92TGqMM+d6Ld!ti#pqd8%c3yX&o__U'
    'Or|v*K^XlB^bqDI2H?2<Hfl_`x@Gaeea%EFD5FMzVEy2fi2dbrPDCt1iw&Wkz9jMzrJePE!RtNq&pgU0c>3vBDO4s1%K'
    '<OGB9VoqZqXVV4Zh8Wb);7_B()+h(Q_$yAP;{Vly@L*vu6GWk;{G-j_r(<S<rMT_3i@UW8cIPArJ$WD=&=;EI|Y3=1?@'
    '>e`%=(>6!csQs-&QUDQG+e9ZEqHDd<=VN@t)nC^}F&luJP^DX29C%}GIXQ_#E=G(QEkrJ(au&;==IVG6n^1znPYE=@t5'
    'DQIa5TAqTgO+h^==!O(@V+#5}3i@CQx+MjzPeC6}LARx#LJIm=3fh>0`cu&66tpD;eKG~zn}Yr*1${OJeLe;KMGE>t3V'
    'I*~{cQ^RVhZ|l3VJXFeKQ3OrJ#pW(9RU}SPI&mg1(!A_N1VFDd<27dM*W3QqaK^G@gPErJ#uvbSwp>Gf=wxrlsUJ1+}E'
    '0))X`+1<g%C^HR|K6x5c2&QC!Xq@aZ<=%N&KNea4DhkkXvE`Cqsf3jXz8njlB2W+`sBG?vGkw%-%TUDXl^?$2s{{yyse'
    '7^NvcrLXqAf+}>Z-}h5t?ke44NHe|`>%zUrM=<JJ>l9-eZ`o0Z>Z-8q+{rn>kGmAN4;G=ZD&UNdwWCu*Y?f8SRW1yA1V'
    '>K{+@n~;u)QA?VpNZ^Wzju0oOvVTwnHs7zJ?BU?3vz@oOM}!84&d=!(ex>j)zqvPLjEPy|rAfcaVt`nBgXOM@0tX@PtW'
    'm*6U8N4M8^7ZEvf<e@HHxNLf-ppA6X^RxR6y=VJ3*tnivjp{TY5AtaW<A<g05eI6&at1V>x2@qtwsOc(D+w2LNC}p_-?'
    ')i%JQTtlyun9J!RB1Q1qk)~FR7~3&i00+HnykB%v=jy^~E!7kdr?&psK*cF71u^bn=_?^VD18YqgFOJ{xI!D1`NE>Ikx'
    'tf+I*jV@66>CnJjIH}_uNl%g2eIEh{hX{#g;+bjhUpw~+-H44b^;2PsYT@-C6iD>j!1;1wsuKhC;Y@R=<3>|ErtQUrsq'
    'A5(va`{YHD@mV>S9oi}lJvFU6~nM3eKKCpgd1Pl?D)cW8}KoYwCknmG(~7;rH7e<_w*9=W$1NqCM*ut)+CE04dzv#EYC'
    ';IFR`Bvu2LNl83devY92ZarM5yqy{M9$FX)sXw&4QxTzY<gqYV!hUn+wD#WH~h*5Gp}MpYGFrSnT@0UK<EeY22H(jf~K'
    'g~#&&*-{iZ`$^d<dssQgAa5|RxP)AVzgV5)L*IN&#L4kK!Db_e3y$`NwEF0435^2QXYne2*58BqgfJf$b9FX?v3CG7>J'
    '9a|@TBtm{z|5&t3S7It<Bau(4S`re%s)<07bF!K{FJj5;5I0uBuS8Yw_^(zB{2Ap!l8QpZozsS&$2O3V}&B)8QZ+#^cw'
    'ec4Jc*YZ8R8Jz0xwtX6@VM2_?w@PB|L;}xi(b=h|SuTYEu4Mywr0ABl_)udIc*S-UI?SB@pjn6^Wg^u@q_awzNXqgW+Y'
    '<VZRsGW2av`s!AzBkm=POJMV<djzB<$b@V%=-ytUO!@U_4ha~@K35(ZeRr}CMahPo_sHbxpLAE&|IkBoTkH=VN)9lG0H'
    '{{RQOUE10gE^qzMqzkoO-tiQ)atcOHZswECcx5qz0K9_LVOu#(9X$YzneHjyA+R^E^pL+);_-6S2#(*#o2F`z-PedW;B'
    'g`$}oTxlT33p%Ayw$V+FCfk=cxXl#Y&}Kz(?=Ru7F78Q4A+~=-Tngv+tsaot@*N|fP{aKt@xFTo@Sf<qM}d29<2#T|Zm'
    'pxkcl|@BDY~BE+J2^=ZFBZz02dq`(7G;euGw^zzADuyvm#}={iU%)RiB_Fg1+$p^Z>C$qrD*F4KBI@yvq-6v7z+jR8>}'
    'Zl(|s)K5V9iAYOfo?zmSv&q0z}&evBvDG$B;YyYnNP|*=8m5ui&m5MjG1C&ay^=hR8ELa@}S)@`3OmK`$sFT$__()}L^'
    '}vK8Sq<E1Y=bO;7w`LKPw2!5>W_Z*#EL$Swn4}H5bwfQ_#q8aLi3T(d{iX4Rl$|2T@8fzr#?ZE{63NvbX)1i41gIRKMS'
    'fVD!s}ymA1J;;81?wqRV=tdmoC2o#$Fx4ygREYh6+(-*Kt0zPo>8_e86z@9E#zGtr*v2l_V-OthqWrGKN+_(vcu&vD8('
    'Z?ej7C(z&~ig&8-;lCvMANWh6@iWMNL4OYrVg(9wKo(Y&<5v{)X0TFqB(NCJ1akN%Z^v?ga;d0X?^XIiB|%9xgMyU~ao'
    'YZ#_3JB04fJe23;%ncHK3B?vM(XKIWgTHiv9*j@e(noZlug&F$f$f%avVYF-wPQ3_pJrGZ8nZhuuob*g!~_>*yq-+l?e'
    'qrQTJcJTQY{Zt-!q>}CziKn0pUB)&v!jl(^*{Wi%r#*na(VLv${jzOQ==BZG3T9p;k8B~^l=`Jau3MIF=I8#q7*Q>0Vh'
    'M%HPtA!g|OhCp;)y)AZl8<Bfz)mcr%UZj6Q&&V<XR(4bx;R8^iN)YOKXxAL9;mk*kgA05g23hkR3TGR4T4!xjpAl$-~z'
    'nJWfn2ptL%nqG=MBr+f}dfPr0CD%Ph^I>Rp^PFa}X#IR^}a^#CVWh7Yk~dPi9<4y{(Hf-MIN@T-{&WAB0@0I~ct;ngG@'
    '%kD5A63dutaK}iey16#8@4+X_z@GCq<kX7k2Qhgp&C%{lC++(&q=EG)&*946P<8eG4UJ`tctZp0l^0`}^2AjE=7#Gw)<'
    '*0nU)y%m3MOXWhd|k4gocF@IU1k8f@%B=g8dLo+QJDlVFS+Zl`-TC>66)njU$ht+C-C-p+ce+O``)4v+-Sfs5YWJ3}yE'
    'hb34lzMleUeeLcfOj$Qo+@&l5?*+Wv7`o-_0uwkTEx?pH^S-ym~4#SdkfwhNXM$$31xhtYX^N@5gOJfJ_$clJ?ZPw&Zd'
    'GLCMT6qmlc(ve9=}=K*Es^>JbiC?}oKOj%5U#0L;MJqfuxjsV5SLZE>2-z$V8`|)py&`{RJ*-ZuUYa}FmK!7Vh=fvlZ!'
    'iM0vXH6lt34RpMXZ}7}@?gfELvEUkldu;#myy76Y+K``aAc939m=c#@`J(_&w=hoByz_+I;PS<zxE@Tf|(sv@V($O}=*'
    'a^WWVEKIA*DlfJ`_<tZH#rsJ1TBsw)`Idd<@E|FyBOJSi=(JA2%ouAwzU}zy!TCVMTZKqTJ4pa3={hMLtYdup#e<75c<'
    'Db1mV8!bbFDZXi0d#Tp=f0*zlE-`x+c=VG%%FUcj$ZufPn(?lK=z8QKqI|0iYQ5SL8qyU{)efw<I2PSv{&~K>&LL!@!*'
    '+yvpsfuv(#y0L2rD9Q^m2N|^ngTUIa~<_&OtaBc}aZG@-8^yvY3;^@<Z@bnva+P?)JB1#1ER35#BVfN=jDU|Es>GVetl'
    'tF1QUpg1>4fR5g`5~C-A3jV~V=k&l;KkB2(ZI=FH}vM&h{e`)5kH*P6b58_q;7_4(34DTfgY;Cdo=h5Obm^VoRKz!iU)'
    'ha^2A?Pgj%JbF+pkr!&T&rXehI*()hrmMN;v6XkRArda0e4K8ZVK<-qHs*%iu{ci{I40&2Bb;BDa4#WsMeGx9-95Gvj%'
    '6_?YNcCA;LcMEOf;%{S9DjJw7<&X2JQbY!BicnP+7#0@lIeEnyN}HCzD`a|<v+!J9T?;jt%)<tG)JCGnKaE+S(zz<Vu7'
    'a)sPlxLq7O=xLxB@@yBPy~upsdW(H1RM=2-m6ZbB}SvHQ>)@V%eAkWMKXx%m|6<ifAowK5dQSl&kbz#2$*!Y;%c=la?@'
    'In)DdU2y24w#Cm8ag<1<<8gwb1peq581sdd5{#DmdgX)3X7kG)|<vd<K!;9ik{<H`w%mba@sdix=O@p{4aGxK<#qMIOp'
    'nnJk-ULDS(1y8$vRVQobGbTW5xg`Qs~zF(yp%BQoF^qXAxBC~6Ry9C_}KTfSKKBVyC7%dbL>+>u`a|dk0U+Thvw2(V5&'
    't<3kE`%p^^y<mCM**pp(8{8OK*H80e<2gY?xx0)6zs8Vo21m)di@N`jUuhji2u_n6(yZdUla80Krr_m$!;)tLYPL)mT{'
    'zp8AruP&SQe^a(Rt!&V{Xk}9tEykiv^e5<VR|UHG=6^-Qqk{B;tmllh;}II@dW%`%sF4o@kl>qJ)1-DoOFDEjQq&+6G>'
    '3%SwV2|^q!;3e-<1Ap5~io3L5y!mF@yLys)bFpn<FC~7+ts~iG**)ZLk_t{7ge4Xn~MycvCH!*PA2qOwg>D=g(hP$H#Y'
    '*G*h<}SM6=&8t5B-%@_<#LSOSqVL|h-aKlI&XhBA>;2qTAA$evjx9KBQg;q8*HU*v-`ox0MiCCc{1-uq}NKV)C5Qm`<e'
    'Be=)emaX%P1}FWP{zNK=247`G)-}le`QLUG`f(S0E=d{KxFY9u#FZrW=f+)d(2X_FlK^YS{hXaOOW*k*%FKr>z6JstQC'
    'zTJ(1{s$b>3?PI-$qZ4^1M4qX;0WC3B@LS~^GM@(Dx)4Pi!H5T$uW8{%BbzoCh8^>&{{sC)K2Q;hFTeXEOW~e?H>u@EW'
    'HkDvsgPlVH`v?A2L}4LLRvP${xGi!CyM+`}#5H5GV~b2P1BHi(ss3OA<rvUm4|zNw@?)x)qhg;+yPLl{P_ptN7?Kdz7!'
    'Ks1`^GguXS~g-ZsTZ2m#=O^yCPqCNsEs~tQf<hARTp}c6cDF!%4RQ+e6NnyTJeebz2U-TIm&0iP|I0`=2#j$f(C`jF^S'
    'ZQM4$3L-!Rqlt;duul`dmpxabKd5U%c6b39O@~DMuwvu+BTNb&-CDOPmnw5_MA#q#R1=&}EtW;Fa`pk}UZnqgjEkLa5w'
    'rB|uk?$xL*PT-)-$C5Dvca*+@+j+w?=&kv12mffM=c-$%NV%9qU$DeBs&kf8o8X^kN3zvyvDK!=U8iFg$!T?=#h&~RNT'
    '<}u{7AxEoP7vdIHi3PAnt<DDbN@Si+)Sk4G0G-78qAN=@S<)1<9~P!_P&hlnf3+2M+x2SJeC2^6S(R6JaRLD!%rQ>vJ|'
    '9$2g7Afir^1e0)=hHz1Zw6%xnaP>`Nai|ZRkpaj;cAX=xJlUlX7YM+hv^CC1TZiD6fZrHIk1tJwJhu+Xk0g?L_5@u$8u'
    'AVoU8w<Vm0jK7MaZsqgRXA;w4Pe1&e#a$t*(}~9%Im95oS&_0#ef>n{+9SWsoE`;ySj85)1WPiI!8nAM!>ix#4AosX^f'
    'c$%JZPM@s0q5p;D4a1n<)H-Hmrq-S$RP&}Z)dm6^;TL8fpl{Td<@;pWx^vNe1IkL?H5+U5?5NtMKesIxFVtGl%3NE)uj'
    'W4l`IIZ4*-?b}!iBs@A1$DzqTr9HXX?lnSbnR$O*h5<g{d{!OE*3Kaxn6G}_gRY8bE28j7O7bOh8238Sf>7fwYi3qSF-'
    'ZAE!CUaSOyFc;F3`=E3={A&=gR9Uc@l<sNBH9fh3?y8glEoBVb(r6exKc&ln&b%75Wd-ByJR$;-UzjB@Os*IDK4Zs>@>'
    'o7~@rcP}T;7{G^}mZneCJ&<7WyYMQF8U;(!JB&XG2oG?kw*5WuWLK*+N1?81iTi$WHYs0f>TD|VxIn8<<6kYwEzZIN3}'
    '+W-;mKiU*>^5>v-BDsWiVyu7xqxmYq$qLHbvScOxgJnzT?3U{4*gCvnu87*`OJrdCW-_`qsM{rXf%H?GnAnisus8*3}A'
    'r7+Lm>DL=5#!F#UZdgUZq-Rg`|Aa1`CY<uOAWnj+cqd6Nc)?;y+ZLatnIv_)Njsk80v>@<~4k6v6v><3-9E!Vt2reFVu'
    '>v=B@j19ETeGQkPU5oISL8b<rg@d=Lts1?!X;J!&5Cd&Lw5Ig)+@g%qMDvSEr>mm?;L}XM<6F<8bp@dV=8G6Zat>VS&r'
    'UcF?#(wri}EM4uJ*;Fh3%UC$c^WGS?KvpoMq|7_?}E1)bzjz(CFt)UF=v<)vZ<EK-JV#-U4TkmG;%0O%ypOY{7|*J8Yg'
    'eD6|Q9bs*C(!icNDX}NG#m0&ENACv$_Uh?{JO5A8nxp3Bm|IS7SAU)jhyU?2l}a{k1UZr526#ER4i%2)IZWTQ)V2rfRR'
    'CDiS%!)4fhb(lC_eGcKgAlB*I^-^g2!KL&|&-{;aVH-KkMfM75H(si^^<><R3MN#@+#`I0tQeKJaUR1+$kxlXx99NAw)'
    'LPXs=Bb)d4_%`o>PeVmdDLBplCYdFzV60@HP)0P=K44^5T7>D<CeE*}pD|U^&Yo4m|OcrPlQA>Q<&1hfd?4F0zqW!@$#'
    'rP<uWkCe-V4zEULmCvwvGvlR6`AyajeD;DyPUHAUh0uo_kWY?H%NzsK!|Vt*sW`==nBm&u_QC(_`nFrB^{f}nTIX~QXv'
    '#8b;zEFZG7nS^pR5AOg}ZdPA?4Ix`Ju`GmeSl8YL$B1tji0-~4C3xe4;<9f&>-xBi}9CHh@_4=dnP0=T)04?Iuv>F+tc'
    'u&`i-PR>i1Jk&eZ)BE4da~}@;Oq|)5T?pJ94<qzUFNGP$!;$`;NNPZcZ|;J`2b_E$jCZ4uC3WV50UP}THIof>zqZhkp$'
    'xC`OW;Oz%uLESIZfS}tM24*#OG;7AF=|QSojwlQE4Dv%W&Hh;x|B@fx%TJ<dD&@Y9>qngkvw#+1bIR$7ANVoj_aby{!N'
    '26aLXBHj5ceN0@w28D2}%ZaStU=8$!k;V_Og9o9#hpk0wE<&Y8oilIcFQX4@VT^g`TA!|mNMXF=bu&>oROKS!Cd5*;kA'
    'kQjZ`aO09?cszun5PW^nWRr<hd(iy+FL#Ba2r^^K|CrHJ5HaKAwCN^F4PRS8O4pmZRNtOR;PJsrf`kwwzi}bQ}A9xhl{'
    'Q`Y%eV|XErcF@XydFGObq^LASY9b4ChvXT%K7h?pg3cY=0`E~FooeS{7$-bO#$`a_WJ>ga3(?N=+~hRUJf+CsJ!EOuVL'
    '1bGBb3K{<8nIdapV@BJR7BtC-d&t!32+OX7>>lE!cG~wQTA8KS@y)-+&%9>~SuN?SR97O3XV<JQawm3xJ(6(xmt=wq>P'
    'i@6)sQ&$9f+Zk-(U#3R1YytE<mPM0C*~sd~rr_64P*LAzLm?Yjvr}kM{IzlGRdrhdDOi;j@TYexI5tn%mPeW4R561{FJ'
    'gTp|VXfgu75@mB%qKn?%ITAWt`mIVbUY}x@Ql+W0bR^YS9J}{PsVmZ=0WEi8lX&K4k!%ZoN3CG{iHv?l4jma=MVQP1b@'
    '8leS9oN?CzDy2yGSWvTX_VW3%cWncwrBFJ(A9Rlj)78?-ENTvOr}oN7AWMwR<Q*aK=59;zX-2;op5;=AK*9lL~B}0dTW'
    '`XWtE||%m`>(RvD#slhi?xADciPT%C$bV;Q7&qts!<SihQxwO5M+4jK{&ZWe^LOvW)CZVdbqkarw@3j7A(*8{(9_>t15'
    '&dH@upM$#scLnZ)a36$w9PV+r55av1?g_Xj;64WTu^<~no5vJ4C6e4wvCxa)=Y-z|gt)lc&0UebNa5sXt@JtsXuOIez>'
    'Z|xpm4`nu(4=NuLE1E4zj<z^vf~G_uy2_ccd3MT|bqUH(4j6TAdVNoxEwKb%K%i9)ssN{Bq%?wahg4M9V6Zbe?kW0_EN'
    'xCZR^!^f;-yIu9{vEwoIExpz`Lh?J_c^Csy6lFUEh1zEis_rq`#;MWMhX81h`zaPQxdHDT)Dy^G5;B_9{bK#x~_Z+zAz'
    '}*UWE8Hz`x4@l)J9NrVv2bUvt{aU<op9}j-vIoErcSDxG80fesV?aI)%7qLc2(V>?cgw@b_8R4$5zrA9yOCVD8=B?AXS'
    'h&Xvg8wJ6MBI?omEiqt8FA1OqphI+J-Gb%qCx)*k5!9fCns5i{CD;6`S6ls8smZ*c=j4}!+<=YL5e|FA{t<B8B8kxu_v'
    'll`=R)F|Fv_iN4|EP~#qiYzNg1k~L(S9!3*A#12Yade10otoIigA0u_6X`hFAstmWLmKQ0<g{86nHVv|9t@95tFDcB6$'
    '14c2vrMa+FuNpWjh5PasPEKM8Hm^HiB~iz#03n{j^;zqO%XX-E@Y5urERpmymMkog|@9YP4AmBJWZD4M&BMN3&MOu0tp'
    'zP9F{%g()88F+E5$W+loT6j|d-G$DxyMr~xX!Js?|(W<rX%aZhvt@hJJn^{>L@|on#Y=fb~tCWmW1J@A&FS4<LR9Wgq+'
    'Bk#A6|7>T)3F;#C--usr=WMZ%_P?(gd*}@__CSgJVWdCjP%#p!=)dveqlN};ppCx?Y}!yG(kVG!ZCCECG_*e8=$9%qFv'
    'B@^0D(*jhaPYg8T3)3-p)hN|Guza8l&vR3@T0W>pY2waG4y_OmES$*z`4QX1sg&|t*TgCS-2ms$~AW8y5biUX(0)EUdb'
    '&Iu^toR0AJOT(+O^J9xJ`WU8I3n}Pi5hN>eagSz`d#QC`2J1jDkyW{vG0g^E0SAcrEv_*r2yu^@!nEIz221O4{9nnKtB'
    'o6RSR(BA_amJhv^C(-dBGNp7Q4>>AXpTf+U_)Gl5A?cgt(?Kh5>;eK@A1L{DWrjAi7&noy)*1?$A6`C)$c{;B#SRu%12'
    '0aF8e-%)718Na97*D)HU-b}8I6l6KxmNfMSw8WnQ7PQ*2niQp#_@QKvHYM2_|h@}zwWLE>jyUW110XyujRyQ*oHVC%?o'
    '5U<2^8syW`3BN4X)5eE8f0uI$&xvU-%`%5a!C=^G2Zxkjs5gKj1pYbBP~-!ci?n;8QUb98-_Q=GD)PI8egHm0pg9xv1M'
    'Uq)kHR67o*H1jPf!u&A*Oy#&A4V%!EfS#=_OVQo3Sld|su5t1~u0vdy*j&?f0nX~bLAV5*&Hccqis-R;9pizH-wl&4nf'
    'D#@@)8qaB*N#m%CUQ~KNRaN>T*<NI-lg;f-Y-JIBaE>e%9tE=y%)Hig`{||MgjOQgj0x8*-7fG;ALRqr0f%2R;QmjGy-'
    'Rw>5aV9UK)dZ7qy6NH==%)LNb}7fplAG6NJ?zj^IhRvl2Rb7l9X$q3Y96s>~cQvLkKUb8RG*jbfAT9N0GYnqd(T*qA&r'
    'oMkQ=lVW;?@)a8ur0<|G}rL*JGCu35VvFROj8Djr*kouRM;?k_nm{(H1C6tv51(K2_Op}x}@uuO!;FvdcF;0m4jiQ=_n'
    'A72+yJ4C>QQrnzYc9Y9)_yW}T@wBdjhlrD6-WrVtZGfaJHiKU07X=f8-~EBU5{4Wqvhx!f-mGa>cdIR>xe5yHG^Hq$lE'
    'OPMpn+1H*)gEJh|LTn;L4bV&pq$&tZGWab<Tk$)=T<)8sfMOdDPSm6+~ybTpoiEhmebVm6X!$Pa&NR35=01}(14@><0&'
    'O?O-oa><C}5)^fvRh4U5xz-}ra`FvwZQf?mjuS)bVw^No)HO6c&K;8YJ_L~y1>I5`>-b{Fy4Pqkytu<i-Z8zi-lJ^0N1'
    'IL-XG-nXB!*2%ps_ZhAu6D=mizG%9yJCnEwY9md_LJAnemyerL#ba2%N))G160A9;wHAQ=Yql;-kq$wjp<8M9OFOP0Vo'
    'GLy-nceJ+j;?YRx*<lM{F6-<+l-gexGV|c`Mj!uzgsogQ~8=N>`frAs0>l_>Viy}cX#4#UnI5Zq@YB=8fpW;}KIA~Xi{'
    'oofG3xw@W<9lyf0aQbkXElw#h|kbOom$mvYac{+MOAQVU;%jX(sJevlu<FiLiyz^ib75orw7Y&8jLc!jT_~%TyWoF*<`'
    'uAo0FHxwYgB2bxrFm#;Kd3={vQ47gQ<Bc!fD=6+q`~73O=Do)J~`*JYoV>T((BCPu2`81NoI{|-ALLb^wJ6(T_AK3rmP'
    '3Te_VjuC9?YWA@#GPT918u(X2F$*+SsPymT;-C+x4$+j67E#maG%kt9rh^~RN{5$~SFyidrUD+Hh1v6IZA}FFJSXUlIO'
    '!GUNP9R&ydLv5q{XglHK}XCcsZ^-0f|;(s&t?ql6?YFNvExFS5|V`s)7#T%dSD$rO2*#!If*xwRbh2=9?F%GYqtv1THJ'
    '-TqXGwM)q0wC-VU8zmngW<G=FQ9-e<I!oTH5VUY%SG`9G+n!`)rwIMy6V5`w1?BsuNIt^N`Euh?30@5Y9hg8{hNOm2QU'
    '461^0DVSRPxRF^R9+ED$rl`wViFcg3I|%N9F>WQ4?GLOk~_ggpVl7O==Ze;L(~Tkes{tj6*P!3`fY?<xmBDaxvVU4S&4'
    'Hj0A=jsgX{IwBQ<?d7d=L|kALeZ&cKwGbVH0NE(%7kJ9@K@<A$qo4DrEiiepHPvJ}D4WCTOe3ua8WTDZ-BrC!MQUwK%V'
    '=Dz|e{C$MGN4e-bW=euJdRTkNkK#J+*7T)!i8=l~hDG9(RjVMPAGjU;4+vRmr|>%|eCy~QgtsDm3*Y<%-XG$dAIJN@@X'
    'g!tF7nL{cz=v<{ubUh^3C^SR$Dt6lHI*v1%spZ{40^+(h>t2U2ZNYDy<RaKCoz7XRiYM6QJb)iq0}?HIw*f{^>F_coJL'
    'rpr7`o8~LYu=#i(tN4T<*Zzk{xm3BY;pi8jufqv+<>PB3NLQZ6{{NQd&qpE0rjZW<YZ!yryX&jbaalRRMAcBj}?OO{X3'
    'J~Iocev>G%qVX}WkPp&`Xl+kJg4LvVuFACEzl{8aXuKQJ=+it<wpw)SLb|HX2Q4lx1D32U;vYPl(nlg9SaS?w^5&ih}|'
    'nG_X`^(B||s_y(jKn!yG$YgPC+*Eb$ihP=Pai^Bg0cAtDB{o|VF!?6yYl0#K`StcBu-B#2PU3`!KmjeV2lN?1tB*+7?Y'
    ')36KNySEwH9T%qlq@e9YB3bf(!xT_&(N=7{<r-%^bV-;v#ee0WMW;Rj6#E9XN{d`WyG<aEZ{s{jk#A^sK1iy$h7R!jd#'
    '<JmUGEC%$lrL(M8`O+gj2;sVA6qoE9>=f5Nh5NbiM5L$nKZH!NM5_UqU*R)AT7FH=KeMAaY(Xvv6hsDX|1p3fMpa%NB|'
    'paNke{_2X5lT{yPXj<$;ea*Jc@l49nY|H#lIb8#l3T&Tqs-+T&qRSvKxX&g`i|7O6t?Y<cc=~`VUEn$Q-r!&wcUMg_KP'
    'b8waznRKS`GnlW(pUQ-ni*sL4Pr&tQXE5gzO?M_9(E=CP&Za8!Ud2|tE-z`-|jkB*y8%Q!!<yML8k*;kI2!8MgTyGjL}'
    'ha8lV;-G+(PpA)}7Cl{%S=nc*&Tx+FzA3|f5;M=&Co8xg0Fjsp0Tn3aFkITjlM2&5M;*iT~EjKIk~QybYpXh+sak93k5'
    '`2blM5EG<_To#RX6}j%qNLKk&X=`HSs%j^ZtPYWtwhk~s@i$QOs(UC9+LMN0!A4wzKe^9SRiPX$#Z{k$(rA%f6GGIxO('
    'u7D%anDoV?oz%3fjv+9F5pFh;cA?-tiX|iZ~gWt-9mH9d9=jI&p%}cZ}f!A8SnliN9&M!yu#q7Z=8Ih9lZzK`di9VidC'
    'AF&`L9r})Ia0&$=~92|~V#Hk=ML6_of$XCV_)D=_30q{2g7IdFeri?-zM7U}J5V9g)<!va05apB>Rr2*PLW$%XWOh4nI'
    ';AEqyF#ivWDnI56A15bJ<7u?8D?emN|5^9Hv?J^#rs?36-3|*G1X#sj90}$C>7%UIe@F7R#{;ZU3JOK-erVrReV=5^Z{'
    'V&yI|dc**+V(%mC7}Szk;+T*@ZpuhVfs#r9bx%+U2E%+$ORrUrh`!fzk^dg1pQ2%}~W|5lnuahFo{S}ojKCKV5Wsx|<4'
    'w*{9VzPu8x1h7=73g=&8OQZp;jQ3j8TC>jqsAWo7>y(zX)^O{TvSw%$wRA|OqIDJq#>{sg1^c#@gOI<qa?a*1;nrA|e{'
    '`#0@sGNaAs0w@xqnHaaCu3tXee*ZbgpRbYT?A;O%zo>lUl89KoiWVFD6>Q9v6OsX)aukYlam6D!Q1Ux|+BXGAR5pxt#5'
    'a1YMj*IgkqCWUea`P{D=~a=ePOgkhW>uW7`q{ACrL<)F@yzjz7G#(?=Q+)Qe$`xe2Qy(@5<|9RMcQd+W*#Q7h!kx^5ng'
    '|sQZ#}VASaH@D4s}?F()}TmQ353PH!IcIN*dEIk@;?gc2u$6kBkPqH?x7P;5CU|GY&)~i892RrYVa{bE8oIttR)>SoV{'
    'yFHqui6Td;2UAB9bwrlaeXUeFzqF9%m%bqc0-gNu||N|1%OkutV?mwBY8-LSAkN^EJ&{7J)>+L3X_K-%Cv6W=rSccuh~'
    '(7{isi6qO5`$a0D(DU~##p(W1TOL`AWfxb1|A&R3`IB%vQ|N!tz{GF|QI1w@7K<H+>`kRMn|Gqnrie#5xO$?jF)^*(v@'
    'rN>14Oi|t3WwSA%~SmK()2Im_k>~Xi~sx%wu-11h5ytzo0VaV#rR`6&Us{7&)WUDy9_)w!B7GhAV+25FfWlR5cV<Dy;^'
    '6YP$wUzUVwWE_PFQvg%#buYqn4s%W*Gy_8lg)Tjr_R<R$;YI0l1Xq93DqG`S3qL4#5<wa(UyB{z7^I<75){^an=f?Sth'
    '|dOco!OecsyQT%=C2yBP(@3-8L2dQm3`VMRcxjz=IB5S_bSh5>#+UvXmMyY;E<Qkx>dLnt}bB#T<dVjW{$qR#jByJiKt'
    '?33OWnLZ|YT`yEW7`k$Q$PF>o<3O3|9+Y947Yx8EEBaq6#0^qUXThj_m$-X|vd+=;$N;{7#Bzf0+xmD<>4hE~@F&8{m_'
    'f9}YnCAc%{JC96Wf@^MI)b2?1$3RkQeK77v!nF>8lfu3BP-`h}p&FGgv)k_&>6Ol!1WUn*<l-xFm~`SCei(07xE+x`GK'
    'Hf?A??y{AbF-1?=y@?S7D)ki0mufi3_O(UR(c*4qH-7NX58}z$j)*#kh{ZyqyL#m^MOS5u|N^CKakjUk%DoPs^|$mrDw'
    '_Dq%WSY1)s=E5#e?aX+_$tCexUj887A+!8|9B7#Wk@#_Pr<(ByxGApJw(4`*IJPxO=rFj;-?a#$ws*s$WLx<e*;EMKuG'
    'qMkZgBJfjE4{bGrs49N0*|HXG6PYzXGozOM|k^Z$pw{GP-&#ZiW5LpWV~RPMQR@lU*O5{hq~~HkKmIATrLQf9htIvIBb'
    'yJW8f6v>GQ$7JIHjoa)@}x<jMr892#yj$Tb#G2w!IJkuERaX=+%0KUu>%)^Oqq>2f}f;`w)6OOBk11=kwckyCRXI9NKK'
    'A<hK?=3E=g3*Iv@5%T;&{D=hvreR<;iz}ciII@YwQAqcYd_Rlo5w7=fas?Q!W8}nDxz;44zXCBsd;sTF3%~%WNrbPk4a'
    ';TGvZmH?W~Y&yF}V|3D#v?(03h!<J`kW6w2<$zj_-1!L%Ndx7NvP6IeO~+$a`}Hpm(i_73UyPcf_s>t{I^4mo;iJh|>F'
    'AmSW+^YF1vSJ+ovrC$Hmx$>5jPaGLe$_<(OlYZSY0%L!5qu{j)*f!OQd%E8sKjuRhj1*WvP`SCDtu?3!Y%=7zru%F2h%'
    'F|OZ$TZ_x`b@c7dayJjH+Bn+WCgZPidD_R`|I@mvtTo&JHtv`V{)2YS~v!#r;5|>0NsbehJ&y8Jra_gk7JyR9|obU$HA'
    '`fS>9A`c>^7ZiuLMyS~yLj<IeDK^p!ZRTA=ho3;ixh5;|VKQhO}7`gg5l#0=>{cAP?_$H0((r~;b8HjDZm1*zMtS1&}S'
    'LQZB-5oi730VC<85eqtlYo`vb50>Yw_b8=Kx*!XUvTTg+Fk_URtn>(%Lt6)JLl9#>!sTKla}%yZ*05(|o2s&_j<C2WSS'
    'ouU7mvCa(^Vx&5r7m&2ig>yBa+qzX^Yhn;G?(x5SR$brP}ClFKW_Sx1&QYv(h1<l?`k?4w%<t1FceLY|}$6;xu)qwQ6#'
    '~W8Km^PL-F*yIIvtb1Ab*oJ!hjH)|#hZOt6?SKqZ(*-ytzCkDWJ^o`<vD%zZz3$ZyvLvSVTmz|spol}UrM;vNk$rY-|!'
    'k_Y{U6y*RTAdVhPH==D7p(+;%xuH$n{wsYqbtdgg5%++CAi93B9$jpsb!F77&W+e3~sU&?iav^bdJUG)x&o96?niGGv>'
    '2eJW48YV!@1qsKI+JU~S1IT<{)v;N%ik+VZnf2D*6p&7Yy*w3e-G?Hms`hoHV%)~ysx8IQ44)}U>EHga-~ha(X>WU5X3'
    'Xi5#cZ7U8>llKeOgJPQ*{*1>By;mu=A#(4S^htcR<04M9lG)$}%Qa*CQ<V@3egGeE;TKwa9hdm09XKoG9t)4MtEJK9vO'
    'BRetzmgJ+{tFvv6&NBN~5}(yAGRMBDmH-_1s?6b2n*vZnhL2m>l^0-mj>-dpW=+;{!|faPls&M6Cty7~Eqxr^G+?OKgw'
    '6G0-YumAzL|mj~D0F@{=iGpQL0=3SA&blgPK*I4ChPF};JVp+q%)ltofRjq5&L77YkWuk&INoRND`F+z-nH-<2OoF9*O'
    'UdzAJ`J-5@BNAnX{JO2IN98(x#}JZmfkrgbMjil7^t~QOR&r!uNad{?@UDTgF5z56hEfJ2X99{)>v)<%<ByDnz7&m_A#'
    'ib@Ho3p8ea~b2*9vNwZpD4r~s-X#W6jY1^{y$_hP>?KGCnd1Da1rOY(b4s$W@0`<1k>Wj6FH!0$(?&V7^vtf+QHt4SP_'
    'C+N{KbPokB7s)PUrTjh0-!*XM^bQW#nx^aMabRm2Wh>Ru@4QV}bOAY6MA`ZdvX!dlbpw+EcTKQ$-6XcUtg=Zi%^d?1At'
    'l~95Py;il)^Kmv+)Y(qd_vgpkt~)JoAG~pOAfHzAWh-_0)OEols-hAbQY{?Zc-OX#V@C_Un<wA;*WY94H5I%ylQ`j%OV'
    'gv!qClqh?I5;kJJYchN>Zh)umJMkdDS!3c_@M;ic<XHkSJt;8x_RzX1sIpj%NAkw(EG@0-&LP2vY6F8b4EH5Q@%oT^S-'
    'Xr3WIFtOaSqoELV^WwUMUdouA&Pq9?_2HKy`^?_?mOZmdM=PdL;mJit@J&Pp(Oz7fcWhfumm?j2{LF%it@OlN1USYmsO'
    'SY1Wp4)$gNObh1Y7b#wr`2B+?R<57@wv1Ic|HvORHjRiF!$DdfIklqH!3U=>|VO07Gw8wJHN!Z*_ev-hx$dpPj{Xl7JG'
    'eK(Qg*nY->jY~ij<(k2{544oZ@EhkvJ8^^m&&|n-Er3R)MSGHVm|E;P*N*d$Ld=3l5OvNPRyQLOkPk;5XXRZiWJn%IeZ'
    'e;esZo&>*n2n`BCN*<@_J6Et5y@(tO<ej&Gq}TfN@kJp)p;^a7>cjv5dx+QZy+bN_I+aGrorwS@6vkU2dtpbn1M@H$cA'
    'yx`Zq_Q(ik2bpfbIF>X46%^g5@LTewwopZrm26>ryonsdEz~VH(<)GGrn66v9=!J8^6>L)WE9gR{GRuJ{NUfD`zN9a@i'
    '{afM%*6Ey2LOH=8L*C%2FB$nxQ#?#)wb2b;3myZV{$p(joQSF!0D4RSry8%J2V?T-K$)=8C)Kmo#6~s!Z%47N0tT44e}'
    'JSF1H}DI-r7aw>!JaQ=u%s6<32>VujKbRk(&kCd~^U)#im`=7YFUZ`jG^3)wh(U!k=1YwK&vxK=mU!o_l+v#Y|<h6?4v'
    'E!6)6ltn(vW+9DkKLuUD(Yas{WV*Hx7hUL1-=Ga0)TZ+fr$fT=GXBX6I4?QgiUWU7{}rwkRiwRv{mG`0D`<``4KlZ_U`'
    '#%1;3ROfy<rOm!1J`=_YuQS-oWDzC?ri9HSRX7Qa)dS`<!uTIvE&Tr#5Vn#klOl(Y^3bsz*i}*y@6wV43=pkx^2aD_0J'
    'XPCT#S5$r#Yn~s7zCR&0PCvoKj^E!z;@7t%Bnm)kGto(&5n01mb-w=F0%imPlD2s!#>zwTF6J`Na6=zAsHi*IqIYC#SM'
    '|sDo&8wxEX3YoiX7JKuCS(U))P{S>x!8B~0|N-|TxP3A!gQO?^j3ou#!WoM8bG`N;Rd<|N8f-0dPm!SqmYs@h&Z?ToN('
    'Q*=?0uBxFk>&jIlolcY!ty?i!DA!Cha*Ou=1axammGV^-@_%;Tg`*D@2_O+BN}VrIHKN89dWNN)F;I+5R5NU^ASSh!i='
    '?lVo>?gQC%$TKx}wN86zUu9$_UN%Qs^m_wWAIGUn|5S!<S-@SG%Fj#a_}k>E$_A6Zz15M8vuWU7M#I{!KC~X2Mp4Fg*4'
    '814DtjpC8?XBf35OL<D(-v?nq-SB6ZFPrv|PI)4F+}bA%F&5W9s5_yUG|(gE8pJ^gz!4vVv}`1IPNkI>|TAh{vHf=Y%d'
    'g6rc|i?zS{=>y^E?BaL8p>qCU)(f~JkKbLlhi#4kgnJi|Y(>`*x&B|1aoF%wQm>bz*%Q0zBXHBOzK~QpABMwoD(;bWH{'
    '>dz_@}~q{u_Vq742y;`EtUZq7~N*+z1scOCQt_+y^+pH|EIRrNxTO9eonAbSla~+b_SejbusR|q#K_O<NBlOh_;u#H0a'
    '^{cQe9LG+Dv|o;|VtKBZotxDjt0PB#kX;WX%c=++ukWAJJaG7cC8ZaB>-n)Cqz!Za=UryY+B2ndkoZNO2V=qYHf4c2<*'
    'DAaokk5&~&c5t$IPBmi$I%Dm#I>a1di!`q8Hai|=8_mj*bh?Unzy!vRsgv9xiv!6u6uVePm?7`r>P-e5&%2jX1p}*erE'
    '4M;yOy{HmF-YIDoh%7%u^hIJYzpb@lvkEbsdnSS@{+u16;~2Kv{%FJ0}%W!gr^s+4z7$n~TIBokE>8VA%DfJP$l)=su='
    'm2J6*rxr)-IZ6i=VglNExB`yp9ObBU+p1|46^(@XQ8%*tila1NnYLi8G63Z0R5mUG}(%`J0k2ySqIrO44AaZieIh<r5t'
    'HxwkpSm+Q=z7<q%sGnHCcC=#t;LN^u4DT=^xi2iMgW*%`#m~Ob#AF*o+{>6sA5i);yH@yJO|VkMu_gGONj>wq(4MlhqS'
    '5_=fR`&7?_uN2zx9i-~4aa;wCTv<^fWA9ITKI585suT0-K^0gq00y@{l+f`@}-y;ZJ!*?v;4e9^Jqvcnc!^sl7m<=~>1'
    'NG<D#>@IecaeI~oR~j&C<(q_Ug9p!g`>?l4>DET}pt58UI$@47bsEj=obp6AFn2}lfW{-@>XTQEsbaUX^a$ESu4DT(Hg'
    'r-pG%cegx=Y#(#VKsst(E0w$v41=b8ruca6K?q`50=h8ftZl@;)%g<5jZ8Y2$!;cVexavOwM!aVhp?6cC(F<eOImAN;#'
    'GhHqYumQ*<x=n^xBohCoujBCAd0mfr2cxx7_<_zkN+yk7jSb44#^#~4HpbBd+R4KolfP9W+T$wAU2iI}RF`Um#kDkHBL'
    'eSL8ly6SNJFKVt_5=i%>Zv<(Ad@QP;_b9!mUic`eBkGZG99BlgT3;vq}{oUXjf+FDFq+mnVWq37r+5|0}YBB=WeT%7c^'
    'wC`<0JY>XGijB=O|iQe@!xO1f7_xE)eL`r$NIm=4-C193ojm2#|IRb$sEiLoT$4Fs5#kLkoORPS%HXq%z>Kl&d41x*jF'
    'E4u=B*1xB0rxhak@^FKhX!6EPAl8Zxkf`6#c1L=ZpIiYWc@<07*nz}50WO!}{zS6I;>8i;ACIA2%?CQuy&fe464&VC5i'
    'YI?&o+gs!>`Ip#T)7V^tq~NQ^ow`s55TB^eDBRhy;2J&E*4=Ca(%-W}tKNc(vGyu>&Yc5bzHU<v3i49UChg-)JlawYFz'
    'DSq09VH9WwAp;0~rB}_vZ5^n~p17t+B1vkb4iM?x5rkoPT{gq-KWUJyb$1$k`(Qf}wIuN9pR&;|Y=ihn`*U8B)r4dZ<T'
    't^8i(k2`T1-Wf<U}NxB@c|L14!&nKy-l0LmZI<Fh?}MF<uPJ4)hZ}0_n-*Jsd8yBcxBK=E^E8%oIyEVqIU{r1&=<~S{N'
    'UoTN+#()f?8L$8x~A0c`=1Oh&5kwaodzWk$=I58!eF$e9m(N<C)<_u3;PlT7>*^iW`uBMaRFvTKZ&e#Ov(SVX0$kbfGT'
    'Fvm7_&mK~433QQdR@ptcdplVJYS|J5KO!U0C07oCySW>9GenlCJMv^-pJEx+dc#?&J1)6~*dkYa&xgQL)jcS+TXCLq&l'
    '|A<RXj(0pjK?e-8WeRD##hADCNN~alb1E^+7sRTy>hj@oJ6ACmsNq^n;)ZnGJ>tB|M6POFaWffpA2piIp;0vMQACQni;'
    'KI~n~ChRQ$4RxU}a!tF(~X;nEopuhTqwuKX{^g3a-v>Up@f5CPkKGdLkwb>EnX*!*1jd`Wr7Dn*sdVK*@%g&o=#|64dn'
    '8m+RX}gaSlIKkcxOxI<n61Hq(n&$e4>by@n_q+4(SzFYkI;ecdqA6>n2yTsE33|;iRC!BSpOjH|1t8jx2*Vwk$<I4tLX'
    'cn*H7%ph9Xzuwi~yVJTj)-2aVTTrFL(wCH*x3t0b|eQEd34`88ZwuwE&|=3Tw1tIfjDg;|zK=LvuXS>eUSStr4EbXX4m'
    '0>DC=Q%X$Rev!n(pO_p^A&3vm#YDLKQA!y2W|UY*8_u)XZo%o}<`2<<86Bf57jP?OJ%02!7#PA+0Pbt4OsF&b+R)^54O'
    'su?J0*-qVTMp9^mxHP;Z1pdF2eu;ORIO@q6aAQTs%fYdy^DLgUOVrKL`k_l(*le^;@OXK@|0s7jWT7k5UaU!BSIRwG=W'
    '{O9Nxd5>!Kd_0L0^3WZ!!)v5~RM{uiumO^BB)Dl-HJ_K9y4NUzu8dkFm)&7Fmy!+7E3({EXUCQu{pyxg6T@6FpLST<Nq'
    'Y-YwU*f?B`auV4hE#3qPLgp#HgMopooV8ndgPZ<4+-`?NQI^vk8siUlioM3FN!CX+`boY1<GD4gsZn`sxURU$SH*_!9{'
    ';Wh~u5@u^{UVvH|+mxr2o$Mtc`_%yUo`Rda#UeDgJ^=&qPWi}XznH@QcrPykdNoj%w?O(!rSEc@}1l(15Q;{!)A>;T{;'
    'GkyzKQ@5kdHv_VVyqCaxK{u{RY`5Gaj*yI|(We+DL>9jc0ivbDjCWk$8{645x)(x{uqK3kt7-IylVGUAV(Xel|7{YCp7'
    '?Ng(`axK><NV3)HM3^B-r;6Hmzy&UlEq6!O)XdDJ2b@da7EckFj(tyGK0*4XBzH6A#45z)92@&FDaYcV1yXT{O$nSjKp'
    '(Kx4=52L3I^t-5yAaY>vOD_mME7*=_eL_XAhP)IYhrrjM8KMS&d!f(iXlwV!K?#^+gS}w+Ix+3nhh;7tRRK{-gDsMwVq'
    'PYCaimQcdE0vuP-w~;n(}iz9Km0|UcI_Rk>2FJJ5KpQ!nZmpd*3T?_lxKICOB=PreC(lW+*l5N3}&R9ehnkxBj$KcJH('
    ';JVn10_$yLeMkkJkkHC8jA!AmZVm5cmKZWO10n4IK)6n2sm|9xX@p_&#@1#>Ic!mn!O_*Z(J!_rxB7Foffhvc@*Ugd1='
    '0>r|dfs^8!{?UBF>>te#{{X?P|DRQAZTpvi5_k_M0l0|>Y0lWi^4M7#gyU<tlw%Sxs>yzOrTt{g=v?7n@_;ak#N9O9W)'
    'Nr79r%`Dxxrs_qsWqQ%xFJt?<#VS0ok&9?8Ik*lhCSE++_E_DmCpM@e-~v5z6U~j!ewI81fgE1WpULL9}c6S56E+p_M8'
    'P%IQ?oXnA8i|4P?zlNMkCsG8=C)}s%J1-qF6)KKc^9D3*&x;-W-pHWSlwP7xL@`YV3D)!Lxxs;cdfCV-0;YZ7KMfg_zP'
    'LwE33GTy9;EoP?F#|v$9autoL?bzaW>ZyAOxU|fL~&3%2j^SDpBPQ;9%b!Clq}qGs%la-590?d%P<Kf$ixJ$vGVHuxEm'
    'bg54VQnfmJ}^`t|#^0WB4kxIFz?oWnkCA9h3<j5Xpy^?ed|ToRxyVHCQ~>jrI8lazQ2ocF`~5gs#B44}e9A2b9`PqnMA'
    '=myd*Ofem<E6No|wc8h@_(zbuqN1Xpz2Zc|>G4)n$fdSLkVbLDggYx0e_WG#+$TJ@qM{NH1hYXb^?f`@h@J|T^(r(4Jf'
    'IH`HuS19_TpZPNX+9nEO3qpJz=a=o$(|>k&yV38-z^fl3ei$UWN<WokXcra^rey6j{3(%Yx!7Z@1G?Jiyq3Y4LQbP2k?'
    'tztB{|Xvai&@CXJxS2PH}f&pC8?@Gv96%TM1{75`9Qg$VRuDEvgLxi~FTV#5g0<~?{<C63q=sA=FxS{~9P-qf${QPi-i'
    '+<bVsy-gwxHr%}*E{(t@ADf;=VFG*XFNZB{{Dg!LdN=^(v8mif5??%(mYmMQ$Tmb54%)WxQ1?@0)fm1wEHo5KSP%q(1Y'
    '=gCG7_*o|V<5@AAeEGca9|I(}NIjfHEmKYay|IBmvWdf$-vg0~LT@jJQ~)bWQy0P$XihhrvfYfH#5ZyYH4g0Eg0h(kdk'
    ';R5<#3PCX!1(;JM%<C8SFigP-DQe9+f}7~UpO8*NuCF1VUf(lrf>hr*QpaBjV>a9+{u4+$ExQNuhrB-o;QKd0mK{jVJf'
    '!ZcS?2|;V1C2H0{VbiZ(J0}{}9RX&f81zY>Y$dV}S1z;5#)N@I{bVvzE&PXR+i16t_XgZDKT(g`ZN~IrITBA9h~AhYg1'
    'zodTFI1J)jh5r*HN;nxT7Zn%F8@OF4U0dYnE|5}>`vJIO6bP9g$0Gic9nSA&?1ilOLKY_R%@C-N~_@a)_QRl^hdBu3)r'
    'I}{1t3JZ#g>kSQO>M9L!U>%1Ubt;3!(?^iA`#?mFNc&r@Cl-XJmzV6Z0Lm_!rJQis*|rj2r29MLnk3)YfLA42!2?A58!'
    'tms&9rzrA0sc1-~!?_lp3_evra84%YG8J~<B$=U?9gEGy_Xt7i>B#6rADml^)4kIZ-isx+`iI_qx=`ymp<9)Ros)y7%d'
    'C{fk#Lzc;B6`muekoFH*J-basKF?qLq85G}n12GYJp$QQzYnEQU-vJ^q9XLrWhlu;THbCN{X1O{YlF=K*AA%iiwhxTS1'
    'F(?4rv1M8KCTi`(a=+WLF)Bm>}rYC_UqF2f?p~X0dJLyoO?13?DAR@2{8&ni1Tfem5S1A4Hsv>lNXL=NBexd)lmDP-1p'
    '>Lb-v;4M%~L6Zrt>(vOpna0gXZSV}-&IGui5fzb~B9r>WC4I2(5xU>l5_|$8ca9KP5onAzdQ^#KhTo+E)@#o=w32^TO$'
    '$r0$9BKLp4@qgdtjWxNKt<b2F<$rpeuQR%I$+OhLlamxWNXCkII&2>K5Z7mAs~gFVtUP>nxJO!WDFMQwQjG4Mx2FMXHC'
    '`}(VIX&!b>AnD_iio`!Y6WEPjG?(&HiMAr$-*KLo1yADl60<^RE7;34WustBm*&_Ntnfm#lkzN(_2J`MrGj{x(#h<N}o'
    '2=}EF*9Nm*s!0m$|3G)`S;jKa2XF|b8;{LU_W*ivA0E`x^bs~U%<Ycw+3dOD*Rd#B-M~v|VLRgasKYcJ3Vde2;A@Y(em'
    'ySC{&yp;!GQ!==YbdSK#TK{6!WUOfaX46I8?y<T}@|I>P%^s_b18?P`<!>KkgD|wE4nR1&dq%r<IGM^OcIF7=*c#RMkA'
    '1O#&>FelyBKq~DwXG?A}~!Z$B7B#ZL*VK-`F&{EDpwH$i=JP;Pe$taCGP;bDv9Vf8@PilP5YNM4;Q~SrMBxNfaJIz*()'
    '_d3MdC1V!8X78LSZXQ+2}WF=6p4>eGsc(m&71)n20Xtl-uM-cf1q<btg*4NSBd<i7?ZeN3B_zPX_?c);^C6<x3f;57&r'
    'e!qhEl=dian@*W{qFw$G$&x(c?#1h9T{9JvczItg5Aqg;wTg5^mSg))b9X0;(BP`+NjPS2(kBhrIoQcdg8+qauROdg#N'
    '>gw-QRJN5iZ|L|zOKuEPZc2lBG@ez)m7DKMZTP@RZFrzID}BbvIX1<92YzzEX2nynA>-Zii%}Es5`MhPOS(bjH-*6-W|'
    '}^uTXsJ3SG|ozjNMes7{^rpsf&hGJUvEJn;$ydDx8}ByKaJf(R3cWkN-#A1@;nO=^%~(eSmi4gYe~asm(~*q=9@>H})$'
    'Bv0njglQ7XfB<KH&J_HCD1)L**^E)R&v_Qlz9YIvst6)!oJqr*s3}NRW>?0^{FZLn;??hV$=o>L@*6oWn?1Q9nX3x4>%'
    'n5$Su}Z(7Bq6@TAx+p`$91flJ<*H@HNJjrvXS8)lfRRaS{+Nr{~lBOmy<Ca{PJrsp}2C~M9&=3`RNVQbkSzSkV}ugV1#'
    'UpjEW}u$d|O`({>SkkiKj?3pG&vNvi#Ptrhgd<zZFD(**t7^P9Rf@%auKnDK>QM;cWghu<}6=2g>YaVh|y!t8AmN-R(W'
    '%_>?2m(+Ro?SXCZKA!oxxTd$O_hKwt2i*C2?`LPa6kK%HtDFfB2fhhVgOJm!NX2+~twCVVT#T8ON5DB8ZgYyp-Y+vh$8'
    '(UPe}G1$ltH?zkdSld=TgEb7>EA?$j`=p9>uS|MVFcIOe8${2#-(FGBiedKZiKyp6mb9gYf#CmSKr_viD*{kAVq}K!Qk'
    'Smsk<$9gG<<3B3Fc;zZYBw#OL_GXSUbo<|2SO`|G_L(38aK8Jv4??CM1{+?(yeu}$?61VZIBp5_KN$FLn*y#I)zb}Rfi'
    'TiyL7U>Q3o;|(r3_PCc{c6dc!6ThgxwSrn;NGsDvlFo1v%T?%b{rHv`02XdP+#^JfGl+wl#s2RaCeX%;+LR@P{l5K@g%'
    'GvxN_hlY1ilacXEo0rF$9r>$v_j>5x#1i{7IV!{k%3{f|#Ei&N{!Pw8;?aijm!@t2mz*t$2CPp^}IT8mWu7hd0R7XTd}'
    '%g;QF#B20wEMT5%4PsHc&vuV?hg-uo{(b(fP}5obW*GUv)FVZ#>fHYqvgz&8^6C9J$*!)}|DqXx-2G+u;nu^DaqGY&D!'
    'R{gpUXV-_p~T@Y8JSYJrU(qWZy7WDt2agQzEDT^esSo`oHix9C!$>PJz>CNY`b-&}S|!!0PV$y2u%N<XE~M`%L(2k>>x'
    ';lc&xN^Z$u5V^1<LvkN4Uis{7pO46YLddg%j-QSldyM|&J6X5=ugzP?tJMr8(xSiQO7<6$#_kd^peM-UIbdIp!m8fg-a'
    'eIt{srQk|Ya{RvMX~QJwA_K-I4X+XFZ+AxnVVo;;vC?SJ$2CWru9B-ON;!PVK_!eqbI#Z`po&9e(YI<tYGQ6ZnVc2O#M'
    'cLNQ0T#45RLmOKoZJN;3HuI<vxOv*4YTEw<AOY|^33U(>nj6)bM1;3nZPP(VaK3D4BKz;=Ix9;;UjuQ${|M=8vJ_Cp^m'
    '2XT+05{2&L{s@hUO(w@isCLz`#&Z51CKPLVZJt1UE8-L9BoXIQ#M0$iLb^gIcDh+e&!peH78n4W`x3uJ)O)sX)>3%KMv'
    'b3aV|H}(Wj_Fb*xUW)(yv5Zl#Gardv^Y;FM9(<{J-efUB8QiOP)>HUBoa4_EuMm>n1=O0R$CZ4K-TbSHt1<n9|2@$Kbx'
    'j^?+hMZmMx5FzP~x+6PgqwMga$<3`*=qi>{1=H%_0fxFx6C+)-9*OKrcJY)(WDstt30UTGwWkr=%@iD+VX;Tj0jDz1-!'
    'OS3`JdqJ>K2W%Vu@9F;aV1%iJ4d`5Q7pb1g_z!ZK6>=)usr@&zxfw{A^IXFcUi>cMU|Z9sr0+7lRlp!X6X@|zZyi*u)X'
    'JF+j^DQ!$oe3_z>U_w?HI~m3#5@K9{vxOHxfbHH0&yQG<pP4^8Z^u|k~KEmxy{d?rK^xqfp9qCqEiUXNz%RUp^?T+)um'
    'k<-%|=%RS#hCVvCiA%}k5>CjLR$I7^5_*(gY%094!IB&Z01&EwQo>2!WEq(@0d_y0)@1K;uz!9Kw1seei8Q)!`$Z`+ef'
    'umaVS6-JI~gdOwnFyLTOiJU1VoD81km=W#YdRrSx+d-J2O)!2}N)ORywNMhwUd{!{vr=<A5tMK&Mh1JV4LA$sTsH1|gf'
    '=B85291;^p-7l2+)Eii-=CR3Ys=+wPZm@Sjq@|#9+B)ReJ*s>~R;c4w?C%b--PSEm4%s@5-_fovmCZDG>6_LO1Xxsi-_'
    '!BcZqwkwb9gXF!+Hv34pNu6fouZ0&=@VG=b1>o!lEMhqa)B!sr&lx##kh)wzr{=y4a4e;=W&QNUCv9hhc^AAW3cF6DMz'
    '-RZ6yigV$6%drP^}L^yG1clr7(omZ-v=$?3D%_E15mU|lV6tHtRa%-MrEdr~<|mNeBK`o}p>6nMw=T5&D3q|(6bARDGR'
    'ng|p5y42bU7x+caNfW7BDd==+6)!bl)rKb@y+|%<rD-iKWDgkR8ijAhy$W`<$Y+&(L$Ys>9*>By19aJGRn>YWau?mEN;'
    'Dq$`R3ozo%U9G1ad<5as2n+rOSsC1#U|)aPEq#I^5PB^9ZiWPP9%d@n6mqIn_1T&SX1Rks77N>Ri>N;+IJq-@`doOi`e'
    'phFGP&CeK4`)OPt@OI&e-Ysk^jm`hxV0++?EI$YN6PsXyei2~Wh*;RrO#2rOGPFU4o-dN<~#6`3v#lBq?bjR20r*@~XW'
    '&u_pAN$tG1fJMIT;#EHOjWC6#oDopPQe0Y^)I=OZ~hQ8h*k~gw#vm6{WS%y!LP4k{V4s~O-kE)syg}Xw;jck>l@tCk7f'
    '^-o`CwE=TSZZkE7b7&iIACmFB7w-lowaT`da9Q$?$!<LUt?JzOnz_W?;*<W;Ww10JKFP&{|xnk1|8%wql2P@fqh$EJ}o'
    'TyL4>QSyEU?o(YJXvGex&cbZgPxH(pZcByzbaR)t!*vdi><6LQl_A#*w!2hoEX%)DW%NTI4$?y+I>o8Ohn*r<WNv<}j1'
    'gGBTlF`XNVs-xdqG6VEf*~1Vqu31XYWHXtM=fGrE3p<FlnTORahn^@`XYvQ7GIfC7eQTN`J|-I<*PL=!dwdUrfYibhr}'
    'KfVSv|E5-2WH4=WE0gGjB+iNIhj&K##b9-(V<~t&S&CwyuEXGp=gz{oEc*I*eTtgH|IXqxT9$PMpL$SMy@$;j?f@1uNq'
    'mbul6Xtv!DHYmT3uZdCq90WN0u$(Xi=G@YjbtB#m?J0Vx^tSl9y38736(U{@BYHj^bSN|lY2&4Jg{Z>kX0~djX?9`Xeb'
    'xUJYW^l=(ANRrh5;d<{Tf2xmQVCE<M{iil?A8FkV$03cAjD=%M#<dPv{_ZK7&KnC4BM6eeB+k1vF9cP$E-NActOnAmIJ'
    '{fTK%an4u<9vp^s$ayQ2+RJ!ugj!uqj)LS`4CK;RRC9|<1$iiMDZPUg3z|c_ZXR}7jKZ7-V}n|un18RGDu4^3;^O=!+H'
    '`PoUfksOsf@@&WKPJ?k1gc#_03uSt>X-ykUH+EP=5MriUJAu`^K-s<{Yn3_Sv=L$f|{Dc<_0J^4#x|If=ilP+qtb58|k'
    'Vc1ypd7&u*7CE~u_9HsGHC~dTq4hspk+`urd`<d|^0vF(zu(lvr+bTf6vcmrW*H>34M-M?ID1pzb`R2X23PoEhT<)!?R'
    '9@`TNfcOeC3c5b*?kNr00U~ZFrTa(EB{~YeF<1o*VgEP1PBmFR8UmZsA#RIMdO446VxcyqEQ5-ii!dPA}E}r)(aRKXpP'
    '5I+iU0HYOS|+w!PM=Y7()4^H>XY!l8OFwo*kvMe^3#X9v)0?|<LB|M$N4eeXwi)>(V)wfEY?IeT1dYszxn`7%Rng0S;*'
    'kVr6+sDSa~1IQRu;^ZR4gT_xgUyKp4!H>tY7~_c(<`MpYlHa&)ZTVwcBVb)uzI1V2`O+?47*a|)ZAD2})af3{mpg{5ZF'
    'r$fXA;Yk{8;oZZohb;Zohbb>j>`kCCw~txf-SmevsmYkHy&W0<R{M;61xE-XX>F&aIJtNls0-ein1_sPYp%p<>@SyVO*'
    'zd+fdrDLpzL;yRu`*>yahn3;F2mCzIY|MI;4km74>h<IMVL+g3{D53=rYA>}!HMcxHYI$m+Pk1~AhSchMO&QV5oEAQ8-'
    'E!1SNrMk(8ZMzP8?s7<S2~Qe#K@+`JBQ&hb~7g<c7Npt@Yt{%O9D5nHD#<vI0u78@s;i`e%@y%J$e6CJQ_jpwQ>FMkUN'
    '^gQlD!0gC1=EgRkXF8&bf(f-gfTIq8@H&$GzgL~;ysvgYKulQ&OR`X1!!8t(G7co-f+j0;gVT$h~8_18eSWwKm_2Es1&'
    'o*W8<uG2#T)aT$y22b*aUm7Y+zcBnE{xn~O>CE1*WQaBZOhcpH#KT|9<kW)44r!EQCf2Deo*yP2*gsi6F5b;Jn^ln4+k'
    'KV((W;oH84e#~>LX?q+Ue4vngAB0CB{cAp{e9hXQrDlu|3ri;M@<EDt737dh6wMa$|}_7IMBaK0&m{Y>KQ1Lp2a@)5Dd'
    'DSI_{Ux}Nj}<29G^dWDnPDD;J|TO>Jx@9=f06wK&d25<3FJ`izK(2*&&SJaPt-p$x5b<?V(M>8DWMCzm_zKm9;C8jY`B'
    'FdW}=0cbeM(*l>7(<|;cq+E*8y&%l?J@V&w$-VPzIKPg^e`%4W_tLdWvr^uoqqhtMIx%icN^|!_DBppWIE(LeTB6BQzZ'
    'dKtT&$Ok0@fe1|58+^Xtf_K5)b*h&+5gRCldKy2C)Y)u+aszB0`jCahAEA;9G2!Ip>}Xi^~o3VVdGgnFB9OH1ktZcv+z'
    'cyxeRM3qm;R9PmtiNeedy#vwl$3UD)Jd6_X4%^c*#cirVm?$beBy#@bey%L1ctRde41)N`kts>+8Su_nO;v%nCE}gX!)'
    'n{zFL-i)ikM-{V5a27(296I%skZ1WRpJ6-9z(q#H0b{*N5b{w$&~Rs_*L2aBHS&_PhKs$a<0t`baY;=MSB}0fSVv?b$e'
    'a!_O$kP!oTw_i<DQJaqbZct?G?CNubPb*Hamv}Ud;{~XMl`HIk(MvI)+=o|CB_;%(1lS66>F)`7m8Yv8(gjUr`ykAPOB'
    'ie_m4&N7d$;>e_KH3wLiFQ})VC>b(q8ns~^tMwAzfLzB9^z=S=<CcejRvl}`kc_kNx#Lo;btkQ`{Ii)K#-bm5yN|@aO~'
    '+^DgzdSkW377;4Ncr6Zr8`kan_6b02SN78xB8n#Pq8q2(~VCKp@*%LZV9hXjLgs7*vccxY$5TqlOv+AN+aJ?ALVjCL-S'
    '=l66)XpCtvk{}jjm>nSLo~X7Z>Kq;6*_hg}5^0i4LJm0^uC`%|n=I#-Do<a9X-Pv>*Mqom%NTvDe3R--%{tBxwaVfe&5'
    '2TTJBN>{S;cwaZ9JVxxu)NOcdq3wzPFm`U3}7kZG4T*Emy&rZUwZtoQmAjBVI9v2f=R{gt#H(PB`+s(djxHX*v)h3^?p'
    '`9{hKrXx}CZ_OU2x4q+7kd_Up;iGB2lMNhYnZpb3GxL;T#+DAVD=(@S^vj*JOtbfx!I!69q+egPxe{LV0#-RqF0v7~M2'
    '~Gx%0oMq!)Mov6*+(a(;lxZ&2R9cSyXgOhee}xg7W?R{vj5aR`uRnqPB8GgTUZY8Ff#kUu#aAu{qNdGC-MGo*+-{wuK}'
    '<g+y~%30rw@iZQ%BRJD&aDWglHEBLRME!7({eOhC?mlYMk@;8@8&FUQlPCFjIT0}I{CJj3|%!XD-%nfl!7cEzVyPsP4d'
    'Q4UFF*o&)_I%kZGs{uBniYYml-`*HLEZ@%|DPzK-jU&U^hGxb%dNAkV93yqKPZ0Lrb2@c~gm__k6TO(0UXaDd$<dVB7*'
    'FU*tWGbyjuXCFsP|N1uMxM}q3h7gab>%`Vn-FZfTZLc+d*@Qm05N%5ikMlXT{IFqo?|urj%>1InDXw6;EiWH_bdl=7_Q'
    'Ea*M!ObQ6EbUK41q_Vumsjlu5Ge#N)s7@D+Day@t%Z;<j;C$HEYJ$z3~4i=T;-EAdj@q%y}dl|c}<7wt-S!*w(bbY?a+'
    '7CG=uCFx+eM$eDzI@quRPJmC9i@e<<(oEdPTMRT9!#{Q;XAhJ1E4GRd8`1iX+1t$J&<M7J9y&q0L;HPz(YQ`ok$h#{fM'
    'W^50+-S3(MZZL*i;1+P{-zDreM}N?D1iLRMcYLny5;RU&k+FI6FQL*sZJez>O)r`T~io<Fn?F9Pg+3?}ICitQzn@}4k&'
    'l%nb`Kp8-p<{0PaTki1o{m}uu@B!`pGwZAQiIe-Gp(*qOzWQ>!VVFcNWr##d)=k$chf6MZgi0c>sY2CIO7=HUME>w@l%'
    'e;b_<cl--r_ix?Wj2hsU6}v_@Sr{NEC#^L~%drF!pN_hLz*VDmRAn^euC^`|ihRrOa%UM#(VZjdt%>6*TclO~P^PL1EY'
    '=Z#dB#M^7+*^{o^pkyD-Wszq|Xl#Ya;c{Ml<L_zciQ9)E3<@z1Kj?m<{69F;!jH6EVx%549m|7$?n!8QMG3Ux53^|$#)'
    '6{N|kCELK#et|oF$0L2QnsfdUVtnS{UJqhZ5xW0LGWJ#>BS3wy@PLxFzrWjS~hVL22d2ES<-lePzJNVObLv6w}KqP&ex'
    'pIjrfH9&VhhcGbF?!CS8;nA20l{*6GZ!Dg9wOz6rIrS9?Z;va*P<e6NV`m6Gv}+s4tOxX}>s4G6f<7UAZBp%NV)K=v9B'
    'p~DL9VUVs6BnN^#jgE%4JsXH}xMH8DrgRhPfGdho-GoTG4JGwQN%0AW4<KgEJ*GA5eg>ffkLP~7p-1|bWjHn4N{%8s6~'
    '&@1!ZNhf(*(aDB#eU7!n^$rh&d1oo#c#_^M5R?kC2oR4CrHUDXi;8gP2D9P&;s%15vh3sEzKBo4X-mCc5eTFq{hF<RLa'
    'wD;931GyO|EJ)Ph@i&n?bgt-qX>s2$f4lnU3sD)#j$iXasl4Dy72YCu|eLcw8aa7B#<;z8te^Y_nO;J)q?!Ym}HNr@yy'
    'hY`|hvn7BRsLB&)C_j#x1xyvhc88rV21Q^%d5l$fMt%;O2RucQ|64%#6cEc`fh`hk87Hf=@p6>;6?Mlpa+QYbH*uR0ia'
    'A$YAJT_^MTVz%n;}U7TUZ*_e=Canz*2qo)*^gzQbKoYbprv;Fh9ci^s(5_D^E^qFSC&ib8sm#}go;rnYdD>31*3Fk;xC'
    'mA&gfv3v7Fzb85Lf(Oi<gbQAHFhUZef?rdC%#Bk?VnWQr_5dm4pa5SINlZU;B)+6(KO0u_1c@J3uz6Soa>s<UhVsMsUh'
    '*!oGqd`7Om@h3BGgpmD?%&Ai$syh9Eq<!sW)=iA6t!ROp4s(q2%LXmOfS!h>3D?P2d62{O{m;edKiV?&6t)wD3qBB0D@'
    'L6W|vOzyRnA6h4oT3xua}@RWdF<I!tctV8a4PDq%R0MFR8V}%`$peNkn@n9K=u8#B?A&|_iWnzSl6xJi;o`I*@Wi;YD='
    ';d4*5DU-v9wi8wM6oTzG1^5<NC0|*<6;8-#ZHTj&2&%9l+F;MARzI}^uP!b(A#H*(4X)}^MP0s8?o3lC-}+11zj|U^4n'
    '`FR{CoW6?WHD6m;QBXV07iJ%ytYiu#V`(8}L66@^j=b&DS_gI82CUW&h-88)mZ=m8Y!gBlO4O2vnE-tMp?ij|}I!0xzh'
    'ikyXu51g+M{{X($9*EJtIbOVB_yDfJaZPHj(HUq%9f(?I;2sKh5=gGI3fzX_^mS@|t-97cj96UoDfd7)`MT~0=y%hDpi'
    '!o$`@_fV$K&uZYni!R+c<YQ**UbcJ<KspqH#v&iNr*r&F4idDv^`_j^Cl<iDo-k$3Z0J`s#IlW0-wsh>2b6Vn5<_0y>j'
    '@cp7q5%z3IySBa`{Q(G13hzcF`7Iy3*igX_$=JJcZ1%4)*uc<KtRp~^}(YLVw6ETx8SW=lOA*yt-0=tTg$6|%9$Y&WBC'
    'O6q6s66)&zW3zDMi{hBfpn~>GzZVI@SJV~LF0vJc*HAO003bW04G-+FAUz(R+lbbXoq$Q4n$;11hdKMJdzolz8s6O@R-'
    'x7t`8rUf@^ofaOoUvtE96)OK=9B5ci8@=18PF0$a6HpkC0+ohYy^NA(nUMe$8s6fRQ~Um-`+;6qBT+eL#1=fk-mPPP%d'
    'YqLHmK3?3CQrp5gmEujCMfxN5l?K#A4Lm}YYt03fCD8HUIFwjF3fA(av`lWiM$5#^or%qata*MVu6sjOI|6Av3mpdHiW'
    'gDzfT-%ZPVklp-<z<i_}Y?sc0sxRJSLhzWkJ1XnmXjTos$bd9blPQ24;P=so*@rdc_OBnTUpewIiEP3f5fYJo#?8(8U+'
    'v61Jx}B8e3W`a^Gz3-Lr-MpMpq$0d484Bl-aHzWvu?=N1_j*?t3V{2`_TQ}AjSRpQ1*JFbDB*Ah^YK0&_>U5S4`~==fw'
    'wFnevYkwVA1jY0W-fN(DWTGx?a8lHhQICbIU!T0wk2AtL9Dx9e6F@_LenFg&^*Z|v_@jB1@wzAzL+C!s|I<rZmY(VWg5'
    'XCS}Sn|o+nlBwhzaKiV{EaPOU2TK&4BarYyH^wf^^FTN$~1TEz~JwZz>{P;B>6Y`1Cb%esYDM3D=gEqe&VP8Iy!{Q_<N'
    'NbY_<X0`j6VjFjI&P-e&Cq`0A1pJnWc2eT$mDZVVf*w9`7zX{p7qIvia=geY{MuEt4obr`wGESwEtZDc+ZF3z7EXND=r'
    'K9Gx~8LX6)K`BSFiEF*jKG$RzSlK##@z?B1wfLh}3b_xB-a_W`2)joZ4n;jLPk7YJ727fGd&;qg_R#=wWJ1&h21oT(Qj'
    'G6;Fk+M&+n(6U#nvRx(?#>}pw_32wQ^0Vjm&bEf8IoamUlrIXe6au0;W!bV^vZkC3cnjbyxeFnV)OwCPP0C@phX{dEtt'
    '04uYD4vgZ{M=O(PsNHo1+V5-9d!Ea0+TIlOeAhn=KhAChxnF;peX5%!^_8-mvcgR!8J39(cBG7S@FsZV$$m-?Sd^a4xG'
    'd)iqWpUVtbTRvHesHS{`j1k3~Msepw0w`p+%z8bFBE68^5^+12rADX1?rD8=>%n(}1<d|cz|H%0<owhjwarzu~0Z#)c$'
    'p(&kq>Kjd^X!T2)Ye&14C{ejb1<kmy11iw+?Kt2iFTm!_<Yn0Gm?hSYRHxa$v@R;j_>vQvI?hn|a*-m_k)!CjfAD2OE<'
    '{53%*5P}!_(Xiq1xtpsT_Xcq?%ZNfrGHZyG>{xjo4pm-5}q%1MAvE^cSH*Gam_3TuUtXFtn(f(tU1EszM(?>>K#IjG}l'
    '5jW*~Dvz8Ox_W*-XFWSy!y`iqq7dOyn@0T*^(JOJwvl?&1%_4%9I)`PEO&IhmCH8~KmDLUV$r@1v?>@?n8{}hS`;JO><'
    'NEkqW4qY}<)|okt}}SH8<i~KlqS2>v|s9TjXT9d=1SLfwVkXs+1yGS_7knwpw;fC{caG=4U^psn9eus$4-O&B#j3G#(x'
    'Za%P{^QA^yE4ySrmmJg#)A>+yHIGw_=DO?Fq;^JTM3AEzz<Cz?!M5B|bq{+T{P0hCc@N5QinS`5iV+t<(w(tA5m@p$oa'
    'qIkS0U4X978F-6)fi({m#ec<pv|(s<IsH886=7nr2}85_=|@D5^qmMdu~?L6>8AFk<;#gR;}2SRjL74cUMzZS$_I2~zF'
    '27yXiJ&xW{GK<nkmO48<}n}95RYT&w7|ja-BuH%F<jPV@!LM<5_4&!{ABk=&_L%!*z6?K<j+0|HkE_hes^>wCz_=Y}bX'
    'B@neUC%@`XNM#?~j*Jn4OjYqw#K}RmiR+PL<J`s)Nj&A4)8qH&y_&hoP7a87yootaWHRZ3BGORv6&azPHoW53?G#g^@w'
    'Xy2u5fCa?NG-;WSqjwnSm8Z_$bc==jUTsGCUh%-*Gjt9JXQ|8GGG7_KXk2Qqj)?xSiEyL5F^KZ^cO|`B;xJ5*gFneEB`'
    'DX6>Q+6f(*hi8VFjuXpzMA_1v|QWTpuwQyP1`VlCcUCt4pgH3lix;(b|c9*m<y?QBvsJJ}?7u%pObR~~GKXhn&dTuV~D'
    'MKOjU#$93XAYod)#7iftH{kQ%iP6RLE_AR+`T(E#77{@_y0wky9rTirdowz-!=l-~(QKD!MX|vR@69Or&aE|2s>nyqZI'
    'nUnR0$V?YF=**0Cji)&tdSK@<P(J3oxZVe<A6X;esbH;Tew$Np;S^u;<1wi8b-9BGllSja@f!z;9Qq-Al|#;DM)sXa|I'
    'ygX4|o@drg47>Q#LESN5Ba(<L)&8l5|UWd=?nHG7em!o@YzE>gcPelXV_^)!%B0AYGdZ*>MUoXsnxwS?d;|4lV#Np9w|'
    '7f;5Ien80wB<<a*IG`HfTK5{i_u>R59#>e1rKvu!~hw(6KOycI%xb8i8y-TuqQd7S$Cnkt3TiSt+-cmE-OR{4zJOcNo)'
    '!e+E2iX=83sHe^zqweyLpuHty6xd<=)Ec-`|#$jX990_Iks1^#g%!G2l^svg~iCN(ZZRh1Q@0^cAK7R_CBs`N8FhX-+8'
    '5JCh)gq42NsrU4@-gpuLZ<KyKQSQ#aks8}hlxzrY&P!~0{T(v#DOZK()T?ZjelsAcbNL}s%zxFv_c6_yM!Y>*Ox$#9fT'
    '>#R3@P~t!d2Fq4h$#-chs}8vGtMoUL+o(_eJ6ZvC6A#=ORMjK_%cV)sP0H+rlW4<U)~1lD8pM9ekX7HsvPqQnu&GZkw1'
    '6_z9zEG;RI*wh03T+7h2X=I|hq=TKXD#B_z*k0@E*hFo>%$yh2}!CZ1t_N~OfHC>eCgO(^C_b+}t?4j1!am@kJL>Ui1C'
    'L@tUnB*eM+mNdcKN(9%ODrxKMRqyyZ%r3vLF-#$l#lyYH$4{iaBJ*kNI6VoJo1=~L=NFo7g^qhTy^BhSd1;PxMURB(}{'
    'm;x+u%^mM9<hk9a)nk=EFIA>{~>@#teR5;+8ki!5(Lt~&Z;EaxA(VsXhRvL7J+t?8mHTU}x0kNdy#c-W(@u@@rcD3S5l'
    'V=@vsggGv<ybZbP*pso0Y>CAsqsXoz{;lbvEb^8pANQ|&@L1Smt+D@tlw(B3<B!Qm<Pd&vk>zd3RmY!<WqnI5E*VAkeB'
    '$4lF3OVL66NFmhL*7Kd2)RYG!MjA9lhw=-;a73s8WX!l{$<oS@osrKFmlwFIEKva>3sW7?!|mcnkT!GeGzl^=Afz;HxP'
    '|VkHb;5gN!BxK%-<HLeR7*FqAPtR=1s7+3sbamkqTBrX|aXyLttyw5!$$0g+L@`N0%Jm-+-Ve{iW=aA=m^AkM(I{$~7p'
    'OXLYpNOL}|KG}gVe?b+pV9n8{_~%j|1r%^$^XFSf0=*(r{y2-278RBO*07~rq2e<C^fWcD9#3#XY5qSU&mp1Q1>(ZQIw'
    'cqRACo<P1OqH&RN*`D~j>5GYr-T)runVM^QXW^c&PiL}LJ@lrbV@0E{Y1hKtVu_}pK7rsD#emY)?8R&*7S(8^`A+faPk'
    'QWUFj=^WmPei)*a!XFN;G+p&F9hQb3<|~V?;>NJ=Ve<<iLD;jy$RG%Mu13gkzYCR)kHwiDCnKXC7)QWZVkpEnl#C@H@J'
    'Q(XN4AL2Hht4ot?97JRO-ebep~>u742JTo+YMObs1%>x?Fh@D+~><xmRAUI(Xi14H?_uH8<CgS(FIE2A><a9!ZS^>jwf'
    '16?4J*S5-TF==iK(RiiiqX5%m9heXhsY>yWCnKtsD_sho!vj`~y2RxWe)xkc@SfbutH8i9sB}D4n!!X`3#;OVlF&zj_o'
    'H?U(n&}qG6$DK~eF}Iz@g(L-)<?KNmhr=0EQQtuaRu?x5Ez+B*_XtQUu<)S+(8;t@CtF2CT0e!OGQdEav%IG3o;#YJMY'
    'Jeqpu+P6cOT3wJ<Ynm@ibega8zJL6;y^jRgFE({4-upKZ7I{)={d@BeDM-OY$skGC}4U;bZdx>KKMy25KP04o)AXz!`&'
    'ZfVsWvbcJ!w&)fr)3sieTO3kMbQqM19Wru|%`-Xynu(kZjb=ll*>2Hn$7phAtyeV1W-1*W%RR{|MS5m?hfiiZhi9hL;h'
    'rg*In`1aln^Uqbf!ut+yp!a+NfmPnHoE?a#LeB*2|O<VrX^*@-KuKE{s>2E?>PcD@12HD1r1036{ySsfJh!%)AWn6Jii'
    'v>PU7B((ybDG1Ijem#;_55);_~Q{)jm>&yAZ3sXAMi{_of1;4I%G4+~|HMocvBNaw$A~q3m-DK)i=riS2O^_tomY~;_@'
    'p}JVsF2T}=zTIxbCMg_qKk?4wxThqXx1;9#XHK9N;BPOz>m~%pWI8CR7%=-TFEKCg6q+sm*Wv3&XX9MQ}T9lb$j(X4_s'
    'tODusAkRSd`R_7!rGUTwmN@wtx-w-WKyXt9o~1TH?t|3Xru2U?4=S4)d7D~wL3uRYDIZ@!>!BrE3XQ$+=G95iq~r~}!F'
    'h$?zHIdAlmX1Y82Lqt0pA*;PB(liy|C2@30E4mL{9f;^&4Ceu1S&vL9WKwNQYEdF>BlimLs^8V(>b3e{T7%vn*yp)&?h'
    'zg%W2XbdZXEl!Rj9<$!+k18yOXK%dcCiam6~GYZYNV^&)4hym28bM)&I7}jw(b7BdGyW1@-iHyWXu{SMfkioWK31wCIY'
    'H?C;5oZerPBVG-q6v+`hzap4vP!`!DU7}k#)EOle!@HA>nBOjwQm}8oRSTr<@cixY4asjwL>Ev)n*C3t@G3y(-4&tU@i'
    'H-F(2qVf+k){__W>G!j^^JU7lcUqqbi_=D$XP048ZSR2Kog1LiEAQ!IjSNypnxt7J|bWk2$+!|>?@~2MVOp!tcS_z&UM'
    'Um7d{2=OgCN-K7t3$kI-C$6NER)MV+!w#I0K&QCePbxT}9l5FUWMyu_FiCS^)~OJu#{1nx)7LExY3E+)-vQ9IjWV!LgT'
    'v7MbuWx`JjoX)hOG<m~AwJp)?iI<O$my)C8J7uUAJ2<y>znYxWSJ!L0VUCGWVLYGoPnTiTkE@WnDT?nCJKOQG!VfE2HH'
    'jJ(#i*W>=??yzTKq-Zk9cT3w6Vllm_syjEhUY&aSu$mxYp?;w^hXoTRRck3TC}*CkD|p7P#}}1~H@|R(Q9}6(cLdm{wL'
    'fI+}>$l80-J3zcw9$DFvXEX?afZcfk@jLu|;5#e?#P{*eeiA4#8UrThb8ZLINZ@4(w)a>K}TO$!GgednRcVnz@`X%wYk'
    'Fq%qzo%#w&YmeO`Uuz4GDoIwRg7VT-QPH!xP-q2SKLR&#;WVb$CDjwVuU-^8QAFB#vZoipSQ8M&~5DSq=3S%XhB}DoH#'
    'OwmFYBxxq8z<C!`x{chd)K+~V5i#w9>asiOFd8{Ot^CaR?7f@|iaYID;0@FZ2sUbiYXR@~cF+rpDV9^30y(Y@|kGgpZl'
    'Z#&6SDzTPtkq)Pu-4Ala&F%wc{TZ^s-PN_hJ;WapJ!eijBkplu<GIT4q%&MF@EU}7Kf<$I`ZFlzTycpO<BfN6XGC#uyI'
    'bYj?p73ENByo?kxY(GkTSz<_-nWag35LEdOs;UFgz((+{n`u1S{5l(_-2GNmjb(+vHAiqouhS(3+bQkLM=EPt47Uwz)a'
    'M1p%)?IQ${W%?V8@t8;DJJGm22rU_NtGd30^<fO5&4o^`q3>ZuDx}M}HJn1~^ji&lTQXtasq-w;@2pv<%E_=;PT%u1p0'
    '=1b`5uPN2dR#~9QTAA+qK3zNKG5jR`UAMjkGjKX@K>W(DT;q5Wod~CK*d|EXJMxg>ATJPBankLq(vB9g4fX|V8bTxG0`'
    '(^qNUZmNGz=;bHSeY*aV^b8nFjZx(e+%ITo6l-1ne)$n|z|HsNm{U`84>581(h0++xOu5x{acn^aufwX`lZ3QsvZJJU}'
    's;+nR6-&*cw;2+M_3Z<~18;g(L41GF_W926qzblof>1pVKbBoYp0;NgT=@!5I)deUMA(iY`7%rDm%{ij@lK5CAyWK|$}'
    'RFCYMbUzu2gd@PXZZ3TW@Bc+2S`AI|gOEa|8@#4m({6hMg?qr3PrfVPs83^piNp%h21o3@^z2+Y|mW@Rx!AtD-;EKac0'
    'b_+yg#1b(^HUem)IW*MsW{ezE|@ju&d_BeUj_s|^kVyQV=CWht>c;y0gRrmQjCu{82d-&p+WnN~#(c@%|@9~p2=a>yLv'
    'uySgN)_;_SE^5ujVHNge|$o@zHzb+D!GF>R%(uwEuDhbu-~;5+}gZ3cC(P`#P8-Dw0Wez1>fNY)ZP@Ph?Z{^`xsMdEx0'
    '<UuUle(vt&>Z?9|JgF-mT``c!zVjC+p%3tqNXq;ITs5=D4H$v5&6zSjP`(tcU#`-i<+sd-?|lbR*$&*s0#$SwB{|5&o5'
    '16(-7Of1QhvA@9wHx0UQvQwRA9_uqxxcg4a$%GlL!)Dwb+!Alr*Q#ymQ+T3s419acao12yUVqE1uQcn=oAuRZeH~hDDN'
    'wFfpmkscS_k$q-uFQ}#eSS*g5yS}boS~V6HJZ1idWO|q((@|u#ck{<HN!Ea^u7Bm0p>W8X5SHB3E8>UYQ;>BhZ%NzEYD'
    'AO2*|1a<e?{1Wl<y8|*MhE!UqR8T>n5<qf#wLx|5DcPrlmqAdJMj7!|>GCmAt`xqY%WL3t8VeEM0!?A@sjSuyOKE{Xh3'
    '%@o#OkMd|re_Tv1D=xUTeAo6-T=|OAs)qRXw1hIR|?t*dKjiCS%Cfe{+fPx#yRd*cwjZru`4a~hwk_Qj!e|262~~?tyg'
    '{%<-6{tg2v8yO1xuK-)MA%IrX)xf*ca3z77h<v5V$Dl`pHoBh`2U6e2grRdRmt)r-MEDE__2lZ*S)<bp|Z?eGo(eXW=r'
    '#Ih;~6Z-**L{aQd@-t9T?1479euYHExFJnf^z~(b7JV9D=172YvP@|<$0)^8A4jWf1yorkR#}M;o+Xhv7MkPEJ0vs*jl'
    'iW?qi)8;!xd}$!-K;IOWYqDgLkI)j43roACaPFOQF>fC2&)LiedYU@mr=iAxW6EL@P>&Qe@0EXQtPTns@LR5x{i_eP&E'
    'CHToz@On}ssh<laf+(o_XhIYszxuLy%8Bvvd@`iRcSh4T0MY`R>Mx7{XHUu!tN)IeM+rFs*<ow%{@f`Z`sqrX^qd^4ZJ'
    'jUP0OCZqD#7IT)TR6}Qnh~yVTpDOBuzKW6n)Oz)F<%=EZ2~^X`dVxRidXQg0ycq0@QyZ)WY{{3{s1b&!|Q1f=Am6peYF'
    '}_EW=~26}UH4O7wN%G3PmnL?09$Q^`p}^}&%O1A`*BI-Jh@(b!dC9Kt{tCh~Cy_@pwPJH+dcVMp{_xn3Yf1G=lv?Zl}&'
    'Q5#X80&lW8t$+tolBeLiP_I76$H;u)yO8K^UgDW%j`HF4LYlc<>rt4u*5k)z!befe+u*K%lm9J>Nd@-{IG+ts%ye*SaN'
    'EIc0mp(PAEU4~AKYN_xmCvV75j+hA<;|hU6xjIFriF;{z#er0=SFdE`h5CcNyFja96=y1NSSq>krHHH?;H=KYxPtEF0@'
    'S&>@9i70z)B<eXm#PACgx;@x^_nzP(;92gljjcI7{oz8s~4cI7koLBlS+*%$FQm}zVc!tQv`C$ldQ2I5bC^U^+Z{pD{{'
    'XBSB#zIS(`G(V3Hdf+cN^OJ@c1;!@e?8+OjuwfYj?0Q2`}x`on=%IEFr^9%f81UZWdB`ekxyQDFvhaYP5#>+RM$4^Z`z'
    'xc3Ts(IWu}_}5BH^+<L;OXeitVDlj&nxQNbOjHdl#v$02#V@W>a(_VxN8H@+Ys&8%kI1G@z01m0z1rC~LX@U?OV7D_S$'
    '=O}h?cZz;*))Fc1z<Z>WxpX*r=vAPLO62}1sW0f%aIxq*7D1sOA$|bF$%))u%M`bggOD}o6ANMXS!dw{OTmfFn=#O4A-'
    'WN}MF_4X4=0F#!kGr@`)ngxX}Aj$S7Yj3Mj8gw8>e20A2K&?J07!NEsHkZA7+^(&5v?;8%Kt7GE|e&*z@j!lj_o(l4ho'
    'V=>W;9u@c2Tn=vIw%HZ_1rFAyGj;+%;GK}*;u6l4M%G|=zOuZT7d=Ex#!?pqS;ihvOGDYHL0Zcqkt_Z+WptDO$>SGhQu'
    'HnNP!H1nHd`eVMxM(p*Nj*CnRn<$*vBP7902>*^Ir<m`Z+O&{Cob*8dm1A~MskXTSc5RYkFG00e^(~uJt3Z-)V4V@VW{'
    'G188_0+Q70+~yIu-o>H{XzQ&hV(q)U}Vr_&kOB+iM6*%Tk5<f=%*gvBc~WUtdnRwGWb;y!-tyfsdDs?7!Gd3^vMWKOCy'
    '7o5Q*2EANSoQFrIV{B6m{4hKzNE9(trUIKA*9C`_I6y=%KjP&Dy|WuJt8<3!f_Fkn`MVAnK`I5M6-B8XZ|3&kkaG`&;J'
    'PFv#L~%&tabLZN7KO0Fc&nn&YBL)6GzVH%}G0PK9mqETsF2I67J+0K>toGT&T~HNe9GpiR&Jp=`OsMK#mDl0*)j5ZLNJ'
    'mJS1QFxCHp!Hjx|zv8sdwIvt8lAa`4=7pEm@#GYNXV>V`@Bc9xE8-Q3R85^JJCIlvkTI1E4a&`y=GPDh*Dd+s1T(z(e1'
    '3~FKl%|48C+mZ@@Z9i{)1Bc3=UJ~<;rRsdh%yYe`Iu{1m60&>7mjUk8M}{0jdAG=;lpISnk6$B-*%WL%j`thC451(MZX'
    'iK?NU3Q$KPXF>})vO`)+70G@y-mxQ(xvNHv?4FkrMZN;gJwT=Pfn2t0W5Jb%fGYYI<B+eMNjloZ@zZ`AAmaN}VXM%KYb'
    'YVPLY8R@W0Dde;%R=h`>q~dVrFGiEKKnZD4jZ<|7F$e=OLgqxxc|W|NWv6&Si$RJvv`jSFT5f15%e`rlPqfG_1hdc1^T'
    '0svqWU~4|H$}q7=z3JHy%$nMZsW%jlie=CczW!_K*v`>&PL%Z7}=Wi9ZfCKWr-^_~Yoy58H_d{x~}GKMQzyg~=x4!yLZ'
    '+urHB>Kc;3k(KJIzJ&ar>g4=W$+-J%XHTPK`lhYU1v7}sIz8kq6r4Rlxn)}>1J`gWZF~`Zo>s8i>*H0zMfYwjEAI6W|4'
    '^yGB7j(A-=qv$mlKWvQOuZP>e)&YM!Qo|6VO0Jt*Rq_2(T9J6^DHErD5l%N<dm67(s-SnY!e2YiFa5eQBwoZcdKpYC^W'
    'WZj*{WsMKE2DlCO?Y#*eMHD-&2hVDp|Kg^xbo5Q7J%Q32ExEp-Pkyj-UEu*(Mny-os2U0yQqdX0F=TwY4>!pm!L86Lgt'
    'm!%CS)zPv{chhC%V3?<&=gG^&Z;t7*ti`K_c$qFsT|V|23GwQEyw%4;^f?SZf)5O0ic489yc1=jT)9Q+dX#OExgMoxjE'
    'G!5E#IPoC(Nvz_uNIaIPL7vNTRvfBa$d?$~AVbALc?Paj5W^8A#LYd)(nepC9=iHp?6siAmLjkw{1+D$zC*a`z&%tBx*'
    '|<A&*=6k3yrI7|m&s)<NUfc>(ET2^$q+Udp&mJz8)g3&6|<*UBO&Cx2f(nn6R%}^5ZTtc2p$b3PtIeP8|FG7Z|zXW@0n'
    'E{R8z)U_+PTqf6y-tR@tbLo|0hLPoK7<F<D(%|<52#k!_jd6NLb-(ENlZ1&Zs%R6lN~&f4W7t)PvrU=C%efVA-sRlWha'
    'b6iw+W1Qh$Os5FAR+?C)^z*%7AHHBiG|5DD9HBI`Ag3+~y`5yboVJ_Ny_e4rG?XWakszo0W*=rO0|c3;e6Y&;A#adms_'
    '7MYoAVgrhkl&m6FnCFg48P^+XPNA7MDciALuavUNOsNnpQXbae8eDOyqPUVQcqw6Qhvug;WkO$fvZ|g)>swKb@1a=dGs'
    'QaZud$0K68RYU1vhcQ|ANQXurZ?bMwVDuti7PGb+Bzhh=v$tq7_DmOk`*Y`TWyDZlxhNv<<0xEY%JFoa%+nrt8f$n6EA'
    'FisBPu{*;R1GBVSF#_i7E#f9SwUTt<b6#VOWl+g>-xWp}od)LW*cw(IJ=_iL@<VE+7L9G_}ocBXk=)q&#Zg@!f(++o>1'
    'FY89o2nJ23T2vEU%wOgMKl!!JwolpNwused=){2lZ$GLlj?Bq<F4`KqPl4AYRM^925GhAqX+a0cT4K$u(C|0fO{{Arqr'
    'fKJl9mOhi2Lia;0K@GgSghNY`(xZ6)=y73*!HZm|@*sP=_jOpTJ2fvsmpOIr_amQH>DLVgINu;R8@=~R3^cZFiOl|r<c'
    '^>X+W^o~JIW_^>dUDRJzSoKYK<In0BLgc7R;(Ko3&cS1tbF)I^@8fr^-TRlSMK9cTdmk|PaAK$fE-(BbdRP5kC0zXDLM'
    '31-)~m`vD0oS3tC7gOnNJ!`oNkw{_Q6D>pqTAsMW+w$wS}`Ga?Zned8NazC_hBb=upSNc+g1tRR+eElCo7kvrAj8yE%L'
    'wTXLuCS^e5fujIr~i27g}KgkDmQgBJfwZfCekM~L7@9)NWSMNjW#@_pjZjf!kNaspRfE)B;3KPC#Xdr5(!t@n+eDKJsc'
    '=coP(W+gB!+}w0CAQsYR-X%U>Y?K)iI;K8@bOa4H{6r+s>vbBN4Rs>9mplIGOlCzSSi;oT*CQ@J1=I>nuWNOiwk8SSYx'
    '?f?jhbYE3ugh<V@j2Ntsz+2Nh|VBs0gr(B>M<qWPFQ#SU-94o2~f9q&`LH%&D-2MbdiuJuItWH+Wc8I!)w-L$CI-5GO@'
    't1#&s-JSYd&KNmHyz+x0z0BQ)Qy`ej751suUp3--YNbJV)q%@vGF)CG#Ke_X2wWN7*0&%O&)`=oc2v40$?El$Zmh(q7f'
    '1vwL@+6lyJ;#Ah=svQH<+(gGR9>JUSHYA30*)WV}zOKFjK)VPHuoH^%urea1rkWPrV3*TX4nc<b0vP(#rK$7^A~K&8ff'
    'QkU8}iac$`rNEWLpuWK3~^Gll9pN~0jp6t%YRGTMz`j)4e$NM<CrZrsZ>ck7;i-=lJQ8{CDt~B*!%!RVniPG`nmNmi_>'
    'kP3!oPb8IK4@~x4UfSV#3mK^HYCY^2vd(?h^Lan{xHof13Ih2tDofd0yzxly-cOkHFmZy-n2K=lvXsFG3LrG1+|+uZ+6'
    'Dqv2eBITGhBm!~oAhw0?VF&TLVdnZno>SqhY79+p%}_1WlBHC}D%x|&;fk8zpU^4f{5FR9dIYfdVi8XE^QIh?ogo(XE0'
    'j<J*YfjA^5I=D{M)BOo&3v5KJ(4&OR*T@B117W&i$aFe~V*pg}NFet2ve2+OPTL?{BKHFsWz9@1#aY-rwDnYSkoBF2t2'
    'dsyl7rm6iTL7&+N1G$=694Z6+5*4iK&>netdYO4R^nW#P7t7FGD=a6ew-k_p<%-zL(9l?^O^`sBm()?<EvE$wmu22W!d'
    ';{R}X65Hdx-VBQZoGTmot4l9bofm3r_Q9KyoF-1u{KygB7E~pGIP;uV8AK5F3Q9=ByOj9l{z=i7rI4{1m=2Lf~DZ2JUf'
    'Z<#~p)6A}qvj2F9DW=Sx5m!XsTJ;rp@^a3Ne6PPEc!#nf<p{@VzmL4!4AS~f3^20S*~={p`}|SFga(qUmgDlF9<Fi4dE'
    '3pN0KNBkD@pX5W=S@?t|TVOc3FfjXI=wC7qbVNB#?Bg*hRC?vr`9Zq!wplWdwxisB6Xu;6sFE1hn}O>f!O+CwIo!LA9W'
    '<qlp%wujs<%qQ8PqR?FH9+=7n0lPu?<7HB~;GrmPPYioj#~SEW!jEmxeM`(+X42iZwo<_acxOqyqIfOyl<mVGVq3P5wh'
    '_sKT$0`W!|4=vjzBIRqHuDZ$kyTPm&w{giL+&|EuKzlAKNoz1LJWnzQ?uSBPH8Nm7<z#f>0KX3eW}B3~vAI5q3nADQRU'
    '5uCkj8wuTq9*;?b1R4~)_<hv1rfbcGBZ<DD%ZWLo@P@uWXP9*xXdfYcdWumm(#A+lF^MXhUHjsI@Fi9kt^;_XJ_D&EYF'
    'lon5GurLlYSsrmZL>;73KHT{CJ6Fq)S%ufNTbOjK$#`=6FQ4-SP8S}Rj)hI?krifar8<skh3@+Jaif8^y58OOT8i@+2C'
    'Ru8{}G?spQK-J&<Fzz0tj)va~Hq1{LaqB~HE^4f~n2XtU2IjWR)7Y>2f;Ex5vpR!595@~SPVPlO>Ye6qZSdsDEKy!cCw'
    'b_U@nHXct%&r~YqC5e!xqbGb%n_BGTpfTHUG!JM_YGh|*Mq)Xax=}+Z5N91b7A-K2R@+97cZ1;)&h=45jYl1>V9EJL0o'
    'syt6Y(qM;=+^UZ0GQ9WHGB9IkpXLLQ76aK$77}O^T8sxTG%?{EWni3gKignuA0pt^<(ntQ1KkmQr&NPp;AAn_*ND+8i&'
    'u*-UMS=4(wFh8<-Y`h#=0uy8zTQHJZA67fEGnc35kz)zN%{U<=~VRUepFSl2_8)5~IFGP!c>`2F8ypmE;f}i&iXMuaeC'
    '5v<~E=@wHOP`CO6vcQr%p%`O%#jZ!(qezkPQ{Wked%=SbOs@6C9Q-+HXQuph28n!Q5LF~B}(*liAEI~7SiG3NW;nA6;t'
    'D#fl9LaK}_5_<ArbZ<h5ubuZ2w5peL_IV@)~aG+uZeQMIjR7h<^oSyIn-j~6_@B*tidETsAIh1M`8A6q9{2NXwWL<5!K'
    'Jd<kD$rME97_8WS!gbwda1^l|6|UG}Q*1wFua^1lM@#d5mMCXZsba^8@Hjc^6P2de?gry7t_*yj_YK{TgG3nN+Qk!4M~'
    ')n^jB(B^b(t7V34t-#>Tw~mSiTaX<fpszM%lpCKBoO{Bdgfs#Ru7`RGHM_TbaO@+OI0(eJgn%E7~RH?R<m!u%uRU-}Hw'
    'QO_Uy2mznlUi!P&;QZBd;F;;pSfg2|)!ZQj+?!fFhGtpG)n5L1H>~MI=ZjU_AK2v;+y<r!W;1vj7=fTSpyv{h@nmtF9c'
    '}z3#0eB>WCIrqtI(YBf+OOkFq<A;Hpc{wAopx40Z(CCvjYG5l`TL*0|M~l$zyJCB-}%$EcV~h-xidcCjPU##xDDX8fvW'
    '&_9-IKK4jj|Loe2Ur1l$;K)4`>HTMX`HaBqP72;5e1`@x+8R}JnCI3~cI@dp<SZUDGZ;GPE;4=xMbDsUfz+YRmvxSQal'
    'f$mHIxPIV<gBu6V04@_;F}U^MJ_lz5_Y1gN;M_X`54i5&`hyz|ZaTOWa4fiDaO=T+0&W|)GH{jP1aOVu26b{L<ub3m2='
    'myKjBJ3Zxw$#Hqf}`bS*fbDoZLmptSTc<m7T+?^0>u|b8^|#6dw#fE}2bMC1)pRy_A=cH_F?4W}lQkeUkiWX(#GLSQ|y'
    '-o1dKh46DjbO-@mz<>o9R@%vyz1OJ0RA46`={M5X>jO+y@!cibaUXl;<SeiMDQ?teFJkuxd86tb`Jcjvaxt1j_O;x4CQ'
    ');eH3q2z{k4sC-n4giF&8ilqF3QP$NtL`bIU_51o|u9ENdECTxhjY<6_OFlIwL1rwKyv^IWJYUG$SvA9i>WV*~O!tdv4'
    'jXWrNsUE_Glsmy(e)XnxKjNZi|dXqalCDlIvW9iW=Wv8pU63{~>{`CM)?n~HQK=Vj$AgPKZ#l=9d%REF^$xG2^;C6!H`'
    '4|&T;Nma#0&I}tgXlPi{098tAS~8c#sz&;VHTfUqGiNd8EN_(0e-sPIo9@k~Lvu_|&06e(@-OvXnwmQ=2Z{^j7xR?joy'
    'RR&lnfO$KPP*B7MF*G3dO6+ONG{urebrG=P%3?!w&Q&RiA>5nY2st8vMuY5~^nrl=y#~;r~>QxV+>A@Kz*qW5<z7p6L?'
    'oIa(u0s(z$620`P`?~lLFLaLbX*c>h^g}nDmxa6#iw3k$Dda5cfhs&LxN=gyyLF6TJPH(|gSvffi^Hf<G3sY5N$Bm0pE'
    'z4ljRf}_T<|WU|$jV?}QsJk<=TCWJ4EhOw&g1&~PfIp76<SA%Dkm3ScU9h^95y{0UY=2^KG2HBXXL`0@>CL(OKQva0E!'
    '_yCp#-6J2g2MWduA~wKyH#UNLY?^74#D+#;HfEXeG<94<Qrn`T;W>JlzBd;UupQWd>I{HBsuF*OCgFsZpvb5JS+=fi9L'
    'w7~xqHa+9t4-4`BD@mRf_rD51Jv|lPK=HkLvL^GMQkCkK`hPm#pR^hm+rQB^TjL${-|_t#p8*}6YHZ8r<iFv)cD<8Oig'
    '{w57Qd96u^^pQ^_%~!YDievP}P*I)CH<Bskzw;l5<noL8_>%EENfo2OU;kYVOk1ltDgE;fu;jT@EifG~RKUP$n4*|Ae)'
    'T3}eTE|9oii(0y=FeAz5CaVT@KbI8dZpn{e_KBQrTMh+U{dJ$KZy83yo2&)M+t_swt$)AM6yV^AJ*Q`BCX18@Te0Q5M+'
    'O3zzsuYTcY3uvVTD$*VwN(uNyXe3ETitu_;@@X9T&-2atF%WoE7LyOP%rwc5_My9a`nqISUNIbm_>Pzt<=;(DOp)0h!d'
    '5$yrY=T;9PiF=P2e-=T_XOOBCbZMZ`VvzZ=6S8Hp$3>8_OO^?DEd8y3bGNSggd8fJLOm=R%N2?j5~Rk)nP$mXWcg+GQ_'
    'ym&eM$sh#d#mHnbv~?_F5M}x?*$l^I!M|roTK%%QtSop;4GjwmYyH&O3f&ASjM3?w5H&H6W-TXod}=bw<)#|2Mze8`ag'
    'u)8Wc>^3A+CIUKRk-rHM})n2uFmA_@j|gj3+#!e-Xgd;g5&AJW9l$1(-ET4EKEm#23*T&ZvuGigm5{SMdBTxLgj}&!SW'
    'n8AGWU#t**{FHDJz6@3t8Vkb_X&<173O^Jz`IJwnl+VHR;BmH~^s<><%YN^;97$jw|8SuWZAj7o9A|Hkuf#L9TkeZ#tE'
    'l5}8El!?KMz8QuS(ed;kqod}`G)@~9}WZloNpNNErz0pL0T>gpCDBlmpz{h-sUG~Ws!gwZs?!JKPM+U6<X<YFc1TvVlj'
    '&?@edAvJl|vl3%yld4&W)NOEc!T2}{c;b@^iPlZ_?Qwp=mHh$q4<f`J`;UCGcVD+hYtC&K@Exlkq?FNwjSZb>hmym)a|'
    '#(Z%A3mu?}bP{=(7=D_k(FOsTVN-J#!Pk_9F)z$4vSDBfl5u%hh|7{+8suXTN57C=HW@}N$lWIHXYyRr5Qr#w5s~T10r'
    'VhO`G<x7X+Bc3q2_Y37r}c2p)u^pKMk9lyMV)hc`fk{!LVsrIglL8JQn9<z*qoT!6zj(MJ$+@jQP1ac{ypUDn5hcZft0'
    '1OF6udF)tVTQZkOgwobkESPeaWa9Xn<H+j)0cy*XTg9b4Xi$xDrb~1$GvKMCOEXy9vw7hq(M@KPlMn^qm)+>IOjkeq3_'
    'wi*B8pnyy=0*LFh~HV=>l7x??{0Sy+J5~_<ojBLwq+DXQ79LouJV?Me?s9B5gN53Wc)>_yWkM<uS94ppm4GXbt;PAxhc'
    'XQMaaBM;i8)~eF{6$aJOnie7^{d?~0IFLj9vD-jm|@1ra|jLfe-Ve^rFWWC|mwe-MRrH$*v4Q1}&vt3_yAK%t)chlr4o'
    'P<Z9K7_VJ~x{VYs5+O5Bgtjph5217q8ve$wB7RVW%$Fjxy+-j|5$fV79!_C5>hDJJ>(@lSLlk}^LfxApWd1_^=Tdxv2#'
    'o_N9zfy4t0Lc(t5hzEe|weI8^wz#J%jpBqfkR(2!(z$T>TZ1uUdr6Aquxq|BpmyTSf6a3TIO|k;0)gTn~!-(s&v!i|{I'
    'i$3>|7L4>wXDZZZ4izv*da3-Zk)9}M6-kZ|fQRo!MMa*v^)SaW_q=VFdC&m9x>2Fe4Oko~{^JuuKlrM_nVU(_-{>tjd#'
    '$!+aJC$7b=oM{4ebxA;k0K%&X2sw>*Wc2f3y4qg*XjX(<L!A}HfqlfKlAgfH(~(qvBB+!ziStt3ukA)3*n8k=Ko{zms;'
    '<$hxWcv^gQ5dBY$(N_Sde@t$(}IWC;J+yxPzHp&j>P;Go;>!T@ialAgL<`;GQ9%bjAxlhk`U@6xVpmi+ee+>l5{XZv|q'
    '*$>(oeN)E>J0N}I`OCSv`?Rw@R`>pF5X5iufBEM%Hm#@owst>`9R|31)Y|iQ?F;OpFV-YNc-=S8tOzaDe%mYc(Z(;lAb'
    '$3R_@xK5i`Tv%^0!iuf9|@JXxoq4^x<;~&-~aA@a4BZ@haCgUhkH8^OY%(Ug?9x7b>*Np8t00=~-hT{x37*UOT8&{vLm'
    'FRq)VAraDv-cKnbw^>yn-^@u^h|8<8Uen+&wUE#mo6F3R*vuE#5JgR+m;Kuz4-(&s;u0Ciwro9v7ck*8Ualrr9)p2`{Y'
    'e!5^>v#Vj696CXeP;Oyt$Sj7S^Xa)BbjyI^*Pr5r1sa{dPQ&vlyB|TWxijY)NU%2`YPYnMlxGZt=l~Ils4&1jljJRbi-'
    'f2N;r2)J9_`>-uH&ykAOk)z8OnSYcJMa9doiHl-Jfd<BC1cXcsj-oV4-%@sZ4lpp9qVJEPrv#654sQ7o@^S7r|UNjquu'
    'Dn*KE6y*Qq1y`*<X<sb3899ra2zcK5!l`Gq2NsO#)o(S_r}Fk2&s;gH4PRI2A2MYy<nQFl$|XN*&t;z;{LSh<k<8*}7x'
    'GM{c4^h2H9I{zLV0YSG3vES?WHAy5}a?VK;DdxPIj%*E-0(NHu?vs59PiuW^Sp{p8YP_=e<>kAD(kc{fqXjWk3}-1L|Y'
    '$!PlPK_lwqa<jT6i%OJleMn97peNH>K$4B1Je-HUnF841yaZal`?iaj&bzi`<ch5~cuWc?m{MO!WP=8^s^Bpgr*IwzI<'
    'gw|i=YZZ@_3nZTS}7;IW%w-!>euOa<<<r5=c|7kkaY#Z*ADy2vE-um@|&+!dv|n$@)>vfAN3ct4+1(4ocRwO<d6Mm=!#'
    '2P)$3J7i?gvkuK6hI(IxGN8Lte|FL)5a)V@^snYLQ{J3r+{``OP#GX17oSYx&JoX@f4nl&0Iuj7V}_G<0sY3&@-IzfFH'
    'zwIk?yR4mY%4_w(O;EnV^B0cjE^F<l3OoODs7E9d%|^~QUe-pfsP^g<*DI2F=e6uH*2~(sIUZTg%n^~yhJPg8eso#8q|'
    '&YA;uvUON>xRA#1-v|&CkBh${~H@iyL~cxT5`gz;|Icx4r=R85aEE+Fz`(?@XC;Pda`tv-RrNo`JtujcdL;_gCk*y-e8'
    'V)z{vuvfg_X$^4w{zn4*6N(k>+WnHQ5YRe274Rq=1UY}K3O_i48sy!3;GPbGK?66AfTOQHbeJk{PnRP2YM(zCBsvj}#Z'
    'w+<B_A(oqM*KbMXRBXO?ceJ9==L(Y&u_eY_^h=*^XX47hDPmWPQ(iLrk}Nbn*013rX14OoqpYU=_l)(yVsqbJY5U%EmO'
    'a{@F#2TjopK7-NN@Wj4A1F^=GW(zn*kz(cO{2Kep#w(;4gFmxjET_(Am^M(4MBm-39Yzf|ZKkr@c#J+GNQJZ+7a+Q)WW'
    '3GpxfzA<pXY3txOx>aAv_S?(UzAg*ieabrI?~z$vZ;pWcZTRZW#8cKOZ++kFy}Up0uglU^owN?IeLDK*@sPi*Q%(=dIB'
    'ET)*fO+iYEMXCJIedv3G3#u-prR@hC=+mteLUqgmvSk<x>Wfj|Kj^HNCo>utxpbp&~aU0?K1a;pcOXTkX?+R4omRgz}5'
    '@E_~&f)z;*^`}dsTkpD%^hA)p=y;W;}C{BU+jH88jP9L#`SG;lU=sl0UO!drevziWDM}9xXe_io2fSVp}=zG|@Bcn&ny'
    'EC7M_<wluw<(9LJ<8@8v)=}JjpMH93l3V{kH#&S9}MNcA=>+^&nm2OFWyPnZGHjd>-CB1r*doLX4#2xnUEi5rG2}!-1_'
    '_3_(jH1P(QluAIw#kS%d9`o%;Nt2KqwhSMz_gmiAijH9{5x?Zf%<<~I*m>poiC;jeq4eQbEP&-SuX>n!VAFK<0H2IM=H'
    'x%~cqYwzLF`&UiX>}BS%?so_7w?-xz_Fs(-1Nk)5*CgAmC%bOnbap4m%k=&D*SBoe`s9JV-?=ym=<&0BKd@Tk=WX6$8V'
    'c#@et%=VY@hX&l|MC^;~+oGj9+&z-(!8-{;H(gFlcYO`Um{2-PUpbH@`UC0n0aI;&-!mSttDb?spHKf%-LWi2Cc99oD$'
    'd8}>B*J{kD``gz3U?bbu1yGu@eJ{agXPfaM>X5BGmR=WdZ9nhXWULQK<AJ(9&3r0=s3i;8!c%0kwt@UlwM;*Q^0C|k(8'
    '@G(wYV9}uo0^`3p}iT`*1eYfm32?j(y0;8Li=RWf8Lk#xi#eH{Bvo+Sf4N3A1(jXIwba+JF7<w1$tbsK`TG89$oa~U&o'
    'Ju_GTQudE(0(t&?Ie&GG9B?UhmeKCJ79)|fln2JYyA?P<l}f-!Gf|GHH&=?`WC;7Y$!^Ix}WuTDwZCBXa4)V|PTz^m50'
    'UllWkPK5NB<%<q@FSCZ!9F5;SAIq2d)A@nUDb53Q%@jVOu!+Kl6h5HvK81}GHc(hk;XMlLD7;JI9SZ-Tu$IEx6#h=(Zx'
    'r65&_Ur%3Tr47D7-=8bqar_@EV0zDZE1AWeTe)yhPze3NKK2p2Bk!{z73Dg_RWkOyOAyf1>aVg{SGf>lB42DLg^paSD%'
    '7c$C5;6dtDV5QPURte~)*!ZHefr0@WRr4;U`&`#%lO0oWJ3OY}uP)8v{q0OJtDb!KOP-yd`bP9D8G8Ee6lun_JLWV+{F'
    'QrqcqmZG{=0oWe>L_F=w0ToHg*plu3T-k<r%*>BL!r%!(kawY$WUnWq;v{(6fzXrJSd$)9fb^qHYuf3sH2df&?cdD3Uw'
    '4R6x!S=okAUj423o~N~cgqAw!|fwGQBV-&@veYyZXkz?lE6p{F)3Ijr8>yJsX$CPLLiwcYB5RIi!p9f`BTzwOg%M`+{;'
    'dk(^Qh?%=-#Adzrm2aL&X8Mdp`r(*`leB01f3&B^Je*&Ibv*cvLEB&U)qq<oU_8qxQ{3}owfiQ0HvO4PlQ901)8@o$Zw'
    '1VI+guCdBWCgJ-D489tIs@WuG9C$`252A&eE=|yY%Ye$>B(^KIT0~d+96vydg<ZIKOc0t)Ht6ZolKFwB9g&WvU<iEq$J'
    'L%8+%PqUWjs-|(U3m-*V%A#d+UZpQIz?U`3zNYxJ6_p;S}8qROt*~srp(?->+yIAJHco=HwgRpe%%sr+d8L2QHWwt)r@'
    'o|RsV({SH4IU`(hSx3yEYuboHx(b-G!W(6(f-ve?VfA*kF1&r<9X)9OH=PJ(vJSNdw#-5lyB8f?=Q^J?jPNL$%XH5est'
    '#7#_Yw~6)LwyfAPcg*{`4Nw?wO4G~ixr^EfOI{oKn-w6Cu(NbMoP@;dX`2k+%-Hxv|(N~^;8nc>34*gUQE<fWhbzJ~Fi'
    'xYXB=)eh)e``*AX3oqAQ0A;z6`^aQ81&;u4h_mr5W=f34z^I;s)z6XMwfZQ~GZ*8xI4%pk(OFbjnyo^fXZ8&OH3=lR5k'
    '335*L|*eaOM+*Y65SJwspP?26cxcfugH|d6e>!MNn?lGr)WycOeps114eOi$sF03mi)B&xqXT^nJA0{7wziE_WwSX7&t'
    '@G9MWYys!ePcMY^Jx5`p<+3=s~6}W2*%<kF?g~mU&0@!;AKz^>y@)yYqZ0M<*CdnGhK~1oUQnX=^m?o@ssR=IH>hh6iH'
    'TsGrv|b!LR2+S;t#4R$z<RdU9+PjIx13?@^K$hx%zHYi=X~$zJe=2K>-%OhIn$!_{mDSDW>SV^4xRaglHdA$j*?ZBxy3'
    'X8Zghd6+wKeYM%&TtgVW%_=B6P+A<>MckzKQZ4e<W?3Qj^cs@HT{jIUqIG=i0375_I(5rz&i7U&wsrfxf?52Iu5@FDo*'
    'A?U5fFoFY!oWge6hSAH~7*W6y`=DyvZ~x_<8r-KjRLh3si%$NlBZwM%3X;z9%CA_MK{`@}HT*S)EB#KbsADWjrDOjAh8'
    'Ay!i-u}JwdH8LLxcw>gJa@7duV;2dF{S4+#@kk@Kq2z=aPi7f2l@D$><(RDIPI!r+IP)SniWL82Lvo(E!h9k3qY|Z+Rm'
    'mA*0T?LoFDVlx31&7{LPH)9>*3S!$wa7e<dO0l#uK<E1JjN^TkFknul2QI1yOcdh5vAp@wZ;~E!HvMT_OtKM>1Eri|c1'
    'Ro0QvyOHzM4;dniW&Y4^vorxuy1VSHUe*^oz^XrhEdXa$%3^L^|iaV3qs1VZHS;cq3?c$PNZ5$rly&DmSWj^VO$z+w%z'
    '~oa!%O<IRQDmZS?3l1}c=!9X_8kkGBblRSyiR<P!Y>)6#!)Fx~!hwz|2;%?E@Tc0dn5*EAY$)JFNlwO3Yq{Kb*PZNd=4'
    'S?rjvGnBcQ=blHiF=A%V>pFNSST+!(^DH}BTpvBC=f;YCcCn6_vZ!djpB{Hx7=@nAOftF@R%pZU0hnAT|D=c(h-A}OWw'
    'Q3m#R-B7`j=EV1?kptew?1Hv;@brWxhGj_8~M~Xj(_9wwV0K@%BvAhl>)iv2~$@xtRWGIk(=z*s+=*fjL2ZqsDr)Qu-b'
    '|wc=wuf(zDvcH)AY<YS4#k;*(tl^JDJF&>Dz(DZfP--wzpn?<VpO|BzjKZ=bO>MIz`P3j7m!usa7gi-B52FH`TLI*S#t'
    'nBc~tEzny)8|ZhKyS>IW9%pN5Snf!hiB=6o`^I72n8JYk01K6v+fcL?a440%0qxZOc5Zpt9l!>CYCmDO3T?z-Ku=V7hC'
    '6lf>mV*Naf#d!V1A*Pd&fAkW$<FN0whBz&$E&3dt+yY|*YJD1NZhS{Qk&8=PbRaNVo|%3F;94EAnaZBk29Fg!tM;tUUW'
    '9q%9X>6o%HXvi3`5qs`>-6uB;EPd~l&!`my&sdPRXsVWO+a0WSA)@Sy#4|#3nQnl)D~?<FY@J;U#9>DPe)?2^YEhNdD_'
    'hMV(Pp`f)PD@kS&6q`3mC!|kP9K++v~Dc)2z|MDh&;@Mef!AfVDcl+#Kav(E7HfHu+JPvk}A3!^RPQ{9OuCml$n?Zto_'
    'EMq<f2-s{3?$OSwYFlYU77Kt8$jJ*U^OuzSTTB`{^CVct^&RN^haV@eX?^6#z@h@HV*W5>1!4MCWihjq-hqPweJNnUuc'
    '`Iy~RnE(-hwo|p`L{J1SK9zE$e&7WnuywP{LP&LS^DDwO}lpc6|+kLFdO)-_MS{)$xF+a12*AFaZZHWY0V@uTu6<~2!0'
    'qfjkrngc=hd@t=Bd^w#fLzIX|?;9X+>e*n*&4{e%%d^^Fn@rmK`7PVv`(`lL@t1wn8Wq^QYh-X*eR^^`t}C)f<u@i}1d'
    'sJXA<7^c0JY&1<P(-sHzz8GErFLSj$nxQt_=~VZp_gl@x%f|Y0iiuH8t<X36YQZgz=BS*@V7TT43bN31tJu|&0vX?mat'
    'a`y36#^=o0O+}bO{hfpyH*5zToG9I6Qg1TN(vkWIj8gWVz6fd4|XKt40qHK4G@+@%{4CvqZE6->vo^ad&eFukP;XeQF{'
    'xGyr%iyLafW6mY<7%P29PGW$sPVrw>;B#mut>qIEn^u&Oc&oLfTfBHI>o}0sAb0>Zy4b$WL>i;uIr>H2#Y5l$Ozi_EVl'
    'm4lj;&tsPnUo@Zpq?8g8<KM~k`h8nEHmNuFi(M&QgXUgNfS6v+D~a3a9}GvZTh$ghtUa9CQ>CYnkv-!B<{}T!2=sgkj<'
    'ySylCM<454dPRaXN8=^*?iOFzpW(nY1H{^uM@rjn0W8&e!!GT}g~E-@j1$D-rO{13^^8lK*M&_lCkg;&__zswZ1ZOacT'
    'mqx}W^Vc2^1>7Joahxf{*#+#0YP)Zo;E3XxuxECJSM8pk_FM>g2X<9Qc&@unbI)eYRD$rmqp;GCQ!6tHfX-oK&&WzAH2'
    'i4l2%&FdVCNqJZKYVjM$gIo_Y5JAG!JE+C2stMV{hS%NhueE%wV$C#YKNX-6otk`!cC^2L@KT^FDhxQ~)9$N@Zf_{;h('
    'rguOO*IvUK$h$QhaPePj8V`A!V&?;I8`Alpy#?zRu=P$Mf)~F`wv1Hk>i?shpPo9^VkAJRzMmyMyU8mN%&I`jJ$8PY&Y'
    '#{MmQIW&Na!D(A{jL)~@CRRP`Z*|Tl9}`~htw6@)3BIN#`+8y+k@7d^zeObe-n6d2}KsgZ(-CC!l5MBrpDL71$=cN`It'
    'Tc$AD@`QH%#-`K5!3)Txx21~Yix-on;K8fAFPMPqh9mh{)lav=l|MEHbCJGV{mDVD`(-<Z?;sjr<%YSw1AhHClE^5@4p'
    '+CJufm-ER^oO%)6%J{ArKw$)B|JbqjaGd?C>9nWxMotl*gj|GR6@Y$ji(G-(7Y~IhWaKsLxVM11$a+dnU((MaIZ$HP#<'
    'fI4=by2c^pohgZIJ5NRycF-`f&1v+%Bvi0`8VGW<IFi4RwEwLKu+dOQ4$Lfm~?}^C~SCZR3rZo<SXuE8cl>;uD>F9WzW'
    'u=BF1_&6JpauF*1tUtC=GVONZh(1K1SvS*{Ng;z{)>{7!%J-zh(FP8|D&c>d)p84*Qj5&;P+LHDCjzBvk9Nniwd%@N9$'
    'k|(&<|(Cs-2~$y-?p|*_>+)KhCap&kzNB#9ccO+Jx47Gg2!zEqrT*4+gDgN?Vk23npW!fYAQ(eVRQNG!Ic;mpacSR_Hj'
    '?Sg|_QWreg}ntm?HqdNa+JEM?YxPx=N>)?&IeBrMuC-Hgd9L?;mbPr$|eKM$CZwMW|IK`0o0NRakeL6{CZ$<9WRIEUp+'
    '7*?Abe7{0X$O!#;2lQBUWrHfw^m8I3MPGx>zq%n%dgN)yBy8zDX)?)^#BIOhn5|drI^<anxQI1IJIvxBSJPd$<_));JR'
    '07tLBcUAWB_}TuRUUsnRInFSQl5xQKDWEY!HxgWSHes$lJe^-I1o*v#u~W+xB*|^H-Ads`TBM4VDky?-zq40Xo>21K6A'
    'y1*I}Ilq2(YypH$0Hoo3ZUW95Vm&JIvGVNp}qDJp$K|8T(TMCENg0%6q0yAA(P<wS=dMlyJ;!s?xM-NptjsmlBPQN1`@'
    'bC-G2H5P79j4${N0C6^q@YXWlvH2$N|G-HZJB#m0e*(&>Z3+)0V5^Z0d@_Pbp7!K(HICbrMyHbj(X&;J}9Jyyh-RU^g1'
    '|h>J9_K;l`=5XT)0p6HZ^UdhvDd=ebQV8Q&Sgl0Zg9HoQ+$Lk9|~`RJKk(j8T)Rx_XAzPJ9G-$vtPxsH}Q#qcImjBl9{'
    'fXOj6A^V;c|NS5tv&uR^sa8PueTkZ|R!w5OA(rO21Ce(_fCYD7rwiU-rVmcVn7jNCiP5QCS|0Fgy{n0lgyn$XUtJ>n$!'
    '@>{?0HF|qTKlQ+P8Ae3t^_J5UJh1$&?1j$Xrm>VnF-K$yY9<5p-p7-{Q9wx2rL{>s$7mj0WQ_GbM7*nDI`b(uqC>vB#T'
    '^XL-7njl^q~K9AfHGa++A39%?VZuTtUXR|b|awlBcMZ5qisnOyNnRGe}%W2n8bvn5QlLrTmsngenHWK9vSq;JbBX@8|M'
    'WqdC;EcvbNTpiJ3wJ13qqW~cDCXJxi#a&Ml@2yp<%F4a0+N%voVBh0N6&?1@{eDvbx5k$v-u84M{<&-Qz{^30C?XDLo4'
    '|u-ltyVE$cEjAUk7QNpvj&R5(&yYZo@weWvlpnr2{j8=~O!?6dDQ&k|N{NzL{BMmdNFX+1I89_3>V*s?O<J3oe!`VO<V'
    '2gPS(a%j2?g*O=@{};gAjWDj#=Hk3AslwgQmG8fV?#$E$FR`N}iT=oh%x=!LQX0`3Oe)`j3*<C?Gt0P$g90v`f0t9BQQ'
    ')M`6sMx_!pXCU_q_k877Jwmzl14K{Y?WYtETGJ>5PhRp6!`fWRf_8jKR>8%E;HTnf%fq!W`*o_zVT$Gu)DZ_1Tjk4Yzj'
    'SZ7ztV9Pa0II6fXh;_;cw*!UA6E|HxiSt~jyd-1g8@-?IzE#M4EeOrE@^78qQlRem79boA;qD7#(9pF{+F{3lgPR%43w'
    'Ty?2rvcv?@dr?uxUAM|ShG2l-Y|@GUHA31RY{X{CXi6ZtjkDxO|97#uaUtcZ_4L!%hVjot55|m!R@v&MRdEYJDUD;_In'
    '(PtU;CUtO>X|AL6X<u+X+PYI8xR3{E)w4^BEhVH1eY!68y!ab1w<XLcOAFAAW7n}B;xY1&(nO#~NK3|ii58$lNl_2k!!'
    '04LbDQe#3?bdvk-IQAC7fIaVry$bq=0E~BwD~X0u??PnTar@9>j_8`#dI`3299~z^<&wV+#hcHC%E&aRr0+YnzA-dB7l'
    '2N3GO@}#qOE6&GZ~~s5dzy0IUxKQUbuIjT)TAV+~gfDR^TzYk?rYhMp~cjL%Pa7r^kvOa+U6((gGs##Q-=sv-r+ak{tR'
    '<mS*cC5ipdbe@|bPY+!~C>!bH|g1sJ!76d)86P8ltr^@zCZ6^eeszc9v+G1pl-W1H}x&`StN%B<uuO0=p%g#x%%)#_-D'
    'U(fAPQuLmn~q~2THoo9?@}_gv;;>;5#=Nqb~Pw0H<9y>`^q%o&i1*<YG82@#iUszJ^($0gLDi#CMV%g?`)oVH2wc#!B}'
    '+@A*B;S#%_0!VOu|%wf(TBX6q_C9VM)KP#^&55|T_Zo95vYk~C4&3r;^W)7P%|cd#EBO5@LLLDt_CO%lG#6f^lFqit<x'
    '0&l7)xYg>%Zdpk`&_EZy`5pU7D(=oqXycSF@1w)9B*A}x%@Bd>m0i~O6=KYGDlyjGm8Qpgsz76RWOawM!)nrM+rFB+p$'
    'LHay>Y+KsQu<i>aSZl6ZFuoNT23CCziaEv64W3XxmhbP0yC{?ldBCVkFU`*~#Zu3m@DD=~W(uur6^Ze5TF`O+qZGVX{S'
    '>9%uWWuW=|+i@C7oxx4osc}hl#)YcfW6hCJOOTbk<x5{<Rx$A)#l&>J?K?9M4?1<#AJZMIZZnQl%^A0Wbc+g;^gnyP$R'
    '4Q61x=%%SOVRnZSdsye(g1#HB*k;t5Nvx=?$fs<<D#Bsa&9(xnrSlC7NJz<UxSXtuaiqe{NnLh_R({$w^4SPyU_P-Awj'
    '<40~DsmWI1p^baAl~Aqf+otaFOsN*^LkX`XdqI?`j!$e8-v)fmD66s=HxSpp=h5Y%->-xs{`GTRm{PM3ef@+7BB@+l$V'
    'S|Q7Lb{oQ10EpOWar2U!d``ec`-S$PrN73Sd?US+v@4;pKC)GO(Tazkmc)^eLO_EvYgpAmSVz~X3K1T(LX{;n_bmGS`!'
    'dAL3q=@RHy+$w>S=yS%__edO!uStw?o!fkk8G$-f2=58-^=uOj$c5SuiU3J<zp_r_RZe4=EWRCe_gk5jgNfzj&F6cO0Z'
    '&`?pY#?S`UW#jm57o7tzP29Ml?zd<)@$yZ8`Tc%g~b}3J0V9hAuO5*t;aO_7UMj`8pxm@z#iJpqFT0ZnXm&b;Io?I%ML'
    '*-Lth>)-f10C!jUJ$`lM6}^BV|+`I4pA(*<p7!sCT6_e0(Hp@DGv2#IeP#{QipsZaWLag&7Q?nre(nn2yc0EOkTtc(;D'
    'm*Xqj*gj5SJDdC~VO^?#>Spj0fX`gVc_k0W8}+eStu(uOqTps8&<F*gjq`}*C9hHJfS^|`7Aa_h;P@Cbdy>ch9#K@|g<'
    '3emNU06`7z!7(M19DK!qpNH=jC?ftun3vr?m9+m~@APY4iA-YI{+_Q*HNYa*FcE!aAezY{7a^nroT!r3<F_@m`mWW0`J'
    'J(vn7C~DAxM6qfo>6IiQ;pX4=@7m$s5w<3BV-pJff2Xx&f8%+pu*bWvFzm0VQy^JE*$ADrQ2Isd6D&NewI)jW`j<o!d+'
    '_oP=QG5DlBg$W2XxQUq76>XW9bE~Mz=uM4xm5xk422QmW{YzyVuYFGE}JnO6o(u<8yh#~!RbPdSkEnRrNj*6>klqp!0;'
    'e&Ay@?wNUu$J6~Hhtfcv$VsF0rh9j9vXsds2}T}MQh`h_+RvJz1OFe@WeKHwHL1-RWm59?*Aam4cx?Ka**8JQF;`{FJX'
    'rk94&<rt0B<4>9bZ!aiuXbcT(>LJSTT092I%$@L7z&^!k#6V1(lCjwly;6YG&`j7E;uX?-IHg9$=}>2_f&^@OfUsGw`1'
    'x@=P*;G?j%uz4%5OE-;wg$a(zPR!>1bV^&(>0d*_s+h;Mtmrc9g+VwQ@TK;o>wAQUiXD=RPp05vB>pX2nz3Sffy`}VQ='
    'k-}r&bNx(S-qUUL~I4bPY2av;#+a+%ev;8dZ7^K4a*<n5S5acBuKw+QKzNjR-xYchw<UtlWAsIs67*B4bj5b6hw(z(FX'
    'ztZb_psl-XIX9xtoB~9h~sF#69(lyMX)nkbID|=pz*}J$FXWmB4sfIS{3jPna(ZZ^{OOhD(Clm&=J`IdL$TXJFMk$G|#'
    '-bKacq(}WN8vybFt7%gAZH`Nx_!wKauV|S!=>$7*7Tm5RvWs+^qpbu!^6+!OEV~LE~Mom!N}=x6nx!U#<v{gOOm?4#aF'
    '|uWXD!V4h4(hO?!uRu6|4q(ANPgBxbhGM1c^K3`KXbeFA5wH}6OY*#eI?zxx5)ls3-`cM;$N65c^~-P4hlgC4QcJbbJx'
    'ZLaz{ExE_WTEkb$b!Sb_*jFjyOKFkKuwqSWkVMz{hsOlP`7p>;`LFc?M@?5_hlo}4EXCo?tsuDrkwSMmXB1j3=f{kQbY'
    'ZV4@9N*=qNJx!XZ;9r1}n}|sHvQue?t-!ghhY7es{YHCf&_!njHCl&T)Tnsl#m1js9-29$GMG?SUc_ykupRqaFIAvl^d'
    '9Xc!rh>FYt209aj0N{~d&l5U<W4Q)<%6ez?0cO@jQG){XudLH*OV*Ncp{;Crm?o4nR*jk}Cl*$!uu%p~MFNhu%N<ztZ8'
    '~h9p*=fG^p6P#KVZN@7yI{j?b*C@_r(sl;MaLx;R)ZgtD}+zM;*R6t+Di!o@2;Mi@e8w6CHqWB+L6tftr35icDuk+F__'
    '5S&7F$0rm`ns<a^<>qE$gF<Ao&h4xX*#^<zmw4M*UPC{QVq_FYD9ufUaK0;v`gySKxtqmXRv5dOjcBpd)`<t;tf#j3?a'
    'C_opwJ|=#7l)uk9U>2EX|ED+tA>-hREFE5;M)8yN3LOMS1zgzq#VTjNgWkrUEQRFqCU?Bobu>VrJ?j)WU!m*s=9;$(+3'
    '65yzL}O<BXEQuz&KBWJAyt%>Nd;D;BCWx$ZN6YriOJ@3{DsVJC3j}haBY@2{eFg=LgZP#x9Ls*k^injGEuz65wbvU`XD'
    'zEo+y;JMG_2Xw`n#ZyusZ(k5la6e$@YCi>&86nyK4ZaXF>VK)*$snr3^1tCDgv^*}VD*L^8-PuX^Ao>7`%0auk6bqbe='
    ')q{lcDRzSS4B0yyrVM8TDRlR$AM1VbOt9<Chd>hDKqXEMLl0#M|jvLCLb!J_Dr|fMx4PPK@Dta+N;QY?F%dWIDTeXn#g'
    'i-pqZ1%=z!yySUfVLSD4N2!|kPW7)Atq(k?KumtV)r3;$Su6Auuy?gi0i46=u^C#GKDH`ul3eipT%Fubcj@w$yGc9#B}'
    'Q<%C6*BsuhBNP(jFlAy?dhUNzMEDiRo7zBk*^$@WN@zzw<pw@EAQ=@MfQ-P>w-3JY_`YUqwALe1SuGBx*rzy5#{yW$!)'
    'msmf<g_H?~M`LIp%`Z5{D_@W#7`nv2W~MK3<qZM@?NT=HbNhE4hl(9oLT~o8&%(hF9st>Ai1~K}dQ#ug2xW!|a1%-N0%'
    'ID})8^<?8K5Yt^@w*?)e(U<B3QQOn~0OI72q0Ko~^1ip{IBpfJPMoz4$#%h+TP7F*lz83g|C=%Lk1IwE=R=G=+lsE`*2'
    '(yL}Kf4#&sCT(6!Y@;-bazhzmArJpFoO%~?f2CCBB3}R6iTgL5~|Q5HLwY!H%&n0t`FZmlTWa{V+>&@((KeR$H1N%69d'
    'T>8v#{BiE95dBK^L-4-vl>BxhNTYGKVNSbh=Q&GQ&bsglhx$fXWs()dfUGUfW-sPuKi{PJH9Io_@Jkm8^L`0udEtq+ff'
    'g>W@wq;VYwVZG{iMDZaV-FTmGt9ej`2T~k>5$eKk^vUi9nU!Z%)*yOyu$|aIyqG-8hW<~rpGpT6zU%fI0+apn8{!Hxo_'
    'q2Uf6YR!Yk?IoVjNHMZ8RhR#k{F5tr0jRIX05QjMU$5{9GO)XPI`}yz12vndM&4=H{nH4n{17yQRHy=k@5!&Z)cliMDn'
    'k=nWEK7M7L@xg=rV$V<0R049|+g;+-@PTZ6{t75nX_*EI01=H3W5Uj`?HQKp-;Gm|B4$2mvWiV<I2f`Gg#>i;7NuX7KX'
    'Mo|g-Ox1lowE_H?mjC%M2^f*R#m#lRxn>%)+x+(S{eX8!&^=GGx1A5^xVt&;lgTs>OW{%Ue`dBm(LRW416q>Opr&25wy'
    'Wxx;Fe9$wq3_><CV#%q&ci69@pw=>j6~6x7Z)iWvfm3hc3-kp_b*Hse2e%h-+7j0>ar4qx|dohRoE;>C#b2WR%5acKd<'
    '+WiyK1%PL(_K16|je64uC=NU)iD~lJ&2z?z_VYwpE0lb*!&xN<%VSQIB)G+;@>=7p;i|2gb;Gw#C3g}T5_U2O9s60#Dx'
    '!Z%68|$N>^@i;n&4uoCmnoeRYUNtpl?3rV1kE<%I-OUY7K(BpF!{F_(uSR|L)GF{^$249G`S`1!{=rIUZUUKO1R(*N`f'
    'DWrjZ5JJ+O>5@8jpBBf#J92K7O2_VE}K*gR*Z#RVt*pg6nruC0j@Uss2LpGO-?rW5iM8nn70GlKrci|$JEw1K5@;3c0^'
    '}clK*#{U@t;rE-__M+d>^on4Zg2;I0J_tfuCx&WA@8hY{`X*~)S$wgGN(>A5K8WpQ*Y#edq$b@3I55F?M9%y!(Q?DFQH'
    '=uKtR&DW;HHHO2$jfj|1y2H*f$-xrm#r%J`m{Wb!X5;QTMjMVvMd4<n0y1c487`n9{xAC6|4HQM4Z?^>f8<L>M0Dv^iB'
    '&W86VKOMC(U)cJ`2rfSO<f^Kc$ANgS%umU5jrwB7F6M*k`N9sqVq4E9w&de#xB5c>>4<&p$mn!<&Grz{y^Tzcjbya3+|'
    'p$1X6JrvP8Q{`ZNAvXRB2fl;)dW`QH}VV?1lsJDGDJ4f}$WWe2UIG|IFgZH;LVxc~9-tDAP&O1#@jl!$BvYCbl(XII${'
    '$LS>_jYzzBzCZ)FerwC|0EHV6GFlM>z7xBm#lM?9=kwsYOz#Q(}NBQSY;P2E}twkHJy(pgozs5)u4EwhAwov`yoEt=->'
    'D81y_taLW62017!e)QX_C*&_t02Kv4P&$%h;{7u{i-lQrAoA9q3PH$HS?M`0}Dd5OS8JkO#oIpFDA8y@8|d&yVm$VRyB'
    'X*w%qpOR>$UIW|5hAM8IdqLvKBLrflb{uFy^b(}vA}SIB~8gODnHctXyJ{aiScw0E9D0Kwa-LHdX}Ri~h|f9)>^CV<4J'
    '3=UiRrXtq1LPx@iefOHCo|=67<}ImBBD6H<lWz^(OFvIdfl>f)tW!VRa1AT8i+;u7RK@Ns*B}tiKkzswaP>ijuvYy|5e'
    'xb}bZ-~rFx__d;O~TZtbt2Xg)hejjf`8LAp4?kKUs_}I&aJo+V;4NUt|3bFhss@*EsOg+9WLoN|KFkX%A*s7PIv@3P6v'
    'e`hnn)U%75fCL@cnAmT-1H&;-Fdd2S)Fy%_7C_0x|wz@h$YnaiDN@pSE;D<-=_{OBAor}@#b>E#xS}1QsxD;9c>FEL~&'
    '^0mo5ZBb%M!w}vo;T1B-z73_tp+F(;D;i%kAXM}t<s1)8=BGA(*RWv^76x?Pk7@@Yn+cZJVfvL$tNj+#slPgK&6ahjL?'
    'VutQ(gd$uSadEb|6p*n!x$$+?6WJ2THQe7O^}*IJYu8ybtjR_C1@k7?n5d`;1Ez}G3o{5gg@5M>e3cLv@fUhRpzF*awn'
    'SkB3}wenlC6@-#|As$zpU(d%fobB`@DhlfNB1EWQ*Xu{Hc27F0z7ki{@GfPJ;J!av)-Z5|g>!(#!K}8`p}}Ldo*X=&U<'
    'rTOK&3rp5FHpW?0^F@E}aWdN_i1)9XY)kqp!G5kE0|`;Vx%yY3#`&6>42zgQhST*TOgJV5HnzMWRays2`91&(a@K=F9R'
    'TW`YYy6+d@zDB9DGByrsI1U}u02FLs+Y2XeTDNMuiceg{O=<b+^_r3ORf;~u`UWObV49;XoPCrna4AQ7DemNDo(;80H*'
    'wAlViJ-K@L!QLrrP6gtupPqG>bq|6=)ZViiRK^$7Gd5=t%6#(#}MohH4oT_+%L~I5)}Y{=j%s1XO+~DGC7%X1uPK^e7K'
    'W<Ji4aUQkJdsdd6R#M8^*|5FVHJ%CZMN^4f^*GPH-9{-8|g1KJfG?`x3fllG_v>za>pUUs(4j;f{+>$CE$NGg6fmwPS|'
    'RJcxp5dUMC4Xw0%Oc5&%cg18C9V|K%0u_f?o!*xn1d%mDJ>qGHQuUQ$MgHlL=)(+alI4(26EpegI@xz~9*wo~JElr~T2'
    'l2{c7`2RNQY4o#;_~D>yCz~{kE$w^rXcO#{Ud3!D6o?fsMJ43InT)t$G8(M|zLU+1oKEIsP5wovT4snB|VA=};N~{th?'
    '`qTfP{M57gc<G)-=Wr|xDs!M7Mg_RA(fqDD9P>H7+In1DHw3q(hhL7wDA-;3wr$Mfi`IQ<b+rlFuN{_e|2bMnb30Fa5)'
    '?*U3vDy*%;eG$n9Yl-VH9wp3{!#IYXBz9)CxT>G&!?vt87&yr*2<+&=Zxk3rOw}<&n9&ovr<@XN|zH|l1y<5a`AUnm%9'
    'cesJ|{>uAgg}&X1z7bW}8&Ctg9|bqFAUyD-lFSAy$hRa0UPyH0;4x4dirB{h$huj?6swYZ$w3ZTP`Q`P{#2D31L5m@rF'
    '0{PoB9s(=4<FMY+J{G@15PfTMnvN-veHSxFzvxxpY~^Ug!8z-N6!9#$sMP(msxM(i{?kcLy_7eYXT<wYLs!zm@*nL;O|'
    '=8Frn@r}rZ1BtdeH!^pgz)An~w@D-!b}?7_hjWqrEp|4YdKYQ6s&bmP8)88zF92#Ogx?(*qx*R|d-e>e{+#3raAI;{NG'
    'jT#lL1;dM(1{=5|+l-NyF%<>vmFlkLnqHVxs5t{oDgr>4=@M#nE&gB?896ucMn-4QtWKTUZjXVv?uk9ZzrBtz7%?QK?#'
    'gJw6EJKTk?<`nx*YjoB!&zjYSh;ZMXWdh92XBG50CnI)9xVcuQeCk?xc<fQDq0(|*hTZ;h*y9X;NBV7SRK~uZ#G*Lz;X'
    '`C`D8~jxV?!=Tbf3K?p4RFW{9R~G126#yJktNxVVLRp+$ZYQneR2;TWTZxQVqwOiamo&HZsNu(?Eel^Y8fg@D89Z@<Wz'
    't>L#9Y3yxP_Ow+e7W1(nZl3+K{-R<;6jWRJwR-F@gu6!r1jE!LPm>Q70T9vF-^l<WpjL%R-rXbjwFg0K*4mWAsoV{IEg'
    'Kzg7#I<RfuGvgmC=?sAqg4^<Dh(rz#Cwweb{b<Z$FVL(k{e$1qOyBdwN&~&}0Y0HJ2M<l4FuWtTr@cP|%m0WVh~tE=y3'
    'Qv9wZ{lJB8FluU&ng9|)GG2v#R3j>zs7nFA7-K3A&m#z6}Y7uXzH68NGeKaP$c-$Y}IeF^~^0k5O5F6+vvaUqt0`r?f&'
    'Ezt;D6JId41Mtrmsxmw7BWZimY6V0Nb&m3pa7SN^g>nPZ#F$gdn%Lk=`6x+-sBD2xgQk=6u%B+ZwdC4**?zPGXHoNNa>'
    'q1!=uuv21TySd77;^3>QMv-Lr#fK-pk48Nk{c`rlN<mbMlmeHTOY8^=XpNRHv@`nZYJxhfEF^jFZ?<WoQBM};ue%?f+`'
    'Fr{s=Xa8MH5>3MjzC5wZu*R)jD*B|Nbt)CJn13u=YCn;LCnhgEtRp&AP&@8ABfQzMX{<zo4r?gRLbMgCQU^Z52Q9X?UH'
    'IlFjk`UF@2jZ2ahqEay&o+^bz8F;hFL#N#$;D{SUD*@AGzRrJ=nUCE(OMh*kCOX_s?UD1yw{E!XdS%HUO;SZH-qDGEkC'
    '{V#E%`8krbvd8IZZP8$BqLQ&<eh_1{;YzPl<buLn#gLg6wXJthB9Nu`-J+E=h#Uy|59H`FH7eRt5R@=Q`)Qa`v0A`DXH'
    'i}M*@fuNaKtMuGJ0$@EYP4LnkYI630o8>Ts<fheEN?w4EW2d%y0K!_etHCDGVom^gY9L#WV`<MH9|qWOFl8_K?Ve9tVa'
    '2)=FPXv_E?L|6ttGGW^9-7@9QS;^5Jn|fP*$FE<jgh|D9=mrZXF_t5Z7tT8-)YO~eAUCc_aJa-4w`I=Qq*8ITWgdgE_J'
    'kfNzmIaeNHKwK7;D(lsgYi3TVQ8Jes0vCRbhWvSd<XeU)>t~rRq6^)2cuy{>+yH9Rdg=+KY4q2D9k%fMm0|R~+1|B5$k'
    'CH$JBPxGhFCiJx8Ex2;dgJPJp9pv4{rhhT;j-PBth*Tnj_j7gtr3FuOI~!6I>b<)jxO<appR{IkwY__N+<pN6*@OQVl='
    'RYi%8CD;vqZN0t}`GLBgtZ5>N(Ji(nk<*5MwmkvO4V({Oa%T*11xX|o`!ID{8aQGJK$flGtuQLf~+STjg%3}jmVuu&}&'
    'g9*1zH@!k`CGr4p^cBo=^oeq#xOxxBV<zrM9-DheNmZ=&ro%nL<%FHywgD0K9}qn7xX$5*_KUL%E)vjE8c6*sNAQOhIB'
    'poNb<yM?wQSi6}U!Ug*YMe5$`ykooR@vR(2vhqt2~|CT>{sbs1bo5w**x)n!ds+)4lI>r2sRM}^=U>i0Ms4i>U8{HN6q'
    'Ci6qVJ+Bm)4Y&lIv~i~H;tAcpaOrl7COXZbhfVL!tU_w2%q<`!Y|macpUSc2{?>hM?K@QUPO-I@>gBXiYlT96hjTGjFI'
    'OaxsSN=5_pLRU6`+k|P*fj>vP@eI3Y56>el!egTBT5c^3g<8Aiuifl?iml+VvzG!J3WL%|qvHh1Fg1oZ$q<qQ1{N@@*G'
    '3B+L=9^NTexaFt<zQ&Wz&2t<QGI@jXUJv|29<@heXUJjH~|6g7x)9ygoYM4{_{D04MvqKz|Xi;XL(r+(89x%p+!^h8)?'
    '%Zw{f$@%DkLF0(u24Th;~{*u0y%cJm~SMw(utk8M*Nl;!)29pr}?m(EH>hh`&JL<R6vpSOfXuYA=~lkvqlS^_I0j8fd0'
    'rCs62I;h4qOr^s~*wG%sP`TK3k^Jsks$QY7&hRJHv0QIjj>DyaQ9kFW;2QzzLQs3N^?$e{>2rsSYl{MqwF#1lNmrv4%U'
    '`8HgOwJ36r*J!r`;W^mZVdGZGX*xz=3=}I%EhK}3^Os)Ew-EOxUVIw0Jp=2Wn~Tl8|KtIIj_jb|2sr~Y!(ARJsuIloxa'
    '=-Tjl`ye0CsbOMzZ@<4R@0Ey920ipAr5O_2vs5DXTX%T<JQ>^96@SA|R5OxhLpsV*5|_d&6*-Mxf4x56L1CVTe&6U*Zw'
    'O;*oRYxs_(5@aSl*v}nml;ZeTxfKgdL($a(IQkcC6Dbb*NLeKv)mr&Wa2#3zeK~M4NEmCVylfc}^xPbxf|I_nk+YzD8I'
    '}%|5;gh;!uzXExCgEEKrfH}0NCY{sl~QJCG<X$?*M)u&pTrjLSPUVc-i>^)`iG{ns1Szz)ydy+=S|B^?A+m!r^ot%d{+'
    'qSd{acNXw8C@fM?S#{S1HsXL!`#nkk=l;d=sMpiX`ny6kOhk1e*->~@UnrK-K%q0WnlTAnZdqIk++o=x7?GkqTBL>-q-'
    'JIc#TsY7CIn4E>9)edbu3;D~=K+<MG-Xt*uV^AkO<PJN&dHsg%1lzdU7?W(%hZlO}RY?}ws?Z49#a-^KdVa)%u2I_}za'
    'wO9A$R6W%r}y!F3N}$E5=&=u_B2`BjC{On8kwzp27nhb2Y5q)LCH06wZo@UP3+cvBz3t&l80DK9sci?VZx)xj0$%w<PL'
    'f2L7z(@D$upuux8dT`EKRs|#&4@+V79iF}Cj%Ef~=!GB57S0s|s8l|LRuje}<uN7d(CqJ0hpey<$c_eJHhI!m(^GGsC!'
    '|i62;c|NV()2zQcu78&<lM@Si{`E;3BzUYe;?+LPoF2i8aWTCqhVDPn(O0hind_YwO3kKY8b{RTAwR4LBVQHw!y$|nUw'
    '9=&q~~X|6dUTp-%j{<3UBzm|9%UWU|wk;XR!e41gyFH;lDns-LoWlr8Q%wrC7ePvKDT^v|@pks(TyQs`rvP1@5=T@>GB'
    '@S)5NbBoHCnM~S%yhauke?)XCmh7wl3dh*4H*E;8&RXxhieuTRAP+i1zc-wp>X2Y=QsD$qrsczQ!X1v&fE57EDk`sSK|'
    'V=H2;r@taxfpbMa|bo5R$l?j_^a|elN*?LA<Op8?%{<K~F>lBwHJpe#J?Kg2i~dlA6oR)%cFfRCft0fh(r2d{BhXrze-'
    '=dgJ{OCkT-Dv*zC3L7J`G5Vb5;?3LuSK?!FZ+I2Rxc|N^M%ZPOGP_Z}#{YRldM3I^WIexJxmWk1k5?J_w%zD#bW6V3as'
    'zC_<VZ(J61U7u15nAV;-^Fngg&z+WDifQqZ1h3~X~D)DC~eAZEke3*K3!z!!8O5R%^gEODo9s12<Rwn5i3+njvgTcGDN'
    'BuriA?nq<OyX8eK79NSW7?bn(xMB05?DqQONvRA@-sJWvB|KT`QJZ0IfU8DS8MIO;sCuAGeYc;5n_kij7uz6F1)3iI2A'
    'zD@pg-N$=vl)lCW+06`vm8`6Kg^WH!Xt0NRJv`1Kp62Utadk8!1f3dVuK32Ra`5CeFxmhkOzF<YIZ0k+WAm?eHt(?kE@'
    '6tT<me6jet<_Kq@mn{FCbO?h{6?L#7!eU2*#Fm{+kaG-<HC0@@DOR+_eQOlavvCbiL2gm#hc>8%Z*>Fsq=K%Q0RUVUkL'
    'l7xr;AUruHtI1Swdl-KkPj`bS)Sodv2qbH18w%@XU9q%Ju8|Ik(q=iT`FU-j~^gc;0z7VkS0a02v+T^Q}&<@d`<T1QQ-'
    '}fjelHy81CP*6=VHlpl3Ynm6^3kgobS;a{n}-dECQ9+uh5sw`Ttn%?X5cYkCR%`-@Z`=r%!1yOq6#FacYvh>X30Z<U*Y'
    'I;Y*gypvps7*6>a=U8U^Gtd;B$Pm>rvb#Q!6#E~zC-yPF<Q@r;X@TTaAT5aS>6l5;(Lvy}6A%!|Jn+{|N4Q&W!9#-$5T'
    '*eyqFv%h6{QQ>XjP@yIE%2zn)zK20eTP(xPzY88oL*Yfmr?*~0hdjfPRqrMDs8f9HF_5KLW}376d^tE>7HVW)=1oJ~BH'
    '7oE0?klk6x;2+M4OPRAu`Fl9Gyhr0zwT1YheAD>8c2tlsOx5=>kfzB_n)b000004@WyxhA_Sw00H&C1dG4~)3XS=vBYQ'
    'l0ssI200dcD'
)



def _embedded_aucdtect():
    """Restore the ORIGINAL engine, silently, inside this app's private data.

    Zero external ZIP/download/engine installation steps. Explicitly verified
    SHA-256 before execution. Never overwrite nonmatching user-owned files.
    """
    if not IS_WIN:
        raise RuntimeError("Original AudioChecker engine is Windows-only.")
    folder = DEPS / "auCDtect"
    binary = folder / "aucdtect.exe"
    readme = folder / "Readme"
    output_map = {
        "Codecs/Analyzer/aucdtect.exe": binary,
        "Codecs/Analyzer/Readme": readme,
    }
    # Never execute a swapped/malicious file even if installed previously.
    for logical, target in output_map.items():
        if target.is_symlink():
            raise RuntimeError("Original auCDtect component is an unsafe symlink.")
        if target.is_file() and sha(target) != _AUCDTECT_ALLOWED[logical]:
            raise RuntimeError("Original auCDtect integrity mismatch: " + target.name)
    if all(path.is_file() for path in output_map.values()):
        return binary
    bundle = lzma.decompress(base64.b85decode("".join(_AUCDTECT_REFERENCE_ARCHIVE)))
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for logical, target in output_map.items():
            if target.exists():
                continue
            payload = archive.read(logical)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != _AUCDTECT_ALLOWED[logical]:
                raise RuntimeError("Embedded original auCDtect has invalid SHA-256.")
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = target.with_name(target.name + "-" + uuid.uuid4().hex + ".tmp")
            try:
                stage.write_bytes(payload)
                if sha(stage) != _AUCDTECT_ALLOWED[logical]:
                    raise RuntimeError("Staged original auCDtect failed verification.")
                os.replace(stage, target)
            finally:
                stage.unlink(missing_ok=True)
    if sha(binary) != _AUCDTECT_ALLOWED["Codecs/Analyzer/aucdtect.exe"]:
        raise RuntimeError("Original auCDtect binary failed post-install verification.")
    return binary


def _native_aucdtect():
    return _embedded_aucdtect()


def _original_checker_checksum(results):
    """Original AudioChecker 2.0 (build 457) 32-bit UTF-8 report checksum."""
    entries = []
    for track, category, probability in results:
        if category not in ("CDDA", "MPEG") or not 0 <= probability <= 100:
            raise ValueError("Only confirmed auCDtect classifications are valid.")
        entries.append(f"{track.name}|{category}|{probability}%")
    value = 0
    for character in "\r".join(entries).encode("utf-8"):
        value = ((value << 4) + (character ^ 0xD1)) & 0xFFFFFFFF
        high = value & 0xF0000000
        if high:
            value ^= high >> 24
            value &= (~high) & 0xFFFFFFFF
    return value


def _original_checker_report(folder_name, results):
    """Preserve the historic AUDIOCHECKER v2 report layout using REAL verdicts.

    The true auCDtect decision engine supplies every probability; no inference,
    calibration or spectral score translation is performed by this wrapper.
    """
    if not results:
        raise RuntimeError("No verified auCDtect classifications.")
    lines = [
        "AUDIOCHECKER v2.0 beta (build 457) - by Dester - opdester@freemail.hu",
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", "-=== DO NOT EDIT THIS FILE! ===-", "",
        "Path: ...\\" + str(folder_name), "",
    ]
    score = []
    width = len(str(len(results)))
    for idx, (track, label, prob) in enumerate(results, 1):
        if label not in ("CDDA", "MPEG") or not 0 <= prob <= 100:
            raise RuntimeError("Unverified auCDtect classification.")
        lines.append(f"{idx:0{width}d} -=- {track.name} -=- {label} ({prob}%)")
        score.append(prob if label == "CDDA" else 100 - prob)
    if len(score) > 1:
        lines.append(("Summary %.2f%% CDDA" % (sum(score) / len(score))).replace(".", ","))
    lines.append(str(_original_checker_checksum(results)))
    return "\r\n".join(lines) + "\r\n"


def _parse_native_aucdtect(text):
    match = _AC_NATIVE_RESULT.search(str(text))
    if not match:
        raise RuntimeError("The original auCDtect engine supplied no valid CDDA/MPEG verdict.")
    probability = int(match.group(2))
    if probability > 100:
        raise RuntimeError("Original auCDtect supplied an invalid probability.")
    return match.group(1).upper(), probability


def _original_checker_job(track, ff, ffprobe, native, stop_event):
    if stop_event.is_set():
        raise InterruptedError("AudioChecker cancelled.")
    details = probe(ffprobe, track)
    rate = int(details.get("sample_rate") or 0)
    channels = int(details.get("channels") or 0)
    declared_depth = details.get("bits_per_raw_sample") or details.get("bits_per_sample")
    try:
        depth = int(declared_depth)
    except (TypeError, ValueError):
        depth = 0
    if depth and depth != 16:
        raise RuntimeError(
            f"{track.name}: original audio is {depth}-bit, not CD 16-bit. "
            "Converting to 16-bit could change the original auCDtect result; "
            "no fabricated parity report is permitted.")
    if rate != 44100 or channels not in (1, 2):
        raise RuntimeError(
            f"Original auCDtect CD-audio mode needs 44100 Hz mono/stereo; "
            f"{track.name} has {rate} Hz / {channels} channels. "
            "Do not silently resample or invent a score.")
    with tempfile.TemporaryDirectory(prefix="MLO_auCDtect_", dir=str(DATA)) as td:
        wav = Path(td) / "track.wav"
        decoded = cmd([ff, "-hide_banner", "-v", "error", "-nostdin",
                       "-i", str(track), "-map", "0:a:0", "-vn", "-sn", "-dn",
                       "-c:a", "pcm_s16le", "-ar", "44100",
                       "-f", "wav", str(wav)], timeout=3600)
        if decoded.returncode or not wav.is_file():
            raise RuntimeError("Source audio decoding failed: " + decoded.stderr[-300:])
        if stop_event.is_set():
            raise InterruptedError("AudioChecker cancelled.")
        analyzed = cmd([str(native), "-mS0", str(wav)], timeout=3600)
        body = analyzed.stdout + "\n" + analyzed.stderr
        if analyzed.returncode and not _AC_NATIVE_RESULT.search(body):
            raise RuntimeError("Original auCDtect failed: " + body[-350:])
        label, probability = _parse_native_aucdtect(body)
        return track, label, probability


def _verify_original_checker_report(path, tracks, folder_name):
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if not text.startswith("AUDIOCHECKER v2.0 beta (build 457)"):
            return False
        if "\r\nPath: ...\\" + str(folder_name) + "\r\n" not in text:
            return False
        found = []
        for line in text.splitlines():
            m = re.match(r"^\d+ -=- (.*?) -=- (CDDA|MPEG) \((\d{1,3})%\)$", line)
            if m:
                found.append((Path(m.group(1)), m.group(2), int(m.group(3))))
        if len(found) != len(tracks) or any(
                a.name != b.name for (a, _, _), b in zip(found, tracks)):
            return False
        if int(text.splitlines()[-1]) != _original_checker_checksum(found):
            return False
        return raw == _original_checker_report(folder_name, found).encode("utf-8")
    except (ValueError, OSError, UnicodeError):
        return False


def native_check_web_release(dest, fmt, ff, stop_event, workers=4, release_name=None):
    """Real auCDtect classifications; never downgrade to homemade FFT output."""
    native = _native_aucdtect()
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe unavailable for the genuine auCDtect analysis.")
    provenance = []
    for base, dirs, filenames in os.walk(dest):
        if stop_event.is_set():
            raise InterruptedError("AudioChecker cancelled.")
        folder = Path(base)
        tracks = sorted(folder / fn for fn in filenames
                        if Path(fn).suffix.lower() in (".flac", ".m4a"))
        if not tracks:
            continue
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, int(workers))) as pool:
            futures = [pool.submit(_original_checker_job, track, ff, ffprobe, native,
                                   stop_event) for track in tracks]
            results = [future.result() for future in futures]
        if len(results) != len(tracks):
            raise RuntimeError("Original auCDtect did not check every file.")
        name = (release_name or folder.name) if folder == dest else folder.name
        report = folder / "audiochecker.log"
        if report.exists():
            raise RuntimeError("Refusing to overwrite an existing checker report.")
        report.write_bytes(_original_checker_report(name, results).encode("utf-8"))
        if not _verify_original_checker_report(report, tracks, name):
            report.unlink(missing_ok=True)
            raise RuntimeError("Original AudioChecker-style report checksum/coverage mismatch.")
        provenance.append({"report": str(report.relative_to(dest)),
                           "analyzer": "Original auCDtect -mS0 (not homemade FFT)",
                           "workers": int(workers), "input": fmt,
                           "results": len(results),
                           "mpeg": sum(item[1] == "MPEG" for item in results),
                           "cdda": sum(item[1] == "CDDA" for item in results)})
    if not provenance:
        raise RuntimeError("Original auCDtect found no tracks to analyze.")
    return provenance


def completion_reasons(info, export_warnings, checker, checker_enabled=True):
    """Return every unresolved release requirement. No unexplained PARTIAL."""
    reasons = []
    if not info.get("metadata_verified"):
        reasons.append("Exact release edition metadata not verified")
    if any("unresolved" in n.lower() or "not auto-selected" in n.lower()
           for n in info.get("notes", [])):
        reasons.append("Original metadata/media reference unresolved")
    if export_warnings:
        reasons.append("CUE or supporting-file fidelity not fully verified")
    if bool(info.get("physical")) and not info.get("country"):
        reasons.append("No physical release region verified or supplied")
    if not bool(info.get("physical")) and not (info.get("barcode") or info.get("catalog")):
        reasons.append("Neither barcode nor catalog verified for WEB edition")
    if checker_enabled and not bool(info.get("physical")) and not checker:
        reasons.append("Original auCDtect report missing")
    elif checker_enabled and not bool(info.get("physical")) and any(
            x.get("results", 0) < 1 for x in checker):
        reasons.append("Original auCDtect report has incomplete coverage")
    # A verified WEB barcode does not require a
    # separate MusicBrainz catalog number.
    return reasons



def _invalid_old_checker_reports(target):
    """Detect historical fake FFT output without changing the existing files."""
    if not target.is_dir() or target.is_symlink():
        return 0
    count = 0
    for previous in target.rglob("audiochecker.log"):
        if previous.is_symlink() or not previous.is_file():
            continue
        try:
            with previous.open("rb") as stream:
                if stream.read(60).startswith(b"MLO Integrated AudioChecker v0.3."):
                    count += 1
        except OSError:
            continue
    return count



# Apple iTunes UPC artwork and verified Spotify fallback; standalone, no keys.
ARTWORK_UNDO = DATA / "artwork-undo.json"
ARTWORK_LIMIT = 96 * 1024 * 1024


def _cover_request(url, hosts, maximum=ARTWORK_LIMIT):
    item = urllib.parse.urlsplit(str(url))
    if item.scheme != "https" or item.hostname not in hosts or item.username or item.password:
        raise ValueError("Untrusted cover URL: " + str(url)[:130])
    req = urllib.request.Request(url, headers={"User-Agent": APP_NAME + "/" + VERSION,
                                                "Accept": "image/jpeg,application/json,*/*;q=0.2"})
    with urllib.request.urlopen(req, timeout=18) as resp:
        actual = urllib.parse.urlsplit(resp.geturl())
        if actual.scheme != "https" or actual.hostname not in hosts:
            raise ValueError("Cover redirects to an untrusted host")
        if int(resp.headers.get("Content-Length") or 0) > maximum:
            raise ValueError("Cover exceeds maximum download size")
        data = resp.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("Cover download exceeds size limit")
        return data


def _cover_json(url, hosts):
    return json.loads(_cover_request(url, hosts, 3 * 1024 * 1024).decode("utf-8-sig"))


def _cover_jpeg_size(data):
    """Verify JPEG magic/EOI and dimensions instead of saving PNG as .jpg."""
    if not isinstance(data, bytes) or len(data) < 64 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        raise ValueError("Not a complete JPEG image")
    i = 2
    while i + 9 < len(data):
        if data[i] != 255:
            raise ValueError("Bad JPEG marker")
        while i < len(data) and data[i] == 255:
            i += 1
        if i == len(data):
            break
        marker = data[i]
        i += 1
        if marker == 0xda:
            break
        if marker in (0x01, 0xd8, 0xd9) or 0xd0 <= marker <= 0xd7:
            continue
        n = int.from_bytes(data[i:i + 2], "big")
        if n < 2 or i + n > len(data):
            raise ValueError("Bad JPEG segment")
        if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
                      0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
            h = int.from_bytes(data[i + 3:i + 5], "big")
            w = int.from_bytes(data[i + 5:i + 7], "big")
            if min(h, w) < 64 or max(h, w) > 12000:
                raise ValueError("Invalid JPEG dimensions")
            return w, h
        i += n
    raise ValueError("JPEG dimensions unavailable")


def _cover_upcs(value):
    code = str(value or "")
    if not _valid_gtin(code):
        return []
    variants = [code]
    if len(code) == 12:
        variants.append("0" + code)
    if len(code) == 13 and code.startswith("0"):
        variants.append(code[1:])
    return list(dict.fromkeys(x for x in variants if _valid_gtin(x)))


def _cover_apple_urls(url):
    obj = urllib.parse.urlsplit(str(url))
    host = obj.hostname or ""
    if obj.scheme != "https" or not re.fullmatch(r"is[1-5]-ssl\.mzstatic\.com", host):
        return []
    root, sep, _ = obj.path.rpartition("/")
    if not sep or not re.search(r"(?i)\.(?:jpe?g|png)$", root):
        return []
    return ["https://" + host + root + "/" + size for size in
            ("10000x0w-999.jpg", "6000x0w-999.jpg", "4000x0w-999.jpg",
             "3000x0w-999.jpg", "2000x0w-999.jpg",
             "1200x1200bb.jpg", "600x600bb.jpg")]


def _cover_apple(barcode, title, stop):
    reasons = []
    for country in ("US", "GB", "FR", "JP"):
        for code in _cover_upcs(barcode):
            if stop.is_set():
                raise InterruptedError("Artwork cancelled")
            url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode({
                "upc": code, "entity": "album", "country": country})
            try:
                hits = _cover_json(url, {"itunes.apple.com"}).get("results", [])
                matches = sorted(
                    [(_release_title_similarity(title, item.get("collectionName") or ""), item)
                     for item in hits if item.get("wrapperType") == "collection"
                     and item.get("artworkUrl100")], key=lambda pair: -pair[0])
                if not matches or matches[0][0] < 0.55:
                    continue
                if len(matches) > 1 and abs(matches[0][0] - matches[1][0]) < .015:
                    reasons.append("Ambiguous Apple UPC matches")
                    continue
                for candidate in _cover_apple_urls(matches[0][1]["artworkUrl100"]):
                    if stop.is_set():
                        raise InterruptedError("Artwork cancelled")
                    try:
                        data = _cover_request(candidate, {
                            f"is{i}-ssl.mzstatic.com" for i in range(1, 6)})
                        w, h = _cover_jpeg_size(data)
                        return {"bytes": data, "size": f"{w}x{h}",
                                "provider": "Apple Music",
                                "link": matches[0][1].get("collectionViewUrl") or url}, reasons
                    except (OSError, ValueError) as exc:
                        reasons.append("Apple image: " + str(exc)[:100])
            except InterruptedError:
                raise
            except (OSError, ValueError, TimeoutError) as exc:
                reasons.append("Apple lookup: " + str(exc)[:100])
    return None, reasons


def _cover_spotify(barcode, title, stop):
    """Search exact GTIN MusicBrainz release URL relations, no Spotify auth."""
    reasons, albums = [], []
    try:
        ids = []
        for code in _cover_upcs(barcode):
            if stop.is_set():
                raise InterruptedError("Artwork cancelled")
            path = "release/?" + urllib.parse.urlencode({
                "query": "barcode:" + code, "fmt": "json", "limit": "100"})
            for item in mb_json(path).get("releases", []):
                if (str(item.get("barcode") or "").lstrip("0") == barcode.lstrip("0") and
                        _release_title_similarity(title, item.get("title", "")) >= 0.65 and
                        item.get("id")):
                    ids.append(item["id"])
        for rid in list(dict.fromkeys(ids))[:6]:
            if stop.is_set():
                raise InterruptedError("Artwork cancelled")
            release = mb_json("release/" + rid + "?inc=release-groups+url-rels&fmt=json")
            nodes = [release]
            group_id = (release.get("release-group") or {}).get("id")
            if group_id:
                nodes.append(mb_json("release-group/" + group_id + "?inc=url-rels&fmt=json"))
            for node in nodes:
                for rel in node.get("relations") or []:
                    resource = str((rel.get("url") or {}).get("resource") or "")
                    m = re.fullmatch(
                        r"https://open\.spotify\.com/album/([A-Za-z0-9]{22})(?:[/?#].*)?",
                        resource)
                    if m:
                        albums.append("https://open.spotify.com/album/" + m.group(1))
    except InterruptedError:
        raise
    except Exception as exc:
        reasons.append("Spotify MusicBrainz relations: " + str(exc)[:120])
    for album_url in dict.fromkeys(albums):
        if stop.is_set():
            raise InterruptedError("Artwork cancelled")
        try:
            url = "https://open.spotify.com/oembed?" + urllib.parse.urlencode({"url": album_url})
            meta = _cover_json(url, {"open.spotify.com"})
            jpeg = _cover_request(meta.get("thumbnail_url") or "", {"i.scdn.co"})
            w, h = _cover_jpeg_size(jpeg)
            return {"bytes": jpeg, "size": f"{w}x{h}",
                    "provider": "Spotify", "link": album_url}, reasons
        except (OSError, ValueError, TimeoutError) as exc:
            reasons.append("Spotify oEmbed: " + str(exc)[:100])
    return None, reasons + ["No Spotify cover for the exact barcode release"]


def _cover_save(root, folder, artwork, manifest):
    """Save cover to Destination root, named after the source release folder."""
    if (not root.is_dir() or root.is_symlink() or
            not folder.is_dir() or folder.is_symlink() or
            (folder != root and root not in folder.parents)):
        raise ValueError("Unsafe cover destination or release folder")
    dest = root / (folder.name + ".jpg")
    if os.path.lexists(dest):
        return dest, False
    _cover_jpeg_size(artwork)
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_BINARY", 0))
    committed = False
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(artwork)
            out.flush()
            os.fsync(out.fileno())
        digest = hashlib.sha256(artwork).hexdigest()
        if sha(dest) != digest:
            raise ValueError("Saved cover checksum mismatch")
        manifest["created"].append({"path": str(dest.resolve()), "sha256": digest,
                                    "release_name": folder.name})
        try:
            write_json(ARTWORK_UNDO, manifest)
        except Exception:
            # Avoid a stale Undo reference if persisting this image failed.
            manifest["created"].pop()
            raise
        committed = True
        return dest, True
    finally:
        if not committed:
            dest.unlink(missing_ok=True)



def _cover_release_barcode(folder):
    """Prefer folder UPC, then tagged UPC, then verified MusicBrainz catalog."""
    ident, physical = catalog(folder.name)
    if _valid_gtin(ident):
        return ident
    for file in collect_files(folder):
        if file.suffix.casefold() not in AUDIO:
            continue
        try:
            from mutagen import File as MutagenFile
            tags = MutagenFile(str(file), easy=True)
            for key in ("barcode", "upc"):
                candidate = str((tags.get(key) or [""])[0]) if tags else ""
                if _valid_gtin(candidate):
                    return candidate
        except Exception:
            pass
        break
    if not ident:
        return ""
    # An 11-digit physical CD catalog is NOT a UPC. MusicBrainz must
    # corroborate an exact catalog, edition type and release title before
    # allowing the public Apple UPC artwork lookup.
    title_match = _RELEASE_PARTS.fullmatch(folder.name)
    title = title_match.group("title") if title_match else folder.name
    try:
        entries = _mb_catalog_search(ident, physical=physical)
        accepted = set()
        for entry in entries[:25]:
            if _release_title_similarity(title, entry.get("title", "")) < 0.65:
                continue
            release_id = str(entry.get("id") or "")
            if not release_id:
                continue
            concrete = mb_json("release/" + release_id +
                               "?inc=labels+media+release-groups&fmt=json")
            if not _matches_catalog(concrete, ident):
                continue
            media = concrete.get("media") or []
            if not media or not all(
                    ("cd" in str(m.get("format") or "").lower() if physical
                     else "digital media" in str(m.get("format") or "").lower())
                    for m in media):
                continue
            code = str(concrete.get("barcode") or "")
            if _valid_gtin(code):
                accepted.add(code.lstrip("0"))
        if len(accepted) == 1:
            return next(iter(accepted))
    except (OSError, ValueError, RuntimeError):
        return ""
    return ""


def _cover_archive_prior_undo():
    """Preserve the preceding artwork journal before a new download run.

    This matters when a user previously ran v0.3.18, which put images
    inside release directories. Preserve that recovery evidence rather
    than overwriting it with the new flat-output operation.
    """
    if not os.path.lexists(ARTWORK_UNDO):
        return None
    if ARTWORK_UNDO.is_symlink() or not ARTWORK_UNDO.is_file():
        raise ValueError("Previous Artwork Undo journal is not a regular file")
    if not isinstance(read_json(ARTWORK_UNDO, None), dict):
        raise ValueError("Previous Artwork Undo journal is unreadable; refusing to overwrite")
    history = DATA / "artwork-undo-history"
    history.mkdir(parents=True, exist_ok=True)
    archive = history / (
        "artwork-undo-" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S") +
        "-" + uuid.uuid4().hex[:12] + ".json")
    ARTWORK_UNDO.replace(archive)
    return archive


def _cover_undo_latest():
    if not ARTWORK_UNDO.is_file():
        return False
    if not UNDO.is_file():
        return True
    return ARTWORK_UNDO.stat().st_mtime_ns >= UNDO.stat().st_mtime_ns





class Organizer:
    """Organizes releases into a destination; sources are never modified."""
    def __init__(self, fmt="ALAC", encoding_workers=4, checker_workers=4,
                 enable_encoding=True, enable_checker=True, enable_splitting=True,
                 progress_cb=None):
        ensure_data()
        self.fmt = str(fmt)
        self.encoding_workers = int(encoding_workers)
        self.checker_workers = int(checker_workers)
        self.enable_encoding = bool(enable_encoding)
        self.enable_checker = bool(enable_checker)
        self.enable_splitting = bool(enable_splitting)
        self.progress_cb = progress_cb
        self.running = False
        self.mode = "organize"
        self.stop = threading.Event()
        self._status = ""
        self.progress = 0
        self.counts = {"total": 0, "done": 0, "partial": 0, "skipped": 0, "failed": 0, "warnings": 0}
        self.results = []
        self.activity = []
        self.error = ""
        self.lock = threading.RLock()
        self.log_path = _new_log("run")

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value
        if self.progress_cb is not None:
            self.progress_cb(value, self.counts["done"] + self.counts["partial"] +
                             self.counts["skipped"] + self.counts["failed"],
                             max(1, self.counts["total"]))

    def info(self, message):
        with self.lock:
            self.activity.append(message)
            self.activity = self.activity[-250:]
            try:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + message + "\n")
            except OSError as exc:
                self.error = "Activity log could not be written: " + str(exc)

    def cancel(self):
        self.stop.set()
        return {"ok": True}

    def organize_groups(self, groups, dest, fmt, artist_main, credit_consensus,
                        skip_files=frozenset()):
        """Organize [(source_name, members, source_root)] into dest; blocking."""
        staging_root = None
        manifest = None
        try:
            with self.lock:
                self.counts["total"] = len(groups)
                self.running = True
            if not groups:
                self.status = "No audio releases found."
                self.info(self.status)
                return
            dest.mkdir(parents=True, exist_ok=True)
            dest = dest.resolve(strict=True)
            staging_root = dest / (".MCC-stage-" + uuid.uuid4().hex)
            staging_root.mkdir()
            ff = ffprobe = None
            seen = set()
            self._artist_root = artist_main
            self._credit_consensus = credit_consensus
            for index, (source_name, members, source) in enumerate(groups, 1):
                if self.stop.is_set():
                    self.status = "Cancelled. Completed output can be undone."
                    break
                members = tuple(p.resolve(strict=True) for p in members)
                grouped = len(members) > 1
                folder = members[0].parent if grouped else members[0]
                result = {"name": source_name, "source": str(members[0]), "target": "",
                          "status": "", "message": "", "warnings": [],
                          "metadata": {}, "checker": [], "timings_seconds": {},
                          "processing": {"encoding": self.enable_encoding,
                                         "audiochecker": self.enable_checker,
                                         "split_images": self.enable_splitting}}
                started_release = time.monotonic()
                try:
                    if any(source != member and source not in member.parents
                           for member in members):
                        raise RuntimeError("Input release escaped the source root.")
                    # When output already exists under the *same name*,
                    # skip before expensive sequential MusicBrainz requests.
                    # A fresh destination is required to reprocess releases.
                    preexisting = dest / source_name
                    if os.path.lexists(preexisting):
                        result["target"] = str(preexisting)
                        obsolete_count = _invalid_old_checker_reports(preexisting)
                        if obsolete_count:
                            result["status"] = "partial"
                            result["message"] = (
                                f"Existing output contains {obsolete_count} "
                                "INVALID custom-FFT AudioChecker report(s); "
                                "no originals or outputs changed. Recreate in "
                                "a new empty destination with genuine auCDtect.")
                            result["warnings"].append(result["message"])
                            result["unmet_requirements"] = ["Invalid historic FFT report"]
                            self.counts["partial"] += 1
                        else:
                            result["status"] = "skipped"
                            result["message"] = "Output already exists - not overwritten; no lookup required."
                            self.counts["skipped"] += 1
                        continue
                    files = ([fp for member in members for fp in collect_files(member)]
                             if grouped else collect_files(folder))
                    files = [fp for fp in files if fp.resolve(strict=False) not in skip_files]
                    if not files:
                        raise RuntimeError("Release is empty.")
                    if any(fp.suffix.lower() in LOSSY for fp in files):
                        raise RuntimeError("Lossy input present; conversion to purported lossless is prohibited.")
                    self.status = f"Looking up release {index}/{len(groups)}: {folder.name}"
                    artist_hint = artist_main
                    metadata_start = time.monotonic()
                    if grouped:
                        info = release_identity(folder, files, default_artist=artist_hint,
                                                source_name=source_name, disc_folders=members)
                    else:
                        info = release_identity(folder, files, default_artist=artist_hint)
                    result["timings_seconds"]["musicbrainz_metadata"] = round(
                        time.monotonic() - metadata_start, 2)
                    result["metadata"] = {k: v for k, v in info.items() if k != "folder"}
                    result["warnings"].extend(info["notes"])
                    out_name = release_folder_target(info)
                    result["warnings"].extend(x for x in info["notes"] if x not in result["warnings"])
                    target = dest / out_name
                    result["target"] = str(target)
                    if out_name.casefold() in seen:
                        raise RuntimeError("Two input editions map to identical output folder: " + out_name)
                    seen.add(out_name.casefold())
                    if os.path.lexists(target):
                        # Incompatible pre-v0.3.9 homemade FFT reports must
                        # never be treated as successfully verified AudioChecker
                        # results merely because the output folder exists.
                        obsolete_count = _invalid_old_checker_reports(target)
                        if obsolete_count:
                            result["status"] = "partial"
                            result["message"] = (
                                "Existing output contains " + str(obsolete_count) +
                                " INVALID custom-FFT AudioChecker report(s); "
                                "no originals or outputs changed. Recreate in "
                                "a new empty destination with genuine auCDtect.")
                            result["warnings"].append(result["message"])
                            result["unmet_requirements"] = [
                                "Original auCDtect analysis absent; previous FFT reports are invalid"]
                            self.counts["partial"] += 1
                        else:
                            result["status"] = "skipped"
                            result["message"] = "Output already exists - not overwritten."
                            self.counts["skipped"] += 1
                    else:
                        if info["physical"]:
                            if any(fp.name.casefold() == "audiochecker.log" for fp in files):
                                result["warnings"].append(
                                    "Ignored WEB-only audiochecker.log from physical CD output (source preserved).")
                            if not any(fp.suffix.lower() == ".cue" for fp in files):
                                result["warnings"].append("CD CUE absent; genuine source not fabricated.")
                            if not any(fp.suffix.lower() == ".log" and
                                       fp.name.casefold() != "audiochecker.log" for fp in files):
                                result["warnings"].append("CD ripping log absent; not fabricated.")
                            if not info["catalog"]:
                                result["warnings"].append("Specific physical edition catalog not verified.")
                        if ff is None:
                            ff, ffprobe = ensure_ffmpeg()
                        tmp = staging_root / (str(index) + "-" + uuid.uuid4().hex)
                        tmp.mkdir()
                        self._current_identity = info
                        self._current_release_feature = info.get("feature_hint") or ""
                        self._export_warnings = []
                        self._export_notices = []
                        try:
                            self.status = f"Organizing {index}/{len(groups)}: {out_name}"
                            export_started = time.monotonic()
                            if grouped:
                                self._export_release(
                                    folder, tmp, fmt, ff, ffprobe,
                                    source_files=files, disc_folders=members)
                            else:
                                self._export_release(folder, tmp, fmt, ff, ffprobe, source_files=files)
                            result["timings_seconds"]["encoding_copy"] = round(
                                time.monotonic() - export_started, 2)
                            result["warnings"].extend(self._export_warnings)
                            # Actual AudioChecker is performed before finalizing the release.
                            if not info["physical"] and self.enable_checker:
                                checker_started = time.monotonic()
                                try:
                                    self.status = f"AudioChecker {index}/{len(groups)}: {out_name}"
                                    result["checker"] = native_check_web_release(
                                        tmp, fmt, ff, self.stop, self.checker_workers,
                                        release_name=target.name)
                                except InterruptedError:
                                    raise
                                except Exception as exc:
                                    result["warnings"].append("REQUIRED AudioChecker not completed: " + str(exc))
                                finally:
                                    result["timings_seconds"]["original_aucdetect"] = round(
                                        time.monotonic() - checker_started, 2)
                            output_files = collect_files(tmp)
                            if not output_files:
                                raise RuntimeError("No output generated.")
                            hashes = {str(fp.relative_to(tmp)).replace("\\", "/"): sha(fp)
                                      for fp in output_files}
                            if self.stop.is_set():
                                raise InterruptedError("Cancelled before committing release.")
                            if os.path.lexists(target):
                                raise RuntimeError("Target appeared during export; no overwrite.")
                            if manifest is None:
                                previous = read_json(UNDO, None)
                                if previous and previous.get("created"):
                                    HISTORY.mkdir(parents=True, exist_ok=True)
                                    archive = HISTORY / (time.strftime("%Y%m%d-%H%M%S") + "-" +
                                                         uuid.uuid4().hex[:8] + ".json")
                                    write_json(archive, previous)
                                manifest = {"version": VERSION, "source": str(source),
                                            "dest": str(dest), "format": fmt,
                                            "processing": {"encoding": self.enable_encoding,
                                                           "audiochecker": self.enable_checker,
                                                           "split_images": self.enable_splitting},
                                            "created": [], "pending": None}
                            rec = {"path": str(target), "files": hashes}
                            manifest["pending"] = rec
                            write_json(UNDO, manifest)
                            os.rename(tmp, target)
                            manifest["created"].append(rec)
                            manifest["pending"] = None
                            write_json(UNDO, manifest)
                            reasons = completion_reasons(
                                info, self._export_warnings, result["checker"],
                                checker_enabled=self.enable_checker)
                            result["unmet_requirements"] = reasons
                            if reasons:
                                result["status"] = "partial"
                                self.counts["partial"] += 1
                                result["warnings"].extend(x for x in reasons if x not in result["warnings"])
                                result["message"] = (str(len(output_files)) +
                                    " output files; PARTIAL: " + "; ".join(reasons))
                            else:
                                result["status"] = "done"
                                self.counts["done"] += 1
                                result["message"] = str(len(output_files)) + " verified output files."
                            if self._export_notices:
                                result["message"] += " | " + " | ".join(self._export_notices)
                        finally:
                            self._current_identity = None
                            if tmp.exists():
                                shutil.rmtree(tmp)
                except InterruptedError:
                    self.status = "Cancelled. Committed output remains Undo-able."
                    self.info(self.status)
                    break
                except Exception as exc:
                    result["status"], result["message"] = "failed", str(exc)
                    self.counts["failed"] += 1
                finally:
                    result["timings_seconds"]["total_release"] = round(
                        time.monotonic() - started_release, 2)
                    if result["status"]:
                        if result["timings_seconds"].get("total_release", 0) >= 2:
                            self.info("PERFORMANCE: " + source_name + " | " +
                                " | ".join(k + "=" + str(v) + "s" for k, v in
                                         result["timings_seconds"].items()))
                        self.counts["warnings"] += len(result["warnings"])
                        with self.lock:
                            self.results.append(result)
                            self.progress = round(index * 100 / len(groups))
                        self.info(result["status"].upper() + ": " + source_name +
                                  " -> " + result["target"] + " - " + result["message"] +
                                  ((" | " + "; ".join(result["warnings"])) if result["warnings"] else ""))
                    write_json(REPORT, {"version": VERSION, "source": str(source),
                                        "output": str(dest), "format": fmt,
                                        "processing": {"encoding": self.enable_encoding,
                                                       "audiochecker": self.enable_checker,
                                                       "split_images": self.enable_splitting},
                                        "counts": dict(self.counts), "releases": list(self.results)})
            if not self.stop.is_set():
                self.status = ("Finished: " + str(self.counts["done"]) + " compliant, " +
                               str(self.counts["partial"]) + " partially organized, " +
                               str(self.counts["skipped"]) + " existing, " +
                               str(self.counts["failed"]) + " failed.")
                self.info(self.status)
        except Exception as exc:
            self.error = str(exc)
            self.status = "Batch failed: " + str(exc)
            self.info("BATCH ERROR: " + traceback.format_exc()[-3500:])
        finally:
            if staging_root is not None and staging_root.exists():
                try:
                    shutil.rmtree(staging_root)
                except Exception as exc:
                    self.info("Staging cleanup error: " + str(exc))
            with self.lock:
                self.running = False

    def _export_release(self, source, dest, fmt, ff, ffprobe,
                        source_files=None, disc_folders=()):
        files = list(source_files) if source_files is not None else collect_files(source)
        def output_subdir(parent):
            for position, disc in enumerate(disc_folders, 1):
                if parent == disc or disc in parent.parents:
                    return Path(f"CD {position}") / parent.relative_to(disc)
            if disc_folders:
                raise RuntimeError("Grouped CD file escaped its source disc folder.")
            return parent.relative_to(source)
        cues = [p for p in files if p.suffix.lower() == ".cue"]
        ident = getattr(self, "_current_identity", None)
        if ident:
            cat = ident.get("catalog") or ident.get("barcode") or ""
            physical = bool(ident.get("physical"))
            valid_cat = bool(ident.get("metadata_verified") and cat)
        else:
            cat, physical = catalog(source.name)
            valid_cat = bool(cat and cat.lower() != "none")
        extension = ".m4a" if fmt == "ALAC" else ".flac"
        # A single CUE image must be handled as indivisible input.
        images, by_cue, source_images = [], {}, set()
        unsafe_images = []
        for cp in cues:
            parsed = cue_read(cp)
            for rec in parsed["records"]:
                if rec["file"]:
                    linked = (cp.parent / rec["file"].replace("\\", os.sep)).resolve()
                    if source != linked and source not in linked.parents:
                        raise RuntimeError("CUE audio escapes release folder: " + rec["file"])
            try:
                found = cue_image_plan(cp, parsed)
            except ValueError as exc:
                if str(exc) != "INDEX00 occurs after INDEX01 in the same audio file.":
                    raise
                # Cannot correct impossible pregap positions without evidence.
                # Preserve the whole image, do not invent an INDEX value or
                # generate incorrectly cut track files.
                all_refs = {rec.get("file", "").replace("\\", "/").casefold()
                            for rec in parsed["records"]}
                if len(all_refs) != 1 or not parsed["records"]:
                    raise
                common = parsed["records"][0]["file"]
                original = (cp.parent / common.replace("\\", os.sep)).resolve()
                if original.is_symlink() or not original.is_file() or original.suffix.lower() not in AUDIO:
                    raise
                if source != original and source not in original.parents:
                    raise
                unsafe_images.append((cp, original))
                source_images.add(original)
                continue
            if found:
                if len(found) != 1 or len(found[0][1]) != len(parsed["records"]):
                    raise RuntimeError("Mixed/split image CUE needs manual review.")
                by_cue[cp] = (parsed, found[0])
                images.append((cp, parsed, found[0]))
                source_images.add(found[0][0].resolve())
        mapping = {}
        new_cues = {}
        for cp, src_img in unsafe_images:
            if src_img in mapping:
                raise RuntimeError("Cannot preserve the same malformed CUE image twice.")
            target = dest / output_subdir(src_img.parent) / src_img.name
            if os.path.lexists(target):
                raise RuntimeError("Malformed CUE preservation destination collision.")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_img, target)
            if sha(src_img) != sha(target):
                raise RuntimeError("Malformed CUE image copy differs from original.")
            mapping[src_img] = target
            getattr(self, "_export_warnings", []).append(
                cp.name + ": INDEX 00 occurs after INDEX 01 in the same source file. "
                "Original image and index data preserved; unsafe splitting skipped.")
        for cp, parsed, (src_img, records, ticks) in images:
            if not getattr(self, "enable_splitting", True):
                # Retain one source album image: the CUE indexes remain intact.
                src_img = src_img.resolve(strict=True)
                if src_img in mapping:
                    continue
                ext = extension if getattr(self, "enable_encoding", True) else src_img.suffix
                output = dest / output_subdir(src_img.parent) / (
                    _sanitize_windows_name(src_img.stem) + ext)
                if os.path.lexists(output):
                    raise RuntimeError("Whole image destination exists: " + str(output))
                output.parent.mkdir(parents=True, exist_ok=True)
                info = probe(ffprobe, src_img)
                codec = str(info.get("codec_name", "")).lower()
                if codec not in _MB_LOSSLESS:
                    raise RuntimeError("Whole album image is not lossless: " + str(src_img))
                if (not getattr(self, "enable_encoding", True) or
                    (fmt == "FLAC" and codec == "flac") or
                    (fmt == "ALAC" and codec == "alac")):
                    shutil.copy2(src_img, output)
                    if sha(src_img) != sha(output):
                        raise RuntimeError("Whole album image copy hash mismatch.")
                else:
                    convert(ff, src_img, output, fmt, ffprobe=ffprobe)
                mapping[src_img] = output
                getattr(self, "_export_notices", []).append(
                    "Album image kept whole: " + src_img.name)
                continue
            info = probe(ffprobe, src_img)
            rate = int(info.get("sample_rate", 0))
            if rate <= 0 or rate % 75:
                raise RuntimeError("Sample rate cannot represent 75fps CUE boundaries exactly.")
            if str(info.get("codec_name", "")).lower() not in {"alac", "flac", "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_f64le", "ape", "wavpack", "pcm_s16be", "pcm_s24be", "pcm_s32be"}:
                raise RuntimeError("Audio image is not verified lossless: " + str(info.get("codec_name", "")))
            sub = output_subdir(cp.parent)
            if src_img.resolve() not in source_images:
                raise RuntimeError("Image mapping invalid.")
            names = {}
            image_jobs = []
            seen_image_names = set()
            for k, rec in enumerate(records):
                start_sample = ticks[k] * (rate // 75)
                end_sample = ticks[k + 1] * (rate // 75) if k + 1 < len(records) else None
                new_title, new_artist = normalize_artist_title(
                    rec["title"], getattr(self, "_artist_root", ""),
                    getattr(self, "_artist_root", ""),
                    getattr(self, "_credit_consensus", None))
                name = track_filename(rec["number"], new_title, extension)
                output = dest / sub / name
                if str(output).casefold() in seen_image_names or os.path.lexists(output):
                    raise RuntimeError("Image tracks map to the same output path: " + str(output))
                seen_image_names.add(str(output).casefold())
                image_jobs.append((rec, name, output, start_sample, end_sample, k,
                                   new_title, new_artist))
            def encode_image(job):
                rec, name, output, start_sample, end_sample, k, new_title, new_artist = job
                if self.stop.is_set():
                    raise InterruptedError("Cancelled.")
                convert(ff, src_img, output, fmt, start_sample, end_sample,
                        new_title, rec["number"], artist=new_artist, ffprobe=ffprobe)
                return rec["number"], name, k
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max(1, int(self.encoding_workers))) as pool:
                futures = [pool.submit(encode_image, job) for job in image_jobs]
                for future in concurrent.futures.as_completed(futures):
                    num, name, k = future.result()
                    names[num] = (name, ticks[k], ticks[k + 1] if k + 1 < len(ticks) else None)
            new_cues[cp] = image_cue_text(parsed, names)
        # Prepare all ordinary tracks before encoding. Duplicate target names
        # are verified against decoded PCM; never drop different audio.
        audio_jobs = {}
        ordinary_sources = [x for x in files if x.suffix.lower() in AUDIO
                            and x.resolve() not in source_images]
        for fp in files:
            if self.stop.is_set():
                raise InterruptedError("Encoding cancelled.")
            if fp.resolve() in source_images or fp.suffix.lower() not in AUDIO:
                continue
            number, title, artist = extract_number_title(
                fp, getattr(self, "_artist_root", ""),
                getattr(self, "_credit_consensus", None))
            if number <= 0 or not title:
                raise RuntimeError("Track has no valid number/title: " + str(fp))
            # A release-folder (ft. X) belongs on its single *song*, never on
            # the folder. Propagate only if the same one-track recording lacks
            # that explicitly supplied credit; never add it to all EP tracks.
            released_feature = getattr(self, "_current_release_feature", "")
            info = getattr(self, "_current_identity", {}) or {}
            if (released_feature and len(ordinary_sources) == 1 and
                    not _song_parts(title)[3] and
                    _song_key(title) == _song_key(info.get("title", ""))):
                title = normalized_title(title + " (ft. " + released_feature + ")")
                root_artist = getattr(self, "_artist_root", "")
                if root_artist and (
                        artist.casefold() == (
                            root_artist + " & " + released_feature).casefold() or
                        artist.casefold() == (
                            root_artist + " feat. " + released_feature).casefold()):
                    artist = root_artist
            output_ext = extension if getattr(self, "enable_encoding", True) else fp.suffix
            dst = dest / output_subdir(fp.parent) / track_filename(number, title, output_ext)
            audio_jobs.setdefault(str(dst).casefold(), (dst, []) )[1].append(
                (fp, number, title, artist))
        jobs = list(audio_jobs.values())

        def encode_normal(entry):
            dst, variants = entry
            if os.path.lexists(dst):
                raise RuntimeError("Audio target exists: " + str(dst))
            src, number, title, artist = variants[0]
            dst.parent.mkdir(parents=True, exist_ok=True)
            source_info = probe(ffprobe, src)
            codec = str(source_info.get("codec_name", "")).lower()
            if codec not in _MB_LOSSLESS:
                raise RuntimeError("Refusing to encode non-lossless audio: " + str(src))
            encode = getattr(self, "enable_encoding", True)
            if (not encode or
                (fmt == "ALAC" and codec == "alac") or
                (fmt == "FLAC" and codec == "flac")):
                shutil.copy2(src, dst)
                if sha(src) != sha(dst):
                    raise RuntimeError("Source copy hash mismatch: " + str(src))
                try:
                    _update_copied_track_tags(dst, title, artist, number)
                except Exception as exc:
                    if encode or src.suffix.casefold() in (".flac", ".m4a"):
                        raise
                    getattr(self, "_export_warnings", []).append(
                        "Copied " + src.name + " without updated tags; container "
                        "does not safely support them: " + str(exc)[:180])
            else:
                convert(ff, src, dst, fmt, title=title, number=number,
                        artist=artist, ffprobe=ffprobe)
            # Additional files mapping to this name are discarded ONLY when
            # the decoded PCM equals the successfully verified first copy.
            for variant, _, _, _ in variants[1:]:
                if pcm_hash(ff, variant) != pcm_hash(ff, dst):
                    raise RuntimeError("Distinct tracks collide: " + str(variant) + " -> " + str(dst))
            return dst, [x[0].resolve() for x in variants]

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, int(self.encoding_workers))) as pool:
            futures = [pool.submit(encode_normal, job) for job in jobs]
            for future in concurrent.futures.as_completed(futures):
                completed, originals = future.result()
                for original in originals:
                    mapping[original] = completed
                if self.stop.is_set():
                    raise InterruptedError("Encoding cancelled.")
        # Preserve CUE text, rewriting only correct FILE paths; keep originals in source.
        destinations = set()
        unresolved_cues = set()
        for fp in files:
            if fp.resolve() in source_images or fp.suffix.lower() in AUDIO:
                continue
            if fp.name.casefold() == "audiochecker.log":
                # WEB: create a genuine fresh report against the output tracks.
                # CD: NEVER copy a WEB-only AudioChecker report into a physical
                # rip, even if one happens to exist in the source archive.
                # The original source sidecar is deliberately never altered.
                continue
            sub = output_subdir(fp.parent)
            if fp.suffix.lower() == ".cue":
                dest_name = cat + ".cue" if physical and valid_cat else fp.name
            elif fp.suffix.lower() == ".log" and fp.name.lower() != "audiochecker.log":
                dest_name = cat + ".log" if physical and valid_cat else fp.name
            elif fp.name.lower() == "audiochecker.log":
                dest_name = "audiochecker.log"
            else:
                dest_name = fp.name
            target = dest / sub / dest_name
            rel = str(target.relative_to(dest)).casefold()
            if rel in destinations or target.exists():
                raise RuntimeError("Supporting file destination collision: " + str(target))
            destinations.add(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if fp.suffix.lower() == ".cue":
                if fp in new_cues:
                    rewritten = new_cues[fp]
                else:
                    cue = cue_read(fp)
                    original_refs = [r["file"] for r in cue["records"] if r["file"]]
                    # A shared old WAV image is not recoverable from several
                    # already-split files without reliable pregap provenance.
                    # This is not a reason to throw away valid audio tracks.
                    is_shared = (len(original_refs) > 1 and
                                 len({x.casefold() for x in original_refs}) < len(original_refs))
                    is_absent = any(
                        not (fp.parent / x.replace(chr(92), os.sep)).is_file()
                        for x in original_refs)
                    if is_shared and is_absent:
                        rewritten, reason = reconstruct_missing_image_cue(cue, fp, mapping)
                        if rewritten:
                            target.write_text(rewritten, encoding="utf-8",
                                              newline="\r\n" if IS_WIN else "\n")
                            notice = (fp.name + ": playable split-track CUE rebuilt after "
                                      "sample-exact sector verification; original CUE untouched.")
                            getattr(self, "_export_notices", []).append(notice)
                            self.info(notice)
                            continue
                        if not any(path.parent == fp.parent for path in mapping):
                            raise RuntimeError(
                                "Original shared CUE WAV missing and no surviving split tracks.")
                        unresolved_cues.add(fp)
                        fallback = target.parent / ("Unresolved CUE - " + fp.stem + ".cue")
                        if os.path.lexists(fallback):
                            raise RuntimeError("Unresolved CUE filename collision.")
                        shutil.copy2(fp, fallback)
                        if sha(fp) != sha(fallback):
                            raise RuntimeError("CUE evidence copy differs from original.")
                        getattr(self, "_export_warnings", []).append(
                            fp.name + ": old full-image WAV absent; cannot safely rewrite "
                            "CUE for individual tracks: " + reason +
                            ". Original is retained as documentary CUE only.")
                        continue
                    refs = {}
                    unresolved_reason = None
                    for rec in cue["records"]:
                        if not rec["file"]:
                            raise RuntimeError("CUE missing FILE for track " + str(rec["number"]))
                        key = rec["file"].replace("\\", "/").casefold()
                        src_audio = (fp.parent / rec["file"].replace("\\", os.sep)).resolve()
                        if src_audio not in mapping:
                            # Old CD CUE may still name the former WAV even when
                            # it has been split/converted to numbered FLAC files.
                            # Match a unique track by its actual track number.
                            matches = []
                            for old_audio, new_audio in mapping.items():
                                num, _, _ = extract_number_title(old_audio)
                                if num == rec["number"] and old_audio.parent == fp.parent:
                                    matches.append(new_audio)
                            if len(set(matches)) != 1:
                                raise RuntimeError("Cannot uniquely remap legacy CUE FILE: " + rec["file"])
                            if len({r["file"].casefold() for r in cue["records"] if r["file"]}) < len(cue["records"]):
                                unresolved_reason = (
                                    "CUE references an absent shared album image. "
                                    "Exact INDEX00 and pregap distribution cannot be proven "
                                    "from split tracks. Audio preserved, original CUE quarantined.")
                                break
                            if rec["index"].get(1, -1) != 0:
                                unresolved_reason = "Legacy CUE index offsets cannot be verified against separate audio."
                                break
                            refs[key] = os.path.relpath(matches[0], target.parent).replace("/", "\\")
                        else:
                            refs[key] = os.path.relpath(mapping[src_audio], target.parent).replace("/", "\\")
                    if unresolved_reason:
                        unresolved_cues.add(fp)
                        fallback = target.parent / ("Unresolved CUE - " + fp.stem + ".cue")
                        if os.path.lexists(fallback):
                            raise RuntimeError("Cannot preserve original unresolved CUE due to name collision.")
                        shutil.copy2(fp, fallback)
                        if sha(fp) != sha(fallback):
                            raise RuntimeError("Unresolved original CUE copy changed.")
                        getattr(self, "_export_warnings", []).append(
                            fp.name + ": " + unresolved_reason)
                        continue
                    rewritten = normal_cue_text(cue, refs)
                target.write_text(rewritten, encoding="utf-8", newline="\r\n" if IS_WIN else "\n")
            else:
                shutil.copy2(fp, target)
                if sha(fp) != sha(target):
                    raise RuntimeError("Copied support file differs: " + str(fp))
        # Ensure physical cue(s) and logs preserved or explicitly absent.
        for fp in files:
            if fp.suffix.lower() == ".cue" and fp not in unresolved_cues and not (dest / output_subdir(fp.parent) / (cat + ".cue" if physical and valid_cat else fp.name)).is_file():
                raise RuntimeError("A CUE was lost during export.")

    def _download_artwork(self, root, releases):
        manifest = {"root": str(root), "created": [],
                    "layout": "destination-root", "kind": "artwork",
                    "started": datetime.now().isoformat()}
        try:
            saved_journal = _cover_archive_prior_undo()
            if saved_journal:
                self.info("ARTWORK PRIOR UNDO SAVED: " + str(saved_journal))
            write_json(ARTWORK_UNDO, manifest)
            # A flat artwork directory cannot safely represent same-named
            # releases from different subfolders. Reject every ambiguous
            # basename rather than arbitrarily assigning one cover.
            from collections import Counter
            title_counts = Counter(folder.name.casefold() for folder in releases)
            for index, folder in enumerate(releases, 1):
                if self.stop.is_set():
                    self.status = "Artwork cancelled; created covers can be undone."
                    break
                row = {"name": folder.name, "source": str(folder),
                       "target": str(root), "status": "",
                       "message": "", "warnings": []}
                try:
                    if folder.is_symlink() or folder.resolve(strict=True) != folder:
                        raise ValueError("Release directory changed or is symlinked")
                    if title_counts[folder.name.casefold()] > 1:
                        row["status"] = "partial"
                        row["message"] = ("Duplicate release folder names cannot share "
                                          "one artwork filename in Destination")
                        self.counts["partial"] += 1
                        continue
                    target = root / (folder.name + ".jpg")
                    if os.path.lexists(target):
                        row["status"] = "skipped"
                        row["message"] = "Cover already exists; not overwritten"
                        self.counts["skipped"] += 1
                        continue
                    code = _cover_release_barcode(folder)
                    if not _valid_gtin(code):
                        row["status"] = "partial"
                        row["message"] = "No unique verified UPC/EAN from folder, audio tags or exact MusicBrainz catalog"
                        self.counts["partial"] += 1
                        continue
                    match = _RELEASE_PARTS.fullmatch(folder.name)
                    title = match.group("title") if match else folder.name
                    self.status = f"Artwork {index}/{len(releases)}: {folder.name}"
                    cover, notes = _cover_apple(code, title, self.stop)
                    if not cover:
                        self.info("APPLE MISS: " + folder.name + " | " + "; ".join(notes[-2:]))
                        cover, spotify_notes = _cover_spotify(code, title, self.stop)
                        if not cover:
                            row["status"] = "partial"
                            row["message"] = "Neither Apple nor exact-match Spotify artwork available"
                            row["warnings"] = (notes[-2:] + spotify_notes[-2:])
                            self.counts["partial"] += 1
                            continue
                    if self.stop.is_set():
                        raise InterruptedError("Artwork cancelled")
                    image, written = _cover_save(root, folder, cover["bytes"], manifest)
                    row["status"] = "done" if written else "skipped"
                    row["message"] = (cover["provider"] + " " + cover["size"] + " JPG"
                                      if written else "Cover was already created")
                    row["artwork_source"] = str(cover["link"])
                    self.counts["done" if written else "skipped"] += 1
                    self.info("ARTWORK " + row["status"].upper() + ": " +
                              str(image) + " | " + row["message"] +
                              " | " + str(cover["link"]))
                except InterruptedError:
                    self.status = "Artwork cancelled; completed covers remain Undo-able."
                    break
                except Exception as exc:
                    row["status"], row["message"] = "failed", str(exc)[:350]
                    self.counts["failed"] += 1
                    self.info("ARTWORK FAILED: " + folder.name + " | " +
                              traceback.format_exc()[-1800:])
                finally:
                    self.counts["warnings"] += len(row["warnings"])
                    if row["status"]:
                        with self.lock:
                            self.results.append(row)
                    with self.lock:
                        self.progress = round(index * 100 / len(releases))
            if not self.stop.is_set():
                self.status = (f"Artwork complete: {self.counts['done']} added, "
                               f"{self.counts['skipped']} existing, "
                               f"{self.counts['partial']} unavailable, "
                               f"{self.counts['failed']} failed.")
                self.info(self.status)
        except Exception as exc:
            self.error = str(exc)
            self.status = "Artwork batch failed: " + str(exc)
            self.info("ARTWORK ERROR: " + traceback.format_exc()[-2000:])
        finally:
            with self.lock:
                self.running = False

    def _undo_artwork(self, manifest):
        try:
            root = Path(manifest["root"]).resolve(strict=True)
            files = manifest.get("created", [])
            # Support old v0.3.18 nested-artwork journals without deleting
            # their releases; new journals cover flat Destination-root JPGs.
            flat = manifest.get("layout") == "destination-root"
            if manifest.get("layout") not in (None, "destination-root"):
                raise RuntimeError("Unknown Artwork Undo journal layout")
            # Validate every filename and hash before unlinking anything.
            for entry in files:
                image = Path(entry["path"])
                resolved = image.resolve(strict=True) if image.is_file() else image
                symlink_parent = any(p.is_symlink() for p in image.parents
                                     if p == root or root in p.parents)
                valid_location = (image.parent == root and
                                  image.name == entry.get("release_name", "") + ".jpg"
                                  if flat else
                                  root in image.parents and
                                  image.name == image.parent.name + ".jpg")
                if (not image.is_file() or image.is_symlink() or symlink_parent or
                        not valid_location or
                        not resolved.is_relative_to(root) or
                        sha(image) != entry["sha256"]):
                    raise RuntimeError("Cover changed since download; Undo blocked: " +
                                       str(image))
            for entry in reversed(files):
                Path(entry["path"]).unlink()
            ARTWORK_UNDO.unlink(missing_ok=True)
            self.status = "Artwork Undo complete; audio and existing covers untouched."
            self.info(self.status)
        except Exception as exc:
            self.error = str(exc)
            self.status = "Artwork Undo blocked: " + str(exc)
            self.info("ARTWORK UNDO ERROR: " + traceback.format_exc()[-1800:])
        finally:
            with self.lock:
                self.running = False

    def _undo(self, manifest):
        try:
            targets = list(manifest.get("created", []))
            pending = manifest.get("pending")
            if pending:
                # A crash between rename and manifest commit must not silently destroy data.
                raise RuntimeError("An interrupted Apply has a pending entry. Inspect its destination before Undo.")
            recorded_destination = Path(manifest["dest"]).resolve(strict=True)
            for record in targets:
                folder = Path(record["path"])
                if not folder.is_dir() or folder.is_symlink():
                    raise RuntimeError("Output folder changed/missing: " + str(folder))
                if folder.resolve().parent != recorded_destination:
                    raise RuntimeError("Undo journal points outside its destination: " + str(folder))
                actual = collect_files(folder)
                recorded = record["files"]
                actual_keys = {str(p.relative_to(folder)).replace("\\", "/") for p in actual}
                if actual_keys != set(recorded):
                    raise RuntimeError("Output contents changed; Undo blocked: " + str(folder))
                for p in actual:
                    key = str(p.relative_to(folder)).replace("\\", "/")
                    if sha(p) != recorded[key]:
                        raise RuntimeError("Output file modified; Undo blocked: " + str(p))
            # No mutation until all outputs validated.
            for record in reversed(targets):
                shutil.rmtree(record["path"])
            UNDO.unlink(missing_ok=True)
            self.status = "Undo complete. Original sources were never modified."
            self.info(self.status)
        except Exception as e:
            self.error, self.status = str(e), "Undo blocked: " + str(e)
            self.info("UNDO ERROR: " + traceback.format_exc()[-2000:])
        finally:
            with self.lock:
                self.running = False


def _send_folders_to_recycle_bin(folders: Sequence[Path]) -> None:
    """Send folders to the Windows Recycle Bin (recoverable); never delete permanently."""
    if os.name != "nt":
        raise RuntimeError("Move needs the Windows Recycle Bin; use Copy on this system.")
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
        "$env:MCC_RECYCLE_FOLDER,'OnlyErrorDialogs','SendToRecycleBin')"
    )
    for folder in folders:
        result = run_hidden(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env=dict(os.environ, MCC_RECYCLE_FOLDER=str(folder)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", check=False,
        )
        if result.returncode != 0 or folder.exists():
            raise RuntimeError(f"Could not send to the Recycle Bin:\n{folder}\n{result.stderr.strip()}")


def organize_retained_plan(
    existing: Optional[Path],
    recycle: Path,
    destination: Path,
    releases: List[Release],
    decisions: List[ReleaseDecision],
    move: bool,
    options: Dict[str, object],
    progress_cb=None,
    extra_roots: Sequence[Path] = (),
) -> Dict[str, object]:
    """Run every retained release through the Organizer into destination.

    Sources are never modified by the organizer. With move=True the source folders
    of releases that finished fully compliant go to the Recycle Bin afterwards.
    """
    destination = Path(destination).expanduser()
    by_id = {release.rid: release for release in releases}
    chosen: List[Release] = []
    for decision in decisions:
        release = by_id.get(decision.release_id)
        if release is not None and decision.action in {"KEEP", "ADD", "REPLACE"}:
            chosen.append(release)
    if not chosen:
        raise RuntimeError("No retained releases are selected.")

    resolved_destination = destination.resolve(strict=False)
    for root in (existing, recycle, *extra_roots):
        if root is None:
            continue
        resolved_root = Path(root).resolve(strict=False)
        if (resolved_destination == resolved_root or _is_ancestor(resolved_root, resolved_destination)
                or _is_ancestor(resolved_destination, resolved_root)):
            raise RuntimeError(
                "Destination must be outside the source collection folders:\n\n"
                f"Destination: {destination}\nSource: {root}"
            )

    intra_duplicates = plan_intra_release_duplicates(chosen, [d for d in decisions if d.release_id in {r.rid for r in chosen}])
    skip_files = {item.redundant.resolve(strict=False) for item in intra_duplicates}

    groups: List[Tuple[str, Tuple[Path, ...], Path]] = []
    artist_votes: Counter = Counter()
    for release in chosen:
        root = release.scan_root or (existing if release.root_kind == "existing" else recycle)
        if root is None:
            raise RuntimeError(f"Missing source root for: {release.path}")
        root = Path(root).resolve(strict=False)
        members = tuple(Path(path).resolve(strict=True) for path in _release_paths(release))
        for member in members:
            if member == root or not _is_ancestor(root, member):
                raise RuntimeError(f"Release is outside its source root:\n\nRelease: {member}\nRoot: {root}")
        if len(members) > 1:
            sibling = _sibling_disc_parts(members[0].name)
            source_name = sibling[0] if sibling else members[0].parent.name
        else:
            source_name = members[0].name
        groups.append((source_name, members, root))
        artist_votes[_discography_artist_folder_name(release)] += 1
    artist_main = next((name for name, _count in artist_votes.most_common() if name), "")
    consensus = collection_credit_consensus([m for _n, members, _r in groups for m in members], artist_main)

    file_format = str(options.get("format", "ALAC"))
    engine = Organizer(
        file_format, options.get("encoding_workers", 4), options.get("checker_workers", 4),
        options.get("enable_encoding", True), options.get("enable_checker", True),
        options.get("enable_splitting", True), progress_cb,
    )
    engine.organize_groups(groups, destination, file_format, artist_main, consensus, skip_files)
    if engine.error:
        raise RuntimeError(engine.error)

    created = [Path(row["target"]) for row in engine.results
               if row["status"] in {"done", "partial"} and Path(row["target"]).is_dir()]
    if created:
        artwork = Organizer(file_format, progress_cb=progress_cb)
        artwork.counts["total"] = len(created)
        artwork._download_artwork(destination.resolve(strict=True), created)

    recycled = 0
    if move:
        compliant = {row["source"] for row in engine.results if row["status"] == "done"}
        folders = [member for _n, members, _r in groups if str(members[0]) in compliant for member in members]
        _send_folders_to_recycle_bin(folders)
        recycled = len(folders)
        for root in {root for _n, _m, root in groups}:
            _remove_empty_dirs(root)
        # The Recycle Bin is the way back for a Move; an Undo would only delete the new output.
        UNDO.unlink(missing_ok=True)
        ARTWORK_UNDO.unlink(missing_ok=True)

    return {
        "mode": "move_all" if move else "copy_all",
        "destination": str(destination),
        "logical_releases": len(groups),
        "counts": dict(engine.counts),
        "problems": [f"{row['status'].upper()}: {row['name']} - {row['message']}"
                     for row in engine.results if row["status"] in {"partial", "failed"}],
        "duplicate_files_omitted": len(skip_files),
        "source_folders_modified": recycled > 0,
        "source_folders_recycled": recycled,
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


def undo_last_run() -> Tuple[int, List[str]]:
    """Remove the output of the last Copy (artwork first, then releases).

    Falls back to a Move journal written by MCC v0.5.123 or older.
    """
    if _last_manifest_path().is_file():
        return _undo_legacy_move()
    engine = Organizer()
    removed = 0
    for journal_path, undo in ((ARTWORK_UNDO, engine._undo_artwork), (UNDO, engine._undo)):
        journal = read_json(journal_path, None)
        if not journal:
            continue
        undo(journal)
        if engine.error:
            raise RuntimeError(engine.error)
        removed += len(journal.get("created", []))
    if not removed:
        raise RuntimeError("Nothing to undo.")
    return removed, []


def _undo_legacy_move() -> Tuple[int, List[str]]:
    """Undo a journaled Move made by MCC v0.5.123 or older."""
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
        importlib.import_module("mutagen")
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
            "mutagen>=1.47,<2",
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


DESIGN_CANVAS_HEX = "#0B0E11"  # --canvas in APP_STYLE_CSS (native window background)


APP_STYLE_CSS = r"""
:root {
  color-scheme:dark;
  --primary:#C6F432; --primary-active:#A9D61C; --primary-disabled:#2F3A14; --on-primary:#181A20; --accent:#2DBDB6;
  --canvas:#0B0E11; --surface-card:#1E2329; --surface-elevated:#2B3139; --text:#FFFFFF; --body:#EAECEF;
  --muted:#848E9C; --muted-strong:#929AA5; --hairline:#2B3139; --border-strong:#474D57;
  --positive:#0ECB81; --negative:#F6465D; --info:#3B82F6;
  --font-sans:Inter,-apple-system,"Segoe UI",Roboto,sans-serif;
  --font-numeric:"JetBrains Mono",ui-monospace,Consolas,monospace;
  --font-symbol:"Segoe UI Emoji","Segoe UI Symbol","Segoe UI",sans-serif;
  --radius-xs:2px; --radius-sm:4px; --radius-md:6px; --radius-lg:8px; --radius-xl:12px; --radius-pill:9999px;
  --space-xxs:4px; --space-xs:8px; --space-sm:12px; --space-md:16px; --space-lg:24px; --space-xl:32px;
  --focus-ring:0 0 0 2px rgba(59,130,246,.5); --focus-ring-inset:inset 0 0 0 2px rgba(59,130,246,.5);
}


* { box-sizing:border-box; }
html,body { margin:0; width:100%; height:100%; overflow:hidden; background:var(--canvas); color:var(--body);
  font:400 13px/1.5 var(--font-sans); }
body { display:flex; flex-direction:column; position:relative; }
button,input,select { font:inherit; }
button { user-select:none; text-box:trim-both cap alphabetic; }
:focus-visible { outline:none; box-shadow:var(--focus-ring); }

/* Icons are drawn as masks (not font glyphs) so they are exactly centred in their buttons and follow the text colour. */
#closeDetailsBtn,.clearBtn,.rowMenuBtn,.starBtn,.drawnFolder {font-size:0 !important;}
.clearBtn,.rowMenuBtn,.starBtn,.drawnFolder {position:relative;}
#closeDetailsBtn::before,.clearBtn::before,.rowMenuBtn::before,.starBtn::before,.drawnFolder::before {content:"";position:absolute;inset:0;margin:auto;width:14px;height:14px;background:currentColor;-webkit-mask:var(--icon) center/contain no-repeat;mask:var(--icon) center/contain no-repeat;}
#closeDetailsBtn,.clearBtn {--icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 14 14'%3E%3Cpath d='M3 3L11 11M11 3L3 11' stroke='black' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E");}
.rowMenuBtn {--icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='3' cy='8' r='1.7'/%3E%3Ccircle cx='8' cy='8' r='1.7'/%3E%3Ccircle cx='13' cy='8' r='1.7'/%3E%3C/svg%3E");}
.drawnFolder {--icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M1 2.75h5l1.5 2H15v8.5H1z'/%3E%3C/svg%3E");}
.starBtn {--icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpolygon points='8.00,2.03 9.55,6.49 14.28,6.59 10.51,9.45 11.88,13.97 8.00,11.27 4.12,13.97 5.49,9.45 1.72,6.59 6.45,6.49' fill='none' stroke='black' stroke-width='1.4' stroke-linejoin='round'/%3E%3C/svg%3E");}
.starBtn.on {--icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpolygon points='8.00,1.22 9.76,6.29 15.13,6.40 10.85,9.64 12.41,14.78 8.00,11.72 3.59,14.78 5.15,9.64 0.87,6.40 6.24,6.29'/%3E%3C/svg%3E");}
.iconBtn,.pathOpenBtn,.starBtn {line-height:1;}
/* Segoe UI puts capital letters ~1px below the middle of the line box; trim the box to cap height so labels are centred. */
button {text-box:trim-both cap alphabetic;}

body {position:relative;}
#toolbar {z-index:20;}
#changeBar {position:absolute;right:10px;top:46px;width:210px;display:none;flex-direction:column;align-items:stretch;gap:4px;padding:8px;background:var(--surface-card);border:1px solid var(--hairline);border-radius:var(--radius-lg);z-index:40;}
#changeBar.open {display:flex;}
#changeBar button {text-align:left;}
#changeBar .menuLabel {margin:8px 2px 0;color:var(--muted-strong);font-size:12px;}
#changeBar #sourceLegend {display:flex;flex-direction:column;align-items:stretch;}
#changeBar .sourceLegendPill {max-width:none;}
#planCounts {display:none;}
#statusLine {flex:1 1 200px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--body);font-size:12px;padding:0 8px;}
.reviewBtn {border-color:var(--info);background:var(--canvas);color:var(--text);}
.reviewBtn.open {background:var(--canvas);}
.viewBtn,.changeChip {height:26px;border:1px solid var(--hairline);border-radius:var(--radius-md);background:var(--surface-card);color:var(--body);padding:0 8px;cursor:pointer;white-space:nowrap;font-size:12px;font-weight:600;}
.viewBtn:hover,.changeChip:hover:not(:disabled) {background:var(--surface-elevated);border-color:var(--hairline);color:var(--text);}
.viewBtn.active {background:var(--canvas);border-color:var(--info);color:var(--text);}
.changeChip.active {background:var(--surface-card);border-color:var(--border-strong);color:var(--text);}
.changeChip:disabled {opacity:.38;cursor:default;}
.changeChip.added {color:var(--positive);}
.changeChip.upgraded {color:var(--accent);}
.changeChip.removed {color:var(--negative);}
.changeChip.ignored {color:var(--negative);}
#title {font-weight:600;font-size:16px;margin-right:2px;white-space:nowrap;}
.planCount {height:26px;display:flex;align-items:center;padding:0 8px;border:1px solid var(--hairline);border-radius:var(--radius-md);background:var(--surface-card);color:var(--body);font-size:12px;font-weight:600;}
#resultCounts.changed {border-color:var(--border-strong);background:var(--canvas);color:var(--body);}
#resultCounts.pending {border-color:var(--accent);background:var(--canvas);color:var(--accent);}
#search {width:auto;max-width:300px;min-width:120px;flex:0 1 240px;height:30px;border:1px solid transparent;border-radius:var(--radius-md);background:var(--surface-elevated);color:var(--text);padding:0 8px;outline:none;}
#search:focus {background:var(--surface-elevated);}
#modeText {min-width:0;max-width:440px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--body);font-size:12px;padding-left:4px;}
#spacer {flex:1 1 20px;min-width:0;}
#modeText:empty {display:none;}
@media (max-width:1250px) {
  #toolbar {gap:8px;padding:0 12px;}
  #modeText {display:none;}
  #planCounts {min-width:0;flex:0 1 auto;}
  .planCount {min-width:0;max-width:210px;overflow:hidden;text-overflow:ellipsis;}
  #search {min-width:140px;flex-basis:200px;}
}
@media (max-width:1100px) {
  #title {font-size:16px;}
  .planCount {max-width:180px;padding:0 8px;font-size:12px;}
  #search {min-width:110px;}
  .btn {padding:0 8px;}
}
#main {min-height:0;flex:1;display:flex;position:relative;}
#boardViewport {position:relative;min-width:0;flex:1;overflow-y:auto;overflow-x:hidden;background:var(--canvas);container-name:release-map-viewport;container-type:inline-size;}
#boardContent {position:relative;width:100%;min-width:0;min-height:100%;padding:0 0 24px;}
#boardContent.changesContent {min-height:0;padding-bottom:12px;}
#boardContent.changesContent #connections {display:none;width:0 !important;height:0 !important;}
#connections {position:absolute;inset:0;pointer-events:none;overflow:visible;z-index:1;}
#columns {position:relative;z-index:2;display:grid;grid-template-columns:repeat(var(--visible-columns,3),minmax(0,1fr));align-items:start;width:100%;min-width:0;}
#columns.changesMode {display:block;padding:12px 16px 24px;}
#changeList {width:min(1560px,100%);margin:0 auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(540px,100%),1fr));gap:12px;align-items:start;}
#changeList .changeSection {margin:0;}
.changeSection {margin:0 0 16px;border:1px solid var(--hairline);border-radius:var(--radius-lg);background:color-mix(in srgb, var(--canvas) 58%, transparent);overflow:hidden;}
.changeSectionHead {display:flex;align-items:center;gap:8px;min-height:34px;padding:8px 12px;background:var(--surface-card);border-bottom:1px solid var(--hairline);font-size:12px;font-weight:600;}
.changeSectionCount {color:var(--muted-strong);font-size:12px;font-weight:600;}
.changeRow {min-width:0;min-height:43px;display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:center;gap:8px;padding:8px 12px;border-top:1px solid var(--hairline);cursor:pointer;}
.changeSectionHead + .changeRow {border-top:0;}
.changeRow:hover {background:var(--surface-elevated);}
.changeRow:focus-visible {outline:none;box-shadow:var(--focus-ring-inset);}
.changeRow.selected {background:var(--canvas);border-left:4px solid var(--info);}
.changeIcon {width:24px;text-align:center;font-size:16px;font-weight:600;line-height:1;font-family:var(--font-symbol);}
.changeIcon.added {color:var(--positive);}
.changeIcon.upgraded {color:var(--accent);}
.changeIcon.replaced {color:var(--info);}
.changeIcon.removed,.changeIcon.ignored {color:var(--negative);}
.changeMain {min-width:0;}
.changeName {color:var(--text);font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.changeReason {margin-top:2px;color:var(--muted-strong);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.changeType {color:var(--muted-strong);font-size:12px;font-weight:600;text-transform:uppercase;}
.changeEmpty {padding:28px 16px;text-align:center;color:var(--muted-strong);font-size:12px;}
.rowChangeIcon {flex:0 0 auto;min-width:16px;text-align:center;font-size:13px;font-weight:600;line-height:1;font-family:var(--font-symbol);}
.rowChangeIcon.added {color:var(--positive);}
.rowChangeIcon.upgraded {color:var(--accent);}
.rowChangeIcon.replaced {color:var(--info);}
.rowChangeIcon.removed,.rowChangeIcon.ignored {color:var(--negative);}
.releaseColumn {min-width:0;display:flex;flex-direction:column;padding:0 8px 12px;border-left:1px solid var(--hairline);}
.releaseColumn:first-child {border-left:0;}
.releaseColumn {container-name:release-category;container-type:inline-size;}
.releaseGroups {min-width:0;column-count:1;column-gap:8px;column-fill:balance;padding-bottom:4px;}
.releaseGroups .releaseGroup {display:block;break-inside:avoid-column;page-break-inside:avoid;margin:0 0 2px;}
.releaseColumnHeader {position:sticky;top:0;z-index:5;margin:0 -8px 2px;padding:8px 8px 8px;background:color-mix(in srgb, var(--canvas) 97%, transparent);border-bottom:1px solid var(--hairline);font-size:16px;font-weight:600;}
.releaseGroup {min-width:0;margin:0;padding:0;border:0;border-bottom:1px solid var(--hairline);border-radius:0;background:transparent;}
.releaseGroupTitle {margin:0;padding:4px 4px 4px;color:var(--body);font-size:12px;font-weight:600;border-bottom:1px solid var(--hairline);white-space:nowrap;overflow:hidden;display:flex;align-items:center;gap:4px;}
.groupStatusIcon {flex:0 0 auto;min-width:16px;text-align:center;font-size:13px;line-height:1;font-family:var(--font-symbol);}
.groupStatusIcon.keep {color:var(--positive);font-family:var(--font-symbol);font-weight:600;}
.groupStatusIcon.add {color:var(--positive);font-family:var(--font-symbol);font-weight:600;}
.groupTitleText {min-width:0;overflow:hidden;text-overflow:ellipsis;}
.releaseGroup.compilationGroup .releaseGroupTitle {color:var(--accent);}
.releaseRow {position:relative;height:30px;display:flex;align-items:center;gap:8px;padding:0 4px;border:0;border-top:2px solid var(--hairline);border-radius:0;color:var(--text);cursor:pointer;user-select:none;transition:background .10s ease,opacity .10s ease,box-shadow .10s ease;}
.releaseGroupTitle + .releaseRow {border-top:0;}
.releaseRow.retained {background:color-mix(in srgb, var(--surface-card) 50%, transparent);color:var(--text);}
.releaseRow.retained .releaseName {color:var(--text);font-weight:600;}
.releaseRow:hover {background:var(--surface-elevated);border-color:var(--hairline);}
.releaseRow:focus-visible {outline:none;box-shadow:var(--focus-ring);}
.releaseRow.selected {opacity:1 !important;background:var(--canvas);border-color:var(--info);}
.releaseRow.duplicate {height:28px;opacity:.85;color:var(--body);background:transparent;}
.releaseRow.duplicate:hover {opacity:1;background:var(--surface-elevated);}
.releaseRow.duplicate .releaseName {color:var(--body);font-weight:400;}
.releaseRow.duplicate .folderIcon {filter:grayscale(1);opacity:.70;}
.releaseRow.retained.originOld .folderIcon {background:var(--muted-strong);}
.releaseRow.retained.originOld .folderIcon:before {background:var(--muted-strong);}
.releaseRow.retained.originNew .folderIcon {background:var(--positive);}
.releaseRow.retained.originNew .folderIcon:before {background:var(--positive);}
.releaseRow.ignored {color:var(--negative);background:color-mix(in srgb, var(--negative) 16%, transparent);border-color:var(--negative);border-left:4px solid var(--negative);}
.releaseRow.ignored .releaseName {color:var(--negative);}
.releaseRow.pendingIgnore {color:var(--accent);background:color-mix(in srgb, var(--accent) 16%, transparent);border-color:var(--accent);border-left:4px solid var(--accent);}
.releaseRow.pendingRestore {color:var(--positive);background:color-mix(in srgb, var(--positive) 16%, transparent);border-color:var(--positive);border-left:4px solid var(--positive);}
.releaseRow.carrier {border-color:var(--info);background:var(--canvas);color:var(--text);}
.releaseRow.searchMatch {opacity:1 !important;border-color:var(--accent);background:var(--surface-card);}
.releaseRow.searchDimmed {opacity:.34 !important;}
.releaseRow.dimmed {opacity:.36 !important;}
.releaseRow.carrier {opacity:1 !important;}
/* Transient Re-Analyze change markers (color + symbol). No animation. */
.releaseRow.reanalysisAdded,.changeRow.reanalysisAdded {opacity:1 !important;background:color-mix(in srgb, var(--positive) 16%, transparent) !important;border-left:4px solid color-mix(in srgb, var(--positive) 70%, transparent);}
.releaseRow.reanalysisRemoved,.changeRow.reanalysisRemoved {opacity:1 !important;background:color-mix(in srgb, var(--negative) 16%, transparent) !important;border-left:4px solid color-mix(in srgb, var(--negative) 70%, transparent);}
.releaseRow.reanalysisAdded .releaseName{color:var(--positive);}
.releaseRow.reanalysisRemoved .releaseName{color:var(--negative);}
.releaseRow.reanalysisAdded::after,.releaseRow.reanalysisRemoved::after {content:"+";flex:0 0 auto;padding:0 4px;font:600 12px/1 var(--font-sans);color:var(--positive);}
.releaseRow.reanalysisRemoved::after{content:"−";color:var(--negative);}
.changeRow{position:relative;}
.changeRow.reanalysisAdded::before,.changeRow.reanalysisRemoved::before{content:"+";position:absolute;top:2px;right:6px;line-height:1;font-weight:600;color:var(--positive);pointer-events:none;}
.changeRow.reanalysisRemoved::before{content:"−";color:var(--negative);}
.folderIcon {position:relative;width:16px;height:11px;flex:0 0 16px;border-radius:var(--radius-xs);background:var(--accent);}
.folderIcon:before {content:"";position:absolute;left:1px;top:-4px;width:8px;height:5px;border-radius:var(--radius-xs) var(--radius-xs) 0 0;background:var(--accent);}
.releaseName {min-width:0;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px;}
.releaseMeta {flex:0 0 auto;color:var(--muted-strong);font-size:12px;}
#sourceLegend {display:flex;align-items:center;gap:4px;min-width:0;}
.sourceLegendPill {min-width:0;max-width:220px;height:26px;display:flex;align-items:center;gap:8px;border:1px solid var(--hairline);border-radius:var(--radius-md);padding:0 8px;background:var(--surface-card);color:var(--muted-strong);font-size:12px;}
.sourceLegendPill b {flex:0 0 auto;font-size:12px;}
.sourceLegendPill span {min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sourceLegendPill.old b {color:var(--info);}
.sourceLegendPill.new b {color:var(--positive);}
.sourceSummary {margin:0 0 8px;color:var(--body);font-size:12px;line-height:1.4;overflow-wrap:anywhere;}
.sourceSummary strong {color:var(--body);}
.ripMark {background:var(--surface-elevated);border-color:transparent;color:var(--info);}
.ripMark.log {background:var(--surface-card);border-color:transparent;color:var(--positive);}
.ripMark.log.unscored {background:var(--surface-elevated);border-color:transparent;color:var(--body);}
.ripLogLine {color:var(--body);font-size:12px;}
#exportBar {display:none;flex:0 0 auto;padding:8px 12px;background:var(--surface-card);gap:8px;}
#exportBar.open {display:grid;grid-template-columns:1fr 1fr;}
.exportChoice {min-width:0;display:grid;grid-template-columns:auto 30px minmax(120px,1fr) auto auto;gap:4px;align-items:center;padding:4px 8px;border-radius:var(--radius-lg);background:transparent;}
.exportLabel {min-width:0;white-space:nowrap;font-size:12px;}
#organizerBar {grid-column:1 / -1;display:flex;gap:12px;align-items:center;padding:2px 8px;}
.exportPath {min-width:0;height:30px;display:flex;align-items:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;border:0;border-radius:var(--radius-md);background:var(--surface-elevated);color:var(--muted);padding:0 8px;font-size:13px;}
@media (max-width:1250px) {
  #sourceLegend {display:none;}
  #exportBar.open {grid-template-columns:1fr;}
}
@media (max-width:850px) {
  .exportChoice {grid-template-columns:1fr 30px minmax(90px,1fr) auto;}
  .exportLabel {grid-column:1 / -1;}
}

/* Docked details share the row so the release list stays visible. */
#details {min-width:0;min-height:0;flex:0 0 52%;max-width:720px;overflow:hidden;background:var(--canvas);display:none;flex-direction:column;border-left:1px solid var(--hairline);}
#details.open {display:flex;}
#detailsInner {width:100%;min-width:0;height:100%;display:flex;flex-direction:column;}
#emptyDetails {margin:auto;color:var(--muted);text-align:center;padding:32px;}
#detailsHead {position:relative;padding:8px 12px;border-bottom:1px solid var(--hairline);}
#closeDetailsBtn {position:absolute;right:12px;top:5px;width:28px;height:28px;padding:0;border:1px solid transparent;border-radius:var(--radius-md);background:var(--surface-card);color:var(--text);font-size:20px;line-height:24px;cursor:pointer;}
#closeDetailsBtn:hover {background:var(--border-strong);color:var(--text);}
#releaseName {font-size:16px;line-height:1.3;font-weight:600;margin-bottom:8px;padding-right:36px;overflow-wrap:anywhere;color:var(--text);}
#releaseActions {display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 12px;margin:0 0 8px;}
.releaseBadges {display:flex;flex-wrap:wrap;align-items:center;gap:8px;}
.tick {margin-left:4px;color:var(--positive);font-weight:600;}
.perfectRip {display:inline-flex;align-items:center;gap:8px;}
.perfectTick {color:var(--accent);font-size:24px;font-weight:600;line-height:1;margin-left:2px;}
.planBadge {padding:1px 8px;border-radius:var(--radius-md);font-size:12px;font-weight:600;border:1px solid transparent;}
.planBadge.keep {background:var(--surface-card);border-color:transparent;color:var(--positive);}
.planBadge.drop {background:color-mix(in srgb, var(--negative) 16%, transparent);border-color:transparent;color:var(--negative);}
#essentialCount {color:var(--accent);font-weight:600;}

.releaseButtons {display:flex;gap:8px;align-items:center;}
.releaseButtons .btn,.changeGroupSelect {background:var(--surface-card);border:1px solid transparent;color:var(--text);font-size:13px;height:28px;padding:0 12px;border-radius:var(--radius-md);}
.changeGroupSelect {max-width:200px;padding:0 8px;cursor:pointer;}
.releaseButtons .btn:hover,.changeGroupSelect:hover {background:var(--border-strong);color:var(--text);}
.mediumBadge,.ripMark {display:inline-block;padding:1px 8px;border-radius:var(--radius-md);font-size:12px;font-weight:600;line-height:15px;border:1px solid transparent;}
.mediumBadge {background:var(--surface-elevated);border-color:transparent;color:var(--info);}
#details .releaseButtons #ignoreReleaseBtn {background:color-mix(in srgb, var(--negative) 16%, transparent);border-color:transparent;color:var(--negative);font-weight:600;}
#details .releaseButtons #ignoreReleaseBtn:hover {background:color-mix(in srgb, var(--negative) 16%, transparent);color:var(--text);}
#ignoreReleaseBtn.restore {background:color-mix(in srgb, var(--positive) 16%, transparent);border-color:var(--positive);color:var(--positive);}
#ignoreReleaseBtn.restore:hover {background:color-mix(in srgb, var(--positive) 16%, transparent);border-color:var(--positive);color:var(--text);}
.ignoredNotice {margin:0 0 12px;padding:8px 12px;border:1px solid var(--negative);border-radius:var(--radius-md);background:var(--surface-card);color:var(--negative);font-size:12px;line-height:1.4;}
.pendingNotice {margin:0 0 12px;padding:8px 12px;border:1px solid var(--accent);border-radius:var(--radius-md);background:var(--canvas);color:var(--accent);font-size:12px;line-height:1.4;}
#pathRow {display:flex;gap:8px;align-items:center;}
#releasePath {flex:1;min-width:0;color:var(--text);background:var(--surface-elevated);border:0;border-radius:var(--radius-md);padding:2px 8px;font-family:var(--font-numeric);font-size:12px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;user-select:text;cursor:text;line-height:18px;}
#tracks {min-height:0;flex:1;overflow:auto;padding:4px 8px 12px;display:grid;grid-template-columns:22px minmax(0,1fr) 42px max-content 28px;column-gap:8px;align-content:start;}
#tracks > .altVersions,#tracks > .altRemixes,#tracks > .altLive {grid-column:1 / -1;}
.track {display:grid;grid-template-columns:subgrid;grid-column:1 / -1;position:relative;align-items:center;min-height:28px;padding:2px 4px 2px 8px;border-bottom:1px solid var(--hairline);border-radius:var(--radius-sm);color:var(--text);font-size:12px;cursor:pointer;}
.track:hover {background:var(--surface-elevated);}
#details button:focus-visible,#details select:focus-visible,#details .track:focus-visible {outline:none;background:var(--surface-card);}
.track.unique {background:color-mix(in srgb, var(--accent) 5%, transparent);border-left:4px solid var(--accent);}
.track.orphan {background:color-mix(in srgb, var(--negative) 14%, transparent);}
.track.activeTrack {background:var(--surface-card);}
.track.manual {color:var(--info);}
.track.skipped {color:var(--muted-strong);}
.track.skipped .titleText {color:var(--muted-strong);}
.track.skipped:hover {background:var(--surface-elevated);}
.track .num {color:var(--muted-strong);text-align:right;align-self:center;font-variant-numeric:tabular-nums;}
.track .dur {color:var(--muted);text-align:right;align-self:center;font-variant-numeric:tabular-nums;}
.track .titleCell {display:flex;align-items:center;min-width:0;gap:4px;}
.tagsCell {display:flex;align-items:center;gap:8px;min-width:0;}

.track .dur.differentLength {color:var(--accent);font-weight:600;}
.track .lengthDelta {display:inline-block;white-space:nowrap;font-size:12px;font-weight:600;line-height:1.3;color:var(--accent);background:color-mix(in srgb, var(--accent) 16%, transparent);border:1px solid var(--accent);border-radius:var(--radius-sm);padding:1px 4px;}
.altVersion .altLengthDelta {white-space:nowrap;color:var(--accent);background:var(--surface-card);border:1px solid var(--accent);border-radius:var(--radius-sm);padding:1px 4px;font-size:12px;font-weight:600;}

.track .titleText {flex:0 1 auto;min-width:0;overflow-wrap:anywhere;white-space:normal;line-height:1.35;padding:2px 0;}
.track .advisoryBadge {display:inline-flex;align-items:center;justify-content:center;vertical-align:baseline;min-width:14px;height:15px;margin-left:4px;border-radius:var(--radius-sm);font-size:12px;font-weight:600;line-height:1;border:1px solid var(--negative);background:var(--surface-elevated);color:var(--negative);}
.track .advisoryBadge.clean {border-color:var(--positive);background:var(--surface-card);color:var(--positive);}
.trackGem {display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:26px;font-family:var(--font-symbol);font-size:16px;}
.track.unique .status {color:var(--accent);font-weight:600;}
.track .status {color:var(--body);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;align-self:center;font-size:12px;}
.track .status.replacement {color:var(--positive);font-weight:600;}
.track .status.missing {color:var(--negative);font-weight:600;}
.versionsCell {display:flex;align-items:center;justify-content:flex-start;flex-wrap:wrap;gap:4px;align-self:center;min-width:0;}
.versionsTrack,.remixesTrack,.liveTrack {height:26px;border-radius:var(--radius-md);padding:0 8px;cursor:pointer;font-size:12px;font-weight:600;white-space:nowrap;}
.versionsTrack {border:1px solid var(--accent);background:var(--surface-card);color:var(--accent);}
.versionsTrack:hover {background:color-mix(in srgb, var(--accent) 16%, transparent);border-color:var(--accent);color:var(--accent);}
.remixesTrack {border:1px solid var(--info);background:var(--surface-card);color:var(--info);}
.remixesTrack:hover {background:color-mix(in srgb, var(--info) 16%, transparent);border-color:var(--info);color:var(--text);}
.liveTrack {border:1px solid var(--negative);background:var(--surface-card);color:var(--negative);}
.liveTrack:hover {background:var(--surface-elevated);border-color:var(--negative);color:var(--text);}
.altVersions,.altRemixes,.altLive {display:none;margin:2px 8px 8px 52px;border-radius:var(--radius-lg);overflow:hidden;}
.altVersions {border:1px solid var(--accent);background:var(--canvas);}
.altRemixes {border:1px solid var(--info);background:var(--canvas);}
.altLive {border:1px solid var(--accent);background:var(--canvas);}
.altVersions.open,.altRemixes.open,.altLive.open {display:block;}
.altVersionsHead,.altRemixesHead,.altLiveHead {padding:8px 12px;border-bottom:1px solid var(--hairline);font-size:12px;font-weight:600;text-transform:uppercase;}
.altVersionsHead {color:var(--accent);background:var(--canvas);border-bottom-color:var(--accent);}
.altRemixesHead {color:var(--info);background:var(--surface-card);border-bottom-color:var(--info);}
.altLiveHead {color:var(--positive);background:var(--canvas);border-bottom-color:var(--accent);}
.altVersion {width:100%;display:grid;grid-template-columns:minmax(160px,1fr) 78px 80px minmax(120px,1fr);gap:8px;align-items:center;padding:8px 12px;border:0;border-bottom:1px solid var(--hairline);background:transparent;color:var(--text);text-align:left;cursor:pointer;font-size:12px;}
.altVersion:last-child {border-bottom:0;}
.altVersion:hover {background:var(--surface-elevated);}
.altVersion .altTitle {overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;}
.altVersion .altDuration {color:var(--muted-strong);text-align:center;display:flex;flex-direction:column;gap:2px;justify-content:center;align-items:center;}
.altVersion .altDuration.changed {color:var(--accent);font-weight:600;}
.altVersion .altState {color:var(--muted-strong);white-space:nowrap;}
.altVersion .altState.retained {color:var(--positive);}
.altVersion .altState.available {color:var(--accent);}
.altVersion .altReleases {color:var(--muted-strong);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.trackActionGroup {position:fixed;z-index:50;display:none;flex-direction:column;align-items:stretch;gap:2px;min-width:150px;padding:4px;border-radius:var(--radius-lg);background:var(--surface-card);}
.track.menuOpen .trackActionGroup {display:flex;}
.rowMenuCell {display:flex;justify-content:center;}
.rowMenuBtn {width:28px;height:22px;padding:0;border:0;border-radius:var(--radius-sm);background:transparent;color:var(--muted-strong);font-size:16px;line-height:1;cursor:pointer;}
.rowMenuBtn:hover,.track.menuOpen .rowMenuBtn {background:var(--surface-elevated);color:var(--body);}
.patternMark,.patternBadge {display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;height:28px;padding:0 12px;box-sizing:border-box;white-space:nowrap;justify-content:flex-start;border-radius:var(--radius-sm);border:0;background:transparent;color:var(--body);cursor:pointer;font:500 12px/1 var(--font-sans);}
.patternMark:hover,.patternBadge:hover {background:var(--surface-elevated);}
.ignoreTrack {display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;height:28px;padding:0 12px;justify-content:flex-start;border:0;border-radius:var(--radius-sm);background:transparent;color:var(--negative);font-size:12px;font-weight:600;cursor:pointer;}
.ignoreTrack:hover {background:color-mix(in srgb, var(--negative) 16%, transparent);color:var(--text);}
button:focus-visible,input:focus-visible {outline:none;box-shadow:var(--focus-ring);}
.pathOpenBtn {width:30px;min-width:30px;padding:0;display:inline-flex;align-items:center;justify-content:center;}
.resultAdd {color:var(--positive);} .resultRemove {color:var(--negative);}
#auditBanner{display:none;position:absolute;right:10px;top:46px;width:min(620px,calc(100vw - 20px));max-height:60vh;overflow:auto;flex-direction:column;gap:2px;padding:8px;background:var(--surface-card);border:1px solid var(--hairline);border-radius:var(--radius-lg);z-index:41;font-size:12px;}
#auditBanner.visible{display:flex;}
#auditBanner .auditIntro{color:var(--muted-strong);font-size:12px;padding:2px 8px 8px;}
#auditBanner .auditJump{display:block;width:100%;border:0;border-radius:var(--radius-md);background:none;color:var(--text);font:inherit;padding:8px;text-align:left;cursor:pointer;min-width:0;}
#auditBanner .auditJump:hover{background:var(--surface-elevated);}
#auditBanner .auditJump:focus-visible{outline:none;box-shadow:var(--focus-ring-inset);}
#auditBanner .auditName{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#auditBanner .auditWhy{display:block;color:var(--accent);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#auditBanner .auditHint{color:var(--body);font-size:12px;padding:4px 8px;}
#details .auditNotice{padding:8px 12px;margin:4px 0;background:var(--surface-elevated);color:var(--accent);white-space:pre-wrap;font-size:12px;border-left:3px solid var(--accent);}
/*APP_THEME*/
#content{flex:1;min-height:0;display:grid;grid-template-rows:auto auto minmax(180px,1fr);gap:4px;padding:4px 8px;overflow:auto;}
#content.emptyActivity{grid-template-rows:auto auto;align-content:start;}
#content.emptyActivity .activityCard{display:none;}
.card{border-radius:var(--radius-lg);background:var(--canvas);}
.cardHead{display:flex;align-items:center;justify-content:space-between;padding:4px 8px 2px;}
.cardTitle{font-size:14px;font-weight:600;}
.sources{padding:8px 8px;}
.sourceBlock+.sourceBlock{margin-top:4px;}
.labelRow{display:flex;align-items:baseline;gap:8px;margin-bottom:1px;}
.fieldLabel{font-weight:600;}
.pathRow{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto auto;gap:4px;}
.starBtn{font-size:16px;line-height:1;color:var(--muted-strong);}
.starBtn.on{color:var(--accent);border-color:var(--accent);}
.addFolder{margin-top:4px;width:100%;}
.pathInput{width:100%;height:30px;border:1px solid transparent;border-radius:var(--radius-md);background:var(--surface-elevated);color:var(--text);padding:0 12px;outline:none;}
.pathInput:focus{background:var(--surface-elevated);}
button:focus-visible,input:focus-visible{outline:none;box-shadow:var(--focus-ring);}
.btn.danger{border-color:var(--negative);background:color-mix(in srgb, var(--negative) 16%, transparent);color:var(--body);}
.btn.success{border-color:var(--positive);background:color-mix(in srgb, var(--positive) 16%, transparent);color:var(--positive);}
.options{margin-top:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-top:4px;}
.progressCard{padding:4px 8px;}
.progressTop{display:flex;align-items:center;gap:12px;}
#progressStatus{font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#progressPercent{margin-left:auto;color:var(--body);font-variant-numeric:tabular-nums;}
.progressTrack{height:6px;margin-top:4px;border-radius:var(--radius-pill);background:var(--surface-elevated);overflow:hidden;}
#progressFill{height:100%;width:0;background:var(--accent);transition:width .12s ease;}
#progressDetail{margin-top:2px;color:var(--muted);font-size:12px;}
#progressDetail:empty{display:none;}
.activityCard{min-height:0;display:flex;flex-direction:column;}
#activity{flex:1;min-height:120px;margin:0 8px 8px;padding:4px 8px;overflow:auto;border:0;border-radius:var(--radius-lg);background:var(--canvas);color:var(--body);white-space:pre-wrap;font-family:var(--font-numeric);font-size:12px;line-height:1.45;}
#footer{padding:0 12px;}
#footerSpacer{flex:1;}
#modalBackdrop{display:none;position:fixed;inset:0;z-index:100;background:color-mix(in srgb, var(--canvas) 62%, transparent);align-items:center;justify-content:center;padding:28px;}
#modalBackdrop.open{display:flex;}
#modal{width:min(920px,94vw);max-height:88vh;display:flex;flex-direction:column;border:1px solid var(--hairline);border-radius:var(--radius-xl);background:var(--canvas);overflow:hidden;}
#modalHead{padding:16px 16px 12px;border-bottom:1px solid var(--hairline);}
#modalTitle{font-size:16px;font-weight:600;}
#modalSubtitle{margin-top:4px;color:var(--muted);font-size:12px;line-height:1.45;}
#modalSubtitle:empty{display:none;}
#modalBody{padding:12px 16px;overflow:auto;min-height:80px;}
#modalFoot{display:flex;align-items:center;gap:8px;padding:12px 16px;border-top:1px solid var(--hairline);}
.modalSpacer{flex:1;}
.reviewRow{border:1px solid var(--hairline);border-radius:var(--radius-lg);padding:12px 12px;background:var(--surface-card);margin-bottom:8px;}
.reviewTop{display:flex;align-items:center;gap:12px;}
.reviewTitle{font-weight:600;min-width:0;flex:1;}
.reviewMeta{color:var(--muted-strong);font-size:12px;white-space:nowrap;}
.reviewDetails{margin-top:4px;color:var(--muted-strong);font-size:12px;line-height:1.4;}
.reviewCheck{width:16px;height:16px;accent-color:var(--info);}
.categoryKind{min-width:150px;max-width:100%;padding:8px 8px;min-height:32px;border-radius:var(--radius-md);color:var(--text);background:var(--canvas);border:1px solid var(--hairline);font:inherit;font-size:12px;}
.categoryKind:focus-visible{outline:none;box-shadow:var(--focus-ring);}
.patternReviewRow{padding:12px 12px;transition:border-color .1s ease;}
.patternReviewRow.isChosen{border-color:var(--info);}
.patternChoiceGroup{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:8px;}
.patternChoice{display:inline-flex;align-items:center;justify-content:center;min-width:82px;min-height:36px;padding:8px 12px;border-radius:var(--radius-md);border:1px solid var(--hairline);background:var(--surface-card);color:var(--text);font:inherit;font-size:12px;font-weight:600;cursor:pointer;transition:background .12s,border-color .12s;}
.patternChoice:hover{background:var(--surface-elevated);border-color:var(--info);}
.patternChoice:active{background:var(--canvas);}
.patternChoice:focus-visible{outline:none;box-shadow:var(--focus-ring);}
.patternChoice[aria-pressed="true"]{background:var(--canvas);border-color:var(--info);color:var(--text);}
.patternChoice[data-choice="keep"],.patternChoice[data-choice="skip"]{background:var(--surface-card);color:var(--body);}
.patternChoice[data-choice="keep"]:hover,.patternChoice[data-choice="skip"]:hover{background:var(--surface-elevated);color:var(--text);}
.patternChoice[data-choice="keep"][aria-pressed="true"],.patternChoice[data-choice="skip"][aria-pressed="true"]{background:var(--canvas);border-color:var(--muted);color:var(--text);}
@media(max-width:570px){.patternChoice{flex:1 1 calc(50% - 7px);}}
.categoryHeading{font-weight:600;color:var(--body);margin:12px 0 8px;font-size:12px;}
.pendingPatternNames{color:var(--body);font-size:12px;line-height:1.5;padding:8px 12px;border:1px solid var(--hairline);border-radius:var(--radius-md);overflow-wrap:anywhere;}
.categoryRow{grid-template-columns:minmax(0,1fr) 150px auto;}
@media(max-width:570px){.reviewTop{flex-wrap:wrap;}.categoryRow{grid-template-columns:minmax(0,1fr) auto;}.categoryKind{grid-column:1;}}
.picksEntry{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;margin-bottom:12px;}
.picksList{border:1px solid var(--hairline);border-radius:var(--radius-lg);overflow:hidden;}
.picksList .categoryHeading{margin:0;padding:8px 12px;background:var(--surface-card);border-bottom:1px solid var(--hairline);}
.picksList .pickRow{grid-template-columns:68px minmax(0,1fr) auto auto;}
.picksList .pickRemove{grid-column:4;}
.pickFilter{width:100%;margin-bottom:8px;}
.pickEditInput{min-width:0;height:30px;}
.pickRow{display:grid;grid-template-columns:90px minmax(0,1fr) auto;gap:8px;align-items:center;padding:8px 12px;border-bottom:1px solid var(--hairline);background:var(--surface-card);}
.pickRow:last-child{border-bottom:0;}
.pickMode{color:var(--info);font-size:12px;font-weight:600;}
.pickValue{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.empty{color:var(--muted-strong);padding:16px;text-align:center;}
.msg{line-height:1.55;color:var(--body);}
.msgLine{min-height:1.55em;white-space:pre-wrap;}
.msgPathLine{display:flex;align-items:center;gap:8px;min-width:0;}
.msgPathPrefix{white-space:pre-wrap;}
.msgPathValue{min-width:0;word-break:break-all;font-family:var(--font-numeric);font-size:12px;color:var(--body);}
.doneGrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.doneStat{padding:8px 12px;border:1px solid var(--hairline);border-radius:var(--radius-lg);background:var(--surface-card);}
.doneStat b{display:block;font-size:16px;margin-top:2px;}
.pathNote{margin-top:12px;padding:8px 12px;border:1px solid var(--hairline);border-radius:var(--radius-lg);background:var(--canvas);color:var(--muted-strong);font-family:var(--font-numeric);font-size:12px;word-break:break-all;display:flex;align-items:center;gap:8px;}
.pathNoteText{min-width:0;word-break:break-all;}
.appBar { height:44px; min-height:44px; display:flex; align-items:center; gap:8px; padding:0 12px; background:var(--surface-card);
  border-bottom:1px solid var(--hairline); }
#footer.appBar,#exportBar { border-bottom:0; border-top:1px solid var(--hairline); }
.btn,.iconBtn { height:28px; border:0; border-radius:var(--radius-md); background:var(--surface-card); color:var(--text);
  padding:0 12px; font:600 14px/1 var(--font-sans); cursor:pointer; transition:background .12s ease; white-space:nowrap; flex:0 0 auto; }
.appBar .btn,.appBar .iconBtn,#exportBar .btn,#exportBar .iconBtn { background:var(--surface-elevated); }
.btn:hover:not(:disabled),.iconBtn:hover:not(:disabled) { background:var(--border-strong); }
.btn:disabled,.iconBtn:disabled { opacity:.38; cursor:default; }
.btn.primary,.exportCopyBtn { background:var(--primary); color:var(--on-primary); }
.btn.primary:hover:not(:disabled),.exportCopyBtn:hover:not(:disabled) { background:var(--primary-active); }
.btn.primary:disabled,.exportCopyBtn:disabled { background:var(--primary-disabled); color:var(--muted); opacity:1; }
.btn.success,.btn.apply-ready { background:var(--positive); color:var(--on-primary); border-radius:var(--radius-sm); }
.btn.danger { background:var(--negative); color:var(--text); border-radius:var(--radius-sm); }
.btn.dirty { background:var(--accent); color:var(--on-primary); }
.iconBtn { width:28px; padding:0; display:inline-flex; align-items:center; justify-content:center; }
.field,.pathInput,#search,.exportPath { height:30px; border:1px solid transparent; border-radius:var(--radius-lg); background:var(--surface-elevated);
  color:var(--text); padding:0 12px; outline:none; }
.field:focus,.pathInput:focus,#search:focus { border-color:var(--border-strong); }
select { height:28px; border:0; border-radius:var(--radius-md); background:var(--surface-elevated); color:var(--text); padding:0 8px; }
.workerSetting { display:inline-flex; align-items:center; gap:8px; white-space:nowrap; color:var(--body); }
.toggle { display:inline-flex; align-items:center; gap:8px; color:var(--body); cursor:pointer; white-space:nowrap; }
.toggle input { appearance:none; width:36px; height:20px; border-radius:var(--radius-pill); background:var(--surface-elevated);
  border:1px solid var(--border-strong); position:relative; cursor:pointer; transition:.12s; }
.toggle input:after { content:""; position:absolute; width:12px; height:12px; left:3px; top:3px; border-radius:50%; background:var(--muted); transition:.12s; }
.toggle input:checked { background:var(--accent); border-color:var(--accent); }
.toggle input:checked:after { left:19px; background:var(--canvas); }
.card { border-radius:var(--radius-xl); background:var(--surface-card); }

"""


def _apply_app_theme(html: str) -> str:
    return html.replace("/*APP_THEME*/", APP_STYLE_CSS)


def _webview_release_map_html() -> str:
    html = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Music Collection Cleaner - Release Map</title>
<style>/*APP_THEME*/</style>
</head>
<body>
<div id="toolbar" class="appBar">
  <div id="title">Release Map</div>
  <input id="search" aria-label="Find release or track" placeholder="Search">
  <div id="statusLine" aria-live="polite"></div>
  <button class="btn reviewBtn" id="reviewBtn" aria-expanded="false" style="display:none"></button>
  <div id="modeText" aria-live="polite"></div>
  <button class="btn" id="clearTrackBtn" style="display:none">Clear track highlight</button>
  <button class="btn" id="viewMenuBtn" aria-haspopup="true" aria-expanded="false">View ▾</button>
  <button class="btn" id="reanalyzeBtn" disabled>Re-Analyze</button>
  <button class="btn" id="closeBtn">Close</button>
</div>
<div id="auditBanner" role="region" aria-label="Releases that need a look" aria-live="polite"></div>
<div id="changeBar" aria-label="View options">
  <button class="viewBtn active" id="changesViewBtn" aria-pressed="true">Changes</button>
  <button class="viewBtn" id="fullViewBtn" aria-pressed="false">Full map</button>
  <button class="viewBtn" id="connectionsBtn" aria-pressed="false" title="Show every release connection">Show all links</button>
  <div class="menuLabel">Filter changes</div>
  <button class="changeChip added" id="changesAddedBtn" data-filter="added">+ Added</button>
  <button class="changeChip upgraded" id="changesUpgradedBtn" data-filter="upgraded">⬆️ Upgraded</button>
  <button class="changeChip" id="changesReplacedBtn" data-filter="replaced">↔ Replaced</button>
  <button class="changeChip removed" id="changesRemovedBtn" data-filter="removed">- Removed</button>
  <button class="changeChip ignored" id="changesIgnoredBtn" data-filter="ignored">🚫 Ignored</button>
  <div class="menuLabel">Sources</div>
  <div id="sourceLegend" aria-label="Release source legend">
    <div class="sourceLegendPill old" id="oldLegend" title=""><b>OLD</b><span>Existing</span></div>
    <div class="sourceLegendPill new" id="newLegend" title=""><b>NEW</b><span>New / update</span></div>
  </div>
  <div id="planCounts" title="Tracks = counted tracks in retained releases. Skipped/ignored tracks are not counted.">
    <div class="planCount" id="initialCounts">Initial: --</div>
    <div class="planCount" id="resultCounts">Result: --</div>
  </div>
</div>
<div id="main">
  <div id="boardViewport">
    <div id="boardContent">
      <svg id="connections"></svg>
      <div id="columns"></div>
    </div>
  </div>
  <aside id="details" aria-label="Release details">
    <div id="detailsInner"><div id="emptyDetails">Click a release to inspect it.</div></div>
  </aside>
</div>
<div id="exportBar" aria-label="Copy or move retained releases">
  <div class="exportChoice">
    <div class="exportLabel" title="Final improved discography: retained OLD + additions/upgrades from NEW."><b>Copy into:</b></div>
    <button class="btn pathOpenBtn drawnFolder" id="openAllDestination" disabled title="Open destination" aria-label="Open old plus new destination">📁</button>
    <div class="exportPath" id="allDestination" title="">Choose destination...</div>
    <button class="btn" id="chooseAllDestination">Browse...</button>
    <button class="btn exportCopyBtn" id="copyAllBtn" disabled>Copy old + new</button>
  </div>
  <div class="exportChoice">
    <div class="exportLabel" title="Same as Copy; originals of finished releases go to the Recycle Bin."><b>Move into:</b></div>
    <button class="btn pathOpenBtn drawnFolder" id="openNewDestination" disabled title="Open destination" aria-label="Open move destination">📁</button>
    <div class="exportPath" id="newDestination" title="">Choose destination...</div>
    <button class="btn" id="chooseNewDestination">Browse...</button>
    <button class="btn exportMoveBtn" id="copyNewBtn" disabled>Move old + new</button>
  </div>
  <div id="organizerBar">
    <label class="toggle"><input type="checkbox" id="orgEncode"><span>Encode audio to</span></label>
    <div class="workerSetting"><select id="orgFormat" aria-label="Format"><option value="ALAC">ALAC</option><option value="FLAC">FLAC</option></select></div>
    <label class="toggle"><input type="checkbox" id="orgChecker"><span>AudioChecker</span></label>
    <label class="toggle"><input type="checkbox" id="orgSplit"><span>Split CUE</span></label>
  </div>
</div>
<script type="module">
let bridge = null;
let state = null;
let selectedId = null;
let activeTrack = null;
let rowEls = new Map();
let resizeTimer = null;
let frozenBoardLayout = null;
let viewMode="changes";
let changeFilter="all";
let showAllConnections=false;
const exportDestinations={all:"",new:""};
const REANALYZE_HIGHLIGHT_MS=15000;
let lastReanalyzeToken="";
let reanalyzeHighlightTimer=null;
const reanalyzeHighlights={added:new Set(),removed:new Set()};
function reanalyzeHighlightKind(id){
  const key=String(id);
  return reanalyzeHighlights.added.has(key)?"Added":reanalyzeHighlights.removed.has(key)?"Removed":"";
}
function paintReanalyzeHighlight(row,id){
  const kind=reanalyzeHighlightKind(id);
  row.classList.toggle("reanalysisAdded",kind==="Added");
  row.classList.toggle("reanalysisRemoved",kind==="Removed");
  const originalTitle=row.dataset.baseTitle||"";
  const originalLabel=row.dataset.baseAriaLabel||"";
  if(originalTitle)row.title=originalTitle+(kind?"\nRe-Analyze: "+kind.toLowerCase():"");
  if(originalLabel)row.setAttribute("aria-label",originalLabel+(kind?". Re-Analyze "+kind.toLowerCase()+".":""));
}
function clearReanalyzeHighlights(){
  if(reanalyzeHighlightTimer!==null){clearTimeout(reanalyzeHighlightTimer);reanalyzeHighlightTimer=null;}
  reanalyzeHighlights.added.clear();
  reanalyzeHighlights.removed.clear();
  rowEls.forEach(function(row,id){paintReanalyzeHighlight(row,id);});
}
function acceptReanalyzeHighlights(){
  const result=state&&state.result;
  if(!result||!result.show||!result.highlightToken)return false;
  const token=String(result.highlightToken);
  if(token===lastReanalyzeToken)return false;
  lastReanalyzeToken=token;
  clearReanalyzeHighlights();
  (result.addedReleaseIds||[]).forEach(function(id){reanalyzeHighlights.added.add(String(id));});
  (result.removedReleaseIds||[]).forEach(function(id){reanalyzeHighlights.removed.add(String(id));});
  if(!reanalyzeHighlights.added.size&&!reanalyzeHighlights.removed.size)return false;
  viewMode="full";changeFilter="all";activeTrack=null;
  reanalyzeHighlightTimer=setTimeout(clearReanalyzeHighlights,REANALYZE_HIGHLIGHT_MS);
  return true;
}
function focusFirstReanalyzeChange(){
  const row=Array.from(rowEls.entries()).find(function(entry){return reanalyzeHighlightKind(entry[0]);});
  if(row&&row[1]&&typeof row[1].scrollIntoView==="function"){
    row[1].scrollIntoView({block:"center",inline:"nearest",behavior:"auto"});
  }
}
function defaultExportPath(){
  if(!state)return "";
  const supplied=String(state.defaultExportDestination||"").trim();
  if(supplied)return supplied;
  // If an older/incomplete state omitted the calculated destination,
  // recover it from NEW's original source folder.
  const roots=state.sourceRoots||{};
  let source=String(roots.recycle||"").trim();
  if(!source){
    const node=(state.nodes||[]).find(function(row){
      return String(row.rootKind||"").toLowerCase()==="recycle"
        && String(row.sourceRoot||"").trim();
    });
    source=node?String(node.sourceRoot).trim():"";
  }
  if(!source)return "";
  source=source.replace(/[\\/]+$/,"");
  if(!source || /^[a-z]:$/i.test(source))return "";
  return source+" - UPDATED";
}
function selectedExportPath(mode){
  return String(exportDestinations[mode]||defaultExportPath()).trim();
}

function pathLeaf(value) {
  const parts=String(value||"").split(/[\\/]+/).filter(Boolean);
  return parts.length?parts[parts.length-1]:"";
}
function actionDisplay(n) {
  const action=String(n.action||"").toUpperCase();
  if(action==="REPLACE"){
    const oldRows=(n.upgradeFrom||[]);
    const sourceUpgrade=oldRows.find(function(x){
      return Number(n.sourceRank||0)>Number(x.sourceRank||0);
    });
    if(sourceUpgrade){
      const oldMedium=String(sourceUpgrade.sourceMedium||"OLD").trim()||"OLD";
      const newMedium=String(n.sourceMedium||"NEW").trim()||"NEW";
      return {label:"UPGRADE "+oldMedium+" → "+newMedium, cls:"upgrade"};
    }
    const reason=oldRows.map(function(x){return String(x.upgradeReason||"").trim();}).find(Boolean)||"";
    const more=reason.match(/More complete:\s*\+(\d+)\s+recording/i);
    if(more) return {label:"UPGRADE +"+more[1]+" RECORDING"+(more[1]==="1"?"":"S"),cls:"upgrade"};
    if(/Better CD rip log/i.test(reason)) return {label:"UPGRADE CD RIP",cls:"upgrade"};
    return {label:"REPLACE",cls:"replace"};
  }
  if(action==="ADD") return (state&&state.standaloneMode)
    ? {label:"RETAIN",cls:"keep"} : {label:"+ ADD",cls:"add"};
  if(action==="KEEP") return {label:"KEEP",cls:"keep"};
  if(action==="REMOVE") return {label:"REMOVE",cls:"remove"};
  if(action==="SKIP") return {label:"SKIP",cls:"skip"};
  return {label:action||"PLAN",cls:"keep"};
}
function renderSourceLegend(){
  const roots=state&&state.sourceRoots?state.sourceRoots:{};
  const oldEl=document.getElementById("oldLegend"), newEl=document.getElementById("newLegend");
  const oldPath=String(roots.existing||""), newPath=String(roots.recycle||"");
  oldEl.title=oldPath; newEl.title=newPath;
  oldEl.style.display=(state&&state.standaloneMode)?"none":"";
  newEl.querySelector("b").textContent=(state&&state.standaloneMode)?"SOURCE":"NEW";
  oldEl.querySelector("span").textContent=pathLeaf(oldPath)||"Existing";
  newEl.querySelector("span").textContent=pathLeaf(newPath)||"New / update";
}
function updateExportControls(){
  const bar=document.getElementById("exportBar");
  const enabled=!!(state&&state.editable);
  bar.classList.toggle("open",enabled);
  ["all","new"].forEach(function(mode){
    const cap=mode==="all"?"All":"New";
    const path=selectedExportPath(mode);
    const pathEl=document.getElementById(mode==="all"?"allDestination":"newDestination");
    const openBtn=document.getElementById("open"+cap+"Destination");
    const copyBtn=document.getElementById(mode==="all"?"copyAllBtn":"copyNewBtn");
    pathEl.textContent=path||"Choose destination...";
    pathEl.title=path;
    openBtn.disabled=!path;
    copyBtn.disabled=!enabled||!path||!!state.dirty||!state.applyEnabled;
  });
}

function esc(v) {
  return String(v == null ? "" : v)
    .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;").replaceAll("'","&#39;");
}
function badgeClass(n) {
  if (n >= 6) return "green";
  if (n >= 3) return "yellow";
  return "red";
}
function signedCount(n) {
  n=Number(n||0);
  return n>0 ? "+"+n : String(n);
}
function renderPlanCounts() {
  const pc=state&&state.planCounts?state.planCounts:null;
  const initial=pc&&pc.initial?pc.initial:{releases:0,tracks:0};
  const result=pc&&pc.result?pc.result:initial;
  const delta=pc&&pc.delta?pc.delta:{
    releases:Number(result.releases||0)-Number(initial.releases||0),
    tracks:Number(result.tracks||0)-Number(initial.tracks||0)
  };
  const initialEl=document.getElementById("initialCounts");
  const resultEl=document.getElementById("resultCounts");
  if(state&&state.standaloneMode){
    const scanned=state.scannedCounts||{};
    renderStatusLine();
    initialEl.textContent="Scanned: "+Number(scanned.releases||0)+" releases / "+Number(scanned.tracks||0)+" tracks";
    resultEl.textContent="Proposed retained: "+result.releases+" releases / "+result.tracks+" included tracks"
      +(state.dirty?" - pending Re-Analyze":"");
    resultEl.classList.remove("changed");
    resultEl.classList.toggle("pending",!!state.dirty);
    return;
  }
  renderStatusLine();
  initialEl.textContent="Initial: "+initial.releases+" releases / "+initial.tracks+" tracks";
  resultEl.textContent="Result: "+result.releases+" releases ("+signedCount(delta.releases)+") / "
    +result.tracks+" tracks ("+signedCount(delta.tracks)+")"
    +(state&&state.dirty?" - pending Re-Analyze":"");
  const changed=Number(delta.releases)!==0||Number(delta.tracks)!==0;
  resultEl.classList.toggle("changed",changed&&!state.dirty);
  resultEl.classList.toggle("pending",!!(state&&state.dirty));
}
function openAuditRelease(n){
  if(!n)return;
  if(viewMode!=="full"){viewMode="full";renderChangeSummary();renderBoard();}
  selectedId=Number(n.id);activeTrack=null;
  openDetails(n);updateRowHighlights();scheduleConnections();updateTrackMode();
  const row=rowEls.get(String(n.id));
  if(row)row.scrollIntoView({block:"center",inline:"nearest",behavior:"auto"});
}
let auditExpanded=false;
function auditIssueNodes(){
  return (state&&state.nodes||[]).filter(function(n){return Array.isArray(n.auditIssues)&&n.auditIssues.length;});
}
function renderStatusLine(){
  const el=document.getElementById("statusLine"), btn=document.getElementById("reviewBtn");
  if(!state){el.textContent="";btn.style.display="none";return;}
  const pc=state.planCounts||{}, result=pc.result||pc.initial||{releases:0,tracks:0};
  const delta=pc.delta||{releases:0};
  const scanned=state.scannedCounts||{};
  const keptCount=Number(result.releases||0), noun=keptCount===1?"release":"releases";
  let text=state.standaloneMode
    ? keptCount+" of "+Number(scanned.releases||0)+" releases will be kept."
    : keptCount+" "+noun+" will be kept"+(Number(delta.releases||0)?" ("+signedCount(delta.releases)+")":"")+".";
  if(state.dirty)text+=" Re-Analyze to apply your changes.";
  const count=Number(state.auditIssueCount||0), need=auditIssueNodes().length||count;
  if(count>0)text+=" "+need+" need a look before you can copy or move.";
  el.textContent=text;
  el.title=text+"\nTracks in kept releases: "+Number(result.tracks||0);
  btn.style.display=count>0?"":"none";
  btn.textContent="Review "+need;
  btn.classList.toggle("open",auditExpanded);
  btn.setAttribute("aria-expanded",String(auditExpanded));
}
function renderAuditBanner(){
  const el=document.getElementById("auditBanner");
  const count=Number(state&&state.auditIssueCount||0);
  if(!count)auditExpanded=false;
  el.classList.toggle("visible",count>0&&auditExpanded);
  el.replaceChildren();
  renderStatusLine();
  if(!count||!auditExpanded)return;
  const issues=auditIssueNodes();
  const intro=document.createElement("div");intro.className="auditIntro";
  intro.textContent="Needs a look ("+(issues.length||count)+"). Click one to open it.";
  el.appendChild(intro);
  issues.forEach(function(n){
    const problem=document.createElement("button");
    problem.type="button";problem.className="auditJump";
    const why=n.auditIssues.map(function(x){return String(x||"").trim();}).filter(Boolean).join("; ")||"Unknown integrity issue";
    const name=document.createElement("span");name.className="auditName";name.textContent=String(n.name||"Unknown release");
    const reason=document.createElement("span");reason.className="auditWhy";reason.textContent=why;
    problem.append(name,reason);
    problem.title=String(n.name||"")+"\n"+why;
    problem.onclick=function(){auditExpanded=false;renderAuditBanner();openAuditRelease(n);};
    el.appendChild(problem);
  });
  if(!issues.length){
    const generic=document.createElement("div");generic.className="auditHint";
    generic.textContent=count+" integrity issue(s); detailed release data unavailable.";
    el.appendChild(generic);
  }
}
function getNode(id) {
  return (state.nodes || []).find(function(n){ return Number(n.id) === Number(id); });
}
function carriersForGroup(groupId) {
  if (groupId == null || Number(groupId) < 0) return [];
  return (state.nodes || []).filter(function(n) {
    return (n.tracks || []).some(function(t){ return Number(t.groupId) === Number(groupId); });
  });
}
function baseRelationsForRelease(releaseId) {
  const source=getNode(releaseId), versionIds=new Set(), remixIds=new Set(), liveIds=new Set();
  if(!source) return {versions:versionIds,remixes:remixIds,live:liveIds};
  (state.nodes||[]).forEach(function(other){
    if(Number(other.id)===Number(source.id)) return;
    let hasVersion=false, hasRemix=false, hasLive=false;
    (source.tracks||[]).forEach(function(a){
      if(a.excluded || Number(a.groupId)<0 || !a.baseKey) return;
      (other.tracks||[]).forEach(function(b){
        if(b.excluded || Number(b.groupId)<0 || !b.baseKey) return;
        if(a.baseKey!==b.baseKey || Number(a.groupId)===Number(b.groupId)) return;
        const af=String(a.family||"version"), bf=String(b.family||"version");
        if(af==="live" || bf==="live") hasLive=true;
        else if(af==="remix" || bf==="remix") hasRemix=true;
        else hasVersion=true;
      });
    });
    if(hasVersion) versionIds.add(String(other.id));
    else if(hasRemix) remixIds.add(String(other.id));
    else if(hasLive) liveIds.add(String(other.id));
  });
  return {versions:versionIds,remixes:remixIds,live:liveIds};
}
function buildRowCenters() {
  const content=document.getElementById("boardContent");
  const centers=new Map();
  if(!content) return centers;
  const b=content.getBoundingClientRect();
  rowEls.forEach(function(el,id){
    const a=el.getBoundingClientRect();
    centers.set(String(id),{x:a.left-b.left+a.width/2,y:a.top-b.top+a.height/2});
  });
  return centers;
}
function curveSegment(a,b) {
  if(!a||!b) return "";
  const dx=b.x-a.x, bend=Math.max(42,Math.min(170,Math.abs(dx)*0.42)), sign=dx>=0?1:-1;
  return "M "+a.x+" "+a.y+" C "+(a.x+bend*sign)+" "+a.y+", "+(b.x-bend*sign)+" "+b.y+", "+b.x+" "+b.y+" ";
}
function addCurveBatch(svg,d,color,width,opacity,dash) {
  if(!d) return;
  const p=document.createElementNS("http://www.w3.org/2000/svg","path");
  p.setAttribute("d",d); p.setAttribute("fill","none"); p.setAttribute("stroke",getComputedStyle(document.documentElement).getPropertyValue(color).trim());
  p.setAttribute("stroke-width",String(width)); p.setAttribute("stroke-opacity",String(opacity));
  p.setAttribute("stroke-linecap","round"); p.setAttribute("stroke-linejoin","round");
  if(dash) p.setAttribute("stroke-dasharray",dash);
  svg.appendChild(p);
}
let connectionFrame=0;
function scheduleConnections(){
  if(connectionFrame) return;
  connectionFrame=requestAnimationFrame(function(){
    connectionFrame=0;
    drawConnections();
  });
}
let searchCursor=-1;
let lastSearchQuery="";
function searchMatchesFor(query) {
  const q=String(query||"").trim().toLowerCase();
  if(!q || !state) return [];
  return (state.nodes||[]).filter(function(n){
    if(String(n.name||"").toLowerCase().includes(q)) return true;
    return (n.tracks||[]).some(function(t){
      return String(t.title||"").toLowerCase().includes(q);
    });
  });
}
function applySearchHighlights(resetCursor) {
  const input=document.getElementById("search");
  const q=String(input.value||"").trim().toLowerCase();
  if(resetCursor || q!==lastSearchQuery){ searchCursor=-1; lastSearchQuery=q; }
  const matches=searchMatchesFor(q);
  const ids=new Set(matches.map(function(n){return String(n.id);}));
  rowEls.forEach(function(el,id){
    el.classList.toggle("searchMatch",!!q && ids.has(id));
    el.classList.toggle("searchDimmed",!!q && !ids.has(id));
  });
  if(!activeTrack){
    const mode=document.getElementById("modeText");
    mode.textContent=q
      ? 'Find "'+input.value.trim()+'" - '+matches.length+' release(s)'
      : "";
  }
  return matches;
}
function updateRowHighlights() {
  const carrierIds=new Set();
  if(activeTrack) carriersForGroup(activeTrack.groupId).forEach(function(n){carrierIds.add(String(n.id));});
  rowEls.forEach(function(el,id){
    el.classList.toggle("selected",selectedId!=null && Number(id)===Number(selectedId));
    if(activeTrack){
      const carrier=carrierIds.has(id); el.classList.toggle("carrier",carrier); el.classList.toggle("dimmed",!carrier);
    } else { el.classList.remove("carrier"); el.classList.remove("dimmed"); }
  });
  applySearchHighlights(false);
}
function drawConnections() {
  if(!state) return;
  const svg=document.getElementById("connections"), content=document.getElementById("boardContent");
  if(viewMode==="changes"){
    svg.replaceChildren();
    svg.setAttribute("width","0");svg.setAttribute("height","0");svg.setAttribute("viewBox","0 0 0 0");
    return;
  }
  const width=Math.max(1,content.clientWidth), height=Math.max(content.scrollHeight,content.clientHeight);
  svg.setAttribute("width",String(width)); svg.setAttribute("height",String(height));
  svg.setAttribute("viewBox","0 0 "+width+" "+height);
  svg.replaceChildren();

  const centers=buildRowCenters();
  const center=function(id){return centers.get(String(id))||null;};
  const selected=selectedId==null?null:Number(selectedId);

  let dupNormal="",dupTouch="";
  (state.duplicateLinks||[]).forEach(function(link){
    const segment=curveSegment(center(link.duplicate),center(link.retained));
    if(!segment) return;
    const touch=selected!=null && (Number(link.duplicate)===selected || Number(link.retained)===selected);
    if(touch) dupTouch+=segment; else dupNormal+=segment;
  });
  if(activeTrack){
    if(showAllConnections)addCurveBatch(svg,dupNormal+dupTouch,"--muted-strong",1.45,0.10);
  } else if(selected==null){
    if(showAllConnections)addCurveBatch(svg,dupNormal,"--muted-strong",1.45,0.27);
  } else {
    if(showAllConnections)addCurveBatch(svg,dupNormal,"--muted-strong",1.3,0.12);
    addCurveBatch(svg,dupTouch,"--body",1.8,0.6);
  }

  if(selected!=null && !activeTrack){
    const related=baseRelationsForRelease(selected), source=center(selected);
    let versions="",remixes="",live="";
    related.versions.forEach(function(id){versions+=curveSegment(source,center(id));});
    related.remixes.forEach(function(id){remixes+=curveSegment(source,center(id));});
    related.live.forEach(function(id){live+=curveSegment(source,center(id));});
    addCurveBatch(svg,versions,"--accent",1.6,0.55,"8 5");
    addCurveBatch(svg,remixes,"--info",1.5,0.5,"3 6");
    addCurveBatch(svg,live,"--positive",1.5,0.5,"10 4 2 4");
  }

  if(activeTrack){
    const source=center(activeTrack.releaseId);
    let carriers="";
    carriersForGroup(activeTrack.groupId).forEach(function(n){
      if(Number(n.id)===Number(activeTrack.releaseId)) return;
      carriers+=curveSegment(source,center(n.id));
    });
    addCurveBatch(svg,carriers,"--info",2.2,0.7);
  }
}
function releaseColumnKind(n) {
  // A proven mixed Album/EP family shares one column; original type is unchanged.
  const t=String(n.displayGroupKind||n.releaseType||"").toLowerCase();
  if(t==="compilation") return "compilation";
  if(t==="anthology") return "anthology";
  if(t==="ep") return "ep";
  if(t==="single") return "single";
  // Compilations/unknown long-form releases stay visible instead of disappearing.
  return "album";
}
function cleanReleaseLabel(name) {
  let s=String(name||"").trim();
  s=s.replace(/^\s*\d{4}(?:-\d{2}-\d{2})?\s*-\s*/,"");
  return s||String(name||"").trim();
}
function groupKeyForNode(n) {
  return String(n.displayGroupKey||"").trim().toLowerCase()
    ||String(n.family||"").trim().toLowerCase()
    ||cleanReleaseLabel(n.name).toLowerCase().replace(/[^\p{L}\p{N}]+/gu," ").trim()
    ||String(n.id);
}
function groupTitleForNodes(items) {
  const prepared=items.map(function(n){return String(n.displayGroupTitle||"").trim();}).filter(Boolean);
  if(prepared.length){
    prepared.sort(function(a,b){return a.length-b.length||a.localeCompare(b,undefined,{sensitivity:"base"});});
    return prepared[0];
  }
  const candidates=items.map(function(n){return cleanReleaseLabel(n.name);}).filter(Boolean);
  if(!candidates.length) return "Other";
  candidates.sort(function(a,b){return a.length-b.length||a.localeCompare(b,undefined,{sensitivity:"base"});});
  return candidates[0];
}
let replacementCache=null;
function replacementMap() {
  if(replacementCache)return replacementCache;
  const nodes=(state&&state.nodes)||[];
  const byId=new Map(nodes.map(function(n){return [Number(n.id),n];}));
  const groupSets=new Map(nodes.map(function(n){
    return [Number(n.id),new Set((n.tracks||[]).filter(function(t){
      return t.included&&!t.excluded&&!t.manualSkip&&Number(t.groupId)>=0;
    }).map(function(t){return Number(t.groupId);}))];
  }));
  const candidateTargets=new Map();
  const targetToOld=new Map(),oldToTarget=new Map();
  // Authoritative backend predecessor IDs work even when edition names differ
  // and the UI's separate album display-group heuristics cannot pair them.
  nodes.forEach(function(target){
    if(String(target.rootKind||"")!=="recycle"
        ||String(target.action||"").toUpperCase()!=="REPLACE"
        ||target.manualRemoved)return;
    (target.upgradeFrom||[]).forEach(function(ref){
      const old=byId.get(Number(ref.releaseId));
      if(!old||String(old.rootKind||"")!=="existing"
          ||old.kind!=="duplicate"||old.manualRemoved
          ||oldToTarget.has(Number(old.id)))return;
      const a=groupSets.get(Number(old.id)),b=groupSets.get(Number(target.id));
      if(!a||!a.size||!b||![...a].every(function(gid){return b.has(gid);}))return;
      oldToTarget.set(Number(old.id),target);
      if(!targetToOld.has(Number(target.id)))targetToOld.set(Number(target.id),[]);
      targetToOld.get(Number(target.id)).push(old);
    });
  });
  (state&&state.duplicateLinks||[]).forEach(function(link){
    const old=byId.get(Number(link.duplicate)),target=byId.get(Number(link.retained));
    if(!old||!target)return;
    const oldRemoved=String(old.rootKind||"")==="existing"&&old.kind==="duplicate"&&!old.manualRemoved;
    const targetNew=String(target.rootKind||"")==="recycle"&&["ADD","REPLACE"].includes(String(target.action||"").toUpperCase())&&!target.manualRemoved;
    if(!oldRemoved||!targetNew)return;
    const a=groupSets.get(Number(old.id)),b=groupSets.get(Number(target.id));
    // Shared tracks alone are not enough to claim an OLD -> NEW replacement.
    if(!a||!a.size||!b||![...a].every(function(gid){return b.has(gid);}))return;
    const oldFamily=String(old.displayGroupKey||"").trim().toLowerCase();
    const newFamily=String(target.displayGroupKey||"").trim().toLowerCase();
    const oldAlbum=String(old.family||"").trim().toLowerCase();
    const newAlbum=String(target.family||"").trim().toLowerCase();
    if(!((oldFamily&&oldFamily===newFamily)||(oldAlbum&&oldAlbum===newAlbum)))return;
    if(!candidateTargets.has(Number(old.id)))candidateTargets.set(Number(old.id),[]);
    candidateTargets.get(Number(old.id)).push(target);
  });
  candidateTargets.forEach(function(options,oldId){
    if(oldToTarget.has(oldId))return;
    const oldGroups=groupSets.get(oldId);
    options.sort(function(a,b){
      const ak=String(a.action||"").toUpperCase()==="REPLACE"?0:1;
      const bk=String(b.action||"").toUpperCase()==="REPLACE"?0:1;
      return ak-bk
        ||(groupSets.get(Number(a.id)).size-oldGroups.size)-(groupSets.get(Number(b.id)).size-oldGroups.size)
        ||(a.tracks||[]).length-(b.tracks||[]).length
        ||Number(a.id)-Number(b.id);
    });
    const target=options[0];
    oldToTarget.set(oldId,target);
    if(!targetToOld.has(Number(target.id)))targetToOld.set(Number(target.id),[]);
    targetToOld.get(Number(target.id)).push(byId.get(oldId));
  });
  replacementCache={targetToOld:targetToOld,oldToTarget:oldToTarget};
  return replacementCache;
}
function isRealUpgrade(n) {
  if(String(n.action||"").toUpperCase()!=="REPLACE")return false;
  return (n.upgradeFrom||[]).some(function(old){return !!String(old.upgradeReason||"").trim();});
}
function changeKind(n) {
  if(n.manualRemoved||n.pendingReleaseIgnore||n.pendingReleaseRestore) return "ignored";
  // A standalone selection is not an addition to an existing discography.
  if(state&&state.standaloneMode)return "";
  const pairs=replacementMap();
  if(pairs.oldToTarget.has(Number(n.id)))return "replacementSource";
  if(pairs.targetToOld.has(Number(n.id)))return isRealUpgrade(n)?"upgraded":"replaced";
  const action=String(n.action||"").toUpperCase();
  const root=String(n.rootKind||"");
  if(root==="recycle"&&action==="ADD") return "added";
  if(root==="recycle"&&action==="REPLACE") return isRealUpgrade(n)?"upgraded":"replaced";
  if(root==="existing"&&action!=="KEEP"&&n.kind==="duplicate") return "removed";
  return "";
}
function changeSymbol(kind) {
  if(kind==="added") return "+";
  if(kind==="upgraded") return "⬆️";
  if(kind==="replaced"||kind==="replacementSource") return "↔";
  if(kind==="removed") return "-";
  if(kind==="ignored") return "🚫";
  return "✓";
}
function uniqueAddedTitles(n) {
  return (n.tracks||[]).filter(function(t){return t.unique&&!t.excluded&&!t.manualSkip;})
    .map(function(t){return String(t.title||"");}).filter(Boolean);
}
function changeReason(n,kind) {
  const pairs=replacementMap();
  if(kind==="added"){
    const unique=uniqueAddedTitles(n);
    if(unique.length)return "Retained for: "+unique.slice(0,3).join("; ")+(unique.length>3?"; +"+(unique.length-3)+" more":"");
    if((n.tracks||[]).some(function(t){return t.pendingIgnore||t.pendingRestore;}))return "Ignore changes pending - Re-Analyze required.";
    return String(n.reason||"New addition from the NEW / update folder.");
  }
  if(kind==="upgraded"||kind==="replaced"){
    const olds=pairs.targetToOld.get(Number(n.id))||[];
    const names=olds.map(function(old){return String(old.name||"");}).filter(Boolean);
    const why=(n.upgradeFrom||[]).map(function(old){return String(old.upgradeReason||"").trim();}).find(Boolean)||"";
    return (kind==="upgraded"?"Replaces OLD with a better source/edition: ":"Replaces OLD: ")
      +(names.length?names.join("; "):"previous release")+(why?" - "+why:"");
  }
  if(kind==="replacementSource"){
    const target=pairs.oldToTarget.get(Number(n.id));
    return "Replaced by NEW: "+String(target&&target.name||"replacement release");
  }
  if(kind==="removed") return String(n.reason||"OLD release is not retained in the improved discography.");
  if(kind==="ignored"){
    if(n.pendingReleaseIgnore) return "Pending Ignore - Re-Analyze required.";
    if(n.pendingReleaseRestore) return "Pending Restore - Re-Analyze required.";
    return "Ignored by you.";
  }
  return "Unchanged retained release.";
}
function changedNodes() {
  return (state&&state.nodes||[]).filter(function(n){
    const k=changeKind(n);return !!k&&k!=="replacementSource";
  });
}
function renderChangeSummary() {
  const counts={added:0,upgraded:0,replaced:0,removed:0,ignored:0};
  changedNodes().forEach(function(n){const k=changeKind(n);if(k&&counts[k]!=null)counts[k]++;});
  const total=counts.added+counts.upgraded+counts.replaced+counts.removed+counts.ignored;
  const specs=[
    ["changesAddedBtn","added","+ Added",counts.added],
    ["changesUpgradedBtn","upgraded","⬆️ Upgraded",counts.upgraded],
    ["changesReplacedBtn","replaced","↔ Replaced",counts.replaced],
    ["changesRemovedBtn","removed","- Removed",counts.removed],
    ["changesIgnoredBtn","ignored","🚫 Ignored",counts.ignored]
  ];
  specs.forEach(function(spec){
    const el=document.getElementById(spec[0]);
    el.textContent=spec[2]+" "+spec[3];
    el.classList.toggle("active",viewMode==="changes"&&changeFilter===spec[1]);
    el.disabled=spec[1]!=="all"&&spec[3]===0;
    el.setAttribute("aria-pressed",String(viewMode==="changes"&&changeFilter===spec[1]));
  });
  const changesBtn=document.getElementById("changesViewBtn"), fullBtn=document.getElementById("fullViewBtn");
  changesBtn.textContent=(state&&state.standaloneMode)?"No changes":"Changes "+total;
  changesBtn.classList.toggle("active",viewMode==="changes");
  fullBtn.classList.toggle("active",viewMode==="full");
  changesBtn.setAttribute("aria-pressed",String(viewMode==="changes"));
  fullBtn.setAttribute("aria-pressed",String(viewMode==="full"));
  document.getElementById("connectionsBtn").hidden=viewMode!=="full";
}
function setViewMode(mode,filter) {
  const nextMode=mode==="full"?"full":"changes";
  if(nextMode!==viewMode) releaseFrozenBoardLayout();
  viewMode=nextMode;
  if(filter) changeFilter=filter;
  activeTrack=null;
  const viewport=document.getElementById("boardViewport");
  if(viewport)viewport.scrollTop=0;
  renderChangeSummary();
  renderBoard();
  updateTrackMode();
}
function groupStatusForNodes(items) {
  if(items.some(function(n){return !n.manualRemoved&&String(n.action||"").toUpperCase()==="REPLACE"&&actionDisplay(n).cls==="upgrade";}))
    return {symbol:"⬆️",cls:"upgrade",label:"Upgrade"};
  if(items.some(function(n){return !n.manualRemoved&&String(n.rootKind||"")==="recycle"&&String(n.action||"").toUpperCase()==="ADD";}))
    return (state&&state.standaloneMode)
      ? {symbol:"✓",cls:"keep",label:"Retained in proposed selection"}
      : {symbol:"+",cls:"add",label:"New addition"};
  if(items.some(function(n){return !n.manualRemoved&&String(n.rootKind||"")==="existing"&&String(n.action||"").toUpperCase()==="KEEP";}))
    return {symbol:"✓",cls:"keep",label:"Current / old release stays"};
  return null;
}
function appendReleaseRow(host,n) {
  const row=document.createElement("div");
  let rowState=n.kind==="duplicate"?"duplicate":"retained";
  if(n.manualRemoved) rowState+=" ignored";
  else if(n.pendingReleaseIgnore) rowState+=" pendingIgnore";
  else if(n.pendingReleaseRestore) rowState+=" pendingRestore";
  row.className="releaseRow "+rowState;
  row.dataset.id=String(n.id);
  row.setAttribute("role","button");
  row.tabIndex=0;
  row.classList.add(String(n.rootKind||"")==="existing"?"originOld":"originNew");
  const plan=actionDisplay(n);
  const stateText=n.manualRemoved?"Ignored":(n.pendingReleaseIgnore?"Pending ignore":(n.pendingReleaseRestore?"Pending restore":(n.kind==="duplicate"?"Duplicate":plan.label)));
  row.title=String(n.name||"")+"\n"+stateText+"\n"+(String(n.rootKind||"")==="existing"?"OLD / existing":"NEW / update");
  row.setAttribute("aria-label","Inspect release "+String(n.name||"")+". "+stateText+". "+(String(n.rootKind||"")==="existing"?"Existing discography.":"New or update source."));
  row.dataset.baseTitle=row.title;
  row.dataset.baseAriaLabel=row.getAttribute("aria-label");
  paintReanalyzeHighlight(row,n.id);
  const changed=changeKind(n);
  const changeIcon=changed?'<span class="rowChangeIcon '+changed+'" aria-hidden="true">'+esc(changeSymbol(changed))+'</span>':"";
  const auditIcon=(n.auditIssues||[]).length?'<span title="Audio integrity or incomplete release" aria-label="Validation warning">⚠️ </span>':"";
  const typeIcon=n.typeWarning?'<span title="'+esc(n.typeWarning)+'" aria-label="Release type warning">⚠️ </span>':"";
  row.innerHTML=changeIcon+auditIcon+typeIcon+'<span class="folderIcon"></span><span class="releaseName">'+esc(n.name)+'</span>';
  function activateReleaseRow(){
    const details=document.getElementById("details");
    // Do not unexpectedly dismiss the details when the same row is clicked.
    // The explicit Close button / Escape closes it and restores the board's full width.
    if(selectedId!=null && Number(selectedId)===Number(n.id) && details.classList.contains("open")){
      return;
    }
    selectedId=Number(n.id); activeTrack=null; openDetails(n); updateRowHighlights(); scheduleConnections(); updateTrackMode();
  }
  row.onclick=activateReleaseRow;
  row.onkeydown=function(e){
    if(e.key==="Enter"||e.key===" "){e.preventDefault();activateReleaseRow();}
  };
  host.appendChild(row); rowEls.set(String(n.id),row);
}
function appendChangeRow(host,n,kind) {
  const row=document.createElement("div");
  row.className="changeRow";
  row.dataset.id=String(n.id);
  row.setAttribute("role","button");
  row.tabIndex=0;
  const releaseType=String(n.releaseType||"release");
  row.setAttribute("aria-label",changeSymbol(kind)+" "+String(n.name||"")+". "+changeReason(n,kind));
  row.title=String(n.name||"")+"\n"+changeReason(n,kind);
  row.dataset.baseTitle=row.title;
  row.dataset.baseAriaLabel=row.getAttribute("aria-label");
  paintReanalyzeHighlight(row,n.id);
  row.innerHTML='<div class="changeIcon '+kind+'">'+esc(changeSymbol(kind))+'</div>'
    +'<div class="changeMain"><div class="changeName">'+esc(n.name)+(n.typeWarning?' <span title="'+esc(n.typeWarning)+'" aria-label="Release type warning">⚠️</span>':"")+'</div><div class="changeReason">'+esc(changeReason(n,kind))+'</div></div>'
    +'<div class="changeType">'+esc(releaseType)+'</div>';
  function activate(){
    selectedId=Number(n.id);activeTrack=null;openDetails(n);updateRowHighlights();scheduleConnections();updateTrackMode();
  }
  row.onclick=activate;
  row.onkeydown=function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();activate();}};
  host.appendChild(row);rowEls.set(String(n.id),row);
}
function renderChangesBoard(nodes) {
  const columns=document.getElementById("columns");
  const content=document.getElementById("boardContent");
  content.classList.add("changesContent");
  columns.className="changesMode";
  columns.style.removeProperty("--visible-columns");
  const list=document.createElement("div");
  list.id="changeList";
  const q=document.getElementById("search").value.trim();
  if(q){
    const matches=searchMatchesFor(q);
    const section=document.createElement("section");section.className="changeSection";
    const head=document.createElement("div");head.className="changeSectionHead";
    head.innerHTML='<span>Search results</span><span class="changeSectionCount">'+matches.length+'</span>';
    section.appendChild(head);
    matches.forEach(function(n){
      const kind=changeKind(n);
      appendChangeRow(section,n,kind==="replacementSource"?"replaced":(kind||"unchanged"));
    });
    if(!matches.length){const empty=document.createElement("div");empty.className="changeEmpty";empty.textContent="No matching releases or tracks.";section.appendChild(empty);}
    list.appendChild(section);
  } else {
    const specs=[
      {key:"added",label:"+ Added"},
      {key:"upgraded",label:"⬆️ Upgraded"},
      {key:"replaced",label:"↔ Replaced"},
      {key:"removed",label:"- Removed"},
      {key:"ignored",label:"🚫 Ignored"}
    ];
    let shown=0;
    specs.forEach(function(spec){
      if(changeFilter!=="all"&&changeFilter!==spec.key)return;
      const items=nodes.filter(function(n){return changeKind(n)===spec.key;});
      if(!items.length)return;
      shown+=items.length;
      const section=document.createElement("section");section.className="changeSection";
      const head=document.createElement("div");head.className="changeSectionHead";
      head.innerHTML='<span>'+spec.label+'</span><span class="changeSectionCount">'+items.length+'</span>';
      section.appendChild(head);
      items.forEach(function(n){appendChangeRow(section,n,spec.key);});
      list.appendChild(section);
    });
    if(!shown){
      const empty=document.createElement("div");empty.className="changeEmpty";
      empty.textContent=(state&&state.standaloneMode)
        ? "No additions or removals: only one source folder was supplied. Review the proposed retention and duplicate candidates in Full map."
        : (changeFilter==="all"?"No release changes. The improved discography already matches the retained plan.":"No changes in this category.");
      list.appendChild(empty);
    }
  }
  columns.appendChild(list);
}
function renderFullBoard(nodes) {
  const columns=document.getElementById("columns");
  const content=document.getElementById("boardContent");
  content.classList.remove("changesContent");
  columns.className="fullMapColumns";
  const defs=[
    {key:"album",label:"Albums"},
    {key:"ep",label:"EPs"},
    {key:"single",label:"Singles"},
    {key:"anthology",label:"Anthologies"},
    {key:"compilation",label:"Compilations"}
  ].map(function(def){
    return {key:def.key,label:def.label,typed:nodes.filter(function(n){return releaseColumnKind(n)===def.key;})};
  }).filter(function(def){return def.typed.length;});
  columns.style.setProperty("--visible-columns",String(Math.max(1,defs.length)));
  defs.forEach(function(def){
    const col=document.createElement("section");
    col.className="releaseColumn";
    col.dataset.kind=def.key;
    const head=document.createElement("div");
    head.className="releaseColumnHeader";
    head.textContent=def.label+" · "+def.typed.length;
    col.appendChild(head);
    const flow=document.createElement("div");
    flow.className="releaseGroups";
    const grouped=new Map();
    def.typed.forEach(function(n){
      const key=groupKeyForNode(n);
      if(!grouped.has(key))grouped.set(key,[]);
      grouped.get(key).push(n);
    });
    const groups=Array.from(grouped.values());
    groups.sort(function(a,b){return nodes.indexOf(a[0])-nodes.indexOf(b[0]);});
    groups.forEach(function(items){
      const group=document.createElement("div");
      group.className="releaseGroup"+(items.some(function(n){return String(n.releaseType||"")==="compilation";})?" compilationGroup":"");
      const title=document.createElement("div");title.className="releaseGroupTitle";
      const base=groupTitleForNodes(items),status=groupStatusForNodes(items);
      if(status){
        const icon=document.createElement("span");
        icon.className="groupStatusIcon "+status.cls;icon.textContent=status.symbol;icon.title=status.label;icon.setAttribute("aria-label",status.label);
        title.appendChild(icon);
      }
      const titleText=document.createElement("span");titleText.className="groupTitleText";
      const mixedAlbumEp=items.some(function(n){return n.releaseType==="album";})
        &&items.some(function(n){return n.releaseType==="ep";});
      titleText.textContent=mixedAlbumEp?base+" · Album / EP":base;
      title.appendChild(titleText);group.appendChild(title);
      items.forEach(function(n){appendReleaseRow(group,n);});
      flow.appendChild(group);
    });
    col.appendChild(flow);
    columns.appendChild(col);
  });
}
function releaseFrozenBoardLayout(){
  frozenBoardLayout=null;
  const columns=document.getElementById("columns");
  if(columns)columns.style.removeProperty("grid-template-columns");
  document.querySelectorAll(".releaseGroups").forEach(function(el){
    el.style.removeProperty("column-count");
  });
  const changes=document.getElementById("changeList");
  if(changes)changes.style.removeProperty("grid-template-columns");
}
function applyFrozenBoardLayout(){
  const lock=frozenBoardLayout;
  if(!lock || lock.mode!==viewMode)return;
  const columns=document.getElementById("columns");
  if(viewMode==="full"){
    columns.style.gridTemplateColumns="repeat("+lock.categoryColumns+",minmax(0,1fr))";
    columns.querySelectorAll(".releaseColumn").forEach(function(col){
      const flow=col.querySelector(".releaseGroups");
      const count=lock.groupColumns[col.dataset.kind];
      if(flow && count)flow.style.columnCount=String(count);
    });
  }else{
    const list=document.getElementById("changeList");
    if(list)list.style.gridTemplateColumns="repeat("+lock.changeColumns+",minmax(0,1fr))";
  }
}
function freezeBoardLayout(){
  if(frozenBoardLayout)return;
  const columns=document.getElementById("columns");
  const tracks=window.getComputedStyle(columns).gridTemplateColumns;
  const gridCount=tracks&&tracks!=="none"?tracks.trim().split(/\s+/).length:1;
  const counts={};
  columns.querySelectorAll(".releaseColumn").forEach(function(col){
    const flow=col.querySelector(".releaseGroups");
    if(flow)counts[col.dataset.kind]=Math.max(1,parseInt(window.getComputedStyle(flow).columnCount,10)||1);
  });
  const list=document.getElementById("changeList");
  const changeTracks=list?window.getComputedStyle(list).gridTemplateColumns:"";
  frozenBoardLayout={
    mode:viewMode,
    categoryColumns:Math.max(1,gridCount),
    groupColumns:counts,
    changeColumns:changeTracks&&changeTracks!=="none"?changeTracks.trim().split(/\s+/).length:1
  };
  applyFrozenBoardLayout();
}
function renderBoard() {
  if(!state)return;
  const columns=document.getElementById("columns");
  columns.innerHTML="";rowEls=new Map();
  const nodes=state.nodes||[];
  renderChangeSummary();
  if(viewMode==="changes")renderChangesBoard(nodes);else renderFullBoard(nodes);
  applyFrozenBoardLayout();
  updateRowHighlights();scheduleConnections();
}
function updateTrackMode() {
  const clear=document.getElementById("clearTrackBtn"), mode=document.getElementById("modeText");
  if(activeTrack){
    const carriers=carriersForGroup(activeTrack.groupId); clear.style.display="";
    mode.textContent='"'+activeTrack.title+'" - '+carriers.length+' release(s)';
  } else {
    clear.style.display="none";
    const q=document.getElementById("search").value.trim();
    const matches=searchMatchesFor(q);
    mode.textContent=q
      ? 'Find "'+q+'" - '+matches.length+' release(s)'
      : (state&&state.standaloneMode
        ? (viewMode==="changes"?"No comparison baseline - no changes applied":"Single-folder review - no changes applied")
        : "");
  }
}
function selectTrack(releaseId,track) {
  if(Number(track.groupId)<0) return;
  selectedId=Number(releaseId);
  activeTrack={releaseId:Number(releaseId),groupId:Number(track.groupId),title:String(track.title||"")};
  if(viewMode!=="full"){viewMode="full";renderChangeSummary();renderBoard();}
  updateRowHighlights(); scheduleConnections(); updateTrackMode();
  document.querySelectorAll(".track").forEach(function(el){
    el.classList.toggle("activeTrack",Number(el.dataset.group)===Number(activeTrack.groupId));
  });
}
function alternativesForTrack(t,wantFamily) {
  if(!state || !state.versionFamilies || !t || !t.baseKey) return [];
  const family=state.versionFamilies[t.baseKey]||[];
  return family.filter(function(v){
    return Number(v.groupId)!==Number(t.groupId) && String(v.family||"version")===String(wantFamily);
  });
}
function versionsForTrack(t) { return alternativesForTrack(t,"version"); }
function versionLengthDelta(t,other){
  const a=Number(t&&t.durationSeconds),b=Number(other&&other.durationSeconds);
  if(!Number.isFinite(a)||!Number.isFinite(b)||a<=0||b<=0)return null;
  const delta=Math.abs(a-b);
  return delta>8.0000001 ? delta : null;
}
function lengthDeltaText(seconds){
  return "\u0394"+(Math.round(seconds*10)/10).toFixed(1)+"s";
}
function remixesForTrack(t) { return alternativesForTrack(t,"remix"); }
function liveForTrack(t) { return alternativesForTrack(t,"live"); }
function highlightAlternativeVersion(v) {
  if(!v || Number(v.groupId)<0 || Number(v.releaseId)<0) return;
  if(viewMode!=="full"){viewMode="full";renderChangeSummary();renderBoard();}
  activeTrack={
    releaseId:Number(v.releaseId),
    groupId:Number(v.groupId),
    title:String(v.title||"Alternative version")
  };
  updateRowHighlights(); scheduleConnections(); updateTrackMode();
  document.querySelectorAll(".track").forEach(function(el){
    el.classList.toggle("activeTrack",Number(el.dataset.group)===Number(activeTrack.groupId));
  });
  const row=rowEls.get(String(v.releaseId));
  if(row) row.scrollIntoView({behavior:"smooth",block:"center",inline:"center"});
}
function exclusionStatus(t) {
  const reason=String(t.exclusionReason||"").trim();
  if(reason==="Explicit>Clean") return "Explicit > Clean - excluded from selection";
  if(reason) return "Excluded: "+reason;
  if(t.isRemix&&t.isLive) return "Excluded: Remix / Live";
  if(t.isRemix) return "Excluded: Remix";
  if(t.isLive) return "Excluded: Live";
  return "Excluded from analysis (reason not recorded)";
}
function trackStatus(t,n) {
  if(t.pendingIgnore) return (Number(t.groupId)>=0?"Ignore recording everywhere":"Ignore this track")+" - Re-Analyze required";
  if(t.pendingRestore) return (Number(t.groupId)>=0?"Restore recording everywhere":"Restore this track")+" - Re-Analyze required";
  if(t.manualSkip) return Number(t.groupId)>=0?"Ignored recording everywhere":"Ignored this track";
  if(n && n.manualRemoved){
    if(t.excluded) return exclusionStatus(t);
    if(t.orphaned || !t.replacementSource) return "NO REPLACEMENT - exact recording is not retained elsewhere";
    const more=(t.replacementAlternates||[]).length;
    return (t.coveredByAlternateVersion?"Covered by alternate version: ":"Sourced from: ")+t.replacementSource+(more?" (+"+more+" other retained cop"+(more===1?"y":"ies")+")":"");
  }
  if(t.excluded) return exclusionStatus(t);
  if(t.orphaned) return "No verified replacement - removal would lose it";
  if(t.coveredBy && t.coveredBy.length) return (t.coveredByAlternateVersion?"Replaceable version on: ":"Also on: ")+t.coveredBy.slice(0,2).join("; ");
  const matched=Math.max(0,Number(t.audioMatchEditions)||0);
  const unverified=Math.max(0,Number(t.unverifiedEditions)||0);
  if(matched||unverified){
    const parts=[];
    if(matched) parts.push("Same audio on "+matched+" edition"+(matched===1?"":"s"));
    if(unverified) parts.push("Also listed on "+unverified+" edition"+(unverified===1?"":"s")+" (audio unverified)");
    return parts.join("; ");
  }
  if(t.unique) return "Unique to this release";
  if(t.isGem) return "Gem - no duplicates or other versions";
  if(t.distinction) return t.distinction;
  return "Included";
}
function closeDetails() {
  selectedId=null;
  activeTrack=null;
  const aside=document.getElementById("details");
  aside.classList.remove("open");
  releaseFrozenBoardLayout();
  updateRowHighlights();
  scheduleConnections();
  updateTrackMode();
}
function closeTrackMenus() {
  document.querySelectorAll("#details .track.menuOpen").forEach(function(row){row.classList.remove("menuOpen");});
}
document.addEventListener("click",closeTrackMenus);
document.addEventListener("keydown",function(ev){if(ev.key==="Escape")closeTrackMenus();});
function openDetails(n) {
  const aside=document.getElementById("details"), inner=document.getElementById("detailsInner");
  const opening=!aside.classList.contains("open");
  let tracks="";
  (n.tracks||[]).forEach(function(t){
    const cls=["track",state.editable?"hasActions":"noActions"]; if(t.orphaned) cls.push("orphan"); else if(t.unique&&!t.excluded&&!t.manualSkip) cls.push("unique");
    if(t.excluded) cls.push("skipped");
    if(t.manualSkip||t.pendingIgnore||t.pendingRestore) cls.push("manual");
    if(activeTrack && Number(activeTrack.groupId)===Number(t.groupId)) cls.push("activeTrack");
    let action="";
    // Persisted ignored tracks remain restorable AFTER Re-Analyze even
    // though their current exclusion flag is now true.
    if(state.editable && (!t.excluded || t.manualSkip || t.pendingRestore)){
      const label=(t.manualSkip||t.pendingIgnore)?"Restore":"Ignore";
      action='<button class="ignoreTrack" data-track="'+t.index+'" aria-label="'+label+(Number(t.groupId)>=0?' this recording everywhere':' this track')+'">'+label+'</button>';
    }
    const versions=versionsForTrack(t), remixes=remixesForTrack(t), live=liveForTrack(t);
    const timedAlternatives=versions.map(function(v){return versionLengthDelta(t,v);}).filter(function(v){return v!==null;});
    const nearestDelta=timedAlternatives.length?Math.min.apply(null,timedAlternatives):null;
    let altButtons="";
    if(t.isGem) altButtons+='<span class="trackGem" title="Gem: no duplicates or other Versions">💎</span>';
    if(versions.length) altButtons+='<button class="versionsTrack" data-track="'+t.index+'">Versions '+versions.length+'</button>';
    if(remixes.length) altButtons+='<button class="remixesTrack" data-track="'+t.index+'">Remixes '+remixes.length+'</button>';
    if(live.length) altButtons+='<button class="liveTrack" data-track="'+t.index+'">Live '+live.length+'</button>';
    if(nearestDelta!==null) altButtons+='<span class="lengthDelta" title="Length differs from another edition">'+lengthDeltaText(nearestDelta)+'</span>';
    const versionsCell='<div class="versionsCell">'+altButtons+'</div>';
    const names={remix:"Remix",live:"Live",skip:"Ignored"};
    // Hover actions sit inside the title cell, never over the badge/length/note columns.
    const badge=t.patternKind?
      '<button class="patternBadge" data-track="'+t.index+'" title="Move to Personal Picks" aria-label="Move '+esc(names[t.patternKind]||"pattern")+' to Personal Picks">To Personal Picks</button>':"";
    const actions=state.editable?
      '<span class="trackActionGroup">'+badge+["remix","live"].filter(function(kind){
        return kind!==t.patternKind&&!(kind==="remix"&&t.isRemix)&&!(kind==="live"&&t.isLive);
      }).map(function(kind){
        const label="Mark as "+names[kind];
        return '<button class="patternMark" data-track="'+t.index+'" data-kind="'+kind
          +'" title="'+label+'" aria-label="'+label+'">Mark '+names[kind]+'</button>';
      }).join("")+action+'</span>':"";
    const statusText=trackStatus(t,n);
    const advisory=String(t.explicitState||"unknown").toLowerCase();
    const indicator=advisory==="explicit"?"E":(advisory==="clean"?"C":"");
    const advisoryName=indicator?(indicator==="E"?"Explicit":"Clean"):"";
    const advisoryBadge=indicator
      ?'<span class="advisoryBadge '+(indicator==="C"?"clean":"explicit")+'" title="'+advisoryName+' (metadata classification)" aria-label="'+advisoryName+' (metadata classification)">'+indicator+'</span>'
      :"";
    const statusClass=(n.manualRemoved&&!t.excluded)
      ?((t.orphaned||!t.replacementSource)?"status missing":"status replacement")
      :"status";
    // Mock-up: the note column only names why a track is special (Remix, Live, Ignored...).
    const flagged=!!(t.excluded||t.manualSkip||t.pendingIgnore||t.pendingRestore||t.orphaned||(n&&n.manualRemoved));
    const shortStatus=flagged?statusText.replace(/^Excluded: /,""):(t.unique?"Essential":"");
    tracks+='<div class="'+cls.join(" ")+'" role="button" tabindex="0" aria-label="Inspect track '+esc(t.title)+(advisoryName?' - '+advisoryName+' metadata':'')+'" data-group="'+t.groupId+'" data-index="'+t.index+'" title="'+esc(statusText)+'">'
      +'<div class="num">'+esc(t.number)+'</div><div class="titleCell"><span class="titleText" title="'+esc(t.title)+'">'+esc(t.title)+advisoryBadge+'</span></div>'
      +'<div class="dur'+(nearestDelta!==null?' differentLength':'')+'" title="'+esc(nearestDelta!==null?'Different-length version: '+lengthDeltaText(nearestDelta)+' compared with another edition':'Length: '+t.duration)+'">'+esc(t.duration)
      +'</div>'
      +'<div class="tagsCell">'+versionsCell+'<div class="'+statusClass+'" title="'+esc(statusText)+'">'+esc(shortStatus)+'</div></div>'
      +(state.editable?'<div class="rowMenuCell"><button class="rowMenuBtn" aria-label="Track actions" aria-haspopup="true" title="Track actions">\u22ef</button>'+actions+'</div>':"")+'</div>';
    function addAlternativePanel(items,kind){
      if(!items.length) return "";
      let rows="";
      items.forEach(function(v){
        const stateText=v.retained?"Retained":(v.available?"Available":"Ignored");
        const stateClass=v.retained?"retained":(v.available?"available":"");
        const releaseText=(v.retainedReleaseNames&&v.retainedReleaseNames.length?v.retainedReleaseNames:v.releaseNames||[]).slice(0,2).join("; ");
        const delta=versionLengthDelta(t,v);
        rows+='<button class="altVersion" data-kind="'+kind+'" data-parent="'+t.index+'" data-group="'+v.groupId+'" data-release="'+v.releaseId+'">'
          +'<span class="altTitle">'+esc(v.title)+'</span><span class="altDuration'+(delta!==null?' changed':'')+'">'+esc(v.duration||"")
          +(delta!==null?'<span class="altLengthDelta" title="Different-length version, not a duplicate">'+lengthDeltaText(delta)+'</span>':'')+'</span>'
          +'<span class="altState '+stateClass+'">'+esc(stateText)+'</span><span class="altReleases">'+esc(releaseText)+'</span></button>';
      });
      const panelClass=kind==="remix"?"altRemixes":(kind==="live"?"altLive":"altVersions");
      const headClass=kind==="remix"?"altRemixesHead":(kind==="live"?"altLiveHead":"altVersionsHead");
      const heading=kind==="remix"?"Remixes":(kind==="live"?"Live recordings":"Alternative versions - different audio groups, not duplicates");
      return '<div class="'+panelClass+'" data-for="'+t.index+'"><div class="'+headClass+'">'+heading+'</div>'+rows+'</div>';
    }
    tracks+=addAlternativePanel(versions,"version");
    tracks+=addAlternativePanel(remixes,"remix");
    tracks+=addAlternativePanel(live,"live");
  });
  let ignoreRelease="";
  const keepRelease=state.editable&&(n.forceKeep||n.kind!=="retained")
    ?'<button class="btn'+(n.forceKeep?' primary':'')+'" id="keepReleaseBtn">'+
      (n.forceKeep?"Unkeep release":"Keep release")+'</button>':"";
  if(state.editable && (n.kind==="retained" || n.manualRemoved || n.pendingReleaseChange)){
    const label=n.releaseBlocked?"Restore release":"Ignore release";
    const cls=n.releaseBlocked?"btn restore":"btn";
    ignoreRelease='<button class="'+cls+'" id="ignoreReleaseBtn">'+label+'</button>';
  }
  let albumGroupActions="";
  if(state.editable){
    const kindLabels={album:"Albums",ep:"Albums",single:"Singles",compilation:"Compilations",anthology:"Anthologies"};
    const groupChoices=new Map();
    (state.nodes||[]).forEach(function(other){
      if(Number(other.id)===Number(n.id))return;
      const key=releaseColumnKind(other)+"|"+groupKeyForNode(other);
      if(key===releaseColumnKind(n)+"|"+groupKeyForNode(n))return;
      const current=groupChoices.get(key);
      if(!current||(!other.manualGroupAssigned&&current.manualGroupAssigned))groupChoices.set(key,other);
    });
    const targets=Array.from(groupChoices.values()).sort(function(a,b){
      return groupTitleForNodes([a]).localeCompare(groupTitleForNodes([b]));
    });
    const options=targets.map(function(other){
      const kind=kindLabels[releaseColumnKind(other)]||"Albums";
      return '<option value="'+Number(other.id)+'">'+esc(groupTitleForNodes([other]))+' \u00b7 '+kind+'</option>';
    }).join("")+(n.manualGroupAssigned?'<option value="-1">Automatic group</option>':"");
    if(options)albumGroupActions='<select id="albumGroupSelect" class="changeGroupSelect" aria-label="Change group"><option value="" selected disabled>Change group</option>'+options+'</select>';
  }
  let ignoreNotice="";
  if(n.pendingReleaseIgnore){
    ignoreNotice='<div class="pendingNotice"><b>Pending Ignore.</b> Click Re-Analyze to calculate where every included track will be sourced from. No files have been moved.</div>';
  } else if(n.pendingReleaseRestore){
    ignoreNotice='<div class="pendingNotice"><b>Pending Restore.</b> Click Re-Analyze to put this release back into optimization. No files have been moved.</div>';
  } else if(n.manualRemoved){
    ignoreNotice='<div class="ignoredNotice"><b>Ignored by you.</b> This release stays on the map so you can inspect its replacement sources. To undo: click <b>Restore release</b>, then <b>Re-Analyze</b>.</div>';
  }
  const mediumLabel=String(n.sourceMedium||n.sourceDescription||"Unknown");
  const isCdRip=/^CD\b/i.test(mediumLabel);
  const perfectRip=isCdRip&&!!n.hasCue&&!!n.hasRipLog&&Number(n.ripLogPercent)===100;
  // A perfect rip gets ONE large gold check after the whole group instead of three small ones.
  const tick=perfectRip?'':'<span class="tick" aria-label="OK">\u2713</span>';
  let releaseBadges='<span class="mediumBadge" title="'+esc((String(n.rootKind||"")==="existing"?"OLD":"NEW")+" · "+String(n.sourceRoot||""))+'">'+esc(mediumLabel)+(isCdRip?tick:'')+'</span>';
  if(n.hasCue)releaseBadges+='<span class="ripMark" title="CUE sheet present">CUE'+tick+'</span>';
  if(n.hasRipLog){
    const scored=n.ripLogPercent!=null;
    const problems=(n.ripLogProblems||[]).join("\n");
    const results=(n.ripLogResults||[]).join("\n");
    releaseBadges+='<span class="ripMark log'+(scored?'':' unscored')+'" title="'
      +esc((scored?"Rip log score (worst disc)":("Rip log not scored"+(problems?":\n"+problems:"")))+(results?"\n"+results:""))+'">LOG '
      +(scored?Number(n.ripLogPercent)+'%'+tick:'not scored')+'</span>';
  }
  if(perfectRip)releaseBadges='<span class="perfectRip" title="Perfect rip: CD + CUE + log 100%">'+releaseBadges+'<span class="perfectTick" aria-label="Perfect rip">\u2713</span></span>';
  const plan=actionDisplay(n);
  const readablePlan=({REMOVE:"Removed",KEEP:"Kept",SKIP:"Skipped",RETAIN:"Retained",
    "+ ADD":"Added",REPLACE:"Replaced"})[plan.label]||
    String(plan.label||"").toLowerCase().replace(/^./,function(v){return v.toUpperCase();});
  const planText=n.manualRemoved?"Ignored by you"
    :(n.pendingReleaseIgnore?"Pending ignore"
      :(n.pendingReleaseRestore?"Pending restore"
        :(n.kind==="duplicate"?readablePlan+" \u00b7 Duplicate":readablePlan)));
  const planClass=["Kept","Retained","Added","Replaced"].includes(readablePlan)&&!n.manualRemoved?"keep":"drop";
  const planLine='<span class="planBadge '+planClass+'" title="'+esc(n.reason||"")+'">'+esc(planText)+'</span>'
    +'<span id="essentialCount"'+(Number(n.uniqueCount)>0?'':' hidden')+'>'+Number(n.uniqueCount||0)+' essential (highlighted)</span>';
  let upgradeSummary="";
  if(String(n.action||"").toUpperCase()==="REPLACE" && (n.upgradeFrom||[]).length){
    const upgrades=(n.upgradeFrom||[]).map(function(old){
      const reason=String(old.upgradeReason||"").trim();
      return esc(old.name||"old release")+' ('+esc(old.sourceMedium||old.source||"Unknown")+')'
        +(reason?' - '+esc(reason):'');
    }).join("; ");
    const heading=(n.upgradeFrom||[]).some(function(old){return String(old.upgradeReason||"").trim();})
      ?"Upgrade"
      :"Replacement";
    upgradeSummary='<div class="sourceSummary"><strong>'+heading+':</strong> '+upgrades+' → '+esc(n.name)+' ('+esc(n.sourceMedium||"Unknown")+')</div>';
  }
  inner.innerHTML='<div id="detailsHead"><button id="closeDetailsBtn" title="Close details" aria-label="Close details">×</button><div id="releaseName">'+esc(n.name)+'</div>'
    +(n.typeWarning?'<div class="auditNotice">⚠️ '+esc(n.typeWarning)+'</div>':"")
    +ignoreNotice+((n.auditIssues||[]).length
      ? '<div class="auditNotice">⚠️ Audio integrity / release completeness:\n'+esc(n.auditIssues.join("\n"))+'</div>'
      : '')+upgradeSummary+'<div id="releaseActions"><span class="releaseBadges">'+releaseBadges+planLine+'</span>'
    +'<span class="releaseButtons">'+keepRelease+albumGroupActions+ignoreRelease+'</span></div><div id="pathRow">'
    +'<button class="btn pathOpenBtn drawnFolder" id="openFolderBtn" title="Open release folder" aria-label="Open release folder">📁</button>'
    +'<div id="releasePath" role="textbox" aria-readonly="true" tabindex="0" aria-label="Release folder path (select to copy)">'+esc(n.path)+'</div></div></div>'
    +'<div id="tracks">'+tracks+'</div>';
  // Freeze the current category/group column counts BEFORE the board shrinks.
  // Docking changes column widths, never the release order or scroll position.
  freezeBoardLayout();
  aside.classList.add("open");
  if(opening) requestAnimationFrame(scheduleConnections);
  document.getElementById("closeDetailsBtn").onclick=closeDetails;
  document.getElementById("openFolderBtn").onclick=function(){bridge.openFolder(n.path);};
  document.getElementById("releasePath").onkeydown=function(ev){
    if((ev.ctrlKey||ev.metaKey) && ev.key.toLowerCase()==="a"){
      ev.preventDefault();
      const selection=window.getSelection(),range=document.createRange();
      range.selectNodeContents(this);selection.removeAllRanges();selection.addRange(range);
    }
  };
  const rb=document.getElementById("ignoreReleaseBtn"); if(rb) rb.onclick=function(){bridge.toggleRelease(Number(n.id),receiveReleaseToggle);};
  const groupSelect=document.getElementById("albumGroupSelect");
  if(groupSelect)groupSelect.onchange=function(){
    const dest=Number(groupSelect.value);
    if(Number.isFinite(dest))bridge.setAlbumGroup(Number(n.id),dest,receiveState);
  };
  const keepBtn=document.getElementById("keepReleaseBtn");
  if(keepBtn)keepBtn.onclick=function(){bridge.toggleReleaseKeep(Number(n.id),receiveState);};
  inner.querySelectorAll(".track").forEach(function(el){
    const index=Number(el.dataset.index), track=(n.tracks||[]).find(function(t){return Number(t.index)===index;});
    if(track){
      const activateTrack=function(ev){
        if(ev.target && (
          ev.target.classList.contains("rowMenuBtn")
          || ev.target.classList.contains("ignoreTrack")
          || ev.target.classList.contains("patternMark")
          || ev.target.classList.contains("patternBadge")
          || ev.target.classList.contains("versionsTrack")
          || ev.target.classList.contains("remixesTrack")
          || ev.target.classList.contains("liveTrack")
        )) return;
        selectTrack(n.id,track);
      };
      el.onclick=activateTrack;
      el.onkeydown=function(ev){
        if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();activateTrack(ev);}
      };
    }
  });
  inner.querySelectorAll(".rowMenuBtn").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      const row=btn.closest(".track"),wasOpen=row.classList.contains("menuOpen");
      closeTrackMenus();
      if(wasOpen)return;
      row.classList.add("menuOpen");
      const menu=row.querySelector(".trackActionGroup"),box=btn.getBoundingClientRect();
      menu.style.top=(window.innerHeight-box.bottom>menu.offsetHeight+8?box.bottom+2:box.top-menu.offsetHeight-2)+"px";
      menu.style.left=Math.max(4,box.right-menu.offsetWidth)+"px";
    };
  });
  inner.querySelectorAll(".patternMark").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      closeTrackMenus();
      bridge.markTrackPattern(Number(btn.dataset.track),btn.dataset.kind||"",receivePatternClassification);
    };
  });
  inner.querySelectorAll(".patternBadge").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      closeTrackMenus();
      bridge.markTrackPattern(Number(btn.dataset.track),"keep",receivePatternClassification);
    };
  });
  inner.querySelectorAll(".ignoreTrack").forEach(function(btn){
    btn.onclick=function(ev){ev.stopPropagation();closeTrackMenus();bridge.toggleTrack(Number(btn.dataset.track),receiveTrackToggle);};
  });
  inner.querySelectorAll(".versionsTrack").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      const panel=inner.querySelector('.altVersions[data-for="'+btn.dataset.track+'"]');
      if(panel) panel.classList.toggle("open");
    };
  });
  inner.querySelectorAll(".remixesTrack").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      const panel=inner.querySelector('.altRemixes[data-for="'+btn.dataset.track+'"]');
      if(panel) panel.classList.toggle("open");
    };
  });
  inner.querySelectorAll(".liveTrack").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      const panel=inner.querySelector('.altLive[data-for="'+btn.dataset.track+'"]');
      if(panel) panel.classList.toggle("open");
    };
  });
  inner.querySelectorAll(".altVersion").forEach(function(btn){
    btn.onclick=function(ev){
      ev.stopPropagation();
      const parentIndex=Number(btn.dataset.parent);
      const parentTrack=(n.tracks||[]).find(function(t){return Number(t.index)===parentIndex;});
      const pool=btn.dataset.kind==="remix"
        ? remixesForTrack(parentTrack)
        :(btn.dataset.kind==="live" ? liveForTrack(parentTrack) : versionsForTrack(parentTrack));
      const version=(pool||[]).find(function(v){return Number(v.groupId)===Number(btn.dataset.group);});
      if(version) highlightAlternativeVersion(version);
    };
  });
}
function receiveState(raw) {
  state=JSON.parse(raw); replacementCache=null;
  const showNewHighlights=acceptReanalyzeHighlights();
  if(state.standaloneMode && viewMode==="changes" && !selectedId) viewMode="full";
  renderPlanCounts(); renderAuditBanner(); renderSourceLegend(); updateButtons(); renderChangeSummary(); renderBoard();
  if(selectedId!=null && getNode(selectedId)) openDetails(getNode(selectedId));
  else {
    document.getElementById("details").classList.remove("open");
    releaseFrozenBoardLayout();
  }
  updateTrackMode();
  if(showNewHighlights)focusFirstReanalyzeChange();
}
function applyRootPatch(p) {
  if(!state) return;
  state.dirty=!!p.dirty;
  state.applyEnabled=!!p.applyEnabled && !Number(state.auditIssueCount||0);
  state.applyHighlighted=!!p.applyHighlighted;
  if(p.result) state.result=p.result;
  renderPlanCounts(); updateButtons();
}
function receivePatternClassification(raw){
  const update=JSON.parse(raw);
  if(!update||update.kind!=="patternToggle"){receiveState(raw);return;}
  const current=selectedId==null?null:getNode(selectedId);
  const details=document.getElementById("details");
  const scroll=details.scrollTop;
  const patches=new Map((update.tracks||[]).map(p=>[Number(p.index),p]));
  (state.nodes||[]).forEach(n=>(n.tracks||[]).forEach(t=>{
    const p=patches.get(Number(t.index));
    if(p){t.patternKind=p.patternKind;t.patternKey=p.patternKey;}
  }));
  state.requiresFreshScan=!!update.requiresFreshScan;
  state.applyEnabled=false;
  state.dirty=true;
  updateButtons();
  document.getElementById("modeText").textContent="Classification saved - run Analyze again";
  if(current){
    openDetails(current);
    details.scrollTop=scroll;
  }
}
function receiveTrackToggle(raw) {
  replacementCache=null;
  const p=JSON.parse(raw);
  if(!p || p.kind!=="trackToggle") { receiveState(raw); return; }
  const updated=Array.isArray(p.tracks)&&p.tracks.length
    ?p.tracks:[{index:p.trackIndex,manualSkip:p.manualSkip,pendingIgnore:p.pendingIgnore,pendingRestore:p.pendingRestore}];
  const updates=new Map(updated.map(function(row){return [Number(row.index),row];}));
  const releases=new Map((p.releases||[]).map(function(row){return [Number(row.id),row];}));
  (state.nodes||[]).forEach(function(n){
    (n.tracks||[]).forEach(function(t){
      const row=updates.get(Number(t.index));
      if(!row)return;
      t.manualSkip=!!row.manualSkip;
      t.pendingIgnore=!!row.pendingIgnore;
      t.pendingRestore=!!row.pendingRestore;
      if("unique" in row)t.unique=!!row.unique;
      if("isGem" in row)t.isGem=!!row.isGem;
    });
    const release=releases.get(Number(n.id));
    if(release){
      n.uniqueCount=Number(release.uniqueCount)||0;
      n.isGem=!!release.isGem;
      n.gemTitles=release.gemTitles||[];
      const el=rowEls.get(String(n.id));
      const reason=el&&el.querySelector(".changeReason");
      if(reason){
        const text=changeReason(n,changeKind(n));
        reason.textContent=text;
        el.title=String(n.name||"")+"\n"+text;
        el.setAttribute("aria-label","Inspect release "+String(n.name||"")+". "+text);
        el.dataset.baseTitle=el.title;
        el.dataset.baseAriaLabel=el.getAttribute("aria-label");
        paintReanalyzeHighlight(el,n.id);
      }
    }
  });
  applyRootPatch(p);
  // Update the existing panel IN PLACE. Redrawing it would reset the user's
  // scroll position and focus, repeating the old Release Map UX regression.
  const current=selectedId==null?null:getNode(selectedId);
  if(!current)return;
  const essential=document.getElementById("essentialCount");
  if(essential){
    essential.hidden=!Number(current.uniqueCount);
    essential.textContent=Number(current.uniqueCount||0)+" essential (highlighted)";
  }
  document.querySelectorAll("#details .track[data-index]").forEach(function(el){
    const t=(current.tracks||[]).find(function(row){
      return Number(row.index)===Number(el.dataset.index);
    });
    if(!t||!updates.has(Number(t.index)))return;
    el.classList.toggle("manual",!!(t.manualSkip||t.pendingIgnore||t.pendingRestore));
    el.classList.toggle("unique",!!t.unique&&!t.orphaned&&!t.excluded&&!t.manualSkip);
    const gem=el.querySelector(".trackGem");
    if(gem&&!t.isGem)gem.remove();
    else if(t.isGem&&!gem){
      const cell=el.querySelector(".versionsCell");
      if(cell)cell.insertAdjacentHTML("afterbegin",'<span class="trackGem" title="Gem: no duplicates or other Versions">💎</span>');
    }
    const status=trackStatus(t,current);
    el.title=status;
    const statusEl=el.querySelector(".status");
    if(statusEl){
      const flagged=!!(t.excluded||t.manualSkip||t.pendingIgnore||t.pendingRestore||t.orphaned||current.manualRemoved);
      statusEl.textContent=flagged?status.replace(/^Excluded: /,""):(t.unique?"Essential":"");
      statusEl.title=status;
    }
    const button=el.querySelector(".ignoreTrack");
    if(button){
      const restoring=!!(t.manualSkip||t.pendingIgnore);
      button.textContent=restoring?"Restore":"Ignore";
      button.setAttribute("aria-label",(restoring?"Restore":"Ignore")
        +(Number(t.groupId)>=0?" this recording everywhere":" this track"));
    }
  });
}
function receiveReleaseToggle(raw) {
  replacementCache=null;
  const p=JSON.parse(raw);
  if(!p || p.kind!=="releaseToggle") { receiveState(raw); return; }
  const n=getNode(p.releaseId);
  if(n){
    n.releaseBlocked=!!p.releaseBlocked;
    n.pendingReleaseChange=!!p.pendingReleaseChange;
    n.pendingReleaseIgnore=!!p.pendingReleaseIgnore;
    n.pendingReleaseRestore=!!p.pendingReleaseRestore;
  }
  applyRootPatch(p);
  renderBoard();
  if(selectedId!=null && getNode(selectedId)) openDetails(getNode(selectedId));
}
function updateButtons() {
  const r=document.getElementById("reanalyzeBtn");
  r.disabled=!state.editable||!state.dirty||!!state.requiresFreshScan;
  r.classList.toggle("dirty",!!state.dirty&&!state.requiresFreshScan);
  updateExportControls();
}
function closePopovers(){
  const menu=document.getElementById("changeBar");
  menu.classList.remove("open");document.getElementById("viewMenuBtn").setAttribute("aria-expanded","false");
  if(auditExpanded){auditExpanded=false;renderAuditBanner();}
}
document.getElementById("viewMenuBtn").onclick=function(e){
  e.stopPropagation();
  const menu=document.getElementById("changeBar"), open=!menu.classList.contains("open");
  if(auditExpanded){auditExpanded=false;renderAuditBanner();}
  menu.classList.toggle("open",open);this.setAttribute("aria-expanded",String(open));
};
document.getElementById("reviewBtn").onclick=function(e){
  e.stopPropagation();
  document.getElementById("changeBar").classList.remove("open");
  document.getElementById("viewMenuBtn").setAttribute("aria-expanded","false");
  auditExpanded=!auditExpanded;renderAuditBanner();
};
document.addEventListener("click",function(e){
  if(e.target.closest&&(e.target.closest("#changeBar")||e.target.closest("#auditBanner")))return;
  closePopovers();
});
document.addEventListener("keydown",function(e){if(e.key==="Escape")closePopovers();});
document.getElementById("changesViewBtn").onclick=function(){setViewMode("changes","all");closePopovers();};
document.getElementById("fullViewBtn").onclick=function(){setViewMode("full");closePopovers();};
document.querySelectorAll(".changeChip").forEach(function(btn){
  btn.onclick=function(){if(!btn.disabled){setViewMode("changes",String(btn.dataset.filter||"all"));closePopovers();}};
});
document.getElementById("clearTrackBtn").onclick=function(){
  activeTrack=null;updateRowHighlights();scheduleConnections();updateTrackMode();
  document.querySelectorAll(".track").forEach(function(el){el.classList.remove("activeTrack");});
};
document.getElementById("reanalyzeBtn").onclick=function(){bridge.reanalyze(receiveState);};
function chooseDestination(mode){
  bridge.chooseDestination(mode,function(path){
    path=String(path||"").trim();
    if(!path)return;
    exportDestinations[mode]=path;
    updateExportControls();
  });
}
function copyPlan(mode){
  if(!state||!state.applyEnabled||state.dirty)return;
  const path=selectedExportPath(mode);
  if(!path){chooseDestination(mode);return;}
  const nodes=(state.nodes||[]).filter(function(n){
    const retained=["KEEP","ADD","REPLACE"].includes(String(n.action||"").toUpperCase())&&!n.manualRemoved;
    return retained;
  });
  const oldCount=nodes.filter(function(n){return String(n.rootKind||"")==="existing";}).length;
  const newCount=nodes.filter(function(n){return String(n.rootKind||"")==="recycle";}).length;
  const upgradeCount=nodes.filter(function(n){return changeKind(n)==="upgraded";}).length;
  const summary=oldCount+" OLD + "+newCount+" NEW retained releases ("+upgradeCount+" upgrade(s)).";
  const message=mode==="all"
    ? "Copy retained OLD + NEW releases into:\n\n"+path+"\n\n"+summary+"\n\n"
      +"This is non-destructive: the existing and new/update source folders will not be moved, deleted, or modified."
    : "MOVE retained OLD + NEW releases into:\n\n"+path+"\n\n"+summary+"\n\n"
      +"Releases are written to the destination like Copy; originals of finished releases then go to the Recycle Bin. "
      +"Partial or failed releases stay where they are.";
  if(window.confirm(message))bridge.copyPlan(mode,path);
}
document.getElementById("chooseAllDestination").onclick=function(){chooseDestination("all");};
document.getElementById("chooseNewDestination").onclick=function(){chooseDestination("new");};
document.getElementById("openAllDestination").onclick=function(){const path=selectedExportPath("all");if(path)bridge.openFolder(path);};
document.getElementById("openNewDestination").onclick=function(){const path=selectedExportPath("new");if(path)bridge.openFolder(path);};
function renderOrganizer(raw){
  const o=JSON.parse(raw);
  document.getElementById("orgEncode").checked=!!o.enable_encoding;
  document.getElementById("orgChecker").checked=!!o.enable_checker;
  document.getElementById("orgSplit").checked=!!o.enable_splitting;
  document.getElementById("orgFormat").value=o.format||"ALAC";
  document.getElementById("orgFormat").disabled=!o.enable_encoding;
}
[["orgEncode","enable_encoding","checked"],["orgChecker","enable_checker","checked"],
 ["orgSplit","enable_splitting","checked"],["orgFormat","format","value"]].forEach(function(item){
  document.getElementById(item[0]).onchange=function(){bridge.setOrganizerOption(item[1],this[item[2]],renderOrganizer);};
});
document.getElementById("copyAllBtn").onclick=function(){copyPlan("all");};
document.getElementById("copyNewBtn").onclick=function(){copyPlan("new");};
document.getElementById("closeBtn").onclick=function(){bridge.closeMap();};
document.getElementById("connectionsBtn").onclick=function(){
  showAllConnections=!showAllConnections;
  this.setAttribute("aria-pressed",String(showAllConnections));
  this.textContent=showAllConnections?"Show selected links":"Show all links";
  scheduleConnections();
};
document.addEventListener("keydown",function(e){
  if(e.key==="Escape" && document.getElementById("details").classList.contains("open")){
    e.preventDefault();
    closeDetails();
  }
});
document.getElementById("search").addEventListener("input",function(){
  activeTrack=null;
  if(viewMode==="changes")renderBoard();else applySearchHighlights(true);
  scheduleConnections();
  updateTrackMode();
});
document.getElementById("search").addEventListener("keydown",function(e){
  if(e.key!=="Enter") return;
  const matches=searchMatchesFor(e.target.value);
  if(!matches.length) return;
  searchCursor=(searchCursor+1)%matches.length;
  const n=matches[searchCursor];
  selectedId=Number(n.id);
  activeTrack=null;
  openDetails(n);
  updateRowHighlights();
  scheduleConnections();
  updateTrackMode();
  const row=rowEls.get(String(n.id));
  if(row)row.scrollIntoView({behavior:"smooth",block:"center",inline:"center"});
});
window.addEventListener("resize",function(){clearTimeout(resizeTimer);resizeTimer=setTimeout(function(){renderBoard();scheduleConnections();},100);});
new ResizeObserver(function(){scheduleConnections();}).observe(document.getElementById("boardContent"));
function waitForPywebviewMethod(name,timeoutMs){
  const limit=Number(timeoutMs||30000);
  return new Promise(function(resolve,reject){
    const started=Date.now();
    function probe(){
      const api=window.pywebview&&window.pywebview.api;
      const fn=api&&api[name];
      if(typeof fn==="function"){resolve({api:api,fn:fn});return;}
      if(Date.now()-started>=limit){
        reject(new Error("Desktop bridge method did not become ready: "+String(name)));
        return;
      }
      setTimeout(probe,25);
    }
    probe();
  });
}
function bridgeCall(name,args,callback){
  return waitForPywebviewMethod(name,30000).then(function(entry){
    return entry.fn.apply(entry.api,args);
  }).then(function(result){
    if(callback)callback(typeof result==="string"?result:JSON.stringify(result));
    return result;
  }).catch(function(error){
    console.error(error);
    const mode=document.getElementById("modeText");
    if(mode)mode.textContent="Desktop bridge error: "+String(error&&error.message||error);
    throw error;
  });
}
function createLightBridge(){
  return new Proxy({},{
    get:function(_target,name){
      return function(){
        const args=Array.from(arguments);
        const callback=(args.length&&typeof args[args.length-1]==="function")?args.pop():null;
        return bridgeCall(name,args,callback);
      };
    }
  });
}
bridge=createLightBridge();
bridge.getState(receiveState).catch(function(){});
window.addEventListener("pywebviewready",function(){
  bridge.getOrganizer(renderOrganizer).catch(function(){});
  bridge.getState(receiveState).catch(function(){});
});
</script>
</body>
</html>"""
    return _apply_app_theme(html)


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
    # "Move to another group" works for every release type. Album/EP pairs were
    # already merged by _album_clusters above; any other pair only changes the
    # display group and column, never the optimizer.
    node_by_path = {
        _manual_album_group_path_key(Path(str(row.get("path", "") or ""))): row
        for row in nodes if row.get("path")
    }
    for source_key, target_key in links.items():
        source_row, target_row = node_by_path.get(source_key), node_by_path.get(target_key)
        if source_row is None or target_row is None:
            continue
        source_kind = str(source_row.get("releaseType", "") or "").lower()
        target_kind = str(target_row.get("releaseType", "") or "").lower()
        if source_kind in {"album", "ep"} and target_kind in {"album", "ep"}:
            continue
        source_row["displayGroupKey"] = target_row.get("displayGroupKey", "")
        source_row["displayGroupTitle"] = target_row.get("displayGroupTitle", "")
        source_row["displayGroupKind"] = str(
            target_row.get("displayGroupKind") or target_kind or "album")


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
    # Retained copies of one song, per album tag, with their lengths.
    retained_song_copies: Dict[Tuple[str,str,str],List[Tuple[int,float]]] = defaultdict(list)

    for item in snapshots:
        source_rid = int(item.get("release_id", -1))
        for row in item.get("tracklist", []) or []:
            song_key = _release_map_song_key(row)
            if song_key is not None:
                all_song_carriers[song_key].add(source_rid)
                if str(item.get("action", "")) in {"KEEP", "ADD", "REPLACE"}:
                    # Artist tags differ between editions (a band and its former name).
                    retained_song_copies[(song_key[0], song_key[2], normalize_title(str(row.get("album", "") or "")))].append(
                        (source_rid, float(row.get("duration_seconds", 0) or 0)))
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
            # Same song, same album tag, length within the version bound on
            # another retained release: that copy, not this one, is the reason
            # to keep the song.
            song_key = _release_map_song_key(row)
            row_duration = float(row.get("duration_seconds", 0) or 0)
            row_album_key = normalize_title(str(row.get("album", "") or ""))
            has_same_album_copy_elsewhere = bool(song_key and row_album_key and row_duration > 0 and any(
                other_rid != rid and other_duration > 0
                and abs(row_duration - other_duration) <= DURATION_VERSION_MAX_SAME_SECONDS
                for other_rid, other_duration in retained_song_copies.get((song_key[0], song_key[2], row_album_key), [])))
            unique = bool(retained and included and not manual_skip
                and not has_same_album_copy_elsewhere
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
                "hasCue": bool(item.get("has_cue")),
                "hasRipLog": bool(item.get("has_rip_log")),
                "ripLogPercent": item.get("rip_log_percent"),
                "ripLogProblems": list(item.get("rip_log_problems", []) or []),
                "ripLogResults": list(item.get("rip_log_results", []) or []),
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

        def getOrganizer(self):
            return json.dumps(_organizer_options())

        def setOrganizerOption(self, name: str, value):
            _save_organizer_option(str(name), value)
            return self.getOrganizer()

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
            if source is None:
                raise ValueError("Select a release from the current analysis.")
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
                if target is None or target.rid == source.rid:
                    raise ValueError("Select another group from the current analysis.")
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
        background_color=DESIGN_CANVAS_HEX,
        text_select=True,
        zoomable=True,
    )
    bridge.window = window
    _expose_bridge_methods(
        window,
        bridge,
        (
            "getState",
            "getOrganizer",
            "setOrganizerOption",
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
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Music Collection Cleaner</title>
<style>/*APP_THEME*/</style>
</head>
<body>
<div id="content">
  <section class="card">
    <div class="sources">
      <div id="sourceRows"></div>
      <button class="btn addFolder" id="addFolder" title="Add another source folder">＋ Add folder</button>
      <div class="options">
        <label class="toggle" title="Checked: remixes participate normally. Unchecked: remixes are skipped.">
          <input type="checkbox" id="saveRemixes"><span>Save Remixes</span>
        </label>
        <label class="toggle" title="Checked: live recordings participate normally. Unchecked: live recordings are skipped.">
          <input type="checkbox" id="saveLive"><span>Save Live recordings</span>
        </label>
        <button class="btn" id="personalPicks">Personal Picks</button>
        <button class="btn" id="pendingPatterns">Classify patterns</button>
        <div class="workerSetting" title="Max simultaneous ffprobe/fpcalc disk reads. Auto: HDD, network or unknown = 2, SSD = up to 8; slower of OLD/NEW sources wins. Manual overrides the limit.">
          <label for="ioWorkers">Audio I/O workers</label><select id="ioWorkers" aria-label="Audio I/O workers"><option value="auto">Auto (drive type)</option></select>
        </div>
        <label class="toggle" title="Copy/Move: convert to the selected format. Unchecked: keep the original codec.">
          <input type="checkbox" id="orgEncode"><span>Encode audio to</span>
        </label>
        <div class="workerSetting">
          <select id="orgFormat" aria-label="Format"><option value="ALAC">ALAC</option><option value="FLAC">FLAC</option></select>
        </div>
        <label class="toggle" title="Copy/Move: write audiochecker.log for WEB releases.">
          <input type="checkbox" id="orgChecker"><span>AudioChecker</span>
        </label>
        <label class="toggle" title="Copy/Move: split CUE album images into tracks.">
          <input type="checkbox" id="orgSplit"><span>Split CUE</span>
        </label>
        <label class="toggle" title="Write detailed JSONL audio-comparison logs.">
          <input type="checkbox" id="logging"><span>Logging</span>
        </label>
        <button class="iconBtn drawnFolder" id="openLogs" title="Open logs folder" aria-label="Open logs folder">📁</button>
      </div>
    </div>
  </section>

  <section class="card progressCard">
    <div class="progressTop"><div id="progressStatus">Ready</div><div id="progressPercent">0%</div></div>
    <div class="progressTrack" id="progressTrack" role="progressbar" aria-label="Analysis progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="progressFill"></div></div>
    <div id="progressDetail" aria-live="polite"></div>
  </section>

  <section class="card activityCard">
    <div class="cardHead"><div class="cardTitle">Activity</div></div>
    <div id="activity" role="log" aria-live="polite" aria-relevant="additions text"></div>
  </section>
</div>

<div id="footer" class="appBar">
  <button class="btn primary" id="analyzeBtn">Analyze</button>
  <button class="btn" id="undoBtn">Undo last run</button>
  <button class="btn" id="mapBtn">Release Map...</button>
  <div id="footerSpacer"></div>
  <button class="btn" id="closeBtn">Close</button>
</div>

<div id="modalBackdrop">
  <div id="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle" aria-describedby="modalSubtitle">
    <div id="modalHead"><div id="modalTitle"></div><div id="modalSubtitle"></div></div>
    <div id="modalBody"></div>
    <div id="modalFoot"></div>
  </div>
</div>

<script>
let bridge=null;
let state=null;
let modalKind="";
let localPicks=[];
let currentDone=null;
let modalReturnFocus=null;
let patternLaterAction=null;

function esc(v){
  return String(v==null?"":v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;").replaceAll("'","&#39;");
}
function formatElapsed(ms){
  let s=Math.max(0,Math.floor(ms/1000));
  const h=Math.floor(s/3600);s%=3600;const m=Math.floor(s/60);const sec=s%60;
  return h? h+":"+String(m).padStart(2,"0")+":"+String(sec).padStart(2,"0")
          : String(m).padStart(2,"0")+":"+String(sec).padStart(2,"0");
}
function currentDetail(){
  if(!state)return "";
  let text=String(state.progressCount||"");
  if(/^\d+(\.\d+)?%$/.test(text.trim()))text=""; // already shown as the percent at the right
  if(state.running&&state.runStartedEpochMs){
    const elapsed=formatElapsed(Date.now()-Number(state.runStartedEpochMs));
    text+=(text?" | ":"")+"Elapsed "+elapsed;
  }
  return text;
}
const ioWorkersSelect=document.getElementById("ioWorkers");
for(let n=1;n<=32;n++){const opt=document.createElement("option");opt.value=String(n);opt.textContent=n+" worker"+(n===1?"":"s");ioWorkersSelect.appendChild(opt);}
function foldersBusy(){return !!(state&&(state.running||state.reviewPending||state.mapOpen));}
function pushFolders(rows){bridge.setFolders(rows,renderState);}
function folderRows(){
  return Array.prototype.map.call(document.querySelectorAll("#sourceRows .pathRow"),function(row){
    return {path:row.querySelector(".pathInput").value,star:row.querySelector(".starBtn").classList.contains("on")};
  });
}
let foldersShown="";
function renderFolders(){
  const host=document.getElementById("sourceRows"), busy=foldersBusy();
  const signature=JSON.stringify([state.folders||[],busy]);
  if(signature===foldersShown)return;
  if(host.contains(document.activeElement)&&document.activeElement.classList.contains("pathInput")&&!busy)return;
  foldersShown=signature;
  host.textContent="";
  (state.folders||[]).forEach(function(folder,i){
    const n=i+1, row=document.createElement("div");
    row.className="sourceBlock";
    const label=document.createElement("div");label.className="labelRow";
    const lab=document.createElement("label");lab.className="fieldLabel";lab.setAttribute("for","folderPath"+i);lab.textContent="Source folder "+n;
    label.appendChild(lab);
    const line=document.createElement("div");line.className="pathRow";
    function mk(cls,text,title,onclick){
      const b=document.createElement("button");b.className="iconBtn "+cls;b.textContent=text;b.title=title;b.setAttribute("aria-label",title);
      b.disabled=busy;b.onclick=onclick;return b;
    }
    const star=mk("starBtn"+(folder.star?" on":""),folder.star?"★":"☆",
      folder.star?"Main folder: kept as the base, other folders are compared against it":"Mark as main folder",
      function(){const rows=folderRows();rows[i].star=!rows[i].star;pushFolders(rows);});
    star.setAttribute("aria-pressed",folder.star?"true":"false");
    const input=document.createElement("input");input.id="folderPath"+i;input.className="pathInput";
    input.value=folder.path||"";input.disabled=busy;input.setAttribute("aria-label","Source folder "+n);
    input.placeholder=folder.star?"Already processed collection":"Folder containing releases to analyze and filter";
    input.onchange=function(){pushFolders(folderRows());};
    const open=mk("pathOpenBtn drawnFolder","📁","Show in Explorer",function(){bridge.openPath(input.value);});
    open.disabled=busy||!String(folder.path||"").trim();
    const browse=mk("","📂","Browse for a folder",function(){bridge.browseFolder(i,renderState);});
    const clear=mk("clearBtn","✕",i<2?"Clear this folder":"Remove this folder",function(){
      const rows=folderRows();
      if(i<2)rows[i].path="";else rows.splice(i,1);
      pushFolders(rows);
    });
    [star,input,open,browse,clear].forEach(function(el){line.appendChild(el);});
    row.appendChild(label);row.appendChild(line);host.appendChild(row);
  });
}
function renderState(raw){
  state=typeof raw==="string"?JSON.parse(raw):raw;
  renderFolders();
  document.getElementById("saveRemixes").checked=!!state.saveRemixes;
  document.getElementById("saveLive").checked=!!state.saveLive;
  document.getElementById("logging").checked=!!state.logging;
  document.getElementById("ioWorkers").value=String(state.ioWorkers||"auto");
  const organizer=state.organizer||{};
  document.getElementById("orgEncode").checked=!!organizer.enable_encoding;
  document.getElementById("orgChecker").checked=!!organizer.enable_checker;
  document.getElementById("orgSplit").checked=!!organizer.enable_splitting;
  document.getElementById("orgFormat").value=organizer.format||"ALAC";
  document.getElementById("personalPicks").textContent=state.personalCount
    ?"Personal Picks ("+state.personalCount+")":"Personal Picks";
  const pending=Number(state.pendingPatternCount||0);
  document.getElementById("pendingPatterns").textContent=pending?"Classify patterns ("+pending+")":"Classify patterns";
  document.getElementById("progressStatus").textContent=state.status||"Ready";
  const pct=Math.max(0,Math.min(100,Number(state.progressPct||0)));
  document.getElementById("progressFill").style.width=pct+"%";
  document.getElementById("progressPercent").textContent=Math.round(pct)+"%";
  document.getElementById("progressTrack").setAttribute("aria-valuenow",String(Math.round(pct)));
  document.getElementById("progressDetail").textContent=currentDetail();
  const act=(state.activity||[]).join("\n");
  document.getElementById("content").classList.toggle("emptyActivity",!act.trim()&&!state.running);
  const box=document.getElementById("activity");
  const atBottom=box.scrollHeight-box.scrollTop-box.clientHeight<30;
  box.textContent=act;
  if(atBottom)box.scrollTop=box.scrollHeight;
  const busy=!!state.running||!!state.reviewPending||!!state.mapOpen;
  document.getElementById("analyzeBtn").disabled=busy;
  document.getElementById("undoBtn").disabled=busy;
  document.getElementById("mapBtn").disabled=busy||!state.mapAvailable;
  ["addFolder","saveRemixes","saveLive","personalPicks","pendingPatterns","logging","ioWorkers","openLogs","orgEncode","orgChecker","orgSplit","orgFormat"].forEach(function(id){
    document.getElementById(id).disabled=!!state.running||!!state.reviewPending||!!state.mapOpen;
  });
  if(!(state.organizer||{}).enable_encoding)document.getElementById("orgFormat").disabled=true;
}
setInterval(function(){
  if(state&&state.running)document.getElementById("progressDetail").textContent=currentDetail();
},1000);

function openModal(kind,title,subtitle,bodyHtml,buttonsHtml){
  modalKind=kind;
  // Re-rendering an already open modal must not replace its original focus target
  // with a now-deleted row button.
  if(!document.getElementById("modalBackdrop").classList.contains("open"))
    modalReturnFocus=document.activeElement;
  document.getElementById("modalTitle").textContent=title||"";
  document.getElementById("modalSubtitle").textContent=subtitle||"";
  document.getElementById("modalBody").innerHTML=bodyHtml||"";
  document.getElementById("modalFoot").innerHTML=buttonsHtml||"";
  document.getElementById("modalBackdrop").classList.add("open");
  requestAnimationFrame(function(){
    const first=document.querySelector("#modal button:not(:disabled),#modal input:not(:disabled),#modal select:not(:disabled),#modal textarea:not(:disabled)");
    if(first) first.focus();
  });
}
function closeModal(){
  modalKind="";
  document.getElementById("modalBackdrop").classList.remove("open");
  if(modalReturnFocus&&typeof modalReturnFocus.focus==="function") modalReturnFocus.focus();
  modalReturnFocus=null;
}
document.addEventListener("keydown",function(e){
  if(e.key==="Escape"&&document.getElementById("modalBackdrop").classList.contains("open")){
    e.preventDefault();
    const postpone=modalKind==="pattern"?patternLaterAction:null;
    const cancelManual=modalKind==="manual";
    closeModal();
    if(postpone)postpone();
    else if(cancelManual)bridge.cancelReview();
  }
});
function messageBodyWithPaths(message){
  const lines=String(message==null?"":message).split("\n");
  return '<div class="msg">'+lines.map(function(line){
    let pos=line.search(/[A-Za-z]:[\\/]/);
    if(pos<0){
      const unc=line.indexOf("\\\\");
      if(unc>=0)pos=unc;
    }
    if(pos<0)return '<div class="msgLine">'+(line?esc(line):'&nbsp;')+'</div>';
    const prefix=line.slice(0,pos);
    const path=line.slice(pos).trim();
    if(!path)return '<div class="msgLine">'+esc(line)+'</div>';
    return '<div class="msgLine msgPathLine">'
      +'<span class="msgPathPrefix">'+esc(prefix)+'</span>'
      +'<button class="iconBtn msgPathOpen drawnFolder" data-path="'+esc(path)+'" title="Open path location" aria-label="Open path location">📁</button>'
      +'<span class="msgPathValue">'+esc(path)+'</span></div>';
  }).join("")+'</div>';
}
function bindMessagePathButtons(){
  document.querySelectorAll(".msgPathOpen").forEach(function(btn){
    btn.onclick=function(){bridge.openPath(btn.dataset.path||"");};
  });
}
function messageModal(title,message){
  openModal("message",title,"",messageBodyWithPaths(message),
    '<div class="modalSpacer"></div><button class="btn primary" id="msgOk">OK</button>');
  bindMessagePathButtons();
  document.getElementById("msgOk").onclick=closeModal;
}
function confirmModal(title,message,yesText,onYes){
  openModal("confirm",title,"",'<div class="msg">'+esc(message)+'</div>',
    '<div class="modalSpacer"></div><button class="btn" id="confirmNo">Cancel</button>'
    +'<button class="btn danger" id="confirmYes">'+esc(yesText||"Continue")+'</button>');
  document.getElementById("confirmNo").onclick=closeModal;
  document.getElementById("confirmYes").onclick=function(){closeModal();onYes();};
}
function patternManagerModal(raw){
  const data=typeof raw==="string"?JSON.parse(raw):raw;
  const cat=(data.categories||[]).map(x=>({...x}));
  const pending=(data.pending||[]);
  let content="";
  [["remix","Remix"],["live","Live"],["skip","Skip"]].forEach(function(section){
    const rows=cat.filter(x=>x.kind===section[0]);
    content+='<div class="categoryHeading">'+section[1]+' ('+rows.length+')</div>';
    content+=rows.length?rows.map(x=>'<div class="pickRow">'
      +'<div class="pickValue">'+esc(x.label||x.key)+'</div>'
      +'<button class="btn patternToPicks" data-key="'+esc(x.key)+'">→ Personal Picks</button>'
      +'<button class="btn patternForget" data-key="'+esc(x.key)+'">Forget</button></div>').join("")
      :'<div class="empty">None</div>';
  });
  if(pending.length){
    content+='<div class="categoryHeading">Pending ('+pending.length+')</div>'
      +'<div class="pendingPatternNames">'+pending.map(p=>esc(p.label||p.key)).join(' · ')+'</div>';
  }
  openModal("patternManager","Classify patterns","",content,
    (pending.length?'<button class="btn primary" id="reviewPendingBtn">Review pending ('+pending.length+')</button>':'')
    +'<div class="modalSpacer"></div><button class="btn" id="patternsClose">Close</button>');
  function update(action,key){
    const found=cat.findIndex(x=>x.key===key);
    if(found<0)return;
    const entry=cat.splice(found,1)[0];
    bridge.savePatternManager(JSON.stringify({categories:cat,promote:action==="picks"?[entry]:[]}),
      function(){bridge.getPatternManager(patternManagerModal);});
  }
  document.querySelectorAll(".patternForget").forEach(btn=>{
    btn.onclick=function(){update("forget",btn.dataset.key);};
  });
  document.querySelectorAll(".patternToPicks").forEach(btn=>{
    btn.onclick=function(){update("picks",btn.dataset.key);};
  });
  const reviewPending=document.getElementById("reviewPendingBtn");
  if(reviewPending)reviewPending.onclick=function(){closeModal();bridge.openPendingPatterns();};
  document.getElementById("patternsClose").onclick=closeModal;
}
function patternReview(data){
  const patterns=data.patterns||[];
  const selected=Object.create(null);
  let submitting=false;
  const choices=[
    ["remix","Remix","Remember as Remix; follows Save Remixes"],
    ["live","Live","Remember as Live; follows Save Live recordings"],
    ["keep","Keep","Remember in Personal Picks"],
    ["skip","Skip","Remember: exclude this pattern in future scans"]
  ];
  let rows="";
  patterns.forEach(function(p,i){
    rows+='<div class="reviewRow patternReviewRow" data-pattern-i="'+i+'">'
      +'<div class="reviewTop"><div class="reviewTitle" id="patternLabel'+i+'">'
      +esc(p.label)+' ('+esc(p.count)+')</div></div>'
      +(function(){
        // Show useful track context without restating the pattern name.
        const variants=(p.variants||[]).filter(function(v){
          return String(v).trim().toLowerCase()!==String(p.label).trim().toLowerCase();
        }).slice(0,4);
        const examples=(p.examples||[]).slice(0,3);
        const details=[...new Set(examples.concat(variants).map(String).filter(Boolean))];
        return details.length?'<div class="reviewDetails">'+esc(details.join(" · "))+'</div>':"";
      })()
      +'<div class="patternChoiceGroup" role="group" aria-labelledby="patternLabel'+i+'">'
      +choices.map(function(item){
        return '<button type="button" class="patternChoice" data-i="'+i+'" data-choice="'+item[0]
          +'" aria-pressed="false" aria-label="'+esc(item[2]+": "+p.label)+'" title="'+esc(item[2])+'">'
          +esc(item[1])+'</button>';
      }).join("")
      +'</div></div>';
  });
  const saveError=data.saveError?"Save failed: "+String(data.saveError):"";
  openModal("pattern","Classify patterns",saveError,
    rows||'<div class="empty">No unusual patterns</div>',
    (data.deferred?'':'<button class="btn" id="patternCancel">Cancel scan</button>')
      +'<div class="modalSpacer"></div><button class="btn primary" id="patternLater">Later</button>');
  patternLaterAction=function(){bridge.deferPatternReview(JSON.stringify(selected));};
  document.getElementById("patternLater").onclick=function(){
    const postpone=patternLaterAction;
    closeModal();
    if(postpone)postpone();
  };
  if(!data.deferred)document.getElementById("patternCancel").onclick=function(){
    closeModal();bridge.cancelReview();
  };
  document.querySelectorAll(".patternChoice").forEach(function(button){
    button.onclick=function(){
      if(submitting)return;
      const i=Number(button.dataset.i);
      const p=patterns[i];
      const choice=String(button.dataset.choice||"");
      if(!p||!["remix","live","keep","skip"].includes(choice))return;
      selected[p.key]=choice;
      const row=button.closest(".patternReviewRow");
      if(row){
        row.classList.add("isChosen");
        row.querySelectorAll(".patternChoice").forEach(function(other){
          other.setAttribute("aria-pressed",other===button?"true":"false");
        });
      }
      const count=Object.keys(selected).length;
      if(count<patterns.length){
        document.getElementById("modalSubtitle").textContent=saveError+(saveError?" · ":"")+count+" / "+patterns.length+" classified";
        return;
      }
      // No redundant Save/Continue action: the final choice commits all
      // classifications atomically through the existing validated bridge.
      submitting=true;
      document.querySelectorAll(".patternChoice").forEach(function(other){other.disabled=true;});
      closeModal();
      bridge.submitPatternReview(JSON.stringify(selected));
    };
  });
}
function manualReview(data){
  let rows="";
  (data.candidates||[]).forEach(function(p,i){
    const reason=p.reason==="different_titles_same_audio"
      ?"Strong acoustic match, but the titles are different."
      :"Very close same-title acoustic result, but below automatic acceptance.";
    const metrics=(p.score!==undefined)
      ?("score "+esc(p.score)+" | overlap "+esc(Math.round((p.overlap||0)*100))+"% | good "+esc(Math.round((p.good||0)*100))+"%")
      :"";
    rows+='<div class="reviewRow"><div class="reviewTop">'
      +'<input class="reviewCheck manualSame" type="checkbox" data-i="'+i+'">'
      +'<div class="reviewTitle">Same recording</div>'
      +'<div class="reviewMeta">'+esc(reason)+'</div></div>'
      +'<div class="reviewDetails"><b>A:</b> '+esc(p.title_a||"")+(p.artist_a?' - '+esc(p.artist_a):"")
      +'<br><b>B:</b> '+esc(p.title_b||"")+(p.artist_b?' - '+esc(p.artist_b):"")
      +(metrics?'<br>'+metrics:"")+'</div>'
      +'<div class="reviewTop" style="margin-top:6px">'
      +'<button class="btn manualOpenA" data-i="'+i+'">Open A</button>'
      +'<button class="btn manualOpenB" data-i="'+i+'">Open B</button></div></div>';
  });
  openModal("manual","Manual acoustic review",
    "These are rare ambiguous cases only. Check Same recording only when both files are the same recording/version. Unchecked pairs stay separate and both remain eligible.",
    rows||'<div class="empty">No ambiguous pairs</div>',
    '<button class="btn" id="manualNone">Mark all different</button>'
      +'<div class="modalSpacer"></div><button class="btn" id="manualCancel">Cancel</button>'
      +'<button class="btn primary" id="manualContinue">Continue</button>');
  document.querySelectorAll(".manualOpenA").forEach(function(btn){
    btn.onclick=function(){const p=data.candidates[Number(btn.dataset.i)];bridge.openPath(p.path_a||"");};
  });
  document.querySelectorAll(".manualOpenB").forEach(function(btn){
    btn.onclick=function(){const p=data.candidates[Number(btn.dataset.i)];bridge.openPath(p.path_b||"");};
  });
  document.getElementById("manualNone").onclick=function(){
    document.querySelectorAll(".manualSame").forEach(function(x){x.checked=false;});
  };
  document.getElementById("manualCancel").onclick=function(){closeModal();bridge.cancelReview();};
  document.getElementById("manualContinue").onclick=function(){
    const accepted=[];
    document.querySelectorAll(".manualSame").forEach(function(cb){
      if(cb.checked){
        const p=data.candidates[Number(cb.dataset.i)];
        accepted.push(p.key);
      }
    });
    closeModal();bridge.submitManualReview(JSON.stringify(accepted));
  };
}
function renderPickRows(){
  const host=document.getElementById("pickRows");
  if(!host)return;
  const search=document.getElementById("picksSearch");
  const query=String(search&&search.value||"").trim().toLocaleLowerCase();
  const sections=[["contains","Phrases"],["exact","Exact titles"],["pattern","Patterns"]];
  const rows=sections.map(function(section){
    const matches=localPicks.map((p,i)=>({p,i})).filter(function(x){
      return x.p.mode===section[0] && String(x.p.value).toLocaleLowerCase().includes(query);
    });
    if(!matches.length)return "";
    return '<div class="categoryHeading">'+section[1]+' ('+matches.length+')</div>'
      +matches.map(function(x){
        return '<div class="pickRow"><div class="pickMode">'+(x.p.mode==="contains"?"Phrase":(x.p.mode==="exact"?"Exact":"Pattern"))+'</div>'
          +'<div class="pickValue" title="'+esc(x.p.value)+'">'+esc(x.p.value)+'</div>'
          +(x.p.mode==="pattern"?"":'<button class="btn pickEdit" data-i="'+x.i+'" aria-label="Edit '+esc(x.p.value)+'">Edit</button>')
          +'<button class="btn pickRemove" data-i="'+x.i+'" aria-label="Remove '+esc(x.p.value)+'">Remove</button></div>';
      }).join("");
  }).join("");
  host.innerHTML=rows||(query?'<div class="empty">No matching picks</div>':'<div class="empty">No Personal Picks</div>');
  host.querySelectorAll(".pickRemove").forEach(function(btn){
    btn.onclick=function(){localPicks.splice(Number(btn.dataset.i),1);renderPickRows();};
  });
  host.querySelectorAll(".pickEdit").forEach(function(btn){
    btn.onclick=function(){
      const i=Number(btn.dataset.i), valueEl=btn.parentElement.querySelector(".pickValue");
      const input=document.createElement("input");
      input.className="pathInput pickEditInput";input.value=localPicks[i].value;
      input.setAttribute("aria-label","Edit Personal Pick");
      valueEl.replaceWith(input);btn.textContent="Done";btn.disabled=true;
      let finished=false;
      function finish(commit){
        if(finished)return;finished=true;
        const next=input.value.trim();
        if(commit&&next){
          const duplicate=localPicks.some((p,j)=>j!==i&&p.mode===localPicks[i].mode&&p.value.toLocaleLowerCase()===next.toLocaleLowerCase());
          if(!duplicate)localPicks[i].value=next;
        }
        renderPickRows();
        if(search)search.focus();
      }
      input.addEventListener("keydown",function(ev){
        if(ev.key==="Enter"){ev.preventDefault();finish(true);}
        if(ev.key==="Escape"){ev.preventDefault();finish(false);}
      });
      input.addEventListener("blur",function(){finish(true);},{once:true});
      input.focus();input.select();
    };
  });
}
function personalPicksModal(raw){
  const data=typeof raw==="string"?JSON.parse(raw):raw;
  localPicks=(data.rules||[]).map(function(x){
    const mode=x.mode==="pattern"?"pattern":(x.mode==="exact"?"exact":"contains");
    const item={mode:mode,value:String(x.value||"")};
    if(mode==="pattern")item.key=String(x.key||"");
    return item;
  });
  openModal("picks","Personal Picks",
    "Keep patterns and titles as explicit inclusion exceptions.",
    '<div class="picksEntry"><input class="pathInput" id="pickInput" placeholder="Phrase or exact track title">'
      +'<button class="btn" id="addPhrase">Add phrase</button><button class="btn" id="addExact">Add exact title</button></div>'
      +'<input class="pathInput pickFilter" type="search" id="picksSearch" aria-label="Search Personal Picks" placeholder="Find saved pick...">'
      +'<div class="picksList" id="pickRows"></div>',
    '<button class="btn" id="copyPicks">Copy picks</button><button class="btn danger" id="clearPicks">Clear all</button>'
      +'<div class="modalSpacer"></div><button class="btn" id="picksCancel">Cancel</button>'
      +'<button class="btn primary" id="picksSave">Save</button>');
  renderPickRows();
  document.getElementById("picksSearch").oninput=renderPickRows;
  function add(mode){
    const input=document.getElementById("pickInput"),value=input.value.trim();if(!value)return;
    const key=value.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,"");
    if(!localPicks.some(function(p){return p.mode===mode&&p.value.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,"")===key;})){
      localPicks.push({mode:mode,value:value});renderPickRows();
    }
    input.value="";input.focus();
  }
  document.getElementById("addPhrase").onclick=function(){add("contains");};
  document.getElementById("addExact").onclick=function(){add("exact");};
  document.getElementById("pickInput").onkeydown=function(e){if(e.key==="Enter")add("contains");};
  document.getElementById("copyPicks").onclick=function(){
    bridge.copyText(localPicks.map(function(p){
      return (p.mode==="pattern"?"Pattern: ":(p.mode==="exact"?"Exact title: ":"Phrase: "))+p.value;
    }).join("\n"));
  };
  document.getElementById("clearPicks").onclick=function(){localPicks=[];renderPickRows();};
  document.getElementById("picksCancel").onclick=closeModal;
  document.getElementById("picksSave").onclick=function(){
    closeModal();bridge.savePersonalPicks(JSON.stringify({rules:localPicks}),renderState);
  };
  document.getElementById("pickInput").focus();
}
function doneModal(data){
  currentDone=data;
  const r=data.result||{};
  const body='<div class="doneGrid">'
    +'<div class="doneStat">Recycle releases kept<b>'+esc(r.remaining_recycle||0)+'</b></div>'
    +'<div class="doneStat">Redundant releases moved<b>'+esc(r.moved||0)+'</b></div>'
    +'<div class="doneStat">Duplicate files removed<b>'+esc(r.intra_duplicate_files||0)+'</b></div>'
    +'<div class="doneStat">Moved under !Remixes<b>'+esc(r.remix_moved||0)+'</b></div>'
    +'</div><div class="reviewDetails" style="margin-top:10px">Added: '+esc(r.add||0)
    +' · Replaced: '+esc(r.replace||0)+' · Recycle skipped: '+esc(r.skipped_recycle||0)
    +' · Existing removed: '+esc(r.removed_current||0)+'</div>'
    +'<div class="pathNote"><button class="iconBtn drawnFolder" id="openDupPathInline" title="Open duplicates folder" aria-label="Open duplicates folder">📁</button>'
    +'<span class="pathNoteText">Duplicates: '+esc(data.duplicates||"")+'</span></div>';
  openModal("done","Completed","Filesystem changes finished.",body,
    '<button class="btn" id="openRecycleDone">Open recycle</button>'
    +'<button class="btn" id="openDupDone">Open duplicates</button>'
    +'<button class="btn" id="undoDone">Undo last run</button>'
    +'<button class="btn" id="mapDone">Release Map...</button>'
    +'<div class="modalSpacer"></div><button class="btn primary" id="doneClose">Close</button>');
  document.getElementById("openRecycleDone").onclick=function(){bridge.openPath(data.recycle||"");};
  document.getElementById("openDupDone").onclick=function(){bridge.openPath(data.duplicates||"");};
  document.getElementById("openDupPathInline").onclick=function(){bridge.openPath(data.duplicates||"");};
  document.getElementById("undoDone").onclick=function(){
    confirmModal("Undo last run?","Delete the files created by the last Copy?","Undo",function(){bridge.undoLastRun();});
  };
  document.getElementById("mapDone").onclick=function(){closeModal();bridge.openReleaseMap();};
  document.getElementById("doneClose").onclick=closeModal;
}
function copyDoneModal(data){
  const r=data.result||{};
  const c=r.counts||{};
  const moved=!!r.source_folders_modified;
  const problems=r.problems||[];
  const title=moved?"Discography moved":"Discography copied";
  const body='<div class="doneGrid">'
    +'<div class="doneStat">Releases done<b>'+esc(c.done||0)+'</b></div>'
    +'<div class="doneStat">Partial<b>'+esc(c.partial||0)+'</b></div>'
    +'<div class="doneStat">Failed<b>'+esc(c.failed||0)+'</b></div>'
    +'<div class="doneStat">Skipped<b>'+esc(c.skipped||0)+'</b></div>'
    +'</div>'
    +(problems.length?'<div class="pathNote"><span class="pathNoteText">'+problems.slice(0,8).map(esc).join('<br>')+(problems.length>8?'<br>…':'')+'</span></div>':'')
    +'<div class="pathNote"><button class="iconBtn drawnFolder" id="openCopyPathInline" title="Open output" aria-label="Open output">📁</button>'
    +'<span class="pathNoteText">Destination: '+esc(data.destination||"")+'</span></div>';
  openModal("done",title,moved
    ?"Move complete. Originals are in the Recycle Bin."
    :"Copy complete. Originals were left unchanged.",body,
    (moved?'':'<button class="btn" id="undoCopy">Undo copy</button><button class="btn" id="mapAfterCopy">Release Map...</button>')
    +'<div class="modalSpacer"></div><button class="btn primary" id="copyDoneClose">Close</button>');
  document.getElementById("openCopyPathInline").onclick=function(){bridge.openPath(data.destination||"");};
  if(!moved){
    document.getElementById("undoCopy").onclick=function(){
      confirmModal("Undo last run?","Delete the files created by the last Copy?","Undo",function(){bridge.undoLastRun();});
    };
    document.getElementById("mapAfterCopy").onclick=function(){closeModal();bridge.openReleaseMap();};
  }
  document.getElementById("copyDoneClose").onclick=closeModal;
}
function handleEvent(raw){
  const e=typeof raw==="string"?JSON.parse(raw):raw;
  if(e.type==="error"||e.type==="info"){messageModal(e.title||"Music Collection Cleaner",e.message||"");return;}
  if(e.type==="patternReview"){patternReview(e);return;}
  if(e.type==="manualReview"){manualReview(e);return;}
  if(e.type==="copyDone"){copyDoneModal(e);return;}
  if(e.type==="done"){doneModal(e);return;}
}
document.getElementById("addFolder").onclick=function(){
  const rows=folderRows();rows.push({path:"",star:false});pushFolders(rows);
};
document.getElementById("saveRemixes").onchange=function(){bridge.setOption("saveRemixes",this.checked,renderState);};
document.getElementById("saveLive").onchange=function(){bridge.setOption("saveLive",this.checked,renderState);};
document.getElementById("logging").onchange=function(){bridge.setOption("logging",this.checked,renderState);};
document.getElementById("orgEncode").onchange=function(){bridge.setOrganizerOption("enable_encoding",this.checked,renderState);};
document.getElementById("orgChecker").onchange=function(){bridge.setOrganizerOption("enable_checker",this.checked,renderState);};
document.getElementById("orgSplit").onchange=function(){bridge.setOrganizerOption("enable_splitting",this.checked,renderState);};
document.getElementById("orgFormat").onchange=function(){bridge.setOrganizerOption("format",this.value,renderState);};
document.getElementById("ioWorkers").onchange=function(){bridge.setIoWorkers(this.value,renderState);};
document.getElementById("openLogs").onclick=function(){bridge.openLogsFolder();};
document.getElementById("personalPicks").onclick=function(){bridge.getPersonalPicks(personalPicksModal);};
document.getElementById("pendingPatterns").onclick=function(){bridge.getPatternManager(patternManagerModal);};
document.getElementById("analyzeBtn").onclick=function(){
  bridge.startAnalyze(
    folderRows(),
    document.getElementById("saveRemixes").checked,
    document.getElementById("saveLive").checked,
    document.getElementById("logging").checked,
    renderState
  );
};
document.getElementById("undoBtn").onclick=function(){
  confirmModal("Undo last run?","Delete the files created by the last Copy?","Undo",function(){bridge.undoLastRun();});
};
document.getElementById("mapBtn").onclick=function(){bridge.openReleaseMap();};
document.getElementById("closeBtn").onclick=function(){bridge.closeApp();};

let __deaStateListener=null;
let __deaEventListener=null;
let __deaBridgeFailureShown=false;
window.__deaStateChanged=function(raw){if(__deaStateListener)__deaStateListener(raw);};
window.__deaEventRaised=function(raw){if(__deaEventListener)__deaEventListener(raw);};

function waitForPywebviewMethod(name,timeoutMs){
  const limit=Number(timeoutMs||30000);
  return new Promise(function(resolve,reject){
    const started=Date.now();
    function probe(){
      const api=window.pywebview&&window.pywebview.api;
      const fn=api&&api[name];
      if(typeof fn==="function"){resolve({api:api,fn:fn});return;}
      if(Date.now()-started>=limit){
        reject(new Error("Desktop bridge method did not become ready: "+String(name)));
        return;
      }
      setTimeout(probe,25);
    }
    probe();
  });
}
function showBridgeFailure(error){
  console.error(error);
  if(__deaBridgeFailureShown)return;
  __deaBridgeFailureShown=true;
  const message=String(error&&error.message||error||"Unknown desktop bridge error");
  try{
    document.getElementById("progressStatus").textContent="Desktop bridge failed";
    document.getElementById("progressDetail").textContent=message;
    messageModal("Music Collection Cleaner","Desktop bridge failed:\n\n"+message);
  }catch(_ignored){}
}
function bridgeCall(name,args,callback){
  return waitForPywebviewMethod(name,30000).then(function(entry){
    return entry.fn.apply(entry.api,args);
  }).then(function(result){
    if(callback)callback(typeof result==="string"?result:JSON.stringify(result));
    return result;
  }).catch(function(error){
    showBridgeFailure(error);
    throw error;
  });
}
function createLightMainBridge(){
  const target={
    stateChanged:{connect:function(fn){__deaStateListener=fn;}},
    eventRaised:{connect:function(fn){__deaEventListener=fn;}}
  };
  return new Proxy(target,{
    get:function(obj,name){
      if(name in obj)return obj[name];
      return function(){
        const args=Array.from(arguments);
        const callback=(args.length&&typeof args[args.length-1]==="function")?args.pop():null;
        return bridgeCall(name,args,callback);
      };
    }
  });
}

// Create the bridge immediately. Each call waits until its exact pywebview
// method exists, because pywebview.api can appear before the method table is populated.
bridge=createLightMainBridge();
bridge.stateChanged.connect(renderState);
bridge.eventRaised.connect(handleEvent);
bridge.getState(renderState).catch(function(){});

// Refresh once more when pywebview announces readiness. This is additive,
// not the only initialization path.
window.addEventListener("pywebviewready",function(){
  bridge.getState(renderState).catch(function(){});
});
</script>
</body>
</html>'''
    return _apply_app_theme(html)


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
                    "organizer": _organizer_options(),
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

        def setOrganizerOption(self, name: str, value):
            if self.running or self.review_pending or self.map_open:
                return self._state_json()
            _save_organizer_option(str(name), value)
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
                result = organize_retained_plan(
                    existing if isinstance(existing, Path) else None,
                    recycle, destination, releases, decisions, is_move, _organizer_options(),
                    self._progress, extra_roots=list(session.get("extra_roots", []) or []),
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
            self.status = "Move complete - originals in Recycle Bin" if moved else "Copy complete - Undo available"
            counts = result.get("counts", {})
            self._append_activity(
                f"{'Move' if moved else 'Copy'} complete: {counts.get('done', 0)} done, "
                f"{counts.get('partial', 0)} partial, {counts.get('failed', 0)} failed"
            )
            for problem in result.get("problems", []):
                self._append_activity(problem)
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
        background_color=DESIGN_CANVAS_HEX,
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
            "setOrganizerOption",
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
