/**
 * Map layer config -- mirrors (without being generated from)
 * `data-pipeline/config/layers.yaml`. The real bbox of each layer comes from
 * `GET /layers`; this only decides order/grouping/label/initial state.
 * Order = draw order: the last one is on top.
 */
export const TOGGLEABLE_LAYERS = [
  { id: 'ctx_optical', label: 'CTX (context, ~10 m)', group: 'base', defaultVisible: true, defaultOpacity: 1 },
  { id: 'hirise_optical', label: 'HiRISE (detail, ~0.6 m)', group: 'base', defaultVisible: true, defaultOpacity: 1 },
  { id: 'relief_hillshade', label: 'Relief (DTM hillshade)', group: 'overlay', defaultVisible: false, defaultOpacity: 0.9 },
  { id: 'themis_ti', label: 'Thermal inertia (THEMIS, 100 m)', group: 'overlay', defaultVisible: false, defaultOpacity: 0.6 },
  { id: 'predicted_risk', label: 'Slope risk (predicted)', group: 'overlay', defaultVisible: false, defaultOpacity: 0.6 },
  // points (GeoJSON from /api/atmosphere/track), not tiles: map.js draws it separately
  // inferred from relief per sol/hour (api/insolation.py); hour comes from the panel control
  { id: 'insolation', label: 'Direct sun and shade (inferred)', group: 'overlay', defaultVisible: false, defaultOpacity: 0.75 },
  { id: 'atmosphere_track', label: 'Atmosphere (REMS along the traverse)', group: 'overlay', kind: 'points', defaultVisible: false, defaultOpacity: 1 },
]

/** Color scale of the continuous layers (thermal and atmosphere): blue -> yellow -> red */
export const CONTINUOUS_SCALE = ['rgb(40,30,90)', 'rgb(60,110,190)', 'rgb(240,200,70)', 'rgb(220,70,40)']

/** Layers with no visual pyramid yet, or deliberately out of scope --
 * showing this is more honest than hiding it (feature 01 spec). */
export const PLANNED_LAYERS = [
  { id: 'mineralogy', label: 'Mineralogy (CRISM)', reason: 'sparse coverage in Gale, see NEXT-STEPS.md', status: 'coming_soon' },
  {
    id: 'geophysics',
    label: 'Geophysics',
    reason: 'no useful orbital data at the meter scale of the boxwork -- a scope decision, not a pending item',
    status: 'out_of_scope',
  },
]

/** "Real" max zoom of each layer, from the pixel resolution (Mars
 * radius) -- beyond that it is just overzoom (blurry). See api/tile_server.py. */
export const LAYER_MAXZOOM = {
  hirise_optical: 17, // ~0.64 m/px in the local tiles (Mars Trek z16); the product has 25 cm, not downloaded
  relief_hillshade: 14, // ~5.88 m/px real DTM
  ctx_optical: 13, // ~10.2 m/px in the local tiles (Mars Trek z12); the product has ~6 m, not downloaded
  themis_ti: 10, // 100 m/px (real cell; nearest overzoom)
  insolation: 16, // 2 m grid (from the native 1 m DTM)
  predicted_risk: 17, // same DTM; color by band (nearest), no blur
}

/** 20° limit (Artemis) -- see api/raster_sampling.py. */
export const SLOPE_VERDICT = {
  safe: { color: 'var(--verdict-safe)', label: 'Safe to walk' },
  caution: { color: 'var(--verdict-caution)', label: 'Caution: steep slope' },
  danger: { color: 'var(--verdict-danger)', label: 'Danger: above the Artemis limit (20°)' },
}

/** Same colors in hex -- MapLibre paints via WebGL and does not resolve var()
 * (must match --verdict-* in style.css). */
export const SLOPE_COLOR_HEX = { safe: '#7fe0a8', caution: '#f2b33d', danger: '#e8643f' }

/** Thermal inertia legend -- same stops/range as api/thermal.py
 * (COLOR_STOPS, TI_MIN/TI_MAX). High = rock/firm ground, low = loose material. */
export const TI_LEGEND = {
  min: 200,
  max: 550,
  gradient: 'linear-gradient(90deg, rgb(40,30,90) 0%, rgb(60,110,190) 35%, rgb(240,200,70) 65%, rgb(220,70,40) 100%)',
}
