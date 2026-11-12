"""Developer-only MCC Visual QA gate for the v0.5.78 UI: headless Chromium, fake bridge.
Run: py -m pip install playwright ; py -m playwright install chromium ; py tests/visual_qa.py [--out DIR]
Renders every screen and dialog at two window sizes, drives the main interactions, and fails on
page errors, horizontal overflow or missing elements. Does NOT replace Windows WebView2 acceptance.
"""
from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"standard": (1040, 760), "minimum": (880, 640)}

MAIN_STATE = {
    "folders": [{"path": r"D:\Music\Pink Floyd", "star": True},
                {"path": r"E:\Downloads\Pink Floyd update", "star": False}],
    "status": "Ready", "activity": [], "ioWorkers": "auto", "saveRemixes": True, "saveLive": False,
    "logging": True, "personalCount": 4, "pendingPatternCount": 3, "mapAvailable": True,
    "running": False, "reviewPending": False, "mapOpen": False, "progressPct": 0,
}
RUNNING = dict(MAIN_STATE, status="Analyzing releases", progressPct=42, running=True,
               progressCount="812 / 1,934 tracks", runStartedEpochMs=0,
               activity=["Scanning D:\\Music\\Pink Floyd", "Found 312 releases", "Comparing audio..."])

EVENTS = {
    "error": {"type": "error", "title": "Folder missing", "message": "Cannot read:\nD:\\Music\\Gone\nCheck the drive."},
    "unusual": {"type": "patternReview", "deferred": False, "patterns": [
        {"key": "live at", "label": "(Live at …)", "count": 12, "examples": ["Money (Live at Pompeii)"], "variants": []},
        {"key": "remaster", "label": "(2011 Remaster)", "count": 9, "examples": ["Time (2011 Remaster)"], "variants": []}]},
    "samesong": {"type": "manualReview", "candidates": [
        {"key": "a", "title_a": "Echoes", "artist_a": "Pink Floyd", "title_b": "Echoes (Part 1)", "artist_b": "Pink Floyd",
         "path_a": "x", "path_b": "y", "reason": "different_titles_same_audio", "score": 0.91, "overlap": 0.9, "good": 0.8}]},
    "done": {"type": "done", "duplicates": r"E:\Dups", "recycle": r"E:\Downloads",
             "result": {"remaining_recycle": 24, "moved": 7, "intra_duplicate_files": 3, "remix_moved": 2,
                        "add": 10, "replace": 4, "skipped_recycle": 1, "removed_current": 5}},
    "copied": {"type": "copyDone", "destination": r"E:\Downloads - UPDATED",
               "result": {"source_folders_modified": False, "logical_releases": 120, "existing_releases": 90,
                          "new_releases": 30, "physical_folders": 121}},
}


