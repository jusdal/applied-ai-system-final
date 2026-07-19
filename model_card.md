# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

Give your model a short, descriptive name.  
Example: **VibeFinder 1.0**

**VibeCheck 1.0** — it checks how well a song's vibe (genre, mood, energy, acousticness) matches what you said you wanted.

---

## 2. Intended Use

Describe what your recommender is designed to do and who it is for.

Prompts:

- What kind of recommendations does it generate
- What assumptions does it make about the user
- Is this for real users or classroom exploration

You tell it your favorite genre, favorite mood, how much energy you want, and whether you like acoustic songs. It looks at a small catalog of songs and hands back the top 5 that fit best, plus a plain-English reason for each one.

It assumes you can put your taste into a few simple boxes — one genre, one mood, one energy level. Real people usually like more than one thing at once, so that's a simplification, not a real limitation of taste.

This is a classroom project, not a real app. The catalog only has 18 songs, so it's built for learning how a recommender works and poking at its biases, not for actually finding your next favorite song.

**Non-intended use:** don't use this to make real claims about what music people "objectively" like, and don't treat it as a real product — the catalog is tiny, several genres and moods only have one song, and biases like genre-overriding-mood haven't been fixed, just documented.

---

## 3. How the Model Works

Explain your scoring approach in simple language.

Prompts:

- What features of each song are used (genre, energy, mood, etc.)
- What user preferences are considered
- How does the model turn those into a score
- What changes did you make from the starter logic

Avoid code here. Pretend you are explaining the idea to a friend who does not program.

Every song has a genre, a mood, an energy level (0 to 1), and how acoustic it sounds (0 to 1). There's also tempo, valence, and danceability sitting in the data, but the scoring doesn't use those yet.

Your profile says: favorite genre, favorite mood, target energy, and whether you like acoustic songs.

Each song gets points added up like this:

- Same genre as you asked for? +2 points.
- Same mood as you asked for? +1 point.
- Energy close to what you wanted? Up to +2 points, and it's not all-or-nothing — close counts, so a near-miss still earns most of the points.
- You said you like acoustic, and the song is acoustic enough? +1 point.

Add it all up, sort every song by total points, and hand back the top 5 with a note on which rules fired.

The one change from the starter version: the point values (2, 1, 2, 1) used to be locked in. Now they can be swapped out, so we could actually test "what if energy mattered more than genre" instead of just guessing.

---

## 4. Data

Describe the dataset the model uses.

Prompts:

- How many songs are in the catalog
- What genres or moods are represented
- Did you add or remove data
- Are there parts of musical taste missing in the dataset

18 songs total. 15 different genres, but 13 of them only have ONE song — lofi has 3, pop has 2, everything else (rock, metal, classical, EDM, jazz, and so on) is a genre of one. Moods are similar: chill has 3, happy and intense have 2 each, the other 11 moods each show up exactly once.

Energy ranges from 0.20 (Moonlit Sonata Reimagined) up to 0.97 (Iron Descent), but there's a gap between 0.55 and 0.72 — nothing in that "medium-high" energy zone. We didn't add or remove any songs, just tested against the dataset as-is.

Missing from the data: no lyrics, no real listening history, no way to tell if two "I like pop" fans actually want the same thing, and no use (yet) of the tempo/valence/danceability numbers that are already sitting in the file.

---

## 5. Strengths

Where does your system seem to work well

Prompts:

- User types for which it gives reasonable results
- Any patterns you think your scoring captures correctly
- Cases where the recommendations matched your intuition

Works best when a profile closely matches a real song in the catalog. Chill Lofi's #1 pick, Library Rain, hit every single feature — genre, mood, energy, and acoustic-ness — and scored the max possible points.

Some of the best picks weren't even the "right" genre. Ambient and jazz songs showed up near the top of the Chill Lofi list even though neither is labeled "lofi," just because their energy, mood, and acoustic feel matched so closely. That's the kind of pick a real human music nerd might make too, which is a good sign the energy and acoustic scoring are pulling real weight, not just genre.

