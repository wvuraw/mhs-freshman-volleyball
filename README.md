# MHS SidelineHD automatic roster + clip collector

Uses undocumented public SidelineHD APIs (may change). Does not download video.
Fetches team roster, team games, and clips for each claimed player; filters clips by team game IDs.
Unclaimed players remain in `data/roster.json` but cannot be collected through the claimed-player endpoint.
Individual player API errors are logged; previously saved clips are retained.

## Install
Replace `collect.py`, `config.json`, and `.github/workflows/update-clips.yml` in your existing repository.
Run the **Update SidelineHD clip data** GitHub Action manually once, then inspect
`data/roster.json`, `data/games.json`, and `data/clips.json`.
The workflow also runs every three hours. GitHub may delay scheduled jobs.
The existing website HTML is not yet connected to these JSON files.

## Cautions
The first full-roster run may take several minutes. No authorization headers or team PINs are used.
Clip tags are SidelineHD metadata, not independently verified statistics.
