from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

ROLLING_MATCHES = 5


@dataclass
class TeamHistory:

    # Overall
    matches: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    goals_scored: int = 0
    goals_conceded: int = 0

    clean_sheets: int = 0
    clean_sheet_streak: int = 0

    # Home
    home_matches: int = 0
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0

    home_goals_scored: int = 0
    home_goals_conceded: int = 0

    # Away
    away_matches: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    away_goals_scored: int = 0
    away_goals_conceded: int = 0

    failed_to_score_streak: int = 0
    win_streak: int = 0

    # Rolling Form

    recent_results: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    recent_points: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    recent_scored: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    recent_conceded: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Home Form

    recent_home_results: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Away Form

    recent_away_results: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Momentum

    @property
    def momentum(self) -> float:
        return (
            0.50 * safe_average(self.recent_points)
            + 0.30 * safe_average(self.recent_goal_difference)
            + 0.20 * self.unbeaten
        )

    # xG History

    recent_xg: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    recent_xga: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    recent_goal_difference: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Rest Days

    last_match_date: datetime | None = None

    # Unbeaten Run

    unbeaten: int = 0

    # Recent Shots

    recent_shots: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    recent_shots_on_target: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Possession

    recent_possession: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Corners

    recent_corners: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )

    # Cards

    recent_cards: deque = field(
        default_factory=lambda: deque(maxlen=ROLLING_MATCHES)
    )


team_history = defaultdict(TeamHistory)


# ==========================================================
# HELPERS
# ==========================================================

def reset_history():

    team_history.clear()


def safe_average(values: deque) -> float:

    if len(values) == 0:
        return 0.0

    return sum(values) / len(values)

def average_points(team: str):

    return safe_average(
        team_history[team].recent_points
    )


def average_scored(team: str):

    return safe_average(
        team_history[team].recent_scored
    )


def average_conceded(team: str):

    return safe_average(
        team_history[team].recent_conceded
    )


def average_xg(team: str):

    return safe_average(
        team_history[team].recent_xg
    )


def average_xga(team: str):

    return safe_average(
        team_history[team].recent_xga
    )


def win_rate(team: str):

    history = team_history[team]

    if history.matches == 0:
        return 0.0

    return history.wins / history.matches


def clean_sheet_rate(team: str):

    history = team_history[team]

    if history.matches == 0:
        return 0.5

    return history.clean_sheets / history.matches


def attack_strength(team: str) -> float:

    return safe_average(
        team_history[team].recent_scored
    )


def defence_strength(team: str) -> float:

    return safe_average(
        team_history[team].recent_conceded
    )


def recent_form(team: str) -> float:

    history = team_history[team]

    if len(history.recent_points) == 0:
        return 0.0

    return safe_average(
        history.recent_points
    ) / 3.0

def home_form(team: str) -> float:

    history = team_history[team]

    if len(history.recent_home_results) == 0:
        return 0.5

    return safe_average(
        history.recent_home_results
    ) / 3.0

def away_form(team: str) -> float:

    history = team_history[team]

    if len(history.recent_away_results) == 0:
        return 0.5

    return safe_average(
        history.recent_away_results
    ) / 3.0


def calculate_rest_days(team: str) -> int:

    history = team_history[team]

    if history.last_match_date is None:
        return 5

    match_date = history.last_match_date

    # If PostgreSQL returned a naive timestamp,
    # assume UTC.
    if match_date.tzinfo is None:
        match_date = match_date.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    delta = now - match_date

    return max(delta.days, 0)


def unbeaten(team: str):

    return team_history[team].unbeaten

def failed_to_score_streak(team: str):

    return team_history[team].failed_to_score_streak

def clean_sheet_streak(team: str):

    return team_history[team].clean_sheet_streak

