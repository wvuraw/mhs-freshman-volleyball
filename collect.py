#!/usr/bin/env python3
"""Collect public SidelineHD volleyball clip metadata for one team's games.

Uses observed, undocumented public endpoints; they may change. Does not download videos.
Run from the repository root: python collect.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://sideline-api-439745628468.us-central1.run.app"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HEADERS = {"X-Sideline-Mobile-Version": "2099.10.10", "Accept": "application/json", "User-Agent": "MHS-clip-metadata-collector/1.0"}


def fetch_json(path):
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            code = getattr(exc, "code", None)
            if code is not None and code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def read_existing(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_if_changed(path, payload):
    content = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return True


def clip_key(player_id, game_id, clip_id):
    return json.dumps([player_id, game_id, clip_id], separators=(",", ":"))


def main():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    team_id = config["team_id"]
    games = fetch_json(f"/v2/teams/{urllib.parse.quote(team_id, safe='')}/games")
    if not isinstance(games, list):
        raise ValueError("Unexpected games API response: expected a list")
    game_map = {g["id"]: g for g in games if isinstance(g, dict) and g.get("id")}
    if not game_map:
        raise ValueError("Team API returned no identifiable games; refusing to overwrite saved data")

    # Merge with prior saved data so incremental runs never discard earlier matches.
    previous = read_existing(DATA / "clips.json", {"clips": []})
    merged = {}
    for clip in previous.get("clips", []):
        key = clip_key(clip["playerId"], clip["gameId"], clip["id"])
        merged[key] = clip

    for player in config["players"]:
        player_id = player["api_player_id"]
        if not player_id:
            continue
        seen_cursors = set()
        cursor = None
        pages = 0
        records = 0
        while pages < config.get("max_pages_per_player", 150):
            path = f"/api/player/{urllib.parse.quote(player_id, safe='')}/clips?sport={urllib.parse.quote(config.get('sport', 'vb'))}"
            if cursor is not None:
                path += "&startAfter=" + urllib.parse.quote(str(cursor))
            result = fetch_json(path)
            if not isinstance(result, dict) or not isinstance(result.get("clips"), list):
                raise ValueError(f"Unexpected clips response for {player['name']}")
            batch = result["clips"]
            for raw in batch:
                if not isinstance(raw, dict) or raw.get("gameId") not in game_map or not raw.get("id"):
                    continue
                key = clip_key(player_id, raw["gameId"], raw["id"])
                previous_clip = merged.get(key, {})
                tags = set(previous_clip.get("playTypes", []))
                if raw.get("playType"):
                    tags.add(raw["playType"])
                # Preserve previously seen metadata while updating current fields.
                record = {**previous_clip, **raw, "playerId": player_id,
                          "playerName": player["name"], "playTypes": sorted(tags)}
                merged[key] = record
                records += 1
            pages += 1
            next_cursor = result.get("next")
            if next_cursor is None or not batch:
                break
            token = str(next_cursor)
            if token in seen_cursors or token == str(cursor):
                raise RuntimeError(f"Repeated pagination cursor for {player['name']}")
            seen_cursors.add(token)
            cursor = next_cursor
            time.sleep(0.3)
        else:
            print(f"WARNING: {player['name']} reached the {pages}-page limit; increase max_pages_per_player if needed", file=sys.stderr)
        print(f"{player['name']}: {pages} pages, {records} team clip records encountered")

    # Do not publish clips for games no longer on the selected team page.
    clips = [c for c in merged.values() if c["gameId"] in game_map]
    clips.sort(key=lambda c: (c.get("startTs") or 0, c["gameId"], c["id"], c["playerId"]), reverse=True)
    games_out = sorted(games, key=lambda g: (g.get("scheduleTsStart") or 0, g.get("id", "")), reverse=True)
    a = write_if_changed(DATA / "games.json", {"teamId": team_id, "games": games_out})
    b = write_if_changed(DATA / "clips.json", {"teamId": team_id, "clips": clips})
    print(f"Team games: {len(game_map)} | Unique team/player clips: {len(clips)} | Changed: {a or b}")
    print("NOTE: playTypes reflect SidelineHD clip tags, not independently verified official stats.")


if __name__ == "__main__":
    main()
