import time
import random
import httpx
from riot_retrieve.models import Account, MatchSummary, ParticipantStats, MatchTimeline, TimelineEvent

REGION_TO_CONTINENT = {
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "kr": "asia",
    "jp1": "asia",
    "oc1": "sea",
    "ph2": "sea",
    "sg2": "sea",
    "th2": "sea",
    "tw2": "sea",
    "vn2": "sea",
}

class RiotClient:
    """Thin HTTP client for Riot match-v5 and account-v1 endpoints."""

    def __init__(self, api_key: str, default_platform: str = "na1"):
        self.api_key = api_key.strip()
        self.platform = default_platform.lower()
        self.continent = REGION_TO_CONTINENT.get(self.platform, "americas")
        self._client = httpx.Client(
            headers={"X-Riot-Token": self.api_key},
            timeout=20.0,
        )

    def _get(self, host: str, path: str, params: dict = None):
        url = f"https://{host}.api.riotgames.com{path}"
        max_attempts = 5
        for attempt in range(max_attempts):
            resp = self._client.get(url, params=params)
            # print(f"DEBUG: {resp.status_code} {url}")
            if resp.status_code == 429:
                # Riot header retry-after is usually present, but fall back to exp backoff if missing
                raw_retry = resp.headers.get("Retry-After")
                if raw_retry:
                    wait = float(raw_retry) + random.uniform(0.1, 0.4)
                else:
                    wait = (2 ** attempt) + random.uniform(0.2, 0.8)
                time.sleep(wait)
                continue
            if resp.status_code in (500, 502, 503, 504):
                time.sleep(1.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Exceeded max retries for {url}")

    def get_account_by_riot_id(self, name: str, tag: str) -> Account:
        data = self._get(self.continent, f"/riot/account/v1/accounts/by-riot-id/{name}/{tag}")
        return Account(puuid=data["puuid"], game_name=data["gameName"], tag_line=data["tagLine"])

    def get_match_ids(self, puuid: str, start: int = 0, count: int = 20, queue: int = None) -> list[str]:
        params = {"start": start, "count": count}
        if queue is not None:
            params["queue"] = queue
        return self._get(self.continent, f"/lol/match/v5/matches/by-puuid/{puuid}/ids", params=params)

    def get_match(self, match_id: str) -> MatchSummary:
        # FIXME: Riot returns match id strings prefixed with platform (e.g. NA1_12345), resolve host dynamically
        host = self.continent
        data = self._get(host, f"/lol/match/v5/matches/{match_id}")
        info = data["info"]
        participants = []
        for p in info["participants"]:
            participants.append(
                ParticipantStats(
                    puuid=p["puuid"],
                    summoner_name=p.get("riotIdGameName") or p.get("summonerName", ""),
                    champion_id=p["championId"],
                    champion_name=p["championName"],
                    team_id=p["teamId"],
                    win=p["win"],
                    kills=p["kills"],
                    deaths=p["deaths"],
                    assists=p["assists"],
                    total_damage_dealt=p["totalDamageDealt"],
                    total_damage_to_champions=p["totalDamageDealtToChampions"],
                    gold_earned=p["goldEarned"],
                    total_minions_killed=p["totalMinionsKilled"],
                    neutral_minions_killed=p["neutralMinionsKilled"],
                    vision_score=p["visionScore"],
                    role=p["role"],
                    lane=p["lane"],
                    champ_level=p.get("champLevel", 1),
                    item0=p.get("item0", 0),
                    item1=p.get("item1", 0),
                    item2=p.get("item2", 0),
                    item3=p.get("item3", 0),
                    item4=p.get("item4", 0),
                    item5=p.get("item5", 0),
                    item6=p.get("item6", 0),
                    turret_kills=p.get("turretKills", 0),
                    damage_self_mitigated=p.get("damageSelfMitigated", 0),
                )
            )
        return MatchSummary(
            match_id=match_id,
            game_creation=info["gameCreation"],
            game_duration=info["gameDuration"],
            game_mode=info["gameMode"],
            game_version=info["gameVersion"],
            queue_id=info["queueId"],
            participants=participants,
        )

    def get_timeline(self, match_id: str) -> MatchTimeline:
        data = self._get(self.continent, f"/lol/match/v5/matches/{match_id}/timeline")
        info = data["info"]
        events = []
        for frame in info.get("frames", []):
            for ev in frame.get("events", []):
                events.append(
                    TimelineEvent(
                        timestamp=ev.get("timestamp", 0),
                        type=ev.get("type", "UNKNOWN"),
                        participant_id=ev.get("participantId"),
                        killer_id=ev.get("killerId"),
                        victim_id=ev.get("victimId"),
                        item_id=ev.get("itemId"),
                    )
                )
        return MatchTimeline(
            match_id=match_id,
            frame_interval=info.get("frameInterval", 60000),
            events=events,
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
