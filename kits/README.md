# Academy club shirts

PNG shirt images for the initial-club roulette in thefenomeno.com. Maximum
resolution: 512 × 512 px, with smaller originals left at their original size.
Palette encoding reduces transfer size while keeping the original shirt details.
Cutouts preserve alpha; photographs retain their original backgrounds. The game
uses the `presentation` field to distinguish photos from transparent cutouts.

- `sources.json`: file name, club, country, provider team ID, original image URL,
  metadata catalog or source page, dimensions, encoding and SHA-256 for every image.
- `missing.json`: game club IDs without a verified usable image in the consulted
  catalogs. These clubs remain eligible for the draw and use the crest fallback.

Images come from TheSportsDB's public equipment images, Football Kit Archive,
club announcements and shirt catalogs. The metadata references
include recent lookups and publicly archived team records; exact catalog revisions
are retained per file in `sources.json`, including the original page for curated
photographs. Historical shirt models are illustrative,
and do not represent the availability or model delivered by Football Mystery Box.
No shirts are synthesized, and no sponsors or club marks are replaced. Some
photos include the original product setting or a person wearing the shirt.
`sameClubAs` documents duplicate real-club identities already present in the game
pool, without changing their game IDs or excluding either entry.

The importer and the game-side file catalog live in the application repository:
`scripts/download-academy-kits.mjs` and `src/game/academyKits.json`. Import with a
checkout of this repository alongside the application checkout. Publish the assets,
then pin `ACADEMY_KIT_CDN` in the application to the published commit so new file
URLs do not depend on the moving `@main` cache.
