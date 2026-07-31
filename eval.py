"""
eval.py - Evaluation harness for the music recommender's reliability pipeline.

Runs the 3 core taste profiles and 6 adversarial/edge-case profiles documented
in README.md through the full pipeline (validate_user_prefs ->
recommend_with_strategy -> compute_agreement), confirms nothing crashes
unexpectedly, confirms a confidence score/label comes out the other end, and
checks whether validation caught the adversarial inputs it's supposed to.

Reuses src/recommender.py and src/reliability.py directly - no scoring or
ranking logic is reimplemented here.

Usage:
    python eval.py

Exits 0 if every profile passes, 1 if any profile fails (CI-friendly).
"""

import sys

from tabulate import tabulate

from src.recommender import (
    ProfileValidationError,
    load_songs,
    recommend_with_strategy,
    validate_user_prefs,
)
from src.reliability import compute_agreement, confidence_label

# (profile_name, user_prefs, is_adversarial, expect_valid)
# expect_valid = True  -> profile should pass validate_user_prefs and get scored
# expect_valid = False -> profile should be rejected by validate_user_prefs
PROFILES = [
    # --- Core taste profiles ---
    ("High-Energy Pop", {"genre": "pop", "mood": "euphoric", "energy": 0.85, "likes_acoustic": False}, False, True),
    ("Chill Lofi", {"genre": "lofi", "mood": "chill", "energy": 0.35, "likes_acoustic": True}, False, True),
    ("Deep Intense Rock", {"genre": "rock", "mood": "intense", "energy": 0.9, "likes_acoustic": False}, False, True),
    # --- Adversarial / edge-case profiles ---
    ("Missing Genre Key", {"mood": "chill", "energy": 0.4}, True, False),
    ("Case Mismatch", {"genre": "Lofi", "mood": "Chill", "energy": 0.3, "likes_acoustic": True}, True, True),
    ("Unknown Genre", {"genre": "k-pop", "mood": "happy", "energy": 0.7, "likes_acoustic": False}, True, True),
    ("Out-of-Range Energy", {"genre": "EDM", "mood": "euphoric", "energy": 5.0, "likes_acoustic": False}, True, False),
    ("Empty Genre/Mood", {"genre": "", "mood": "", "energy": 0.5, "likes_acoustic": False}, True, False),
    ("Conflicting Energy/Mood", {"genre": "rock", "mood": "peaceful", "energy": 0.95, "likes_acoustic": False}, True, True),
    # energy=True is a bool, which Python's isinstance(x, int) treats as numeric
    # and 0 <= True <= 1 is also true - validate_user_prefs must explicitly
    # exclude bool to reject this rather than silently scoring energy=1.0.
    ("Boolean Energy", {"genre": "pop", "mood": "happy", "energy": True, "likes_acoustic": False}, True, False),
]


def run_profile(name, user_prefs, is_adversarial, expect_valid, songs):
    """
    Run one profile through validate_user_prefs -> recommend_with_strategy ->
    compute_agreement. Returns a dict describing what happened.
    """
    result = {
        "name": name,
        "adversarial": is_adversarial,
        "passed": False,
        "label": "-",
        "notes": "",
    }

    try:
        validate_user_prefs(dict(user_prefs))
        validation_caught = False
    except ProfileValidationError as exc:
        validation_caught = True
        validation_message = str(exc)
    except Exception as exc:  # unexpected crash out of validation itself
        result["notes"] = f"CRASH in validation: {type(exc).__name__}: {exc}"
        return result

    if validation_caught:
        if expect_valid:
            # Adversarial cases only "expect_valid=False" when we deliberately
            # built them to be rejected; a core/expect-valid profile getting
            # rejected is a real failure.
            result["notes"] = f"validation unexpectedly rejected input: {validation_message}"
            result["passed"] = False
        else:
            result["passed"] = True
            result["notes"] = "validation caught invalid input as expected (no crash)"
        return result

    # Validation passed - it should have caught this one but didn't.
    if is_adversarial and not expect_valid:
        result["notes"] = "validation gap: expected rejection, but input passed validation"
        result["passed"] = False
        # fall through and still try to score it, so we can see how bad it gets

    try:
        recommend_with_strategy(user_prefs, songs, k=5)
        agreement = compute_agreement(user_prefs, songs, k=5)
        label = confidence_label(agreement.confidence)
    except Exception as exc:
        result["notes"] = f"CRASH: {type(exc).__name__}: {exc}"
        result["passed"] = False
        return result

    result["label"] = f"{label} ({agreement.confidence:.2f})"

    if not result["notes"]:
        if is_adversarial:
            result["notes"] = "validation passed input through as expected; scored without crashing"
        else:
            result["notes"] = "processed normally"
        result["passed"] = True

    return result


def main() -> int:
    songs = load_songs("data/songs.csv")

    rows = []
    for name, user_prefs, is_adversarial, expect_valid in PROFILES:
        rows.append(run_profile(name, user_prefs, is_adversarial, expect_valid, songs))

    table = [
        [
            r["name"],
            "PASS" if r["passed"] else "FAIL",
            r["label"],
            r["notes"],
        ]
        for r in rows
    ]

    print("\n============ EVAL SUMMARY ============\n")
    print(
        tabulate(
            table,
            headers=["Profile", "Pass/Fail", "Confidence", "Notes"],
            tablefmt="fancy_grid",
            maxcolwidths=[22, None, None, 55],
        )
    )

    passed = sum(1 for r in rows if r["passed"])
    total = len(rows)
    print(f"\n{passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
