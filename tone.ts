/**
 * Tone handling for the mannequin feature layers. See NOTES.md.
 *
 * The 32 layers split into two families, and each gets a different treatment:
 *
 *   SKIN (nose, mouth, ear, eye)   `applyToneToRgba` — the per-channel `k`.
 *   HAIR (hair, beard, brow)       `applyHairEdgeToRgba` — the `w(r)` edge fix,
 *                                  from the measured table in `wr.json` when the
 *                                  layer has one, `w = r` otherwise.
 *
 * A HAIR layer must NOT get `k`: hair colour is not a function of skin tone, and
 * applying `k` to it was the source of the heavy gamut clipping (2.58% on
 * `hair_midcurly` x MST-01). But it cannot be left alone either — the
 * morphological mask carries `tmp_1`'s skin along with the hair, and on a darker
 * base that skin stays light and draws a pale rim along the hairline.
 *
 * `applyHairEdgeToRgba` fixes the rim without touching the hair. See the
 * function for the derivation; the short version is that shading is
 * multiplicative, so `r = layer / source` is the shading factor already measured
 * against the source base, and `r` doubles as the coverage weight.
 *
 * Every layer in `layers/` carries the skin of `raw/tmp_1.png`. To composite
 * one over a base of a different tone, its pixels are rescaled by a per-channel
 * factor **in linear light**:
 *
 *     linear = srgbToLinear(pixel)
 *     linear *= k            // k = meanLinear(destination skin) / meanLinear(tmp_1 skin)
 *     pixel  = linearToSrgb(linear)
 *
 * Multiplication in linear light is what shading actually does, so it keeps the
 * nose/skin luminance ratio and can never produce a negative value the way an
 * additive shift in Lab does. Alpha is never touched.
 *
 * The factors live in `tones.json`, one entry per Monk Skin Tone base. The
 * hair tables live in `wr.json`, one entry per native HAIR layer.
 * No external dependencies.
 */

/** Per-channel multiplier in linear light. */
export interface ToneFactor {
  r: number;
  g: number;
  b: number;
}

export interface Tone {
  /** "MST-01" … "MST-10". */
  id: string;
  /** Nominal hex of the Monk step. Provenance only — never a display colour. */
  hex: string | null;
  /**
   * The skin as it actually renders: the lit forehead of this base.
   * **This is what a swatch or a store selector shows.**
   */
  measuredHex: string;
  /** File the factor was measured against, e.g. "skin01.webp". */
  base: string;
  k: ToneFactor;
}

export interface ToneTable {
  /** The layers' source of skin; k is relative to this. */
  source: string;
  /** Cheek window behind `k`: [x0, y0, x1, y1]. */
  windowK: [number, number, number, number];
  /** Forehead window behind `measuredHex`. */
  windowDisplay: [number, number, number, number];
  tones: Tone[];
}

/**
 * `wr.json`: the measured `w(r)` of each native HAIR layer, per channel, per
 * band of `r`. `edges` has N + 1 numbers and each channel N values; a `null`
 * is a band the reference had fewer than 20 blocks in. See NOTES.md, "{E, T}"
 * and the sections that follow it.
 */
export interface WrTable {
  source: string;
  reference: string;
  rule: string;
  edges: number[];
  layers: Record<string, { r: (number | null)[]; g: (number | null)[]; b: (number | null)[] }>;
}

/**
 * One layer's `w(r)`, compiled for the hot loop: per channel, the centres of
 * the bands that have a value, and the values, both ascending.
 */
export interface WrCurve {
  centers: [Float64Array, Float64Array, Float64Array];
  values: [Float64Array, Float64Array, Float64Array];
}

/**
 * Compiles the table of `layerName`, or returns `null` when the layer has none
 * — the caller then falls back to `w = r`, which is the best available for the
 * coloured layers until there is a method for them (NOTES.md).
 */
