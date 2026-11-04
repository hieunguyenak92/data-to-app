"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const columns = ["sku", "name", "category", "stock", "reorder_level", "notes"];
  const state = { data: null, index: 0, search: "", missing: false };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function display(value) {
    if (value === null || value === undefined || value === "") return "—";
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  }

  function number(value) {
    return Number.isFinite(Number(value)) ? Number(value).toLocaleString() : "—";
  }

  function currentStep() { return state.data.steps[state.index]; }

  function hasOverride(row, field) {
    return Array.isArray(row.overrides) ? row.overrides.includes(field) : Object.prototype.hasOwnProperty.call(row.overrides || {}, field);
  }

  function hasEdits(row) {
    return Array.isArray(row.overrides) ? row.overrides.length > 0 : Object.keys(row.overrides || {}).length > 0;
  }

  function stepName(step) { return step.title || step.id || "Workspace state"; }

  function renderNavigation() {
    const container = $("state-navigation");
    container.replaceChildren();
    state.data.steps.forEach((step, index) => {
      const button = el("button", "step-button");
      button.type = "button";
      button.classList.toggle("active", index === state.index);
      button.setAttribute("aria-pressed", String(index === state.index));
      button.append(el("span", "step-index", String(index + 1).padStart(2, "0")), el("span", "step-name", stepName(step)));
      button.addEventListener("click", () => chooseStep(index));
      container.append(button);
    });
  }

  function renderHero() {
    const incoming = state.data.steps.find((step) => (step.conflicts || []).some((conflict) => conflict.field === "reorder_level"));
    const conflict = incoming?.conflicts.find((item) => item.field === "reorder_level");
    if (!conflict) return;
    $("hero-source").textContent = display(conflict.base);
    $("hero-local").textContent = display(conflict.local);
    $("hero-incoming").textContent = display(conflict.incoming);
    const identity = conflict.key_values && Object.entries(conflict.key_values).map(([key, value]) => `${key.toUpperCase()} ${display(value)}`).join(" · ");
    $("hero-record").textContent = identity || "Synthetic inventory record";
    $("hero-field").textContent = "reorder_level · three-way comparison";
  }

  function renderComparison(step) {
    const panel = $("comparison-panel");
    panel.replaceChildren();
    const conflict = (step.conflicts || []).find((item) => item.field === "reorder_level") || step.conflicts?.[0];
    panel.hidden = !conflict;
    if (!conflict) return;
    const heading = el("div", "comparison-heading");
    const identity = conflict.key_values ? Object.entries(conflict.key_values).map(([key, value]) => `${key.toUpperCase()} ${display(value)}`).join(" · ") : `Record ${String(conflict.row_id).slice(0, 10)}`;
    heading.append(el("strong", "", "A change that needs your decision"), el("span", "", identity));
    panel.append(heading);
    const values = el("div", "comparison-values");
    for (const [key, caption, className] of [["base", "Previous source", ""], ["local", "Your local edit", "comparison-local"], ["incoming", "Incoming source", ""]]) {
      const card = el("div", className);
      card.append(el("span", "", caption), el("strong", "", display(conflict[key])));
      values.append(card);
    }
    panel.append(values);
    const footer = el("div", "comparison-footer");
    footer.append(el("p", "", "The current workspace value is still your local edit."));
    const button = el("button", "", "See the resolved state →");
    button.type = "button";
    button.addEventListener("click", () => chooseStep(state.data.steps.length - 1));
    footer.append(button); panel.append(footer);
  }

  function renderImportNote(step) {
    const node = $("import-note");
    const counts = step.preview?.counts;
    node.hidden = !counts;
    if (!counts) { node.textContent = ""; return; }
    const parts = [];
    for (const [key, caption] of [["new", "new"], ["updated", "updated"], ["missing", "marked missing"], ["conflicts", "conflicts"]]) {
      if (counts[key] !== undefined) parts.push(`${number(counts[key])} ${key === "conflicts" && Number(counts[key]) === 1 ? "conflict" : caption}`);
    }
    node.textContent = `Snapshot preview: ${parts.join(" · ")}. Missing records remain available through the toggle below.`;
  }

  function renderRows() {
    if (!state.data) return;
    const step = currentStep();
    const rows = step.rows.filter((row) => state.missing || !row.missing);
    const needle = state.search.trim().toLocaleLowerCase();
    const filtered = rows.filter((row) => !needle || Object.values(row.values || {}).some((value) => String(value).toLocaleLowerCase().includes(needle)));
    const body = $("products-body");
    body.replaceChildren();
    const conflictRows = new Set((step.conflicts || []).map((conflict) => conflict.row_id));
    for (const row of filtered) {
      const tr = el("tr", row.missing ? "is-missing" : "");
      for (const column of columns) {
        const td = el("td", column === "sku" ? "key-cell" : "");
        const span = el("span", hasOverride(row, column) ? "local-cell" : "", display(row.values[column]));
        if (row.values[column] === "" || row.values[column] === null || row.values[column] === undefined) span.classList.add("null-value");
        span.title = hasOverride(row, column) ? `Local value. Source: ${display(row.source?.[column])}` : display(row.values[column]);
        td.append(span); tr.append(td);
      }
      const status = el("td");
      if (row.missing) status.append(el("span", "record-badge missing", "Missing"));
      else if (conflictRows.has(row.id)) status.append(el("span", "record-badge needs-review", "Review"));
      else if (hasEdits(row)) status.append(el("span", "record-badge", "Local edit"));
      else status.append(el("span", "source-label", "Source"));
      tr.append(status); body.append(tr);
    }
    $("products-count").textContent = number(rows.length);
    $("visible-products").textContent = `Showing ${number(filtered.length)} of ${number(rows.length)} ${state.missing ? "retained" : "active"} products`;
    $("empty-products").hidden = filtered.length > 0;
    $("products-table").hidden = filtered.length === 0;
  }

  function renderStep(announce) {
    const step = currentStep();
    renderNavigation();
    $("state-eyebrow").textContent = `State ${String(state.index + 1).padStart(2, "0")} / ${String(state.data.steps.length).padStart(2, "0")}`;
    $("state-title").textContent = stepName(step);
    $("state-description").textContent = step.description || "Explore the generated workspace state below.";
    $("metric-records").textContent = number(step.summary.active_rows);
    $("metric-edits").textContent = number(step.summary.local_edits);
    $("metric-conflicts").textContent = number(step.summary.conflicts);
    $("metric-imports").textContent = number(step.summary.imports);
    $("conflict-metric").classList.toggle("has-conflicts", Number(step.summary.conflicts) > 0);
    $("preview-version").textContent = `v${state.data.version} · rev ${step.summary.revision ?? "—"}`;
    $("state-position").textContent = `Step ${state.index + 1} of ${state.data.steps.length} · Generated by the data engine`;
    $("previous-state").disabled = state.index === 0;
    $("next-state").disabled = state.index >= state.data.steps.length - 1;
    $("export-state").disabled = typeof step.csv !== "string";
    renderComparison(step); renderImportNote(step); renderRows();
    if (announce) $("step-announcement").textContent = `Step ${state.index + 1}: ${stepName(step)}. ${step.description || ""}`;
  }

  function chooseStep(index) {
    if (!state.data || index < 0 || index >= state.data.steps.length) return;
    state.index = index;
    renderStep(true);
  }

  async function loadDemo() {
    $("retry-preview").disabled = true;
    $("preview-error").hidden = true;
    $("workspace-preview").setAttribute("aria-busy", "true");
    try {
      const response = await fetch(new URL("demo/states.json", document.baseURI), { cache: "no-cache" });
      if (!response.ok) throw new Error(`Preview data returned HTTP ${response.status}.`);
      const data = await response.json();
      if (!Array.isArray(data.steps) || !data.steps.length || data.steps.some((step) => !step.summary || !Array.isArray(step.rows))) throw new Error("The preview state file is incomplete.");
      state.data = data; state.index = Math.min(state.index, data.steps.length - 1);
      renderHero(); renderStep(false);
    } catch (error) {
      $("preview-error-message").textContent = `${error.message} Reload the page or use the local quickstart below.`;
      $("preview-error").hidden = false;
      $("state-title").textContent = "Preview temporarily unavailable";
      $("state-description").textContent = "The local application can still be built with the quickstart below.";
    } finally {
      $("retry-preview").disabled = false;
      $("workspace-preview").setAttribute("aria-busy", "false");
    }
  }

  function exportState() {
    if (!state.data || typeof currentStep().csv !== "string") return;
    const step = currentStep();
    const blob = new Blob(["\ufeff", step.csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = el("a");
    const slug = String(step.id || state.index + 1).replace(/[^a-z0-9_-]/gi, "-");
    anchor.href = url; anchor.download = `data-to-app-synthetic-${slug}.csv`;
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }

  async function copyCommands() {
    const text = $("quickstart-command").textContent;
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text);
      $("copy-command").textContent = "Copied";
      $("copy-status").textContent = "Commands copied. Run them in your terminal to create the synthetic workspace.";
    } catch (_) {
      const range = document.createRange();
      range.selectNodeContents($("quickstart-command"));
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      $("copy-status").textContent = "Commands selected. Use your keyboard's copy shortcut, then paste into your terminal.";
    }
  }

  $("previous-state").addEventListener("click", () => chooseStep(state.index - 1));
  $("next-state").addEventListener("click", () => chooseStep(state.index + 1));
  $("export-state").addEventListener("click", exportState);
  $("retry-preview").addEventListener("click", loadDemo);
  $("search-products").addEventListener("input", () => { state.search = $("search-products").value; renderRows(); });
  $("include-missing").addEventListener("change", () => { state.missing = $("include-missing").checked; renderRows(); });
  $("clear-search").addEventListener("click", () => { state.search = ""; $("search-products").value = ""; renderRows(); });
  $("copy-command").addEventListener("click", copyCommands);
  loadDemo();
})();