def home_strength(team: str):

    history = team_history[team]

    if history.home_matches == 0:
        return 0.5

    home_win_rate = history.home_wins / history.home_matches
    goal_difference = (
        history.home_goals_scored - history.home_goals_conceded
    ) / history.home_matches

    return (
        0.4 * home_win_rate
        + 0.3 * max(min(goal_difference / 3.0, 1.0), -1.0)
        + 0.2 * attack_strength(team)
        - 0.1 * defence_strength(team)
    )


def away_strength(team: str):

    history = team_history[team]

    if history.away_matches == 0:
        return 0.5

    away_win_rate = history.away_wins / history.away_matches
    goal_difference = (
        history.away_goals_scored - history.away_goals_conceded
    ) / history.away_matches

    return (
        0.4 * away_win_rate
        + 0.3 * max(min(goal_difference / 3.0, 1.0), -1.0)
        + 0.2 * attack_strength(team)
        - 0.1 * defence_strength(team)
    )


# ==========================================================
# TEAM FEATURES
# ==========================================================

def team_features(team: str) -> dict:

    history = team_history[team]

    matches = max(history.matches, 1)

    avg_scored = history.goals_scored / matches

    avg_conceded = history.goals_conceded / matches

    goal_difference = (
        avg_scored -
        avg_conceded
    )

    return {

        "form": recent_form(team),

        "home_form": home_form(team),

        "away_form": away_form(team),

        "attack": attack_strength(team),

        "defence": defence_strength(team),

        "avg_scored": avg_scored,

        "avg_conceded": avg_conceded,

        "goal_difference": goal_difference,

        "win_rate": win_rate(team),

        "clean_sheet_rate": clean_sheet_rate(team),

        "recent_goals_scored":
            safe_average(history.recent_scored),

        "recent_goals_conceded":
            safe_average(history.recent_conceded),

        "recent_points":
            safe_average(history.recent_points),

        "rest_days":
            calculate_rest_days(team),

        "recent_xg":
            safe_average(history.recent_xg),

        "recent_xga":
            safe_average(history.recent_xga),

        "unbeaten":
            unbeaten(team),

        "home_strength":
            home_strength(team),

        "away_strength":
            away_strength(team),

        "win_streak": history.win_streak,

        "failed_to_score_streak": history.failed_to_score_streak,

        "clean_sheet_streak": history.clean_sheet_streak,

        "recent_goal_difference":
            safe_average(history.recent_goal_difference),

        "recent_shots":
            safe_average(history.recent_shots),

        "recent_shots_on_target":
            safe_average(history.recent_shots_on_target),

        "recent_possession":
            safe_average(history.recent_possession),

        "recent_corners":
            safe_average(history.recent_corners),

        "recent_cards":
            safe_average(history.recent_cards),

        "momentum": history.momentum,

    }
# ==========================================================
# UPDATE HISTORY
# ==========================================================

