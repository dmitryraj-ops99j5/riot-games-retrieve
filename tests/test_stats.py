import pytest
from riot_retrieve.stats import (
    calc_kda,
    calc_cs_per_min,
    calc_kill_participation,
    summarize_champion_stats,
    winrate,
    filter_remakes,
)


def test_calc_kda_standard():
    assert calc_kda(10, 2, 5) == 7.5
    assert calc_kda(0, 5, 0) == 0.0
    assert calc_kda(3, 4, 3) == 1.5


def test_calc_kda_zero_deaths():
    # Treat 0 deaths as 1 so perfect games don't blow up with zero division
    assert calc_kda(8, 0, 4) == 12.0
    assert calc_kda(0, 0, 0) == 0.0


def test_winrate_calculation():
    assert winrate(10, 20) == 50.0
    assert winrate(3, 4) == 75.0
    assert winrate(0, 5) == 0.0
    assert winrate(0, 0) == 0.0


def test_cs_per_min():
    # 180 cs in 30 minutes (1800s)
    assert calc_cs_per_min(180, 1800) == 6.0
    # Match too short or invalid duration
    assert calc_cs_per_min(50, 0) == 0.0
    assert calc_cs_per_min(50, 120) == 0.0  # under 3 min threshold


def test_kill_participation():
    assert calc_kill_participation(5, 5, 20) == 50.0
    assert calc_kill_participation(0, 0, 10) == 0.0
    # Team got 0 kills total
    assert calc_kill_participation(0, 0, 0) == 0.0


def test_filter_remakes():
    rows = [
        {"game_duration": 1800, "game_ended_in_early_surrender": False},
        {"game_duration": 210, "game_ended_in_early_surrender": True},   # remake
        {"game_duration": 280, "game_ended_in_early_surrender": False},  # too short
        {"game_duration": 950, "game_ended_in_early_surrender": True},   # 15m ff, not remake
    ]
    valid = filter_remakes(rows)
    assert len(valid) == 2
    assert valid[0]["game_duration"] == 1800
    assert valid[1]["game_duration"] == 950


def test_summarize_champion_stats_empty():
    res = summarize_champion_stats([])
    assert res == []


def test_summarize_champion_stats_basic():
    matches = [
        {"champion_name": "Jinx", "win": True, "kills": 8, "deaths": 2, "assists": 6, "cs": 200, "game_duration": 1800},
        {"champion_name": "Jinx", "win": False, "kills": 2, "deaths": 7, "assists": 3, "cs": 150, "game_duration": 1500},
        {"champion_name": "Thresh", "win": True, "kills": 1, "deaths": 3, "assists": 14, "cs": 30, "game_duration": 1600},
    ]
    summary = summarize_champion_stats(matches)
    assert len(summary) == 2

    # Jinx should be first since more games played
    jinx = summary[0]
    assert jinx["champion"] == "Jinx"
    assert jinx["games"] == 2
    assert jinx["wins"] == 1
    assert jinx["winrate"] == 50.0
    assert jinx["avg_kills"] == 5.0
    assert jinx["avg_deaths"] == 4.5
