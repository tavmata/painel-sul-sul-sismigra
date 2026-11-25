'use strict';
/* Painel web – Migração Sul-Sul no Brasil (SISMIGRA). Sem dependências externas.
   Dados: dados.json (gerado por gerar_web.py). Cada cubo é uma lista plana
   [ano, país, atributo..., contagem, ...]; os filtros agem sobre ano e país. */
(() => {
  // ------------------------------------------------------------------ utilidades
  const FONTE = '12px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  const FONTE_EIXO = '11px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  const fN = new Intl.NumberFormat('pt-BR');
  const fP = new Intl.NumberFormat('pt-BR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fC = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 });
  const N = v => fN.format(Math.round(v || 0));
  const PC = v => (v == null || !isFinite(v)) ? '–' : fP.format(v);
  const CP = v => (v >= 10000 ? fC.format(v) : fN.format(v));
  const SVGNS = 'http://www.w3.org/2000/svg';

  function h(tag, attrs, pai, texto) {
    const e = document.createElement(tag);
    for (const k in attrs || {}) { if (k === 'class') e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (texto != null) e.textContent = texto;
    if (pai) pai.append(e);
    return e;
  }
  function s(tag, attrs, pai, texto) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (texto != null) e.textContent = texto;
    if (pai) pai.append(e);
    return e;
  }
  const ctx2d = document.createElement('canvas').getContext('2d');
  function medir(t, fonte = FONTE) { ctx2d.font = fonte; return ctx2d.measureText(String(t)).width; }
  function truncar(t, larg, fonte = FONTE) {
    t = String(t);
    if (medir(t, fonte) <= larg) return t;
    while (t.length > 1 && medir(t + '…', fonte) > larg) t = t.slice(0, -1);
    return t + '…';
  }
  function marcas(max, n = 4) {
    if (!(max > 0)) return [0, 1];
    const bruto = max / n, mag = Math.pow(10, Math.floor(Math.log10(bruto)));
    const passo = [1, 2, 2.5, 5, 10].map(m => m * mag).find(p => p >= bruto);
    const out = [];
    for (let k = 0; k * passo < max + passo * 0.999; k++) out.push(k * passo);
    return out;
  }
  const intervalo = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);

  // ------------------------------------------------------------------ tooltip
  const tip = document.getElementById('tip');
  function tipMostrar(x, y, titulo, linhas) {
    tip.replaceChildren();
    if (titulo) h('div', { class: 'tip-t' }, tip, titulo);
    for (const l of linhas) {
      const r = h('div', { class: 'tip-r' }, tip);
      if (l.cor) h('span', { class: 'tip-k' }, r).style.background = `var(--${l.cor})`;
      h('strong', null, r, l.valor);
      if (l.nome) h('span', { class: 'tip-n' }, r, l.nome);
    }
    tip.hidden = false;
    const b = tip.getBoundingClientRect();
    let L = x + 14, T = y + 14;
    if (L + b.width > innerWidth - 8) L = x - b.width - 14;
    if (T + b.height > innerHeight - 8) T = y - b.height - 14;
    tip.style.left = Math.max(8, L) + 'px';
    tip.style.top = Math.max(8, T) + 'px';
  }
  const tipEsconder = () => { tip.hidden = true; };
  function interativo(g, conteudo) {
    g.setAttribute('tabindex', '0');
    g.setAttribute('class', ((g.getAttribute('class') || '') + ' alvo').trim());
    g.addEventListener('pointermove', ev => { const [t, l] = conteudo(); tipMostrar(ev.clientX, ev.clientY, t, l); });
    g.addEventListener('pointerleave', tipEsconder);
    g.addEventListener('focus', () => { const b = g.getBoundingClientRect(); const [t, l] = conteudo(); tipMostrar(b.left + b.width / 2, b.top, t, l); });
    g.addEventListener('blur', tipEsconder);
  }

  // ------------------------------------------------------------------ componentes
  function vazio(host, msg) { h('p', { class: 'vazio' }, host, msg || 'Sem registros para esta seleção.'); }
  function novoSvg(host, W, H, rotulo) {
    const svg = s('svg', { class: 'graf', viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img' }, host);
    if (rotulo) svg.setAttribute('aria-label', rotulo);
    return svg;
  }
  function legenda(host, itens, forma) {
    const d = h('div', { class: 'legenda' }, host);
    for (const it of itens) {
      const sp = h('span', null, d);
      h('i', { class: forma === 'lin' ? 'lin' : '' }, sp).style.background = `var(--${it.cor})`;
      sp.append(document.createTextNode(it.nome));
    }
  }
  function barraH(x, y, w, alt) {
    if (w <= 0.6) return `M${x},${y}h0.6v${alt}h-0.6Z`;
    const r = Math.min(4, w, alt / 2);
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + alt - r}Q${x + w},${y + alt} ${x + w - r},${y + alt}H${x}Z`;
  }
  function barraV(x, base, w, alt) {
    if (alt <= 0.6) return `M${x},${base}h${w}v-0.6h${-w}Z`;
    const r = Math.min(4, alt, w / 2), y = base - alt;
    return `M${x},${base}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${base}Z`;
  }
  const largura = host => Math.max(260, Math.floor(host.clientWidth || 360));

  /* Barras horizontais: itens [{rotulo, valor, cor?, detalhe?}] */
  function barras(host, itens, o = {}) {
    itens = itens.filter(d => d.valor > 0);
    if (!itens.length) return vazio(host);
    const fmt = o.fmt || N, W = largura(host);
    const max = Math.max(...itens.map(d => d.valor));
    const rotW = Math.min(Math.max(...itens.map(d => medir(d.rotulo))), W * (o.fracRotulo || 0.42)) + 16;
    const valW = medir(fmt(max)) + 12;
    const LH = o.linha || 24, BH = Math.min(16, LH - 6), H = itens.length * LH + 6;
    const svg = novoSvg(host, W, H, o.rotulo);
    const x0 = rotW, larg = Math.max(10, W - rotW - valW - 2);
    s('line', { x1: x0 + 0.5, x2: x0 + 0.5, y1: 0, y2: H, class: 'base' }, svg);
    itens.forEach((d, i) => {
      const y = 3 + i * LH, g = s('g', {}, svg), w = larg * d.valor / max, cor = d.cor || 's1';
      s('rect', { x: 0, y, width: W, height: LH, class: 'hit' }, g);
      s('text', { x: x0 - 8, y: y + LH / 2, class: 'rot', 'text-anchor': 'end', 'dominant-baseline': 'central' }, g,
        truncar(d.rotulo, rotW - 10));
      s('path', { d: barraH(x0 + 1, y + (LH - BH) / 2, w, BH), class: 'marca', style: `fill:var(--${cor})` }, g);
      s('text', { x: x0 + 1 + w + 6, y: y + LH / 2, class: 'val', 'dominant-baseline': 'central' }, g, fmt(d.valor));
      interativo(g, () => [d.rotulo, [{ valor: fmt(d.valor), nome: d.detalhe || o.serie || '', cor }]]);
    });
  }

  function eixoY(svg, tk, Y, x0, x1) {
    for (const t of tk) {
      s('line', { x1: x0, x2: x1, y1: Y(t), y2: Y(t), class: t === 0 ? 'base' : 'grid' }, svg);
      s('text', { x: x0 - 6, y: Y(t), class: 'eixo', 'text-anchor': 'end', 'dominant-baseline': 'central' }, svg, CP(t));
    }
  }
  function indicesRotulo(n, larguraUtil, minimo = 40) {
    const passo = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(larguraUtil / minimo))));
    const idx = [];
    for (let i = 0; i < n; i += passo) idx.push(i);
    if (idx[idx.length - 1] !== n - 1) {
      if (n - 1 - idx[idx.length - 1] < passo * 0.6) idx.pop();
      idx.push(n - 1);
    }
    return idx;
  }

  /* Linhas com mira: xs (rótulos completos), series [{nome, cor, valores}] */
  function linhas(host, xs, series, o = {}) {
    series = series.filter(sr => sr.valores.some(v => v > 0));
    if (!series.length) return vazio(host);
    if (series.length >= 2) legenda(host, series, 'lin');
    const fmt = o.fmt || N, W = largura(host), H = o.altura || 230;
    const max = Math.max(...series.flatMap(sr => sr.valores));
    const tk = marcas(max), topo = tk[tk.length - 1];
    const mL = Math.max(...tk.map(t => medir(CP(t), FONTE_EIXO))) + 10, mR = 12, mT = 8, mB = 22;
    const svg = novoSvg(host, W, H, o.rotulo);
    const util = W - mL - mR;
    const X = i => mL + (xs.length === 1 ? util / 2 : util * i / (xs.length - 1));
    const Y = v => mT + (H - mT - mB) * (1 - v / topo);
    eixoY(svg, tk, Y, mL, W - mR);
    const curtos = o.curtos || xs;
    for (const i of indicesRotulo(xs.length, util)) {
      s('text', { x: X(i), y: H - 5, class: 'eixo', 'text-anchor': i === 0 && xs.length > 1 ? 'start' : i === xs.length - 1 && xs.length > 1 ? 'end' : 'middle' }, svg, curtos[i]);
    }
    for (const sr of series) {
      s('path', { d: sr.valores.map((v, i) => `${i ? 'L' : 'M'}${X(i)},${Y(v)}`).join(''), class: 'lin', style: `stroke:var(--${sr.cor})` }, svg);
      const u = sr.valores.length - 1;
      s('circle', { cx: X(u), cy: Y(sr.valores[u]), r: 4, class: 'ponto', style: `fill:var(--${sr.cor})` }, svg);
    }
    const cruz = s('line', { y1: mT, y2: H - mB, class: 'cruz', visibility: 'hidden' }, svg);
    const area = s('rect', { x: mL - 12, y: 0, width: util + 24, height: H, class: 'hit', tabindex: '0', 'aria-label': 'Use as setas para percorrer os anos' }, svg);
    let atual = -1;
    const mostrar = (i, cx, cy) => {
      atual = i;
      cruz.setAttribute('x1', X(i)); cruz.setAttribute('x2', X(i)); cruz.setAttribute('visibility', 'visible');
      tipMostrar(cx, cy, xs[i], series.map(sr => ({ valor: fmt(sr.valores[i]), nome: sr.nome, cor: sr.cor })));
    };
    const esconder = () => { cruz.setAttribute('visibility', 'hidden'); tipEsconder(); };
    area.addEventListener('pointermove', ev => {
      const b = svg.getBoundingClientRect(), px = (ev.clientX - b.left) * W / b.width;
      const i = Math.max(0, Math.min(xs.length - 1, Math.round((px - mL) / (util / Math.max(1, xs.length - 1)))));
      mostrar(i, ev.clientX, ev.clientY);
    });
    area.addEventListener('pointerleave', esconder);
    area.addEventListener('blur', esconder);
    area.addEventListener('keydown', ev => {
      if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
      ev.preventDefault();
      const i = Math.max(0, Math.min(xs.length - 1, atual < 0 ? xs.length - 1 : atual + (ev.key === 'ArrowRight' ? 1 : -1)));
      const b = svg.getBoundingClientRect();
      mostrar(i, b.left + X(i) * b.width / W, b.top + 12);
    });
    if (o.nota) h('p', { class: 'nota-graf' }, host, o.nota);
  }

  /* Barras 100% empilhadas: linhasD [{rotulo, partes[]}], chaves [{nome, cor}] */
  function empilhada(host, linhasD, chaves, o = {}) {
    linhasD = linhasD.filter(l => l.partes.some(v => v > 0));
    if (!linhasD.length) return vazio(host);
    legenda(host, chaves.filter((_, j) => linhasD.some(l => l.partes[j] > 0)));
    const W = largura(host), LH = 32, BH = 20;
    const rotW = Math.min(Math.max(...linhasD.map(l => medir(l.rotulo))), W * 0.36) + 16;
    const H = linhasD.length * LH + 22;
    const svg = novoSvg(host, W, H, o.rotulo);
    const x0 = rotW, larg = W - rotW - 4;
    [0, 0.25, 0.5, 0.75, 1].forEach(t => {
      s('text', { x: x0 + larg * t, y: H - 4, class: 'eixo', 'text-anchor': t === 0 ? 'start' : t === 1 ? 'end' : 'middle' }, svg, Math.round(t * 100) + '%');
    });
    linhasD.forEach((l, i) => {
      const y = i * LH + (LH - BH) / 2, tot = l.partes.reduce((a, b) => a + b, 0);
      s('text', { x: x0 - 8, y: y + BH / 2, class: 'rot', 'text-anchor': 'end', 'dominant-baseline': 'central' }, svg, truncar(l.rotulo, rotW - 10));
      const ult = l.partes.reduce((u, v, j) => (v > 0 ? j : u), -1);
      let x = x0;
      l.partes.forEach((v, j) => {
        if (v <= 0) return;
        const w = larg * v / tot, wd = j === ult ? w : Math.max(0.6, w - 2), cor = chaves[j].cor;
        const g = s('g', {}, svg);
        s('rect', { x, y: y - 4, width: w, height: BH + 8, class: 'hit' }, g);
        s('path', { d: j === ult ? barraH(x, y, wd, BH) : `M${x},${y}h${wd}v${BH}h${-wd}Z`, class: 'marca', style: `fill:var(--${cor})` }, g);
        const pct = PC(v / tot);
        if (wd > medir(pct, '600 11px system-ui') + 10) {
          s('text', { x: x + 5, y: y + BH / 2, class: 'dentro' + (cor === 's4' || cor === 'deemph' ? ' s4' : ''), 'dominant-baseline': 'central' }, g, pct);
        }
        interativo(g, () => [l.rotulo, [{ valor: pct, nome: `${chaves[j].nome} · ${N(v)} registros`, cor }]]);
        x += w;
      });
    });
  }

  /* Colunas agrupadas: cats, series [{nome, cor, valores}] */
  function colunas(host, cats, series, o = {}) {
    if (!series.some(sr => sr.valores.some(v => v > 0))) return vazio(host);
    legenda(host, series);
    const fmt = o.fmt || N, W = largura(host), H = o.altura || 240;
    const max = Math.max(...series.flatMap(sr => sr.valores));
    const tk = marcas(max), topo = tk[tk.length - 1];
    const mL = Math.max(...tk.map(t => medir(CP(t), FONTE_EIXO))) + 10, mR = 4, mT = 8, mB = 24;
    const svg = novoSvg(host, W, H, o.rotulo);
    const Y = v => mT + (H - mT - mB) * (1 - v / topo), base = Y(0);
    eixoY(svg, tk, Y, mL, W - mR);
    const gw = (W - mL - mR) / cats.length, n = series.length;
    const bw = Math.max(4, Math.min(24, (gw * 0.72 - 2 * (n - 1)) / n));
    cats.forEach((c, i) => {
      const gx = mL + gw * i + (gw - (bw * n + 2 * (n - 1))) / 2;
      series.forEach((sr, j) => {
        const v = sr.valores[i], x = gx + j * (bw + 2), g = s('g', {}, svg);
        s('rect', { x: x - 1, y: mT, width: bw + 2, height: base - mT, class: 'hit' }, g);
        s('path', { d: barraV(x, base, bw, base - Y(v)), class: 'marca', style: `fill:var(--${sr.cor})` }, g);
        interativo(g, () => [c, [{ valor: fmt(v), nome: sr.nome, cor: sr.cor }]]);
      });
      s('text', { x: mL + gw * i + gw / 2, y: H - 6, class: 'eixo', 'text-anchor': 'middle' }, svg,
        truncar((o.curtos || cats)[i], gw - 4, FONTE_EIXO));
    });
  }

  /* Múltiplos pequenos: um mini gráfico de linha por painel, escala própria */
  function multiplos(host, xs, paineis, o = {}) {
    paineis = paineis.filter(p => p.valores.some(v => v > 0));
    if (!paineis.length) return vazio(host);
    const W = largura(host);
    const cols = Math.max(1, Math.min(o.colunas || 6, Math.floor((W + 14) / 165)));
    const grade = h('div', { class: 'multiplos' }, host);
    grade.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    const pw = Math.floor((W - 14 * (cols - 1)) / cols), ph = 64, H = ph + 20;
    for (const p of paineis) {
      const box = h('div', { class: 'mini' }, grade);
      const max = Math.max(...p.valores), cor = p.cor || 's1';
      h('h4', { title: p.titulo }, box, p.titulo);
      h('div', { class: 'mx' }, box, `máx. ${N(max)}`);
      const svg = novoSvg(box, pw, H, p.titulo);
      const X = i => 3 + (pw - 6) * (xs.length === 1 ? 0.5 : i / (xs.length - 1));
      const Y = v => 4 + ph * (1 - v / max);
      s('line', { x1: 0, x2: pw, y1: Y(0), y2: Y(0), class: 'base' }, svg);
      const caminho = p.valores.map((v, i) => `${i ? 'L' : 'M'}${X(i)},${Y(v)}`).join('');
      s('path', { d: `${caminho}L${X(p.valores.length - 1)},${Y(0)}L${X(0)},${Y(0)}Z`, style: `fill:var(--${cor});opacity:0.1` }, svg);
      s('path', { d: caminho, class: 'lin', style: `stroke:var(--${cor})` }, svg);
      s('text', { x: 0, y: H - 3, class: 'eixo' }, svg, (o.curtos || xs)[0]);
      s('text', { x: pw, y: H - 3, class: 'eixo', 'text-anchor': 'end' }, svg, (o.curtos || xs)[xs.length - 1]);
      const cruz = s('line', { y1: 2, y2: Y(0), class: 'cruz', visibility: 'hidden' }, svg);
      const area = s('rect', { x: 0, y: 0, width: pw, height: H, class: 'hit' }, svg);
      area.addEventListener('pointermove', ev => {
        const b = svg.getBoundingClientRect(), px = (ev.clientX - b.left) * pw / b.width;
        const i = Math.max(0, Math.min(xs.length - 1, Math.round((px - 3) / ((pw - 6) / Math.max(1, xs.length - 1)))));
        cruz.setAttribute('x1', X(i)); cruz.setAttribute('x2', X(i)); cruz.setAttribute('visibility', 'visible');
        tipMostrar(ev.clientX, ev.clientY, `${p.titulo} · ${xs[i]}`, [{ valor: N(p.valores[i]), nome: 'registros', cor }]);
      });
      area.addEventListener('pointerleave', () => { cruz.setAttribute('visibility', 'hidden'); tipEsconder(); });
    }
    if (o.nota) h('p', { class: 'nota-graf' }, host, o.nota);
  }

  /* Tabela: colunas [{t, f?, txt?, cor?(linha)->slot, calor?}], linhas: arrays */
  function tabela(host, colunasT, linhasT, o = {}) {
    if (!linhasT.length) return vazio(host);
    const wrap = h('div', { class: 'tab-wrap' }, host);
    if (o.altura) wrap.style.maxHeight = o.altura + 'px';
    const t = h('table', { class: 'dados' + (o.classe ? ' ' + o.classe : '') }, wrap);
    const trh = h('tr', null, h('thead', null, t));
    colunasT.forEach(c => h('th', { class: c.txt ? 'txt' : '', scope: 'col' }, trh, c.t));
    let maxCalor = 0;
    if (colunasT.some(c => c.calor)) {
      linhasT.forEach(l => colunasT.forEach((c, j) => { if (c.calor && l[j] > maxCalor) maxCalor = l[j]; }));
    }
    const tb = h('tbody', null, t);
    for (const l of linhasT) {
      const tr = h('tr', null, tb);
      colunasT.forEach((c, j) => {
        const td = h('td', { class: (c.txt ? 'txt' : '') + (c.calor ? ' c' : '') }, tr);
        if (c.cor) { const slot = c.cor(l); if (slot) h('span', { class: 'sw' }, td).style.background = `var(--${slot})`; }
        td.append(document.createTextNode(c.f ? c.f(l[j]) : (l[j] ?? '')));
        if (c.calor && maxCalor > 0 && l[j] > 0) td.style.background = `rgb(var(--heat) / ${(0.06 + 0.7 * l[j] / maxCalor).toFixed(3)})`;
      });
    }
    if (o.rodape) {
      const tr = h('tr', null, h('tfoot', null, t));
      o.rodape.forEach((v, j) => h('td', { class: colunasT[j].txt ? 'txt' : '' }, tr, j > 0 && colunasT[j].f ? colunasT[j].f(v) : v));
    }
    if (o.nota) h('p', { class: 'nota-graf' }, host, o.nota);
  }

  // ------------------------------------------------------------------ cartões
  const modoTabela = new Set();
  function cartao(grade, id, titulo, sub, classe) {
    const el = h('section', { class: 'card ' + (classe || ''), id: 'c-' + id, 'aria-label': titulo }, grade);
    const hd = h('header', null, el), tt = h('div', null, hd);
    h('h3', null, tt, titulo);
    if (sub) h('p', { class: 'sub' }, tt, sub);
    return { el, hd, corpo: h('div', { class: 'corpo' }, el), id };
  }
  /* Gráfico com alternância para tabela (a versão acessível de todo gráfico). */
  function grafico(card, desenhar, dadosTabela) {
    const em = () => modoTabela.has(card.id);
    const b = h('button', { type: 'button', class: 'ver-tab', 'aria-pressed': String(em()) }, card.hd, em() ? 'Gráfico' : 'Tabela');
    const pintar = () => {
      card.corpo.replaceChildren();
      if (em()) { const [c, l, op] = dadosTabela(); tabela(card.corpo, c, l, op); } else desenhar(card.corpo);
    };
    b.addEventListener('click', () => {
      em() ? modoTabela.delete(card.id) : modoTabela.add(card.id);
      b.textContent = em() ? 'Gráfico' : 'Tabela';
      b.setAttribute('aria-pressed', String(em()));
      pintar();
    });
    pintar();
  }
  function kpi(pai, rotulo, valor, detalhe, hero) {
    const k = h('div', { class: 'kpi' + (hero ? ' hero' : '') }, pai);
    h('div', { class: 'k-rot' }, k, rotulo);
    h('div', { class: 'k-val' }, k, valor);
    if (detalhe) h('div', { class: 'k-det' }, k, detalhe);
  }

  // ------------------------------------------------------------------ dados e estado
  let D;
  const LARG = { total: 3, faixa_sexo: 5 };
  const larg = nome => LARG[nome] || 4;
  const REG_SUL = ['América Latina e Caribe', 'Ásia', 'África', 'Oceania'];
  const COR_REG = { 'América Latina e Caribe': 's1', 'Ásia': 's2', 'África': 's3', 'Oceania': 's4', 'Europa': 's7', 'América do Norte': 's5', 'Indeterminado': 'deemph' };
  const COR_SEXO = { 'Feminino': 's1', 'Masculino': 's2', 'Não informado': 'deemph' };
  const ACOLHIDA = ['Acolhida humanitária', 'Refúgio/asilo', 'Acolhida a venezuelanos', 'Solicitação de refúgio (DPRNM)'];
  const QUALIF = ['Dirigentes, gerentes e proprietários', 'Profissionais das ciências e intelectuais'];
  const FORA = ['Estudantes e bolsistas', 'Fora da força de trabalho', 'Não classificado ou não informado'];
  const S = { a0: 0, a1: 0, crit: 'onu', regiao: '', pais: -1, aba: 'visao' };
  const ABAS = ['visao', 'origens', 'perfil', 'amparo', 'destinos', 'asia-africa', 'notas'];

  function pred(modo) {
    const { a0, a1, regiao, pais } = S, g = S.crit === 'unctad' ? 4 : 3;
    return (a, p) => {
      if (a < a0 || a > a1) return false;
      if (modo === 'todos') return true;
      const q = D.paises[p];
      if (regiao && q[1] !== regiao) return false;
      if (pais >= 0 && p !== pais) return false;
      if (modo === 'sul') return q[g] === 1;
      if (modo === 'norte') return q[g] === 0;
      if (modo === 'aa') return q[1] === 'Ásia' || q[1] === 'África';
      return true;
    };
  }
  function agg(nome, modo, chave) {
    const c = D.cubos[nome], w = larg(nome), ok = pred(modo), m = new Map();
    for (let i = 0; i < c.length; i += w) {
      if (!ok(c[i], c[i + 1])) continue;
      const k = chave ? chave(c, i) : 0;
      m.set(k, (m.get(k) || 0) + c[i + w - 1]);
    }
    return m;
  }
  const soma = m => { let t = 0; for (const v of m.values()) t += v; return t; };
  const ordenar = m => [...m.entries()].filter(e => e[1] > 0).sort((a, b) => b[1] - a[1]);
  const pais = p => D.paises[p][0];
  const regiaoDe = p => D.paises[p][1];
  const subDe = p => D.paises[p][2];

  /* Indicadores por chave (região, sub-região, país...). chaveP: índice do país -> chave */
  function indicadores(modo, chaveP) {
    const tot = agg('total', modo, (c, i) => chaveP(c[i + 1]));
    const sx = agg('sexo', modo, (c, i) => chaveP(c[i + 1]) + '|' + c[i + 2]);
    const tp = agg('tip', modo, (c, i) => chaveP(c[i + 1]) + '|' + c[i + 2]);
    const gr = agg('grupo', modo, (c, i) => chaveP(c[i + 1]) + '|' + c[i + 2]);
    const iF = D.dims.sexo.indexOf('Feminino'), iM = D.dims.sexo.indexOf('Masculino');
    const iT = D.dims.tip.indexOf('Trabalho/investimentos'), iR = D.dims.tip.indexOf('Reunião familiar');
    const iA = ACOLHIDA.map(t => D.dims.tip.indexOf(t)).filter(i => i >= 0);
    const iQ = QUALIF.map(g => D.dims.grupo.indexOf(g));
    const iO = D.dims.grupo.map((g, i) => (FORA.includes(g) ? -1 : i)).filter(i => i >= 0);
    return k => {
      const t = tot.get(k) || 0, v = (m, i) => m.get(k + '|' + i) || 0;
      const f = v(sx, iF), mm = v(sx, iM);
      const ocup = iO.reduce((a, i) => a + v(gr, i), 0), q = iQ.reduce((a, i) => a + v(gr, i), 0);
      return {
        total: t,
        mulheres: f + mm ? f / (f + mm) : null,
        trab: t ? v(tp, iT) / t : null,
        reun: t ? v(tp, iR) / t : null,
        acolh: t ? iA.reduce((a, i) => a + v(tp, i), 0) / t : null,
        qualif: ocup ? q / ocup : null,
      };
    };
  }

  const anosSel = () => intervalo(S.a0, S.a1);
  const rotAno = a => D.rotulos_ano[a];
  const curtoAno = a => String(D.anos[a]) + (D.rotulos_ano[a] !== String(D.anos[a]) ? '*' : '');
  const temParcial = () => anosSel().some(a => D.rotulos_ano[a] !== String(D.anos[a]));
  const notaParcial = () => (temParcial() ? '* ano parcial: ' + anosSel().filter(a => D.rotulos_ano[a] !== String(D.anos[a])).map(rotAno).join(', ') : '');
  const periodo = () => (S.a0 === S.a1 ? rotAno(S.a0) : `${D.anos[S.a0]} a ${rotAno(S.a1)}`);
  const critNome = () => (S.crit === 'unctad' ? 'UNCTAD' : 'ONU/DESA');

  // ------------------------------------------------------------------ páginas
  const main = document.getElementById('conteudo');

  function semSul(total) {
    if (total > 0) return false;
    const msg = S.pais >= 0
      ? `${pais(S.pais)} não tem registros do Sul Global neste recorte (pelo critério ${critNome()}, pode pertencer ao Norte Global).`
      : 'Nenhum registro do Sul Global para esta seleção.';
    h('p', { class: 'aviso' }, main, msg);
    return true;
  }

  function pgVisao() {
    const porPais = agg('total', 'sul', (c, i) => c[i + 1]);
    const total = soma(porPais), todos = soma(agg('total', 'todos'));
    if (semSul(total)) return;
    const k = h('div', { class: 'kpis' }, main);
    kpi(k, 'Registros Sul-Sul', N(total), periodo(), true);
    kpi(k, '% do total de registros de imigrantes', PC(total / todos), `de ${N(todos)} registros no período`);
    const rank = ordenar(porPais);
    kpi(k, 'Países de origem no Sul Global', N(rank.length), `critério ${critNome()}`);
    kpi(k, 'Principal origem', rank.length ? pais(rank[0][0]) : '–', rank.length ? `${PC(rank[0][1] / total)} dos registros Sul-Sul` : '');
    const geral = indicadores('sul', () => 'T')('T');
    kpi(k, 'Mulheres', PC(geral.mulheres), 'entre registros com sexo informado');

    const grade = h('div', { class: 'grade' }, main);
    const anos = anosSel();
    const sulA = agg('total', 'sul', (c, i) => c[i]), norA = agg('total', 'norte', (c, i) => c[i]);
    const serie = [
      { nome: 'Sul Global', cor: 's1', valores: anos.map(a => sulA.get(a) || 0) },
      { nome: 'Norte Global', cor: 'deemph', valores: anos.map(a => norA.get(a) || 0) },
    ];
    grafico(cartao(grade, 'v-anos', 'Registros por ano', 'Sul Global e Norte Global', 'c8'),
      host => linhas(host, anos.map(rotAno), serie, { curtos: anos.map(curtoAno), nota: notaParcial() }),
      () => [[{ t: 'Ano', txt: true }, { t: 'Sul Global', f: N }, { t: 'Norte Global', f: N }],
        anos.map((a, i) => [rotAno(a), serie[0].valores[i], serie[1].valores[i]])]);

    const porReg = agg('total', 'sul', (c, i) => regiaoDe(c[i + 1]));
    const itReg = ordenar(porReg).map(([r, v]) => ({ rotulo: r, valor: v, cor: COR_REG[r] }));
    grafico(cartao(grade, 'v-reg', 'Por região de origem', null, 'c4'),
      host => barras(host, itReg, { linha: 30 }),
      () => [[{ t: 'Região', txt: true, cor: l => COR_REG[l[0]] }, { t: 'Registros', f: N }, { t: '% do Sul Global', f: PC }],
        itReg.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const top = rank.slice(0, 10).map(([p, v]) => ({ rotulo: pais(p), valor: v }));
    grafico(cartao(grade, 'v-top', '10 principais países de origem', null, 'c4'),
      host => barras(host, top),
      () => [[{ t: 'País', txt: true }, { t: 'Registros', f: N }, { t: '% do Sul Global', f: PC }], top.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const tip_ = ordenar(agg('tip', 'sul', (c, i) => c[i + 2])).map(([t, v]) => ({ rotulo: D.dims.tip[t], valor: v }));
    grafico(cartao(grade, 'v-tip', 'Tipologia de amparo legal', null, 'c4'),
      host => barras(host, tip_),
      () => [[{ t: 'Tipologia', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], tip_.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const ind = indicadores('sul', regiaoDe);
    const linhasInd = itReg.map(d => { const x = ind(d.rotulo); return [d.rotulo, x.total, x.trab, x.acolh]; });
    tabela(cartao(grade, 'v-ind', 'Indicadores por região', 'Acolhida/refúgio: acolhida humanitária, acolhida a venezuelanos, refúgio/asilo e solicitação de refúgio. Mais indicadores em Origens.', 'c4').corpo,
      [{ t: 'Região', txt: true, cor: l => COR_REG[l[0]] }, { t: 'Registros', f: N }, { t: '% trabalho/ invest.', f: PC }, { t: '% acolhida/ refúgio', f: PC }],
      linhasInd, { rodape: ['Total', total, geral.trab, geral.acolh] });
  }

  function pgOrigens() {
    const porPais = agg('total', 'sul', (c, i) => c[i + 1]);
    const total = soma(porPais);
    if (semSul(total)) return;
    const grade = h('div', { class: 'grade' }, main);

    const porSub = agg('total', 'sul', (c, i) => subDe(c[i + 1]));
    const regDaSub = {};
    D.paises.forEach(q => { regDaSub[q[2]] = q[1]; });
    const itSub = ordenar(porSub).map(([sb, v]) => ({ rotulo: sb, valor: v, cor: COR_REG[regDaSub[sb]], detalhe: regDaSub[sb] }));
    const regsPresentes = REG_SUL.filter(r => itSub.some(d => d.detalhe === r));
    grafico(cartao(grade, 'o-sub', 'Registros por sub-região de origem', 'Sub-regiões da ONU (M49), cor pela região', 'c5'),
      host => { legenda(host, regsPresentes.map(r => ({ nome: r, cor: COR_REG[r] }))); barras(host, itSub); },
      () => [[{ t: 'Sub-região', txt: true, cor: l => COR_REG[regDaSub[l[0]]] }, { t: 'Região', txt: true }, { t: 'Registros', f: N }, { t: '% do Sul Global', f: PC }],
        itSub.map(d => [d.rotulo, d.detalhe, d.valor, d.valor / total])]);

    const anos = anosSel();
    const regAno = agg('total', 'sul', (c, i) => regiaoDe(c[i + 1]) + '|' + c[i]);
    const series = REG_SUL.map(r => ({ nome: r, cor: COR_REG[r], valores: anos.map(a => regAno.get(r + '|' + a) || 0) }));
    grafico(cartao(grade, 'o-anos', 'Evolução anual por região de origem', null, 'c7'),
      host => linhas(host, anos.map(rotAno), series, { curtos: anos.map(curtoAno), altura: 260, nota: notaParcial() }),
      () => [[{ t: 'Ano', txt: true }, ...series.filter(x => x.valores.some(v => v > 0)).map(x => ({ t: x.nome, f: N }))],
        anos.map((a, i) => [rotAno(a), ...series.filter(x => x.valores.some(v => v > 0)).map(x => x.valores[i])])]);

    const rank = ordenar(porPais);
    const top = rank.slice(0, 15).map(([p, v]) => ({ rotulo: pais(p), valor: v, cor: COR_REG[regiaoDe(p)], detalhe: regiaoDe(p) }));
    grafico(cartao(grade, 'o-top', '15 principais países de origem', 'Cor pela região', 'c5'),
      host => { legenda(host, REG_SUL.filter(r => top.some(d => d.detalhe === r)).map(r => ({ nome: r, cor: COR_REG[r] }))); barras(host, top); },
      () => [[{ t: 'País', txt: true }, { t: 'Região', txt: true }, { t: 'Registros', f: N }], top.map(d => [d.rotulo, d.detalhe, d.valor])]);

    const ind = indicadores('sul', p => p);
    tabela(cartao(grade, 'o-paises', 'Todos os países de origem do Sul Global', `${rank.length} países, do maior para o menor número de registros`, 'c7').corpo,
      [{ t: 'País', txt: true, cor: l => COR_REG[regDaSub[l[1]]] }, { t: 'Sub-região', txt: true }, { t: 'Registros', f: N },
        { t: '% do Sul', f: PC }, { t: '% mulheres', f: PC }, { t: '% trabalho/ invest.', f: PC }, { t: '% acolhida/ refúgio', f: PC }],
      rank.map(([p, v]) => { const x = ind(p); return [pais(p), subDe(p), v, v / total, x.mulheres, x.trab, x.acolh]; }),
      { altura: 420 });
  }

  function pgPerfil() {
    const total = soma(agg('total', 'sul'));
    if (semSul(total)) return;
    const grade = h('div', { class: 'grade' }, main);
    const sexos = D.dims.sexo, chavesSexo = sexos.map(x => ({ nome: x, cor: COR_SEXO[x] || 'deemph' }));

    const regSx = agg('sexo', 'sul', (c, i) => regiaoDe(c[i + 1]) + '|' + c[i + 2]);
    const regTot = agg('total', 'sul', (c, i) => regiaoDe(c[i + 1]));
    const linhasSx = ordenar(regTot).map(([r]) => ({ rotulo: r, partes: sexos.map((_, j) => regSx.get(r + '|' + j) || 0) }));
    grafico(cartao(grade, 'p-sexo', 'Sexo por região de origem', 'Distribuição percentual', 'c4'),
      host => empilhada(host, linhasSx, chavesSexo),
      () => [[{ t: 'Região', txt: true }, ...sexos.map(x => ({ t: x, f: N }))], linhasSx.map(l => [l.rotulo, ...l.partes])]);

    const fs = agg('faixa_sexo', 'sul', (c, i) => c[i + 2] + '|' + c[i + 3]);
    const faixas = D.dims.faixa;
    const curtosF = faixas.map(f => f.replace(' anos ou mais', '+').replace(' anos', '').replace(' a ', '–').replace('Não informado', 'n/i'));
    const seriesF = sexos.map((x, j) => ({ nome: x, cor: COR_SEXO[x] || 'deemph', valores: faixas.map((_, k) => fs.get(k + '|' + j) || 0) }))
      .filter(x => x.valores.some(v => v > 0));
    grafico(cartao(grade, 'p-faixa', 'Faixa etária e sexo', null, 'c4'),
      host => colunas(host, faixas, seriesF, { curtos: curtosF }),
      () => [[{ t: 'Faixa etária', txt: true }, ...seriesF.map(x => ({ t: x.nome, f: N }))], faixas.map((f, k) => [f, ...seriesF.map(x => x.valores[k])])]);

    const civ = ordenar(agg('civil', 'sul', (c, i) => c[i + 2])).map(([k, v]) => ({ rotulo: D.dims.civil[k], valor: v }));
    grafico(cartao(grade, 'p-civil', 'Estado civil', null, 'c4'),
      host => barras(host, civ),
      () => [[{ t: 'Estado civil', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], civ.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const grp = ordenar(agg('grupo', 'sul', (c, i) => c[i + 2])).map(([k, v]) => ({ rotulo: D.dims.grupo[k], valor: v }));
    grafico(cartao(grade, 'p-grupo', 'Grande grupo ocupacional', 'Classificação própria inspirada na CBO/ISCO', 'c5'),
      host => barras(host, grp, { fracRotulo: 0.5 }),
      () => [[{ t: 'Grupo ocupacional', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], grp.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const prof = ordenar(agg('prof', 'sul', (c, i) => c[i + 2])).slice(0, 15);
    tabela(cartao(grade, 'p-prof', '15 profissões declaradas mais frequentes', null, 'c7').corpo,
      [{ t: 'Profissão', txt: true }, { t: 'Grupo ocupacional', txt: true }, { t: 'Registros', f: N }, { t: '% do total', f: PC }],
      prof.map(([k, v]) => [D.dims.prof[k], D.dims.grupo[D.grupo_da_prof[k]], v, v / total]), { altura: 520 });
  }

  function pgAmparo() {
    const total = soma(agg('total', 'sul'));
    if (semSul(total)) return;
    const grade = h('div', { class: 'grade' }, main);
    const porTip = agg('tip', 'sul', (c, i) => c[i + 2]);
    const tipOrd = ordenar(porTip);
    const itTip = tipOrd.map(([k, v]) => ({ rotulo: D.dims.tip[k], valor: v }));
    grafico(cartao(grade, 'a-tip', 'Registros por tipologia de amparo', null, 'c4'),
      host => barras(host, itTip, { fracRotulo: 0.5 }),
      () => [[{ t: 'Tipologia', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], itTip.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const anos = anosSel();
    const tipAno = agg('tip', 'sul', (c, i) => c[i + 2] + '|' + c[i]);
    const paineis = tipOrd.map(([k]) => ({ titulo: D.dims.tip[k], valores: anos.map(a => tipAno.get(k + '|' + a) || 0) }));
    grafico(cartao(grade, 'a-mult', 'Evolução anual de cada tipologia', 'Cada painel tem escala própria', 'c8'),
      host => multiplos(host, anos.map(rotAno), paineis, { curtos: anos.map(curtoAno), nota: notaParcial() }),
      () => [[{ t: 'Ano', txt: true }, ...paineis.map(p => ({ t: p.titulo, f: N }))], anos.map((a, i) => [rotAno(a), ...paineis.map(p => p.valores[i])])]);

    const regTip = agg('tip', 'sul', (c, i) => regiaoDe(c[i + 1]) + '|' + c[i + 2]);
    const regTot = agg('total', 'sul', (c, i) => regiaoDe(c[i + 1]));
    const regs = ordenar(regTot).map(([r]) => r);
    const linhasCal = tipOrd.map(([k, v]) => [D.dims.tip[k], ...regs.map(r => (regTip.get(r + '|' + k) || 0) / regTot.get(r)), v / total]);
    tabela(cartao(grade, 'a-calor', 'Tipologia de amparo por região de origem', '% de cada região (coluna); cor mais forte = maior participação', 'c7').corpo,
      [{ t: 'Tipologia', txt: true }, ...regs.map(r => ({ t: r, f: PC, calor: true })), { t: 'Sul Global', f: PC }],
      linhasCal, { classe: 'calor' });

    const cls = ordenar(agg('cls', 'sul', (c, i) => c[i + 2])).map(([k]) => k);
    let slot = 0;
    const chavesCls = cls.map(k => ({ nome: D.dims.cls[k], cor: D.dims.cls[k] === 'Não informado' ? 'deemph' : 's' + (++slot) }));
    const regCls = agg('cls', 'sul', (c, i) => regiaoDe(c[i + 1]) + '|' + c[i + 2]);
    const linhasCls = regs.map(r => ({ rotulo: r, partes: cls.map(k => regCls.get(r + '|' + k) || 0) }));
    grafico(cartao(grade, 'a-cls', 'Classificação do registro por região', 'Distribuição percentual', 'c5'),
      host => empilhada(host, linhasCls, chavesCls),
      () => [[{ t: 'Região', txt: true }, ...chavesCls.map(c => ({ t: c.nome, f: N }))], linhasCls.map(l => [l.rotulo, ...l.partes])]);
  }

  function pgDestinos() {
    const total = soma(agg('total', 'sul'));
    if (semSul(total)) return;
    const grade = h('div', { class: 'grade' }, main);
    const porUf = ordenar(agg('uf', 'sul', (c, i) => c[i + 2]));
    const itUf = porUf.map(([k, v]) => ({ rotulo: D.uf_nome[k], valor: v }));
    grafico(cartao(grade, 'd-uf', 'Por Unidade da Federação de residência', null, 'c5'),
      host => barras(host, itUf, { linha: 22 }),
      () => [[{ t: 'UF', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], itUf.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const col = h('div', { class: 'card c7', style: 'background:none;border:0;padding:0;gap:14px' }, grade);
    const porRb = new Map();
    porUf.forEach(([k, v]) => { const r = D.uf_regiao[k]; porRb.set(r, (porRb.get(r) || 0) + v); });
    const itRb = ordenar(porRb).map(([r, v]) => ({ rotulo: r, valor: v }));
    const c1 = cartao(col, 'd-rb', 'Por região do Brasil');
    grafico(c1, host => barras(host, itRb),
      () => [[{ t: 'Região', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], itRb.map(d => [d.rotulo, d.valor, d.valor / total])]);
    const iNI = D.dims.mun.indexOf('Não informado');
    const mun = ordenar(agg('mun', 'sul', (c, i) => c[i + 2])).filter(([k]) => k !== iNI).slice(0, 15)
      .map(([k, v]) => ({ rotulo: D.dims.mun[k], valor: v }));
    const c2 = cartao(col, 'd-mun', '15 principais municípios de residência', 'Exclui registros sem município informado');
    grafico(c2, host => barras(host, mun),
      () => [[{ t: 'Município', txt: true }, { t: 'Registros', f: N }, { t: '%', f: PC }], mun.map(d => [d.rotulo, d.valor, d.valor / total])]);

    const ufReg = agg('uf', 'sul', (c, i) => c[i + 2] + '|' + regiaoDe(c[i + 1]));
    const regs = REG_SUL.filter(r => porUf.some(([k]) => ufReg.get(k + '|' + r)));
    tabela(cartao(grade, 'd-tab', 'UF de residência × região de origem', null, 'c12').corpo,
      [{ t: 'UF', txt: true }, ...regs.map(r => ({ t: r, f: N })), { t: 'Total', f: N }],
      porUf.map(([k, v]) => [D.uf_nome[k], ...regs.map(r => ufReg.get(k + '|' + r) || 0), v]),
      { altura: 620, rodape: ['Total', ...regs.map(r => porUf.reduce((a, [k]) => a + (ufReg.get(k + '|' + r) || 0), 0)), total] });
  }

  function pgAsiaAfrica() {
    h('p', { class: 'aviso' }, main,
      'Esta página inclui todos os países da Ásia e da África, também os do Norte Global (Japão, Coreia do Sul, Israel e Chipre), para comparar a Ásia Oriental com o restante da Ásia e com a África. O critério de Sul Global não se aplica aqui.');
    const porSub = agg('total', 'aa', (c, i) => subDe(c[i + 1]));
    const total = soma(porSub);
    if (!total) return vazio(main, 'Sem registros da Ásia ou da África para esta seleção.');
    const grade = h('div', { class: 'grade' }, main);
    const subsOrdem = [...new Set(D.paises.filter(q => q[1] === 'África' || q[1] === 'Ásia').map(q => q[2]))].filter(sb => porSub.get(sb) > 0);
    const regDaSub = {};
    D.paises.forEach(q => { regDaSub[q[2]] = q[1]; });
    const ind = indicadores('aa', subDe), g = indicadores('aa', () => 'T')('T');
    tabela(cartao(grade, 'aa-ind', 'Indicadores por sub-região', '* dirigentes e profissionais: entre os registros com ocupação declarada no mercado de trabalho', 'c8').corpo,
      [{ t: 'Sub-região', txt: true, cor: l => COR_REG[regDaSub[l[0]]] }, { t: 'Registros', f: N }, { t: '% mulheres', f: PC },
        { t: '% trabalho/ investimentos', f: PC }, { t: '% reunião familiar', f: PC }, { t: '% acolhida humanitária/ refúgio', f: PC },
        { t: '% dirigentes e profissionais*', f: PC }],
      subsOrdem.map(sb => { const x = ind(sb); return [sb, x.total, x.mulheres, x.trab, x.reun, x.acolh, x.qualif]; }),
      { rodape: ['Ásia e África', total, g.mulheres, g.trab, g.reun, g.acolh, g.qualif] });

    const top = ordenar(agg('total', 'aa', (c, i) => c[i + 1])).slice(0, 10)
      .map(([p, v]) => ({ rotulo: pais(p), valor: v, cor: COR_REG[regiaoDe(p)], detalhe: regiaoDe(p) }));
    grafico(cartao(grade, 'aa-top', '10 principais países', 'Cor pela região', 'c4'),
      host => { legenda(host, ['Ásia', 'África'].filter(r => top.some(d => d.detalhe === r)).map(r => ({ nome: r, cor: COR_REG[r] }))); barras(host, top); },
      () => [[{ t: 'País', txt: true }, { t: 'Região', txt: true }, { t: 'Registros', f: N }], top.map(d => [d.rotulo, d.detalhe, d.valor])]);

    const subGr = agg('grupo', 'aa', (c, i) => subDe(c[i + 1]) + '|' + c[i + 2]);
    tabela(cartao(grade, 'aa-grupo', 'Grupo ocupacional por sub-região', '% de cada sub-região (coluna); cor mais forte = maior participação', 'c12').corpo,
      [{ t: 'Grupo ocupacional', txt: true }, ...subsOrdem.map(sb => ({ t: sb, f: PC, calor: true }))],
      D.dims.grupo.map((gn, k) => [gn, ...subsOrdem.map(sb => (subGr.get(sb + '|' + k) || 0) / porSub.get(sb))]),
      { classe: 'calor' });
  }

  function pgNotas() {
    main.append(document.getElementById('tpl-notas').content.cloneNode(true));
  }

  const PAGINAS = { visao: pgVisao, origens: pgOrigens, perfil: pgPerfil, amparo: pgAmparo, destinos: pgDestinos, 'asia-africa': pgAsiaAfrica, notas: pgNotas };

  // ------------------------------------------------------------------ filtros e navegação
  const $ = id => document.getElementById(id);
  function lerHash() {
    const [aba, q] = location.hash.slice(1).split('?');
    // o link define a visão inteira: filtros ausentes voltam ao padrão
    Object.assign(S, { a0: 0, a1: D.anos.length - 1, crit: 'onu', regiao: '', pais: -1 });
    if (ABAS.includes(aba)) S.aba = aba;
    const p = new URLSearchParams(q || '');
    const iAno = v => D.anos.indexOf(Number(v));
    if (p.has('de') && iAno(p.get('de')) >= 0) S.a0 = iAno(p.get('de'));
    if (p.has('ate') && iAno(p.get('ate')) >= 0) S.a1 = iAno(p.get('ate'));
    if (S.a0 > S.a1) [S.a0, S.a1] = [S.a1, S.a0];
    if (p.get('crit') === 'unctad') S.crit = 'unctad';
    if (REG_SUL.includes(p.get('regiao'))) S.regiao = p.get('regiao');
    if (p.has('pais')) { const i = D.paises.findIndex(q2 => q2[0] === p.get('pais')); if (i >= 0) { S.pais = i; S.regiao = regiaoDe(i); } }
  }
  function escreverHash() {
    const p = new URLSearchParams();
    if (S.a0 !== 0) p.set('de', D.anos[S.a0]);
    if (S.a1 !== D.anos.length - 1) p.set('ate', D.anos[S.a1]);
    if (S.crit !== 'onu') p.set('crit', S.crit);
    if (S.regiao) p.set('regiao', S.regiao);
    if (S.pais >= 0) p.set('pais', pais(S.pais));
    const q = p.toString();
    history.replaceState(null, '', '#' + S.aba + (q ? '?' + q : ''));
  }
  function montarFiltros() {
    for (const id of ['de', 'ate']) {
      const sel = $(id);
      D.anos.forEach((a, i) => h('option', { value: i }, sel, rotAno(i)));
    }
    const sr = $('regiao');
    h('option', { value: '' }, sr, 'Todas as regiões');
    REG_SUL.forEach(r => h('option', { value: r }, sr, r));
    const sp = $('pais');
    h('option', { value: '-1' }, sp, 'Todos os países');
    for (const r of REG_SUL) {
      const og = h('optgroup', { label: r }, sp);
      D.paises.map((q, i) => [q, i]).filter(([q]) => q[1] === r)
        .sort((x, y) => x[0][0].localeCompare(y[0][0], 'pt-BR'))
        .forEach(([q, i]) => h('option', { value: i }, og, q[0]));
    }
    $('de').addEventListener('change', e => { S.a0 = Number(e.target.value); if (S.a0 > S.a1) S.a1 = S.a0; atualizar(); });
    $('ate').addEventListener('change', e => { S.a1 = Number(e.target.value); if (S.a1 < S.a0) S.a0 = S.a1; atualizar(); });
    $('crit').addEventListener('change', e => { S.crit = e.target.value; atualizar(); });
    $('regiao').addEventListener('change', e => { S.regiao = e.target.value; if (S.pais >= 0 && regiaoDe(S.pais) !== S.regiao) S.pais = -1; atualizar(); });
    $('pais').addEventListener('change', e => { S.pais = Number(e.target.value); if (S.pais >= 0) S.regiao = regiaoDe(S.pais); atualizar(); });
    document.querySelectorAll('.f-preset').forEach(b => b.addEventListener('click', () => {
      S.a1 = D.anos.length - 1;
      S.a0 = b.dataset.preset === '2016' ? Math.max(0, D.anos.indexOf(2016)) : 0;
      atualizar();
    }));
    $('limpar').addEventListener('click', () => { Object.assign(S, { a0: 0, a1: D.anos.length - 1, crit: 'onu', regiao: '', pais: -1 }); atualizar(); });
    document.querySelectorAll('.abas button').forEach(b => b.addEventListener('click', () => { S.aba = b.dataset.aba; atualizar(); window.scrollTo({ top: 0 }); }));
    document.querySelector('.abas').addEventListener('keydown', ev => {
      if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
      const i = ABAS.indexOf(S.aba), j = (i + (ev.key === 'ArrowRight' ? 1 : ABAS.length - 1)) % ABAS.length;
      S.aba = ABAS[j]; atualizar();
      document.querySelector(`.abas button[data-aba="${S.aba}"]`).focus();
    });
  }
  function sincronizarControles() {
    $('de').value = S.a0; $('ate').value = S.a1; $('crit').value = S.crit; $('regiao').value = S.regiao; $('pais').value = S.pais;
    const ultimo = D.anos.length - 1, i2016 = D.anos.indexOf(2016);
    document.querySelectorAll('.f-preset').forEach(b => {
      const ativo = b.dataset.preset === 'tudo' ? (S.a0 === 0 && S.a1 === ultimo) : (S.a0 === i2016 && S.a1 === ultimo);
      b.setAttribute('aria-pressed', String(ativo));
    });
    const aa = S.aba === 'asia-africa';
    $('crit').disabled = aa;
    $('g-crit').title = aa ? 'Não se aplica à página Ásia e África' : '';
    document.querySelectorAll('.abas button').forEach(b => {
      const sel = b.dataset.aba === S.aba;
      b.setAttribute('aria-selected', String(sel));
      b.tabIndex = sel ? 0 : -1;
    });
  }
  function atualizar() {
    tipEsconder();
    sincronizarControles();
    escreverHash();
    main.replaceChildren();
    PAGINAS[S.aba]();
  }

  // tema claro/escuro (a preferência do sistema vale até a pessoa escolher)
  (function tema() {
    const raiz = document.documentElement;
    try { const t = localStorage.getItem('tema'); if (t) raiz.dataset.theme = t; } catch (e) { /* sem armazenamento */ }
    $('tema').addEventListener('click', () => {
      const escuroAgora = raiz.dataset.theme ? raiz.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
      raiz.dataset.theme = escuroAgora ? 'light' : 'dark';
      try { localStorage.setItem('tema', raiz.dataset.theme); } catch (e) { /* ignora */ }
    });
  })();

  let espera;
  let larguraAnterior = innerWidth;
  addEventListener('resize', () => {
    if (innerWidth === larguraAnterior) return;
    larguraAnterior = innerWidth;
    clearTimeout(espera);
    espera = setTimeout(atualizar, 150);
  });
  addEventListener('hashchange', () => { lerHash(); atualizar(); });
  addEventListener('scroll', tipEsconder, { passive: true });

  fetch('dados.json')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(dados => {
      D = dados;
      S.a1 = D.anos.length - 1;
      $('gerado').textContent = `Dados atualizados em ${D.gerado_em.split('-').reverse().join('/')}`;
      montarFiltros();
      lerHash();
      atualizar();
    })
    .catch(err => {
      main.replaceChildren();
      h('p', { class: 'aviso' }, main, 'Não foi possível carregar os dados (' + err.message + '). Se abriu o arquivo direto do disco, sirva a pasta docs/ por um servidor web local.');
    });
})();
