"""Playwright layout check of both windows at common CSS viewport sizes.

Fails on window scroll, wrapped bar rows, overlapping controls, ellipsis, or fonts
that did not load. Screenshots go to tests/screens/.
"""
import json
import runpy
import shutil
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREENS = HERE / "screens"
VIEWPORTS = [(1024, 720), (1280, 720), (1366, 768), (1536, 864), (1920, 1080), (2560, 1440)]
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


def _app():
    path = next(HERE.parent.glob("Music.Collection.Cleaner.v*.pyw"))
    return runpy.run_path(str(path), run_name="layout_test")


def _track(i, title, disc=1, number=None, remix=False, unique=False, gem=False):
    return dict(index=i, number=number or i + 1, disc=disc, title=title, duration="4:33", durationSeconds=273,
                groupId=100 + i, baseKey="t-%d" % i, family="remix" if remix else "", included=True,
                excluded=False, isRemix=remix, isLive=False, patternKind="", patternKey="", manualSkip=False,
                pendingIgnore=False, pendingRestore=False, unique=unique, isGem=gem, explicitState="unknown",
                replacementSource="", orphaned=False, exclusionReason="", audioMatchEditions=0,
                unverifiedEditions=0, coveredBy=[], coveredByAlternateVersion=False)


def map_fixture():
    red, rut, dz = "D:\\Music\\BT\\RED\\", "D:\\Music\\BT\\rutracker\\BT\\", "D:\\Music\\BT\\Deemix\\"
    rows = [
        ("album", "Emotional Technology", red + "BT - Emotional Technology (2003) {Black Hole CD 42} [Collector's Edition 2007] [FLAC]", "recycle", "REPLACE", "retained"),
        ("album", "Emotional Technology", rut + "[2003] BT - Emotional Technology [0 6700 30344 2 5] CD", "existing", "REMOVE", "duplicate"),
        ("album", "ESCM", rut + "[1997] BT - ESCM [3984-20065-2] CD", "existing", "KEEP", "retained"),
        ("album", "ESCM", dz + "1997-09-08 - ESCM [190295919184]", "recycle", "REMOVE", "duplicate"),
        ("album", "Metaversal", red + "[BHCD223] BT - Metaversal (2021) [CD FLAC]", "recycle", "ADD", "retained"),
        ("album", "The Secret Language of Trees", dz + "2023-07-11 - The Secret Language of Trees [742779548009]", "recycle", "ADD", "retained"),
        ("single", "Flaming June", rut + "[1997] BT - Flaming June [PERF145CD1] CD", "existing", "KEEP", "retained"),
        ("single", "Godspeed", dz + "2025-06-27 - Godspeed (Grum Remix) [8718525365918]", "recycle", "ADD", "retained"),
        ("single", "Walk into the Water", dz + "2023-05-26 - Walk into the Water [4056813545180]", "recycle", "REPLACE", "retained"),
        ("compilation", "10 Years In The Life", rut + "[2002] VA - 10 Years In The Life [R2 78118] 2CD", "existing", "KEEP", "retained"),
        ("compilation", "Laptop Symphony", rut + "[2012] VA - Laptop Symphony [BHCD863] WEB", "existing", "REMOVE", "duplicate"),
    ]
    nodes = []
    for i, (kind, title, path, root, action, state) in enumerate(rows):
        tracks = [_track(j, "Track %d of %s" % (j + 1, title)) for j in range(4)]
        if i == 0:
            tracks = ([_track(j, t, 1, unique=j == 0, gem=j == 0) for j, t in enumerate(
                ["The Meeting of a Hundred Yang", "Knowledge of Self", "Somnambulist (Simply Being Loved)", "Force of Gravity"])]
                + [_track(4 + j, t, 2, number=5 + j, remix=True) for j, t in enumerate(
                    ["Somnambulist (Mark Norman remix)", "Love in the Time of Thieves",
                     "Force of Gravity (Tiësto remix)", "Somnambulist (Sander Kleinenberg's Convertible mix)"])])
        nodes.append(dict(
            id=i + 1, name=path.rsplit("\\", 1)[1], title=title, rootKind=root, sourceRoot=path.rsplit("\\", 1)[0],
            path=path, kind=state, action=action, releaseType=kind, sourceMedium="CD", sourceRank=2 if root == "recycle" else 1,
            includedTracks=len(tracks), uniqueCount=1 if i == 0 else 0, reason="", displayGroupKey=title.lower(), displayGroupTitle=title,
            tracks=tracks, auditIssues=[], hasCue=i == 0, hasRipLog=i == 0, ripLogPercent=100 if i == 0 else None,
            upgradeFrom=[dict(id=2, name=nodes[0]["name"] if nodes else "", upgradeReason="Better CD rip log", sourceRank=1)] if i == 0 else [],
            forceKeep=False, manualRemoved=False, releaseBlocked=False))
    nodes[8]["upgradeFrom"] = [dict(id=7, name="x", upgradeReason="", sourceRank=1)]
    return dict(editable=True, dirty=False, applyEnabled=True, requiresFreshScan=False, standaloneMode=False,
                auditIssueCount=0, nodes=nodes, duplicateLinks=[], versionFamilies={},
                sourceRoots=dict(existing=rut, recycle=red),
                planCounts=dict(initial=dict(releases=11, tracks=44), result=dict(releases=8, tracks=32)))


