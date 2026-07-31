# 🎵 Music Recommender Simulation

## Base Project & Scope of This Extension

**Base project:** Music Recommender Simulation, originally built for Module 3 of this
course (github.com/jusdal/ai110-module3show-musicrecommendersimulation).

**Original goal and capabilities:** the base project is a content-based music
recommender with no collaborative filtering and no user history — it scores each song
in a small catalog against a single stated `UserProfile` (favorite genre, favorite
mood, target energy, acoustic preference) using a weighted rule-based `score_song()`
function, then returns the top-k matches with a human-readable "why" explanation for
each. It supports three interchangeable ranking strategies (`balanced`, `genre-first`,
`energy-similarity`) via a Strategy pattern, plus an optional artist-diversity
penalty (`--diversify`) to prevent one artist from dominating the results. This
original version had no input validation (malformed profiles caused raw crashes) and
no way to signal how confident a given recommendation was.

**What this Project 4 submission adds:** three new AI/reliability components layered
on top of that unchanged core — (1) input validation guardrails that catch malformed
profiles cleanly instead of crashing, (2) an ensemble reliability/confidence scorer
that checks whether the three existing ranking strategies agree on the top pick, with
the result surfaced directly in the CLI output, and (3) an `eval.py` test harness that
exercises both against 10 known profiles. See "Reliability & Confidence Scoring" and
"Guardrails / Input Validation" below for details, and `diagrams/architecture.mmd` for
how these pieces fit into the runtime pipeline.

---

## How The System Works

Most real-world recommenders (Spotify, Netflix, YouTube) blend two approaches: collaborative filtering, which finds patterns across many users' behavior (e.g. "people who liked X also liked Y"), and content-based filtering, which compares an item's own attributes to what a single user has said or shown they like. Large-scale systems lean heavily on collaborative signals and implicit behavioral data — skips, watch time, replays — because that data is abundant and doesn't require anyone to state a preference explicitly. This simulation has no other users to compare against and no behavioral history, so it is a purely **content-based** recommender: it prioritizes explicit attribute matching, scoring how closely each song's own numeric and categorical features align with one user's stated taste profile, rather than relying on what "people like them" enjoyed.

### Features used

**`Song`** — the recommender scores songs using:

- `genre` — categorical, matched against the user's favorite genre
- `mood` — categorical, matched against the user's favorite mood
- `energy` — numeric (0-1), scored by closeness to the user's target energy
- `acousticness` — numeric (0-1), thresholded and checked against the user's acoustic preference

`Song` also carries `tempo_bpm`, `valence`, and `danceability` from the dataset, but these aren't used in scoring yet — they're highly correlated with `energy`/`acousticness` in this catalog, so they'd add little independent signal to a simple version.

**`UserProfile`** stores the taste profile the score is computed against:

- `favorite_genre`
- `favorite_mood`
- `target_energy`
- `likes_acoustic`

### Algorithm Recipe

Each song is scored independently against the user's profile by summing points from four rules, then all songs are sorted by that score and the top `k` are returned:

| Rule               | Condition                                                | Points                                                    |
| ------------------ | -------------------------------------------------------- | --------------------------------------------------------- |
| Genre match        | `song.genre == favorite_genre`                           | `+2.0`                                                    |
| Mood match         | `song.mood == favorite_mood`                             | `+1.0`                                                    |
| Energy closeness   | scaled by distance from `target_energy`                  | `2.0 * (1 - abs(song.energy - target_energy))` (0 to 2.0) |
| Acoustic threshold | `likes_acoustic` is `True` and `song.acousticness > 0.6` | `+1.0`                                                    |

Genre gets the largest flat bonus because it's the strongest single predictor of whether a listener will even give a song a chance. Energy is scaled rather than flat so a near-miss (0.40 vs. a target of 0.35) still earns most of its points, instead of an all-or-nothing cliff. Acousticness is a threshold rather than a scaled score because `likes_acoustic` is a boolean preference, not a target value to converge on.

**Potential bias:** because genre (+2.0) outweighs mood (+1.0) and can outweigh a partial energy match, the system can over-prioritize genre — a `lofi` song with the wrong mood and off-target energy can still outscore a non-`lofi` song that matches the user's mood and energy closely. Listeners with broad genre taste but strong mood/energy preferences may get recommendations that feel genre-correct but emotionally off.

### Ranking Modes (Strategy Pattern)

Everything above describes one way of turning a score into an order — take the weighted
sum and sort by it. `src/recommender.py` factors that decision out into a **Strategy
pattern**: a `RankingStrategy` abstract base class defines a single `rank(user_prefs,
songs, weights)` method, and each concrete strategy implements it differently. All
strategies still call `score_song()` for the per-song score and "why" explanation, so
switching strategies never changes what a song's explanation says — only the order the
songs come back in.

| Mode (`--mode`)      | Strategy class             | How it orders songs                                                                                                                                                       |
| -------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `balanced` (default) | `BalancedStrategy`         | The weighted sum described above — identical to the original `recommend_songs()` behavior.                                                                                |
| `genre-first`        | `GenreFirstStrategy`       | Genre match is a hard tier: every genre-matching song outranks every non-matching song, no matter the weighted score. Ties within a tier fall back to the balanced score. |
| `energy-similarity`  | `EnergySimilarityStrategy` | Ignores genre/mood/acoustic for ordering entirely and sorts purely by closeness to `target_energy`.                                                                       |

`RANKING_STRATEGIES` is a `{mode_name: strategy_instance}` registry, and
`recommend_with_strategy(user_prefs, songs, k, mode, weights)` looks a strategy up by
name and calls `.rank()` on it. `src/main.py` exposes this as a CLI flag:

