# BMW paint data and colour families

The game loads `bmw_individual_colours_complete_five_models_with_images.json` as static data. The file contains 473 model-level records grouped into 154 unique paint codes by `image_dataset_loader.js`. Each record includes BMW paint name/type, model, a COSY static image URL, and a rendered video URL. Current static image URLs were checked against the live host: the sample returned HTTP 200 (`image/jpeg`, 7.3 KB). Images are remote and may later expire or change. No image files are checked into the repository.

## Prepare a review set

Use Python 3.10 or newer. From the repository root:

```sh
python -m pip install -r requirements-colour-review.txt
python scripts/colour_review.py review --clusters 12 --seed 42
```

The script downloads one image per paint code to `data/image-cache/`, checks that the response is an image, decodes it, records its dimensions and simple low-resolution/near-uniform flags, and writes one line per paint to `data/colour-review.csv`. It resizes each image to 48×48, takes the median RGB of the center crop, then runs scikit-learn K-means with the supplied cluster count and seed. This is a repeatable visual grouping aid; cluster numbers have no inherent colour-family meaning. Inspect the cached images and the full review CSV before deciding whether a cluster is coherent. `--refresh` fetches the remote images again.

The BMW COSY renderer can show a vehicle/render rather than an isolated, controlled paint swatch. Crop, background, reflections, lighting, body shape, and renderer changes can dominate representative pixels. The automated flags are only triage signals: every successfully fetched image starts as `awaiting-visual-review`, and fetch/decode failures remain explicit. A cluster or paint-name hint is never treated as a visually validated label.

## Correct assignments and rebuild

Edit `data/color-family-overrides.csv`, keeping one row per paint code. Supported families are Blue, Green, Red, Purple, Yellow, Orange, Brown, Bronze, Grey, Silver, White, Black, Beige, and Unknown. Set `family_status` to `reviewed`, `provisional`, or `unreviewed`; set `image_review_status` to `reviewed`, `needs-review`, `fetch-failed`, or `unavailable`; use `review_note` to record why a rendered image is misleading or an assignment differs from the name hint. The override file is the hand-maintained source of truth and is not rewritten by either command.

Then run:

```sh
python scripts/colour_review.py build
```

This adds explicit `color_family`, `color_family_source`, `color_family_status`, `image_review_status`, and `image_review_note` values to every source record, preserving the original fields. Existing paints without overrides receive a provisional paint-name hint when one unambiguous name cue exists, otherwise `Unknown`/`unreviewed`. Manually reviewed values always take precedence over those hints. Runtime play only reads these static values; it does not fetch images, run clustering, or require Python. Commit both the override CSV and regenerated JSON so corrections survive future rebuilds.

## Dataset fields

- `paint_code`, `paint_name`, `paint_type`: source identity and finish inputs.
- `static_image_url`, `video_url`: BMW source media references.
- `color_family`: explicit family value consumed by the game.
- `color_family_source`: `manual-override`, `paint-name-hint`, or `unassigned`.
- `color_family_status`: confidence state consumed by clue feedback; only `reviewed` families receive a match/mismatch verdict.
- `image_review_status`, `image_review_note`: visible data-quality workflow state.

`image_review_status` is deliberately separate from the family label. A reviewer may decide a render is unsuitable while still confidently assigning a family from the official paint name or another source.
