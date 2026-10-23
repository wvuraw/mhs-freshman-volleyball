# MHS SidelineHD metadata collector (starter)

This is a **non-destructive test version**: it only creates or updates `data/games.json` and `data/clips.json`. It does **not** modify the current website or publish a new UI.

## Setup

1. Copy `config.json`, `collect.py`, and `.github/workflows/update-clips.yml` into the root of the existing `mhs-freshman-volleyball` repository (preserving the workflow folder structure).
2. Commit and push to the repository's default branch.
3. In GitHub, open **Actions → Update SidelineHD clip data → Run workflow**. Scheduled runs occur roughly every 3 hours (GitHub schedules can be delayed).
4. After the first run, inspect `data/games.json` and `data/clips.json` in the repository.
5. Add other players' **API claimed-player IDs** to `config.json` after verifying them. Public profile slugs are not necessarily API player IDs.

## Important limitations

- Only Elin is configured initially; the other nine MHS players still need verified API IDs.
- The initial run walks the configured player's full clip history, up to `max_pages_per_player`; subsequent runs currently also walk full history to catch delayed edits. This is deliberately conservative and will be optimized after validation.
- `gameId` filters all historical player clips to games returned by the configured team's endpoint.
- Duplicate video records for a player/game/clip are combined; all observed `playType` values are retained in `playTypes`.
- `playTypes` and event metadata should **not** be presented as official statistics without additional validation.
- The endpoint is undocumented and may change, require authentication, or impose rate limits. The observed version header is included but may cease working. Use only data you are authorized to publish.
- The workflow commits metadata to the repository. On a **public repository, JSON files are public**, including video links and names; review what you publish before enabling for youth teams.
- A workflow must have repository write permissions to commit. If `git push` fails with a permission error, check **Settings → Actions → General → Workflow permissions**.
- No website templates or HTML files are modified. A separate integration step will be needed to display the new JSON on GitHub Pages.
