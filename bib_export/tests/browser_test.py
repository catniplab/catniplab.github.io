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
from urllib.parse import parse_qs, urlencode, urlsplit

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

            def chip_counts_match(target_page, abstracts=False):
                chips = target_page.locator(".pubs-controls button.chip").evaluate_all("""els => els.map(el => ({
                    group: el.dataset.group, value: el.dataset.value, n: Number(el.querySelector('.n').textContent)
                }))""")
                return bool(chips) and all(c["n"] == sum(
                    (abstracts or e["kind"] != "abstract") and
                    (e["kind"] == c["value"] if c["group"] == "kind" else c["value"] in e[c["group"] + "s"])
                    for e in data) for c in chips)

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
                check("default chip counts match standalone filters", chip_counts_match(page))
                page.check("#show-abstracts")
                check("toggle shows abstracts", shown() == total, f"{shown()} != {total}")
                check("toggle in URL", "abstracts=1" in page.url, page.url)
                check("chip counts include abstracts when enabled", chip_counts_match(page, True))
                page.uncheck("#show-abstracts")
                check("chip counts return to publication scope", chip_counts_match(page))

                accented = sorted({ascii_fold(a["family"]) for e in data for a in e["authors"]
                                   if ascii_fold(a["family"]) != a["family"].lower()})
                for abstracts in (False, True):
                    page.set_checked("#show-abstracts", abstracts)
                    for query in accented:
                        page.fill("#pubs-q", query)
                        expected = {e["key"] for e in data if (abstracts or e["kind"] != "abstract") and
                                    any(query in ascii_fold(a["family"]) for a in e["authors"])}
                        actual = set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)"))
                        texts = page.locator("li.pub:visible").all_inner_texts()
                        check(f"accent search {query}, abstracts={abstracts}: all matching authors shown",
                              bool(expected) and expected <= actual and all(query in ascii_fold(t) for t in texts))
                page.click("#pubs-clear")

                page.clock.install()
                page.clock.pause_at(page.evaluate("Date.now()") + 1000)
                page.evaluate("""() => {
                    window.savedReplace = history.replaceState;
                    window.urlWrites = 0;
                    history.replaceState = function (...args) {
                        window.urlWrites++;
                        return window.savedReplace.apply(this, args);
                    };
                }""")
                page.fill("#pubs-q", "par")
                page.clock.fast_forward(200)
                page.fill("#pubs-q", "park")
                check("search filters before URL write", shown() == sum(
                    e["kind"] != "abstract" and any("park" in ascii_fold(a["family"]) for a in e["authors"])
                    for e in data))
                page.clock.fast_forward(299)
                check("search URL waits for pause", page.evaluate("window.urlWrites") == 0 and "?" not in page.url)
                page.clock.fast_forward(1)
                check("search URL writes once after 300ms", page.evaluate("window.urlWrites") == 1 and
                      parse_qs(urlsplit(page.url).query).get("q") == ["park"])
                page.fill("#pubs-q", "no-matching-publication")
                page.click("#pubs-clear")
                page.clock.fast_forward(300)
                check("clear cancels pending search URL", "?" not in page.url and shown() == default_n)
                page.evaluate("() => { history.replaceState = window.savedReplace; }")
                page.clock.resume()

                theme = next((t for e in data if e["kind"] != "abstract" for t in e["themes"]), None)
                if theme:
                    expected = sum(e["kind"] != "abstract" and theme in e["themes"] for e in data)
                    chip = page.locator(f'.pubs-controls button[data-group="theme"][data-value="{theme}"]')
                    chip.click()
                    check("theme chip filters", shown() == expected, f"{shown()} != {expected}")
                    check("chip pressed", chip.get_attribute("aria-pressed") == "true")
                    check("counts ignore other active filters", chip_counts_match(page))
                    year_sections = page.locator("section.pubs-year")
                    check("empty year headings hide under JS", any(
                        not section.is_visible() for section in year_sections.all()) and all(
                        section.locator("h2").is_visible() == (section.locator("li.pub:not([hidden])").count() > 0)
                        for section in year_sections.all()))
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
                    page.goto(url + "?" + urlencode({k: v + "," + v for k, v in filters.items()}))
                    check("duplicate URL filters are normalized",
                          parse_qs(urlsplit(page.url).query) == {k: [v] for k, v in filters.items()})
                    page.locator(f'.pubs-controls button[data-group="theme"][data-value="{filters["theme"]}"]').click()
                    check("duplicate filter deselects with one click", "theme" not in parse_qs(urlsplit(page.url).query))

                page.goto(url)
                more = page.locator("details.more-tags").first
                check("fixture exercises more tags", more.count() == 1 and more.locator("button.chip").count() > 0)
                more.locator("summary").click()
                extra_chip = more.locator("button.chip").first
                extra_tag = extra_chip.get_attribute("data-value")
                extra_chip.click()
                expected = {e["key"] for e in data if e["kind"] != "abstract" and extra_tag in e["tags"]}
                actual = set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)"))
                check("more tag filters entries", bool(expected) and actual == expected)
                page.click("#pubs-clear")
                zero_chip = page.locator('.pubs-controls button[data-group="tag"]').filter(
                    has=page.locator(".n", has_text="0")).first
                check("abstract-only tag remains available", zero_chip.count() == 1)
                zero_chip.click()
                check("abstract-only tag defaults to zero entries", shown() == 0)
                page.check("#show-abstracts")
                check("abstract-only tag works after toggle", shown() > 0 and chip_counts_match(page, True))

                page.goto(url + "?tag=no-such-tag&abstracts=yes&kind=&q=")
                check("garbage params give default view", shown() == default_n, f"{shown()}")
                before = len(errors)
                page.goto("about:blank")
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

                key = next(e["key"] for e in data if e["kind"] != "abstract")
                for throttled in (False, True):
                    page.goto(url + "#" + key)
                    target = page.locator(f'[id="{key}"]')
                    check(f"hash highlight, throttled={throttled}", target.evaluate(
                        "el => getComputedStyle(el).outlineStyle === 'solid'"))
                    if throttled:
                        page.evaluate("""() => {
                            history.replaceState = () => { throw new DOMException('Throttled', 'SecurityError'); };
                        }""")
                    page.click("#pubs-clear")
                    check(f"clear removes target outline, throttled={throttled}", target.evaluate(
                        "el => getComputedStyle(el).outlineStyle === 'none'"))
                    if throttled:
                        page.fill("#pubs-q", "no-matching-publication")
                        page.clock.fast_forward(300)
                        check("history SecurityError leaves filtering functional", shown() == 0)

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
            check("intro separates publications and abstracts", nojs.locator(".pubs-intro").text_content().startswith(
                f"{default_n} publications and {total - default_n} conference abstracts."))
            check("server-rendered chip counts match default scope", chip_counts_match(nojs))
            check("highlight metadata has no empty separators", all(
                all(part.strip() for part in text.split("\u00b7"))
                for text in nojs.locator(".pub-meta").all_text_contents()))
            check("venues have no leading whitespace", all(
                text == text.lstrip() for text in nojs.locator(".pub-venue").all_text_contents()))
            check("adjacent links have text separators", nojs.locator(".pub-links, .pub-labels").evaluate_all("""els =>
                els.every(el => Array.from(el.querySelectorAll('a')).slice(1).every(a =>
                    a.previousSibling.nodeType === Node.TEXT_NODE && /\\s/.test(a.previousSibling.textContent)))"""))
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
                    nojs.set_viewport_size({"width": width, "height": 900})
                    nojs.goto("about:blank")
                    nojs.goto(url + "#" + key)
                    target = nojs.locator(f'[id="{key}"]')
                    header = nojs.locator(".wrapper-masthead").bounding_box()
                    check(f"no-JS hash below header at {width}px", target.bounding_box()["y"] >= header["y"] + header["height"])
                    check(f"no-JS target outline at {width}px", target.evaluate(
                        "el => getComputedStyle(el).outlineStyle === 'solid'"))
                    if width == 375:
                        cite = page.locator("li.pub:visible details.pub-cite").first
                        cite.locator("summary").click()
                        check("mobile citation wraps", page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth"))
                        check("citation resets base shadow and margin", cite.locator("pre").evaluate("""el => {
                            const s = getComputedStyle(el);
                            return s.boxShadow === 'none' && parseFloat(s.marginTop) === parseFloat(s.fontSize) * 0.5;
                        }"""))
                        check("label chips suppress hover underline", page.locator(".pub-labels a.chip").first.evaluate(
                            "el => getComputedStyle(el, '::after').display === 'none'"))
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
