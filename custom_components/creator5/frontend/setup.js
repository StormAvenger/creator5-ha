/* Original admin setup UI; communicates only through the authenticated HA client. */
export async function createDashboard(hass, {entryId, title, path, showInSidebar = false}) {
  if (!title.trim() || title.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)+$/.test(path)) {
    throw new Error("Enter a title and a dashboard address containing lowercase words separated by hyphens.");
  }
  const config = await hass.callWS({type: "creator5/dashboard_config", entry_id: entryId});
  const existing = await hass.callWS({type: "lovelace/dashboards/list"});
  if (existing.some(item => item.url_path === path)) {
    throw new Error("That dashboard address already exists. Choose another; existing dashboards are never replaced.");
  }
  await hass.callWS({type: "lovelace/dashboards/create", url_path: path, title: title.trim(),
    icon: "mdi:printer-3d", require_admin: false, show_in_sidebar: showInSidebar});
  try {
    await hass.callWS({type: "lovelace/config/save", url_path: path, config});
  } catch (_error) {
    throw new Error(`The new empty dashboard was created at /${path}, but its cards could not be saved. Existing dashboards were not changed.`);
  }
  return `/${path}`;
}

export async function createAlerts(hass, {entryId, target, kinds}) {
  const prepared = await hass.callWS({type: "creator5/alert_config", entry_id: entryId, target, kinds});
  const {config, automation_id: id} = prepared;
  // Use the same native editor API as HA, with an explicit no-overwrite preflight.
  try {
    await hass.callApi("GET", `config/automation/config/${id}`);
  } catch (error) {
    if (error.status_code !== 404 && error.status !== 404) throw error;
    await hass.callApi("POST", `config/automation/config/${id}`, config);
    return id;
  }
  throw new Error("Alerts for this printer already exist. Edit them in Settings → Automations; they were not replaced.");
}

export async function fileAction(hass, {entryId, action, filename, file}, confirmAction = message => globalThis.confirm(message)) {
  if (action === "upload" && (!file || file.size <= 0 || file.size > 64 * 1024 * 1024)) {
    throw new Error("Choose a nonempty sliced file up to 64 MiB.");
  }
  const prepared = await hass.callWS({type: "creator5/file_prepare", entry_id: entryId, action,
    ...(filename ? {filename} : {})});
  if (!await confirmAction(prepared.message)) return null;
  if (action === "upload") {
    const body = new FormData(); body.append("file", file, filename);
    const response = await hass.fetchWithAuth(`/api/creator5/files/${encodeURIComponent(entryId)}/upload`, {
      method: "POST", headers: {"X-Creator5-Confirmation": prepared.token}, body});
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Upload outcome is unconfirmed; refresh the list before retrying.");
    return result;
  }
  return hass.callWS({type: "creator5/file_execute", entry_id: entryId, token: prepared.token});
}

