// H2G2 · F04 · Science card for the point
// Builds the card from GET /science/card. Every line shows instrument, confidence
// badge and source; empty fields do not appear (never "null").
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const ICON = { drill_hole: "◉", ridge: "⋀", hollow: "◡", contact: "┃", feature: "◇" };
  const BADGE = { measured: "tag-red", "inferred from orbit": "tag-amber", context: "", mock: "tag-amber" };
  const SECTION = {
    chemistry: "Measured on the ground · chemistry", mineralogy: "Measured on the ground · mineralogy",
    no_measurement: "Measured on the ground", orbit: "Seen from orbit", terrain: "Terrain", name: "Name and context",
    what_was_done: "What was done", why_it_matters: "Why it matters",
    safety: "Safety", terrain_safety: "Terrain safety",
  };

  function source(l) {
    return esc(l.source_file || "source"); // file name only: an external link does not work offline
  }

  function line(l) {
    const meta = [l.instrument, l.sol != null ? `sol ${l.sol}` : null, l.scale].filter(Boolean).map(esc).join(" · ");
    return `<li class="sci-line">
      <div class="sci-top"><span class="sci-sec">${esc(SECTION[l.section] || l.section)}</span>
        <span class="tag ${BADGE[l.confidence] ?? ""}">${esc(l.confidence_label)}</span></div>
      <p class="sci-txt">${esc(l.text)}</p>
      <p class="caption mono">${meta ? meta + " · " : ""}${source(l)}</p></li>`;
  }

  // state: "loading" | "error" | API data
  window.H2G2Card = {
    title(d) {
      if (d === "loading") return ["Science card", "loading…"];
      if (d === "error" || !d) return ["Science card", "error"];
      if (!d.target) return ["Science card", "no target nearby"];
      return [`${ICON[d.target.kind] || "◇"} ${d.target.name}`, d.target.kind_label];
    },
    html(d) {
      if (d === "loading") return '<p class="empty">Fetching the science card…</p>';
      if (d === "error" || !d) return '<p class="empty error">Failed to fetch the science card.</p>';
      let h = "";
      const a = d.target;
      if (a) {
        const tags = [`sol ${a.sol}`, a.rmc, a.distance_label].filter(Boolean)
          .map((t) => `<span class="tag">${esc(t)}</span>`).join("");
        const img = d.mastcam
          ? `<img class="science-img" src="${esc(d.mastcam.img)}" alt="${esc(d.mastcam.label)}" onerror="this.style.visibility='hidden'">`
          : '<div class="science-img"></div>';
        h += `<div class="science-head">${img}<div><p class="caption mono">${esc(a.name_label)}</p>
          <div class="tags">${tags}</div></div></div>`;
        if (d.position_warning) h += `<p class="caption mono warning">⚠ ${esc(d.position_warning)}</p>`;
      }
      if (d.message) h += `<p class="empty">${esc(d.message)}.</p>`;
      const lines = (d.rows || []).concat(d.context || []);
      if (lines.length) h += `<ul class="sci-lines">${lines.map(line).join("")}</ul>`;
      if (d.mastcam) h += `<p class="caption mono">${esc(d.mastcam.label)} · ${esc(d.mastcam.credit)}</p>`;
      h += '<p class="caption mono">Confidence: <b>measured</b> (Curiosity at the stop) · <b>inferred from orbit</b> (CRISM, ~18 m/px) · <b>context</b> (blog, nomenclature, H2G2 team)</p>';
      return h;
    },
  };
})();
