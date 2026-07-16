import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_PATH = Path.home() / ".riot_retrieve" / "matches.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return configured SQLite connection with foreign keys enabled."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                game_creation INTEGER NOT NULL,
                game_duration INTEGER NOT NULL,
                game_mode TEXT NOT NULL,
                game_version TEXT NOT NULL,
                queue_id INTEGER NOT NULL,
                early_surrender INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS participant_stats (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                summoner_name TEXT NOT NULL,
                riot_id_tagline TEXT NOT NULL DEFAULT '',
                champion_id INTEGER NOT NULL,
                champion_name TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                win INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                total_damage_dealt_to_champions INTEGER NOT NULL,
                gold_earned INTEGER NOT NULL,
                total_minions_killed INTEGER NOT NULL,
                neutral_minions_killed INTEGER NOT NULL,
                vision_score INTEGER NOT NULL,
                role TEXT NOT NULL,
                lane TEXT NOT NULL,
                team_position TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (match_id, puuid),
                FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_participant_puuid ON participant_stats (puuid);
            CREATE INDEX IF NOT EXISTS idx_participant_champ ON participant_stats (puuid, champion_name);
            CREATE INDEX IF NOT EXISTS idx_matches_creation ON matches (game_creation DESC);
        """)


def insert_match(conn: sqlite3.Connection, match_data: Dict[str, Any]) -> bool:
    info = match_data.get("info", {})
    metadata = match_data.get("metadata", {})
    match_id = metadata.get("matchId")
    if not match_id:
        return False

    # print(f"inserting match: {match_id}")

    cur = conn.cursor()
    cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
    if cur.fetchone():
        return False

    # quick surrender before 3m usually means remake
    participants = info.get("participants", [])
    is_remake = any(p.get("gameEndedInEarlySurrender", False) for p in participants)
    if not is_remake and info.get("gameDuration", 0) < 300:
        is_remake = True

    with conn:
        conn.execute(
            """
            INSERT INTO matches (
                match_id, game_creation, game_duration, game_mode, game_version, queue_id, early_surrender
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                info.get("gameCreation", 0),
                info.get("gameDuration", 0),
                info.get("gameMode", ""),
                info.get("gameVersion", ""),
                info.get("queueId", 0),
                1 if is_remake else 0,
            ),
        )

        for p in participants:
            tagline = p.get("riotIdTagline") or ""
            pos = p.get("teamPosition") or p.get("individualPosition") or ""
            conn.execute(
                """
                INSERT INTO participant_stats (
                    match_id, puuid, summoner_name, riot_id_tagline, champion_id, champion_name,
                    team_id, win, kills, deaths, assists,
                    total_damage_dealt_to_champions, gold_earned,
                    total_minions_killed, neutral_minions_killed, vision_score, role, lane, team_position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    p.get("puuid", ""),
                    p.get("summonerName", ""),
                    tagline,
                    p.get("championId", 0),
                    p.get("championName", ""),
                    p.get("teamId", 0),
                    1 if p.get("win") else 0,
                    p.get("kills", 0),
                    p.get("deaths", 0),
                    p.get("assists", 0),
                    p.get("totalDamageDealtToChampions", 0),
                    p.get("goldEarned", 0),
                    p.get("totalMinionsKilled", 0),
                    p.get("neutralMinionsKilled", 0),
                    p.get("visionScore", 0),
                    p.get("role", ""),
                    p.get("lane", ""),
                    pos,
                ),
            )
    return True


def fetch_player_rows(
    conn: sqlite3.Connection,
    puuid: str,
    queue_id: Optional[int] = None,
    exclude_remakes: bool = True,
    limit: Optional[int] = None,
) -> List[sqlite3.Row]:
    # FIXME: add index on queue_id if queue-specific queries crawl on big dbs
    query = """
        SELECT
            p.*,
            m.game_creation,
            m.game_duration,
            m.game_mode,
            m.queue_id,
            m.early_surrender
        FROM participant_stats p
        JOIN matches m ON p.match_id = m.match_id
        WHERE p.puuid = ?
    """
    params: List[Any] = [puuid]

    if exclude_remakes:
        query += " AND m.early_surrender = 0 AND m.game_duration >= 300"

    if queue_id is not None:
        query += " AND m.queue_id = ?"
        params.append(queue_id)

    query += " ORDER BY m.game_creation DESC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()
