"""Native Windows WebView2 smoke: real host, embedded map and screenshot.

This runs on a GitHub-hosted Windows desktop; it does not touch user music.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

import webview

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / os.environ.get("MCC_TEST_SOURCE", "Music.Collection.Cleaner.v0.05.174.pyw")
loader = importlib.machinery.SourceFileLoader("mcc_native_ui", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
mcc = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = mcc
loader.exec_module(mcc)

class Bridge:
    def getState(self):
        return json.dumps({
            "folders": [], "saveRemixes": False, "saveLive": False,
            "logging": False, "ioWorkers": "auto", "uiSizePercent": 100,
            "status": "Ready", "progressPct": 0, "activity": [],
            "mapAvailable": True, "running": False, "mapOpen": True,
        })

    def getOrganizer(self):
        return json.dumps({"format": "ALAC", "enable_encoding": False})

    def mapCall(self, name, args_json="[]"):
        if name == "getState":
            return json.dumps({
                "editable": False, "dirty": False, "nodes": [],
                "standaloneMode": True, "versionFamilies": {},
                "result": {"show": False}, "sourceRoots": {},
                "applyEnabled": False,
            })
        if name == "getOrganizer":
            return self.getOrganizer()
        return "{}"


def main():
    result = {"ok": False, "error": None}
    window = webview.create_window(
        "MCC 0.5.174 Windows UI smoke", html=mcc._webview_main_html(),
        width=1440, height=900, min_size=(1024, 720),
        background_color=mcc.DESIGN_CANVAS_HEX,
        js_api=Bridge(),
    )

    def inspect():
        try:
            # Wait for WebView2 DOM, not a fixed animation frame.
            for _ in range(60):
                try:
                    is_ready = window.evaluate_js(
                        "document.readyState==='complete' && !!document.getElementById('mapBtn')")
                    if is_ready:
                        break
                except Exception:
                    pass
                time.sleep(.3)
            else:
                raise RuntimeError("Main WebView2 DOM did not become ready.")
            window.evaluate_js("showMapInWindow(" +
                               json.dumps(mcc._webview_release_map_html()) + ")")
            for _ in range(60):
                try:
                    ready = window.evaluate_js(
                        """(() => {const frame=document.getElementById('mapFrame');
                           return frame && !frame.parentNode.hidden &&
                           !!frame.contentDocument &&
                           !!frame.contentDocument.getElementById('fullViewBtn');})()""")
                    if ready:
                        break
                except Exception:
                    pass
                time.sleep(.3)
            else:
                raise RuntimeError("Embedded map did not render in real WebView2.")
            window.evaluate_js(
                """state={running:true,status:'Writing to C:\\\\MCC-TEST\\\\Example',
                      copyDestination:'C:\\\\MCC-TEST'}; updateCopyBar();""")
            ok = window.evaluate_js(
                """(() => ({
                    map: !!document.getElementById('mapFrame').contentDocument.getElementById('fullViewBtn'),
                    copyOpen: document.getElementById('copyOpen').offsetParent !== null,
                    output: document.getElementById('copyPath').textContent,
                    mapWindowCount: 1
                }))()""")
            if not isinstance(ok, dict) or not ok.get("map") or not ok.get("copyOpen"):
                raise RuntimeError("WebView2 map or Open destination control failed: " + repr(ok))
            output = ok.get("output") or ""
            if "Example" not in output:
                raise RuntimeError("Actual output path is not displayed: " + str(output))
            try:
                from PIL import ImageGrab
                shot = ROOT / "tests" / "screens" / "native-win-v174.png"
                shot.parent.mkdir(parents=True, exist_ok=True)
                ImageGrab.grab().save(str(shot))
            except Exception as error:
                print("SCREENSHOT NOT AVAILABLE:", error, flush=True)
            print("NATIVE WEBVIEW2 PASS:", ok, flush=True)
            result["ok"] = True
        except BaseException:
            result["error"] = traceback.format_exc()
            print("NATIVE WEBVIEW2 FAIL:\n" + result["error"], flush=True)
        finally:
            window.destroy()

    window.events.shown += lambda: threading.Thread(target=inspect, daemon=True).start()
    webview.start(gui="edgechromium", debug=False, private_mode=True)
    if not result["ok"]:
        raise RuntimeError(result["error"] or "WebView2 smoke test did not complete")


if __name__ == "__main__":
    main()