def update_team_history(
    team: str,
    goals_for: int,
    goals_against: int,
    is_home: bool = False,
    match_date=None,
):
    goals_for = int(goals_for)
    goals_against = int(goals_against)

    history = team_history[team]

    # -------------------------------------------------
    # Overall
    # -------------------------------------------------

    history.matches += 1

    history.goals_scored += goals_for
    history.goals_conceded += goals_against

    if goals_for == 0:
        history.failed_to_score_streak += 1
    else:
        history.failed_to_score_streak = 0

    # -------------------------------------------------
    # Clean Sheet
    # -------------------------------------------------

    if goals_against == 0:
        history.clean_sheets += 1
        history.clean_sheet_streak += 1
    else:
        history.clean_sheet_streak = 0

    # -------------------------------------------------
    # Result
    # -------------------------------------------------

    if goals_for > goals_against:
        history.wins += 1
        history.win_streak += 1
        history.unbeaten += 1

        history.recent_results.append(3)
        history.recent_points.append(3)

    elif goals_for == goals_against:
        history.draws += 1
        history.win_streak = 0
        history.unbeaten += 1

        history.recent_results.append(1)
        history.recent_points.append(1)

    else:
        history.losses += 1
        history.win_streak = 0
        history.unbeaten = 0

        history.recent_results.append(0)
        history.recent_points.append(0)

    # -------------------------------------------------
    # Home / Away totals
    # -------------------------------------------------

    if is_home:

        history.home_matches += 1

        history.home_goals_scored += goals_for
        history.home_goals_conceded += goals_against

        history.recent_home_results.append(
            history.recent_points[-1]
        )

    else:

        history.away_matches += 1

        history.away_goals_scored += goals_for
        history.away_goals_conceded += goals_against

        history.recent_away_results.append(
            history.recent_points[-1]
        )

    # -------------------------------------------------
    # Approximate xG
    # -------------------------------------------------

    estimated_xg = max(

    0.20,

    goals_for * 0.82

    + attack_strength(team) * 0.25

    )

    estimated_xga = max(

    0.20,

    goals_against * 0.82

    + defence_strength(team) * 0.25

    )

    # Estimate shots and shots on target if not available
    # Use goals and attack strength to derive a reasonable estimate
    estimated_shots = float(
        max(
            1,
            round(goals_for * 4 + attack_strength(team) * 2)
        )
    )
    estimated_shots_on_target = max(0.0, estimated_shots * 0.35)

    estimated_possession = min(
        70.0,
        max(
            30.0,
            50.0
            + attack_strength(team) * 3.5
            - defence_strength(team) * 1.5
        ),
    )

    estimated_corners = max(2.0, estimated_shots * 0.3)

    history.recent_scored.append(goals_for)
    history.recent_conceded.append(goals_against)
    history.recent_xg.append(
        estimated_xg
    )

    history.recent_xga.append(
        estimated_xga
    )

    history.recent_goal_difference.append(
        goals_for - goals_against
    )

    history.recent_shots.append(estimated_shots)

    history.recent_shots_on_target.append(estimated_shots_on_target)

    history.recent_possession.append(
        estimated_possession
    )

    history.recent_corners.append(
        estimated_corners
    )

    estimated_cards = 2.0
    history.recent_cards.append(estimated_cards)

    # -------------------------------------------------
    # Rest Days
    # -------------------------------------------------

    if match_date is not None:
        history.last_match_date = match_date


# ==========================================================
# BUILD FEATURES
# ==========================================================

