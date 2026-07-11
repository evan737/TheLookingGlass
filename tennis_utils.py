import re


def normalize_player_name(name):
    """
    Reduces a player name down to just the lowercased surname for matching
    purposes. Handles two conventions:
      - "Surname, Firstname" (e.g. odds-api.io: "Muchova, Karolina") -> takes
        the part before the comma
      - "Firstname Surname" (e.g. likely Kalshi format: "Novak Djokovic") ->
        takes the last word

    Caveat: this will collide on genuinely shared surnames (rare in ATP/WTA
    draws, but not impossible). Good enough as a starting heuristic; worth
    tightening if a mismatch shows up in practice.
    """
    if not name:
        return ""
    name = name.strip()
    if "," in name:
        surname_part = name.split(",")[0]
    else:
        parts = name.split()
        surname_part = parts[-1] if parts else ""
    return re.sub(r"[^a-zA-Z]", "", surname_part).lower()