MAIN_STATE = {
    "folders": [{"path": "D:\\Music\\BT\\rutracker\\BT", "star": True}, {"path": "D:\\Music\\BT\\RED", "star": False},
                {"path": "D:\\Music\\BT\\Deemix", "star": False}],
    "saveRemixes": True, "saveLive": False, "logging": False, "ioWorkers": "auto", "uiSizePercent": 100,
    "status": "Done", "progressPct": 100, "mapAvailable": True, "running": False,
    "activity": ["06:48  Done  23 releases · 21 changes",
                 "06:31  Match  Emotional Technology [0 6700 30344 2 5] CD ↔ [BHCD42] 2CD Collector's Edition"]
    + ["01:%02d  Scanned 190 releases in D:\\Music\\BT\\Deemix" % i for i in range(60)],
}

LAYOUT_PROBE = r"""async () => {
  await document.fonts.ready;
  const problems = [];
  const de = document.documentElement;
  if (de.scrollHeight > innerHeight + 1 || de.scrollWidth > innerWidth + 1 || document.body.scrollHeight > innerHeight + 1)
    problems.push("window scroll " + de.scrollWidth + "x" + de.scrollHeight);
  for (const face of [["Inter", "600 13px Inter"], ["JetBrains Mono", '13px "JetBrains Mono"']]) {
    const loaded = [...document.fonts].some(f => f.family.replace(/"/g, "") === face[0] && f.status === "loaded");
    if (!loaded || !document.fonts.check(face[1])) problems.push("font not loaded: " + face[0]);
  }
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0) || getComputedStyle(el).visibility === "hidden") return false;
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (getComputedStyle(p).overflowY === "visible") continue;
      const c = p.getBoundingClientRect();
      if (r.bottom <= c.top || r.top >= c.bottom || r.right <= c.left || r.left >= c.right) return false;
    }
    return true;
  };
  for (const row of document.querySelectorAll(".sep")) {
    if (!visible(row) || row.closest("#modalBackdrop")) continue;
    const kids = [...row.children].filter(visible).filter(el => !el.classList.contains("gap"));
    for (let i = 1; i < kids.length; i++) {
      const a = kids[i - 1].getBoundingClientRect(), b = kids[i].getBoundingClientRect();
      if (b.top >= a.bottom - 1 || a.top >= b.bottom - 1) problems.push("wrapped row: " + (row.id || row.className) + " at " + (kids[i].id || kids[i].textContent.trim().slice(0, 20)));
      if (a.right > b.left + 0.5) problems.push("overlap: " + (kids[i - 1].id || kids[i - 1].textContent.trim().slice(0, 20)) + " / " + (kids[i].id || kids[i].textContent.trim().slice(0, 20)));
    }
  }
  const controls = [...document.querySelectorAll("button,input,select,summary")].filter(visible).filter(el => !el.closest("#modalBackdrop,.trackActionGroup"));
  for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
    if (controls[i].contains(controls[j]) || controls[j].contains(controls[i])) continue;
    const a = controls[i].getBoundingClientRect(), b = controls[j].getBoundingClientRect();
    if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5)
      problems.push("overlapping controls: " + (controls[i].id || controls[i].textContent.trim().slice(0, 20)) + " / " + (controls[j].id || controls[j].textContent.trim().slice(0, 20)));
  }
  for (const el of document.querySelectorAll("body *")) {
    if (getComputedStyle(el).textOverflow === "ellipsis" && visible(el)) problems.push("ellipsis style: " + (el.id || el.className));
  }
  if (/…|\.\.\./.test(document.body.innerText)) problems.push("ellipsis text");
  // Text never smaller than 11px; key sizes per the type scale.
  for (const el of document.querySelectorAll("body *")) {
    if (!visible(el) || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size < 11 && !el.closest(".releaseFacts")) problems.push("text " + size + "px: " + (el.id || el.className || el.tagName));
  }
  const expect = [[".appName", 24], ["body", 14], [".changeChip", 11], [".btn", 14], [".stepLabel", 14]];
  for (const [sel, px] of expect) {
    const el = document.querySelector(sel);
    if (el && visible(el) && parseFloat(getComputedStyle(el).fontSize) !== px) problems.push(sel + " is " + getComputedStyle(el).fontSize + ", expected " + px + "px");
  }
  for (const id of ["analyzeBtn", "mapBtn", "reanalyzeBtn", "addFolder", "exportBtn"]) {
    const el = document.getElementById(id);
    if (el && visible(el) && !el.disabled) {
      const cs = getComputedStyle(el);
      if (cs.backgroundColor !== "rgb(43, 196, 212)" || cs.color !== "rgb(16, 16, 16)" || cs.opacity !== "1" || cs.paddingTop !== "5px" || cs.fontWeight !== "600" || cs.fontSize !== "14px") problems.push("#" + id + " is not the teal step button");
    }
  }
  for (const id of ["undoBtn", "personalPicks"]) {
    const el = document.getElementById(id);
    if (el && visible(el) && !el.disabled && (getComputedStyle(el).backgroundColor !== "rgba(0, 0, 0, 0)" || getComputedStyle(el).borderTopWidth !== "1px")) problems.push("#" + id + " is not outlined");
  }
  for (const el of document.querySelectorAll(".stepLabel")) {
    const cs = getComputedStyle(el);
    if (visible(el) && (cs.fontSize !== "14px" || cs.lineHeight !== "18px" || cs.fontWeight !== "600" || cs.color !== "rgb(242, 242, 242)")) problems.push("step label style: " + el.textContent);
  }
  if (/Replaced/i.test(document.body.innerText) || document.getElementById("changesReplacedBtn")) problems.push("Replaced is still shown");
  for (const el of document.querySelectorAll(".releaseFacts")) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    if (parseFloat(cs.fontSize) !== 10 || cs.fontWeight !== "500" || el.textContent.includes(" /") || el.textContent.includes("/ ")) problems.push("row markers are not 10px/500 without spaces around slashes");
    const row = el.closest(".releaseRow"), name = row.querySelector(".releaseName");
    if (Math.abs(el.getBoundingClientRect().right - row.getBoundingClientRect().right) > 0.5) problems.push("row markers are not right-aligned");
    const sym = row.querySelector(".rowMarker");
    if (sym) { const ink = sym.getBoundingClientRect(); if (ink.right > name.getBoundingClientRect().left - 1.5) problems.push("status symbol touches the name"); }
  }
  const xs = new Set([...document.querySelectorAll(".releaseRow .releaseName")].filter(visible).map(e => Math.round(e.getBoundingClientRect().left * 2) / 2));
  if (document.getElementById("columns") && xs.size > 3) problems.push("folder names start at " + xs.size + " different x positions");
  for (const el of document.querySelectorAll(".btn:not(.tagBtn),input.field,select,.btn.primary")) {
    if (visible(el) && !el.closest("#modalBackdrop") && Math.abs(el.getBoundingClientRect().height - 24) > 0.5) problems.push("control height " + el.getBoundingClientRect().height.toFixed(1) + "px (expected 24): " + (el.id || el.className));
  }
  for (const el of document.querySelectorAll(".changeChip,.tagBtn")) {
    if (visible(el) && Math.abs(el.getBoundingClientRect().height - 18) > 0.5) problems.push("chip height " + el.getBoundingClientRect().height.toFixed(1) + "px (expected 18): " + (el.id || el.className));
  }
  const rowHeights = new Set([...document.querySelectorAll(".track,.releaseRow")].filter(visible).filter(e => e.getBoundingClientRect().height < 30).map(e => e.getBoundingClientRect().height.toFixed(1)));
  if (rowHeights.size > 1) problems.push("single-line rows have different heights: " + [...rowHeights].join(", "));
  const selectGroup = document.getElementById("albumGroupSelect");
  if (selectGroup && visible(selectGroup) && getComputedStyle(selectGroup).borderTopWidth !== "1px") problems.push("Group control is not outlined");
  const secondary = document.querySelector(".track .dur,.track .note");
  if (secondary && visible(secondary) && ![12, 14].includes(parseFloat(getComputedStyle(secondary).fontSize))) problems.push("secondary text size " + getComputedStyle(secondary).fontSize);
  // Spacing: neighbours and container edges are 4, 8 or 12 px apart.
  const ok = v => [4, 8, 12].some(x => Math.abs(v - x) <= 0.5);
  const name = el => (el.id ? "#" + el.id : el.tagName.toLowerCase() + (typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\s+/).join(".") : ""));
  const leaves = [...document.querySelectorAll("button,input,select,summary,label,.stepLabel,.appName,.versionTag,.buildState,.sectionLabel,.releaseColumnHeader,.releaseGroupTitle,.releaseName,.discHead,#releaseName,#releasePath,.field,.track .titleText,.track .dur,.track .num,.track .note,#progressText,#progressPercent")]
    .filter(visible).filter(el => !el.closest("#modalBackdrop,.trackActionGroup,#auditBanner") && !(el.parentElement && el.parentElement.closest("button,label,summary")));
  for (const el of leaves) {
    const r = el.getBoundingClientRect();
    const sibs = [...el.parentElement.children].filter(x => x !== el && visible(x) && !x.classList.contains("gap"));
    const right = sibs.map(x => x.getBoundingClientRect()).filter(b => b.left >= r.right - 0.5 && b.top < r.bottom && r.top < b.bottom);
    let next = el.nextElementSibling;
    while (next && !visible(next) && !next.classList.contains("gap")) next = next.nextElementSibling;
    const spread = getComputedStyle(el.parentElement).justifyContent === "space-between";
    if (right.length && !spread && !(next && next.classList.contains("gap"))) {
      const d = Math.min(...right.map(b => b.left - r.right));
      if (!ok(d)) problems.push("spacing " + d.toFixed(1) + "px to neighbour: " + name(el));
    }
    // Walk up to the nearest padded/bordered box; stop early if something sits to the left on the same line.
    let box = el.parentElement, leftNeighbour = false, level = el, lineEdge = null;
    while (box && box !== document.body) {
      // A divider line centred in the gap to the left counts as the container edge.
      if (getComputedStyle(level, "::before").content !== "none" && getComputedStyle(level, "::before").width === "1px") {
        lineEdge = level.getBoundingClientRect().left - 4; break;
      }
      const rowFlow = /^(flex|inline-flex)$/.test(getComputedStyle(box).display) && getComputedStyle(box).flexDirection === "row";
      leftNeighbour = [...box.children].some(x => x !== level && visible(x) && (() => {
        const b = x.getBoundingClientRect();
        const sameLine = b.right <= r.left + 0.5 && (rowFlow || (b.top < r.bottom && r.top < b.bottom));
        const alignedAbove = b.bottom <= r.top + 0.5 && Math.abs(b.left - r.left) <= 0.5;  // stacked under an aligned sibling
        return sameLine || alignedAbove; })());
      const cs = getComputedStyle(box);
      if (leftNeighbour || parseFloat(cs.paddingLeft) || parseFloat(cs.borderLeftWidth) || parseFloat(cs.marginLeft) || box.matches(".releaseRows,#mainContent")) break;
      level = box; box = box.parentElement;
    }
    if (!leftNeighbour) {
      let edge = 0;
      if (lineEdge !== null) edge = lineEdge;
      else if (box && box !== document.body) {
        const cs = getComputedStyle(box);
        // An indent made with margin counts from where the margin starts.
        edge = box.getBoundingClientRect().left + (parseFloat(cs.borderLeftWidth) || 0)
          - (parseFloat(cs.paddingLeft) || parseFloat(cs.borderLeftWidth) ? 0 : parseFloat(cs.marginLeft) || 0);
      }
      const d = r.left - edge;
      if (!ok(d)) problems.push("spacing " + d.toFixed(1) + "px to container edge: " + name(el) + " in " + (box && box !== document.body ? name(box) : "window"));
    }
  }
  return [...new Set(problems)];
}"""