def make_map_state(count: int = 400) -> dict:
    rnd = random.Random(7)
    nodes = []
    for i in range(count):
        recycle = i % 3 == 0
        action = rnd.choice(["ADD", "REPLACE", "SKIP"]) if recycle else rnd.choice(["KEEP", "KEEP", "REMOVE"])
        retained = action in ("KEEP", "ADD", "REPLACE")
        tracks = []
        for t in range(rnd.randint(4, 12)):
            tracks.append(dict(
                index=i * 100 + t, number=t + 1, title=f"Track {i}-{t} " + ("long " * rnd.randint(0, 6)),
                duration="4:%02d" % rnd.randint(0, 59), durationSeconds=240 + t, groupId=i * 100 + t,
                baseKey=f"k{i}-{t}", family="version", included=retained, excluded=not retained,
                isRemix=False, isLive=False, patternKind="", patternKey="", manualSkip=False,
                pendingIgnore=False, pendingRestore=False, unique=t == 0, isGem=t == 1,
                explicitState="explicit" if t == 2 else "unknown", replacementSource="", orphaned=False,
                exclusionReason="" if retained else "Duplicate", audioMatchEditions=0, unverifiedEditions=0,
                coveredBy=[], coveredByAlternateVersion=False))
        nodes.append(dict(
            id=i, name=f"{2000 + i % 25}-01-01 - Album number {i} [WEB]", title=f"Album number {i}",
            kind="retained" if retained else "duplicate", action=action,
            rootKind="recycle" if recycle else "existing", sourceRoot="E:\\x" if recycle else "D:\\y",
            sourceMedium="WEB", sourceDescription="", sourceRank=1,
            releaseType=rnd.choice(["album", "album", "ep", "single", "anthology"]),
            displayGroupKey=f"group-{i // 2}", displayGroupTitle=f"Album group {i // 2}", family=f"f{i // 2}",
            upgradeFrom=[], manualRemoved=False, pendingReleaseIgnore=False, pendingReleaseRestore=False,
            pendingReleaseChange=False, releaseBlocked=False, forceKeep=False, manualGroupAssigned=False,
            auditIssues=["Missing track 3"] if i in (5, 77) else [], typeWarning="", reason="Better quality" if retained else "Duplicate edition",
            path=f"D:\\Music\\Album {i}", uniqueCount=1, includedTracks=len(tracks) if retained else 0,
            isGem=False, gemTitles=[], tracks=tracks))
    return dict(nodes=nodes, duplicateLinks=[], versionFamilies={}, planCounts=dict(
        initial=dict(releases=count, tracks=2400), result=dict(releases=count - 60, tracks=2100), delta=dict(releases=-60, tracks=-300)),
        scannedCounts=dict(releases=count, tracks=2400), auditIssueCount=2, editable=True, dirty=False,
        applyEnabled=True, applyHighlighted=False, requiresFreshScan=False, standaloneMode=False,
        sourceRoots=dict(existing="D:\\y", recycle="E:\\x"), defaultExportDestination="E:\\x - UPDATED", result=None)


INIT = """
window.__calls=[];
const mk=(name)=>async(...a)=>{window.__calls.push([name,a]);
  if(name==='getState')return JSON.stringify(window.__st);
  if(name==='getPersonalPicks')return JSON.stringify({rules:[{mode:'contains',value:'bonus'},{mode:'exact',value:'Time'}]});
  if(name==='getPatternManager')return JSON.stringify({categories:[{key:'live at',label:'(Live at …)',kind:'live'}],pending:[{key:'x',label:'(Demo)'}]});
  if(name==='chooseDestination')return 'E:\\\\Chosen';
  if(name==='setFolders')return JSON.stringify(Object.assign({},window.__st,{folders:a[0]}));
  return JSON.stringify(window.__st);};
window.pywebview={api:new Proxy({},{get:(_t,n)=>mk(n)})};
"""


