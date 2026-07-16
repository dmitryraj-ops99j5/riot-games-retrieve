import argparse
import os
import sys
from riot_retrieve.client import RiotClient, RiotApiError
from riot_retrieve.db import init_db, save_matches, get_db_connection, list_recent_matches
from riot_retrieve.stats import calculate_player_stats, get_champion_breakdown

QUEUE_NAMES = {
    420: "Ranked Solo",
    440: "Ranked Flex",
    450: "ARAM",
    400: "Normal Draft",
    430: "Normal Blind",
    1700: "Arena",
}


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        prog="riot-retrieve",
        description="Track League match history locally without web bloat.",
    )
    parser.add_argument(
        "--key",
        dest="api_key",
        help="Riot API key (defaults to RIOT_API_KEY env var)",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default="riot_stats.db",
        help="SQLite file path (default: riot_stats.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync
    sync_p = subparsers.add_parser("sync", help="Fetch recent matches and save to db")
    sync_p.add_argument("game_name", help="Riot ID game name (e.g. Faker)")
    sync_p.add_argument("tag_line", help="Riot ID tagline (e.g. KR1)")
    sync_p.add_argument(
        "--region",
        default="na1",
        help="Platform routing region: na1, euw1, kr, etc. (default: na1)",
    )
    sync_p.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of matches to pull (default: 20)",
    )
    sync_p.add_argument(
        "--queue",
        type=int,
        default=None,
        help="Queue ID to pull (e.g. 420 for Ranked Solo)",
    )

    # stats
    stats_p = subparsers.add_parser("stats", help="Print aggregated performance metrics")
    stats_p.add_argument("--puuid", help="Filter by specific player PUUID")
    stats_p.add_argument("--queue", type=int, help="Filter by queue ID (420, 440, 450)")
    stats_p.add_argument("--champs", action="store_true", help="Include champion breakdown table")

    # list
    list_p = subparsers.add_parser("list", help="Show short tabular list of stored matches")
    list_p.add_argument("--limit", type=int, default=10, help="Matches to show (default: 10)")
    list_p.add_argument("--puuid", help="Highlight stats for this player")

    return parser.parse_args(args)


def run_sync(args, api_key):
    conn = init_db(args.db_path)
    client = RiotClient(api_key=api_key, default_region=args.region)

    print(f"Resolving account {args.game_name}#{args.tag_line}...")
    try:
        account = client.get_account_by_riot_id(args.game_name, args.tag_line)
    except RiotApiError as e:
        print(f"Error finding account: {e}", file=sys.stderr)
        return 1

    puuid = account["puuid"]
    print(f"Found PUUID: {puuid[:12]}... Fetching match IDs (queue={args.queue or 'all'})...")

    match_ids = client.get_match_ids_by_puuid(puuid, count=args.count, queue=args.queue)
    if not match_ids:
        print("No matches found.")
        return 0

    print(f"Discovered {len(match_ids)} matches. Downloading details...")
    matches_data = []
    for idx, mid in enumerate(match_ids, start=1):
        sys.stdout.write(f"\r[{idx}/{len(match_ids)}] fetching {mid}")
        sys.stdout.flush()
        try:
            detail = client.get_match(mid)
            matches_data.append(detail)
        except RiotApiError as err:
            print(f"\nFailed on match {mid}: {err}", file=sys.stderr)
            break

    # print(f"DEBUG: fetched {len(matches_data)} items")
    print("")
    saved = save_matches(conn, matches_data)
    print(f"Saved {saved} new matches to {args.db_path}")
    return 0


def format_champ_table(champs):
    headers = ["Champion", "Games", "WinRate", "KDA", "CS/m", "Dmg"]
    rows = []
    for c in champs:
        win_pct = f"{c['win_rate']:.0f}%"
        kda_str = f"{c['kda']:.2f}"
        rows.append([
            c["champion_name"],
            str(c["games"]),
            win_pct,
            kda_str,
            f"{c['cs_per_min']:.1f}",
            f"{int(c['avg_damage']):,}"
        ])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    fmt = "  ".join([f"{{:<{w}}}" for w in col_widths])
    divider = "  ".join(["-" * w for w in col_widths])

    lines = [fmt.format(*headers), divider]
    for row in rows:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


def run_stats(args):
    conn = get_db_connection(args.db_path)
    summary = calculate_player_stats(conn, puuid=args.puuid, queue_id=args.queue)
    if not summary or summary.get("total_games", 0) == 0:
        print("No match data found matching criteria.")
        return 0

    q_label = QUEUE_NAMES.get(args.queue, f"Queue {args.queue}") if args.queue else "All Queues"
    print(f"\n--- Overall Performance ({q_label}) ---")
    print(f"Matches Tracked: {summary['total_games']}")
    print(f"Win Rate:        {summary['win_rate']:.1f}% ({summary['wins']}W / {summary['losses']}L)")
    print(f"Avg KDA:         {summary['avg_kda']:.2f} ({summary['avg_kills']:.1f}/{summary['avg_deaths']:.1f}/{summary['avg_assists']:.1f})")
    print(f"Avg CS/min:      {summary['avg_cs_per_min']:.1f}")
    print(f"Avg Damage:      {summary['avg_damage']:,}")

    if args.champs:
        champs = get_champion_breakdown(conn, puuid=args.puuid, queue_id=args.queue)
        if champs:
            print("\n--- Champion Breakdown ---")
            print(format_champ_table(champs))
    return 0


def run_list(args):
    conn = get_db_connection(args.db_path)
    matches = list_recent_matches(conn, limit=args.limit, puuid=args.puuid)
    if not matches:
        print("No matches found in database.")
        return 0

    print(f"\n{'Match ID':<16} {'Queue':<14} {'Result':<6} {'Champion':<12} {'K/D/A':<12} {'CS':<5}")
    print("-" * 70)
    for m in matches:
        q_str = QUEUE_NAMES.get(m["queue_id"], str(m["queue_id"]))[:12]
        res = "WIN" if m["win"] else "LOSS"
        kda = f"{m['kills']}/{m['deaths']}/{m['assists']}"
        print(f"{m['match_id']:<16} {q_str:<14} {res:<6} {m['champion_name']:<12} {kda:<12} {m['total_minions_killed']:<5}")
    return 0


def main():
    args = parse_args()
    api_key = args.api_key or os.environ.get("RIOT_API_KEY")

    if args.command == "sync" and not api_key:
        print("Missing API key. Pass --key or set RIOT_API_KEY.", file=sys.stderr)
        sys.exit(1)

    if args.command == "sync":
        sys.exit(run_sync(args, api_key))
    elif args.command == "stats":
        sys.exit(run_stats(args))
    elif args.command == "list":
        sys.exit(run_list(args))


if __name__ == "__main__":
    main()
