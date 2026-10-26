/* Original admin setup UI; communicates only through the authenticated HA client. */
export async function createDashboard(hass, {entryId, title, path}) {
  if (!title.trim() || title.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)+$/.test(path)) {
    throw new Error("Enter a title and a dashboard address containing lowercase words separated by hyphens.");
  }
  const config = await hass.callWS({type: "creator5/dashboard_config", entry_id: entryId});
  const existing = await hass.callWS({type: "lovelace/dashboards/list"});
  if (existing.some(item => item.url_path === path)) {
    throw new Error("That dashboard address already exists. Choose another; existing dashboards are never replaced.");
  }
  await hass.callWS({type: "lovelace/dashboards/create", url_path: path, title: title.trim(),
    icon: "mdi:printer-3d", require_admin: false, show_in_sidebar: true});
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
      <main><h1>Creator 5 setup</h1><p>Create a printer dashboard and choose useful alerts. These setup actions send no commands to your printer.</p>
      <label for="printer">Printer</label><select id="printer"></select>
      <section><h2>Add a printer dashboard</h2><p>A separate, editable dashboard with your printer's actual entities, grouped material slots, camera and enabled controls. Existing dashboards stay as they are.</p>
      <label for="title">Dashboard title</label><input id="title" maxlength="64" value="Creator 5">
      <label for="path">Dashboard address</label><input id="path" spellcheck="false">
      <button id="dashboard" disabled>Create dashboard</button></section>
      <section><h2>Set up notifications</h2><p>Choose where alerts go and which events matter. One alert per event; no layer or percentage messages. Existing automations are preserved.</p>
      <label for="target">Destination</label><select id="target"></select><div id="alerts"></div>
      <button id="notifications" disabled>Create alerts</button></section>
      <section><h2>Cooling and maintenance</h2><p>Under Settings → Devices &amp; services → Creator 5 → Configure, set the bed-cooled threshold, pause/offline delays and maintenance intervals. A maintenance interval of 0 disables that reminder.</p><p>Record completed maintenance using the device's Record bed cleaning, Record rail lubrication or Record nozzle inspection buttons. Those buttons update local records only.</p></section>
      <p id="status" role="status" aria-live="polite">Loading printers…</p></main>`;
    this.$("printer").addEventListener("change", () => this.selectPrinter());
    this.$("dashboard").addEventListener("click", () => this.run("dashboard"));
    this.$("notifications").addEventListener("click", () => this.run("notifications"));
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
  }
  async run(kind) {
    const button = this.$(kind); button.disabled = true;
    try {
      const entryId = this.$("printer").value;
      if (kind === "dashboard") {
        const path = await createDashboard(this._hass, {entryId, title: this.$("title").value, path: this.$("path").value});
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
