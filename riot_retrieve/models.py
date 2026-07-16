from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Account:
    puuid: str
    game_name: str
    tag_line: str

@dataclass
class ParticipantStats:
    puuid: str
    summoner_name: str
    champion_id: int
    champion_name: str
    team_id: int
    win: bool
    kills: int
    deaths: int
    assists: int
    total_damage_dealt: int
    total_damage_to_champions: int
    gold_earned: int
    total_minions_killed: int
    neutral_minions_killed: int
    vision_score: int
    role: str
    lane: str
    champ_level: int = 1
    item0: int = 0
    item1: int = 0
    item2: int = 0
    item3: int = 0
    item4: int = 0
    item5: int = 0
    item6: int = 0
    turret_kills: int = 0
    damage_self_mitigated: int = 0

@dataclass
class MatchSummary:
    match_id: str
    game_creation: int
    game_duration: int
    game_mode: str
    game_version: str
    queue_id: int
    participants: list[ParticipantStats] = field(default_factory=list)

@dataclass
class TimelineEvent:
    timestamp: int
    type: str
    participant_id: Optional[int] = None
    killer_id: Optional[int] = None
    victim_id: Optional[int] = None
    item_id: Optional[int] = None

@dataclass
class MatchTimeline:
    match_id: str
    frame_interval: int
    events: list[TimelineEvent] = field(default_factory=list)
