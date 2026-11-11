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

## Fonts

`fonts/` holds WOFF2 web fonts, subset to the Google Fonts "latin" range
(Basic Latin, Latin-1 incl. Portuguese accents, common punctuation, €).

**Gravata Display** — italic condensed display face derived from Noto Sans
(SIL OFL 1.1, see [fonts/GravataDisplay-OFL.txt](fonts/GravataDisplay-OFL.txt)):

| File | Base | Weight |
|---|---|---|
| `GravataDisplay-Original.woff2` | Noto Sans ExtraCondensed Black Italic, tighter spacing | 900 |
| `GravataDisplay-Clean.woff2` | Noto Sans Condensed ExtraBold Italic | 800 |

```css
@font-face {
  font-family: 'Gravata Display';
  src: url('https://cdn.jsdelivr.net/gh/TheSMF-Group/thefenomeno-assets@main/fonts/GravataDisplay-Original.woff2') format('woff2');
  font-weight: 900;
  font-style: italic;
  font-display: swap;
}
@font-face {
  font-family: 'Gravata Display Clean';
  src: url('https://cdn.jsdelivr.net/gh/TheSMF-Group/thefenomeno-assets@main/fonts/GravataDisplay-Clean.woff2') format('woff2');
  font-weight: 800;
  font-style: italic;
  font-display: swap;
}
```