def create_training_features(
    home_stats,
    away_stats,
):

    return {

        # -------------------------------------------------
        # Core Features
        # -------------------------------------------------

        "home_form":
            home_stats["form"],

        "away_form":
            away_stats["form"],

        "home_attack":
            home_stats["attack"],

        "away_attack":
            away_stats["attack"],

        "home_defence":
            home_stats["defence"],

        "away_defence":
            away_stats["defence"],

        "home_avg_scored":
            home_stats["avg_scored"],

        "away_avg_scored":
            away_stats["avg_scored"],

        "home_avg_conceded":
            home_stats["avg_conceded"],

        "away_avg_conceded":
            away_stats["avg_conceded"],

        "home_goal_difference":
            home_stats["goal_difference"],

        "away_goal_difference":
            away_stats["goal_difference"],

        "home_win_rate":
            home_stats["win_rate"],

        "away_win_rate":
            away_stats["win_rate"],

        "home_clean_sheet_rate":
            home_stats["clean_sheet_rate"],

        "away_clean_sheet_rate":
            away_stats["clean_sheet_rate"],

        "home_momentum":
            home_stats["momentum"],
        "away_momentum":
            away_stats["momentum"],

        "home_win_streak":
            home_stats["win_streak"],
        "away_win_streak":
            away_stats["win_streak"],


        "home_failed_to_score_streak":
            home_stats["failed_to_score_streak"],

        "away_failed_to_score_streak":
            away_stats["failed_to_score_streak"],

        "home_clean_sheet_streak":
            home_stats["clean_sheet_streak"],
        "away_clean_sheet_streak":
            away_stats["clean_sheet_streak"],

        "home_recent_shots":
            home_stats["recent_shots"],
        "away_recent_shots":
            away_stats["recent_shots"],

        "home_recent_shots_on_target":
            home_stats["recent_shots_on_target"],
        "away_recent_shots_on_target":
            away_stats["recent_shots_on_target"],

        "home_recent_possession":
            home_stats["recent_possession"],
        "away_recent_possession":
            away_stats["recent_possession"],

        "home_recent_corners":
            home_stats["recent_corners"],
        "away_recent_corners":
            away_stats["recent_corners"],

        "home_recent_cards":
            home_stats["recent_cards"],
        "away_recent_cards":
            away_stats["recent_cards"],

        # -------------------------------------------------
        # Recent Goals
        # -------------------------------------------------

        "home_recent_goals":
            home_stats["recent_goals_scored"],

        "away_recent_goals":
            away_stats["recent_goals_scored"],

        "home_recent_conceded":
            home_stats["recent_goals_conceded"],

        "away_recent_conceded":
            away_stats["recent_goals_conceded"],

        "home_recent_goal_difference":
            home_stats["recent_goal_difference"],

        "away_recent_goal_difference":
            away_stats["recent_goal_difference"],

        # -------------------------------------------------
        # Home / Away Form
        # -------------------------------------------------

        "home_home_form":
            home_stats["home_form"],

        "away_away_form":
            away_stats["away_form"],

        # -------------------------------------------------
        # Rest
        # -------------------------------------------------

        "home_rest":
            home_stats["rest_days"],

        "away_rest":
            away_stats["rest_days"],

        # -------------------------------------------------
        # xG
        # -------------------------------------------------

        "home_recent_xg":
            home_stats["recent_xg"],

        "away_recent_xg":
            away_stats["recent_xg"],

        "home_recent_xga":
            home_stats["recent_xga"],

        "away_recent_xga":
            away_stats["recent_xga"],

        # -------------------------------------------------
        # Recent Points
        # -------------------------------------------------

        "home_recent_points":
            home_stats["recent_points"],

        "away_recent_points":
            away_stats["recent_points"],

        # -------------------------------------------------
        # Unbeaten Run
        # -------------------------------------------------

        "home_unbeaten":
            home_stats["unbeaten"],

        "away_unbeaten":
            away_stats["unbeaten"],

        # -------------------------------------------------
        # Strength
        # -------------------------------------------------

        "home_strength":
            home_stats["home_strength"],

        "away_strength":
            away_stats["away_strength"],

        # -------------------------------------------------
        # Engineered Difference Features
        # -------------------------------------------------

        "attack_difference":
            home_stats["attack"] -
            away_stats["attack"],

        "defence_difference":
            home_stats["defence"] -
            away_stats["defence"],

        "form_difference":
            home_stats["form"] -
            away_stats["form"],

        "goal_difference":
            home_stats["goal_difference"] -
            away_stats["goal_difference"],

        "win_rate_difference":
            home_stats["win_rate"] -
            away_stats["win_rate"],

        "recent_points_difference":
            home_stats["recent_points"] -
            away_stats["recent_points"],

        "recent_goal_difference":
            home_stats["recent_goal_difference"] -
            away_stats["recent_goal_difference"],

        "recent_conceded_difference":
            away_stats["recent_goals_conceded"] -
            home_stats["recent_goals_conceded"],

        "strength_difference":
            home_stats["home_strength"] -
            away_stats["away_strength"],

        "momentum_difference":
            home_stats["momentum"] -
            away_stats["momentum"],

        "shots_difference":
            home_stats["recent_shots"] -
            away_stats["recent_shots"],

        "sot_difference":
            home_stats["recent_shots_on_target"] -
            away_stats["recent_shots_on_target"],

        "possession_difference":
            home_stats["recent_possession"] -
            away_stats["recent_possession"],

        "corners_difference":
            home_stats["recent_corners"] -
            away_stats["recent_corners"],

        "cards_difference":
            home_stats["recent_cards"] -
            away_stats["recent_cards"],

        # -------------------------------------------------

        "home_advantage":
            1.0,

    }