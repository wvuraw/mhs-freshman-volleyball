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
    team = fetch_json(f"/v2/teams/{urllib.parse.quote(team_id, safe='')}")
    if not isinstance(team, dict) or team.get("id") != team_id or not isinstance(team.get("players"), list):
        raise ValueError("Unexpected team roster response; refusing to overwrite data")
    roster = []
    for p in team["players"]:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        roster.append({
            "id": p["id"],
            "name": " ".join(filter(None, [p.get("nameFirst"), p.get("nameLast")])),
            "jerseyNum": p.get("jerseyNum", ""),
            "claimedPlayerId": p.get("claimedPlayerId") or "",
            "isActive": p.get("isActive", True),
            "imageUrlSmall": p.get("imageUrlSmall") or "",
            "imageUrl": p.get("imageUrl") or "",
        })
    if not roster:
        raise ValueError("Team roster empty; refusing to overwrite data")
    roster.sort(key=lambda p: (int(p["jerseyNum"]) if str(p["jerseyNum"]).isdigit() else 9999, p["name"]))
    games = fetch_json(f"/v2/teams/{urllib.parse.quote(team_id, safe='')}/games")
    if not isinstance(games, list):
        raise ValueError("Unexpected games API response: expected a list")
    game_map = {g["id"]: g for g in games if isinstance(g, dict) and g.get("id")}

    # Merge with prior saved data so incremental runs never discard earlier matches.
    previous = read_existing(DATA / "clips.json", {"clips": []})
    merged = {}
    for clip in previous.get("clips", []):
        key = clip_key(clip["playerId"], clip["gameId"], clip["id"])
        merged[key] = clip

    history_previous = read_existing(DATA / "player-history.json", {"clips": []})
    history = {}
    for clip in history_previous.get("clips", []):
        if isinstance(clip, dict) and clip.get("id") and clip.get("playerId"):
            history[clip_key(clip["playerId"], clip.get("gameId", ""), clip["id"])] = clip
    # Resolve historical team names once per unique team, caching results between runs.
    previous_directory = read_existing(DATA / "teams.json", {"teams": {}})
    team_directory = dict(previous_directory.get("teams", {}))
    team_directory[team_id] = team.get("name") or team.get("teamName") or "MHS Freshman 2026"
    failures = []
    for player in roster:
        player_id = player["claimedPlayerId"]
        if not player_id:
            continue
        seen_cursors = set()
        cursor = None
        pages = 0
        records = 0
        try:
            while pages < config.get("max_pages_per_player", 150):
                path = f"/api/player/{urllib.parse.quote(player_id, safe='')}/clips?sport={urllib.parse.quote(config.get('sport', 'vb'))}"
                if cursor is not None:
                    path += "&startAfter=" + urllib.parse.quote(str(cursor))
                result = fetch_json(path)
                if not isinstance(result, dict) or not isinstance(result.get("clips"), list):
                    raise ValueError("Unexpected clips response")
                batch = result["clips"]
                for raw in batch:
                    if not isinstance(raw, dict) or not raw.get("id"):
                        continue
                    game_id = raw.get("gameId") or ""
                    key = clip_key(player_id, game_id, raw["id"])
                    previous_clip = history.get(key, {})
                    tags = set(previous_clip.get("playTypes", []))
                    if raw.get("playType"):
                        tags.add(str(raw["playType"]))
                    # Store only public display fields, not the full upstream payload.
                    record = {
                        "id": raw["id"], "gameId": game_id, "playerId": player_id,
                        "playerName": player["name"], "playTypes": sorted(tags),
                        "startTs": raw.get("startTs") or previous_clip.get("startTs"),
                        "textMatchupName": raw.get("textMatchupName") or previous_clip.get("textMatchupName") or "",
                        "teamId": raw.get("teamId") or previous_clip.get("teamId") or "",
                        "fileDownloadUrl": raw.get("fileDownloadUrl") or previous_clip.get("fileDownloadUrl") or "",
                    }
                    history[key] = record
                    if game_id in game_map:
                        old_clip = merged.get(key, {})
                        team_tags = set(old_clip.get("playTypes", [])) | set(record["playTypes"])
                        merged[key] = {**old_clip, **record, "playTypes": sorted(team_tags)}
                        records += 1
                pages += 1
                next_cursor = result.get("next")
                if next_cursor is None or not batch:
                    break
                token = str(next_cursor)
                if token in seen_cursors or token == str(cursor):
                    raise RuntimeError("Repeated pagination cursor")
                seen_cursors.add(token)
                cursor = next_cursor
                time.sleep(config.get("request_delay_seconds", 0.3))
            else:
                raise RuntimeError(f"Reached {pages}-page limit; increase max_pages_per_player")
            print(f"{player['name']}: {pages} pages, {records} team clip records encountered")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as exc:
            failures.append(f"{player['name']}: {exc}")
            print(f"WARNING: {player['name']} retrieval incomplete ({exc}); previously collected clips retained", file=sys.stderr)

    # Do not publish clips for games no longer on the selected team page.
    clips = [c for c in merged.values() if c["gameId"] in game_map]
    clips.sort(key=lambda c: (c.get("startTs") or 0, c["gameId"], c["id"], c["playerId"]), reverse=True)
    games_out = sorted(games, key=lambda g: (g.get("scheduleTsStart") or 0, g.get("id", "")), reverse=True)
    r = write_if_changed(DATA / "roster.json", {"teamId": team_id, "players": roster})
    a = write_if_changed(DATA / "games.json", {"teamId": team_id, "games": games_out})
    b = write_if_changed(DATA / "clips.json", {"teamId": team_id, "clips": clips})
    history_clips = sorted(history.values(), key=lambda c: (c.get("startTs") or 0, c.get("id", ""), c.get("playerId", "")), reverse=True)
    h = write_if_changed(DATA / "player-history.json", {"teamId": team_id, "clips": history_clips})
    historic_ids = sorted({str(c.get("teamId")) for c in history_clips if c.get("teamId")})
    for historic_id in historic_ids:
        if historic_id in team_directory and team_directory[historic_id]:
            continue
        try:
            past = fetch_json(f"/v2/teams/{urllib.parse.quote(historic_id, safe='')}")
            if isinstance(past, dict) and past.get("id") == historic_id:
                name = past.get("name") or past.get("teamName") or past.get("displayName")
                if isinstance(name, str) and name.strip():
                    team_directory[historic_id] = name.strip()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"WARNING: Could not resolve historical team {historic_id}: {exc}", file=sys.stderr)
        time.sleep(config.get("request_delay_seconds", 0.3))
    d = write_if_changed(DATA / "teams.json", {"teams": team_directory})
    print(f"Historical teams resolved: {len(team_directory)} | Changed: {d}")
    print(f"Player history: {len(history_clips)} records | Changed: {h}")
    print(f"Team games: {len(game_map)} | Unique team/player clips: {len(clips)} | Changed: {r or a or b}")
    print(f"Roster: {len(roster)} players | Claimed: {sum(bool(p['claimedPlayerId']) for p in roster)} | Failed: {len(failures)}")
    if failures:
        print("WARNING: Some player retrievals were incomplete; see warnings above.", file=sys.stderr)
    print("NOTE: playTypes reflect SidelineHD clip tags, not independently verified official stats.")


if __name__ == "__main__":
    main()
