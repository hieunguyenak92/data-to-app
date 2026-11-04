"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    bootstrap: null, table: null, section: "records", view: "", search: "", missing: false,
    offset: 0, limit: 50, total: 0, rows: [], revision: 0, requestId: 0,
    rowsController: null, retry: null, edit: null, importPreview: null,
    modalBusy: false, returnFocus: null, toastTimer: null,
  };

  class ApiError extends Error {
    constructor(message, status, code) { super(message); this.status = status; this.code = code; }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function label(value) {
    return String(value).replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function display(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function number(value) {
    return Number.isFinite(Number(value)) ? Number(value).toLocaleString() : "—";
  }

  function currentTable() {
    return state.bootstrap?.tables.find((table) => table.id === state.table);
  }

  function tableLabel(id) {
    const table = state.bootstrap?.tables.find((item) => item.id === id);
    return table?.label || label(id);
  }

  async function api(path, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.method && options.method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-DTA-Token"] = state.bootstrap?.csrf_token || "";
    }
    const response = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options, headers });
    let data;
    try { data = await response.json(); }
    catch (_) { throw new ApiError("The local runtime returned an unexpected response. Check that it is still running.", response.status, "invalid_response"); }
    if (!response.ok) throw new ApiError(data.message || data.error || "The request could not be completed.", response.status, data.error);
    return data;
  }

  function post(path, body) {
    return api(path, { method: "POST", body: JSON.stringify(body) });
  }

  function showError(error, retry = refreshWorkspace) {
    $("global-error-message").textContent = error.message || String(error);
    $("global-error").hidden = false;
    $("global-error-title").textContent = error.status === 409 ? "This workspace changed in the meantime" : "Something needs your attention";
    state.retry = retry;
    $("global-retry").hidden = !retry;
  }

  function clearError() { $("global-error").hidden = true; state.retry = null; }

  function toast(message) {
    clearTimeout(state.toastTimer);
    $("toast").textContent = message;
    $("toast").hidden = false;
    state.toastTimer = setTimeout(() => { $("toast").hidden = true; }, 5500);
  }

  function setModalBusy(busy) {
    state.modalBusy = busy;
    document.querySelectorAll(".app-dialog button,.app-dialog input,.app-dialog select,.app-dialog textarea").forEach((item) => { item.disabled = busy; });
  }

  function openDialog(id) {
    state.returnFocus = document.activeElement;
    $(id).showModal();
  }

  function closeDialog(id) {
    if (state.modalBusy) return;
    $(id).close();
    if (state.returnFocus?.isConnected) state.returnFocus.focus();
  }

  function renderSummary() {
    const summary = state.bootstrap.summary || {};
    $("metric-records").textContent = number(summary.active_rows);
    $("metric-edits").textContent = number(summary.local_edits);
    $("metric-conflicts").textContent = number(summary.conflicts);
    $("metric-imports").textContent = number(summary.imports);
    const count = Number(summary.conflicts) || 0;
    $("conflict-badge").textContent = number(count);
    $("conflict-badge").hidden = count === 0;
    $("metric-conflicts-button").classList.toggle("is-warning", count > 0);
    $("metric-conflict-description").textContent = count ? "Your local values are preserved" : "Everything is in step";
    $("runtime-version").textContent = `Runtime ${state.bootstrap.version || "local"}`;
    $("runtime-revision").textContent = `rev ${state.revision}`;
  }

  function renderNavigation() {
    const nav = $("table-navigation");
    nav.replaceChildren();
    for (const table of state.bootstrap.tables) {
      const button = el("button", "nav-item");
      button.type = "button";
      button.classList.toggle("active", state.section === "records" && state.table === table.id);
      if (state.section === "records" && state.table === table.id) button.setAttribute("aria-current", "page");
      const glyph = el("span", "nav-glyph", "▦"); glyph.setAttribute("aria-hidden", "true");
      button.append(glyph, el("span", "nav-item-label", table.label || label(table.id)));
      button.addEventListener("click", () => navigate("records", table.id));
      nav.append(button);
    }
    $("nav-conflicts").classList.toggle("active", state.section === "conflicts");
    $("nav-history").classList.toggle("active", state.section === "history");
    for (const [id, section] of [["nav-conflicts", "conflicts"], ["nav-history", "history"]]) {
      if (state.section === section) $(id).setAttribute("aria-current", "page"); else $(id).removeAttribute("aria-current");
    }
  }

  function renderViews() {
    const container = $("view-tabs");
    container.replaceChildren();
    const views = [{ id: "", label: "All records" }, ...(currentTable()?.views || [])];
    for (const view of views) {
      const button = el("button", "view-tab", view.label || label(view.id));
      button.type = "button";
      button.classList.toggle("active", state.view === view.id);
      button.setAttribute("aria-pressed", String(state.view === view.id));
      button.addEventListener("click", () => { state.view = view.id; state.offset = 0; renderViews(); loadRows(); });
      container.append(button);
    }
  }

  function renderSection() {
    for (const section of ["records", "conflicts", "history"]) $(section + "-section").hidden = state.section !== section;
    $("breadcrumb-current").textContent = state.section === "records" ? tableLabel(state.table) : state.section === "conflicts" ? "Review conflicts" : "Import history";
    $("export-button").disabled = !state.table;
    $("import-button").disabled = !state.bootstrap.tables.length;
    renderNavigation();
  }

  async function navigate(section, tableId = state.table) {
    state.section = section;
    if (tableId !== state.table) {
      state.table = tableId; state.view = ""; state.offset = 0; state.search = "";
      $("search-input").value = "";
    }
    $("app-frame").classList.remove("nav-open");
    $("menu-toggle").setAttribute("aria-expanded", "false");
    $("menu-toggle").setAttribute("aria-label", "Open navigation");
    renderSection();
    clearError();
    if (section === "records") { renderViews(); await loadRows(); }
    else if (section === "conflicts") await loadConflicts();
    else await loadHistory();
  }

  function editIcon() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15l-1 6Z");
    svg.append(path); return svg;
  }

  function renderRows(data) {
    const table = currentTable();
    const columns = table.columns.map((column) => typeof column === "string" ? column : column.name);
    const head = el("tr");
    for (const column of columns) { const th = el("th", "", label(column)); th.scope = "col"; head.append(th); }
    const stateHead = el("th", "", "State"); stateHead.scope = "col"; head.append(stateHead);
    const actionHead = el("th", "actions-cell", ""); actionHead.scope = "col"; actionHead.append(el("span", "sr-only", "Actions")); head.append(actionHead);
    $("records-head").replaceChildren(head);
    const body = $("records-body"); body.replaceChildren();
    for (const row of data.rows) {
      const tr = el("tr", row.missing ? "is-missing" : "");
      for (const column of columns) {
        const td = el("td", (table.key || []).includes(column) ? "key-cell" : "");
        const isLocal = Array.isArray(row.overrides) ? row.overrides.includes(column) : Object.prototype.hasOwnProperty.call(row.overrides || {}, column);
        const span = el("span", isLocal ? "cell-local" : "cell-value", display(row.values[column]));
        if (row.values[column] === "" || row.values[column] === null || row.values[column] === undefined) span.classList.add("null-value");
        if (isLocal) span.title = `Local edit. Source: ${display(row.source?.[column])}`;
        else span.title = display(row.values[column]);
        td.append(span); tr.append(td);
      }
      const stateCell = el("td");
      const hasEdits = Array.isArray(row.overrides) ? row.overrides.length > 0 : Object.keys(row.overrides || {}).length > 0;
      if (row.missing) stateCell.append(el("span", "record-state missing", "Missing"));
      else if (hasEdits) stateCell.append(el("span", "record-state", "Edited"));
      else stateCell.append(el("span", "muted", "Source"));
      tr.append(stateCell);
      const actions = el("td", "actions-cell");
      if ((table.editable || []).length && !row.missing) {
        const button = el("button", "row-edit"); button.type = "button";
        button.setAttribute("aria-label", `Edit ${recordIdentity(row, table)}`);
        button.title = "Edit record"; button.append(editIcon());
        button.addEventListener("click", () => openEditor(row)); actions.append(button);
      }
      tr.append(actions); body.append(tr);
    }
    state.rows = data.rows; state.total = data.total;
    if (data.revision !== undefined) state.revision = data.revision;
    $("table-title").textContent = table.label || label(table.id);
    $("collection-count").textContent = `${number(data.total)} ${data.total === 1 ? "record" : "records"}${state.search || state.view ? " in this view" : ""}`;
    $("records-empty").hidden = data.rows.length !== 0;
    $("records-table").hidden = data.rows.length === 0;
    $("table-context").textContent = (table.key || []).length ? `Identified by ${(table.key || []).map(label).join(" + ")}. Source values stay intact.` : "Your original values stay intact.";
    const start = data.total === 0 ? 0 : state.offset + 1;
    $("page-description").textContent = `${number(start)}–${number(Math.min(state.offset + data.rows.length, data.total))} of ${number(data.total)}`;
    $("previous-page").disabled = state.offset === 0;
    $("next-page").disabled = state.offset + data.rows.length >= data.total;
    $("runtime-revision").textContent = `rev ${state.revision}`;
  }

  async function loadRows() {
    if (!state.table) {
      $("records-loading").hidden = true; $("records-empty").hidden = false; $("records-table").hidden = true;
      $("collection-count").textContent = "No collections"; return;
    }
    state.rowsController?.abort();
    const controller = new AbortController(); state.rowsController = controller;
    const requestId = ++state.requestId;
    $("records-loading").hidden = false; $("table-region").setAttribute("aria-busy", "true");
    $("records-table").hidden = true; $("records-empty").hidden = true;
    const query = new URLSearchParams({ table: state.table, search: state.search, missing: state.missing ? "1" : "0", offset: String(state.offset), limit: String(state.limit) });
    if (state.view) query.set("view", state.view);
    try {
      const data = await api(`/api/rows?${query}`, { signal: controller.signal });
      if (requestId !== state.requestId || state.section !== "records") return;
      if (!data.rows.length && data.total > 0 && state.offset >= data.total) { state.offset = Math.floor((data.total - 1) / state.limit) * state.limit; await loadRows(); return; }
      renderRows(data); clearError();
    } catch (error) {
      if (error.name !== "AbortError" && requestId === state.requestId) showError(error, loadRows);
    } finally {
      if (requestId === state.requestId) { $("records-loading").hidden = true; $("table-region").setAttribute("aria-busy", "false"); }
    }
  }

  function recordIdentity(row, table = currentTable()) {
    const values = (table?.key || []).map((key) => `${label(key)} ${display(row.values[key])}`);
    return values.length ? values.join(" · ") : String(row.id).slice(0, 10);
  }

  function showDialogError(id, message) { $(id).textContent = message; $(id).hidden = false; }

  function renderEditFields(row, draft) {
    const fields = $("edit-fields"); fields.replaceChildren();
    const table = currentTable();
    for (const [index, column] of (table.editable || []).entries()) {
      const field = el("div", "field");
      const fieldLabel = el("label", "", label(column)); fieldLabel.htmlFor = `edit-field-${index}`;
      const current = draft && Object.prototype.hasOwnProperty.call(draft, column) ? draft[column] : String(row.values[column] ?? "");
      const input = el(column.toLowerCase().includes("note") || current.includes("\n") || current.length > 100 ? "textarea" : "input");
      if (input.tagName === "INPUT") input.type = "text";
      input.id = `edit-field-${index}`; input.name = column; input.value = current; input.maxLength = 65536;
      input.autocomplete = "off";
      const help = el("p", "source-value", `Source: ${display(row.source?.[column])}`); help.id = `edit-source-${index}`;
      input.setAttribute("aria-describedby", help.id);
      if (draft && current !== String(row.values[column] ?? "")) help.classList.add("is-changed");
      field.append(fieldLabel, input, help); fields.append(field);
    }
    $("edit-identity").textContent = recordIdentity(row, table);
  }

  function openEditor(row) {
    state.edit = { row, table: state.table, revision: state.revision };
    $("edit-error").hidden = true; $("reload-record").hidden = true;
    $("save-record").textContent = "Save local changes";
    renderEditFields(row); openDialog("edit-dialog");
    $("edit-fields").querySelector("input,textarea")?.focus();
  }

  function editDraft() {
    const values = {};
    for (const input of $("edit-fields").querySelectorAll("input,textarea")) values[input.name] = input.value;
    return values;
  }

  async function saveEditor(event) {
    event.preventDefault();
    if (state.modalBusy || !state.edit) return;
    const draft = editDraft();
    const changes = Object.fromEntries(Object.entries(draft).filter(([field, value]) => value !== String(state.edit.row.values[field] ?? "")));
    if (!Object.keys(changes).length) { closeDialog("edit-dialog"); toast("No changes to save."); return; }
    $("edit-error").hidden = true; $("reload-record").hidden = true;
    setModalBusy(true); $("save-record").textContent = "Saving…";
    try {
      await post("/api/edit", { table: state.edit.table, row: state.edit.row.id, values: changes, revision: state.edit.revision });
      setModalBusy(false); closeDialog("edit-dialog"); toast("Changes saved locally. Your source file is unchanged.");
      await refreshWorkspace();
    } catch (error) {
      showDialogError("edit-error", error.status === 409 ? "The workspace changed after you opened this record. Load the latest values, review your retained draft, then save again." : error.message);
      $("reload-record").hidden = error.status !== 409;
    } finally { setModalBusy(false); $("save-record").textContent = "Save local changes"; }
  }

  async function reloadEditor() {
    if (state.modalBusy || !state.edit) return;
    const old = state.edit;
    // Retain only fields the user actually changed. Untouched fields should
    // adopt the current row instead of reverting an intervening source update.
    const draft = Object.fromEntries(Object.entries(editDraft()).filter(
      ([field, value]) => value !== String(old.row.values[field] ?? "")
    ));
    setModalBusy(true);
    try {
      const data = await api(`/api/row?${new URLSearchParams({ table: old.table, id: old.row.id })}`);
      const row = data.row;
      if (!row) throw new Error("This record is not available in the latest results. Close the editor and refresh the workspace before continuing.");
      if (row.missing) throw new Error("This record is now missing from the source snapshot. Close the editor and review it in the missing-records view.");
      state.edit = { row, table: old.table, revision: data.revision };
      renderEditFields(row, draft);
      showDialogError("edit-error", "Latest source values loaded. Your draft is retained above; review it before saving.");
      $("reload-record").hidden = true;
    } catch (error) { showDialogError("edit-error", error.message); }
    finally { setModalBusy(false); }
  }

  function openImport() {
    const select = $("import-table"); select.replaceChildren();
    for (const table of state.bootstrap.tables) { const option = el("option", "", table.label || label(table.id)); option.value = table.id; select.append(option); }
    if (state.table) select.value = state.table;
    $("import-form").reset(); if (state.table) select.value = state.table;
    state.importPreview = null; $("import-preview").hidden = true; $("import-error").hidden = true;
    $("preview-import").hidden = false; $("apply-import").hidden = true;
    $("preview-import").textContent = "Preview changes"; $("apply-import").textContent = "Apply snapshot";
    openDialog("import-dialog");
  }

  function invalidatePreview() {
    state.importPreview = null; $("import-preview").hidden = true; $("apply-import").hidden = true; $("preview-import").hidden = false; $("import-error").hidden = true;
  }

  async function fileBase64(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
    return btoa(binary);
  }

  function renderImportPreview(preview) {
    const counts = $("import-counts"); counts.replaceChildren();
    for (const [key, title] of [["new", "New"], ["updated", "Updated"], ["unchanged", "Unchanged"], ["missing", "Missing"], ["conflicts", "Conflicts"], ["duplicates", "Duplicates collapsed"]]) {
      const card = el("div", `import-count${key === "conflicts" && Number(preview.counts[key]) > 0 ? " warning" : ""}`);
      card.append(el("strong", "", number(preview.counts[key])), el("span", "", title)); counts.append(card);
    }
    const warnings = $("import-warnings"); warnings.replaceChildren();
    for (const warning of preview.warnings || []) warnings.append(el("p", "", typeof warning === "string" ? warning : warning.message || JSON.stringify(warning)));
    $("import-preview-revision").textContent = `rev ${preview.revision}`;
    $("import-preview").hidden = false; $("preview-import").hidden = true; $("apply-import").hidden = false;
  }

  async function previewImport(event) {
    event.preventDefault(); if (state.modalBusy) return;
    const file = $("import-file").files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { showDialogError("import-error", "This file is larger than 10 MB. Split it into smaller snapshots before importing."); return; }
    if (!/\.(csv|xlsx)$/i.test(file.name)) { showDialogError("import-error", "Choose a CSV or XLSX file."); return; }
    $("import-error").hidden = true; setModalBusy(true); $("preview-import").textContent = "Reading snapshot…";
    try {
      const preview = await post("/api/import/preview", { table: $("import-table").value, filename: file.name, content_base64: await fileBase64(file) });
      state.importPreview = preview; renderImportPreview(preview);
    } catch (error) { showDialogError("import-error", error.message); }
    finally { setModalBusy(false); $("preview-import").textContent = "Preview changes"; }
  }

  async function applyImport() {
    if (state.modalBusy || !state.importPreview) return;
    setModalBusy(true); $("apply-import").textContent = "Applying snapshot…"; $("import-error").hidden = true;
    try {
      await post("/api/import/apply", { token: state.importPreview.token, revision: state.importPreview.revision });
      setModalBusy(false); closeDialog("import-dialog"); toast("Snapshot applied. Review any conflicts to choose which values to keep.");
      await refreshWorkspace();
    } catch (error) {
      showDialogError("import-error", error.status === 409 ? "This preview is out of date because the workspace changed. Preview the file again before applying it." : error.message);
      if (error.status === 409) { state.importPreview = null; $("apply-import").hidden = true; $("preview-import").hidden = false; }
    } finally { setModalBusy(false); $("apply-import").textContent = "Apply snapshot"; }
  }

  function emptySection(container, symbol, title, description) {
    const empty = el("div", "empty-state");
    const icon = el("span", "empty-icon", symbol); icon.setAttribute("aria-hidden", "true");
    empty.append(icon, el("h3", "", title), el("p", "", description)); container.replaceChildren(empty);
  }

  async function loadConflicts() {
    const container = $("conflicts-list"); container.replaceChildren(el("p", "loading-state", "Reading conflicts…"));
    try {
      const data = await api("/api/conflicts");
      if (state.section !== "conflicts") return;
      state.revision = data.revision;
      $("conflicts-count").textContent = `${number(data.conflicts.length)} ${data.conflicts.length === 1 ? "choice" : "choices"} to make`;
      if (!data.conflicts.length) { emptySection(container, "✓", "Everything is in step", "No incoming values are waiting for a decision."); return; }
      container.replaceChildren();
      for (const conflict of data.conflicts) {
        const card = el("article", "conflict-card");
        const heading = el("div", "conflict-heading"); const title = el("div");
        const identity = conflict.key_values && typeof conflict.key_values === "object" ? Object.entries(conflict.key_values).map(([key, value]) => `${label(key)} ${display(value)}`).join(" · ") : `Record ${String(conflict.row_id).slice(0, 10)}`;
        title.append(el("strong", "", conflict.field === "__record__" ? "Record missing from source" : label(conflict.field)), el("p", "", identity));
        heading.append(title, el("span", "conflict-table", tableLabel(conflict.table_id))); card.append(heading);
        const values = el("div", "conflict-values");
        for (const [key, caption, className] of [["base", "Previous source", ""], ["local", "Your local value", "local-choice"], ["incoming", "Incoming source", ""]]) {
          const value = el("div", `conflict-value ${className}`); value.append(el("h3", "", caption), el("p", "", display(conflict[key]))); values.append(value);
        }
        card.append(values);
        const actions = el("div", "conflict-actions");
        const local = el("button", "button button-secondary button-small", "Keep my edit"); local.type = "button";
        const incoming = el("button", "button button-primary button-small", "Use incoming"); incoming.type = "button";
        const error = el("p", "conflict-inline-error"); error.setAttribute("role", "alert"); error.hidden = true;
        async function resolve(choice) {
          local.disabled = true; incoming.disabled = true; error.hidden = true;
          try {
            await post("/api/conflicts/resolve", { id: conflict.id, choice, revision: state.revision });
            toast(choice === "local" ? "Your local edit is kept." : "Incoming source value accepted.");
            await refreshWorkspace();
          } catch (problem) {
            error.textContent = problem.status === 409 ? "The workspace changed. Refresh this view and review the latest values before choosing." : problem.message;
            error.hidden = false;
          } finally { local.disabled = false; incoming.disabled = false; }
        }
        local.addEventListener("click", () => resolve("local")); incoming.addEventListener("click", () => resolve("source"));
        actions.append(local, incoming); card.append(actions, error); container.append(card);
      }
    } catch (error) { container.replaceChildren(); showError(error, loadConflicts); }
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  async function loadHistory() {
    const container = $("history-list"); container.replaceChildren(el("p", "loading-state", "Reading import history…"));
    try {
      const data = await api("/api/history");
      if (state.section !== "history") return;
      state.revision = data.revision;
      $("history-count").textContent = `${number(data.history.length)} ${data.history.length === 1 ? "snapshot" : "snapshots"}`;
      if (!data.history.length) { emptySection(container, "↳", "Your history starts here", "Import a snapshot to keep a trace of its changes."); return; }
      container.replaceChildren();
      for (const item of data.history) {
        const entry = el("article", "history-entry"); const icon = el("span", "history-icon", "↳"); icon.setAttribute("aria-hidden", "true");
        const detail = el("div"); detail.append(el("h3", "", item.filename || item.source || "Snapshot"));
        detail.append(el("p", "", tableLabel(item.table_id)));
        const stats = el("div", "history-stats"); const counts = item.counts || item;
        for (const [key, caption] of [["added", "new"], ["new", "new"], ["updated", "updated"], ["missing", "missing"], ["conflicts", "conflicts"]]) {
          if (counts[key] === undefined || (key === "new" && counts.added !== undefined)) continue;
          const stat = el("span"); stat.append(el("strong", "", number(counts[key])), document.createTextNode(` ${caption}`)); stats.append(stat);
        }
        detail.append(stats);
        const time = el("time", "history-time", formatDate(item.created_at || item.timestamp));
        if (item.created_at || item.timestamp) time.dateTime = item.created_at || item.timestamp;
        entry.append(icon, detail, time); container.append(entry);
      }
    } catch (error) { container.replaceChildren(); showError(error, loadHistory); }
  }

  async function refreshWorkspace() {
    try {
      const data = await api("/api/bootstrap");
      if (!Array.isArray(data.tables)) throw new Error("The workspace model does not contain a tables list.");
      state.bootstrap = data; state.revision = data.revision;
      if (!data.tables.some((table) => table.id === state.table)) { state.table = data.tables[0]?.id || null; state.view = ""; state.offset = 0; }
      $("workspace-title").textContent = data.title || "Your working data.";
      document.title = `${data.title || "Workspace"} · Data to App`;
      renderSummary(); renderSection(); clearError();
      if (state.section === "records") { renderViews(); await loadRows(); }
      else if (state.section === "conflicts") await loadConflicts();
      else await loadHistory();
    } catch (error) { showError(error, refreshWorkspace); $("records-loading").hidden = true; $("table-region").setAttribute("aria-busy", "false"); }
  }

  $("global-retry").addEventListener("click", () => state.retry?.());
  $("nav-conflicts").addEventListener("click", () => navigate("conflicts"));
  $("nav-history").addEventListener("click", () => navigate("history"));
  $("metric-conflicts-button").addEventListener("click", () => state.bootstrap && navigate("conflicts"));
  $("menu-toggle").addEventListener("click", () => {
    const open = $("app-frame").classList.toggle("nav-open");
    $("menu-toggle").setAttribute("aria-expanded", String(open)); $("menu-toggle").setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  });
  let searchTimer;
  $("search-input").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.search = $("search-input").value; state.offset = 0; loadRows(); }, 200); });
  $("show-missing").addEventListener("change", () => { state.missing = $("show-missing").checked; state.offset = 0; loadRows(); });
  $("clear-filters").addEventListener("click", () => { clearTimeout(searchTimer); state.search = ""; state.view = ""; state.offset = 0; $("search-input").value = ""; renderViews(); loadRows(); });
  $("previous-page").addEventListener("click", () => { state.offset = Math.max(0, state.offset - state.limit); loadRows(); });
  $("next-page").addEventListener("click", () => { state.offset += state.limit; loadRows(); });
  $("export-button").addEventListener("click", () => { if (state.table) window.location.assign(`/api/export?${new URLSearchParams({ table: state.table })}`); });
  $("import-button").addEventListener("click", () => state.bootstrap && openImport());
  $("edit-form").addEventListener("submit", saveEditor);
  $("reload-record").addEventListener("click", reloadEditor);
  $("import-form").addEventListener("submit", previewImport);
  $("import-file").addEventListener("change", invalidatePreview);
  $("import-table").addEventListener("change", invalidatePreview);
  $("apply-import").addEventListener("click", applyImport);
  for (const button of document.querySelectorAll("[data-close]")) button.addEventListener("click", () => closeDialog(button.dataset.close));
  for (const dialog of document.querySelectorAll("dialog")) {
    dialog.addEventListener("cancel", (event) => { if (state.modalBusy) event.preventDefault(); });
    dialog.addEventListener("close", () => { if (state.returnFocus?.isConnected) state.returnFocus.focus(); });
  }
  $("import-button").disabled = true; $("export-button").disabled = true;
  refreshWorkspace();
})();
