import csv
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

def _user_prefs_from_profile(user: UserProfile) -> Dict:
    """Adapt a UserProfile's field names to the shape score_song expects."""
    return {
        "genre": user.favorite_genre,
        "mood": user.favorite_mood,
        "energy": user.target_energy,
        "likes_acoustic": user.likes_acoustic,
    }


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py

    Wraps the module-level score_song/recommend_songs functions so the
    class-based and function-based interfaces share one scoring rule.
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        user_prefs = _user_prefs_from_profile(user)
        scored = [
            (song, score_song(user_prefs, asdict(song))[0])
            for song in self.songs
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [song for song, _ in scored[:k]]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        user_prefs = _user_prefs_from_profile(user)
        _, reasons = score_song(user_prefs, asdict(song))
        return ", ".join(reasons) if reasons else "No matching attributes"

NUMERIC_FIELDS = (
    "energy",
    "tempo_bpm",
    "valence",
    "danceability",
    "acousticness",
    "instrumentalness",
    "liveness",
)


def load_songs(csv_path: str) -> List[Dict]:
    """Read songs.csv into a list of dicts, converting numeric fields to int/float."""
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["id"] = int(row["id"])
            for field in NUMERIC_FIELDS:
                if field in row:
                    row[field] = float(row[field])
            songs.append(row)
    print(f"Loaded songs: {len(songs)}")
    return songs

DEFAULT_WEIGHTS = {"genre": 2.0, "mood": 1.0, "energy": 2.0, "acoustic": 1.0}


class ProfileValidationError(ValueError):
    """Raised when a user_prefs/UserProfile dict is missing or has invalid fields."""


def validate_user_prefs(user_prefs: Dict) -> Dict:
    """
    Validate a user_prefs dict before it's used for scoring.

    Checks that genre/mood are present and non-empty, and that energy is a
    number within [0, 1]. Raises ProfileValidationError (and logs it) with a
    clear message instead of letting a bare KeyError/TypeError surface from
    deep inside score_song.
    """
    errors = []

    for field in ("genre", "mood"):
        value = user_prefs.get(field)
        if value is None:
            errors.append(f"missing required field '{field}'")
        elif isinstance(value, str) and value.strip() == "":
            errors.append(f"field '{field}' cannot be empty")

    if "energy" not in user_prefs or user_prefs["energy"] is None:
        errors.append("missing required field 'energy'")
    else:
        energy = user_prefs["energy"]
        if not isinstance(energy, (int, float)) or isinstance(energy, bool):
            errors.append(f"field 'energy' must be numeric, got {energy!r}")
        elif not (0.0 <= energy <= 1.0):
            errors.append(f"field 'energy' must be within [0, 1], got {energy}")

    if errors:
        message = "Invalid user profile: " + "; ".join(errors)
        logger.error(message)
        raise ProfileValidationError(message)

    return user_prefs


def score_song(user_prefs: Dict, song: Dict, weights: Optional[Dict] = None) -> Tuple[float, List[str]]:
    """Score one song against user_prefs using the Algorithm Recipe and return (score, reasons)."""
    weights = weights or DEFAULT_WEIGHTS
    score = 0.0
    reasons = []

    if song["genre"] == user_prefs["genre"]:
        score += weights["genre"]
        reasons.append(f"genre match (+{weights['genre']:.1f})")

    if song["mood"] == user_prefs["mood"]:
        score += weights["mood"]
        reasons.append(f"mood match (+{weights['mood']:.1f})")

    energy_points = max(0.0, weights["energy"] * (1 - abs(song["energy"] - user_prefs["energy"])))
    score += energy_points
    reasons.append(f"energy closeness (+{energy_points:.2f})")

    if user_prefs.get("likes_acoustic") and song["acousticness"] > 0.6:
        score += weights["acoustic"]
        reasons.append(f"acoustic match (+{weights['acoustic']:.1f})")

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5, weights: Optional[Dict] = None) -> List[Tuple[Dict, float, str]]:
    """Score every song against user_prefs and return the top k, sorted highest score first."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, weights)
        scored.append((song, score, ", ".join(reasons)))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


class RankingStrategy(ABC):
    """
    Strategy pattern: each concrete strategy is a different way of ordering
    songs for a user. Every strategy still calls score_song for the per-song
    score and "why" explanation, so the reasons shown to the user always
    reflect the real weighted score - only the sort order changes between
    strategies.
    """

    name: str

    @abstractmethod
    def rank(
        self, user_prefs: Dict, songs: List[Dict], weights: Optional[Dict] = None
    ) -> List[Tuple[Dict, float, str]]:
        """Return every song as (song, score, explanation), best match first."""
        raise NotImplementedError


class BalancedStrategy(RankingStrategy):
    """Default: one weighted sum across genre/mood/energy/acoustic (score_song as-is)."""

    name = "Balanced"

    def rank(self, user_prefs, songs, weights=None):
        return recommend_songs(user_prefs, songs, k=len(songs), weights=weights)


class GenreFirstStrategy(RankingStrategy):
    """
    Genre match acts as a hard tier: every genre-matching song outranks every
    non-matching song, no matter how well the rest of the profile fits. Ties
    within a tier fall back to the normal weighted score.
    """

    name = "Genre-First"

    def rank(self, user_prefs, songs, weights=None):
        scored = []
        for song in songs:
            score, reasons = score_song(user_prefs, song, weights)
            genre_tier = 1 if song["genre"] == user_prefs.get("genre") else 0
            scored.append((song, score, ", ".join(reasons), genre_tier))

        scored.sort(key=lambda item: (item[3], item[1]), reverse=True)
        return [(song, score, reasons) for song, score, reasons, _ in scored]


class EnergySimilarityStrategy(RankingStrategy):
    """
    Ranks purely by how close a song's energy is to the user's target energy.
    Genre/mood/acoustic still appear in the explanation (via score_song) but
    play no part in the ordering.
    """

    name = "Energy-Similarity"

    def rank(self, user_prefs, songs, weights=None):
        scored = []
        for song in songs:
            score, reasons = score_song(user_prefs, song, weights)
            closeness = 1 - abs(song["energy"] - user_prefs["energy"])
            scored.append((song, score, ", ".join(reasons), closeness))

        scored.sort(key=lambda item: item[3], reverse=True)
        return [(song, score, reasons) for song, score, reasons, _ in scored]


RANKING_STRATEGIES: Dict[str, RankingStrategy] = {
    "balanced": BalancedStrategy(),
    "genre-first": GenreFirstStrategy(),
    "energy-similarity": EnergySimilarityStrategy(),
}


DEFAULT_ARTIST_PENALTY = 1.5


def apply_artist_diversity(
    ranked: List[Tuple[Dict, float, str]],
    k: int,
    penalty: float = DEFAULT_ARTIST_PENALTY,
) -> List[Tuple[Dict, float, str]]:
    """
    Greedily rebuild the top-k list so one artist can't quietly take multiple
    slots (a mini "filter bubble") just because their songs happen to fit the
    profile well. Each time an artist is picked, every remaining song by that
    same artist loses `penalty` points before the next pick is chosen - so a
    second song from an already-picked artist has to be a strong enough match
    to still be worth a slot over a first song from someone new.
    """
    remaining = list(ranked)
    artist_counts: Dict[str, int] = {}
    selected: List[Tuple[Dict, float, str]] = []

    while remaining and len(selected) < k:
        remaining.sort(
            key=lambda item: item[1] - artist_counts.get(item[0]["artist"], 0) * penalty,
            reverse=True,
        )
        song, score, reasons = remaining.pop(0)
        repeats = artist_counts.get(song["artist"], 0)
        if repeats:
            score -= repeats * penalty
            reasons = f"{reasons}, diversity penalty (-{repeats * penalty:.1f} for repeat artist)"
        selected.append((song, score, reasons))
        artist_counts[song["artist"]] = repeats + 1

    return selected


def recommend_with_strategy(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    mode: str = "balanced",
    weights: Optional[Dict] = None,
    diversify: bool = False,
    artist_penalty: float = DEFAULT_ARTIST_PENALTY,
) -> List[Tuple[Dict, float, str]]:
    """Rank songs with the named strategy (see RANKING_STRATEGIES) and return the top k."""
    try:
        strategy = RANKING_STRATEGIES[mode]
    except KeyError:
        raise ValueError(
            f"Unknown ranking mode {mode!r}. Choose from {sorted(RANKING_STRATEGIES)}."
        ) from None

    validate_user_prefs(user_prefs)
    ranked = strategy.rank(user_prefs, songs, weights)
    if diversify:
        return apply_artist_diversity(ranked, k, artist_penalty)
    return ranked[:k]