```bash
python -m src.main --mode genre-first
python -m src.main --mode energy-similarity
```

The default run (no flag, or `--mode balanced`) also prints a **ranking mode
comparison** for the "Calm Rock Contradiction" profile (rock genre, peaceful mood, low
energy — the same profile the bias example above is built on) under the weight-shift
experiment's _shifted_ weights. That comparison is the clearest illustration of why mode
and weights are genuinely different levers: under shifted weights, `balanced` already
stops favoring the mismatched rock song, but `genre-first` still forces it to #1 —
because its tier is a hard rule, not a number that weight-tuning can out-vote.

### Diversity / Fairness (Artist Penalty)

Scoring alone can let one artist quietly take multiple slots in the top 5 just because
two of their songs both happen to fit the profile — a small-scale "filter bubble." The
`--diversify` flag turns on a greedy repeat-artist penalty, implemented as
`apply_artist_diversity()` in `src/recommender.py`: it rebuilds the top-k list one song at
a time, and every time an artist gets picked, their remaining songs lose
`--artist-penalty` points (default `1.5`) before the next pick is chosen. A second song
from an already-picked artist still has to be a strong match — it just has to beat that
penalty, not merely beat the rest of the field.

```bash
python -m src.main --diversify
python -m src.main --diversify --artist-penalty 3.0
```

This composes with `--mode`: `recommend_with_strategy(..., diversify=True)` runs the
chosen ranking strategy first, then applies the artist penalty on top of whatever order
that strategy produced. See the model card's "Diversity / fairness" note for how this
affects fairness, and "Diversity comparison" below for a real before/after.

### Reliability & Confidence Scoring (Ensemble Agreement)

`src/reliability.py` treats the three ranking strategies in `RANKING_STRATEGIES`
(`balanced`, `genre-first`, `energy-similarity`) as an implicit ensemble: all three
score songs with the same `score_song()`, but disagree on how to _order_ them. When
they land on the same top pick, that's a signal the recommendation is robust to how
you rank, not just how you score. When they scatter, the "best" answer is really just
whichever strategy happened to be selected — a much shakier basis for trust.

`compute_agreement(user_prefs, songs, weights, k)` runs every registered strategy
against the same profile and combines two signals into one 0-1 confidence score:

| Signal           | What it measures                                                     | Weight |
| ---------------- | -------------------------------------------------------------------- | ------ |
| `top1_agreement` | Fraction of strategies whose #1 pick matches the most common #1 pick | 0.6    |
| `avg_jaccard`    | Average pairwise Jaccard overlap between strategies' top-`k` sets    | 0.4    |

`confidence_label()` buckets the resulting score into **High** (≥0.75), **Medium**
(≥0.45), or **Low** (below 0.45). `src/main.py` renders this as a badge under each
recommendation table via `format_confidence()`, with a `⚠ LOW CONFIDENCE` warning
banner when the label is Low — see "Confidence badge examples" below for real output,
including a constructed Low case.

