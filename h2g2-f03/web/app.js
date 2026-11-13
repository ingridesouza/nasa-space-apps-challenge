// H2G2 · Visor do astronauta
// Visor (esquerda) + caixa de coordenadas; painel direito com status, panorama, fotos e ficha.
(async function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let win = null;
  try { win = (await (await fetch("/map")).json()).window || null; } catch { /* segue sem janela */ }

  // ---------------- Coordenadas ----------------
  $("coords").addEventListener("submit", (e) => { e.preventDefault(); enviar(); });

  function msg(texto, ok = false) {
    $("coords-msg").hidden = !texto;
    $("coords-msg").textContent = texto || "";
    $("coords-msg").classList.toggle("ok", ok);
  }

  function lerCoords() {
    const lat = parseFloat($("lat").value);
    let lon = parseFloat($("lon").value);
    const latOk = Number.isFinite(lat) && lat >= -90 && lat <= 90;
    const lonOk = Number.isFinite(lon);
    $("lat").setAttribute("aria-invalid", !latOk);
    $("lon").setAttribute("aria-invalid", !lonOk);
    if (!latOk || !lonOk) return null;
    if (lon < 0) { lon += 360; $("lon").value = lon.toFixed(6); }
    return { lat, lon };
  }

  async function enviar() {
    const c = lerCoords();
    if (!c) return msg("Latitude entre −90 e 90; longitude numérica (°E).");
    const { lat, lon } = c;
    const dentro = !win || (lat >= win.lat_min && lat <= win.lat_max && lon >= win.lon_min && lon <= win.lon_max);
    msg(dentro ? null : "Fora da janela do boxwork — resultados podem ser vazios.");
    $("hud-pos").textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E`;

    carregando();
    const q = `lat=${lat}&lon=${lon}`;
    const [pano, fotos] = await Promise.allSettled([
      fetch(`/panoramas/nearest?${q}`).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
      fetch(`/photos/near?${q}`).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
    ]);
    if (pano.status === "fulfilled") { mostrarStatus(pano.value); mostrarPano(pano.value); mostrarFicha(FICHA_EXEMPLO); }
    else { erro("c-status", "Falha ao consultar a API."); limparPano(); }
    if (fotos.status === "fulfilled") mostrarFotos(fotos.value);
    else $("c-fotos").hidden = true;
  }

  function carregando() {
    for (const id of ["c-pano", "c-fotos", "c-ficha"]) $(id).hidden = true;
    const primeira = $("flutuante").hidden;
    if (primeira) colapsarBarra(true);          // nasce transparente e faz fade-in
    card("c-status", '<p class="vazio">Processando posição…</p>');
    posicionarToggle();
    if (primeira) requestAnimationFrame(() => requestAnimationFrame(() => colapsarBarra(false)));
  }

  function card(id, html) { $(id).innerHTML = html; $(id).hidden = false; $("flutuante").hidden = false; }
  function erro(id, texto) { card(id, `<p class="vazio erro">${esc(texto)}</p>`); }

  // ---------------- Status ----------------
  function mostrarStatus(p) {
    if (!p.found) return card("c-status", `<p class="vazio">${esc(p.mensagem)}.</p>`);
    const linhas = [
      ["Sol", p.sol], ["Site · drive", p.rmc.replace("_", " · ")], ["Data", p.date || "—"],
      ["Distância da parada", `${p.distancia_m} m`], ["Rumo ponto → parada", `${p.rumo_ponto_para_parada}°`],
    ];
    card("c-status", linhas.map(([k, v]) => `<div class="kv"><span>${k}</span><span>${esc(v)}</span></div>`).join(""));
  }

  // ---------------- Panorama ----------------
  let viewer = null;      // preview (sempre no painel)
  let viewerFundo = null; // cópia no visor
  let cfgPano = null;
  let noVisor = false;

  // preview mais aproximado; no fundo, volta a 90° e sobe/desce um pouco rumo ao centro da imagem
  const HFOV_PREVIEW = 65, HFOV_FUNDO = 90, CENTRO_FUNDO = 0.5, CENTRO_PREVIEW = 0.3;
  let voff = 0;

  let panoSeq = 0;
  function limparPano() {
    panoSeq++;
    if (noVisor) recolher();
    if (viewer) { viewer.destroy(); viewer = null; }
    $("pano").innerHTML = "";
    $("c-pano").hidden = true;
  }

  function mostrarPano(p) {
    limparPano();
    if (!p.found) return;
    $("c-pano").hidden = false;
    $("pano-rotulo").innerHTML = `${esc(p.rotulo)} · ${esc(p.credito)}` +
      (p.page_url ? ` · <a href="${esc(p.page_url)}" target="_blank" rel="noopener">NASA</a>` : "");
    voff = p.pannellum.vOffset || 0;
    cfgPano = Object.assign({}, p.pannellum, {
      showControls: false, compass: false,
      hotSpots: [{ pitch: 0, yaw: p.pannellum.yaw, type: "info", text: "direção do ponto informado" }],
    });
    // cria o viewer só depois do card pintar: init do pannellum é pesado e travava a animação
    const seq = panoSeq;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (seq !== panoSeq) return;
      viewer = pannellum.viewer("pano", Object.assign({}, cfgPano, { hfov: HFOV_PREVIEW, pitch: voff * CENTRO_PREVIEW }));
    }));
  }

  // barra da direita: colapsa/expande
  function colapsarBarra(c) {
    $("flutuante").classList.toggle("colapsada", c);
    $("flutuante-toggle").textContent = c ? "‹" : "›";
    $("flutuante-toggle").title = c ? "Expandir barra" : "Recolher barra";
    $("flutuante-toggle").setAttribute("aria-expanded", String(!c));
    $("fichas").classList.toggle("colapsada", c);
    posicionarToggle();
  }
  // botão fica à esquerda do card de status (largura variável); recolhido, vai para a borda
  function posicionarToggle() {
    const t = $("flutuante-toggle"), s = $("c-status");
    const colap = $("flutuante").classList.contains("colapsada");
    const mobile = matchMedia("(max-width:900px)").matches;
    // sem card de status visível (ou recolhida): colado à borda direita da tela
    t.style.right = mobile ? "" : (colap || s.hidden) ? "20px" : (20 + s.offsetWidth + 8) + "px";
  }
  // fichas ancoradas na base do bloco de fotos (ou topo da barra no mobile), crescem para cima
  function posicionarFichas() {
    const f = $("fichas"), fl = $("flutuante");
    if (fl.hidden) return;
    const mobile = matchMedia("(max-width:900px)").matches;
    const ref = mobile || $("c-fotos").hidden ? fl.getBoundingClientRect() : $("c-fotos").getBoundingClientRect();
    f.style.bottom = (mobile ? innerHeight - ref.top + 8 : Math.max(20, innerHeight - ref.bottom)) + "px";
  }
  {
    const ro = new ResizeObserver(() => { posicionarFichas(); posicionarToggle(); });
    for (const id of ["flutuante", "c-status", "c-pano", "c-fotos"]) ro.observe($(id));
    addEventListener("resize", () => { posicionarFichas(); posicionarToggle(); });
    $("flutuante").addEventListener("scroll", posicionarFichas);
  }
  $("flutuante-toggle").addEventListener("click", () => colapsarBarra(!$("flutuante").classList.contains("colapsada")));

  // visor ganha um 2º viewer (mesma imagem, yaw atual); o preview continua no painel
  function expandir() {
    if (!viewer) return;
    colapsarBarra(true);
    fecharFoto();
    const d = document.createElement("div");
    d.id = "pano-fundo";
    $("visor-stage").appendChild(d);
    viewerFundo = pannellum.viewer("pano-fundo", Object.assign({}, cfgPano, {
      hfov: HFOV_FUNDO, pitch: voff * CENTRO_FUNDO, yaw: viewer.getYaw(),
    }));
    $("visor-vazio").hidden = true;
    $("visor-fechar").hidden = false;
    noVisor = true;
    // tira o foco do botão (agora na barra recolhida) e entrega ao panorama
    if (document.activeElement) document.activeElement.blur();
    d.tabIndex = 0;
    d.focus({ preventScroll: true });
  }
  function recolher() {
    if (viewerFundo) { viewerFundo.destroy(); viewerFundo = null; }
    const d = $("pano-fundo"); if (d) d.remove();
    $("visor-vazio").hidden = !!viewer;
    $("visor-fechar").hidden = true;
    noVisor = false;
    colapsarBarra(false);
  }
  $("pano-expandir").addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); noVisor ? recolher() : expandir(); });

  // ---------------- Fotos ----------------
  function mostrarFotos(f) {
    $("c-fotos").hidden = !f.total;
    if (!f.total) return;
    $("fotos").innerHTML = "";
    for (const ft of f.fotos) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "foto"; b.title = ft.rotulo;
      b.innerHTML = `<img loading="lazy" src="${esc(ft.thumb)}" alt=""><p>${ft.distancia_m} m · ${esc(ft.instrument)}</p>`;
      b.onclick = () => abrirFoto(ft);
      $("fotos").appendChild(b);
    }
  }

  function abrirFoto(ft) {
    if (noVisor) recolher();
    $("visor-img").src = ft.img;
    $("visor-img").alt = ft.rotulo;
    $("visor-img").hidden = false;
    $("visor-vazio").hidden = true;
    $("visor-fechar").hidden = false;
  }
  function fecharFoto() {
    $("visor-img").hidden = true;
    $("visor-img").removeAttribute("src");
    $("visor-vazio").hidden = noVisor;
    $("visor-fechar").hidden = !noVisor;
  }

  function fecharVisor() { if (noVisor) recolher(); fecharFoto(); }
  $("visor-fechar").addEventListener("click", fecharVisor);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharVisor(); });

  // ---------------- Ficha científica (só layout, dado de exemplo) ----------------
  const FICHA_EXEMPLO = {
    alvo: "Mojo", tipo: "hollow (depressão)", sol: 4643, faixa: "4641–4644", rmc: "118_2028",
    instrumentos: ["Mastcam"],
    feito: "Rover estacionado dentro do hollow Mojo; mosaicos das cristas, de um sulco e do piso do hollow para ver movimento de regolito.",
    blog: "https://science.nasa.gov/blog/curiosity-blog-sols-4641-4648-thinking-outside-and-inside-the-boxwork/",
    mastcam: "https://mars.nasa.gov/msl-raw-images/msss/04643/mcam/4643ML1082140001804938C00_DXXX.jpg",
  };

  function mostrarFicha(a) {
    $("c-ficha").open = false;
    $("c-ficha").hidden = !a;
    if (!a) return;
    $("ficha-nome").textContent = a.alvo;
    $("ficha-tipo").textContent = a.tipo;
    $("flutuante").hidden = false;
    requestAnimationFrame(posicionarFichas);
    $("ficha").innerHTML = `
      <div class="ficha">
        <img class="ficha-img" src="${esc(a.mastcam)}" alt="Mastcam do alvo ${esc(a.alvo)}" onerror="this.style.visibility='hidden'">
        <div class="tags"><span class="tag">sol ${a.sol}</span><span class="tag">${esc(a.rmc)}</span>
          ${a.instrumentos.map((i) => `<span class="tag">${esc(i)}</span>`).join("")}</div>
      </div>
      <p class="ficha-txt">${esc(a.feito)}</p>
      <p class="rotulo mono"><a href="${esc(a.blog)}" target="_blank" rel="noopener">post do blog Curiosity</a> · Mastcam NASA/JPL-Caltech/MSSS</p>`;
  }
})();
