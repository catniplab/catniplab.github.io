# AGENTS.md - catniplab.github.io

Instructions for AI agents working on the lab website.
`CLAUDE.md` is a local, gitignored symlink to this file
(`ln -s AGENTS.md CLAUDE.md`), so every harness reads the same instructions.

This repository is the public lab website:
whatever reaches `master` is published by GitHub Pages.
Publication list and `catniplab.bib` conventions are in `README.md`.

## AI attribution on announcements and blog posts

Applies to posts in `news/_posts/` (announcements and blog posts).
Does not apply to regular pages (`index.md`, `research.md`, `people.md`,
`publications.html`, and the like).

A post where more than half of the text was produced by AI agents carries an
attribution note.
A post that is mostly written by a person does not.
An agent that contributes to a post that already has the note adds itself to it,
even if its own contribution is small.

The accountable person is the one who directed the work and is named in the note.
Agents are never authors.

### Form on this site

The last paragraph of the post, with the `.ai-attribution` class
(small gray text under a thin rule, defined in `style.scss`):

```markdown
Written primarily by AI agents under <Name>'s direction.
Agents: <Model Name> (<model-id>) via <Harness> <version> - drafted. <YYYY-MM-DD>
{: .ai-attribution}
```

Example:

```markdown
Written primarily by AI agents under Memming's direction.
Agents: Claude Opus 5.5 (claude-opus-5-5) via Claude Code 2.1.318 - drafted. 2026-11-06
{: .ai-attribution}
```

Use plain hyphens, not em dashes.

### Append protocol

The agent list is append-only.
Every agent that contributes adds exactly one line for itself, directly above
the `{: .ai-attribution}` line, using exactly this grammar:

```
<Model Name> (<model-id>) via <Harness> <version>[ (version scraped from terminal | version from cached config)] - <role>. <YYYY-MM-DD>
```

- Roles (pick one, lowercase): `drafted` | `revised` | `reviewed only` | `figures` | `data analysis`.
  Multiple roles: comma-separate (`drafted, revised`).
- Never edit or delete existing lines.
  If you are already listed, append your new role and update the date on your own line only.
- Keep the note concise.

### Resolving model, harness, version

Try in order; first hit wins.
Never trust a model's report of its own identity, and never guess.

1. **Environment or API**: the model string from the runtime environment or the API `model` field.
2. **Shell**: `<harness> --version` (e.g. `claude --version`), else the package manager.
3. **Terminal**: the harness's own status line, matched by a harness-specific pattern only.
   A failed or ambiguous match means `unknown`.
   Annotate scraped values `(version scraped from terminal)`.
4. **Ask the user** once and reuse the answer; annotate `(version from cached config)`.
5. **`unknown`**, or a truthful partial (e.g. `Gemini 3.x Flash, exact version unresolved`).
   Never fabricate.

Date: the system clock (`date +%F`) only.

### Never

- An AI as the author of a post.
- Softened wording ("AI-assisted") on a post that is mostly AI-written.
- A note hidden or styled to be unreadable; it stays the visible last paragraph.
- A fabricated or self-reported model version.
