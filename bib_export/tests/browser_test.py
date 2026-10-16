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
import re
import sys
import threading
import unicodedata
from html import unescape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import median
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

            def select_view(target_page, abstracts):
                option = "show-abstracts" if abstracts else "show-papers"
                target_page.locator(f'label[for="{option}"]').click()

            def chip_counts_match(target_page, abstracts=False):
                chips = target_page.locator(".pubs-controls button.chip").evaluate_all("""els => els.map(el => ({
                    group: el.dataset.group, value: el.dataset.value, n: Number(el.querySelector('.n').textContent)
                }))""")
                return bool(chips) and all(c["n"] == sum(
                    (abstracts or e["kind"] != "abstract") and
                    (e["refereed"] if c["group"] == "review" else
                     e["kind"] == c["value"] if c["group"] == "kind" else c["value"] in e[c["group"] + "s"])
                    for e in data) for c in chips)

            # journals are always refereed, so only the bar marks them; the label is for the rest
            def labeled_review(e):
                return e["refereed"] and e["kind"] != "journal"

            def markers_match(target_page):
                entries = target_page.locator("li.pub, .pubs-highlights li").evaluate_all("""els => {
                    const primary = getComputedStyle(document.querySelector('.pubs-view input:checked + label')).backgroundColor;
                    return els.map(el => ({
                        key: el.id || el.querySelector('a').getAttribute('href').slice(1),
                        flag: el.dataset.refereed,
                        labels: Array.from(el.querySelectorAll('.pub-review')).map(l => l.textContent),
                        bar: getComputedStyle(el).borderLeftColor === primary && parseFloat(getComputedStyle(el).borderLeftWidth) > 0
                    }));
                }""")
                expected = {e["key"]: e["refereed"] for e in data}
                labeled = {e["key"] for e in data if labeled_review(e)}
                return len(entries) == total + sum(e["selected"] for e in data) and all(
                    e["flag"] == str(expected[e["key"]]).lower() and e["bar"] == expected[e["key"]] and
                    e["labels"] == (["peer-reviewed"] if e["key"] in labeled else []) for e in entries)

            page.goto(url)
            check("default hides abstracts", shown() == default_n, f"{shown()} != {default_n}")
            check("initial Papers radio and count", page.get_by_role(
                "radio", name=f"Papers ({default_n})", exact=True).is_checked())
            check("All radio has total count", page.get_by_role(
                "radio", name=f"All, with abstracts ({total})", exact=True).count() == 1)
            check("count text", page.inner_text("#pubs-count") == f"{default_n} papers",
                  page.inner_text("#pubs-count"))
            enhanced = page.locator(".pubs-js").first.is_visible()
            check("filter controls enhanced", enhanced)
            check("copy buttons enhanced", page.locator("button.copy").count() == 2 * total)

            # A missing script is the expected RED baseline. Do not wait for
            # controls that are deliberately hidden until enhancement runs.
            if enhanced:
                check("topic facets collapsed initially", not page.locator(".pubs-topics").evaluate("el => el.open"))
                check("Search retains its accessible name", page.get_by_role("searchbox", name="Search", exact=True).count() == 1)
                check("Search label is visually hidden", page.locator(".pubs-search > span").evaluate(
                    "el => getComputedStyle(el).clipPath === 'inset(50%)'"))
                check("Review has its own visible labelled group", page.get_by_role("group", name="Review", exact=True)
                      .locator('.chip-group-name').inner_text() == "Review" and
                      page.get_by_role("group", name="Kind", exact=True).locator('[data-group="review"]').count() == 0)
                full_names = {label["id"]: label["name"] for e in data for label in e["labels"] if label["group"] == "theme"}
                check("theme chip titles retain full names", all(
                    chip.get_attribute("title") == full_names[chip.get_attribute("data-value")]
                    for chip in page.locator('button[data-group="theme"]').all()))
                check("Highlights visible on landing", page.locator(".pubs-highlights").is_visible())
                check("Papers and Highlights markers match JSON", markers_match(page))
                check("default chip counts match standalone filters", chip_counts_match(page))
                check("Show all hidden without filtering", not page.locator("#pubs-show-all").is_visible())
                check("Clear hidden in unfiltered Papers", not page.locator("#pubs-clear").is_visible())
                select_view(page, True)
                check("one click on All shows every entry", shown() == total, f"{shown()} != {total}")
                check("unfiltered All count and Clear state", page.inner_text("#pubs-count") == f"{total} entries" and
                      not page.locator("#pubs-clear").is_visible())
                check("All view in URL", parse_qs(urlsplit(page.url).query) == {"abstracts": ["1"]}, page.url)
                check("chip counts include abstracts when enabled", chip_counts_match(page, True))
                check("All and Highlights markers match JSON", markers_match(page))
                check("Highlights visible in unfiltered All view", page.locator(".pubs-highlights").is_visible())
                select_view(page, False)
                check("chip counts return to publication scope", chip_counts_match(page))
                review_chip = page.locator('button[data-group="review"][data-value="refereed"]')
                for abstracts in (False, True):
                    select_view(page, abstracts)
                    expected = {e["key"] for e in data if e["refereed"] and (abstracts or e["kind"] != "abstract")}
                    check(f"Peer-reviewed standalone count, All={abstracts}",
                          review_chip.locator(".n").text_content() == str(len(expected)))
                    review_chip.click()
                    denominator, noun = (total, "entries") if abstracts else (default_n, "papers")
                    check(f"filtered count uses current view, All={abstracts}", page.inner_text("#pubs-count") ==
                          f"{len(expected)} of {denominator} {noun}" and page.locator("#pubs-clear").is_visible())
                    check(f"Highlights hide with review filter, All={abstracts}", not page.locator(".pubs-highlights").is_visible())
                    check(f"Peer-reviewed filter matches JSON, All={abstracts}",
                          set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)")) == expected)
                    check(f"review=refereed in URL, All={abstracts}", parse_qs(urlsplit(page.url).query).get("review") == ["refereed"])
                    page.reload()
                    check(f"review URL round trip, All={abstracts}", review_chip.get_attribute("aria-pressed") == "true" and
                          set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)")) == expected)
                    page.click("#pubs-clear")
                    check(f"Clear removes review filter, All={abstracts}", "review" not in parse_qs(urlsplit(page.url).query))
                    check(f"Clear hides and restores unfiltered count, All={abstracts}",
                          not page.locator("#pubs-clear").is_visible() and
                          page.inner_text("#pubs-count") == f"{denominator} {noun}")
                    check(f"Clear returns focus to Search, All={abstracts}", page.locator("#pubs-q").evaluate(
                        "el => el === document.activeElement"))
                select_view(page, False)
                page.locator("#show-papers").focus()
                page.keyboard.press("ArrowRight")
                check("keyboard right arrow selects All", page.is_checked("#show-abstracts") and shown() == total)
                page.keyboard.press("ArrowLeft")
                check("keyboard left arrow selects Papers", page.is_checked("#show-papers") and shown() == default_n)

                accented = sorted({ascii_fold(a["family"]) for e in data for a in e["authors"]
                                   if ascii_fold(a["family"]) != a["family"].lower()})
                for abstracts in (False, True):
                    select_view(page, abstracts)
                    for query in accented:
                        page.fill("#pubs-q", query)
                        expected = {e["key"] for e in data if (abstracts or e["kind"] != "abstract") and
                                    any(query in ascii_fold(a["family"]) for a in e["authors"])}
                        actual = set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)"))
                        texts = page.locator("li.pub:visible").all_inner_texts()
                        check(f"accent search {query}, abstracts={abstracts}: all matching authors shown",
                              bool(expected) and expected <= actual and all(query in ascii_fold(t) for t in texts))
                page.click("#pubs-clear")
                check("Clear filters preserves All view", page.is_checked("#show-abstracts") and shown() == total and
                      parse_qs(urlsplit(page.url).query) == {"abstracts": ["1"]})
                select_view(page, False)

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
                check("Show all appears when search hides entries", page.locator("#pubs-show-all").is_visible())
                check("search count uses Papers denominator", page.inner_text("#pubs-count") ==
                      f"{shown()} of {default_n} papers" and page.locator("#pubs-clear").is_visible())
                check("Highlights hide with search", not page.locator(".pubs-highlights").is_visible())
                page.clock.fast_forward(299)
                check("search URL waits for pause", page.evaluate("window.urlWrites") == 0 and "?" not in page.url)
                page.clock.fast_forward(1)
                check("search URL writes once after 300ms", page.evaluate("window.urlWrites") == 1 and
                      parse_qs(urlsplit(page.url).query).get("q") == ["park"])
                page.fill("#pubs-q", "no-matching-publication")
                page.click("#pubs-clear")
                page.clock.fast_forward(300)
                check("clear cancels pending search URL", "?" not in page.url and shown() == default_n)
                check("Clear restores Highlights", page.locator(".pubs-highlights").is_visible())
                page.evaluate("() => { history.replaceState = window.savedReplace; }")
                page.clock.resume()

                theme = next((t for e in data if e["kind"] != "abstract" for t in e["themes"]), None)
                if theme:
                    expected = sum(e["kind"] != "abstract" and theme in e["themes"] for e in data)
                    chip = page.locator(f'.pubs-controls button[data-group="theme"][data-value="{theme}"]')
                    chip.click()
                    check("theme chip filters", shown() == expected, f"{shown()} != {expected}")
                    check("Highlights hide with theme filter", not page.locator(".pubs-highlights").is_visible())
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
                    check("Clear filters preserves Papers view", shown() == default_n and
                          page.is_checked("#show-papers") and "?" not in page.url, page.url)

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
                    check("active topic group stays visible", page.locator(".pubs-topics").evaluate("el => el.open") and
                          page.locator(f'button[data-group="tag"][data-value="{filters["tag"]}"]').is_visible())
                    filters["review"] = "refereed"
                    page.goto(url + "?" + urlencode(filters))
                    expected = {e["key"] for e in data if e["key"] in expected and e["refereed"]}
                    check("review combines with theme, kind and tag by AND",
                          set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)")) == expected)
                    page.goto(url + "?" + urlencode({k: v + "," + v for k, v in filters.items()}))
                    check("duplicate URL filters are normalized",
                          parse_qs(urlsplit(page.url).query) == {k: [v] for k, v in filters.items()})
                    page.locator(f'.pubs-controls button[data-group="theme"][data-value="{filters["theme"]}"]').click()
                    check("duplicate filter deselects with one click", "theme" not in parse_qs(urlsplit(page.url).query))
                    for abstracts in (False, True):
                        params = dict(filters, q="no-matching-publication")
                        if abstracts:
                            params["abstracts"] = "1"
                        page.goto(url + "?" + urlencode(params))
                        check(f"Show all available from filtered view, All={abstracts}",
                              shown() == 0 and page.locator("#pubs-show-all").is_visible())
                        check(f"Highlights hidden with zero results, All={abstracts}",
                              not page.locator(".pubs-highlights").is_visible())
                        page.click("#pubs-show-all")
                        check(f"Show all moves focus to All, All={abstracts}", page.locator("#show-abstracts").evaluate(
                            "el => el === document.activeElement"))
                        check(f"Show all restores Highlights, All={abstracts}", page.locator(".pubs-highlights").is_visible())
                        check(f"Show all resets count and hides Clear, All={abstracts}",
                              page.inner_text("#pubs-count") == f"{total} entries" and
                              not page.locator("#pubs-clear").is_visible())
                        check(f"Show all clears all filters and selects All, All={abstracts}",
                              shown() == total and page.is_checked("#show-abstracts") and
                              page.input_value("#pubs-q") == "" and
                              page.locator('.pubs-controls button[aria-pressed="true"]').count() == 0)
                        check(f"Show all leaves only abstracts=1, All={abstracts}",
                              urlsplit(page.url).query == "abstracts=1" and not urlsplit(page.url).fragment and
                              not page.locator("#pubs-show-all").is_visible())

                page.goto(url)
                page.locator(".pubs-topics > summary").click()
                more = page.locator("details.more-tags").first
                check("fixture exercises more tags", more.count() == 1 and more.locator("button.chip").count() > 0)
                more.locator("summary").click()
                extra_chip = more.locator("button.chip").first
                extra_tag = extra_chip.get_attribute("data-value")
                extra_chip.click()
                expected = {e["key"] for e in data if e["kind"] != "abstract" and extra_tag in e["tags"]}
                actual = set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)"))
                check("more tag filters entries", bool(expected) and actual == expected)
                page.reload()
                check("active more tag revealed after reload", extra_chip.is_visible() and more.evaluate("el => el.open"))
                page.locator(".pubs-topics > summary").click()
                check("collapsed topics indicate an active filter", page.locator(".pubs-topics > summary").evaluate(
                    "el => getComputedStyle(el, '::after').content.includes('active')"))
                page.fill("#pubs-q", "park")
                check("search preserves collapsed active topics", not page.locator(".pubs-topics").evaluate("el => el.open"))
                page.fill("#pubs-q", "")
                select_view(page, True)
                check("view switch preserves collapsed active topics", not page.locator(".pubs-topics").evaluate("el => el.open"))
                review_chip.click()
                check("review filter preserves collapsed active topics", not page.locator(".pubs-topics").evaluate("el => el.open"))
                page.click("#pubs-clear")
                select_view(page, False)
                entry_tag = page.locator('li.pub:visible .pub-labels a[data-group="tag"]').first
                entry_tag_value = entry_tag.get_attribute("data-value")
                entry_tag.click()
                check("entry tag link filters and reveals topics", page.locator(".pubs-topics").evaluate("el => el.open") and
                      parse_qs(urlsplit(page.url).query).get("tag") == [entry_tag_value] and
                      set(page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.id)")) ==
                      {e["key"] for e in data if e["kind"] != "abstract" and entry_tag_value in e["tags"]})
                page.click("#pubs-clear")
                page.goto(url + "?" + urlencode({"tag": extra_tag}))
                more.locator("summary").click()
                page.fill("#pubs-q", "park")
                check("search preserves collapsed more tags", not more.evaluate("el => el.open"))
                page.click("#pubs-clear")
                more.locator("summary").click()
                zero_chip = page.locator('.pubs-controls button[data-group="tag"]').filter(
                    has=page.locator(".n", has_text=re.compile(r"^0$"))).first
                if zero_chip.count():
                    check("abstract-only tag remains available", zero_chip.is_visible() and zero_chip.is_enabled())
                    zero_chip.click()
                    check("abstract-only tag defaults to zero entries", shown() == 0)
                    select_view(page, True)
                    check("abstract-only tag works in All", shown() > 0 and chip_counts_match(page, True))
                else:
                    print("SKIP abstract-only tag checks: no zero-count tag", flush=True)

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
                    check("hash selects All view", page.is_checked("#show-abstracts"))
                    check("fragment alone does not expose Clear", not page.locator("#pubs-clear").is_visible())
                    page.fill("#pubs-q", abstract_key)
                    page.click("#pubs-clear")
                    check("clear removes fragment", "#" not in page.url, page.url)
                    page.reload()
                    check("Clear keeps All after reload", shown() == total and page.is_checked("#show-abstracts"))
                    page.goto(url + "#" + abstract_key)
                    select_view(page, False)
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
                    page.fill("#pubs-q", key)
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
            if any(e["key"] == "HostileFixture" for e in data):
                page.goto(url)
                hostile = page.locator("#HostileFixture")
                check("hostile fixture remains literal text in every display field", all(
                    f'data-pub-fixture-xss="{field}"' in hostile.locator(selector).text_content()
                    for field, selector in (("title", ".pub-title"), ("author", ".pub-authors"),
                                            ("journal", ".pub-venue"), ("note", ".pub-note"),
                                            ("abstract", ".pub-abstract p"))))
                check("hostile fixture creates no elements or executable attributes", hostile.locator(
                    "img, script, [data-pub-fixture-xss], [onerror]"
                ).count() == 0 and page.evaluate("typeof window.pubFixtureXss === 'undefined'"))

            nojs_ctx = browser.new_context(java_script_enabled=False, reduced_motion="reduce")
            nojs_ctx.route("**/*", local_only)
            nojs = nojs_ctx.new_page()
            nojs.goto(url)
            check("no-JS markers match JSON", markers_match(nojs))
            check("server-rendered view names and counts", nojs.get_by_role("group", name="Entry format").count() == 1 and
                  nojs.get_by_role("radio", name=f"Papers ({default_n})", exact=True).is_checked() and
                  nojs.get_by_role("radio", name=f"All, with abstracts ({total})", exact=True).count() == 1)
            check("server-rendered chip counts match default scope", chip_counts_match(nojs))
            check("highlight metadata has no empty separators", all(
                all(part.strip() for part in text.split("\u00b7"))
                for text in nojs.locator(".pub-meta").all_text_contents()))
            expected_meta = [e["year_label"] + (" " + unescape(re.sub(r"<[^>]+>", "", e["venue_html"]))
                             if e["venue_html"] else "") for e in data if e["selected"]]
            check("Highlights show year and venue without kind", nojs.locator(".pub-meta-venue").all_text_contents() ==
                  expected_meta and nojs.locator(".pubs-highlights .pub-kind").count() == 0)
            check("venue notes have a visible separator", nojs.locator(".pub-note").evaluate_all("""els => els.every(el => {
                const content = getComputedStyle(el, '::before').content;
                return el.previousElementSibling ? content.includes('\\u00b7') : content === 'none';
            })"""))
            check("entry tags are muted and borderless with dot separators", nojs.locator(".pub-labels a").evaluate_all("""els =>
                els.length > 0 && els.every(el => {
                    const s = getComputedStyle(el);
                    return parseFloat(s.fontSize) === 13 && parseFloat(s.borderWidth) === 0 &&
                        s.color === getComputedStyle(document.querySelector('.pub-kind')).color &&
                        (!el.previousElementSibling || getComputedStyle(el, '::before').content.includes('\\u00b7'));
                })"""))
            check("peer-reviewed labels use neutral text color", nojs.locator(".pub-review").evaluate_all("""els =>
                els.every(el => getComputedStyle(el).color === getComputedStyle(document.querySelector('.pub-venue')).color)
            """))
            check("venues have no leading whitespace", all(
                text == text.lstrip() for text in nojs.locator(".pub-venue").all_text_contents()))
            check("adjacent links have text separators", nojs.locator(".pub-links, .pub-labels").evaluate_all("""els =>
                els.every(el => Array.from(el.querySelectorAll('a')).slice(1).every(a =>
                    a.previousSibling.nodeType === Node.TEXT_NODE && /\\s/.test(a.previousSibling.textContent)))"""))
            check("link and label blocks preserve text spacing", nojs.locator(".pub-links, .pub-labels").evaluate_all(
                """els => els.every(el => el.nextSibling?.nodeType === Node.TEXT_NODE && /\\s/.test(el.nextSibling.textContent))"""))
            check("labels have separators before links and after tags", nojs.locator(".pub-labels").evaluate_all(
                """els => els.every(el => {
                    const after = getComputedStyle(el, '::after'), before = getComputedStyle(el, '::before');
                    return after.content.includes('\\u00b7') && parseFloat(after.marginLeft) > 0 &&
                        (!el.previousElementSibling.matches('.pub-links') ||
                         (before.content.includes('\\u00b7') && parseFloat(before.marginRight) > 0));
                })"""))
            check("no-JS: controls hidden", not nojs.locator(".pubs-js").first.is_visible())
            check("no-JS: abstracts hidden by CSS", nojs.locator("li.pub:visible").count() == default_n)
            check("no-JS: peer-reviewed paper labels visible", nojs.locator("li.pub:visible .pub-review:visible").count() ==
                  sum(labeled_review(e) and e["kind"] != "abstract" for e in data))
            select_view(nojs, True)
            check("no-JS: All shows every entry and year", nojs.locator("li.pub:visible").count() == total and
                  nojs.locator(".pubs-year:visible").count() == len({e["year_label"] for e in data}))
            check("no-JS: all peer-reviewed labels visible", nojs.locator("li.pub:visible .pub-review:visible").count() ==
                  sum(labeled_review(e) for e in data))
            nojs.emulate_media(media="print")
            check("print retains peer-reviewed labels", nojs.locator("li.pub:visible .pub-review:visible").count() ==
                  sum(labeled_review(e) for e in data))
            nojs.emulate_media(media="screen")
            select_view(nojs, False)
            check("no-JS: Papers hides abstracts and empty years", nojs.locator("li.pub:visible").count() == default_n and
                  nojs.locator(".pubs-year:visible").count() == len({e["year_label"] for e in data if e["kind"] != "abstract"}))
            nojs.locator("#show-papers").focus()
            nojs.keyboard.press("ArrowRight")
            check("no-JS: arrow key selects All", nojs.is_checked("#show-abstracts") and
                  nojs.locator("li.pub:visible").count() == total)
            nojs.keyboard.press("ArrowLeft")
            check("no-JS: arrow key selects Papers", nojs.is_checked("#show-papers") and
                  nojs.locator("li.pub:visible").count() == default_n)
            nojs.locator("li.pub:visible details.pub-cite summary").first.focus()
            nojs.keyboard.press("Enter")
            check("no-JS: citation readable", nojs.locator("li.pub:visible .cite-bibtex").first.is_visible())
            paper_years = {e["year_label"] for e in data if e["kind"] != "abstract"}
            abstract_targets = [e for e in data if e["kind"] == "abstract"][:1]
            abstract_only = next((e for e in data if e["year_label"] not in paper_years), None)
            if abstract_only and abstract_only not in abstract_targets:
                abstract_targets.append(abstract_only)
            for entry in abstract_targets:
                nojs.goto("about:blank")
                nojs.goto(url + "#" + entry["key"])
                target = nojs.locator(f'[id="{entry["key"]}"]')
                check(f"no-JS: abstract fragment visible in Papers ({entry['key']})", nojs.is_checked("#show-papers") and
                      target.is_visible() and target.locator("xpath=ancestor::section").is_visible() and
                      nojs.locator('li.pub[data-kind="abstract"]:visible').count() == 1)
                header = nojs.locator(".wrapper-masthead").bounding_box()
                check(f"no-JS: abstract fragment lands below masthead ({entry['key']})", target.bounding_box()["y"] >=
                      header["y"] + header["height"] and target.bounding_box()["y"] < nojs.viewport_size["height"])
                nojs.goto(url)
                check(f"no-JS: clearing fragment hides abstract again ({entry['key']})", not target.is_visible() and
                      nojs.locator("li.pub:visible").count() == default_n)

            if shots:
                Path(shots).mkdir(parents=True, exist_ok=True)
                for width in (375, 1280):
                    page.set_viewport_size({"width": width, "height": 812 if width == 375 else 800})
                    page.goto(url)
                    check(f"no horizontal overflow at {width}px", page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"))
                    check(f"readable entries and headings at {width}px", page.locator(
                        "li.pub:visible .pub-title, li.pub:visible .pub-authors, li.pub:visible .pub-venue, "
                        "li.pub:visible .pub-labels a, .pubs h2:visible"
                    ).evaluate_all("""els => els.every(el => {
                        const s = getComputedStyle(el), size = parseFloat(s.fontSize);
                        return size >= (el.matches('.pub-title') ? 14 : 13) && parseFloat(s.lineHeight) / size >= 1.35;
                    })"""))
                    kind_box = page.get_by_role("group", name="Kind", exact=True).bounding_box()
                    review_box = page.get_by_role("group", name="Review", exact=True).bounding_box()
                    check(f"Kind and Review share a row at {width}px", abs(kind_box["y"] - review_box["y"]) < 1 and
                          review_box["x"] >= kind_box["x"] + kind_box["width"])
                    check(f"Highlights metadata stays on one line at {width}px", page.locator(".pub-meta-venue").evaluate_all(
                        """els => els.every(el => {
                            const s = getComputedStyle(el);
                            return s.whiteSpace === 'nowrap' && s.textOverflow === 'ellipsis' && s.overflow === 'hidden' &&
                                el.getBoundingClientRect().height <= Math.max(parseFloat(s.lineHeight),
                                    parseFloat(getComputedStyle(el.closest('li')).lineHeight)) + 1;
                        })"""))
                    if width == 375:
                        check("mobile controls and chips have 32px targets", page.locator(
                            ".pubs button:visible, .pubs .chip:visible, .pubs-view label, .pubs summary:visible"
                        ).evaluate_all("els => els.every(el => el.getBoundingClientRect().height >= 32)"))
                        check("mobile entry and Highlights links have 24px targets", page.locator(
                            "li.pub:visible a:visible, .pubs-highlights a:visible"
                        ).evaluate_all("els => els.every(el => el.getBoundingClientRect().height >= 24)"))
                        page.locator(".pubs-topics > summary").click()
                        page.locator(".more-tags > summary").first.click()
                        check("mobile chip groups scroll without wrapping", page.locator(".chip-group:visible").evaluate_all(
                            """els => els.every(el => {
                                const s = getComputedStyle(el);
                                const tops = Array.from(el.querySelectorAll('button')).filter(b => b.getClientRects().length)
                                    .map(b => b.getBoundingClientRect().top);
                                return s.overflowX === 'auto' && s.whiteSpace === 'nowrap' &&
                                    tops.every(t => Math.abs(t - tops[0]) < 1);
                            })"""), page.locator(".chip-group:visible").evaluate_all("""els => JSON.stringify(els.map(el => ({
                                name: el.getAttribute('aria-label'),
                                tops: Array.from(el.querySelectorAll('button')).filter(b => b.getClientRects().length)
                                    .map(b => b.getBoundingClientRect().top)
                            })))"""))
                        page.locator(".pubs-topics > summary").click()
                        page.evaluate("window.scrollTo(0, 0)")
                    switch = page.locator(".pubs-view").bounding_box()
                    header = page.locator(".wrapper-masthead").bounding_box()
                    check(f"view switch visible before Highlights at {width}px", switch["y"] >= header["y"] + header["height"] and
                          switch["y"] + switch["height"] <= page.viewport_size["height"] and
                          switch["y"] < page.locator(".pubs-highlights").bounding_box()["y"])
                    page.screenshot(path=f"{shots}/publications-{width}.png", animations="disabled")
                    count_titles = """() => {
                        const bottom = document.querySelector('.wrapper-masthead').getBoundingClientRect().bottom;
                        return Array.from(document.querySelectorAll('.pub-title')).filter(el => {
                            const r = el.getBoundingClientRect();
                            return r.height > 0 && r.top >= bottom && r.bottom <= innerHeight;
                        }).length;
                    }"""
                    print(f"METRIC {width}px initial screen: {page.evaluate(count_titles)} entry titles", flush=True)
                    heights = page.locator("li.pub:visible").evaluate_all("els => els.map(el => el.getBoundingClientRect().height)")
                    print(f"METRIC {width}px median entry height: {median(heights):.2f}px", flush=True)
                    if width == 1280:
                        check("first laptop screen includes list entries", page.evaluate(count_titles) > 0)
                    key = page.locator("li.pub:visible").first.get_attribute("id")
                    page.goto(url + "#" + key)
                    print(f"METRIC {width}px list screen: {page.evaluate(count_titles)} entry titles", flush=True)
                    page.screenshot(path=f"{shots}/publications-{width}-list.png", animations="disabled")
                    target_top = page.locator(f'[id="{key}"]').bounding_box()["y"]
                    header = page.locator(".wrapper-masthead").bounding_box()
                    check(f"hash target below header at {width}px", target_top >= header["y"] + header["height"])
                    nojs.set_viewport_size(page.viewport_size)
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
                        check("entry tags suppress hover underline", page.locator(".pub-labels a").first.evaluate(
                            "el => getComputedStyle(el, '::after').display === 'none'"))
                        cite.scroll_into_view_if_needed()
                        page.screenshot(path=f"{shots}/publications-375-citation.png", animations="disabled")
                    for group in ("tag", "theme"):
                        page.goto(url)
                        entry_link = page.locator(f'li.pub:visible .pub-labels a[data-group="{group}"]').last
                        value = entry_link.get_attribute("data-value")
                        entry_link.focus()
                        page.keyboard.press("Enter")
                        chip = page.locator(f'.pubs-controls button[data-group="{group}"][data-value="{value}"]')
                        check(f"entry {group} keyboard link focuses pressed chip at {width}px", chip.evaluate("""el => {
                            const r = el.getBoundingClientRect();
                            const group = el.closest('.chip-group').getBoundingClientRect();
                            const header = document.querySelector('.wrapper-masthead').getBoundingClientRect();
                            // Native scrolling rounds offsets to whole pixels.
                            return document.activeElement === el && el.getAttribute('aria-pressed') === 'true' &&
                                r.top >= header.bottom && r.bottom <= innerHeight &&
                                r.left >= group.left - 1 && r.right <= group.right + 1 && r.left >= 0 && r.right <= innerWidth;
                        }"""))
            browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join()
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
