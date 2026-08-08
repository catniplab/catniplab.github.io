# Golden testcase - publication export

A **matched** input->output fixture for validating a Python reimplementation of
the JabRef publication export (see `../PUBLICATION_EXPORT_SPEC.md`).

## Provenance

Extracted verbatim from git commit **`c3994a0`** ("Dowling2026a on arXiv") of
`catniplab.github.io`, the **last commit that regenerated the bib and both HTML
files together** - so the HTML is exactly what JabRef produced from this bib.
(After `c3994a0`, the bib was edited further without regenerating the HTML, which
is the drift this whole exercise fixes; do not use `HEAD` HTML as golden.)

## Files

- `input.bib` - `catniplab.bib` @ `c3994a0`. 174 `@`-lines = 172 entries +
  2 `@Comment{jabref-meta:...}`. **171 entries render** (see spec section 6 -
  one entry is dropped by JabRef; identify + match or fix).
- `expected/publications.html` - CATNIP table output @ `c3994a0` (171 `<tr class="entry">`).
- `expected/publications_apa.html` - CATNIP-APA list output @ `c3994a0`
  (171 `<div class="entry">`, year-descending).
- `layouts/` - the six `.layout` templates as they were at `c3994a0` (the
  rendering contract; snapshot so the fixture is self-describing even if the live
  layouts later change).

## How to validate a future implementation

1. Run the tool on `input.bib`, freezing the footer date to the commit's
   generation date (the table footer is `Created by JabRef on DD/MM/YYYY`;
   read the exact value from `expected/publications.html`).
2. Diff against `expected/publications.html` and `expected/publications_apa.html`.
   - Tier 1: byte-exact (after the date is pinned).
   - Tier 2: whitespace-normalized structural + text equality.
3. Confirm the hard cases listed in spec section 9 (accents, arXiv/bioRxiv
   eprints, DOI, `@inproceedings`/`@inbook`/`@misc`, volume+number+pages,
   url-only entries).

## Regenerating this fixture (if ever needed)

```sh
git show c3994a0:bib_export/catniplab.bib   > input.bib
git show c3994a0:publications.html          > expected/publications.html
git show c3994a0:publications_apa.html      > expected/publications_apa.html
```
