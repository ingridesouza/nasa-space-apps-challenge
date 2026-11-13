// H2G2 · Feature 03 · Panorama no ponto
// O mapa é só de exibição: o ponto vem das duas caixas (lat/lon).
(async function () {
  const $ = (id) => document.getElementById(id);
  const info = await (await fetch("/map")).json();
  const win = info.window;

  // ---------------- Mapa (Leaflet, lat/lon em graus) ----------------
  const map = L.map("map", { crs: L.CRS.EPSG4326, minZoom: 8, maxZoom: 22, zoomSnap: 0.25,
                             attributionControl: false });
  const winBounds = [[win.lat_min, win.lon_min], [win.lat_max, win.lon_max]];
  if (info.orbital) {
    const o = info.orbital;
    L.imageOverlay("/bundle/" + o.image, [[o.lat_min, o.lon_min], [o.lat_max, o.lon_max]]).addTo(map);
  }
  map.fitBounds(winBounds);
  L.rectangle(winBounds, { color: "#e0703a", weight: 1, fill: false, dashArray: "4 4" }).addTo(map);

  const stops = info.stops || [];
  if (stops.length) {
    L.polyline(stops.map((s) => [s.lat, s.lon]), { color: "#fff", weight: 1.5, opacity: 0.7 }).addTo(map);
  }
  const panoIcon = L.divIcon({ className: "marker-pano", html: "360", iconSize: [18, 18] });
  for (const s of stops) {
    const tip = `Parada ${s.rmc} · sol ${s.sol}${s.pano ? " · panorama" : ""}`;
    if (s.pano) L.marker([s.lat, s.lon], { icon: panoIcon, interactive: true }).bindTooltip(tip).addTo(map);
    else L.circleMarker([s.lat, s.lon], { radius: 3, color: "#9b8a7d", weight: 1 }).bindTooltip(tip).addTo(map);
  }
  let alvo = null, raio = null, linha = null;

  // ---------------- Pontos de exemplo ----------------
  for (const ex of info.examples || []) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = ex.nome;
    b.onclick = () => { $("lat").value = ex.lat; $("lon").value = ex.lon; buscar(); };
    $("exemplos").appendChild(b);
  }

  // ---------------- Busca ----------------
  let viewer = null;
  $("form").addEventListener("submit", (e) => { e.preventDefault(); buscar(); });

  async function buscar() {
    const lat = parseFloat($("lat").value);
    let lon = parseFloat($("lon").value);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90) {
      return aviso("Latitude entre −90 e 90 e longitude numérica, por favor.");
    }
    if (lon < 0) { lon += 360; $("lon").value = lon.toFixed(6); }
    const dentro = lat >= win.lat_min && lat <= win.lat_max && lon >= win.lon_min && lon <= win.lon_max;
    if (!dentro) {
      return aviso(`Ponto fora da área do mapa. Use lat ${win.lat_min} a ${win.lat_max} e lon ${win.lon_min} a ${win.lon_max}.`);
    }
    aviso(null);
    $("estado").textContent = "Buscando…";

    if (alvo) map.removeLayer(alvo);
    alvo = L.marker([lat, lon]).addTo(map).bindTooltip("ponto informado");
    map.setView([lat, lon], Math.max(map.getZoom(), 17));

    const q = `lat=${lat}&lon=${lon}`;
    const [pano, fotos] = await Promise.all([
      fetch(`/panoramas/nearest?${q}`).then((r) => r.json()),
      fetch(`/photos/near?${q}`).then((r) => r.json()),
    ]);
    mostrarPano(pano, lat, lon);
    mostrarFotos(fotos);
    const img = $("orbital");
    img.hidden = false;
    img.src = `/orbital/crop?${q}&t=${Date.now()}`;
    $("estado").textContent = "";
  }

  function aviso(msg) {
    $("aviso").hidden = !msg;
    $("aviso").textContent = msg || "";
  }

  function mostrarPano(p, lat, lon) {
    if (raio) map.removeLayer(raio);
    if (linha) map.removeLayer(linha);
    if (viewer) { viewer.destroy(); viewer = null; }
    if (!p.found) {
      $("pano-wrap").hidden = true;
      $("sem-pano").hidden = false;
      $("sem-pano").textContent = p.mensagem + ". Veja as fotos próximas e a vista orbital abaixo.";
      return;
    }
    $("sem-pano").hidden = true;
    $("pano-wrap").hidden = false;
    $("pano-rotulo").textContent = p.rotulo;
    $("pano-credito").innerHTML = `${p.credito} · abre virado para o ponto informado (rumo ${p.rumo_parada_para_ponto}°)` +
      (p.page_url ? ` · <a href="${p.page_url}" target="_blank" rel="noopener">página da NASA</a>` : "");
    linha = L.polyline([[p.lat, p.lon], [lat, lon]], { color: "#ffd23f", weight: 2, dashArray: "3 5" }).addTo(map);
    viewer = pannellum.viewer("pano", Object.assign({}, p.pannellum, {
      showControls: true,
      hotSpots: [{ pitch: 0, yaw: p.pannellum.yaw, type: "info", text: "direção do ponto informado" }],
    }));
  }

  function mostrarFotos(f) {
    const box = $("fotos");
    box.innerHTML = "";
    $("fotos-n").textContent = f.total ? `${f.total} a até 200 m, por distância` : "";
    if (!f.total) {
      box.innerHTML = '<div class="vazio">Nenhuma foto Navcam a menos de 200 m.</div>';
      return;
    }
    for (const ft of f.fotos) {
      const el = document.createElement("div");
      el.className = "foto";
      el.innerHTML = `<img loading="lazy" src="${ft.thumb}" alt=""><p>${ft.rotulo}<br>${ft.credito}</p>`;
      el.onclick = () => {
        $("foto-grande-img").src = ft.img;
        $("foto-grande-rotulo").textContent = `${ft.rotulo} · ${ft.id} · ${ft.credito}`;
        $("foto-grande").showModal();
      };
      box.appendChild(el);
    }
  }
  $("fechar").onclick = () => $("foto-grande").close();
})();
