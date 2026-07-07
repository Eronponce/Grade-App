const state = {
  grades: [],
  canonicals: [],
  turmas: [],
  currentBim: { year: 2026, bim: 2 },
  calendar: {},
  query: "",
  view: "search",
  cart: loadCart(),
};

const CART_KEY = "grade_lab_cart_v1";
const BIM_MONTHS = {
  1: "Fev–Abr",
  2: "Mai–Jul",
  3: "Ago–Set",
  4: "Out–Dez",
};

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { studentName: "", targetTurmaId: null, items: [] };
}

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(state.cart));
}

function cartHas(canonical) {
  return state.cart.items.some((it) => it.canonical === canonical);
}

function cartAdd(canonical) {
  if (cartHas(canonical)) return;
  state.cart.items.push({ canonical });
  saveCart();
  refreshCartUI();
}

function cartRemove(canonical) {
  state.cart.items = state.cart.items.filter((it) => it.canonical !== canonical);
  saveCart();
  refreshCartUI();
}

function cartClear() {
  state.cart.items = [];
  saveCart();
  refreshCartUI();
}

function refreshCartUI() {
  const count = state.cart.items.length;
  $("#cart-count").textContent = count;
  $("#cart-count").classList.toggle("zero", count === 0);
  const modal = $("#cart-modal");
  if (!modal.classList.contains("hidden")) renderCartModal();
  // Update add-cart buttons in visible cards
  document.querySelectorAll(".add-cart-btn").forEach((btn) => {
    const c = btn.dataset.canonical;
    if (cartHas(c)) { btn.classList.add("in-cart"); btn.textContent = "✓ no carrinho"; }
    else { btn.classList.remove("in-cart"); btn.textContent = "+ carrinho"; }
  });
}

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function foldStr(s) {
  return (s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").trim();
}

function fuzzyMatch(query, target) {
  const q = foldStr(query);
  const t = foldStr(target);
  if (!q) return true;
  if (t.includes(q)) return true;
  const tokens = q.split(/\s+/).filter(Boolean);
  return tokens.every((tok) => t.includes(tok));
}

function scoreMatch(query, target) {
  const q = foldStr(query);
  const t = foldStr(target);
  if (!q) return 0;
  if (t === q) return 1000;
  if (t.startsWith(q)) return 500;
  if (t.includes(q)) return 200;
  const tokens = q.split(/\s+/).filter(Boolean);
  let score = 0;
  tokens.forEach((tok) => { if (t.includes(tok)) score += 50; });
  return score;
}

async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function bimIndex(y, b) { return y * 4 + (b - 1); }

async function loadAll() {
  const [gradesResp, canonicalsResp, turmasResp, healthResp, calResp] = await Promise.all([
    fetchJSON("/api/grades"),
    fetchJSON("/api/canonicals"),
    fetchJSON("/api/turmas"),
    fetchJSON("/api/health"),
    fetchJSON("/api/calendar"),
  ]);
  state.grades = gradesResp.grades;
  state.canonicals = canonicalsResp.canonicals;
  state.turmas = turmasResp.turmas;
  state.currentBim = turmasResp.current_bimestre;
  state.calendar = {};
  (calResp.periods || []).forEach((p) => {
    state.calendar[`${p.year}-${p.bim}`] = p;
  });

  $("#bim-year").value = state.currentBim.year;
  $("#bim-num").value = state.currentBim.bim;

  const active = state.turmas.filter((t) => !t.graduated).length;
  const grads = state.turmas.length - active;
  $("#health-line").textContent =
    `${healthResp.grades} grades · ${healthResp.disciplines} disc · ${active} turmas ativas${grads ? ` · ${grads} formada${grads > 1 ? "s" : ""}` : ""}`;

  renderSidebar();
  renderResults();
  renderTimeline();
}

async function refreshCanonicals() {
  const r = await fetchJSON("/api/canonicals");
  state.canonicals = r.canonicals;
  renderResults();
  renderTimeline();
}

async function refreshTurmasOnly() {
  const r = await fetchJSON("/api/turmas");
  state.turmas = r.turmas;
  state.currentBim = r.current_bimestre;
  renderSidebar();
}

function renderSidebar() {
  const container = $("#turmas-list");
  container.innerHTML = "";
  if (state.turmas.length === 0) {
    container.innerHTML = `<div class="empty-turmas">Nenhuma turma. Clique <b>+</b> ou <b>Autopopular</b>.</div>`;
    return;
  }
  const byGrade = {};
  state.turmas.forEach((t) => { (byGrade[t.grade_id] ||= []).push(t); });
  Object.keys(byGrade).sort().forEach((gid) => {
    byGrade[gid].forEach((t) => container.appendChild(turmaRowEl(t, gid)));
  });
}

function turmaRowEl(turma, gradeId) {
  const el = document.createElement("div");
  const gradClass = turma.graduated ? " graduated" : "";
  const srcClass = turma.source === "agenda2026" ? " source-agenda" : "";
  el.className = `turma-row${gradClass}${srcClass}`;
  el.innerHTML = `
    <div class="turma-head">
      <span class="turma-grade">${escapeHtml(gradeId)}</span>
      <span class="turma-label" contenteditable="true" data-id="${turma.id}">${escapeHtml(turma.label)}</span>
      <button class="turma-delete" data-id="${turma.id}" title="Remover">×</button>
    </div>
    <div class="turma-mod-display">
      <span class="cur-label">MÓDULO</span>
      <span class="cur-val${turma.graduated ? " grad" : ""}">${turma.graduated ? "FORMADA" : turma.current_module}</span>
    </div>
    <div class="turma-start">
      <span class="lbl">início:</span>
      <input type="number" class="turma-year" data-id="${turma.id}" value="${turma.start_year}" min="2015" max="2035" step="1" />
      <select class="turma-bim" data-id="${turma.id}">
        ${[1, 2, 3, 4].map((n) => `<option value="${n}" ${turma.start_bim === n ? "selected" : ""}>${n}º bim</option>`).join("")}
      </select>
    </div>
  `;
  const patchStart = async () => {
    const y = parseInt(el.querySelector(".turma-year").value, 10);
    const b = parseInt(el.querySelector(".turma-bim").value, 10);
    if (isNaN(y) || isNaN(b)) return;
    await fetchJSON(`/api/turmas/${turma.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_year: y, start_bim: b }),
    });
    await refreshTurmasOnly();
    refreshCanonicals();
  };
  el.querySelector(".turma-year").addEventListener("change", patchStart);
  el.querySelector(".turma-bim").addEventListener("change", patchStart);
  el.querySelector(".turma-delete").addEventListener("click", async () => {
    if (!confirm(`Remover turma "${turma.label}" (${gradeId})?`)) return;
    await fetchJSON(`/api/turmas/${turma.id}`, { method: "DELETE" });
    await loadAll();
  });
  const lbl = el.querySelector(".turma-label");
  lbl.addEventListener("blur", async () => {
    const newLabel = lbl.textContent.trim();
    if (newLabel && newLabel !== turma.label) {
      await fetchJSON(`/api/turmas/${turma.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: newLabel }),
      });
      turma.label = newLabel;
      refreshCanonicals();
    } else {
      lbl.textContent = turma.label;
    }
  });
  lbl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); lbl.blur(); }
  });
  return el;
}

