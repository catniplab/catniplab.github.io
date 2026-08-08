# Spec: Python publication-export tool (replace JabRef CLI)

> Status: **SPEC ONLY - not implemented.** Reverse-engineered 2026-08-08 from the
> JabRef `.layout` export templates and the last matched HTML output.
> Golden fixture: `spec_testcase/` (see its README).

## 1. Motivation

The lab website's two publication pages are generated from `catniplab.bib` by
`bib_export/p.sh`, which drives the **JabRef desktop app** in CLI mode with two
custom export formats (`CATNIP`, `CATNIP-APA`). This is fragile:

- The CLI `-o` export **hangs** when no JabRef GUI instance is running (blocks on
  the single-instance remote handshake; 0% CPU), and **silently writes nothing**
  when a GUI instance *is* running (the job is handed to the running instance,
  which does not perform the export). Observed on JabRef 5.15, macOS, 2026-08-08.
- It depends on GUI-registered custom export formats (stored in the Java prefs
  backend `~/Library/Preferences/com.apple.java.util.prefs.plist`), which are not
  version-controlled and can be lost on upgrade/machine change.

JabRef here is only a **templating engine over BibTeX**. A small, deterministic,
testable Python tool replaces it with no GUI dependency.

## 2. Scope

Read `catniplab.bib`, write two files (identical filenames/locations as today):

- `../publications.html` - "CATNIP" searchable/sortable **table** view.
- `../publications_apa.html` - "CATNIP-APA" **APA hanging-indent list**, sorted
  by year descending.

Non-goals: editing the bib, the Jekyll build (`docker.sh`), or the site CSS/nav.

## 3. Inputs

1. **`catniplab.bib`** - JabRef-managed BibTeX. Entry types seen: `@article`,
   `@unpublished`, `@inproceedings`, `@inbook`, `@misc`, `@incollection`, `@book`.
   Trailing `@Comment{jabref-meta: ...}` lines MUST be ignored.
2. **Layout templates** (the rendering contract, in `bib_export/`, snapshotted in
   `spec_testcase/layouts/`): `tablerefs.{begin,,end}.layout`,
   `aparefs.{begin,,end}.layout`. The tool may either (a) parse these JabRef
   layouts, or (b) reimplement their behavior directly in Python/Jinja - **(b) is
   recommended** (simpler; the layouts are static and rarely change). If (b), the
   `.layout` files remain the human-readable spec of record.

Fields referenced by the layouts (per entry): `author`, `title`, `year`,
`journal`, `booktitle`, `volume`, `number`, `pages`, `school`, `howpublished`,
`note`, `entrytype`, `doi`, `url`, `pdf`, `data`, `youtube`, `code`, `eprint`,
`archivePrefix`.

## 4. JabRef formatter semantics to reproduce

The layouts use JabRef markup. Exact behaviors to replicate:

### 4.1 Conditional blocks
`\begin{FIELD} ... \end{FIELD}` renders the enclosed text **only if FIELD is
present and non-empty**; otherwise the whole block (including literal text inside)
is omitted. Nesting is shallow (one level). This drives almost all optionality
(volume/number/pages/doi/url/eprint/...).

### 4.2 Author formatting - `\format[Authors(...)]{\author}`
Parse the BibTeX `author` field on ` and `. For each name produce **Last, Initials**:
- **Table** (`Authors(LastFirst,InitialsNoSpace)`): initials have **no internal
  space** -> `Park, I.M.`; `Dowling, M.`. Separator between authors is `, `;
  the last author is preceded by ` and ` (JabRef default).
  Example: `Dowling, M., Jeon, H., Savin, C. and Park, I.M.`
- **APA** (`Authors(LastFirst,Initials,Sep=, ,LastSep=, & )`): initials have an
  internal space -> `Park, I. M.`; separator `, `, last separator `, & `.
  Example: `Filipe, A. C., Bernaerts, Y., ... & Park, I. M.`
- Von/Jr particles and `{Braced Names}` follow BibTeX name rules; keep JabRef's
  handling (verify against fixtures with de Polavieja, da Silva-style names).

### 4.3 `\format[HTMLChars]{...}` - LaTeX -> HTML entities
Convert TeX accent/special macros to **named HTML entities**, exactly as JabRef's
`HTMLChars` formatter does. Confirmed from the golden output:
`\'a`->`&aacute;`, `\'A`->`&Aacute;`, `\'o`->`&oacute;`, `\'e`->`&eacute;`,
`\l`->`&lstrok;`, `{\ss}`/`\ss`->`&szlig;`, etc. Strip stray braces.
Implementation hint: `pylatexenc` (LatexNodes2Text) to Unicode, then a
Unicode->named-entity map matching JabRef's table. **The named-entity forms must
match byte-for-byte** (`&aacute;`, not `&#225;` or a raw `á`) or the fixture
diff fails.

### 4.4 `\format[FormatPagesForHTML]{...}`
Page/number ranges: `--` -> en dash `&ndash;` (verify exact entity vs literal in
fixture). Applies to `\pages` and `\number`.

