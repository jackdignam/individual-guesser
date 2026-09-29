#!/usr/bin/env python3
"""Prepare image and K-means review files, then build the static game dataset.

Run `python scripts/colour_review.py review` to fetch/cache images and create
data/colour-review.csv. Review clusters visually and record final choices in
data/color-family-overrides.csv. Run `python scripts/colour_review.py build`
to write explicit family fields into the runtime JSON.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bmw_individual_colours_complete_five_models_with_images.json"
OUTPUT = ROOT / "bmw_individual_colours_complete_five_models_with_images.json"
OVERRIDES = ROOT / "data" / "color-family-overrides.csv"
REVIEW = ROOT / "data" / "colour-review.csv"
CACHE = ROOT / "data" / "image-cache"
FAMILIES = {"Blue", "Green", "Red", "Purple", "Yellow", "Orange", "Brown", "Bronze", "Grey", "Silver", "White", "Black", "Unknown"}


def family_hint(name: str) -> str:
    value = name.casefold()
    rules = [
        ("Blue", r"\bblue\b|\bbleu\b|\bazur\b"),
        ("Green", r"\bgreen\b|\bverde\b|\bmantis\b|\bperidot\b|\bmalachite\b|\bagave\b"),
        ("Red", r"\bred\b|\bruby\b|\brosso\b|\brosso\b|\bcinabar\b|\bchili\b|\bimola\b|\bbarbera\b"),
        ("Purple", r"\bviolet\b|\bpurple\b|\borchid\b|\bamethyst\b|\bbelladonna\b|\bmora\b"),
        ("Yellow", r"\byellow\b|\bdakar\b"),
        ("Orange", r"\borange\b|\bcopper\b"),
        ("Brown", r"\bbrown\b|\bmahogany\b|\bchestnut\b|\bmacadamia\b|\bsepia\b|\bjatoba\b"),
        ("Bronze", r"\bbronze\b|\bbrass\b"),
        ("Grey", r"\bgrey\b|\bgray\b|\bgunmetal\b|\bchalk\b|\bstone\b|\bplatinum\b|\bstratus\b"),
        ("Silver", r"\bsilver\b"),
        ("White", r"\bwhite\b"),
        ("Black", r"\bblack\b"),
    ]
    found = [label for label, pattern in rules if re.search(pattern, value)]
    return found[0] if len(found) == 1 else "Unknown"


def rows_by_code():
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for row in rows:
        code = str(row.get("paint_code", "")).strip()
        if code:
            grouped[code].append(row)
    return rows, grouped


def read_overrides():
    with OVERRIDES.open(newline="", encoding="utf-8-sig") as stream:
        return {row["paint_code"].strip(): row for row in csv.DictReader(stream) if row.get("paint_code", "").strip()}


def read_image_review():
    if not REVIEW.exists():
        return {}
    with REVIEW.open(newline="", encoding="utf-8-sig") as stream:
        return {row["paint_code"].strip(): row for row in csv.DictReader(stream) if row.get("paint_code", "").strip()}


def review(args):
    try:
        import numpy as np
        from PIL import Image, ImageStat
        from sklearn.cluster import KMeans
    except ImportError as exc:
        print("Image review dependencies are missing. Install with: python -m pip install -r requirements-colour-review.txt", file=sys.stderr)
        raise SystemExit(2) from exc

    _, grouped = rows_by_code()
    images, features, errors = [], [], {}
    CACHE.mkdir(parents=True, exist_ok=True)
    for code, group in sorted(grouped.items()):
        name = group[0].get("paint_name", "")
        url = next((r.get("static_image_url", "") for r in group if r.get("static_image_url")), "")
        image_path = CACHE / f"{code}.jpg"
        try:
            if args.refresh or not image_path.exists():
                request = urllib.request.Request(url, headers={"User-Agent": "PaintStudyColourReview/1.0"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    content_type = response.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        raise ValueError(f"unexpected content type: {content_type or 'missing'}")
                    image_path.write_bytes(response.read())
            image = Image.open(image_path).convert("RGB")
            width, height = image.size
            sample = image.resize((48, 48))
            # Center crop discounts borders, while preserving all three channels.
            left, top = 8, 8
            center = sample.crop((left, top, 40, 40))
            pixels = np.asarray(center, dtype=np.float32).reshape(-1, 3)
            features.append(np.median(pixels, axis=0))
            stat = ImageStat.Stat(image)
            flags = []
            if min(width, height) < 80:
                flags.append("low-resolution")
            if max(stat.stddev) < 4:
                flags.append("near-uniform-image")
            images.append({"paint_code": code, "paint_name": name, "image_url": url, "image_path": image_path.as_posix(), "width": width, "height": height, "image_quality_flags": ";".join(flags) or "none-detected"})
        except Exception as exc:  # URL and image decoding errors belong in the review file.
            errors[code] = f"image-unavailable: {type(exc).__name__}: {exc}"
            images.append({"paint_code": code, "paint_name": name, "image_url": url, "image_path": "", "width": "", "height": "", "image_quality_flags": errors[code]})

    clusters = {}
    if features:
        count = min(args.clusters, len(features))
        labels = KMeans(n_clusters=count, random_state=args.seed, n_init=10).fit_predict(np.asarray(features))
        good = [item for item in images if item["paint_code"] not in errors]
        clusters = {item["paint_code"]: int(label) for item, label in zip(good, labels)}
    overrides = read_overrides()
    fields = ["paint_code", "paint_name", "image_url", "image_path", "width", "height", "image_quality_flags", "cluster_id", "name_family_hint", "suggested_family", "family_status", "image_review_status", "review_note"]
    with REVIEW.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in images:
            override = overrides.get(item["paint_code"], {})
            writer.writerow({**item, "cluster_id": clusters.get(item["paint_code"], ""), "name_family_hint": family_hint(item["paint_name"]), "suggested_family": override.get("color_family") or family_hint(item["paint_name"]), "family_status": override.get("family_status") or "provisional", "image_review_status": override.get("image_review_status") or ("fetch-failed" if item["paint_code"] in errors else "awaiting-visual-review"), "review_note": override.get("review_note", "")})
    print(f"Reviewed {len(images)} unique paints; {len(errors)} image fetch/decode failures.")
    print(f"Wrote {REVIEW.relative_to(ROOT)}. Cluster IDs are suggestions; inspect the cached images before editing {OVERRIDES.relative_to(ROOT)}.")


def build(_args):
    rows, grouped = rows_by_code()
    overrides = read_overrides()
    image_reviews = read_image_review()
    assignments = {}
    for code, group in grouped.items():
        name = group[0].get("paint_name", "")
        override = overrides.get(code, {})
        image_review = image_reviews.get(code, {})
        family = override.get("color_family", "").strip()
        status = override.get("family_status", "").strip()
        image_status = override.get("image_review_status", "").strip()
        note = override.get("review_note", "").strip()
        if family:
            if family not in FAMILIES:
                raise SystemExit(f"Unsupported color_family {family!r} for {code}; choose from {', '.join(sorted(FAMILIES))}.")
            if status not in {"reviewed", "provisional", "unreviewed"}:
                raise SystemExit(f"Set family_status to reviewed, provisional, or unreviewed for override {code}.")
            if image_status not in {"reviewed", "needs-review", "fetch-failed", "unavailable"}:
                raise SystemExit(f"Set image_review_status for override {code} to reviewed, needs-review, fetch-failed, or unavailable.")
            source = "manual-override"
        else:
            family = family_hint(name)
            status = "provisional" if family != "Unknown" else "unreviewed"
            image_status = image_review.get("image_review_status") or ("awaiting-visual-review" if any(r.get("static_image_url") for r in group) else "unavailable")
            source = "paint-name-hint" if family != "Unknown" else "unassigned"
        image_note = note or image_review.get("image_quality_flags", "")
        assignments[code] = {"color_family": family, "color_family_source": source, "color_family_status": status, "image_review_status": image_status, "image_review_note": image_note}
    for row in rows:
        row.update(assignments.get(str(row.get("paint_code", "")).strip(), {"color_family": "Unknown", "color_family_source": "unassigned", "color_family_status": "unreviewed", "image_review_status": "unavailable", "image_review_note": "Missing paint code"}))
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = defaultdict(int)
    for data in assignments.values():
        statuses[data["color_family_status"]] += 1
    print(f"Wrote {len(rows)} model records covering {len(assignments)} paints to {OUTPUT.name}.")
    print("Family status counts: " + ", ".join(f"{key}={value}" for key, value in sorted(statuses.items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    review_parser = commands.add_parser("review", help="Download paint images and produce a K-means review CSV")
    review_parser.add_argument("--clusters", type=int, default=12)
    review_parser.add_argument("--seed", type=int, default=42)
    review_parser.add_argument("--refresh", action="store_true", help="Fetch all images again")
    review_parser.set_defaults(func=review)
    build_parser = commands.add_parser("build", help="Apply overrides and write explicit family fields into game data")
    build_parser.set_defaults(func=build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