function renderResults() {
  const results = $("#results");
  const emptyHint = $("#empty-hint");
  const q = state.query.trim();
  if (!q) {
    results.innerHTML = "";
    emptyHint.style.display = "block";
    return;
  }
  emptyHint.style.display = "none";
  const matches = state.canonicals
    .map((c) => ({ ...c, _score: scoreMatch(q, c.canonical) }))
    .filter((c) => c._score > 0 || fuzzyMatch(q, c.canonical))
    .sort((a, b) => b._score - a._score)
    .slice(0, 40);
  if (matches.length === 0) {
    results.innerHTML = `<div class="empty-hint"><p>Nenhuma disciplina bate com <b>"${escapeHtml(q)}"</b>.</p></div>`;
    return;
  }
  results.innerHTML = matches.map(cardHTML).join("");
  results.querySelectorAll(".card").forEach((el) => {
    el.addEventListener("click", (e) => {
      // Ignore clicks on the add-cart button
      if (e.target.closest("[data-action=add-cart]")) return;
      openDetail(el.dataset.canonical);
    });
  });
  results.querySelectorAll("[data-action=add-cart]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const c = btn.dataset.canonical;
      if (cartHas(c)) cartRemove(c);
      else cartAdd(c);
    });
  });
}

function cardHTML(item) {
  const badge = item.grade_count === 1
    ? `<span class="card-badge exclusive">Exclusiva · ${item.offerings[0].grade_id}</span>`
    : `<span class="card-badge">${item.grade_count} grades</span>`;
  const inCart = cartHas(item.canonical);
  const btnLabel = inCart ? "✓ no carrinho" : "+ carrinho";
  const btnClass = inCart ? "add-cart-btn in-cart" : "add-cart-btn";
  const offerings = item.offerings.map(offeringHTML).join("");
  return `
    <div class="card" data-canonical="${escapeAttr(item.canonical)}">
      <div class="card-head">
        <h3 class="card-title">${escapeHtml(item.canonical)}</h3>
        <div style="display:flex;gap:6px;align-items:center;">
          ${badge}
          <button class="${btnClass}" data-canonical="${escapeAttr(item.canonical)}" data-action="add-cart">${btnLabel}</button>
        </div>
      </div>
      <div class="offerings">${offerings}</div>
    </div>
  `;
}

