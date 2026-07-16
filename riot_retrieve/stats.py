from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import sqlite3


@dataclass
class ChampionStats:
    champion_name: str
    games: int
    wins: int
    losses: int
    winrate: float
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    kda: float
    cs_per_min: float
    avg_damage: float
    avg_gold: float


@dataclass
class PlayerOverview:
    puuid: str
    total_games: int
    wins: int
    losses: int
    winrate: float
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    kda: float
    cs_per_min: float
    avg_vision_score: float
    champions: List[ChampionStats]


def _safe_div(num: float, denom: float, default: float = 0.0) -> float:
    return num / denom if denom > 0 else default


def aggregate_stats(rows: List[sqlite3.Row], puuid: str = "") -> PlayerOverview:
    """Compute full performance summary including champion pool metrics."""
    if not rows:
        return PlayerOverview(
            puuid=puuid,
            total_games=0,
            wins=0,
            losses=0,
            winrate=0.0,
            avg_kills=0.0,
            avg_deaths=0.0,
            avg_assists=0.0,
            kda=0.0,
            cs_per_min=0.0,
            avg_vision_score=0.0,
            champions=[],
        )

    total = len(rows)
    wins = sum(1 for r in rows if r["win"] == 1)
    losses = total - wins

    total_k = sum(r["kills"] for r in rows)
    total_d = sum(r["deaths"] for r in rows)
    total_a = sum(r["assists"] for r in rows)
    total_vis = sum(r["vision_score"] for r in rows)

    total_cs = 0
    total_duration_sec = 0
    champ_groups: Dict[str, List[sqlite3.Row]] = {}

    for r in rows:
        c_name = r["champion_name"]
        champ_groups.setdefault(c_name, []).append(r)

        cs = (r["total_minions_killed"] or 0) + (r["neutral_minions_killed"] or 0)
        total_cs += cs
        total_duration_sec += r["game_duration"]

    overall_cspm = (total_cs / (total_duration_sec / 60.0)) if total_duration_sec > 0 else 0.0
    kda_ratio = (total_k + total_a) / max(1, total_d)

    # breakdown per champ
    champ_stat_list: List[ChampionStats] = []
    for c_name, c_rows in champ_groups.items():
        c_total = len(c_rows)
        c_wins = sum(1 for x in c_rows if x["win"] == 1)
        c_k = sum(x["kills"] for x in c_rows)
        c_d = sum(x["deaths"] for x in c_rows)
        c_a = sum(x["assists"] for x in c_rows)
        c_dmg = sum(x["total_damage_dealt_to_champions"] for x in c_rows)
        c_gold = sum(x["gold_earned"] for x in c_rows)

        c_sec = sum(x["game_duration"] for x in c_rows)
        c_cs = sum((x["total_minions_killed"] or 0) + (x["neutral_minions_killed"] or 0) for x in c_rows)
        c_cspm = (c_cs / (c_sec / 60.0)) if c_sec > 0 else 0.0

        champ_stat_list.append(
            ChampionStats(
                champion_name=c_name,
                games=c_total,
                wins=c_wins,
                losses=c_total - c_wins,
                winrate=(c_wins / c_total) * 100.0,
                avg_kills=c_k / c_total,
                avg_deaths=c_d / c_total,
                avg_assists=c_a / c_total,
                kda=(c_k + c_a) / max(1, c_d),
                cs_per_min=c_cspm,
                avg_damage=c_dmg / c_total,
                avg_gold=c_gold / c_total,
            )
        )

    champ_stat_list.sort(key=lambda x: (x.games, x.winrate), reverse=True)

    return PlayerOverview(
        puuid=puuid or rows[0]["puuid"],
        total_games=total,
        wins=wins,
        losses=losses,
        winrate=(wins / total) * 100.0,
        avg_kills=total_k / total,
        avg_deaths=total_d / total,
        avg_assists=total_a / total,
        kda=kda_ratio,
        cs_per_min=overall_cspm,
        avg_vision_score=total_vis / total,
        champions=champ_stat_list,
    )
