import logging
import joblib
import numpy as np
import os

from ml_pipeline.train_model import MODELS_DIR

logger = logging.getLogger(__name__)


class PredictionEngine:

    def __init__(
        self,
        model,
        scaler,
        encoder,
        elo,
        team_stats,
    ):

        self.model = model
        self.scaler = scaler
        self.encoder = encoder
        self.elo = elo
        self.team_stats = team_stats

    # =====================================================
    # FEATURE COLUMNS (cached; reloaded if retraining rewrites the file)
    # =====================================================

    def _feature_columns(self):
        path = os.path.join(MODELS_DIR, "feature_columns.pkl")
        mtime = os.path.getmtime(path)

        cached = getattr(self, "_fc_cache", None)

        if cached is None or cached[0] != mtime:
            self._fc_cache = (mtime, joblib.load(path))

        return self._fc_cache[1]

    # =====================================================
    # SAFE LOOKUPS
    # =====================================================

    def get_team_elo(self, team):

        rating = self.elo.get(team, 1500)

        return (float(rating) - 1500.0) / 400.0

    def get_team_stat(
        self,
        team,
        field,
        default=0.5,
    ):

        stats = self.team_stats.get(team)

        if stats is None:
            return default

        value = stats.get(field, default)

        # Older artifacts used American spelling.  New artifacts use the
        # feature name used throughout training, while this keeps deployed
        # models readable until they are retrained.
        if field == "defence" and field not in stats:
            value = stats.get("defense", default)

        if value is None:
            return default

        try:
            return float(value)

        except Exception:
            return default

    # =====================================================
    # TEAM FORM
    # =====================================================

    def calculate_form(
        self,
        team,
    ):

        stats = self.team_stats.get(team, {})

        if "form" in stats:

            try:
                return float(stats["form"])
            except Exception:
                pass

        matches = stats.get("last_matches", [])

        if not matches:
            return 0.5

        score_map = {

            "win": 1.0,

            "draw": 0.5,

            "loss": 0.0,

        }

        values = [

            score_map.get(result, 0.5)

            for result in matches[-5:]

        ]

        return float(sum(values) / len(values))

    # =====================================================
    # RECENT GOALS
    # =====================================================

    def recent_goals_scored(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("recent_goals_scored", 0)
        )


    def recent_goals_conceded(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("recent_goals_conceded", 0)
        )

    # =====================================================
    # HOME / AWAY FORM
    # =====================================================

    def home_form(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("home_form", 0.5),
            0.5,
        )


    def away_form(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("away_form", 0.5),
            0.5,
        )

    # =====================================================
    # REST DAYS
    # =====================================================

    def rest_days(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("rest_days", 5),
            5,
        )

    # =====================================================
    # XG
    # =====================================================

    def recent_xg(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("recent_xg", 1.2),
            1.2,
        )


    def recent_xga(self, team):

        stats = self.team_stats.get(team, {})

        return self.safe_float(
            stats.get("recent_xga", 1.2),
            1.2,
        )

    # =====================================================
    # SAFE CONVERSIONS
    # =====================================================

    def safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def safe_average(self, values, default=0.0):
        if not values or not isinstance(values, (list, tuple)):
            return default
        try:
            filtered = [float(v) for v in values if v is not None]
            if not filtered:
                return default
            return sum(filtered) / len(filtered)
        except (TypeError, ValueError):
            return default

    # =====================================================
    # PROBABILITY CALIBRATION
    # =====================================================

    def softmax_smooth(
        self,
        probabilities,
        temperature=1.40,
    ):

        probs = np.asarray(
            probabilities,
            dtype=float,
        )

        probs = np.clip(
            probs,
            1e-9,
            1.0,
        )

        logits = np.log(probs)

        logits /= temperature

        logits -= np.max(logits)

        exp = np.exp(logits)

        total = exp.sum()

        if total <= 0 or np.isnan(total):

            logger.warning(
                "Probability calibration failed."
            )

            return np.array(
                [
                    0.34,
                    0.33,
                    0.33,
                ]
            )

        return exp / total
    
    # =====================================================
    # FEATURE ENGINEERING
    # MUST MATCH train_model.py EXACTLY
    # =====================================================

    def build_features(
        self,
        home_team,
        away_team,
    ):

        # -------------------------------------------------
        # Team Encoding
        # -------------------------------------------------

        try:
            home_enc = float(
                self.encoder.transform([home_team])[0]
            )

        except Exception:

            logger.warning(
                "Unknown team: %s",
                home_team,
            )

            home_enc = -1.0

        try:
            away_enc = float(
                self.encoder.transform([away_team])[0]
            )

        except Exception:

            logger.warning(
                "Unknown team: %s",
                away_team,
            )

            away_enc = -1.0

        home_recent_points = self.team_value(
            home_team,
            "recent_points",
        )
        away_recent_points = self.team_value(
            away_team,
            "recent_points",
        )

        home_recent_goals = self.team_value(
            home_team,
            "recent_goals_scored",
        )
        away_recent_goals = self.team_value(
            away_team,
            "recent_goals_scored",
        )

        home_recent_conceded = self.team_value(
            home_team,
            "recent_goals_conceded",
        )
        away_recent_conceded = self.team_value(
            away_team,
            "recent_goals_conceded",
        )

        home_unbeaten = self.team_value(
            home_team,
            "unbeaten",
        )
        away_unbeaten = self.team_value(
            away_team,
            "unbeaten",
        )

        home_strength = self.team_value(
            home_team,
            "home_strength",
        )
        away_strength = self.team_value(
            away_team,
            "away_strength",
        )

        # -------------------------------------------------
        # Elo
        # -------------------------------------------------

        home_elo = self.get_team_elo(home_team)
        away_elo = self.get_team_elo(away_team)

        elo_difference = (
            home_elo -
            away_elo
        )

        # -------------------------------------------------
        # Form
        # -------------------------------------------------

        home_form = self.calculate_form(
            home_team
        )

        away_form = self.calculate_form(
            away_team
        )

        form_difference = (
            home_form -
            away_form
        )

        # -------------------------------------------------
        # Attack
        # -------------------------------------------------

        home_attack = self.get_team_stat(
            home_team,
            "attack",
        )

        away_attack = self.get_team_stat(
            away_team,
            "attack",
        )

        attack_difference = (
            home_attack -
            away_attack
        )

        # -------------------------------------------------
        # Defence
        # -------------------------------------------------

        home_defence = self.get_team_stat(
            home_team,
            "defence",
        )

        away_defence = self.get_team_stat(
            away_team,
            "defence",
        )

        defence_difference = (
            home_defence -
            away_defence
        )

        # -------------------------------------------------
        # Average Goals
        # -------------------------------------------------

        home_avg_scored = self.get_team_stat(
            home_team,
            "avg_scored",
        )

        away_avg_scored = self.get_team_stat(
            away_team,
            "avg_scored",
        )

        home_avg_conceded = self.get_team_stat(
            home_team,
            "avg_conceded",
        )

        away_avg_conceded = self.get_team_stat(
            away_team,
            "avg_conceded",
        )

        # -----------------------------------------------
        # Goal Difference
        # -------------------------------------------------

        home_goal_difference = self.get_team_stat(
            home_team,
            "goal_difference",
        )

        away_goal_difference = self.get_team_stat(
            away_team,
            "goal_difference",
        )

        goal_difference = (
            home_goal_difference -
            away_goal_difference
     )

        recent_points_difference = (
            home_recent_points -
            away_recent_points
        )

        home_recent_goal_difference = self.team_value(
            home_team,
            "recent_goal_difference",
        )

        away_recent_goal_difference = self.team_value(
            away_team,
            "recent_goal_difference",
        )

        recent_goal_difference = (
            home_recent_goal_difference -
            away_recent_goal_difference
        )

        # Recent conceded difference (home - away)
        recent_conceded_difference = (
            home_recent_conceded -
            away_recent_conceded
        )

        strength_difference = (
            home_strength -
            away_strength
        )

        # -------------------------------------------------
        # Win Rate
        # -------------------------------------------------

        home_win_rate = self.get_team_stat(
            home_team,
            "win_rate",
        )

        away_win_rate = self.get_team_stat(
            away_team,
            "win_rate",
        )

        win_rate_difference = (
            home_win_rate -
            away_win_rate
        )

        # -------------------------------------------------
        # Clean Sheets
        # -------------------------------------------------

        home_clean_sheet_rate = self.get_team_stat(
            home_team,
            "clean_sheet_rate",
        )

        away_clean_sheet_rate = self.get_team_stat(
            away_team,
            "clean_sheet_rate",
        )

        home_recent_goals = self.recent_goals_scored(home_team)
        away_recent_goals = self.recent_goals_scored(away_team)

        home_recent_conceded = self.recent_goals_conceded(home_team)
        away_recent_conceded = self.recent_goals_conceded(away_team)

        home_home_form = self.home_form(home_team)
        away_away_form = self.away_form(away_team)

        home_rest = self.rest_days(home_team)
        away_rest = self.rest_days(away_team)

        home_recent_xg = self.team_value(
            home_team,
            "recent_xg",
        )
        away_recent_xg = self.team_value(
            away_team,
            "recent_xg",
        )

        home_recent_xga = self.team_value(
            home_team,
            "recent_xga",
        )
        away_recent_xga = self.team_value(
            away_team,
            "recent_xga",
        )

        # -------------------------------------------------
        # Home Advantage
        # -------------------------------------------------

        home_advantage = 1.0

        # -------------------------------------------------
        # Additional streaks / recent metrics
        # Provide relative values (home - away) to match other features
        # and avoid undefined variable errors when building feature dict.
        # -------------------------------------------------
        home_win_streak = self.team_value(
            home_team,
            "win_streak",
        )
        away_win_streak = self.team_value(
            away_team,
            "win_streak",
        )
        win_streak = (
            home_win_streak -
            away_win_streak
        )

        home_failed_to_score_streak = self.team_value(
            home_team,
            "failed_to_score_streak",
        )
        away_failed_to_score_streak = self.team_value(
            away_team,
            "failed_to_score_streak",
        )
        failed_to_score_streak = (
            home_failed_to_score_streak -
            away_failed_to_score_streak
        )

        home_clean_sheet_streak = self.team_value(
            home_team,
            "clean_sheet_streak",
        )
        away_clean_sheet_streak = self.team_value(
            away_team,
            "clean_sheet_streak",
        )
        clean_sheet_streak = (
            home_clean_sheet_streak -
            away_clean_sheet_streak
        )

        home_recent_shots = self.team_value(
            home_team,
            "recent_shots",
        )
        away_recent_shots = self.team_value(
            away_team,
            "recent_shots",
        )
        recent_shots = (
            home_recent_shots -
            away_recent_shots
        )

        home_recent_shots_on_target = self.team_value(
            home_team,
            "recent_shots_on_target",
        )
        away_recent_shots_on_target = self.team_value(
            away_team,
            "recent_shots_on_target",
        )
        recent_shots_on_target = (
            home_recent_shots_on_target -
            away_recent_shots_on_target
        )

        home_recent_possession = self.team_value(
            home_team,
            "recent_possession",
        )
        away_recent_possession = self.team_value(
            away_team,
            "recent_possession",
        )
        recent_possession = (
            home_recent_possession -
            away_recent_possession
        )

        home_recent_corners = self.team_value(
            home_team,
            "recent_corners",
        )
        away_recent_corners = self.team_value(
            away_team,
            "recent_corners",
        )
        recent_corners = (
            home_recent_corners -
            away_recent_corners
        )

        home_recent_cards = self.team_value(
            home_team,
            "recent_cards",
        )
        away_recent_cards = self.team_value(
            away_team,
            "recent_cards",
        )
        recent_cards = (
            home_recent_cards -
            away_recent_cards
        )

        home_momentum = self.team_value(home_team, "momentum")
        away_momentum = self.team_value(away_team, "momentum")

        momentum = (
            home_momentum -
            away_momentum
        )

        shots_difference = (
            home_recent_shots -
            away_recent_shots
        )
        sot_difference = (
            home_recent_shots_on_target -
            away_recent_shots_on_target
        )
        possession_difference = (
            home_recent_possession -
            away_recent_possession
        )
        corners_difference = (
            home_recent_corners -
            away_recent_corners
        )
        cards_difference = (
            home_recent_cards -
            away_recent_cards
        )
        momentum_difference = momentum

        # -------------------------------------------------
        # IMPORTANT
        # THIS ORDER MUST MATCH train_model.py
        # -------------------------------------------------

        feature_dict = {

            "home_form": home_form,
            "away_form": away_form,
            "home_attack": home_attack,
            "away_attack": away_attack,
            "home_defence": home_defence,
            "away_defence": away_defence,
            "home_avg_scored": home_avg_scored,
            "away_avg_scored": away_avg_scored,
            "home_avg_conceded": home_avg_conceded,
            "away_avg_conceded": away_avg_conceded,
            "home_goal_difference": home_goal_difference,
            "away_goal_difference": away_goal_difference,
            "home_win_rate": home_win_rate,
            "away_win_rate": away_win_rate,
            "home_clean_sheet_rate": home_clean_sheet_rate,
            "away_clean_sheet_rate": away_clean_sheet_rate,
            "home_momentum": home_momentum,
            "away_momentum": away_momentum,
            "home_win_streak": home_win_streak,
            "away_win_streak": away_win_streak,
            "home_failed_to_score_streak": home_failed_to_score_streak,
            "away_failed_to_score_streak": away_failed_to_score_streak,
            "home_clean_sheet_streak": home_clean_sheet_streak,
            "away_clean_sheet_streak": away_clean_sheet_streak,
            "home_recent_shots": home_recent_shots,
            "away_recent_shots": away_recent_shots,
            "home_recent_shots_on_target": home_recent_shots_on_target,
            "away_recent_shots_on_target": away_recent_shots_on_target,
            "home_recent_possession": home_recent_possession,
            "away_recent_possession": away_recent_possession,
            "home_recent_corners": home_recent_corners,
            "away_recent_corners": away_recent_corners,
            "home_recent_cards": home_recent_cards,
            "away_recent_cards": away_recent_cards,
            "home_recent_goals": home_recent_goals,
            "away_recent_goals": away_recent_goals,
            "home_recent_conceded": home_recent_conceded,
            "away_recent_conceded": away_recent_conceded,
            "home_home_form": home_home_form,
            "away_away_form": away_away_form,
            "home_rest": home_rest,
            "away_rest": away_rest,
            "home_recent_xg": home_recent_xg,
            "away_recent_xg": away_recent_xg,
            "home_recent_xga": home_recent_xga,
            "away_recent_xga": away_recent_xga,
            "home_recent_points": home_recent_points,
            "away_recent_points": away_recent_points,
            "home_unbeaten": home_unbeaten,
            "away_unbeaten": away_unbeaten,
            "home_strength": home_strength,
            "away_strength": away_strength,
            "attack_difference": attack_difference,
            "defence_difference": defence_difference,
            "form_difference": form_difference,
            "goal_difference": goal_difference,
            "win_rate_difference": win_rate_difference,
            "recent_points_difference": recent_points_difference,
            "recent_goal_difference": recent_goal_difference,
            "recent_conceded_difference": recent_conceded_difference,
            "strength_difference": strength_difference,
            "momentum_difference": momentum_difference,
            "shots_difference": shots_difference,
            "sot_difference": sot_difference,
            "possession_difference": possession_difference,
            "corners_difference": corners_difference,
            "cards_difference": cards_difference,
            "home_advantage": home_advantage,

            # Team identity + Elo (train_model.prepare_features adds these)
            "home_recent_goal_difference": home_recent_goal_difference,
            "away_recent_goal_difference": away_recent_goal_difference,

            "home_enc": home_enc,
            "away_enc": away_enc,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_difference": elo_difference,

        }

        feature_columns = self._feature_columns()

        missing = [c for c in feature_columns if c not in feature_dict]

        if missing:
            raise RuntimeError(
                "Prediction engine is out of sync with the trained model; "
                f"missing features: {missing}"
            )

        features = np.array(
            [[feature_dict[c] for c in feature_columns]],
            dtype=float,
        )

        return features

    # =====================================================
    # MACHINE LEARNING PREDICTION
    # =====================================================

    def predict_ml(
        self,
        home_team,
        away_team,
    ):

        features = self.build_features(
            home_team,
            away_team,
        )

        if self.scaler is not None:
            try:
                features = self.scaler.transform(features)
            except Exception:
                logger.warning(
                    "Feature scaling failed. Using raw features."
                )

        try:
            raw = self.model.predict_proba(features)[0]
        except Exception:
            logger.exception(
                "Failed to generate probabilities for %s vs %s",
                home_team,
                away_team,
            )
            return {
                "home_win": 0.34,
                "draw": 0.33,
                "away_win": 0.33,
            }

        class_probs = {
            int(label): float(prob)
            for label, prob in zip(self.model.classes_, raw)
        }

        probabilities = [
            class_probs.get(0, 0.0),
            class_probs.get(1, 0.0),
            class_probs.get(2, 0.0),
        ]

        probabilities = self.softmax_smooth(probabilities)

        return {
            "home_win": float(probabilities[0]),
            "draw": float(probabilities[1]),
            "away_win": float(probabilities[2]),
        }

    # =====================================================
    # CONFIDENCE
    # =====================================================

    def calculate_confidence(
        self,
        probabilities,
    ):

        highest = max(probabilities.values())

        return round(highest * 100, 2)

    # =====================================================
    # ESTIMATED XG
    # =====================================================

    def estimate_xg(
        self,
        probabilities,
    ):

        home = (
            0.8
            + probabilities["home_win"] * 1.8
            + probabilities["draw"] * 0.2
        )

        away = (
            0.8
            + probabilities["away_win"] * 1.8
            + probabilities["draw"] * 0.2
        )

        return {
            "home": round(home, 2),
            "away": round(away, 2),
        }

    # =====================================================
    # PUBLIC API
    # =====================================================

    def predict(
        self,
        home_team,
        away_team,
    ):

        probabilities = self.predict_ml(
            home_team,
            away_team,
        )

        prediction_key = max(
            probabilities,
            key=probabilities.get,
        )

        prediction_map = {
            "home_win": "HOME",
            "draw": "DRAW",
            "away_win": "AWAY",
        }

        confidence = self.calculate_confidence(
            probabilities
        )

        xg = self.estimate_xg(
            probabilities
        )

        return {
            "home_team": home_team,
            "away_team": away_team,
            "prediction": prediction_map[prediction_key],
            "confidence": confidence,
            "probabilities": {
                "home_win": round(probabilities["home_win"] * 100, 2),
                "draw": round(probabilities["draw"] * 100, 2),
                "away_win": round(probabilities["away_win"] * 100, 2),
            },
            "xg": {
                "home": round(xg["home"], 2),
                "away": round(xg["away"], 2),
            },
        }

    def safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def team_value(
        self,
        team,
        key,
        default=0.0,
    ):

        stats = self.team_stats.get(team)

        if stats is None:
            return default

        value = stats.get(key, default)

        return self.safe_float(
            value,
            default,
        )

    