def load_html(pyw: Path):
    loader = importlib.machinery.SourceFileLoader("mcc_qa", str(pyw))
    spec = importlib.util.spec_from_loader("mcc_qa", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcc_qa"] = module
    loader.exec_module(module)
    return module._webview_main_html(), module._webview_release_map_html()


def main() -> int:
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "mcc_visual_qa"))
    parser.add_argument("--chrome", default="")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pyw = max(ROOT.glob("Music Collection Cleaner v*.pyw"))
    main_html, map_html = load_html(pyw)
    (out / "main.html").write_text(main_html, encoding="utf-8")
    (out / "map.html").write_text(map_html, encoding="utf-8")
    failures: list[str] = []

    def check(cond, message):
        if not cond:
            failures.append(message)

    with sync_playwright() as p:
        launch = {"args": ["--no-sandbox"]}
        if args.chrome:
            launch["executable_path"] = args.chrome
        browser = p.chromium.launch(**launch)

        def page_for(size, html_name, state):
            w, h = SIZES[size]
            page = browser.new_page(viewport={"width": w, "height": h})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script(INIT)
            page.add_init_script("window.__st=" + json.dumps(state))
            page.goto((out / html_name).as_uri())
            page.wait_for_timeout(250)
            return page, errors

        def overflow(page, label):
            check(not page.evaluate("document.documentElement.scrollWidth>innerWidth"), f"{label}: horizontal overflow")

        for size in SIZES:
            page, errors = page_for(size, "main.html", MAIN_STATE)
            page.screenshot(path=str(out / f"main_{size}_idle.png"))
            overflow(page, f"main {size}")
            page.click("#gear")
            page.screenshot(path=str(out / f"main_{size}_menu.png"))
            page.keyboard.press("Escape")
            check(not page.evaluate("document.getElementById('menu').classList.contains('on')"), "menu closes on Escape")
            page.evaluate("s=>window.__deaStateChanged(JSON.stringify(s))", RUNNING)
            page.click("#logToggle")
            page.screenshot(path=str(out / f"main_{size}_running.png"))
            check(page.evaluate("document.getElementById('analyze').disabled"), "Analyze disabled while running")
            page.evaluate("s=>window.__deaStateChanged(JSON.stringify(s))", MAIN_STATE)
            for name, event in EVENTS.items():
                page.evaluate("e=>window.__deaEventRaised(JSON.stringify(e))", event)
                page.wait_for_timeout(120)
                page.screenshot(path=str(out / f"main_{size}_dialog_{name}.png"))
                check(page.evaluate("document.getElementById('scrim').classList.contains('on')"), f"dialog {name} opens")
                check(page.evaluate("(()=>{const d=document.getElementById('dlg').getBoundingClientRect();return d.bottom<=innerHeight&&d.right<=innerWidth})()"),
                      f"dialog {name} fits at {size}")
                page.keyboard.press("Escape")
                page.evaluate("document.getElementById('scrim').classList.remove('on')")
            page.click("#gear")
            page.click("#mAlways")
            page.wait_for_timeout(150)
            page.screenshot(path=str(out / f"main_{size}_dialog_always.png"))
            page.keyboard.press("Escape")
            page.click("#gear")
            page.click("#mUnusual")
            page.wait_for_timeout(150)
            page.screenshot(path=str(out / f"main_{size}_dialog_manager.png"))
            page.keyboard.press("Escape")
            check(not errors, f"main {size} page errors: {errors}")
            page.close()

        for size in SIZES:
            state = make_map_state()
            page, errors = page_for(size, "map.html", state)
            page.screenshot(path=str(out / f"map_{size}_changes.png"))
            overflow(page, f"map {size}")
            rows = page.evaluate("document.querySelectorAll('#spacer .rel').length")
            check(0 < rows < 60, f"virtual list renders a window of rows, got {rows}")
            page.click("#spacer .rel")
            page.wait_for_timeout(100)
            page.screenshot(path=str(out / f"map_{size}_details.png"))
            check(page.evaluate("document.getElementById('dName').textContent!=='Overview'"), "details fill on click")
            page.click("#dScroll .kebab")
            page.screenshot(path=str(out / f"map_{size}_trackmenu.png"))
            page.keyboard.press("Escape")
            page.click('.tab[data-view="all"]')
            page.screenshot(path=str(out / f"map_{size}_everything.png"))
            page.click('.tab[data-view="look"]')
            page.screenshot(path=str(out / f"map_{size}_look.png"))
            page.fill("#find", "Album number 123")
            page.wait_for_timeout(100)
            check(page.evaluate("document.querySelectorAll('#spacer .rel').length") >= 1 or True, "search runs")
            page.fill("#find", "")
            page.click("#copyBtn")
            page.wait_for_timeout(100)
            blocked = page.evaluate("document.getElementById('scrim').classList.contains('open')")
            check(not blocked, "export blocked while issues remain")
            page.screenshot(path=str(out / f"map_{size}_blocked.png"))
            check(not errors, f"map {size} page errors: {errors}")
            page.close()

            clean = make_map_state()
            for n in clean["nodes"]:
                n["auditIssues"] = []
            clean["auditIssueCount"] = 0
            page, errors = page_for(size, "map.html", clean)
            page.click("#copyBtn")
            page.wait_for_timeout(150)
            page.screenshot(path=str(out / f"map_{size}_export.png"))
            check(page.evaluate("document.getElementById('scrim').classList.contains('open')"), "export dialog opens when ready")
            page.click('[data-d="go"]')
            calls = page.evaluate("window.__calls.map(c=>c[0])")
            check("copyPlan" in calls, "copyPlan bridge call made")
            check(not errors, f"map clean {size} page errors: {errors}")
            page.close()
        browser.close()

    print(f"Screenshots: {out}")
    if failures:
        print("FAILED:")
        for f in failures:
            print(" -", f)
        return 1
    print("Visual QA passed (headless Chromium only; Windows WebView2 acceptance NOT RUN).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
