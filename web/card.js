// H2G2 · F04 · Ficha científica do ponto
// Monta o card a partir de GET /science/card. Toda linha mostra instrumento, selo de
// confiança e fonte; campo vazio não aparece (nunca "null").
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const ICONE = { furo: "◉", crista: "⋀", hollow: "◡", contato: "┃", "feição": "◇" };
  const SELO = { medido: "tag-red", "inferido de órbita": "tag-amber", contexto: "", mock: "tag-amber" };
  const SECAO = {
    quimica: "Medido no chão · química", mineralogia: "Medido no chão · mineralogia",
    sem_medicao: "Medido no chão", orbita: "Visto de órbita", terreno: "Terreno", nome: "Nome e contexto",
    o_que_foi_feito: "O que foi feito", por_que_importa: "Por que importa",
    seguranca: "Segurança", seguranca_terreno: "Segurança do terreno",
  };

  function fonte(l) {
    return esc(l.fonte_arquivo || "fonte"); // só o nome do arquivo: link externo não funciona offline
  }

  function linha(l) {
    const meta = [l.instrumento, l.sol != null ? `sol ${l.sol}` : null, l.escala].filter(Boolean).map(esc).join(" · ");
    return `<li class="fl">
      <div class="fl-top"><span class="fl-sec">${esc(SECAO[l.secao] || l.secao)}</span>
        <span class="tag ${SELO[l.confianca] ?? ""}">${esc(l.confianca_rotulo)}</span></div>
      <p class="fl-txt">${esc(l.texto)}</p>
      <p class="rotulo mono">${meta ? meta + " · " : ""}${fonte(l)}</p></li>`;
  }

  // estado: "carregando" | "erro" | dados da API
  window.H2G2Card = {
    titulo(d) {
      if (d === "carregando") return ["Ficha científica", "carregando…"];
      if (d === "erro" || !d) return ["Ficha científica", "erro"];
      if (!d.alvo) return ["Ficha científica", "sem alvo perto"];
      return [`${ICONE[d.alvo.tipo] || "◇"} ${d.alvo.nome}`, d.alvo.tipo_rotulo];
    },
    html(d) {
      if (d === "carregando") return '<p class="vazio">Consultando a ficha…</p>';
      if (d === "erro" || !d) return '<p class="vazio erro">Falha ao consultar a ficha científica.</p>';
      let h = "";
      const a = d.alvo;
      if (a) {
        const tags = [`sol ${a.sol}`, a.rmc, a.distancia_rotulo].filter(Boolean)
          .map((t) => `<span class="tag">${esc(t)}</span>`).join("");
        const img = d.mastcam
          ? `<img class="ficha-img" src="${esc(d.mastcam.img)}" alt="${esc(d.mastcam.rotulo)}" onerror="this.style.visibility='hidden'">`
          : '<div class="ficha-img"></div>';
        h += `<div class="ficha">${img}<div><p class="rotulo mono">${esc(a.rotulo_nome)}</p>
          <div class="tags">${tags}</div></div></div>`;
        if (d.aviso_posicao) h += `<p class="rotulo mono aviso">⚠ ${esc(d.aviso_posicao)}</p>`;
      }
      if (d.mensagem) h += `<p class="vazio">${esc(d.mensagem)}.</p>`;
      const linhas = (d.linhas || []).concat(d.contexto || []);
      if (linhas.length) h += `<ul class="fls">${linhas.map(linha).join("")}</ul>`;
      if (d.mastcam) h += `<p class="rotulo mono">${esc(d.mastcam.rotulo)} · ${esc(d.mastcam.credito)}</p>`;
      h += '<p class="rotulo mono">Confiança: <b>medido</b> (Curiosity na parada) · <b>inferido de órbita</b> (CRISM, ~18 m/px) · <b>contexto</b> (blog, nomenclatura, equipe H2G2)</p>';
      return h;
    },
  };
})();