**Why confidence is computed pre-diversity, deliberately:** `compute_agreement()`
always reruns all three strategies _without_ the `--diversify` artist penalty, even
when the recommendation on screen was diversified. Diversity re-sorts an already-good
list to spread it across artists — it doesn't change whether the underlying strategies
agree on what counts as a good match. Feeding the diversified order into the agreement
calculation would conflate two different questions ("do the strategies agree on
quality?" vs. "did we then spread the results across artists?") and would make a list
_less_ confident purely because it got fairer — the wrong thing to penalize. See the
`NOTE1` callout in [`diagrams/architecture.mmd`](diagrams/architecture.mmd) for the
same rule diagrammed.

### Guardrails / Input Validation

`validate_user_prefs()` (in `src/recommender.py`) checks a `user_prefs` dict before
it's allowed anywhere near scoring:

- `genre` and `mood` must be present and non-empty strings
- `energy` must be present, numeric, and within `[0, 1]` — booleans are explicitly
  rejected even though `isinstance(True, int)` is `True` in Python and `0 <= True <=
1`, so a stray `energy: True` can't silently score as `energy: 1.0`

Any violation raises `ProfileValidationError` (a `ValueError` subclass) with every
problem collected into one message, and logs it via `logger.error()`, instead of
letting the first missing key surface as an opaque crash three frames deep in
`score_song()`.

**This used to be a gap**: only `recommend_with_strategy()` called
`validate_user_prefs()`. `compute_agreement()` didn't, so a profile that never reached
`recommend_with_strategy()` first — or was passed straight to the reliability layer —
could still blow up with a raw `KeyError`. Before the fix, running the "Missing Genre
Key" profile (`{mood: chill, energy: 0.4}`, no `genre`) straight through
`compute_agreement()` produced this real traceback:

```
Traceback (most recent call last):
  File "repro.py", line 9, in <module>
    compute_agreement(prefs, songs, k=5)
  File "src/reliability.py", line 68, in compute_agreement
    ranked = strategy.rank(user_prefs, songs, weights)
  File "src/recommender.py", line 199, in rank
    return recommend_songs(user_prefs, songs, k=len(songs), weights=weights)
  File "src/recommender.py", line 167, in recommend_songs
    score, reasons = score_song(user_prefs, song, weights)
  File "src/recommender.py", line 145, in score_song
    if song["genre"] == user_prefs["genre"]:
KeyError: 'genre'
```

**After the fix**, `compute_agreement()` calls `validate_user_prefs()` first, so the
exact same input now fails fast with a clear, actionable message instead:

```
ERROR: Invalid user profile: missing required field 'genre'
```

(logged via `logger.error()`, then raised as `ProfileValidationError` — `src/main.py`
catches it and prints `-> INVALID PROFILE: <message>` for that profile instead of
crashing the whole run.) `validate_user_prefs()` is now called at the top of **both**
entry points — `recommend_with_strategy()` and `compute_agreement()` — so every path
into scoring sees the same checks, independently, with no shared state between the two
calls.

### Architecture Diagram

[`diagrams/architecture.mmd`](diagrams/architecture.mmd) is a Mermaid flowchart of the
full pipeline: CLI args and a `user_prefs` dict feed into the two independent
`validate_user_prefs()` calls, valid profiles flow into `recommend_with_strategy()`
(strategy selection → scoring → optional `--diversify`) and into `compute_agreement()`
(all three strategies run unconditionally → agreement → confidence label), and both
outputs meet at `format_recommendations()` / `format_confidence()` for the human
review point. It also documents `eval.py` as a separate, offline dev/CI path that
exercises the same `validate_user_prefs → recommend_with_strategy → compute_agreement`
pipeline against a fixed set of profiles, and calls out the two deliberate design
notes described above (validation runs twice with no shared state; confidence is
always computed pre-diversity).

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

   ```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

Optionally pick a ranking mode (default is `balanced`; see "Ranking Modes" above):

```bash
python -m src.main --mode genre-first
python -m src.main --mode energy-similarity
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

### Running the Evaluation Harness (eval.py)

`eval.py` is a standalone, CI-friendly harness for the reliability pipeline. It reuses
`src/recommender.py` and `src/reliability.py` directly — no scoring or ranking logic
is reimplemented — and runs a fixed list of 10 profiles (the 3 core taste profiles
plus 7 adversarial/edge-case profiles, including "Boolean Energy" —
`energy: True` — which specifically exercises the bool-vs-numeric guardrail described
above) through the full `validate_user_prefs → recommend_with_strategy →
compute_agreement` pipeline. For each profile it checks:

- Whether validation accepted/rejected the input as expected (`expect_valid` in the
  `PROFILES` list)
- Whether scoring and agreement computation complete without an unexpected crash
- That a confidence score/label comes out the other end for every profile that passes
  validation

Run it with:

```bash
python eval.py
```

It prints a PASS/FAIL table and exits `0` only if every profile passes (`1`
otherwise), so it's safe to wire into CI. Real output from a local run:

```
============ EVAL SUMMARY ============

╒═════════════════════╤═════════════╤═══════════════╤════════════════════════════════════════════════════════╕
│ Profile             │ Pass/Fail   │ Confidence    │ Notes                                                  │
╞═════════════════════╪═════════════╪═══════════════╪════════════════════════════════════════════════════════╡
│ High-Energy Pop     │ PASS        │ Medium (0.71) │ processed normally                                     │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Chill Lofi          │ PASS        │ High (0.91)   │ processed normally                                     │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Deep Intense Rock   │ PASS        │ High (1.00)   │ processed normally                                     │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Missing Genre Key   │ PASS        │ -             │ validation caught invalid input as expected (no crash) │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Case Mismatch       │ PASS        │ High (0.91)   │ validation passed input through as expected; scored    │
│                     │             │               │ without crashing                                       │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Unknown Genre       │ PASS        │ High (0.80)   │ validation passed input through as expected; scored    │
│                     │             │               │ without crashing                                       │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Out-of-Range Energy │ PASS        │ -             │ validation caught invalid input as expected (no crash) │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Empty Genre/Mood    │ PASS        │ -             │ validation caught invalid input as expected (no crash) │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Conflicting         │ PASS        │ High (0.80)   │ validation passed input through as expected; scored    │
│ Energy/Mood         │             │               │ without crashing                                       │
├─────────────────────┼─────────────┼───────────────┼────────────────────────────────────────────────────────┤
│ Boolean Energy      │ PASS        │ -             │ validation caught invalid input as expected (no crash) │
╘═════════════════════╧═════════════╧═══════════════╧════════════════════════════════════════════════════════╛

10/10 passed
```

---

## Sample Recommendation Output

Output from `python -m src.main`, one table per user profile. Recommendations are
rendered with [`tabulate`](https://pypi.org/project/tabulate/) (`format_recommendations()`
in `src/main.py`) so the score and the "Why" explanation are readable side by side
instead of scrolling through separate print statements — this is the "Visual Output /
Summary Table" stretch feature.

### Core taste profiles

**High-Energy Pop** — `{genre: pop, mood: euphoric, energy: 0.85, likes_acoustic: False}`

```
╒═════╤═══════════════╤══════════════╤═════════╤══════════════════════════════════════════════╕
│   # │ Title         │ Artist       │   Score │ Why                                          │
╞═════╪═══════════════╪══════════════╪═════════╪══════════════════════════════════════════════╡
│   1 │ Sunrise City  │ Neon Echo    │    3.94 │ genre match (+2.0), energy closeness (+1.94) │
├─────┼───────────────┼──────────────┼─────────┼──────────────────────────────────────────────┤
│   2 │ Gym Hero      │ Max Pulse    │    3.84 │ genre match (+2.0), energy closeness (+1.84) │
├─────┼───────────────┼──────────────┼─────────┼──────────────────────────────────────────────┤
│   3 │ Pulse Horizon │ DJ Kinetic   │    2.8  │ mood match (+1.0), energy closeness (+1.80)  │
├─────┼───────────────┼──────────────┼─────────┼──────────────────────────────────────────────┤
│   4 │ Carnival Sol  │ Ritmo Dorado │    2    │ energy closeness (+2.00)                     │
├─────┼───────────────┼──────────────┼─────────┼──────────────────────────────────────────────┤
│   5 │ Storm Runner  │ Voltline     │    1.88 │ energy closeness (+1.88)                     │
╘═════╧═══════════════╧══════════════╧═════════╧══════════════════════════════════════════════╛
```

**Chill Lofi** — `{genre: lofi, mood: chill, energy: 0.35, likes_acoustic: True}`

```
╒═════╤═════════════════════╤════════════════╤═════════╤═══════════════════════════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                                           │
╞═════╪═════════════════════╪════════════════╪═════════╪═══════════════════════════════════════════════╡
│   1 │ Library Rain        │ Paper Lanterns │    6    │ genre match (+2.0), mood match (+1.0), energy │
│     │                     │                │         │ closeness (+2.00), acoustic match (+1.0)      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   2 │ Midnight Coding     │ LoRoom         │    5.86 │ genre match (+2.0), mood match (+1.0), energy │
│     │                     │                │         │ closeness (+1.86), acoustic match (+1.0)      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   3 │ Focus Flow          │ LoRoom         │    4.9  │ genre match (+2.0), energy closeness (+1.90), │
│     │                     │                │         │ acoustic match (+1.0)                         │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   4 │ Spacewalk Thoughts  │ Orbit Bloom    │    3.86 │ mood match (+1.0), energy closeness (+1.86),  │
│     │                     │                │         │ acoustic match (+1.0)                         │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   5 │ Coffee Shop Stories │ Slow Stereo    │    2.96 │ energy closeness (+1.96), acoustic match      │
│     │                     │                │         │ (+1.0)                                        │
╘═════╧═════════════════════╧════════════════╧═════════╧═══════════════════════════════════════════════╛
```

**Deep Intense Rock** — `{genre: rock, mood: intense, energy: 0.9, likes_acoustic: False}`

```
╒═════╤═══════════════╤═══════════════╤═════════╤═══════════════════════════════════════════════╕
│   # │ Title         │ Artist        │   Score │ Why                                           │
╞═════╪═══════════════╪═══════════════╪═════════╪═══════════════════════════════════════════════╡
│   1 │ Storm Runner  │ Voltline      │    4.98 │ genre match (+2.0), mood match (+1.0), energy │
│     │               │               │         │ closeness (+1.98)                             │
├─────┼───────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   2 │ Gym Hero      │ Max Pulse     │    2.94 │ mood match (+1.0), energy closeness (+1.94)   │
├─────┼───────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   3 │ Pulse Horizon │ DJ Kinetic    │    1.9  │ energy closeness (+1.90)                      │
├─────┼───────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   4 │ Carnival Sol  │ Ritmo Dorado  │    1.9  │ energy closeness (+1.90)                      │
├─────┼───────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   5 │ Iron Descent  │ Grave Circuit │    1.86 │ energy closeness (+1.86)                      │
╘═════╧═══════════════╧═══════════════╧═════════╧═══════════════════════════════════════════════╛
```

### Adversarial / edge-case profiles

**Conflicting Energy/Mood** — `{genre: rock, mood: peaceful, energy: 0.95, likes_acoustic: False}`

```
╒═════╤═══════════════╤═══════════════╤═════════╤══════════════════════════════════════════════╕
│   # │ Title         │ Artist        │   Score │ Why                                          │
╞═════╪═══════════════╪═══════════════╪═════════╪══════════════════════════════════════════════╡
│   1 │ Storm Runner  │ Voltline      │    3.92 │ genre match (+2.0), energy closeness (+1.92) │
├─────┼───────────────┼───────────────┼─────────┼──────────────────────────────────────────────┤
│   2 │ Pulse Horizon │ DJ Kinetic    │    2    │ energy closeness (+2.00)                     │
├─────┼───────────────┼───────────────┼─────────┼──────────────────────────────────────────────┤
│   3 │ Gym Hero      │ Max Pulse     │    1.96 │ energy closeness (+1.96)                     │
├─────┼───────────────┼───────────────┼─────────┼──────────────────────────────────────────────┤
│   4 │ Iron Descent  │ Grave Circuit │    1.96 │ energy closeness (+1.96)                     │
├─────┼───────────────┼───────────────┼─────────┼──────────────────────────────────────────────┤
│   5 │ Carnival Sol  │ Ritmo Dorado  │    1.8  │ energy closeness (+1.80)                     │
╘═════╧═══════════════╧═══════════════╧═════════╧══════════════════════════════════════════════╛
```

**Acoustic Paradox** — `{genre: metal, mood: aggressive, energy: 0.9, likes_acoustic: True}`

```
╒═════╤═════════════════╤═══════════════╤═════════╤═══════════════════════════════════════════════╕
│   # │ Title           │ Artist        │   Score │ Why                                           │
╞═════╪═════════════════╪═══════════════╪═════════╪═══════════════════════════════════════════════╡
│   1 │ Iron Descent    │ Grave Circuit │    4.86 │ genre match (+2.0), mood match (+1.0), energy │
│     │                 │               │         │ closeness (+1.86)                             │
├─────┼─────────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   2 │ Dusty Highway   │ Wade Carter   │    2.3  │ energy closeness (+1.30), acoustic match      │
│     │                 │               │         │ (+1.0)                                        │
├─────┼─────────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   3 │ Midnight Coding │ LoRoom        │    2.04 │ energy closeness (+1.04), acoustic match      │
│     │                 │               │         │ (+1.0)                                        │
├─────┼─────────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   4 │ Focus Flow      │ LoRoom        │    2    │ energy closeness (+1.00), acoustic match      │
│     │                 │               │         │ (+1.0)                                        │
├─────┼─────────────────┼───────────────┼─────────┼───────────────────────────────────────────────┤
│   5 │ Storm Runner    │ Voltline      │    1.98 │ energy closeness (+1.98)                      │
╘═════╧═════════════════╧═══════════════╧═════════╧═══════════════════════════════════════════════╛
```

**Missing Genre Key** — `{mood: chill, energy: 0.4}` (no `genre` key)

```
-> FAILED: KeyError: 'genre'
```

**Case Mismatch** — `{genre: Lofi, mood: Chill, energy: 0.3, likes_acoustic: True}`

```
╒═════╤═════════════════════╤════════════════╤═════════╤══════════════════════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                                      │
╞═════╪═════════════════════╪════════════════╪═════════╪══════════════════════════════════════════╡
│   1 │ Riverbend Ashes     │ Hollow Pine    │    3    │ energy closeness (+2.00), acoustic match │
│     │                     │                │         │ (+1.0)                                   │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────┤
│   2 │ Spacewalk Thoughts  │ Orbit Bloom    │    2.96 │ energy closeness (+1.96), acoustic match │
│     │                     │                │         │ (+1.0)                                   │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────┤
│   3 │ Library Rain        │ Paper Lanterns │    2.9  │ energy closeness (+1.90), acoustic match │
│     │                     │                │         │ (+1.0)                                   │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────┤
│   4 │ Coffee Shop Stories │ Slow Stereo    │    2.86 │ energy closeness (+1.86), acoustic match │
│     │                     │                │         │ (+1.0)                                   │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────┤
│   5 │ Focus Flow          │ LoRoom         │    2.8  │ energy closeness (+1.80), acoustic match │
│     │                     │                │         │ (+1.0)                                   │
╘═════╧═════════════════════╧════════════════╧═════════╧══════════════════════════════════════════╛
```

**Unknown Genre** — `{genre: k-pop, mood: happy, energy: 0.7, likes_acoustic: False}`

```
╒═════╤══════════════════╤═══════════════╤═════════╤═════════════════════════════════════════════╕
│   # │ Title            │ Artist        │   Score │ Why                                         │
╞═════╪══════════════════╪═══════════════╪═════════╪═════════════════════════════════════════════╡
│   1 │ Rooftop Lights   │ Indigo Parade │    2.88 │ mood match (+1.0), energy closeness (+1.88) │
├─────┼──────────────────┼───────────────┼─────────┼─────────────────────────────────────────────┤
│   2 │ Sunrise City     │ Neon Echo     │    2.76 │ mood match (+1.0), energy closeness (+1.76) │
├─────┼──────────────────┼───────────────┼─────────┼─────────────────────────────────────────────┤
│   3 │ Concrete Kingdom │ MC Solace     │    1.96 │ energy closeness (+1.96)                    │
├─────┼──────────────────┼───────────────┼─────────┼─────────────────────────────────────────────┤
│   4 │ Night Drive Loop │ Neon Echo     │    1.9  │ energy closeness (+1.90)                    │
├─────┼──────────────────┼───────────────┼─────────┼─────────────────────────────────────────────┤
│   5 │ Dusty Highway    │ Wade Carter   │    1.7  │ energy closeness (+1.70)                    │
╘═════╧══════════════════╧═══════════════╧═════════╧═════════════════════════════════════════════╛
```

**Out-of-Range Energy** — `{genre: EDM, mood: euphoric, energy: 5.0, likes_acoustic: False}`

```
╒═════╤═════════════════╤════════════════╤═════════╤═══════════════════════════════════════════════╕
│   # │ Title           │ Artist         │   Score │ Why                                           │
╞═════╪═════════════════╪════════════════╪═════════╪═══════════════════════════════════════════════╡
│   1 │ Pulse Horizon   │ DJ Kinetic     │       3 │ genre match (+2.0), mood match (+1.0), energy │
│     │                 │                │         │ closeness (+0.00)                             │
├─────┼─────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   2 │ Sunrise City    │ Neon Echo      │       0 │ energy closeness (+0.00)                      │
├─────┼─────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   3 │ Midnight Coding │ LoRoom         │       0 │ energy closeness (+0.00)                      │
├─────┼─────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   4 │ Storm Runner    │ Voltline       │       0 │ energy closeness (+0.00)                      │
├─────┼─────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   5 │ Library Rain    │ Paper Lanterns │       0 │ energy closeness (+0.00)                      │
╘═════╧═════════════════╧════════════════╧═════════╧═══════════════════════════════════════════════╛
```

**Empty Genre/Mood** — `{genre: "", mood: "", energy: 0.5, likes_acoustic: False}`

```
╒═════╤═════════════════════╤═════════════╤═════════╤══════════════════════════╕
│   # │ Title               │ Artist      │   Score │ Why                      │
╞═════╪═════════════════════╪═════════════╪═════════╪══════════════════════════╡
│   1 │ Velvet Whisper      │ Simone Rae  │    1.96 │ energy closeness (+1.96) │
├─────┼─────────────────────┼─────────────┼─────────┼──────────────────────────┤
│   2 │ Dusty Highway       │ Wade Carter │    1.9  │ energy closeness (+1.90) │
├─────┼─────────────────────┼─────────────┼─────────┼──────────────────────────┤
│   3 │ Midnight Coding     │ LoRoom      │    1.84 │ energy closeness (+1.84) │
├─────┼─────────────────────┼─────────────┼─────────┼──────────────────────────┤
│   4 │ Focus Flow          │ LoRoom      │    1.8  │ energy closeness (+1.80) │
├─────┼─────────────────────┼─────────────┼─────────┼──────────────────────────┤
│   5 │ Coffee Shop Stories │ Slow Stereo │    1.74 │ energy closeness (+1.74) │
╘═════╧═════════════════════╧═════════════╧═════════╧══════════════════════════╛
```

### Ranking mode comparison

`python -m src.main` also runs the "Calm Rock Contradiction" profile (`{genre: rock, mood: peaceful, energy: 0.35, likes_acoustic: False}`) through all three ranking modes under the weight-shift experiment's shifted weights (`genre: 1.0, energy: 4.0`), to isolate what changing the ranking _strategy_ does versus changing the _weights_:

```
-- Balanced (balanced) --
╒═════╤═════════════════════╤════════════════╤═════════╤═════════════════════════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                                         │
╞═════╪═════════════════════╪════════════════╪═════════╪═════════════════════════════════════════════╡
│   1 │ Moonlit Sonata      │ Elena Voss     │    4.4  │ mood match (+1.0), energy closeness (+3.40) │
│     │ Reimagined          │                │         │                                             │
├─────┼─────────────────────┼────────────────┼─────────┼─────────────────────────────────────────────┤
│   2 │ Library Rain        │ Paper Lanterns │    4    │ energy closeness (+4.00)                    │
├─────┼─────────────────────┼────────────────┼─────────┼─────────────────────────────────────────────┤
│   3 │ Coffee Shop Stories │ Slow Stereo    │    3.92 │ energy closeness (+3.92)                    │
├─────┼─────────────────────┼────────────────┼─────────┼─────────────────────────────────────────────┤
│   4 │ Focus Flow          │ LoRoom         │    3.8  │ energy closeness (+3.80)                    │
├─────┼─────────────────────┼────────────────┼─────────┼─────────────────────────────────────────────┤
│   5 │ Riverbend Ashes     │ Hollow Pine    │    3.8  │ energy closeness (+3.80)                    │
╘═════╧═════════════════════╧════════════════╧═════════╧═════════════════════════════════════════════╛

-- Genre-First (genre-first) --
╒═════╤═════════════════════╤════════════════╤═════════╤══════════════════════════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                                          │
╞═════╪═════════════════════╪════════════════╪═════════╪══════════════════════════════════════════════╡
│   1 │ Storm Runner        │ Voltline       │    2.76 │ genre match (+1.0), energy closeness (+1.76) │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   2 │ Moonlit Sonata      │ Elena Voss     │    4.4  │ mood match (+1.0), energy closeness (+3.40)  │
│     │ Reimagined          │                │         │                                              │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   3 │ Library Rain        │ Paper Lanterns │    4    │ energy closeness (+4.00)                     │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   4 │ Coffee Shop Stories │ Slow Stereo    │    3.92 │ energy closeness (+3.92)                     │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   5 │ Focus Flow          │ LoRoom         │    3.8  │ energy closeness (+3.80)                     │
╘═════╧═════════════════════╧════════════════╧═════════╧══════════════════════════════════════════════╛

-- Energy-Similarity (energy-similarity) --
╒═════╤═════════════════════╤════════════════╤═════════╤══════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                      │
╞═════╪═════════════════════╪════════════════╪═════════╪══════════════════════════╡
│   1 │ Library Rain        │ Paper Lanterns │    4    │ energy closeness (+4.00) │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────┤
│   2 │ Coffee Shop Stories │ Slow Stereo    │    3.92 │ energy closeness (+3.92) │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────┤
│   3 │ Focus Flow          │ LoRoom         │    3.8  │ energy closeness (+3.80) │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────┤
│   4 │ Riverbend Ashes     │ Hollow Pine    │    3.8  │ energy closeness (+3.80) │
├─────┼─────────────────────┼────────────────┼─────────┼──────────────────────────┤
│   5 │ Spacewalk Thoughts  │ Orbit Bloom    │    3.72 │ energy closeness (+3.72) │
╘═════╧═════════════════════╧════════════════╧═════════╧══════════════════════════╛
```

At these weights, `balanced` has already stopped favoring the mismatched rock song (Storm Runner doesn't even make its top 5). `genre-first` still forces Storm Runner to #1 anyway, despite its low score — proving the tier is a hard rule that weight-tuning can't override. `energy-similarity` ignores genre entirely and produces yet another order, built purely from energy distance.

### Diversity comparison

`python -m src.main` also runs the "Chill Lofi" profile (`{genre: lofi, mood: chill, energy: 0.35, likes_acoustic: True}`) with and without `--diversify`. Without it, LoRoom takes two of the five slots ("Midnight Coding" at #2, "Focus Flow" at #3) simply because both songs fit the profile well:

```
-- Without diversity penalty --
╒═════╤═════════════════════╤════════════════╤═════════╤═══════════════════════════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                                           │
╞═════╪═════════════════════╪════════════════╪═════════╪═══════════════════════════════════════════════╡
│   1 │ Library Rain        │ Paper Lanterns │    6    │ genre match (+2.0), mood match (+1.0), energy │
│     │                     │                │         │ closeness (+2.00), acoustic match (+1.0)      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   2 │ Midnight Coding     │ LoRoom         │    5.86 │ genre match (+2.0), mood match (+1.0), energy │
│     │                     │                │         │ closeness (+1.86), acoustic match (+1.0)      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   3 │ Focus Flow          │ LoRoom         │    4.9  │ genre match (+2.0), energy closeness (+1.90), │
│     │                     │                │         │ acoustic match (+1.0)                         │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   4 │ Spacewalk Thoughts  │ Orbit Bloom    │    3.86 │ mood match (+1.0), energy closeness (+1.86),  │
│     │                     │                │         │ acoustic match (+1.0)                         │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   5 │ Coffee Shop Stories │ Slow Stereo    │    2.96 │ energy closeness (+1.96), acoustic match      │
│     │                     │                │         │ (+1.0)                                        │
╘═════╧═════════════════════╧════════════════╧═════════╧═══════════════════════════════════════════════╛

-- With diversity penalty (-1.5 per repeat artist) --
╒═════╤═════════════════════╤════════════════╤═════════╤═══════════════════════════════════════════════╕
│   # │ Title               │ Artist         │   Score │ Why                                           │
╞═════╪═════════════════════╪════════════════╪═════════╪═══════════════════════════════════════════════╡
│   1 │ Library Rain        │ Paper Lanterns │    6    │ genre match (+2.0), mood match (+1.0), energy │
│     │                     │                │         │ closeness (+2.00), acoustic match (+1.0)      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   2 │ Midnight Coding     │ LoRoom         │    5.86 │ genre match (+2.0), mood match (+1.0), energy │
│     │                     │                │         │ closeness (+1.86), acoustic match (+1.0)      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   3 │ Spacewalk Thoughts  │ Orbit Bloom    │    3.86 │ mood match (+1.0), energy closeness (+1.86),  │
│     │                     │                │         │ acoustic match (+1.0)                         │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   4 │ Focus Flow          │ LoRoom         │    3.4  │ genre match (+2.0), energy closeness (+1.90), │
│     │                     │                │         │ acoustic match (+1.0), diversity penalty      │
│     │                     │                │         │ (-1.5 for repeat artist)                      │
├─────┼─────────────────────┼────────────────┼─────────┼───────────────────────────────────────────────┤
│   5 │ Coffee Shop Stories │ Slow Stereo    │    2.96 │ energy closeness (+1.96), acoustic match      │
│     │                     │                │         │ (+1.0)                                        │
╘═════╧═════════════════════╧════════════════╧═════════╧═══════════════════════════════════════════════╛
```

Same five songs, different order: Focus Flow (LoRoom's second pick) drops from #3 to #4, its score docked 1.5 points for repeating an artist already on the list, and Spacewalk Thoughts (a different artist, Orbit Bloom) moves up to #3 in its place.

### Confidence badge examples

`python -m src.main` prints a confidence badge under every core taste profile's table
(see "Reliability & Confidence Scoring" above for how it's computed). Real output from
a local run — the three core profiles land at Medium and High:

```bash
python -m src.main
```

```
=== High-Energy Pop ===
[... table omitted, see "Core taste profiles" above ...]
Confidence: Medium (0.71) — #1 agreement 67%, top-5 overlap 78%

=== Chill Lofi ===
[... table omitted, see "Core taste profiles" above ...]
Confidence: High (0.91) — #1 agreement 100%, top-5 overlap 78%

=== Deep Intense Rock ===
[... table omitted, see "Core taste profiles" above ...]
Confidence: High (1.00) — #1 agreement 100%, top-5 overlap 100%
```

None of the three built-in profiles happen to land in **Low** territory, so below is a
**custom test case** — not one of the three taste profiles `python -m src.main` ships
by default, and not in `PROFILES` in `eval.py` either — built specifically to make the
strategies disagree: `genre: metal` (only one metal song in the catalog, and it's
high-energy) crossed with a low-energy, low-key target (`energy: 0.2, mood: chill`)
that no metal song is close to. Run it yourself with a one-off script calling
`recommend_with_strategy()` / `compute_agreement()` directly, the same way this output
was captured. `balanced`, `genre-first`, and `energy-similarity` each pick a
_different_ song for #1:

```
=== [CUSTOM TEST CASE] Metal/Chill Contradiction (not a shipped default profile) ===
Profile: {'genre': 'metal', 'mood': 'chill', 'energy': 0.2, 'likes_acoustic': True}
╒═════╤════════════════════╤════════════════╤═════════╤══════════════════════════════════════════════╕
│   # │ Title              │ Artist         │   Score │ Why                                          │
╞═════╪════════════════════╪════════════════╪═════════╪══════════════════════════════════════════════╡
│   1 │ Spacewalk Thoughts │ Orbit Bloom    │    3.84 │ mood match (+1.0), energy closeness (+1.84), │
│     │                    │                │         │ acoustic match (+1.0)                        │
├─────┼────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   2 │ Library Rain       │ Paper Lanterns │    3.7  │ mood match (+1.0), energy closeness (+1.70), │
│     │                    │                │         │ acoustic match (+1.0)                        │
├─────┼────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   3 │ Midnight Coding    │ LoRoom         │    3.56 │ mood match (+1.0), energy closeness (+1.56), │
│     │                    │                │         │ acoustic match (+1.0)                        │
├─────┼────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   4 │ Moonlit Sonata     │ Elena Voss     │    3    │ energy closeness (+2.00), acoustic match     │
│     │ Reimagined         │                │         │ (+1.0)                                       │
├─────┼────────────────────┼────────────────┼─────────┼──────────────────────────────────────────────┤
│   5 │ Riverbend Ashes    │ Hollow Pine    │    2.8  │ energy closeness (+1.80), acoustic match     │
│     │                    │                │         │ (+1.0)                                       │
╘═════╧════════════════════╧════════════════╧═════════╧══════════════════════════════════════════════╛
⚠  LOW CONFIDENCE — the ranking strategies disagree significantly on this recommendation; treat it with caution.
Confidence: Low (0.43) — #1 agreement 33%, top-5 overlap 59%
```

All three strategies pick a _different_ #1: `balanced` (the table above) lands on
"Spacewalk Thoughts" because no metal song is close enough on mood/energy to win on
weighted score alone; `genre-first` forces the catalog's only metal song, "Iron
Descent," to #1 regardless of its energy/mood mismatch, because its hard tier doesn't
care about anything else; and `energy-similarity` — which ignores genre and mood
entirely — lands on "Moonlit Sonata Reimagined," whose energy (0.20) is a near-exact
match for the 0.2 target. Zero overlap on #1 across all three strategies is exactly
the disagreement the confidence score is designed to surface.

**Screenshot or video** _(optional)_: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

- **Weight shift (genre halved 2.0→1.0, energy doubled 2.0→4.0).** Run automatically by
  `python -m src.main` on the "Calm Rock Contradiction" profile (rock genre, peaceful
  mood, energy 0.35). Under default weights, the catalog's one rock song (Storm Runner —
  high energy, mood "intense") still narrowly wins on genre's flat +2.0 bonus, even
  though it barely matches the rest of the profile. Under shifted weights, "Moonlit
  Sonata Reimagined" — the song that actually matches mood and energy — takes over, and
  Storm Runner drops out of the top 5 entirely. See "Sample Recommendation Output" →
  "Ranking mode comparison" for the real tables.
- **Ranking mode vs. weight-tuning.** Re-ran that same profile through all three
  `--mode` strategies under the shifted weights above, to check whether `genre-first`
  hard-tiering and "a large genre weight" were secretly doing the same thing. They
  aren't: `balanced` responds to the reweighting and drops Storm Runner, but
  `genre-first` still forces it to #1 regardless of score, because a hard tier isn't
  something weight-tuning can out-vote.
- **Diversity penalty.** Ran "Chill Lofi" with and without `--diversify`. Without it,
  one artist (LoRoom) takes 2 of 5 slots purely because both of their songs happen to
  fit well; with it, the weaker LoRoom pick is docked 1.5 points and a different artist
  moves up instead. See "Diversity comparison" above for the real before/after.
- **Different user types.** High-Energy Pop vs. Chill Lofi share zero songs in their
  top 5 — the two profiles disagree on every axis. High-Energy Pop vs. Deep Intense
  Rock share 4 of 5, since both target energy around 0.85–0.9. Full writeup in the
  model card's "Comparing the profiles" section.
- **Not tried:** adding `tempo_bpm`/`valence`/`danceability` to the score, and letting a
  profile hold more than one favorite genre or mood — both listed as future work in
  `model_card.md` §8.

---

## Limitations and Risks

- **Tiny, lopsided catalog.** 18 songs total, and 13 of 15 genres have exactly one
  song — a niche-genre request has no fallback if that single song is a poor fit on
  everything else (see the "Calm Rock Contradiction" example above).
- **Genre can override an explicit mood/energy preference.** A genre match (+2.0)
  outweighs a mood match (+1.0) and can outweigh a partial energy mismatch, so a
  recommendation can be genre-correct but emotionally off. This is documented, not
  fixed — see `model_card.md` §6 for the full bias writeup.
- **No lyrics, audio content, or listening history.** This is a purely content-based
  recommender scored against one stated profile — it doesn't learn from behavior or
  understand anything about a song beyond its four scored attributes.
- **One genre, one mood, per profile.** A profile can't represent someone who
  genuinely likes two genres equally — real listeners usually do.
- **Three dataset columns go unused.** `tempo_bpm`, `valence`, and `danceability` are
  loaded but never scored.
- **Confidence is a heuristic, not a calibrated probability.** It measures whether
  three rule-based ranking strategies agree, not whether a recommendation is
  objectively "correct" — "High confidence" means consensus, not accuracy.
- **Validation is duplicated, not shared.** `validate_user_prefs()` is called
  independently in both `recommend_with_strategy()` and `compute_agreement()` with no
  shared state — harmless today, but if one call site's rules get updated and the
  other doesn't, that reintroduces the exact crash this guardrail was built to prevent
  (see "A flawed AI suggestion" below).

You'll find a deeper dive on data, strengths, and bias in `model_card.md`.

---

## Reflection on AI Collaboration and System Design

### How I used AI during development

I used Claude Code throughout this project — for scaffolding the validation and
reliability modules, wiring the CLI output, building the eval harness, and drafting
the architecture diagram. I worked in an iterative loop: giving it scoped, specific
prompts for one piece at a time rather than asking for the whole feature set at once,
then testing and reviewing before moving on. I also used it to reason through design
decisions — like whether the confidence score should account for `--diversify` or be
computed independently of it — rather than just accepting the first implementation it
produced.

### A helpful AI suggestion

The idea to reuse the three existing ranking strategies as an implicit ensemble for
measuring confidence — rather than building a separate mechanism from scratch — felt
obviously right as soon as it was suggested. It kept the new feature tightly
integrated with the existing architecture instead of bolting on something
disconnected, and it's a big part of why the feature was achievable in a one-day
budget.

### A flawed AI suggestion

The initial implementation wired validation asymmetrically: `recommend_with_strategy()`
caught `ProfileValidationError` cleanly, but `compute_agreement()` didn't — so an
invalid profile would crash `main()` uncaught, in exactly the scenario the guardrail
feature was supposed to prevent. The bug passed all automated tests, since `eval.py`
wraps its own calls in a try/except and reported 9/9 passing regardless. I only caught
it by reviewing the architecture diagram against the real code and noticing the two
validation call sites behaved differently. It was a reminder that I'd assumed passing
tests meant the feature worked — but the tests were only checking what they were
written to check, not the actual runtime behavior a real user would hit.

### Limitations and future improvements

The redundant validation is the limitation that bothers me most: both
`recommend_with_strategy()` and `compute_agreement()` independently call
`validate_user_prefs()` on the same input, with no shared state between them. It's
functionally harmless today, but it's exactly the kind of duplication that tends to
drift out of sync over time — if one call site's validation logic gets updated and the
other doesn't, that's a new version of the same bug I just fixed. If I had another day,
the first thing I'd do is collapse this into a single shared validation gate — validate
once, and pass a validated object downstream to both functions — so there's one source
of truth instead of two independently-maintained copies of the same check.
