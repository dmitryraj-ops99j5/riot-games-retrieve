# riot-games-retrieve

I got tired of slow tracker websites filled with ads just to look up my match history and champ winrates. This pulls match data from Riot API directly into a local SQLite database and gives me quick terminal summaries.

## Requirements

- Python 3.11+
- Riot Games API key (get one from developer.riotgames.com)

## Setup

```bash
git clone https://github.com/username/riot-games-retrieve.git
cd riot-games-retrieve
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Export your API token:

```bash
export RIOT_API_KEY="RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

## Usage

Fetch last 20 ranked matches for a player:

```bash
riot-retrieve sync --game-name Faker --tag-line KR1 --region asia --queue ranked
```

Inspect summary for recently synced matches:

```bash
riot-retrieve stats --game-name Faker --tag-line KR1
```

Show champion performance breakdown:

```bash
riot-retrieve stats --game-name Faker --tag-line KR1 --by-champ
```

Dump raw match payloads to JSONL for ad-hoc sqlite queries:

```bash
riot-retrieve export --output matches.jsonl
```

## License

MIT

<!-- refreshed: 2026-09-08 -->