@unittest.skipIf(sync_playwright is None or CHROME is None, "Playwright or Chrome not installed")
class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = _app()
        cls.main_html = app["_webview_main_html"]()
        cls.map_html = app["_webview_release_map_html"]()
        SCREENS.mkdir(exist_ok=True)

    def _open(self, browser, size, html, init=""):
        page = browser.new_context(viewport=dict(width=size[0], height=size[1])).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        if init:
            page.add_init_script(init)
        page.route("http://mcc.test/**", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html))
        page.goto("http://mcc.test/x")
        page.wait_for_timeout(400)
        return page, errors

    def _check(self, page, errors, name, size):
        page.screenshot(path=str(SCREENS / ("%s-%dx%d.png" % (name, size[0], size[1]))))
        problems = page.evaluate(LAYOUT_PROBE) + ["page error: " + e for e in errors]
        self.assertEqual(problems, [], "%s at %dx%d" % (name, size[0], size[1]))

    def test_both_windows_fit_every_viewport(self):
        map_init = ("window.__fixture=" + json.dumps(map_fixture(), ensure_ascii=False) + ";window.pywebview={api:{"
                    "getState:()=>JSON.stringify(window.__fixture),"
                    "getOrganizer:()=>JSON.stringify({format:'ALAC',enable_encoding:true,enable_checker:true,enable_splitting:false})}};")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            for size in VIEWPORTS:
                with self.subTest(size=size):
                    page, errors = self._open(browser, size, self.main_html)
                    page.evaluate("s=>renderState(s)", MAIN_STATE)
                    page.wait_for_timeout(300)
                    self._check(page, errors, "main", size)
                    page, errors = self._open(browser, size, self.map_html, map_init)
                    page.wait_for_selector(".releaseRow")
                    self._check(page, errors, "map-changes", size)
                    page.click("#fullViewBtn")
                    page.click('.releaseRow[data-id="1"]')
                    page.wait_for_selector("#details.open")
                    self._check(page, errors, "map-full", size)
            browser.close()

    def test_unscanned_map_offers_rescan_and_main_window_labels(self):
        map_init = ("window.__fixture=" + json.dumps(dict(map_fixture(), editable=False), ensure_ascii=False) + ";window.__calls=[];window.pywebview={api:{"
                    "getState:()=>JSON.stringify(window.__fixture),requestScan:()=>window.__calls.push('scan'),"
                    "getOrganizer:()=>JSON.stringify({format:'ALAC',enable_encoding:true,enable_checker:true,enable_splitting:false})}};")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            page, errors = self._open(browser, VIEWPORTS[0], self.map_html, map_init)
            page.wait_for_selector(".releaseRow")
            self.assertFalse(page.is_disabled("#reanalyzeBtn"))
            self.assertTrue(page.is_visible("#scanNote"))
            page.click("#reanalyzeBtn")
            self.assertEqual(page.evaluate("window.__calls"), ["scan"])
            page, errors = self._open(browser, VIEWPORTS[0], self.main_html)
            page.evaluate("s=>renderState(s)", dict(MAIN_STATE, mapOpen=True))
            self.assertEqual(page.eval_on_selector_all(".roleLabel", "e=>e.map(x=>x.textContent)")[1:], ["Folder 2", "Folder 3"])
            self.assertFalse(page.is_disabled("#openLogs"))
            self.assertTrue(page.is_visible("#activity") and page.is_visible("#ioWorkers"))
            self.assertEqual(page.eval_on_selector_all("#keepOptions .check", "e=>e.map(x=>x.textContent)"),
                             ["Keep Remixes", "Keep Live recordings"])
            keep = page.eval_on_selector("#keepOptions", "e=>{const r=e.getBoundingClientRect();return r.left+r.width/2}")
            row = page.eval_on_selector("#folderOptions", "e=>{const r=e.getBoundingClientRect();return r.left+r.width/2}")
            self.assertAlmostEqual(keep, row, delta=1)
            browser.close()


if __name__ == "__main__":
    unittest.main()
