# MHS player history pilot

Replace ONLY these three existing repository files:

- `index.html`
- `collect.py`
- `.github/workflows/update-clips.yml` (create/update via GitHub's file editor if hidden folders cannot be uploaded)

Keep your existing `config.json` and existing `data/` folder.

Run **Actions > Update SidelineHD clip data > Run workflow**. The first run writes `data/player-history.json`. The homepage will report an error until that file exists. Check the Action logs and GitHub repository before opening the site.

The collector uses undocumented public SidelineHD API endpoints. It fetches all available volleyball clip metadata for claimed roster profiles and retains current-team match filtering. Historical team names are not reliably available from the known endpoint, so the UI labels unknown teams using their IDs rather than guessing. Video files are **not** stored on GitHub. The Download / Save link points to SidelineHD's `fileDownloadUrl`; cross-origin browser download restrictions or expired links may require the user to open the video and use Save video as, or may prevent downloads. Test on real clips.

Clip metadata can include duplicate videos tagged for multiple players; deduplication is per player/game/clip ID. Player history is retained between runs; a new claim becomes available on the next collection. No private authorization credentials are needed.
