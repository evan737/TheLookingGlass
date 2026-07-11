"""
Infers a rough tournament tier from the tournament/series name, since
Kalshi's market data doesn't directly tag tournament level.

IMPORTANT CAVEAT: this is a name-matching heuristic, not confirmed against
Kalshi's actual full market catalog -- as of building this, only Wimbledon
(a Grand Slam) has been observed live, so the "Masters"/"Tour" categories
below are best guesses about what Kalshi's naming looks like for those
tiers, not yet verified. Also unconfirmed: whether Kalshi lists anything
below ATP/WTA main tour level at all (Challenger, ITF) -- if it doesn't,
the "Tour" bucket here may just mean "not a Slam", not truly obscure.
Revisit this once real non-Slam tournament names show up in the data.
"""

GRAND_SLAM_NAMES = ["wimbledon", "us open", "australian open", "french open", "roland garros"]
MASTERS_NAMES = ["masters", "1000"]


def infer_tournament_tier(name):
    if not name:
        return "Unknown"

    lowered = name.lower()

    if any(slam in lowered for slam in GRAND_SLAM_NAMES):
        return "Grand Slam"
    if any(masters in lowered for masters in MASTERS_NAMES):
        return "Masters 1000"
    if "challenger" in lowered:
        return "Challenger"
    if "itf" in lowered:
        return "ITF"

    return "Tour (250/500)"