export function wrCurveFor(table: WrTable, layerName: string): WrCurve | null {
  const entry = table.layers[layerName];
  if (!entry) return null;
  const n = table.edges.length - 1;
  const compile = (vals: (number | null)[]): [Float64Array, Float64Array] => {
    if (vals.length !== n) throw new Error(`wr.json: ${layerName} has ${vals.length} bands, edges imply ${n}`);
    const cs: number[] = [];
    const vs: number[] = [];
    for (let i = 0; i < n; i += 1) {
      const v = vals[i];
      if (v === null || v === undefined) continue;
      cs.push((table.edges[i]! + table.edges[i + 1]!) / 2);
      vs.push(v);
    }
    if (cs.length === 0) throw new Error(`wr.json: ${layerName} has no band with a value`);
    return [Float64Array.from(cs), Float64Array.from(vs)];
  };
  const [cr, vr] = compile(entry.r);
  const [cg, vg] = compile(entry.g);
  const [cb, vb] = compile(entry.b);
  return { centers: [cr, cg, cb], values: [vr, vg, vb] };
}

/**
 * `w(r)` for one channel: linear interpolation between band centres, the end
 * value repeated outside them, clamped to [0, 1]. Same as `numpy.interp`
 * followed by `clip`, which is what the table was validated with.
 */
export function wOfR(r: number, centers: Float64Array, values: Float64Array): number {
  const n = centers.length;
  let w: number;
  if (!(r > centers[0]!)) w = values[0]!;
  else if (r >= centers[n - 1]!) w = values[n - 1]!;
  else {
    let i = 1;
    while (centers[i]! < r) i += 1;
    const c0 = centers[i - 1]!;
    const c1 = centers[i]!;
    const v0 = values[i - 1]!;
    const v1 = values[i]!;
    w = v0 + ((r - c0) / (c1 - c0)) * (v1 - v0);
  }
  return w > 1 ? 1 : w > 0 ? w : 0;
}

// ---------------------------------------------------------------- transfer functions

