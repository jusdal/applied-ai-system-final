"""
Reliability/confidence scoring for the ranking-strategy ensemble.

The three ranking strategies in RANKING_STRATEGIES are an implicit ensemble:
they all score songs with the same score_song, but disagree on how to order
them. When they agree on what to recommend, that's a signal the pick is
robust to *how* you rank, not just how you score. When they don't agree,
the "best" recommendation is more a matter of which strategy happened to be
selected. compute_agreement() turns that agreement (or lack of it) into a
single 0-1 confidence score the CLI can show next to the recommendation
table.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.recommender import RANKING_STRATEGIES, validate_user_prefs

TOP1_WEIGHT = 0.6
JACCARD_WEIGHT = 0.4

HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.45


@dataclass
class AgreementResult:
    confidence: float
    top1_agreement: float
    avg_jaccard: float
    top1_unanimous: bool
    top1_by_mode: Dict[str, str]


def _song_key(song: Dict):
    """Identify a song across strategies (songs.csv rows always carry an id)."""
    if "id" in song:
        return song["id"]
    return (song.get("title"), song.get("artist"))


def _jaccard(a: set, b: set) -> float:
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def compute_agreement(
    user_prefs: Dict,
    songs: List[Dict],
    weights: Optional[Dict] = None,
    k: int = 5,
) -> AgreementResult:
    """
    Run every strategy in RANKING_STRATEGIES against the same user_prefs/songs
    and measure how much they agree: whether they pick the same #1 song, and
    how much their top-k lists overlap (average pairwise Jaccard). Returns an
    AgreementResult whose `confidence` combines both signals into one score.
    """
    validate_user_prefs(user_prefs)

    top_k_by_mode: Dict[str, List] = {}
    top1_by_mode: Dict[str, str] = {}

    for mode, strategy in RANKING_STRATEGIES.items():
        ranked = strategy.rank(user_prefs, songs, weights)
        top_k = ranked[:k]
        top_k_by_mode[mode] = top_k
        if top_k:
            top1_by_mode[mode] = top_k[0][0].get("title", str(_song_key(top_k[0][0])))

    top1_keys = [_song_key(top_k[0][0]) for top_k in top_k_by_mode.values() if top_k]
    if top1_keys:
        counts = Counter(top1_keys)
        top1_agreement = counts.most_common(1)[0][1] / len(top1_keys)
        top1_unanimous = len(counts) == 1
    else:
        top1_agreement = 0.0
        top1_unanimous = False

    key_sets = [
        {_song_key(song) for song, _, _ in top_k}
        for top_k in top_k_by_mode.values()
    ]
    pair_scores = [
        _jaccard(key_sets[i], key_sets[j])
        for i in range(len(key_sets))
        for j in range(i + 1, len(key_sets))
    ]
    avg_jaccard = sum(pair_scores) / len(pair_scores) if pair_scores else 1.0

    confidence = TOP1_WEIGHT * top1_agreement + JACCARD_WEIGHT * avg_jaccard

    return AgreementResult(
        confidence=confidence,
        top1_agreement=top1_agreement,
        avg_jaccard=avg_jaccard,
        top1_unanimous=top1_unanimous,
        top1_by_mode=top1_by_mode,
    )


def confidence_label(score: float) -> str:
    """Map a 0-1 confidence score to a High/Medium/Low label."""
    if score >= HIGH_THRESHOLD:
        return "High"
    if score >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"
