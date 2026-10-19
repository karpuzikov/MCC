"""Developer-only MCC Visual QA Gate: browser rendering and interaction fixtures.
Run: py -m pip install playwright; py -m playwright install chromium
     py tests/visual_qa.py
This does NOT replace actual Windows WebView2 acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import traceback


def fixture():
    root = r"C:\!deemix Music\Noisia\Noisia ALAC"
    def track(i, title, saved="", excluded=True):
        return dict(index=i, number=i+1, title=title, duration="4:33",
                    durationSeconds=273, groupId=100+i, baseKey="test-"+str(i),
                    family="remix", included=not excluded, excluded=excluded,
                    isRemix=excluded, isLive=False, patternKind=saved,
                    patternKey="noisia remix" if saved else "", manualSkip=False,
                    pendingIgnore=False, pendingRestore=False, unique=not excluded,
                    isGem=False, explicitState="unknown", replacementSource="",
                    orphaned=False, exclusionReason="Remix" if excluded else "",
                    audioMatchEditions=0, unverifiedEditions=0, coveredBy=[],
                    coveredByAlternateVersion=False)
    tracks = [
        track(0, "Voodoo (Noisia's 'Outer Edges' Remix)", "remix"),
        track(1, "Tommy's Theme (Noisia's 'Outer Edges' Remix) - " +
              "Extremely Long Extended Festival Mix with Another Descriptor " * 2),
        track(2, "Dead Limit (Noisia's 'Outer Edges' Remix)"),
        track(3, "Diplodocus (Noisia's 'Outer Edges' Remix)", excluded=False),
        track(4, "Surfaceless (Noisia's 'Outer Edges' Remix)", "skip"),
    ]
    original = dict(id=1, name="2017-06-09 - Outer Edges (Noisia Remixes) [VSN030]",
                    title="Outer Edges (Noisia Remixes)", rootKind="existing",
                    sourceRoot=root, path=root+r"\2017-06-09 - Outer Edges (Noisia Remixes) [VSN030]",
                    kind="duplicate", action="REMOVE", releaseType="album",
                    sourceMedium="WEB", sourceRank=1, includedTracks=1,
                    uniqueCount=0, reason="Duplicate edition",
                    displayGroupKey="noisia-remixes", tracks=tracks, auditIssues=[],
                    upgradeFrom=[], forceKeep=False, manualRemoved=False, releaseBlocked=False)
    other = dict(original, id=2, name="2018-01-01 - Another Album [ABC123]",
                 title="Another Album", path=root+r"\2018-01-01 - Another Album [ABC123]",
                 displayGroupKey="another-album", action="KEEP", kind="retained",
                 tracks=[track(10, "Unrelated track", excluded=False)])
    return dict(editable=True, dirty=False, applyEnabled=False,
                requiresFreshScan=False, standaloneMode=False, auditIssueCount=0,
                nodes=[original, other], duplicateLinks=[],
                versionFamilies={"test-2": [dict(groupId=333, releaseId=2,
                    family="version", title="Dead Limit (Alternate Version)",
                    duration="4:21", durationSeconds=261, available=True,
                    retained=False, releaseNames=["Another Album"])]},
                sourceRoots=dict(existing=root, recycle=r"C:\!deemix Music\Noisia\deemix"),
                planCounts=dict(initial=dict(releases=2, tracks=6),
                                result=dict(releases=1, tracks=1)),
                result=dict(show=False), defaultExportDestination="")


GEOMETRY = r"""() => {
 const faults=[], panel=document.querySelector('#details');
 const rect=e=>e.getBoundingClientRect();
 if(!panel||!panel.classList.contains('open'))return ['Details did not open'];
 const p=rect(panel);
 if(p.left<-1||p.right>innerWidth+1)faults.push('Details outside viewport');
 for(const [i,row] of [...document.querySelectorAll('#tracks .track')].entries()){
   const cols=['.num','.titleCell','.dur','.versionsCell','.status','.trackActionGroup']
     .map(x=>row.querySelector(x)).filter(Boolean);
   for(let j=1;j<cols.length;j++){
     if(rect(cols[j-1]).right>rect(cols[j]).left+1.5)
       faults.push('Row '+i+': overlapping columns');
   }
   const r=rect(row);
   if(r.left<p.left-1||r.right>p.right+1)faults.push('Row '+i+': clipped row');
   const status=row.querySelector('.status');
   for(const btn of row.querySelectorAll('button')){
     const style=getComputedStyle(btn);
     if(style.visibility==='hidden'||style.display==='none')continue;
     const b=rect(btn);
     if(b.width<20||b.height<20)faults.push('Row '+i+': tiny button');
     if(b.left<r.left-1||b.right>r.right+1||b.top<r.top-1||b.bottom>r.bottom+1)
       faults.push('Row '+i+': button outside row');
     if(status&&btn.closest('.trackActionGroup')){
       const a=rect(status);
       if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1.5 &&
          Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1.5)
         faults.push('Row '+i+': action covers status');
     }
   }
   const badge=row.querySelector('.patternBadge'),title=row.querySelector('.titleText');
   if(badge&&title){
     const a=rect(title),b=rect(badge);
     if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1.5&&
        Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1.5)
       faults.push('Row '+i+': saved badge covers title');
   }
 }
 if(document.documentElement.scrollWidth>innerWidth+2)faults.push('Horizontal page overflow');
 return faults;
}"""


def run(app, output, browser_kind):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("Install test dependency: py -m pip install playwright")
    if not app.is_file():
        raise SystemExit("Missing source: "+str(app))
    html=runpy.run_path(str(app),run_name="mcc_visual_qa")["_webview_release_map_html"]()
    if html.count("</script>")!=1:
        raise RuntimeError("MCC Release Map must contain exactly one module script")
    html=html.replace("</script>",
        "window.__visualQa={receiveState,openDetails,getNode};\n</script>")
    output.mkdir(parents=True,exist_ok=True)
    fixture_file=output/"release-map-fixture.html"
    fixture_file.write_text(html,encoding="utf-8")
    data=fixture()
    report=dict(app=str(app),browser=browser_kind,
                native_windows_webview2="NOT RUN",cases=[],errors=[],screenshots=[])
    cases=[("normal",1486,913,1),("minimum",1050,680,1),
           ("large",1700,1000,1),("zoom125",1486,913,1.25)]
    try:
        with sync_playwright() as pw:
            args=dict(headless=True)
            if browser_kind=="edge":
                args["channel"]="msedge"
            elif browser_kind=="system":
                executable=shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
                if not executable:
                    raise RuntimeError("No system Chromium; install Playwright Chromium")
                args["executable_path"]=executable
            browser=pw.chromium.launch(**args)
            try:
                for name,width,height,zoom in cases:
                    context=browser.new_context(viewport=dict(width=width,height=height))
                    page=context.new_page()
                    js_errors=[]
                    page.on("pageerror",lambda e:js_errors.append(str(e)))
                    page.on("console",lambda m:js_errors.append(
                        "console: "+m.text) if m.type=="error" else None)
                    init="window.__qaFixture="+json.dumps(data,ensure_ascii=False)+";"+r"""
