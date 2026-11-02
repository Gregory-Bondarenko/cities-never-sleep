// Береговая линия для витрины: слой «суша» Natural Earth 1:50m (общественное достояние)
// из пакета world-atlas, только побережья, без политических границ.
//
//   npm i --no-save world-atlas@2 topojson-client@3
//   node scripts/coastline.mjs
//
// Результат: analytics/exports/coastline.json (массив линий [[lon, lat], ...]) и метаданные.
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const topo = require("world-atlas/land-50m.json");
const { feature } = require("topojson-client");

const BOX = { latMin: 40, latMax: 82.5 };
const inBox = (lon, lat) =>
  lat >= BOX.latMin && lat <= BOX.latMax && ((lon >= 18 && lon <= 180) || (lon >= -180 && lon <= -165));
const STEP = 0.12; // прореживание: точка не ближе 0,12° к предыдущей

const lines = [];
for (const f of feature(topo, topo.objects.land).features) {
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  for (const poly of polys)
    for (const ring of poly) {
      let seg = [];
      for (const [lon, lat] of ring) {
        if (inBox(lon, lat)) seg.push([+lon.toFixed(2), +lat.toFixed(2)]);
        else { if (seg.length > 3) lines.push(seg); seg = []; }
      }
      if (seg.length > 3) lines.push(seg);
    }
}
const thin = lines
  .map((r) => r.reduce((o, p) => { const q = o[o.length - 1]; if (!q || Math.hypot(p[0] - q[0], p[1] - q[1]) > STEP) o.push(p); return o; }, []))
  .filter((r) => r.length > 4);

writeFileSync("analytics/exports/coastline.json", JSON.stringify(thin));
writeFileSync("analytics/exports/coastline.meta.json", JSON.stringify({
  schema_version: "1.0.0",
  source: "Natural Earth 1:50m land (world-atlas@2)",
  built_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
  package_version: "scripts/coastline.mjs",
  n_rows: thin.length,
  license_note: "Natural Earth: общественное достояние",
  n_points: thin.reduce((a, r) => a + r.length, 0),
  bbox: { lat: [BOX.latMin, BOX.latMax], lon: "18…180, −180…−165" },
  simplify_deg: STEP,
}, null, 2) + "\n");
console.log(`${thin.length} линий`);
