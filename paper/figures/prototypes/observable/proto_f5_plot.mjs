// Architecture spike: F5 in Observable Plot (headless via jsdom), PNG via resvg.
import fs from "node:fs";
import {JSDOM} from "jsdom";
import * as Plot from "@observablehq/plot";
import {Resvg} from "@resvg/resvg-js";

const {document} = new JSDOM("").window;
const parse = (p) => {
  const lines = fs.readFileSync(p, "utf8").split("\n").filter((l) => l && !l.startsWith("#"));
  const head = lines[0].split(",");
  return lines.slice(1).map((l) => Object.fromEntries(l.split(",").map((v, i) => [head[i], isNaN(+v) ? v : +v])));
};
const d = parse("../../data/F5_variance_reduction.csv");
const ins = parse("../../data/F5_inset_aof_p1.csv");
const rows = [...new Set(d.sort((a, b) => a.order - b.order).map((r) => r.row))];
const off = {p1: -0.22, p2: 0, p3: 0.22};
d.forEach((r) => { r.y = rows.indexOf(r.row) + off[r.role]; r.c = r.row.startsWith("AoF") ? "#2a78d6" : "#1baf7a"; });
const med = rows.map((row, i) => ({y: i, x: d.filter((r) => r.row === row).map((r) => r.var_ratio).sort()[1], row}));
const W = 7.2 * 96, H = 2.3 * 96; // CSS px at 96 dpi = final physical size
const a = Plot.plot({
  document, width: W * 0.72, height: H, marginLeft: 118, marginBottom: 32, style: {fontFamily: "Arial", fontSize: "8.7px"},
  x: {domain: [0, 1.13], label: "variance ratio  Var(estimator D) / Var(raw D)", labelAnchor: "center", labelArrow: "none"},
  y: {type: "linear", domain: [-0.5, rows.length - 0.5], ticks: rows.map((_, i) => i), tickFormat: (i) => rows[i], label: null, reverse: true},
  marks: [
    Plot.ruleX([1], {stroke: "#0b0b0b", strokeWidth: 0.8}),
    Plot.ruleX([0.5], {stroke: "#9a9994", strokeDasharray: "2,2"}),
    Plot.link(d, {x1: "ci_lo", x2: "ci_hi", y1: "y", y2: "y", stroke: "c", strokeWidth: 1.1}),
    Plot.dot(d, {x: "var_ratio", y: "y", fill: "c", stroke: "white", strokeWidth: 0.6, r: 3,
      symbol: (r) => ({p1: "circle", p2: "square", p3: "triangle"}[r.role])}),
    Plot.link(med, {x1: "x", x2: "x", y1: (r) => r.y - 0.36, y2: (r) => r.y + 0.36, stroke: "#0b0b0b", strokeWidth: 1.5}),
    Plot.text(med, {x: 1.08, y: "y", text: (r) => r.x.toFixed(2), fill: "#52514e"}),
    Plot.axisX({tickSize: 3}), Plot.axisY({tickSize: 0}),
  ],
});
const b = Plot.plot({
  document, width: W * 0.28, height: H, marginLeft: 52, marginBottom: 32, style: {fontFamily: "Arial", fontSize: "8.7px"},
  x: {label: "AoF p1 edge (BB/100)", labelAnchor: "center", labelArrow: "none", nice: true},
  y: {domain: ["raw", "allin_ev"], tickFormat: (e) => (e === "raw" ? "raw" : "all-in EV"), label: null},
  marks: [Plot.ruleX([0], {stroke: "#0b0b0b"}),
    Plot.link(ins, {x1: "ci_lo", x2: "ci_hi", y1: "estimator", y2: "estimator", stroke: "#2a78d6", strokeWidth: 1.3}),
    Plot.dot(ins, {x: "mean_bb100", y: "estimator", fill: "#2a78d6", stroke: "white", r: 3})],
});
// compose side by side into one SVG
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="white"/>` +
  `<g>${a.outerHTML}</g><g transform="translate(${W * 0.72},0)">${b.outerHTML}</g>` +
  `<text x="4" y="12" font-family="Arial" font-weight="bold" font-size="11">a</text><text x="${W * 0.72 + 4}" y="12" font-family="Arial" font-weight="bold" font-size="11">b</text></svg>`;
fs.writeFileSync("../proto_f5_observable.svg", svg);
const png = new Resvg(svg, {fitTo: {mode: "width", value: 4320}, font: {loadSystemFonts: true, defaultFontFamily: "Arial"}, background: "white"}).render().asPng();
fs.writeFileSync("../proto_f5_observable.png", png);
console.log("ok");
