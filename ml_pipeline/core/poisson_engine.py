import math


class PoissonEngine:
    """
    Professional Poisson probability engine.

    Uses expected goals (xG) to estimate:

    - Win / Draw / Loss probabilities
    - Correct score probabilities
    - Most likely score
    - Top scorelines
    - BTTS
    - Over / Under goals
    - Clean sheets
    """

    def __init__(self, max_goals: int = 8):
        self.max_goals = max_goals

    # ======================================================
    # POISSON PROBABILITY
    # ======================================================

    def poisson_probability(self, goals: int, expected: float) -> float:

        expected = max(0.01, float(expected))

        return (
            math.exp(-expected)
            * (expected ** goals)
            / math.factorial(goals)
        )

    # ======================================================
    # SCORE MATRIX
    # ======================================================

    def build_score_matrix(
        self,
        home_xg: float,
        away_xg: float,
    ) -> dict:

        matrix = {}

        total = 0.0

        for home in range(self.max_goals + 1):

            home_prob = self.poisson_probability(home, home_xg)

            for away in range(self.max_goals + 1):

                away_prob = self.poisson_probability(away, away_xg)

                probability = home_prob * away_prob

                matrix[(home, away)] = probability

                total += probability

        # Normalize

        if total > 0:

            for score in matrix:

                matrix[score] /= total

        return matrix

    # ======================================================
    # MATCH RESULT
    # ======================================================

    def match_probabilities(self, matrix):

        home = 0.0
        draw = 0.0
        away = 0.0

        for (hg, ag), probability in matrix.items():

            if hg > ag:

                home += probability

            elif hg == ag:

                draw += probability

            else:

                away += probability

        return {
            "home_win": round(home, 4),
            "draw": round(draw, 4),
            "away_win": round(away, 4),
        }

    # ======================================================
    # MOST LIKELY SCORE
    # ======================================================

    def most_likely_score(self, matrix):

        score, probability = max(
            matrix.items(),
            key=lambda item: item[1]
        )

        return {
            "score": f"{score[0]}-{score[1]}",
            "probability": round(probability * 100, 2)
        }

    # ======================================================
    # TOP SCORES
    # ======================================================

    def top_scores(
        self,
        matrix,
        limit=5
    ):

        ordered = sorted(
            matrix.items(),
            key=lambda item: item[1],
            reverse=True
        )[:limit]

        results = []

        for (hg, ag), probability in ordered:

            results.append({

                "score": f"{hg}-{ag}",

                "probability": round(
                    probability * 100,
                    2
                )

            })

        return results

    # ======================================================
    # BOTH TEAMS TO SCORE
    # ======================================================

    def both_teams_to_score(self, matrix):

        probability = sum(

            p

            for (hg, ag), p in matrix.items()

            if hg > 0 and ag > 0

        )

        return round(probability, 4)

    # ======================================================
    # OVER GOALS
    # ======================================================

    def over_probability(
        self,
        matrix,
        line,
    ):

        probability = sum(

            p

            for (hg, ag), p in matrix.items()

            if (hg + ag) > line

        )

        return round(probability, 4)

    # ======================================================
    # UNDER GOALS
    # ======================================================

    def under_probability(
        self,
        matrix,
        line,
    ):

        probability = sum(

            p

            for (hg, ag), p in matrix.items()

            if (hg + ag) < line

        )

        return round(probability, 4)

    # ======================================================
    # CLEAN SHEETS
    # ======================================================

    def clean_sheet_home(self, matrix):

        probability = sum(

            p

            for (hg, ag), p in matrix.items()

            if ag == 0

        )

        return round(probability, 4)

    def clean_sheet_away(self, matrix):

        probability = sum(

            p

            for (hg, ag), p in matrix.items()

            if hg == 0

        )

        return round(probability, 4)

    # ======================================================
    # FULL PREDICTION
    # ======================================================

    def predict(
        self,
        home_xg,
        away_xg,
    ):

        matrix = self.build_score_matrix(
            home_xg,
            away_xg,
        )

        return {

            "probabilities":
                self.match_probabilities(matrix),

            "most_likely_score":
                self.most_likely_score(matrix),

            "top_scores":
                self.top_scores(matrix),

            "btts":
                round(
                    self.both_teams_to_score(matrix) * 100,
                    2
                ),

            "over_1_5":
                round(
                    self.over_probability(matrix, 1.5) * 100,
                    2
                ),

            "over_2_5":
                round(
                    self.over_probability(matrix, 2.5) * 100,
                    2
                ),

            "over_3_5":
                round(
                    self.over_probability(matrix, 3.5) * 100,
                    2
                ),

            "under_2_5":
                round(
                    self.under_probability(matrix, 2.5) * 100,
                    2
                ),

            "clean_sheet_home":
                round(
                    self.clean_sheet_home(matrix) * 100,
                    2
                ),

            "clean_sheet_away":
                round(
                    self.clean_sheet_away(matrix) * 100,
                    2
                ),

            "score_matrix":
                matrix,

        }