### 4.5 `\format[ToLowerCase]{\entrytype}`
Reftype column: entry type lowercased (`Article`->`article`,
`Unpublished`->`unpublished`, `InProceedings`->`inproceedings`).

### 4.6 eprint URL (archivePrefix-aware)
`\begin{eprint}` block builds a link:
- base = `archivePrefix` mapped: `arXiv`->`arxiv.org/abs`,
  `bioRxiv`->`www.biorxiv.org/content/10.1101`; default `arxiv.org/abs`.
- href = `https://<base>/<eprint>`; link text = `archivePrefix` (default `arXiv`).

### 4.7 Other single-field links
`doi` -> `<a href="https://doi.org/DOI">` (APA) / `DOICheck` normalization
(table); `url`,`pdf` (prefixed `/publications/`),`data`,`youtube`,`code` -> plain
anchors. See `tablerefs.layout` / `aparefs.layout` for exact surrounding markup,
spacing, and label text (`URL `, `PDF `, `[PDF]`, `[Code]`, ...). Reproduce
whitespace exactly.

### 4.8 Footer date - `\format[CurrentDate]{dd/MM/yyyy}` (table only)
JabRef stamps the generation date in the table footer. **This makes output
non-deterministic and breaks byte-exact testing.** Decision for the tool: either
(a) omit the date, or (b) make it injectable/frozen (CLI `--date` or env) so tests
pin it. Recommend (b) with a fixed value in the fixture run.

## 5. Assembly & ordering

- **Table (`publications.html`)**: `tablerefs.begin.layout` (static head: CSS,
  QuickSearch JS, tablesorter JS, masthead/nav) + one `<tr>` per entry in
  **bib-file order** (JabRef CLI preserves source order; the visible year-desc
  order is applied client-side by tablesorter `sortList:[[2,1],[4,0]]`) +
  `tablerefs.end.layout` (footer, GA).
- **APA (`publications_apa.html`)**: `aparefs.begin.layout` + one
  `<div class="entry">` per entry, then **sorted by year descending** by
  `sort_html_entries.py` (stable; within-year order stays bib order) +
  `aparefs.end.layout`. The Python tool should sort in-process (fold in
  `sort_html_entries.py`'s job) rather than post-process.

## 6. Entry inclusion

The golden fixture has **171 rendered entries** from 174 `@`-lines
(2 are `@Comment{jabref-meta:...}`). That leaves a **1-entry discrepancy** to
resolve: identify which bib entry JabRef omits (likely an entry lacking a
required field, or an unsupported type) and match that behavior, or treat it as
a bug to fix (document the choice).

## 7. Dependencies (suggested, confirm with Memming before implementing)

- BibTeX parse: `bibtexparser` (>=2) or `pybtex`. Must expose raw fields +
  ordered author list + preserve source order.
- LaTeX->text: `pylatexenc` for accents; plus an explicit Unicode->HTML-entity
  map to hit JabRef's named entities.
- Templating: `jinja2` (translate the `.layout` bodies), or plain f-strings.
- Run via `uv` (PEP 723 inline metadata), per lab convention. No network.

## 8. CLI / interface

```
uv run export_pubs.py --bib catniplab.bib \
    --out-table ../publications.html \
    --out-apa   ../publications_apa.html \
    [--date 2026-06-05]      # freeze footer date for reproducibility
```
Idempotent; deterministic given (bib, date); exit non-zero on parse error.

## 9. Acceptance test

See `spec_testcase/`. Golden pair extracted from the last matched generation
(git commit `c3994a0`, "Dowling2026a on arXiv").

- Run the tool on `spec_testcase/input.bib` with `--date` frozen to that commit's
  generation date.
- Compare stdout files against `spec_testcase/expected/publications.html` and
  `.../publications_apa.html`.
- **Tier 1 (ideal):** byte-exact match (after pinning the footer date).
- **Tier 2 (acceptable):** normalize insignificant whitespace between tags, then
  assert structural + text equality (same entry ids, same order, same rendered
  author strings, same entity encodings, same link hrefs).
- Spot-check the hard cases the fixture already contains: accented authors
  (Sagodi/Sokol/Gallego/de Polavieja), arXiv vs bioRxiv eprint links, DOI links,
  `@inproceedings`/`@inbook`/`@misc`, entries with volume+number+pages, and
  entries with only a `url`.

## 10. Migration

When the tool passes the fixture on the *current* live `catniplab.bib`:
1. Replace the body of `p.sh` (keep the filename) with a call to the Python tool
   (drop the JabRef launch/wait logic added 2026-08-08).
2. Keep the `.layout` files as the documented rendering reference.
3. Publishing rules unchanged: regenerate -> test (`docker.sh`) -> **explicit user
   confirmation** -> commit + push (public site). See `../CLAUDE.md` upstream and
   PM4MP memory `feedback_catniplab_site_publish_workflow`.
