#!/usr/bin/env python3
# /// script
# dependencies = ["playwright>=1.50"]
# ///
"""Browser checks for /publications.html in a built site directory.

Usage: uv run --script browser_test.py SITE_OUT DATA_JSON [SHOTS_DIR]
Serves SITE_OUT on 127.0.0.1 with an OS-assigned port from a thread in this
process; the server stops when the script exits. Exits 1 on any failure.
"""
import functools
import json
import sys
import threading
import unicodedata
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def ascii_fold(s):
    s = unicodedata.normalize("NFD", s.replace("\u0142", "l").replace("\u0141", "L"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def main(site, data_path, shots=None):
    with open(data_path, encoding="utf-8") as fh:
        data = json.load(fh)
    total = len(data)
    default_n = sum(e["kind"] != "abstract" for e in data)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=site))
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{srv.server_address[1]}"
    url = origin + "/publications.html"
    failures = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" ({detail})"),
              flush=True)
        if not ok:
            failures.append(name)

    def local_only(route):
        # Keep analytics, remote fonts and other third-party resources offline.
        if route.request.url.startswith(origin + "/"):
            route.continue_()
        else:
            content_type = "application/javascript" if route.request.resource_type == "script" else "text/css"
            route.fulfill(status=200, content_type=content_type, body="")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(permissions=["clipboard-read", "clipboard-write"], reduced_motion="reduce")
            ctx.route("**/*", local_only)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

            def shown():
                return page.locator("li.pub:visible").count()

            page.goto(url)
            check("default hides abstracts", shown() == default_n, f"{shown()} != {default_n}")
            check("count text", page.inner_text("#pubs-count") == f"Showing {default_n} of {total}",
                  page.inner_text("#pubs-count"))
            enhanced = page.locator(".pubs-js").is_visible()
            check("filter controls enhanced", enhanced)
            check("copy buttons enhanced", page.locator("button.copy").count() == 2 * total)

            # A missing script is the expected RED baseline. Do not wait for
            # controls that are deliberately hidden until enhancement runs.
            if enhanced:
                page.check("#show-abstracts")
                check("toggle shows abstracts", shown() == total, f"{shown()} != {total}")
                check("toggle in URL", "abstracts=1" in page.url, page.url)
                page.uncheck("#show-abstracts")

                accented = next((a["family"] for e in data for a in e["authors"]
                                 if e["kind"] != "abstract" and ascii_fold(a["family"]) != a["family"].lower()), None)
                if accented:
                    page.fill("#pubs-q", ascii_fold(accented))
                    texts = page.locator("li.pub:visible").all_inner_texts()
                    check("accent-insensitive search", bool(texts) and all(
                        ascii_fold(accented) in ascii_fold(t) for t in texts), f"{len(texts)} hits")
                    page.fill("#pubs-q", "")

                theme = next((t for e in data if e["kind"] != "abstract" for t in e["themes"]), None)
                if theme:
                    expected = sum(e["kind"] != "abstract" and theme in e["themes"] for e in data)
                    chip = page.locator(f'.pubs-controls button[data-group="theme"][data-value="{theme}"]')
                    chip.click()
                    check("theme chip filters", shown() == expected, f"{shown()} != {expected}")
                    check("chip pressed", chip.get_attribute("aria-pressed") == "true")
                    page.reload()
                    check("URL state survives reload", shown() == expected, f"{shown()} != {expected}")
                    page.click("#pubs-clear")
                    check("clear resets", shown() == default_n and "?" not in page.url, page.url)

                themes = sorted({t for e in data for t in e["themes"]})[:2]
                tagged = next((e for e in data if e["kind"] != "abstract" and e["themes"] and e["tags"]), None)
                if themes:
                    page.goto(url + "?" + urlencode({"theme": ",".join(themes)}))
                    expected = {e["key"] for e in data if e["kind"] != "abstract" and set(themes).intersection(e["themes"])}
                    actual = set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)"))
                    check("themes combine with OR", actual == expected)
                if tagged:
                    filters = {"theme": tagged["themes"][0], "kind": tagged["kind"], "tag": tagged["tags"][0]}
                    page.goto(url + "?" + urlencode(filters))
                    expected = {e["key"] for e in data if e["kind"] == filters["kind"] and
                                filters["theme"] in e["themes"] and filters["tag"] in e["tags"]}
                    actual = set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)"))
                    check("filter groups combine with AND", actual == expected)

                page.goto(url + "?tag=no-such-tag&abstracts=yes&kind=&q=")
                check("garbage params give default view", shown() == default_n, f"{shown()}")
                before = len(errors)
                page.goto(url + "#%E0")
                check("malformed fragment gives default view", shown() == default_n)
                check("malformed fragment has no page error", len(errors) == before)

                abstract_key = next((e["key"] for e in data if e["kind"] == "abstract"), None)
                if abstract_key:
                    page.goto(url + "?q=no-matching-publication#" + abstract_key)
                    check("hash overrides conflicting filters", page.locator(f'[id="{abstract_key}"]').is_visible()
                          and page.input_value("#pubs-q") == "")
                    page.goto(url + "#" + abstract_key)
                    check("hash reveals hidden abstract", page.locator(f'[id="{abstract_key}"]').is_visible())
                    check("hash checks abstract box", page.is_checked("#show-abstracts"))
                    page.click("#pubs-clear")
                    check("clear removes fragment", "#" not in page.url, page.url)
                    page.reload()
                    check("clear survives reload", shown() == default_n and not page.is_checked("#show-abstracts"))
                    page.goto(url + "#" + abstract_key)
                    page.uncheck("#show-abstracts")
                    check("filter hiding target removes fragment", "#" not in page.url, page.url)

                page.goto(url)
                page.evaluate("history.pushState(null, '', '?abstracts=1'); window.dispatchEvent(new PopStateEvent('popstate'))")
                check("popstate restores abstracts", shown() == total and page.is_checked("#show-abstracts"))
                page.go_back()
                expect(page.locator("#show-abstracts")).not_to_be_checked()
                check("back restores default state", shown() == default_n)
                page.go_forward()
                expect(page.locator("#show-abstracts")).to_be_checked()
                check("forward restores abstracts", shown() == total)

                page.goto(url)
                first = page.locator("li.pub:visible").first
                first.locator("details.pub-cite summary").click()
                for label, selector in (("APA", ".cite-apa"), ("BibTeX", ".cite-bibtex")):
                    expected = first.locator(selector).text_content()
                    button = first.get_by_role("button", name="Copy " + label, exact=True)
                    button.click()
                    expect(first.get_by_role("button", name="Copied", exact=True)).to_have_count(1)
                    clip = page.evaluate("navigator.clipboard.readText()")
                    check("copy " + label, clip == expected, clip[:60])
                    expect(button).to_have_text("Copy " + label)

                page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true})")
                first.get_by_role("button", name="Copy APA", exact=True).click()
                check("copy fallback selects citation", page.evaluate("window.getSelection().toString()") ==
                      first.locator(".cite-apa").text_content())

                page.goto(url)
                kind_chip = page.locator('.pubs-controls button[data-group="kind"]').first
                kind_chip.focus()
                page.keyboard.press("Enter")
                check("keyboard toggles chip", kind_chip.get_attribute("aria-pressed") == "true")

            check("no console errors", not errors, "; ".join(errors[:3]))

            nojs_ctx = browser.new_context(java_script_enabled=False, reduced_motion="reduce")
            nojs_ctx.route("**/*", local_only)
            nojs = nojs_ctx.new_page()
            nojs.goto(url)
            check("no-JS: controls hidden", not nojs.locator(".pubs-js").is_visible())
            check("no-JS: abstracts hidden by CSS", nojs.locator("li.pub:visible").count() == default_n)
            nojs.check("#show-abstracts")
            check("no-JS: checkbox shows abstracts", nojs.locator("li.pub:visible").count() == total)
            nojs.locator("li.pub:visible details.pub-cite summary").first.focus()
            nojs.keyboard.press("Enter")
            check("no-JS: citation readable", nojs.locator("li.pub:visible .cite-bibtex").first.is_visible())

            if shots:
                Path(shots).mkdir(parents=True, exist_ok=True)
                for width in (375, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.goto(url)
                    check(f"no horizontal overflow at {width}px", page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"))
                    page.screenshot(path=f"{shots}/publications-{width}.png", animations="disabled")
                    key = page.locator("li.pub:visible").first.get_attribute("id")
                    page.goto(url + "#" + key)
                    target_top = page.locator(f'[id="{key}"]').bounding_box()["y"]
                    header = page.locator(".wrapper-masthead").bounding_box()
                    check(f"hash target below header at {width}px", target_top >= header["y"] + header["height"])
                    if width == 375:
                        cite = page.locator("li.pub:visible details.pub-cite").first
                        cite.locator("summary").click()
                        check("mobile citation wraps", page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth"))
                        cite.scroll_into_view_if_needed()
                        page.screenshot(path=f"{shots}/publications-375-citation.png", animations="disabled")
            browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join()
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
