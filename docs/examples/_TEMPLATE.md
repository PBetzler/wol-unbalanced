# NN — <Recipe title: "How to <achieve result>">

> One-sentence statement of the **result** this recipe produces.

**Maps to (request):** which unit-table Comment / design rule / open-issue / backlog item this
came from (cite it). **Status:** [STATIC] done · [EDITOR]/[GAME] parked (see Verify).

---

## Result
What the player sees/gets when this is done. Be concrete (a number, a button, a behavior).

## Mechanism
The exact engine construct: which catalog/field/clone/galaxy call, and *why it's the one that
works* (name the no-op alternative it avoids — cross-ref [02](02-no-op-traps.md)). 1–3 short
paragraphs. Cite the relevant [learnings.md](../learnings.md) / [implementation-patterns.md](../implementation-patterns.md) section.

## Worked example (real, from this repo)
The actual shipped implementation, with **real ids** and **`file:line` citations**. Show the
real snippet (XML or genlib tuple or galaxy), e.g.:

```xml
<!-- src/mod/Base.SC2Data/GameData/<File>.xml:NN -->
<C... id="...WoLU" parent="...">
  ...
</C...>
```
```python
# scripts/genlib.py:NN
("Unit", "<id>", "<Field>", "<value>", "<Op>", "<comment>"),
```

Walk through *why each line is there*. Note the merc/hero **reach** (does the edit reach
mercs/heroes? per [01 §reach](01-per-player-scalar-stat-edit.md) / [06](06-merc-hero-parity.md)).

## Reusable snippet (swap the ids)
A minimal, generic copy-paste template with `<PLACEHOLDERS>` and a one-line "resolve these ids
first" reminder.

## Gotchas / no-op traps
Bullet list of what silently fails here (indexed-array edit, link edit, string-field edit,
load-time read, missing `index=` on an append, friendly-fire default, clone-Effect re-default,
passive-vs-action button, wrong card cell). Cross-ref [02](02-no-op-traps.md).

## Verify
- **Static:** the exact `audit.py` CHECK / `galaxy_lint` / card-merge-sim signal that proves the
  structure, **and what it does *not* prove**. `[STATIC]`
- **Editor (Previewer):** what to look at and the expected render. `[EDITOR]` — add to queue.
- **In-game (Test Document / owner playtest):** the exact thing to observe + the mission.
  `[GAME]` — add to queue.

## Parked for bunch-verify
The specific [EDITOR]/[GAME] line(s) to copy into [_QUEUE.md](_QUEUE.md), or "none — fully
[STATIC]".
</content>