function offeringHTML(o) {
  let cls = "offering";
  const chips = (o.turma_deltas || []).map((td) => {
    const d = td.delta;
    let cc = "turma-delta-chip";
    let val = "?";
    if (d === null || d === undefined) val = "?";
    else if (d === 0) { cc += " zero now"; val = "agora"; }
    else if (d > 0) { cc += " positive"; if (d <= 2) cc += " next"; val = `+${d}`; }
    else { cc += " negative"; val = `${d}`; }
    return `<span class="${cc}"><span class="lbl">${escapeHtml(td.label)}</span><span class="val">${val}</span></span>`;
  }).join("");
  if (o.turma_deltas && o.turma_deltas.length) {
    const deltas = o.turma_deltas.map((td) => td.delta).filter((d) => d !== null && d !== undefined);
    if (deltas.some((d) => d === 0)) cls += " now";
    else if (deltas.some((d) => d > 0 && d <= 2)) cls += " next";
    else if (deltas.length && deltas.every((d) => d < 0)) cls += " past";
  }
  return `
    <div class="${cls}">
      <div class="offering-line1">
        <span>${o.grade_id}</span>
        <span>M${escapeHtml(String(o.modulo))}</span>
      </div>
      <div class="offering-line2">
        <span class="mono">${escapeHtml(o.codigo)}</span>
      </div>
      ${chips ? `<div class="turma-deltas">${chips}</div>` : ""}
    </div>
  `;
}

function openDetail(canonicalName) {
  const item = state.canonicals.find((c) => c.canonical === canonicalName);
  if (!item) return;
  const modal = $("#detail-modal");
  const content = $("#modal-content");
  content.innerHTML = `
    <h1>${escapeHtml(item.canonical)}</h1>
    <div class="modal-meta">${item.offerings.length} oferta(s) · ${item.grade_count} grade(s)</div>
    <div class="modal-section-label">Ementa</div>
    <div class="modal-ementa">${item.ementa_sample ? escapeHtml(item.ementa_sample) : "<em style='color:var(--text-muted)'>Indisponível.</em>"}</div>
    <div class="modal-section-label">Ofertas por grade</div>
    <div class="modal-equiv">
      ${item.offerings.map(offeringDetailHTML).join("")}
    </div>
  `;
  modal.classList.remove("hidden");
}

