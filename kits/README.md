# Academy club shirts

Transparent PNGs for the initial-club roulette in thefenomeno.com. Maximum
resolution: 512 × 512 px, with smaller originals left at their original size.
Palette encoding reduces transfer size while keeping the shirt artwork and alpha.

- `sources.json`: file name, club, country, provider team ID, original image URL,
  pinned metadata catalog, dimensions, encoding and SHA-256 for every image.
- `missing.json`: game club IDs without a verified usable image in the consulted
  catalogs. These clubs remain eligible for the draw and use the crest fallback.

Artwork comes from TheSportsDB's public equipment images. The metadata references
include recent lookups and publicly archived team records; exact catalog revisions
are retained per file in `sources.json`. Historical shirt models are illustrative,
and do not represent the availability or model delivered by Football Mystery Box.
No shirts are synthesized, and no sponsors or club marks are replaced.

The importer and the game-side file catalog live in the application repository:
`scripts/download-academy-kits.mjs` and `src/game/academyKits.json`. Import with a
checkout of this repository alongside the application checkout. Publish the assets,
then pin `ACADEMY_KIT_CDN` in the application to the published commit so new file
URLs do not depend on the moving `@main` cache.