window.__qaEvents=[];window.pywebview={api:{
 getState:()=>JSON.stringify(window.__qaFixture),
 markTrackPattern:(index,kind)=>{
   window.__qaEvents.push({index,kind});
   return JSON.stringify({kind:'patternToggle',tracks:[],requiresFreshScan:true});
 }
}};"""
                    page.add_init_script(init)
                    # Real <script type="module"> is blocked on file:// in
                    # Chromium by origin/CORS policy. Fulfill a same-origin HTTP
                    # navigation locally, without making any external requests.
                    # This tests the actual module, not a downgraded classic script.
                    page.route("http://mcc-visual.test/**", lambda route: route.fulfill(
                        status=200, content_type="text/html; charset=utf-8", body=html))
                    page.goto("http://mcc-visual.test/release-map", wait_until="load")
                    try:
                        page.wait_for_function(
                            "!!window.__visualQa && !!document.querySelector('.releaseRow')",
                            timeout=15000)
                    except Exception:
                        # Keep actionable diagnostic artifacts even if init fails.
                        screenshot=name+"-initialization-error.png"
                        page.screenshot(path=str(output/screenshot), full_page=True)
                        report["screenshots"].append(screenshot)
                        report["errors"].append(
                            name+": startup failed: "+("; ".join(js_errors) or
                            page.evaluate("document.body.innerText.slice(0,800)")))
                        raise
                    if zoom!=1:
                        page.evaluate("(z)=>document.body.style.zoom=String(z)",zoom)
                    page.locator('.releaseRow[data-id="1"]').click()
                    page.locator('#tracks .track').first.hover()
                    screenshot=name+"-hover.png"
                    page.screenshot(path=str(output/screenshot))
                    report["screenshots"].append(screenshot)
                    problems=page.evaluate(GEOMETRY)
                    if page.locator("#copyPathBtn").count():
                        problems.append("Duplicate Copy path button")
                    if not page.locator(".trackActionGroup").first.is_visible():
                        problems.append("Hover actions inaccessible")
                    if page.locator('.track').first.locator('.patternMark[data-kind="remix"]').count():
                        problems.append("Saved Remix duplicated in actions")
                    group=page.locator(".albumGroupActions")
                    if group.count():
                        if group.evaluate("(x)=>x.open"):
                            problems.append("Album group not initially collapsed")
                        group.locator("summary").click()
                        if not group.evaluate("(x)=>x.open"):
                            problems.append("Album group cannot open")
                        screenshot=name+"-album-group.png"
                        page.screenshot(path=str(output/screenshot))
                        report["screenshots"].append(screenshot)
                        problems.extend(page.evaluate(GEOMETRY))
                    page.locator("#releasePath").focus()
                    page.keyboard.press("Control+A")
                    if page.evaluate("window.getSelection().toString()")!=data["nodes"][0]["path"]:
                        problems.append("Ctrl+A path selection failed")
                    badge=page.locator(".track").first.locator(".patternBadge")
                    badge.focus()
                    if not page.locator(".trackActionGroup").first.is_visible():
                        problems.append("Actions hidden from keyboard focus")
                    badge.press("Enter")
                    page.wait_for_function("window.__qaEvents.some(x=>x.kind==='keep')")
                    page.keyboard.press("Escape")
                    if page.locator("#details").evaluate("(x)=>x.classList.contains('open')"):
                        problems.append("Escape did not close details")
                    problems += ["JavaScript: "+e for e in js_errors]
                    report["cases"].append(dict(name=name,viewport=[width,height],css_zoom=zoom,
                        status="FAIL" if problems else "PASS",issues=problems))
                    report["errors"] += [name+": "+error for error in problems]
                    context.close()
            finally:
                browser.close()
    except Exception as exc:
        report["errors"].append(type(exc).__name__+": "+str(exc))
        report["traceback"]=traceback.format_exc()[-4000:]
    finally:
        location=output/"report.json"
        location.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print("Browser Visual QA: "+("FAIL" if report["errors"] else "PASS")+" | "+str(location))
        for error in report["errors"]:
            print("FAIL: "+error)
        print("Native Windows WebView2: NOT RUN")
    return int(bool(report["errors"]))


if __name__=="__main__":
    p=argparse.ArgumentParser(description="MCC headless visual regression gate")
    # Always test the latest versioned one-file app in the checkout. Keeping a
    # hard-coded old default silently tests the wrong UI after version bumps.
    root=Path(__file__).resolve().parents[1]
    candidates=list(root.glob("Music Collection Cleaner v*.pyw"))
    if not candidates:
        raise SystemExit("No Music Collection Cleaner versioned .pyw in "+str(root))
    latest=max(candidates,key=lambda file: tuple(
        int(part) for part in file.stem.rsplit(" v",1)[-1].split(".")
    ))
    p.add_argument("--app",type=Path,default=latest)
    p.add_argument("--browser",choices=["edge","chromium","system"],
        default="edge" if os.name=="nt" else "system")
    p.add_argument("--output",type=Path,default=Path.home()/"Documents"/"Karpuzikov Tools"/
        "Music Collection Cleaner"/"testing"/("visual-qa-"+datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")))
    args=p.parse_args()
    sys.exit(run(args.app.resolve(),args.output.resolve(),args.browser))
