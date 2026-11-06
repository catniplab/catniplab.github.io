# CATNIP Lab website

## Publications page

`/publications.html` is rendered by Jekyll from `_data/publications.json`, which
`bib_export/build_publications.py` generates from `bib_export/catniplab.bib`.
Editing the bib alone does not change the page; the JSON must be regenerated
and committed with it.

To add or change a paper:

1. Edit `bib_export/catniplab.bib` (conventions below).
2. Regenerate: `cd bib_export && ./p.sh` (skip this if the pre-commit hook is
   installed; it does it for you).
3. Commit the bib and `_data/publications.json` together, then push.

### Pre-commit hook (recommended, once per clone)

From the repository root:

```bash
ln -sf "$PWD/bib_export/pre-commit" "$(git rev-parse --git-path hooks)/pre-commit"
```

When a commit includes `bib_export/catniplab.bib`, `_data/publication_labels.yml`,
`_data/lab_members.json` or `bib_export/build_publications.py`, the hook builds
`_data/publications.json` from the staged files and adds it to the commit. If
the bib has an error (an unknown tag, an unparseable entry, a bad URL), the
commit is aborted and the generator's message says which entry. It needs
[uv](https://docs.astral.sh/uv/). To skip it once: `git commit --no-verify`.
Check that it is installed: `ls -l "$(git rev-parse --git-path hooks)/pre-commit"`.

### catniplab.bib conventions

`catniplab.bib` is the lab's publication record. It feeds this page and the
CV, which is built with BibTeX, so a field the page ignores can still show in
the CV.

Entries differ in layout (braces or quotes, field order, alignment) depending
on the tool that exported them. Neither output cares; do not reformat entries
you are not otherwise changing.

#### Adding an entry

- New entries go at the top (newest first).
- Key: `AuthorYYYYa`, the first author's family name, the year the work first
  appeared, and a letter. The key never changes, including when a preprint is
  published: the CV cites it.
- The entry type sets the kind shown on the page: `@Article` journal paper,
  `@InProceedings` conference paper, `@Unpublished` preprint (with `eprint` or
  `url`; without either, a manuscript), `@PhdThesis`/`@MastersThesis` thesis,
  `@InBook` book chapter. `pubtype` overrides it.
- Add `abstract` when available; the page shows it.

#### Preprints

- arXiv: `@Unpublished` with `archivePrefix = {arXiv}`, `eprint = {2507.05505}`
  and `primaryclass` set to the paper's primary category on arXiv (e.g.
  `math.DS`). No `journal`: the page shows `arXiv:<id>` from `eprint`, and the
  CV prints `arXiv:<id> [<primaryclass>]`.
- bioRxiv, DOI prefix `10.1101`: `archivePrefix = {bioRxiv}` and `eprint` set
  to the part after `10.1101/` (e.g. `2021.04.14.439872`).
- bioRxiv, DOI prefix `10.64898` (minted from late 2025): no
  `archivePrefix`/`eprint`, because the link would be built under `10.1101`.
  Use `journal = {bioRxiv}`, `doi` and `url` instead (e.g. `Jeon2026a`).
- When a preprint is published, change the entry type and add the venue, but
  keep the key and the `archivePrefix`/`eprint`/`primaryclass` fields; the page
  links both versions.

#### Site-specific fields

BibTeX ignores these; the page uses them.

- `pubtype`: `abstract` for conference abstracts and extended abstracts
  (COSYNE, SfN, CNS, workshops; hidden in the default view), `invited`,
  `patent`, `manuscript`, `other`. Without it, an `@InProceedings` abstract is
  listed as a conference paper.
- `refereed`: `true`/`false`. Journal and conference papers default to `true`,
  everything else to `false`. Set `refereed = {false}` on a paper that was not
  reviewed. On an abstract, `true` means a review that selects (COSYNE, CNS,
  DeepMath, a reviewed workshop); a meeting whose review is a basic quality
  screen (SfN, Bernstein) stays `false`. Where that line falls is a judgment
  call, not a hard boundary, so the flag stays binary and the kind stays
  "Conference abstract" whatever the format (a 2-page extended abstract or an
  abstract alone). The CV draws the same line between "Peer-reviewed
  Conference Abstracts" and "Conference Abstracts".
- `themes`, `tags`: `;`-separated ids from `_data/publication_labels.yml`; an
  unknown id stops the build.
- `selected = {true}`: listed under Highlights.
- Links, in display order: `pdf` (a file name in `publications/`), the
  `eprint` link, `doi` (bare, `10.xxxx/...`), `url`, `url2`, `code`, `data`,
  `youtube`. A URL that duplicates an earlier link (same DOI or arXiv id) is
  shown once.

`note` is shown after the venue (and printed by BibTeX); a note containing
"In press" is highlighted.

#### Editing fields

`uv run --script bib_export/set_fields.py CHANGES.csv` inserts or replaces
single-line fields without touching the rest of the file and checks the result
before writing it (CSV columns and details in the script's header).

### Tests

- `bib_export/run_tests.sh`: generator and bib tool unit tests.
- `bib_export/tests/build_site.sh`: builds the site with the GitHub Pages gem
  set in Docker. Then run `tests/check_site.py` and `tests/browser_test.py` on
  its output (usage in each script's header).