function offeringDetailHTML(o) {
  const total = Math.round(o.ch_total || 0);
  const teo = Math.round(o.ch_teo || 0);
  const pra = Math.round(o.ch_pra || 0);
  const ext = Math.round(o.ch_ext || 0);
  const chips = (o.turma_deltas || []).map((td) => {
    const d = td.delta;
    let cc = "turma-delta-chip";
    let val = "?";
    if (d === null || d === undefined) val = "?";
    else if (d === 0) { cc += " zero now"; val = "agora"; }
    else if (d > 0) { cc += " positive"; if (d <= 2) cc += " next"; val = `+${d} bim`; }
    else { cc += " negative"; val = `${d} bim`; }
    return `<span class="${cc}"><span class="lbl">${escapeHtml(td.label)}</span><span class="val">${val}</span></span>`;
  }).join("");
  return `
    <div class="offering">
      <div class="offering-line1">
        <span>${o.grade_id}</span>
        <span>M${escapeHtml(String(o.modulo))}</span>
      </div>
      <div class="offering-line2">
        <span class="mono">${escapeHtml(o.codigo)}</span>
      </div>
      <div class="ch-badges">
        <span class="ch total">${total}h</span>
        ${teo ? `<span class="ch">T ${teo}</span>` : ""}
        ${pra ? `<span class="ch">P ${pra}</span>` : ""}
        ${ext ? `<span class="ch">E ${ext}</span>` : ""}
      </div>
      ${chips ? `<div class="turma-deltas">${chips}</div>` : ""}
    </div>
  `;
}

function renderTimeline() {
  const head = $("#timeline-head");
  const body = $("#timeline-body");
  let maxMod = 0;
  const hasIntro = state.grades.some((g) => g.modules.includes("Introdutório"));
  state.grades.forEach((g) => {
    g.modules.forEach((m) => {
      const n = parseInt(m, 10);
      if (!isNaN(n) && n > maxMod) maxMod = n;
    });
  });
  const cols = [];
  if (hasIntro) cols.push("Introdutório");
  for (let i = 1; i <= maxMod; i++) cols.push(String(i));
  head.innerHTML =
    `<th class="corner">Grade</th>` +
    cols.map((c) => `<th>${c === "Introdutório" ? "Intro" : "M" + c}</th>`).join("");

  const map = {};
  state.canonicals.forEach((item) => {
    item.offerings.forEach((o) => {
      (map[o.grade_id] ||= {});
      (map[o.grade_id][String(o.modulo)] ||= []).push({ canonical: item.canonical, codigo: o.codigo });
    });
  });

  const turmasByGrade = {};
  state.turmas.forEach((t) => {
    if (t.graduated) return;
    (turmasByGrade[t.grade_id] ||= []).push(t);
  });

  const q = state.query.trim();
  body.innerHTML = state.grades.map((g) => {
    const gradeTurmas = turmasByGrade[g.id] || [];
    const cells = cols.map((c) => {
      const list = (map[g.id] && map[g.id][c]) || [];
      const currentTurmas = gradeTurmas.filter((t) => String(t.current_module) === c);
      const cellClass = currentTurmas.length ? " current-cell" : "";
      const tags = currentTurmas.map((t) => `<span class="turma-tag" title="${escapeAttr(t.label)}">${escapeHtml(shortLabel(t.label))}</span>`).join("");
      const inner = list.map((d) => {
        const cls = q && fuzzyMatch(q, d.canonical) ? "disc match" : "disc";
        return `<div class="${cls}" data-canonical="${escapeAttr(d.canonical)}" title="${escapeAttr(d.codigo)}">${escapeHtml(d.canonical)}</div>`;
      }).join("");
      return `<td class="${cellClass}">${inner}${tags ? `<div>${tags}</div>` : ""}</td>`;
    }).join("");
    return `<tr><td class="grade-cell">${g.id}</td>${cells}</tr>`;
  }).join("");

  body.querySelectorAll(".disc").forEach((el) => {
    el.addEventListener("click", () => openDetail(el.dataset.canonical));
  });
}

// ============ Carrinho ============