It also doesn't crash or return garbage on most weird input — unknown genres, blank fields, energy way out of range — it just quietly stops giving credit for the parts that don't apply and moves on.

Energy matching feels natural: a near-miss still scores well instead of falling off a cliff, so "pretty close" energy shows up the way a real listener would expect it to.

---

## 6. Limitations and Bias

Where the system struggles or behaves unfairly.

Prompts:

- Features it does not consider
- Genres or moods that are underrepresented
- Cases where the system overfits to one preference
- Ways the scoring might unintentionally favor some users

When we tested a profile asking for a "peaceful" mood at low energy (0.35) but a "rock" genre preference, the recommender still ranked Storm Runner — the catalog's only rock song, energy 0.91, mood "intense" — above Moonlit Sonata Reimagined, a song that matched the requested mood and energy almost exactly. This happened because a genre match is worth twice as many points as a mood match, so it can override an explicit mood and energy preference whenever the genre-matching song is a poor fit on every other axis. The effect hits niche genres hardest: rock, metal, and classical each have only one song in the catalog, so there's no second, better-fitting option to fall back on, and that single mismatched track gets pushed to the top regardless of whether it captures what the user actually asked for. Doubling the energy weight and halving the genre weight fixed this specific case in testing, which suggests the default scoring can favor a category label over the qualities the user actually described.

---

## 7. Evaluation

How you checked whether the recommender behaved as expected.

Prompts:

- Which user profiles you tested
- What you looked for in the recommendations
- What surprised you
- Any simple tests or comparisons you ran

No need for numeric metrics unless you created some.

### Profiles tested

- **High-Energy Pop** — upbeat pop, euphoric mood, energy 0.85.
- **Chill Lofi** — relaxed lofi, chill mood, energy 0.35, likes acoustic songs.
- **Deep Intense Rock** — rock, intense mood, energy 0.9.
- **Conflicting Energy/Mood** — rock genre, but a "peaceful" mood at energy 0.95 (an intentionally contradictory ask).
- **Calm Rock Contradiction** — rock genre again, "peaceful" mood, but this time energy 0.35 — built to check whether the system would still force a rock song to the top even when nothing else about the request fits rock.
- **Acoustic Paradox** — aggressive metal at high energy, but also says they like acoustic songs.
- A handful of "broken input" profiles: an unknown genre ("k-pop"), a genre typed with different capitalization, blank genre/mood, an energy value way outside the normal range, and a profile missing the genre field entirely.

### What surprised me

Leaving out the genre field entirely didn't just get ignored — it crashed the program, because the code assumes every profile has a genre to compare. A capitalization difference ("Lofi" vs. "lofi") also quietly broke matching instead of raising any warning, which is arguably worse than crashing since it fails silently. The biggest surprise was that asking for rock at low energy and a peaceful mood still put the catalog's one rock song (high energy, "intense" mood) in first place — genre out-ranked the two things I'd actually described in more detail. Doubling how much energy counts and halving how much genre counts fixed that one case, but for most other profiles it changed nothing about the actual ranking — a reminder that a "big" looking tweak to the scoring can still be a no-op if you don't check whether the order of results actually changed.

### Comparing the profiles

