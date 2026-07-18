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

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Paste a sample of your recommender's output here as a text block so a reader can see what it produces:

```
# e.g.:
# User profile: genre=indie, mood=chill, energy=low
# Recommendations:
#   1. ...
#   2. ...
#   3. ...
```

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