function renderCartModal() {
  const modal = $("#cart-modal");
  const items = state.cart.items;
  $("#cart-count-modal").textContent = items.length;

  // Populate turma selector
  const turmaSel = $("#cart-target-turma");
  const activeTurmas = state.turmas.filter((t) => !t.graduated);
  turmaSel.innerHTML = `<option value="">— selecione a turma do aluno —</option>` +
    activeTurmas.map((t) => `<option value="${t.id}" ${state.cart.targetTurmaId === t.id ? "selected" : ""}>${escapeHtml(t.grade_id)} · ${escapeHtml(t.label)} (M${t.current_module})</option>`).join("");

  $("#cart-student-name").value = state.cart.studentName || "";

  const target = activeTurmas.find((t) => t.id === state.cart.targetTurmaId);
  const container = $("#cart-items");
  if (items.length === 0) {
    container.innerHTML = `<div class="cart-empty">Carrinho vazio. Clique <b>+ carrinho</b> nos resultados de busca.</div>`;
    $("#cart-email").value = "";
    return;
  }

  container.innerHTML = items.map((it) => cartItemHTML(it, target)).join("");
  container.querySelectorAll("[data-action=cart-remove]").forEach((btn) => {
    btn.addEventListener("click", () => cartRemove(btn.dataset.canonical));
  });

  $("#cart-email").value = generateEmail(items, target);
}

function cartItemHTML(item, target) {
  const canonical = state.canonicals.find((c) => c.canonical === item.canonical);
  if (!canonical) {
    return `<div class="cart-item"><div class="cart-item-info"><div class="cart-item-name">${escapeHtml(item.canonical)}</div><div class="cart-item-meta">disciplina não encontrada</div></div><button class="cart-item-remove" data-action="cart-remove" data-canonical="${escapeAttr(item.canonical)}">×</button></div>`;
  }
  // Find offering in target turma's grade (if any)
  let meta = `${canonical.grade_count} grade(s)`;
  if (target) {
    const off = canonical.offerings.find((o) => o.grade_id === target.grade_id);
    if (off) {
      const td = (off.turma_deltas || []).find((td) => td.turma_id === target.id);
      const delta = td ? td.delta : null;
      const deltaLabel = deltaHumanized(delta);
      meta = `${off.grade_id} · M${off.modulo} · ${deltaLabel}`;
    } else {
      meta = `NÃO ofertada em ${target.grade_id}`;
    }
  }
  return `
    <div class="cart-item">
      <div class="cart-item-info">
        <div class="cart-item-name">${escapeHtml(item.canonical)}</div>
        <div class="cart-item-meta">${escapeHtml(meta)}</div>
      </div>
      <button class="cart-item-remove" data-action="cart-remove" data-canonical="${escapeAttr(item.canonical)}" title="Remover">×</button>
    </div>
  `;
}

function deltaHumanized(delta) {
  if (delta === null || delta === undefined) return "—";
  if (delta === 0) return "cursando agora";
  if (delta === 1) return "próximo bimestre (+1)";
  if (delta > 1) return `+${delta} bimestres`;
  if (delta === -1) return "bimestre anterior (-1)";
  return `${delta} bimestres (já passou)`;
}

function futureBim(currentBim, deltaBim) {
  const idx = currentBim.year * 4 + (currentBim.bim - 1) + deltaBim;
  const y = Math.floor(idx / 4);
  const b = (idx % 4) + 1;
  const cal = state.calendar[`${y}-${b}`] || null;
  return { year: y, bim: b, months: BIM_MONTHS[b], cal };
}

function fmtBR(isoDate) {
  if (!isoDate) return "?";
  const m = isoDate.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : isoDate;
}

function bestFutureOffering(canonical) {
  // All active turmas with positive delta; group by min delta so multiple grades appear.
  const options = [];
  for (const o of canonical.offerings) {
    for (const td of o.turma_deltas || []) {
      if (td.delta !== null && td.delta !== undefined && td.delta > 0) {
        options.push({
          delta: td.delta,
          turmaLabel: td.label,
          gradeId: o.grade_id,
          module: o.modulo,
        });
      }
    }
  }
  if (!options.length) return null;
  const minDelta = Math.min(...options.map((o) => o.delta));
  return { delta: minDelta, options: options.filter((o) => o.delta === minDelta) };
}

