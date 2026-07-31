"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import argparse
import logging

from tabulate import tabulate

from src.recommender import (
    DEFAULT_ARTIST_PENALTY,
    DEFAULT_WEIGHTS,
    RANKING_STRATEGIES,
    ProfileValidationError,
    load_songs,
    recommend_with_strategy,
)
from src.reliability import AgreementResult, compute_agreement, confidence_label

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the music recommender simulation.")
    parser.add_argument(
        "--mode",
        choices=sorted(RANKING_STRATEGIES),
        default="balanced",
        help="Ranking strategy used for the core and edge-case profiles (default: balanced).",
    )
    parser.add_argument(
        "--diversify",
        action="store_true",
        help="Penalize repeat artists in the top-k so one artist can't dominate the list.",
    )
    parser.add_argument(
        "--artist-penalty",
        type=float,
        default=DEFAULT_ARTIST_PENALTY,
        help=f"Points deducted per repeat artist when --diversify is set (default: {DEFAULT_ARTIST_PENALTY}).",
    )
    return parser.parse_args()


def format_recommendations(recommendations) -> str:
    """Render (song, score, explanation) tuples as a readable table, reasons included."""
    rows = [
        [i + 1, song["title"], song["artist"], f"{score:.2f}", explanation]
        for i, (song, score, explanation) in enumerate(recommendations)
    ]
    return tabulate(
        rows,
        headers=["#", "Title", "Artist", "Score", "Why"],
        tablefmt="fancy_grid",
        maxcolwidths=[None, 20, 16, None, 45],
    )


def format_confidence(agreement: AgreementResult, label: str) -> str:
    """Render an AgreementResult as a confidence line, with a warning banner if Low."""
    line = (
        f"Confidence: {label} ({agreement.confidence:.2f}) "
        f"— #1 agreement {agreement.top1_agreement:.0%}, top-5 overlap {agreement.avg_jaccard:.0%}"
    )
    if label == "Low":
        line = (
            f"⚠  LOW CONFIDENCE — the ranking strategies disagree significantly on this "
            f"recommendation; treat it with caution.\n{line}"
        )
    return line