export class Creator5SetupPanel extends HTMLElement {
  set hass(value) {
    this._hass = value;
    if (!this._started) {
      this._started = true;
      this.render();
      this.load();
    }
  }
  render() {
    this.attachShadow({mode: "open"});
    this.shadowRoot.innerHTML = `
      <style>
        :host {display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100%;font:16px var(--paper-font-body1_-_font-family,system-ui)}
        main {max-width:760px;margin:auto;padding:32px 24px 64px} h1 {font-size:28px;margin:0 0 12px} h2 {font-size:21px;margin:0 0 12px}
        section {padding:24px;margin:24px 0;border:1px solid var(--divider-color,#ccc);border-radius:16px;background:var(--card-background-color)}
        p {line-height:1.55;color:var(--secondary-text-color)} label {display:block;margin:16px 0 6px} input,select {box-sizing:border-box;max-width:100%;padding:11px;border:1px solid var(--divider-color,#aaa);border-radius:8px;background:var(--card-background-color);color:inherit;font:inherit}
        input:not([type=checkbox]),select {width:100%} button {margin-top:20px;padding:12px 18px;border:0;border-radius:22px;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);font:inherit;cursor:pointer} button:disabled {opacity:.5;cursor:default}
        .check {display:flex;gap:12px;align-items:center} .check input {width:20px;height:20px} #status {white-space:pre-wrap;line-height:1.6} a {color:var(--primary-color,#03a9f4)}
      </style>
      <main><h1>Creator 5 tools</h1><p>Browse recent sliced files, manage optional print actions, create a dashboard and choose alerts. File actions require separate confirmation.</p>
      <label for="printer">Printer</label><select id="printer"></select>
      <section><h2>Printer files</h2><p>The printer reports a recent-file list, which may omit older stored files. Refresh and previews are read-only.</p>
      <button id="refresh-files" disabled>Refresh files</button>
      <label for="files">Recent sliced files</label><select id="files"></select>
      <button id="preview-file" disabled>Show preview</button><br><img id="file-preview" hidden alt="Selected sliced-file preview" style="max-width:100%;max-height:260px">
      <p id="file-permission">Uploads, reprints and cancellation are off by default. Enable them in the integration's Configure settings.</p>
      <button id="start-file" disabled>Start / reprint selected file…</button>
      <label for="upload-file">Upload a trusted sliced .3mf or .gcode (up to 64 MiB)</label><input id="upload-file" type="file" accept=".3mf,.gcode">
      <button id="send-file" disabled>Upload only…</button>
      <p>Uploading does not start printing. Reprinting uses the slicer's numbered material slots; previous custom mappings and HA tool notes are not applied. Check the bed, nozzles and materials before confirming.</p>
      <button id="cancel-print" disabled>Cancel current print…</button>
      <p id="file-status" role="status" aria-live="polite">Choose Refresh files to read the printer's list.</p></section>
      <section><h2>Add a printer dashboard</h2><p>A separate, editable dashboard with your printer's actual entities, grouped material slots, camera and enabled controls. Existing dashboards stay as they are.</p>
      <label for="title">Dashboard title</label><input id="title" maxlength="64" value="Creator 5">
      <label for="path">Dashboard address</label><input id="path" spellcheck="false">
      <label class="check"><input id="dashboard-sidebar" type="checkbox">Show the new dashboard in the sidebar</label>
      <button id="dashboard" disabled>Create dashboard</button></section>
      <section><h2>Set up notifications</h2><p>Choose where alerts go and which events matter. One alert per event; no layer or percentage messages. Existing automations are preserved.</p>
      <label for="target">Destination</label><select id="target"></select><div id="alerts"></div>
      <button id="notifications" disabled>Create alerts</button></section>
      <section><h2>Preferences and maintenance</h2><p>Under Settings → Devices &amp; services → Creator 5 → Configure, enable or hide the Creator 5 tools sidebar shortcut, enable file actions, or set cooling, alert and maintenance preferences. The tools shortcut is off by default; this page remains accessible from the integration. A maintenance interval of 0 disables that reminder.</p><p>Record completed maintenance using the device's Record bed cleaning, Record rail lubrication or Record nozzle inspection buttons. Those buttons update local records only.</p></section>
      <p id="status" role="status" aria-live="polite">Loading printers…</p></main>`;
    this.$("printer").addEventListener("change", () => this.selectPrinter());
    this.$("dashboard").addEventListener("click", () => this.run("dashboard"));
    this.$("notifications").addEventListener("click", () => this.run("notifications"));
    this.$("files").addEventListener("change", () => { this.clearPreview(); this.updateFileButtons(); });
    this.$("upload-file").addEventListener("change", () => this.updateFileButtons());
    for (const kind of ["refresh-files", "preview-file", "start-file", "send-file", "cancel-print"]) {
      this.$(kind).addEventListener("click", () => this.runFile(kind));
    }
  }
  $(id) { return this.shadowRoot.getElementById(id); }
  async load() {
    try {
      this.info = await this._hass.callWS({type: "creator5/setup_info"});
      for (const printer of this.info.printers) {
        this.$("printer").add(new Option(printer.name, printer.entry_id));
      }
      for (const [id, name] of Object.entries(this.info.targets)) this.$("target").add(new Option(name, id));
      for (const [kind, label] of Object.entries(this.info.alerts)) {
        const row = document.createElement("label"); row.className = "check";
        const check = document.createElement("input"); check.type = "checkbox"; check.value = kind;
        check.checked = ["completed", "bed_cooled", "error", "offline"].includes(kind);
        row.append(check, document.createTextNode(label)); this.$("alerts").append(row);
      }
      this.selectPrinter();
      this.$("status").textContent = this.info.printers.length ? "Choose a setup action above." : "Add a Creator 5 integration first, then reopen this page.";
    } catch (_error) { this.$("status").textContent = "Setup could not load. Sign in as an administrator and check that the integration is loaded."; }
  }
  selectPrinter() {
    const entry = this.info.printers.find(p => p.entry_id === this.$("printer").value);
    if (entry) { this.$("path").value = entry.dashboard_path; this.$("title").value = entry.name; }
    this.$("dashboard").disabled = !entry || !this.info.dashboards_available;
    this.$("notifications").disabled = !entry;
    this.$("files").replaceChildren(); this.$("upload-file").value = ""; this.clearPreview();
    this.$("file-status").textContent = "Choose Refresh files to read the printer's list.";
    this.updateFileButtons();
  }
  clearPreview() { this.$("file-preview").hidden = true; this.$("file-preview").removeAttribute("src"); }
  updateFileButtons() {
    const entry = this.info?.printers.find(p => p.entry_id === this.$("printer").value);
    const busy = !!this._fileBusy, writable = !!entry?.file_controls;
    this.$("printer").disabled = busy;
    this.$("files").disabled = busy;
    this.$("upload-file").disabled = busy || !writable;
    this.$("refresh-files").disabled = busy || !entry;
    this.$("preview-file").disabled = busy || !this.$("files").value;
    this.$("start-file").disabled = busy || !writable || !this.$("files").value;
    this.$("send-file").disabled = busy || !writable || !this.$("upload-file").files?.length;
    this.$("cancel-print").disabled = busy || !writable;
    this.$("file-permission").textContent = writable ? "File actions enabled. Every upload, start and cancellation requires confirmation." : "Uploads, reprints and cancellation are off. Enable them in the integration's Configure settings, then reopen this page.";
  }
  async runFile(kind) {
    if (this._fileBusy) return;
    this._fileBusy = true; this.updateFileButtons();
    this.$("file-status").textContent = "Working…";
    try {
      const entryId = this.$("printer").value, filename = this.$("files").value;
      if (kind === "refresh-files") {
        const result = await this._hass.callWS({type: "creator5/files", entry_id: entryId});
        this.$("files").replaceChildren(); this.clearPreview();
        for (const name of result.files) this.$("files").add(new Option(name, name));
        this.$("file-status").textContent = result.files.length ? `${result.files.length} recent files reported. No print action was sent.` : "No supported sliced files reported.";
      } else if (kind === "preview-file") {
        this.clearPreview();
        const result = await this._hass.callWS({type: "creator5/file_thumbnail", entry_id: entryId, filename});
        if (!["image/png", "image/jpeg"].includes(result.mime) || !/^[A-Za-z0-9+/=]+$/.test(result.image)) throw new Error("Unsupported preview.");
        this.$("file-preview").src = `data:${result.mime};base64,${result.image}`; this.$("file-preview").hidden = false;
        this.$("file-status").textContent = "Preview loaded. No print action was sent.";
      } else {
        const action = {"start-file": "start", "send-file": "upload", "cancel-print": "cancel"}[kind];
        const file = this.$("upload-file").files?.[0];
        const result = await fileAction(this._hass, {entryId, action, filename: action === "upload" ? file?.name : filename, file});
        this.$("file-status").textContent = result === null ? "No action sent." : action === "upload" ? `Upload verified as ${result.filename}. Refresh files to find it. No print was started.` : `Printer confirmed state: ${result.state}.`;
        if (result && action === "upload") this.$("upload-file").value = "";
      }
    } catch (error) { this.$("file-status").textContent = error.message || "Request failed. Check the printer before retrying any print action."; }
    finally { this._fileBusy = false; this.updateFileButtons(); }
  }
  async run(kind) {
    const button = this.$(kind); button.disabled = true;
    try {
      const entryId = this.$("printer").value;
      if (kind === "dashboard") {
        const path = await createDashboard(this._hass, {entryId, title: this.$("title").value, path: this.$("path").value, showInSidebar: this.$("dashboard-sidebar").checked});
        this.$("status").textContent = "Dashboard created. ";
        const link = document.createElement("a"); link.href = path; link.textContent = "Open dashboard"; this.$("status").append(link);
      } else {
        const kinds = [...this.$("alerts").querySelectorAll("input:checked")].map(item => item.value);
        await createAlerts(this._hass, {entryId, target: this.$("target").value, kinds});
        this.$("status").textContent = "Alerts created. You can edit or disable them in Settings → Automations. Filenames are not included in notifications.";
      }
    } catch (error) { this.$("status").textContent = error.message || "The setup action could not complete. Check Home Assistant's logs."; button.disabled = false; }
  }
}
if (!customElements.get("creator5-setup-panel")) customElements.define("creator5-setup-panel", Creator5SetupPanel);
