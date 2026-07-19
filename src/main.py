"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from recommender import DEFAULT_WEIGHTS, load_songs, recommend_songs


def main() -> None:
    songs = load_songs("data/songs.csv")

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

    for profile_name, user_prefs in user_profiles.items():
        recommendations = recommend_songs(user_prefs, songs, k=5)

        print(f"\n=== {profile_name} ===")
        print("Top recommendations:\n")
        for rec in recommendations:
            # You decide the structure of each returned item.
            # A common pattern is: (song, score, explanation)
            song, score, explanation = rec
            print(f"{song['title']} - Score: {score:.2f}")
            print(f"Because: {explanation}")
            print()

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
            recommendations = recommend_songs(user_prefs, songs, k=5)
        except Exception as exc:
            print(f"-> FAILED: {type(exc).__name__}: {exc}")
            continue

        print("Top recommendations:\n")
        for rec in recommendations:
            song, score, explanation = rec
            print(f"{song['title']} - Score: {score:.2f}")
            print(f"Because: {explanation}")
            print()

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
        default_recs = recommend_songs(user_prefs, songs, k=5)
        shifted_recs = recommend_songs(user_prefs, songs, k=5, weights=shifted_weights)

        print(f"\n=== {profile_name} ===")
        print(f"Profile: {user_prefs}\n")

        print("-- Default weights --")
        for song, score, explanation in default_recs:
            print(f"{song['title']} - Score: {score:.2f}  ({explanation})")

        print("\n-- Shifted weights (genre 1.0, energy x4) --")
        for song, score, explanation in shifted_recs:
            print(f"{song['title']} - Score: {score:.2f}  ({explanation})")
        print()


if __name__ == "__main__":
    main()