def main() -> None:
    args = parse_args()
    songs = load_songs("data/songs.csv")
    mode_label = RANKING_STRATEGIES[args.mode].name

    # Taste profiles: keys map to the features identified in Step 1 (see README
    # "Features used"): genre/mood are matched categorically, energy is compared
    # by closeness, and likes_acoustic flags a preference for higher acousticness.
    user_profiles = {
        "High-Energy Pop": {
            "genre": "pop",
            "mood": "euphoric",
            "energy": 0.85,
            "likes_acoustic": False,
        },
        "Chill Lofi": {
            "genre": "lofi",
            "mood": "chill",
            "energy": 0.35,
            "likes_acoustic": True,
        },
        "Deep Intense Rock": {
            "genre": "rock",
            "mood": "intense",
            "energy": 0.9,
            "likes_acoustic": False,
        },
    }

    diversify_label = f", diversify (penalty {args.artist_penalty})" if args.diversify else ""
    print(f"\nRanking mode: {mode_label} ({args.mode}){diversify_label}")
    for profile_name, user_prefs in user_profiles.items():
        try:
            recommendations = recommend_with_strategy(
                user_prefs,
                songs,
                k=5,
                mode=args.mode,
                diversify=args.diversify,
                artist_penalty=args.artist_penalty,
            )

            agreement = compute_agreement(user_prefs, songs, k=5)
        except ProfileValidationError as exc:
            print(f"\n=== {profile_name} ===")
            print(f"-> INVALID PROFILE: {exc}")
            continue
        except Exception as exc:
            print(f"\n=== {profile_name} ===")
            print(f"-> FAILED: {type(exc).__name__}: {exc}")
            continue

        label = confidence_label(agreement.confidence)

        print(f"\n=== {profile_name} ===")
        print(format_recommendations(recommendations))
        print(format_confidence(agreement, label))

    # Adversarial / edge-case profiles: each targets a specific weak point in
    # score_song (contradictory signals, missing keys, case sensitivity,
    # out-of-range values, empty strings) to see whether it crashes or
    # silently produces nonsensical recommendations.
    edge_case_profiles = {
        "Conflicting Energy/Mood": {
            "genre": "rock",
            "mood": "peaceful",
            "energy": 0.95,
            "likes_acoustic": False,
        },
        "Acoustic Paradox": {
            "genre": "metal",
            "mood": "aggressive",
            "energy": 0.9,
            "likes_acoustic": True,
        },
        "Missing Genre Key": {
            "mood": "chill",
            "energy": 0.4,
        },
        "Case Mismatch": {
            "genre": "Lofi",
            "mood": "Chill",
            "energy": 0.3,
            "likes_acoustic": True,
        },
        "Unknown Genre": {
            "genre": "k-pop",
            "mood": "happy",
            "energy": 0.7,
            "likes_acoustic": False,
        },
        "Out-of-Range Energy": {
            "genre": "EDM",
            "mood": "euphoric",
            "energy": 5.0,
            "likes_acoustic": False,
        },
        "Empty Genre/Mood": {
            "genre": "",
            "mood": "",
            "energy": 0.5,
            "likes_acoustic": False,
        },
    }

    print("\n\n############ EDGE CASE PROFILES ############")
    for profile_name, user_prefs in edge_case_profiles.items():
        print(f"\n=== [EDGE CASE] {profile_name} ===")
        print(f"Profile: {user_prefs}")
        try:
            recommendations = recommend_with_strategy(
                user_prefs,
                songs,
                k=5,
                mode=args.mode,
                diversify=args.diversify,
                artist_penalty=args.artist_penalty,
            )
        except ProfileValidationError as exc:
            print(f"-> INVALID PROFILE: {exc}")
            continue
        except Exception as exc:
            print(f"-> FAILED: {type(exc).__name__}: {exc}")
            continue

        print(format_recommendations(recommendations))

    # Experiment: Weight Shift — double the importance of energy, halve genre.
    # Reruns the same profiles under both weight sets so we can compare
    # rankings side by side and see whether genre was overpowering mood/energy.
    shifted_weights = {**DEFAULT_WEIGHTS, "genre": 1.0, "energy": 4.0}
    experiment_profiles = {
        **user_profiles,
        "Conflicting Energy/Mood": edge_case_profiles["Conflicting Energy/Mood"],
        # Purpose-built to force a ranking flip: the only "rock" song (Storm
        # Runner) is high-energy, but this profile targets low energy and the
        # "peaceful" mood that belongs to a different song (Moonlit Sonata
        # Reimagined). Under default weights genre narrowly keeps the
        # energy-mismatched rock song on top; doubling energy's weight should
        # let the mood+energy match overtake it.
        "Calm Rock Contradiction": {
            "genre": "rock",
            "mood": "peaceful",
            "energy": 0.35,
            "likes_acoustic": False,
        },
    }

    print("\n\n############ EXPERIMENT: WEIGHT SHIFT (genre halved, energy doubled) ############")
    print(f"Default weights:  {DEFAULT_WEIGHTS}")
    print(f"Shifted weights:  {shifted_weights}")

    for profile_name, user_prefs in experiment_profiles.items():
        default_recs = recommend_with_strategy(user_prefs, songs, k=5, mode="balanced")
        shifted_recs = recommend_with_strategy(
            user_prefs, songs, k=5, mode="balanced", weights=shifted_weights
        )

        print(f"\n=== {profile_name} ===")
        print(f"Profile: {user_prefs}\n")

        print("-- Default weights --")
        print(format_recommendations(default_recs))

        print("\n-- Shifted weights (genre 1.0, energy x4) --")
        print(format_recommendations(shifted_recs))

    # Ranking mode comparison: run one profile through every strategy in
    # RANKING_STRATEGIES, using the *shifted* weights (genre already
    # de-emphasized) so the comparison isolates what mode alone changes.
    # Under shifted weights, Balanced already stops favoring the mismatched
    # rock song (see the weight-shift experiment above) - but Genre-First
    # still forces it to #1 regardless of weights, because its tier is a
    # hard rule, not a score. That's the actual difference between "tune the
    # weights" and "change the ranking strategy."
    mode_comparison_profile = experiment_profiles["Calm Rock Contradiction"]

    print("\n\n############ RANKING MODE COMPARISON (Calm Rock Contradiction, shifted weights) ############")
    print(f"Profile: {mode_comparison_profile}")
    print(f"Weights: {shifted_weights}")
    for mode_key, strategy in RANKING_STRATEGIES.items():
        recommendations = recommend_with_strategy(
            mode_comparison_profile, songs, k=5, mode=mode_key, weights=shifted_weights
        )
        print(f"\n-- {strategy.name} ({mode_key}) --")
        print(format_recommendations(recommendations))

    # Diversity comparison: "Chill Lofi" pulls two of its top picks from the
    # same artist (LoRoom - Midnight Coding and Focus Flow), a mini "filter
    # bubble" where one artist quietly takes multiple slots just because both
    # songs fit the profile well. Compare with/without --diversify to show
    # the artist penalty spreading the list out instead.
    diversity_profile_name = "Chill Lofi"
    diversity_profile = user_profiles[diversity_profile_name]

    print(f"\n\n############ DIVERSITY COMPARISON ({diversity_profile_name}) ############")
    print(f"Profile: {diversity_profile}")

    plain_recs = recommend_with_strategy(diversity_profile, songs, k=5, mode="balanced")
    diverse_recs = recommend_with_strategy(
        diversity_profile, songs, k=5, mode="balanced", diversify=True
    )

    print("\n-- Without diversity penalty --")
    print(format_recommendations(plain_recs))

    print(f"\n-- With diversity penalty (-{DEFAULT_ARTIST_PENALTY} per repeat artist) --")
    print(format_recommendations(diverse_recs))


if __name__ == "__main__":
    main()
