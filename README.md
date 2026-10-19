# thefenomeno-assets

Static image assets for [thefenomeno.com](https://thefenomeno.com) — club crests,
trophy photos and Hall of Fame streamer cards. Served via jsDelivr CDN to keep them
off the app's serverless edge (cost). Public on purpose (these already render on the
live site); no source code here.

## Academy shirts

`kits/` contains transparent club shirt PNGs for the initial-club reveal.
`kits/sources.json` records each image's original source, team identity,
metadata snapshot, dimensions and SHA-256. `kits/missing.json` records clubs
without a usable image in the consulted sources. See [kits/README.md](kits/README.md).