function projectedNewTurma(canonical, cur) {
  const mods = canonical.offerings.map((o) => o.modulo).filter((m) => typeof m === "number");
  if (!mods.length) return null;
  const minMod = Math.min(...mods);
  const grades = canonical.offerings.filter((o) => o.modulo === minMod).map((o) => o.grade_id);
  const idx = (cur.year + 1) * 4 + 0 + (minMod - 1);
  const y = Math.floor(idx / 4);
  const b = (idx % 4) + 1;
  return {
    year: y,
    bim: b,
    module: minMod,
    grades,
    cal: state.calendar[`${y}-${b}`] || null,
  };
}

const BIM_ORDINAL = { 1: "primeiro", 2: "segundo", 3: "terceiro", 4: "quarto" };
const MESES = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

function condenseGrades(gradeIds) {
  // Keep only latest version per course prefix (ADS 5000 > ADS 4000).
  const byPrefix = {};
  gradeIds.forEach((g) => {
    const m = g.match(/^([A-Z]+)\s+(\d+)/);
    if (!m) return;
    const [_, prefix, ver] = m;
    const n = parseInt(ver, 10);
    if (!byPrefix[prefix] || n > byPrefix[prefix].n) byPrefix[prefix] = { g, n };
  });
  return Object.values(byPrefix).map((x) => x.g);
}

function dayApprox(iso) {
  if (!iso) return "";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso;
  const day = parseInt(m[3], 10);
  const monthName = MESES[parseInt(m[2], 10) - 1] || "";
  const part = day <= 10 ? "no começo" : day <= 20 ? "em meados" : "no final";
  return `${part} de ${monthName}`;
}

function generateEmail(items, target) {
  const student = state.cart.studentName.trim();
  const greet = student ? `Olá ${student},` : "Olá,";
  const cur = state.currentBim;
  const lines = [greet, "", "Segue a resposta sobre as disciplinas consultadas:"];

  if (target) {
    lines.push(
      `(Grade de referência: ${target.grade_id} · ${target.label} · módulo atual ${target.current_module}, bimestre ${cur.year}-${cur.bim})`
    );
  }
  lines.push("");

  items.forEach((it) => {
    const canonical = state.canonicals.find((c) => c.canonical === it.canonical);
    if (!canonical) {
      lines.push(`• ${it.canonical}`);
      lines.push(`  - Não encontrada nas grades atuais.`);
      lines.push("");
      return;
    }
    lines.push(`• ${canonical.canonical}`);

    const off = target ? canonical.offerings.find((o) => o.grade_id === target.grade_id) : null;
    const myDelta = (() => {
      if (!off || !target) return null;
      const td = (off.turma_deltas || []).find((t) => t.turma_id === target.id);
      return td ? td.delta : null;
    })();

    if (off && myDelta === 0) {
      lines.push(`  - Você está cursando agora mesmo, no ${BIM_ORDINAL[cur.bim]} bimestre de ${cur.year}, na sua própria grade.`);
    } else if (off && typeof myDelta === "number" && myDelta > 0) {
      const fb = futureBim(cur, myDelta);
      lines.push(
        `  - Próxima oferta pra você será aproximadamente em: ${fb.year} no ${BIM_ORDINAL[fb.bim]} bimestre, em sua própria grade — somente esperar.`
      );
      if (fb.cal && fb.cal.limite_inclusao) {
        lines.push(
          `  - Prazo máximo de inclusão: ${dayApprox(fb.cal.limite_inclusao)} (${fmtBR(fb.cal.limite_inclusao)}).`
        );
      }
    } else {
      // Not in student's grade OR already passed → find next in any active turma
      const best = bestFutureOffering(canonical);
      if (best) {
        const fb = futureBim(cur, best.delta);
        lines.push(
          `  - Próxima oferta pra você será aproximadamente em: ${fb.year} no ${BIM_ORDINAL[fb.bim]} bimestre.`
        );
        if (fb.cal && fb.cal.limite_inclusao) {
          lines.push(
            `  - Prazo máximo de inclusão: ${dayApprox(fb.cal.limite_inclusao)} (${fmtBR(fb.cal.limite_inclusao)}).`
          );
        }
        const alts = best.options
          .map((o) => `${o.gradeId} (${o.turmaLabel}, módulo ${o.module})`)
          .join(" / ou ");
        lines.push(`    Via: ${alts}.`);
      } else {
        const proj = projectedNewTurma(canonical, cur);
        if (proj) {
          lines.push(
            `  - Próxima oferta pra você será aproximadamente em: ${proj.year} no ${BIM_ORDINAL[proj.bim]} bimestre.`
          );
          if (proj.cal && proj.cal.limite_inclusao) {
            lines.push(
              `  - Prazo máximo de inclusão: ${dayApprox(proj.cal.limite_inclusao)} (${fmtBR(proj.cal.limite_inclusao)}).`
            );
          }
          lines.push(
            `    Via turma ingressante em ${proj.year}, nas grades: ${proj.grades.join(" / ou ")}.`
          );
        } else {
          lines.push(`  - Sem previsão de oferta com as turmas atuais.`);
        }
      }
    }

    if (canonical.grade_count === 1) {
      lines.push(`  - Exclusiva da grade ${canonical.offerings[0].grade_id}.`);
    }
    lines.push("");
  });

  lines.push("Qualquer dúvida, estou à disposição.");
  lines.push("");
  lines.push("Att,");
  lines.push("Prof. Eron");
  return lines.join("\n");
}

