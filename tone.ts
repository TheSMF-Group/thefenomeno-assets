/**
 * Tone transfer for the mannequin feature layers. See NOTES.md.
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
 * The factors live in `tones.json`, one entry per Monk Skin Tone base.
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
