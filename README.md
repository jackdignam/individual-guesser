# Paint Study — BMW Individual

A static daily paint identification game. The browser loads the paint JSON directly, so no build step, package installation, backend, or runtime clustering is required. Deploy the repository root as a static Vercel project.

## Run locally

Serve this directory with any static file server, then open its URL. For example:

```sh
python -m http.server 8000
```

The BMW mode offers three daily cars with no repeated colour families and at least one Frozen finish, five guesses per car, paint-name/code suggestions, finish and colour-family clues, saved progress, shareable results, and a daily reset at Dublin midnight. The same date always gets the same set. Paint answers are rotated so none repeats within the previous 17 days; because the current data has only 18 Frozen paints and one is required each day, a Frozen answer must recur after at most 18 days. The non-Frozen pool is rotated in roughly 68-day cycles.

To check the daily rollover without waiting for midnight, serve locally and open `/?testDay=2026-09-29`. Start BMW mode and read the amber test banner for the selected paints and models. Change the date to `/?testDay=2026-09-30` and reload; the next day’s set appears. Test progress uses separate local storage and does not change your regular daily game. Remove `testDay` to return to the real Dublin date and countdown. The normal game still switches at Dublin midnight and reloads when it detects the new date.

The current data has five source model names: BMW M340i Touring, BMW 8 Series Cabrio, BMW M5 Sedan, BMW X4, and BMW X3 M50. There is no model allowlist in the current draw; each paint code is grouped and its first source model record supplies the car media. The source contains no M3, M4, or 4 Series records. PTS is a mode-selection placeholder until an appropriate dataset and rules are available.

## Paint data

`image_dataset_loader.js` groups source records by paint code and preserves the existing finish normalization. The generated JSON also stores an explicit `color_family` and its review status; gameplay does not calculate families from images. See [DATA_WORKFLOW.md](DATA_WORKFLOW.md) for image checks, reproducible K-means review, human overrides, and rebuilding the runtime dataset.