- **High-Energy Pop vs. Chill Lofi** — zero overlap in the top 5. Makes sense: the two profiles disagree on every axis (genre, mood, energy, acoustic preference), so nothing in one list has a reason to also show up in the other.
- **High-Energy Pop vs. Deep Intense Rock** — these actually share 4 of their 5 top songs (Storm Runner, Gym Hero, Pulse Horizon, Carnival Sol), just in a different order and with different scores. Both profiles want energy around 0.85–0.9, so they're pulling from the same "loud" corner of the catalog; the one song that differs (Sunrise City vs. Iron Descent) is decided by which genre — pop or rock — gets the bonus.
- **Chill Lofi vs. Deep Intense Rock** — zero overlap, and closer to opposite than High-Energy Pop is. Energy targets are almost as far apart as they can be (0.35 vs. 0.9), so this pair confirms energy is doing real separating work, not just genre.
- **Conflicting Energy/Mood vs. Calm Rock Contradiction** — same genre (rock) and same mood request ("peaceful"), only the target energy changes (0.95 vs. 0.35). In the first, the one rock song's actual energy (0.91) happens to be close to what was asked, so it wins by a wide margin. In the second, that same rock song's energy is now far from the target, yet it _still_ narrowly won — proving genre alone, without real energy or mood support, was enough to win. Comparing these two side by side makes the genre-bias problem visible in a way neither profile shows on its own.
- **Calm Rock Contradiction under default weights vs. under energy-doubled/genre-halved weights** — under the original scoring, the mismatched rock song narrowly beat the song that actually matched the mood and energy request. Under the reweighted version, the well-matched song jumped to first place and the rock song dropped out of the top 5 entirely. Makes sense — once energy differences count for more, a song that's dramatically off on energy can no longer make up the difference with genre alone.

---

## 8. Future Work

Ideas for how you would improve the model next.

Prompts:

- Additional features or preferences
- Better ways to explain recommendations
- Improving diversity among the top results
- Handling more complex user tastes

1. Make a bad energy or mood mismatch actually cost points instead of just earning zero — right now genre can quietly cover for a song that's a bad fit on everything else.
2. Use the tempo/valence/danceability numbers that already exist in the data to break ties, instead of just falling back on whichever song happens to be listed first in the file.
3. Let a profile hold more than one favorite genre or mood — real people don't like just one thing, and right now the system can't represent that at all.

---

## 9. Personal Reflection

A few sentences about your experience.

Prompts:

- What you learned about recommender systems
- Something unexpected or interesting you discovered
- How this changed the way you think about music recommendation apps

Building this made recommenders feel a lot less like magic. It's really just a point system — add up a few numbers, sort, done. What decides whether it "feels right" isn't some deep understanding of music, it's which numbers someone chose to make bigger.

**My biggest learning moment** was building the "Calm Rock Contradiction" test on purpose to catch genre in the act. I already suspected genre was too strong, but suspecting it and watching it happen are different things — seeing the one rock song beat a way-better-fitting song by name, then watching that flip the moment I changed one weight, is what actually made the bias click for me. It wasn't abstract anymore, it was two specific songs and two specific numbers.

**How AI helped, and where I double-checked it:** Claude was fastest at the stuff I didn't want to do by hand — designing edge-case profiles on purpose to break things, predicting the math before running it, and writing up long comparisons quickly. But "predicting the math" is exactly where I made sure to check its work — I had it actually run the code and show me the real output instead of trusting the arithmetic on paper, since a hand-waved prediction and a real ranking aren't always the same thing. I also double-checked anything that sounded like an opinion dressed up as fact, like which recommendations "feel right" musically — that's a judgment call, not something AI can just be correct about, so I used its take as a starting point to push back on, not a verdict to accept.

**What surprised me about something this simple "feeling" like a recommendation:** ambient and jazz songs landed near the top of my chill lofi list even though neither is labeled lofi at all — they just happened to have almost identical energy and acoustic-ness. That felt like the system actually understood a "vibe," but it was really just a few numbers landing close together. It's a little unsettling how convincing four numbers can be.

**What I'd try next:** actually fix genre overpowering mood instead of just documenting it, let a profile hold more than one favorite genre or mood since nobody likes just one thing, and start using the tempo/valence/danceability columns that have been sitting unused this whole time. I'd also want to test all of this again on a much bigger, more evenly-balanced catalog, to see if the single-song-genre bias I found here gets better, worse, or just harder to spot at scale.
