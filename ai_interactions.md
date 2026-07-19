# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

<!-- Describe the goal you asked the agent to accomplish -->

**Prompts used:**

<!-- Paste the key prompts you gave the agent -->

**What did the agent generate or change?**

<!-- List the files edited, code generated, or commands run -->

**What did you verify or fix manually?**

<!-- Describe anything the agent got wrong or that required human review -->

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

Strategy. `src/recommender.py` defines a `RankingStrategy` abstract base class with one
method, `rank(user_prefs, songs, weights) -> List[Tuple[song, score, explanation]]`, and
three interchangeable implementations: `BalancedStrategy` (the original weighted-sum
behavior), `GenreFirstStrategy` (genre match as a hard tier above everything else), and
`EnergySimilarityStrategy` (orders purely by energy distance, ignoring genre/mood).

**How did AI help you brainstorm or implement it?**

I asked Claude to implement "multiple ranking modes" as a stretch feature after already
having a working weighted-sum scorer (`score_song`) and a weight-shift experiment in
`main.py`. Claude's first suggestion was Strategy, reasoning that the project already had
one interchangeable "algorithm" (how to turn per-song data into an order) that different
callers might want to swap at runtime — the textbook case for Strategy over e.g. Factory
(which is about *creating* objects, not swapping behavior) or Observer (event
notification, not applicable here).

The more useful part of the exchange was Claude catching that my first version of
`GenreFirstStrategy` would be indistinguishable from `BalancedStrategy` in the sample
output: with the default weights, genre's weight (+2.0) already dominates the sum, so a
"hard tier by genre" and "weighted sum sorted by score" produce the *same* order on most
profiles in this dataset. Claude proposed re-running the mode comparison under the
weight-shift experiment's *shifted* weights (genre 1.0, energy 4.0) instead of the
defaults — at those weights `balanced` stops favoring the mismatched rock song, but
`genre-first` still forces it to #1 regardless, which is what actually demonstrates that
a hard tier and a large weight are not the same mechanism.

**How does the pattern appear in your final code?**

- `RankingStrategy` (abstract base) and its three subclasses: `src/recommender.py`
- `RANKING_STRATEGIES`, a `{mode_name: strategy_instance}` registry used to look up a
  strategy by name: `src/recommender.py`
- `recommend_with_strategy(user_prefs, songs, k, mode, weights)`, the entry point that
  looks up a strategy and calls `.rank()` on it: `src/recommender.py`
- `--mode` CLI flag (`balanced` / `genre-first` / `energy-similarity`), wired to
  `recommend_with_strategy`: `src/main.py`

**What I verified manually:** ran `pytest` (still 2/2 passing — the Strategy classes are
additive and don't touch `score_song`/`recommend_songs`/the `Recommender` class used by
the tests), then ran `python -m src.main --mode genre-first` and
`python -m src.main --mode energy-similarity` by hand and read the output tables to
confirm each strategy actually reorders songs differently rather than silently falling
back to the same sort.
