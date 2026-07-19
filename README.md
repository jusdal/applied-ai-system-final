# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

Replace this paragraph with your own summary of what your version does.

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

| Rule | Condition | Points |
| --- | --- | --- |
| Genre match | `song.genre == favorite_genre` | `+2.0` |
| Mood match | `song.mood == favorite_mood` | `+1.0` |
| Energy closeness | scaled by distance from `target_energy` | `2.0 * (1 - abs(song.energy - target_energy))` (0 to 2.0) |
| Acoustic threshold | `likes_acoustic` is `True` and `song.acousticness > 0.6` | `+1.0` |

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

| Mode (`--mode`) | Strategy class | How it orders songs |
| --- | --- | --- |
| `balanced` (default) | `BalancedStrategy` | The weighted sum described above — identical to the original `recommend_songs()` behavior. |
| `genre-first` | `GenreFirstStrategy` | Genre match is a hard tier: every genre-matching song outranks every non-matching song, no matter the weighted score. Ties within a tier fall back to the balanced score. |
| `energy-similarity` | `EnergySimilarityStrategy` | Ignores genre/mood/acoustic for ordering entirely and sorts purely by closeness to `target_energy`. |

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
experiment's *shifted* weights. That comparison is the clearest illustration of why mode
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

`python -m src.main` also runs the "Calm Rock Contradiction" profile (`{genre: rock, mood: peaceful, energy: 0.35, likes_acoustic: False}`) through all three ranking modes under the weight-shift experiment's shifted weights (`genre: 1.0, energy: 4.0`), to isolate what changing the ranking *strategy* does versus changing the *weights*:

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

**Screenshot or video** _(optional)_: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this
