from liana_survey_shared.scoring import csat_score, nps_score, thumbs_score


def compare_scores(survey_type: str, rows: list[dict]) -> dict:
    groups: dict[str, dict[str, dict[str, int]]] = {"segments": {}, "months": {}}
    for row in rows:
        for category, key in (("segments", row["segment"]), ("months", str(row["month"]))):
            counts = groups[category].setdefault(key, {})
            value = str(int(row["value_number"]))
            counts[value] = counts.get(value, 0) + row["count"]

    def score(counts):
        if survey_type == "nps":
            return nps_score(counts).score
        if survey_type == "thumbs":
            return thumbs_score(counts).positive
        if survey_type == "csat":
            return csat_score(counts).satisfied
        return None

    return {
        category: [
            {"label": key, "score": score(counts), "answers": sum(counts.values())}
            for key, counts in sorted(values.items())
        ]
        for category, values in groups.items()
    }