function shortLabel(l) {
  const m = l.match(/(\d{4})/);
  return m ? `T${m[1].slice(2)}` : l.slice(0, 4);
}

function showToast(msg, type = "success") {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = `toast toast-${type} show`;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.remove("show"), 3000);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

// ============ event wiring ============
document.addEventListener("DOMContentLoaded", async () => {
  await loadAll();
  $("#loading").classList.add("hidden");

  const searchInput = $("#search");
  searchInput.addEventListener("input", (e) => {
    state.query = e.target.value;
    renderResults();
    renderTimeline();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== searchInput && !e.target.matches("input,textarea,[contenteditable]")) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
    if (e.key === "Escape") {
      $("#detail-modal").classList.add("hidden");
      $("#turma-modal").classList.add("hidden");
      $("#cart-modal").classList.add("hidden");
      if (document.activeElement === searchInput) {
        searchInput.value = "";
        state.query = "";
        renderResults();
        renderTimeline();
      }
    }
  });

  // Bimestre global config
  const saveBim = async () => {
    const y = parseInt($("#bim-year").value, 10);
    const b = parseInt($("#bim-num").value, 10);
    if (isNaN(y) || isNaN(b)) return;
    await fetchJSON("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_bimestre: { year: y, bim: b } }),
    });
    await loadAll();
  };
  $("#bim-year").addEventListener("change", saveBim);
  $("#bim-num").addEventListener("change", saveBim);

  $$(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      $$(".tab").forEach((x) => x.classList.remove("active"));
      $$(".view").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      state.view = t.dataset.view;
      $(`#view-${state.view}`).classList.add("active");
    });
  });

  $("#reload-btn").addEventListener("click", async () => {
    const btn = $("#reload-btn");
    btn.textContent = "carregando…";
    await fetchJSON("/api/reload", { method: "POST" });
    await loadAll();
    btn.textContent = "↻ Recarregar grades";
  });

  $("#modal-close").addEventListener("click", () => $("#detail-modal").classList.add("hidden"));
  $("#detail-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) $("#detail-modal").classList.add("hidden");
  });

  // Cart wiring
  refreshCartUI();
  $("#cart-btn").addEventListener("click", () => {
    renderCartModal();
    $("#cart-modal").classList.remove("hidden");
  });
  $("#cart-modal-close").addEventListener("click", () => $("#cart-modal").classList.add("hidden"));
  $("#cart-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) $("#cart-modal").classList.add("hidden");
  });
  $("#cart-target-turma").addEventListener("change", (e) => {
    state.cart.targetTurmaId = e.target.value || null;
    saveCart();
    renderCartModal();
  });
  $("#cart-student-name").addEventListener("input", (e) => {
    state.cart.studentName = e.target.value;
    saveCart();
    $("#cart-email").value = generateEmail(state.cart.items, state.turmas.find((t) => t.id === state.cart.targetTurmaId));
  });
  $("#cart-clear").addEventListener("click", () => {
    if (state.cart.items.length && !confirm("Limpar todo o carrinho?")) return;
    cartClear();
  });
  $("#cart-copy").addEventListener("click", async () => {
    const txt = $("#cart-email").value;
    try {
      await navigator.clipboard.writeText(txt);
      const btn = $("#cart-copy");
      const old = btn.textContent;
      btn.textContent = "✓ Copiado!";
      setTimeout(() => { btn.textContent = old; }, 1500);
    } catch (err) {
      alert("Falha ao copiar. Selecione o texto manualmente.");
    }
  });

  // Turma modal
  const tmodal = $("#turma-modal");
  const gradeSel = $("#turma-form-grade");
  const yearInp = $("#turma-form-year");
  const bimSel = $("#turma-form-bim");
  const labelInp = $("#turma-form-label");
  const preview = $("#turma-form-preview");

  function refreshPreview() {
    const y = parseInt(yearInp.value, 10);
    const b = parseInt(bimSel.value, 10);
    if (isNaN(y) || isNaN(b)) { preview.textContent = "..."; return; }
    const mod = bimIndex(state.currentBim.year, state.currentBim.bim) - bimIndex(y, b) + 1;
    preview.textContent = `Módulo atual será: ${mod > 0 ? mod : "(ainda não começou)"}`;
  }

  function refreshGradeOptions() {
    gradeSel.innerHTML = state.grades.map((g) => `<option value="${g.id}">${g.id} — ${g.nome_completo.slice(0, 40)}</option>`).join("");
  }

  yearInp.addEventListener("input", refreshPreview);
  bimSel.addEventListener("change", refreshPreview);

  $("#add-turma-btn").addEventListener("click", () => {
    refreshGradeOptions();
    labelInp.value = "";
    yearInp.value = state.currentBim.year;
    bimSel.value = state.currentBim.bim;
    refreshPreview();
    tmodal.classList.remove("hidden");
    setTimeout(() => labelInp.focus(), 50);
  });
  $("#turma-modal-close").addEventListener("click", () => tmodal.classList.add("hidden"));
  $("#turma-form-cancel").addEventListener("click", () => tmodal.classList.add("hidden"));
  tmodal.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) tmodal.classList.add("hidden");
  });
  $("#turma-form-save").addEventListener("click", async () => {
    const btn = $("#turma-form-save");
    if (btn.disabled) return;
    const payload = {
      grade_id: gradeSel.value,
      label: labelInp.value.trim() || `Turma ${yearInp.value}`,
      start_year: parseInt(yearInp.value, 10),
      start_bim: parseInt(bimSel.value, 10),
    };
    if (!payload.grade_id || isNaN(payload.start_year) || isNaN(payload.start_bim)) {
      alert("Preencha grade + ano + bimestre.");
      return;
    }
    const oldTxt = btn.textContent;
    btn.disabled = true;
    btn.textContent = "salvando…";
    try {
      const resp = await fetchJSON("/api/turmas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      console.log("[turma criada]", resp.turma);
      tmodal.classList.add("hidden");
      await refreshTurmasOnly();
      refreshCanonicals();
      showToast(`✓ Turma "${resp.turma.label}" adicionada em ${resp.turma.grade_id}`);
    } catch (err) {
      console.error("[erro criar turma]", err);
      alert(`Erro ao adicionar turma: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = oldTxt;
    }
  });
});