/** sRGB (0..1) → linear light. IEC 61966-2-1. */
export function srgbToLinear(c: number): number {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** Linear light → sRGB (0..1). */
export function linearToSrgb(c: number): number {
  if (c <= 0) return 0;
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

/** Byte → linear, precomputed once. */
const BYTE_TO_LINEAR: Float64Array = (() => {
  const table = new Float64Array(256);
  for (let i = 0; i < 256; i += 1) table[i] = srgbToLinear(i / 255);
  return table;
})();

// ---------------------------------------------------------------- lookup table

/**
 * A tone collapses to 768 bytes: for each channel, what every possible input
 * byte becomes. Building it once and indexing per pixel keeps the hot loop to
 * three array reads, with no pow() per pixel.
 */
export type ToneLut = Uint8Array;

export function buildToneLut(k: ToneFactor): ToneLut {
  const lut = new Uint8Array(768);
  const factors = [k.r, k.g, k.b];
  for (let channel = 0; channel < 3; channel += 1) {
    const factor = factors[channel]!;
    const offset = channel * 256;
    for (let value = 0; value < 256; value += 1) {
      const out = linearToSrgb(BYTE_TO_LINEAR[value]! * factor) * 255;
      lut[offset + value] = out < 0 ? 0 : out > 255 ? 255 : Math.round(out);
    }
  }
  return lut;
}

// ---------------------------------------------------------------- application

/**
 * Applies a tone to RGBA bytes **in place**. Expects non-premultiplied alpha,
 * which is what `ImageData` carries. Alpha is copied through untouched.
 */
export function applyToneToRgba(data: Uint8ClampedArray | Uint8Array, lut: ToneLut): void {
  if (data.length % 4 !== 0) throw new Error(`RGBA buffer length ${data.length} is not a multiple of 4`);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = lut[data[i]!]!;
    data[i + 1] = lut[256 + data[i + 1]!]!;
    data[i + 2] = lut[512 + data[i + 2]!]!;
    // data[i + 3] — alpha, untouched on purpose.
  }
}

/** Same, returning a new buffer and leaving the input alone. */
export function toneRgba(data: Uint8ClampedArray, lut: ToneLut): Uint8ClampedArray {
  const copy = new Uint8ClampedArray(data);
  applyToneToRgba(copy, lut);
  return copy;
}

// ---------------------------------------------------------------- hair edge fix

/**
 * The HAIR-family transform: fixes the pale rim a hair layer draws along the
 * hairline on any base other than its source, **without touching the hair**.
 *
 * Per pixel, in linear light:
 *
 *     r    = layer / source                   per channel
 *     w    = clamp(r.red, 0, 1)               scalar — coverage is geometric
 *     out  = w * (r * base) + (1 - w) * layer
 *
 * Why this shape, and why there is nothing to tune:
 *
 * `r` is the shading factor of this layer measured against the source base, the
 * same multiplicative quantity behind the `k` transfer. Where the mask kept
 * skin, `r` is high and `r * base` is what that skin should look like on THIS
 * tone. Where there is opaque hair, `r` is near zero and the native pixel is
 * already right.
 *
 * `r` also serves as the weight, because a high `r` means "most of the base's
 * light comes through here", which is exactly when the base should decide. That
 * pins the two ends: `w(0) = 0` leaves hair alone, `w(1) = 1` rebuilds pure skin
 * from the base.
 *
 * Since `layer = r * source` by definition of `r`, the error against `r * base`
 * has a closed form:
 *
 *     error = |w - 1| * r * |source - base|
 *
 * The two pinned ends mean any curve between them trades one regime's error for
 * the other's — there is no `w` that zeroes both. `sqrt(r)` was measured and
 * rejected: it cut the transition peak 27% but moved the hair 3.7x more
 * (1.48 -> 5.44 levels), past the 2.89 that WebP q88 already costs. `w = r`
 * keeps the hair at 0.86-1.48 and is smoother than doing nothing at all.
 *
 * That was the state of things while there was no ground truth for the
 * transition band. There is one now: two renders of each native layer over
 * the MST-10 base, made by the same generator (NOTES.md, "Render de
 * referência"). Decomposing the native pixel against them gives, per pixel,
 * `L = E + T * S` — an emission `E` that stays and a transmitted skin `T * S`
 * that has to follow the base — and the measured `T / r` per band of `r` is
 * the `w(r)` table in `wr.json`. Same formula, `w` read from the table per
 * channel instead of being `r` itself:
 *
 *     w_c  = table_c(r_c)                     per channel, clamped to [0, 1]
 *     out  = w * (r * base) + (1 - w) * layer  (= L - w * r * (S - B))
 *
 * `w = r` overshoots (the pale halo, 3-17k px on MST-10) and `w = 1` undershoots
 * (12-14 levels too dark on stubble); the table sits between, cross-validated
 * between the two renders to 0.02-0.16 of the base ratio. Identity on the
 * source base is by construction: `S = B` makes the correction vanish.
 *
 * A layer without a table — the 24 coloured ones — still gets `w = r`: the
 * table does not transfer between colours (`r` does not index coverage in
 * light hair), and `w = r` is the closest thing measured for them so far.
 *
 * This is an EDGE FIX, not a tint — hair keeps its native colour.
 *
 * `layer` is modified in place. `source` is `build/source.webp` and `base` is
 * the destination tone's base, both as RGBA bytes on the same canvas. No mask is
 * needed: outside the head, source and base are both background, so `r * base`
 * collapses to `layer` and the transform is inert.
 */
export function applyHairEdgeToRgba(
  layer: Uint8ClampedArray | Uint8Array,
  source: Uint8ClampedArray | Uint8Array,
  base: Uint8ClampedArray | Uint8Array,
  curve: WrCurve | null = null,
): void {
  if (layer.length % 4 !== 0) throw new Error(`RGBA buffer length ${layer.length} is not a multiple of 4`);
  if (source.length !== layer.length || base.length !== layer.length) {
    throw new Error(
      `layer, source and base must share a canvas; got ${layer.length}, ${source.length}, ${base.length}. ` +
      "The runtime never interpolates — the build has to deliver them at the same size.",
    );
  }
  if (curve) {
    for (let i = 0; i < layer.length; i += 4) {
      for (let c = 0; c < 3; c += 1) {
        const s = BYTE_TO_LINEAR[source[i + c]!]!;
        const l = BYTE_TO_LINEAR[layer[i + c]!]!;
        const r = s > 0 ? l / s : 0;
        const w = wOfR(r, curve.centers[c]!, curve.values[c]!);
        const out = linearToSrgb(w * (r * BYTE_TO_LINEAR[base[i + c]!]!) + (1 - w) * l) * 255;
        layer[i + c] = out < 0 ? 0 : out > 255 ? 255 : Math.round(out);
      }
      // layer[i + 3] — alpha, untouched on purpose.
    }
    return;
  }
  for (let i = 0; i < layer.length; i += 4) {
    const sr = BYTE_TO_LINEAR[source[i]!]!;
    // r.red doubles as the weight; a black source pixel carries no ratio.
    let w = sr > 0 ? BYTE_TO_LINEAR[layer[i]!]! / sr : 0;
    if (w > 1) w = 1;
    else if (!(w > 0)) w = 0;
    const rest = 1 - w;
    for (let c = 0; c < 3; c += 1) {
      const s = BYTE_TO_LINEAR[source[i + c]!]!;
      const l = BYTE_TO_LINEAR[layer[i + c]!]!;
      const r = s > 0 ? l / s : 0;
      const out = linearToSrgb(w * (r * BYTE_TO_LINEAR[base[i + c]!]!) + rest * l) * 255;
      layer[i + c] = out < 0 ? 0 : out > 255 ? 255 : Math.round(out);
    }
    // layer[i + 3] — alpha, untouched on purpose.
  }
}

// ---------------------------------------------------------------- families

/** Which treatment a slot gets. See NOTES.md, "Duas famílias de camada". */
export type Family = "skin" | "hair";

/** Slot prefixes that follow the tone's `k`. */
export const SKIN_SLOTS = ["nose", "mouth", "ear", "eye"] as const;
/** Slot prefixes that keep their native colour and get the edge fix instead. */
export const HAIR_SLOTS = ["hair", "beard", "brow"] as const;

/**
 * Family of a layer name such as "hair_midcurly" or "nose_wide".
 *
 * Note that the HAIR family is not homogeneous: `brow_*` has almost no opaque
 * core (9.6% of its middle below r = 0.15, against 41-71% for hair and beard),
 * so anything calibrated on `hair_*` has to be checked on `brow_*` separately.
 */
export function familyOf(layerName: string): Family {
  const slot = layerName.split("_")[0]!;
  if ((SKIN_SLOTS as readonly string[]).includes(slot)) return "skin";
  if ((HAIR_SLOTS as readonly string[]).includes(slot)) return "hair";
  throw new Error(`unknown slot "${slot}" in layer "${layerName}"`);
}

// ---------------------------------------------------------------- composition

/**
 * Slot order, back to front. The base is drawn first, then these.
 *
 * `beard` sits BEFORE `mouth`: facial hair grows around the lip, not over it.
 * With beard after mouth, `beard_longfull`, `beard_shortfull` and
 * `beard_stubble` each covered 100% of every mouth core — the mouth slot was
 * drawn and then completely painted over, so changing mouth changed nothing in
 * the composite. Measured 10/09/2026; see NOTES.md.
 *
 * `hair` stays last: it overlaps the forehead and the ears on purpose.
 */
export const COMPOSE_ORDER = ["ear", "eye", "brow", "nose", "beard", "mouth", "hair"] as const;

/**
 * Per-layer placement offset, as a fraction of the canvas edge. Positive `dy`
 * moves the layer DOWN.
 *
 * A fraction, not pixels, because the same table has to hold at any build
 * resolution. The caller multiplies by the canvas edge and **rounds to whole
 * pixels** — a fractional `drawImage` offset would resample, and the runtime
 * never interpolates.
 *
 * `ear_*` sits about 8% of face height too high in the render: the ear top
 * lands 74-78 px above the eye line and its base 72-75 px above the nose base,
 * on the 1254 reference canvas. Both ends are off by nearly the same amount and
 * the ear's own height matches the eye-to-nose span within 5 px, so this is a
 * rigid translation, not a sizing error — which is exactly what an offset can
 * fix without touching the asset. 75/1254 = 0.0598.
 *
 * Only SKIN-family layers may be offset today. Offsetting a HAIR layer would
 * also have to shift the `source` and `base` reads inside `applyHairEdgeToRgba`,
 * since `r` is defined per pixel against the source base.
 */
export const LAYER_OFFSET: Readonly<Record<string, { dx: number; dy: number }>> = {
  ear_normal: { dx: 0, dy: 75 / 1254 },
  ear_protruding: { dx: 0, dy: 75 / 1254 },
};

/** Placement of `layerName` on a square canvas of `edge` px, in whole pixels. */
export function offsetFor(layerName: string, edge: number): { dx: number; dy: number } {
  const o = LAYER_OFFSET[layerName];
  if (!o) return { dx: 0, dy: 0 };
  if (familyOf(layerName) === "hair") {
    throw new Error(
      `${layerName} is HAIR-family and cannot be offset: applyHairEdgeToRgba reads ` +
      "source and base at the layer's own pixel positions.",
    );
  }
  return { dx: Math.round(o.dx * edge), dy: Math.round(o.dy * edge) };
}

// ---------------------------------------------------------------- table helpers

export function findTone(table: ToneTable, id: string): Tone {
  const tone = table.tones.find((entry) => entry.id === id);
  if (!tone) throw new Error(`unknown tone "${id}"; have ${table.tones.map((t) => t.id).join(", ")}`);
  return tone;
}

/**
 * One LUT per tone, built lazily and kept. Ten tones is 7.5 KB of tables, so
 * there is no reason to rebuild one per frame.
 */
export function createToneCache(table: ToneTable): (id: string) => ToneLut {
  const cache = new Map<string, ToneLut>();
  return (id: string): ToneLut => {
    let lut = cache.get(id);
    if (!lut) {
      lut = buildToneLut(findTone(table, id).k);
      cache.set(id, lut);
    }
    return lut;
  };
}

// ---------------------------------------------------------------- browser helper

/**
 * Draws `layer` onto `ctx` retoned. The layer is rasterised to an offscreen
 * canvas, its bytes are mapped, and the result is composited — so the caller's
 * existing canvas state (transform, globalAlpha) still applies.
 *
 * Browser-only: needs a 2D context. The pure functions above work anywhere.
 */
export function drawTonedLayer(
  ctx: CanvasRenderingContext2D,
  layer: CanvasImageSource & { width: number; height: number },
  lut: ToneLut,
  dx = 0,
  dy = 0,
): void {
  const { width, height } = layer;
  const scratch = document.createElement("canvas");
  scratch.width = width;
  scratch.height = height;
  const scratchCtx = scratch.getContext("2d", { willReadFrequently: true });
  if (!scratchCtx) throw new Error("could not get a 2D context");
  scratchCtx.drawImage(layer, 0, 0);
  const image = scratchCtx.getImageData(0, 0, width, height);
  applyToneToRgba(image.data, lut);
  scratchCtx.putImageData(image, 0, 0);
  ctx.drawImage(scratch, dx, dy);
}

/** Rasterises an image source to RGBA bytes on its own canvas. */
function rasterise(img: CanvasImageSource & { width: number; height: number }): ImageData {
  const scratch = document.createElement("canvas");
  scratch.width = img.width;
  scratch.height = img.height;
  const c = scratch.getContext("2d", { willReadFrequently: true });
  if (!c) throw new Error("could not get a 2D context");
  c.drawImage(img, 0, 0);
  return c.getImageData(0, 0, img.width, img.height);
}

/**
 * Draws a HAIR-family `layer` onto `ctx` with the edge fix applied.
 *
 * `source` is `build/source.webp` and `base` is the tone's base, both on the
 * same canvas as the layer. `curve` is the layer's compiled `w(r)` from
 * `wr.json` (see `wrCurveFor`), or `null` for `w = r`. No `k` is involved —
 * hair keeps its native colour.
 *
 * Browser-only. `applyHairEdgeToRgba` above works anywhere.
 */
export function drawHairLayer(
  ctx: CanvasRenderingContext2D,
  layer: CanvasImageSource & { width: number; height: number },
  source: CanvasImageSource & { width: number; height: number },
  base: CanvasImageSource & { width: number; height: number },
  curve: WrCurve | null = null,
  dx = 0,
  dy = 0,
): void {
  const { width, height } = layer;
  const image = rasterise(layer);
  applyHairEdgeToRgba(image.data, rasterise(source).data, rasterise(base).data, curve);
  const scratch = document.createElement("canvas");
  scratch.width = width;
  scratch.height = height;
  const scratchCtx = scratch.getContext("2d");
  if (!scratchCtx) throw new Error("could not get a 2D context");
  scratchCtx.putImageData(image, 0, 0);
  ctx.drawImage(scratch, dx, dy);
}
