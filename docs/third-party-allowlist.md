# Third-party content allowlist

Policy (see [CLAUDE.md](../CLAUDE.md) §Repo Hygiene): third-party content is **excluded by
default**. An item may be committed to this repo or bundled into a distributed build **only
if it is listed here with a license/permission on file that allows redistribution**, and a
matching `!`-negation is added to `.gitignore`. No author license on file ⇒ not eligible.

This keeps us honest: we redistribute someone else's work only when they've said we may.

## Allowed (redistribution permitted)

*(none yet)*

## Requested / pending a license

| Item | Author | Why we'd want it | License status | Current handling |
|---|---|---|---|---|
| **Nightmare Difficulty** pack (`NightmareMod.SC2Mod` + its maps) | Rhyme (TheRealRhyme) | base layer for the optional harder build (`build.py build nightmare`) | **No license file** — the pack ships only a `metadata.txt` (title/desc/author/version); no redistribution terms published | **Build-it-yourself**: we ship the build mode, not the artifact. A user who already owns the Nightmare pack runs `build.py build nightmare` locally to combine it with our mod — no redistribution by us. To distribute a ready-made combined zip we'd first need Rhyme's explicit permission or a published license; then move this row to *Allowed* and add the `!`-negation. |

## How to add an allowed item
1. Confirm the author's license/permission allows redistribution; save the text/link here.
2. Move it to **Allowed** with the license summary.
3. Add a `!`-negation in `.gitignore` for the specific path (e.g. `!mods/<thing>/`), so only that item is un-ignored.
4. Credit the author in [README.md](../README.md) §Credits (the pre-commit `check_credits.py` reminder helps).
