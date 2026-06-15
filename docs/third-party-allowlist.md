# Third-party content allowlist

Policy (see [CLAUDE.md](../CLAUDE.md) §Repo Hygiene): third-party content is **excluded by
default**. An item may be bundled into a **distributed release zip** only if it is listed
below as **Allowed**, with the basis recorded and the author **credited + their source
linked**. (We still don't commit large third-party binaries into git *history* — bundling
happens at build time into the release-asset zip, never into the repo.)

Basis for "Allowed" — either is sufficient for a non-commercial fan mod in the CCM ecosystem:
- **(a)** a redistribution license/permission on file, **or**
- **(b)** an explicit **owner decision** to redistribute per standard CCM fan-mod practice
  (the community norm is bundle-the-dependency + credit + link the source), with the owner
  taking responsibility and crediting the author. Honor any "do not redistribute" request.

## Allowed

| Item | Author | Basis | Where to get it (source linked in README) | Handling |
|---|---|---|---|---|
| **Nightmare Difficulty** pack (`NightmareMod.SC2Mod` + its maps) | Rhyme (TheRealRhyme) | **(b) owner decision** — no license file is published (pack ships only `metadata.txt`); redistributed per CCM fan-mod norm, credited to Rhyme, source linked | GiantGrantGames' Custom Campaign Manager Discord — <https://discord.com/invite/ywvCz7CN> | Bundled at build time by `build.py build/package nightmare` into the **Nightmare** release zip (a complete download — no end-user build). Credit Rhyme in README §Credits + link the GGG Discord. If Rhyme ever asks us not to, pull the variant. |

## How to add an allowed item
1. Record the basis: a license/permission link **or** an explicit owner decision.
2. Add the row above with the author + the public **source link**.
3. Credit the author in [README.md](../README.md) §Credits (the pre-commit `check_credits.py` reminder helps).
4. Only if the item must also live *in the repo* (rare): add a `!`-negation in `.gitignore` for its path. (The Nightmare pack does NOT — it's fetched locally and bundled into the release zip at build time, never committed.)
