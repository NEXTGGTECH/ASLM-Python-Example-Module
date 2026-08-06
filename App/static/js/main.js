"use strict";

// Theme (CSS variables from host snapshot)

/** Map host theme colors.* tokens onto dashboard CSS custom properties. */
function applyHostTheme(themePayload) {
    if (!themePayload || !themePayload.colors) return;

    const root = document.documentElement;
    const c = themePayload.colors;
    const theme = (themePayload.theme || "dark").toLowerCase();
    root.setAttribute("data-theme", theme);

    /** Convert #AARRGGBB from .NET to #RRGGBB for CSS. */
    function hex(token) {
        const raw = c[token];
        if (!raw) return null;
        if (raw.length === 9 && raw[0] === "#") return "#" + raw.slice(3);
        return raw;
    }

    // ASLM canonical color names → local --c-* variables (see style.css).
    const map = {
        "--c-bg-primary": hex("BackgroundPrimary"),
        "--c-bg-secondary": hex("BackgroundSecondary"),
        "--c-bg-tertiary": hex("BackgroundTertiary"),
        "--c-label-primary": hex("LabelPrimary"),
        "--c-label-secondary": hex("LabelSecondary"),
        "--c-label-tertiary": hex("LabelTertiary"),
        "--c-separator": hex("Separator"),
        "--c-accent": hex("SystemBlue"),
        "--c-system-green": hex("SystemGreen"),
        "--c-system-red": hex("SystemRed"),
        "--c-system-orange": hex("SystemOrange"),
        "--c-system-yellow": hex("SystemYellow"),
        "--c-system-purple": hex("SystemPurple"),
        "--c-system-teal": hex("SystemTeal"),
        "--c-placeholder": hex("PlaceholderText"),
    };

    for (const [prop, value] of Object.entries(map)) {
        if (value) root.style.setProperty(prop, value);
    }
}

/** Apply theme embedded in index.html before the first API round-trip. */
(function () {
    const raw = document.getElementById("aslm-theme-data");
    if (raw) {
        try { applyHostTheme(JSON.parse(raw.textContent)); } catch (_) {}
    }
})();

// Utilities

/** GET/POST JSON and throw on non-2xx with a readable message. */
async function fetchJson(url, options) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        const msg = data.error || data.message || `HTTP ${res.status}`;
        throw new Error(msg);
    }
    return data;
}

/** Shorthand for document.getElementById. */
function el(id) { return document.getElementById(id); }

/** Replace innerHTML of an element by id (no-op if missing). */
function setHtml(id, html) {
    const node = el(id);
    if (node) node.innerHTML = html;
}

/** Escape text for safe HTML insertion. */
function escHtml(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/** Render a formatted JSON block inside a <pre class="json-pre">. */
function jsonPre(obj) {
    return `<pre class="json-pre">${escHtml(JSON.stringify(obj, null, 2))}</pre>`;
}

/** Like fetchJson but never throws — returns { ok, status, data }. */
async function fetchJsonResponse(url, options) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
}

/** Build request/response HTML for one host interop HTTP exchange. */
function renderExchangeBlock(exchange) {
    if (!exchange) return "";
    const status = exchange.statusCode != null ? String(exchange.statusCode) : "—";

    return `
        <div class="io-label io-label--request">Request — ${escHtml(exchange.method)} ${escHtml(exchange.url)}</div>
        ${jsonPre({
            headers: exchange.requestHeaders || {},
            body: exchange.requestBody == null ? null : exchange.requestBody,
        })}
        <div class="io-label io-label--response">Response <span class="status-code">HTTP ${escHtml(status)}</span></div>
        ${jsonPre(exchange.responseBody ?? {})}
    `;
}

/** Prepend one exchange entry to the interop log panel. */
function appendInteropExchange(title, exchange) {
    const log = el("interop-exchange-log");
    if (!log || !exchange) return;

    const placeholder = log.querySelector(".state-msg");
    if (placeholder) placeholder.remove();

    const entry = document.createElement("div");
    entry.className = "exchange-entry";
    entry.innerHTML = `
        <h4>${escHtml(title)}<span class="exchange-time">${escHtml(new Date().toLocaleTimeString())}</span></h4>
        ${renderExchangeBlock(exchange)}
    `;
    log.prepend(entry);
}

/** Small colored badge for a setting type column. */
function typeBadge(type) {
    return `<span class="type-badge t-${escHtml(type)}">${escHtml(type)}</span>`;
}

/** Green/neutral pill for boolean manifest flags. */
function boolPill(value, trueLabel, falseLabel) {
    return value
        ? `<span class="pill ok">${escHtml(trueLabel)}</span>`
        : `<span class="pill neutral">${escHtml(falseLabel)}</span>`;
}

// Module Info

/** Fill Module Info, ASLM env vars, and manifest summary sections. */
async function loadInfo() {
    const data = await fetchJson("/api/info");

    // Core runtime identifiers from GET /api/info.
    setHtml("info-table", `
        <table class="kv-table">
            <tr><td>Module ID</td><td><code>${escHtml(data.moduleId)}</code></td></tr>
            <tr><td>Module dir</td><td><code>${escHtml(data.moduleDir)}</code></td></tr>
            <tr><td>Python</td><td><code>${escHtml(data.pythonExecutable || "")}</code></td></tr>
            <tr><td>Engine env</td><td><code>${escHtml(data.engineEnvDir || "")}</code></td></tr>
            <tr><td>UI port</td><td><code>${escHtml(data.uiPort)}</code></td></tr>
            <tr><td>Interop URL</td><td><code>${escHtml(data.interopBaseUrl)}</code></td></tr>
        </table>
    `);

    // All ASLM_* variables injected by the host.
    const envEntries = Object.entries(data.allAslmEnvVars || {});
    if (envEntries.length) {
        const rows = envEntries
            .map(([k, v]) => `<tr><td>${escHtml(k)}</td><td><code>${escHtml(v)}</code></td></tr>`)
            .join("");
        setHtml("env-table", `<table class="kv-table">${rows}</table>`);
    } else {
        setHtml("env-table", `<p class="state-msg">Launch via ASLM to see injected variables.</p>`);
    }

    // Compact manifest excerpt (bridge, interop, engines).
    const manifest = data.manifest || {};
    if (manifest.id) {
        const bridge = manifest.downloadsBridge || {};
        const interop = manifest.moduleInterop || {};
        const deps = manifest.dependencies || {};
        const engines = (deps.engines || [])
            .map((e) => `<li><code>${escHtml(e.id)}</code> — libraries: ${escHtml((e.libraries || []).join(", ") || "—")}</li>`)
            .join("");

        setHtml("manifest-table", `
            <table class="kv-table">
                <tr><td>Module</td><td><code>${escHtml(manifest.id)}</code> v${escHtml(manifest.version)} (${escHtml(manifest.type)})</td></tr>
                <tr><td>Settings</td><td>${escHtml(manifest.settingsCount)} keys — types: ${escHtml((manifest.settingTypes || []).join(", "))}</td></tr>
                <tr><td>Downloads bridge</td><td>v${escHtml(bridge.protocolVersion)} — ${escHtml((bridge.operations || []).join(", "))}</td></tr>
                <tr><td>Module interop</td><td>v${escHtml(interop.protocolVersion)} — client ${interop.clientEnabled ? "enabled" : "disabled"}</td></tr>
                <tr><td>Dependencies</td><td><ul style="margin:0;padding-left:18px">${engines || "<li>—</li>"}</ul></td></tr>
            </table>
        `);
    } else {
        setHtml("manifest-table", `<p class="state-msg">Could not read ASLM_Module.json.</p>`);
    }
}

// Settings

/** Render the settings table from GET /api/settings. */
async function loadSettings() {
    const data = await fetchJson("/api/settings");
    const settings = data.settings || [];

    if (!settings.length) {
        setHtml("settings-table-body", `<tr><td colspan="6"><p class="state-msg">No settings.</p></td></tr>`);
        return;
    }

    const rows = settings.map((s) => {
        // Mask password-type values; show allowedValues when present.
        const valueDisplay =
            s.type === "password" && s.value
                ? `<em style="color:var(--c-label-tertiary)">••••••••</em>`
                : `<code>${escHtml(String(s.value ?? ""))}</code>`;
        const defaultDisplay =
            s.default === null || s.default === undefined
                ? "—"
                : `<code>${escHtml(String(s.default))}</code>`;
        const allowed =
            s.allowedValues && s.allowedValues.length
                ? `<div class="text-muted" style="margin-top:var(--space-4)">allowed: ${escHtml(s.allowedValues.join(", "))}</div>`
                : "";
        return `
            <tr>
                <td class="col-key"><code>${escHtml(s.key)}</code></td>
                <td class="col-name">${escHtml(s.name || s.key)}</td>
                <td class="col-type">${typeBadge(s.type)}</td>
                <td class="col-value">${valueDisplay}</td>
                <td class="col-default">${defaultDisplay}</td>
                <td class="col-desc">${escHtml(s.description || "")}${allowed}</td>
            </tr>
        `;
    }).join("");

    setHtml("settings-table-body", rows);
}

// Host theme

/** Load host theme snapshot and paint swatches + CSS variables. */
async function loadTheme() {
    const data = await fetchJson("/api/theme");

    if (!data.available) {
        setHtml("theme-content", `<p class="state-msg">${escHtml(data.message)}</p>`);
        return;
    }

    applyHostTheme(data);

    // Summary row: appearance, effective theme id, custom theme name.
    const meta = `
        <table class="kv-table" style="margin-bottom:var(--space-12)">
            <tr><td>Appearance</td><td><code>${escHtml(data.appearance || "")}</code></td></tr>
            <tr><td>Effective</td><td><code>${escHtml(data.theme || "")}</code></td></tr>
            <tr><td>Custom theme</td><td><code>${escHtml(data.customThemeName || data.customThemeId || "—")}</code></td></tr>
        </table>
    `;

    // One swatch per colors.* token from the host snapshot.
    const colors = data.colors || {};
    const swatches = Object.entries(colors)
        .map(([name, hex]) => {
            const cssColor = hex.length === 9 ? "#" + hex.slice(3) : hex;
            return `
                <div class="swatch">
                    <div class="swatch-color" style="background:${escHtml(cssColor)}"></div>
                    <div class="swatch-label">
                        <div class="swatch-name">${escHtml(name)}</div>
                        <div class="swatch-hex">${escHtml(hex)}</div>
                    </div>
                </div>
            `;
        })
        .join("");

    setHtml(
        "theme-content",
        meta +
            `<div class="palette-grid">${swatches}</div>` +
            `<details class="block-details"><summary>Full theme snapshot JSON</summary>${jsonPre(data.rawPayload || data)}</details>` +
            (data.snapshotPath
                ? `<p class="text-muted" style="margin-top:var(--space-8)">File: <code>${escHtml(data.snapshotPath)}</code></p>`
                : "")
    );
}

// Host locale

/** Load host locale snapshot (language, displayName). */
async function loadLocale() {
    const data = await fetchJson("/api/locale");

    if (!data.available) {
        setHtml("locale-content", `<p class="state-msg">${escHtml(data.message)}</p>`);
        return;
    }

    setHtml(
        "locale-content",
        `
        <table class="kv-table">
            <tr><td>Language</td><td><code>${escHtml(data.language || "")}</code></td></tr>
            <tr><td>Display name</td><td>${escHtml(data.displayName || "")}</td></tr>
        </table>
        <details class="block-details"><summary>Full locale snapshot JSON</summary>${jsonPre(data.rawPayload || data)}</details>
        ${data.snapshotPath ? `<p class="text-muted" style="margin-top:var(--space-8)">File: <code>${escHtml(data.snapshotPath)}</code></p>` : ""}
    `
    );
}

// Downloads bridge

/** Run all five bridge ops via GET /api/downloads and render stdin/stdout pairs. */
async function loadDownloads() {
    const data = await fetchJson("/api/downloads");

    // Protocol note from the server (v1 stdin/stdout contract).
    const noteEl = el("downloads-protocol-note");
    if (noteEl) {
        const text = (data.protocolNote || "").trim();
        if (text) {
            noteEl.textContent = text;
            noteEl.classList.remove("is-hidden");
        } else {
            noteEl.textContent = "";
            noteEl.classList.add("is-hidden");
        }
    }

    const manifestBlock =
        data.manifestCategories || data.manifestTargets
            ? `<div class="bridge-manifest">
                <details>
                    <summary>Manifest categories &amp; targets</summary>
                    ${jsonPre({ categories: data.manifestCategories, targets: data.manifestTargets })}
                </details>
               </div>`
            : "";

    // One card per operation with request/response JSON.
    const operations = data.operations || [];
    const sections = operations
        .map(
            (op) => `
        <div class="bridge-op">
            <div class="bridge-op-title">
                <span class="method-badge">stdio</span>
                <h3>${escHtml(op.operation)}</h3>
            </div>
            <div class="io-label io-label--request">stdin request</div>
            ${jsonPre(op.request || {})}
            <div class="io-label io-label--response">stdout response</div>
            ${jsonPre(op.response || {})}
        </div>
    `
        )
        .join("");

    setHtml("downloads-content", manifestBlock + sections);
}

// Module Interop

/** Read example-int from settings as auto-refresh interval (ms). */
async function getInteropRefreshIntervalMs() {
    try {
        const data = await fetchJson("/api/settings");
        const row = (data.settings || []).find((s) => s.key === "example-int");
        const ms = Number(row?.value);
        return Number.isFinite(ms) && ms > 0 ? ms : 10000;
    } catch {
        return 10000;
    }
}

/** Fetch INTEROP_API_SPEC and render the Supported HTTP API table. */
async function loadInteropSpec() {
    const spec = await fetchJson("/api/interop/spec");
    renderInteropApiSpec(spec);
}

/** Build the interop API spec table (routes, bodies, error codes). */
function renderInteropApiSpec(spec) {
    const node = el("interop-api-spec");
    if (!node) return;

    const endpoints = spec.endpoints || [];
    const rows = endpoints
        .map((ep) => {
            const errors = (ep.errorResponses || [])
                .map((e) => `HTTP ${e.status} <code>${escHtml(e.code)}</code> — ${escHtml(e.message)}`)
                .join("<br>");
            const req = ep.requestBody
                ? jsonPre(ep.requestBody)
                : "<span class=\"state-msg\">—</span>";
            return `
            <tr>
                <td><code>${escHtml(ep.method)} ${escHtml(ep.path)}</code></td>
                <td>${escHtml(ep.summary)}</td>
                <td>${req}</td>
                <td>${errors || "—"}</td>
            </tr>
        `;
        })
        .join("");

    // Extra row for POST /v1/modules/start result status codes.
    const startEp = endpoints.find((e) => String(e.path || "").includes("start"));
    const statuses = startEp?.resultStatuses || [];

    const constraints = (spec.constraints || [])
        .map((c) => `<li>${escHtml(c)}</li>`)
        .join("");

    node.innerHTML = `
        <table class="api-spec-table">
            <thead>
                <tr>
                    <th>Route</th>
                    <th>Description</th>
                    <th>Request body</th>
                    <th>Error responses</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
        ${
            statuses.length
                ? `<p class="text-secondary" style="margin:var(--space-8) 0"><strong>Start result statuses:</strong> ${statuses.map((s) => `<code>${escHtml(s)}</code>`).join(", ")}</p>`
                : ""
        }
        <ul class="text-secondary list-compact">${constraints}</ul>
        <p class="text-muted" style="margin-top:var(--space-8)">
            Protocol v${escHtml(spec.protocolVersion)} —
            env <code>${escHtml(spec.baseUrlEnv)}</code>
            ${spec.interopBaseUrl ? ` — active <code>${escHtml(spec.interopBaseUrl)}</code>` : " — not available outside ASLM"}
        </p>
    `;
}

const interopState = {
    registry: null,
    callerId: "aslm-python-example",
    filter: "",
    autoRefreshTimer: null,
    selectedIds: new Set(),
};

let interopControlsReady = false;
let interopDelegationReady = false;

/** Map start result status strings to pill CSS classes. */
const START_STATUS_PILL = {
    started: "ok",
    alreadyRunning: "info",
    notFound: "missing",
    noRunCommands: "warn",
    firstRunFailed: "missing",
    error: "missing",
};

/** Show or hide the interop status banner above the tables. */
function showInteropAlert(message, kind) {
    const node = el("interop-alert");
    if (!node) return;
    if (!message) {
        node.hidden = true;
        node.innerHTML = "";
        return;
    }
    node.hidden = false;
    node.className = `alert alert--${kind || "info"}`;
    node.textContent = message;
}

/** Set of module ids currently in runningModules[]. */
function getRunningIdSet(registry) {
    return new Set((registry.runningModules || []).map((m) => m.id));
}

/** True when the row can be started (not self, has run commands, not already running). */
function isStartableModule(m, runningIds, callerId) {
    if (!m || m.id === callerId) return false;
    if (!m.hasRunCommands) return false;
    if (runningIds.has(m.id)) return false;
    return true;
}

/** Installed modules with isRunning flag, optionally filtered by search box. */
function mergeInstalledRows(registry) {
    const running = getRunningIdSet(registry);
    const rows = (registry.installedModules || []).map((m) => ({
        ...m,
        isRunning: running.has(m.id),
    }));

    // Text filter on id, display name, instance folder.
    const filter = interopState.filter.trim().toLowerCase();
    if (!filter) return rows;

    return rows.filter(
        (m) =>
            m.id.toLowerCase().includes(filter) ||
            (m.name || "").toLowerCase().includes(filter) ||
            (m.instanceFolder || "").toLowerCase().includes(filter)
    );
}

/** Hide interop UI and show an error when the proxy is unavailable. */
function renderInteropUnavailable(data) {
    el("interop-toolbar")?.setAttribute("hidden", "");
    el("interop-panels")?.setAttribute("hidden", "");
    el("interop-hint")?.classList.add("is-hidden");
    showInteropAlert(
        data.message || data.error || "Interop API is not available. Launch this module from ASLM with moduleInterop enabled.",
        "error"
    );
    setHtml("interop-installed-body", "");
    setHtml("interop-running-body", "");
    if (el("interop-raw-json")) el("interop-raw-json").textContent = "—";
}

/** Render installed modules table with checkboxes and per-row Start buttons. */
function renderInstalledTable(registry) {
    const tbody = el("interop-installed-body");
    if (!tbody) return;

    const running = getRunningIdSet(registry);
    const caller = interopState.callerId;
    const rows = mergeInstalledRows(registry);

    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="5"><p class="state-msg">No modules match the filter.</p></td></tr>`;
        updateInteropActionButtons(registry);
        return;
    }

    tbody.innerHTML = rows
        .map((m) => {
            // Row state: running, caller (cannot start self), startable checkbox.
            const isSelf = m.id === caller;
            const canStart = isStartableModule(m, running, caller);
            const checked = interopState.selectedIds.has(m.id) ? "checked" : "";
            const rowClass = [m.isRunning ? "is-running" : "", isSelf ? "is-self" : ""].filter(Boolean).join(" ");

            const statePill = m.isRunning
                ? `<span class="pill ok">running</span>`
                : m.enabled
                  ? `<span class="pill warn">stopped</span>`
                  : `<span class="pill warn">stopped</span> <span class="pill neutral" title="Disabled in ASLM module settings">settings off</span>`;

            const details = [
                boolPill(m.installed, "installed", "missing"),
                boolPill(m.firstRunCompleted, "first-run ok", "first-run pending"),
                m.hasMultipleInstances ? `<span class="pill neutral">multi-instance</span>` : "",
            ].join(" ");

            const selfNote = isSelf
                ? `<div class="text-muted">caller (cannot start self)</div>`
                : "";

            return `
                <tr class="${rowClass}" data-module-id="${escHtml(m.id)}">
                    <td>
                        <input type="checkbox" class="interop-row-check" data-id="${escHtml(m.id)}"
                            ${canStart ? "" : "disabled"} ${checked}
                            ${isSelf ? 'title="Cannot start the caller module"' : ""} />
                    </td>
                    <td>
                        <div class="mono">${escHtml(m.id)}</div>
                        <div class="text-secondary">${escHtml(m.name)} v${escHtml(m.version)}</div>
                        ${m.instanceFolder ? `<div class="text-muted">${escHtml(m.instanceFolder)}</div>` : ""}
                        ${selfNote}
                    </td>
                    <td>${statePill}</td>
                    <td>${details}</td>
                    <td class="interop-actions-cell">
                        <button type="button" class="btn btn--sm interop-start-one"
                            data-id="${escHtml(m.id)}" ${canStart ? "" : "disabled"}
                            ${isSelf ? 'title="Cannot start the caller module"' : !m.hasRunCommands ? 'title="No run commands"' : ""}>
                            Start
                        </button>
                    </td>
                </tr>
            `;
        })
        .join("");

    updateInteropActionButtons(registry);
}

/** Render runningModules[] as a read-only table. */
function renderRunningTable(registry) {
    const tbody = el("interop-running-body");
    if (!tbody) return;

    const rows = registry.runningModules || [];
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="3"><p class="state-msg">No modules are running.</p></td></tr>`;
        return;
    }

    tbody.innerHTML = rows
        .map(
            (m) => `
        <tr class="is-running">
            <td>
                <span class="status-dot running"></span>
                <span class="mono">${escHtml(m.id)}</span>
                <div class="text-secondary">${escHtml(m.name)}</div>
            </td>
            <td class="mono">${escHtml(m.instanceFolder || "—")}</td>
            <td class="mono text-muted">${escHtml(m.sourcePath || "")}</td>
        </tr>
    `
        )
        .join("");
}

/** Update toolbar labels: base URL, caller id, installed/running counts. */
function updateInteropMeta(registry) {
    if (el("interop-base-url")) {
        el("interop-base-url").textContent = registry.interopBaseUrl || "—";
    }
    if (el("interop-caller-id")) {
        el("interop-caller-id").textContent = interopState.callerId;
    }
    if (el("interop-counts")) {
        const installed = (registry.installedModules || []).length;
        const running = (registry.runningModules || []).length;
        el("interop-counts").textContent = `${running} running / ${installed} installed`;
    }
}

/** Show hint when no other modules can be started. */
function updateInteropHint(registry) {
    const hint = el("interop-hint");
    if (!hint || !registry) return;

    const running = getRunningIdSet(registry);
    const startable = (registry.installedModules || []).filter((m) =>
        isStartableModule(m, running, interopState.callerId)
    );

    if (startable.length === 0) {
        hint.textContent =
            "No other stopped modules with run commands are available. The caller module cannot start itself.";
        hint.classList.remove("is-hidden");
    } else {
        hint.classList.add("is-hidden");
    }
}

/** Enable/disable bulk Start buttons and sync select-all checkbox state. */
function updateInteropActionButtons(registry) {
    if (!registry) return;

    const running = getRunningIdSet(registry);
    const stoppable = (registry.installedModules || []).filter((m) =>
        isStartableModule(m, running, interopState.callerId)
    );

    const startSelected = el("interop-start-selected-btn");
    const startStopped = el("interop-start-stopped-btn");
    const hasSelection = interopState.selectedIds.size > 0;

    if (startSelected) startSelected.disabled = !hasSelection;
    if (startStopped) startStopped.disabled = stoppable.length === 0;

    updateInteropHint(registry);

    // Tri-state header checkbox when only some startable rows are selected.
    const selectAll = el("interop-select-all");
    if (selectAll && stoppable.length > 0) {
        const selectedStartable = stoppable.filter((m) => interopState.selectedIds.has(m.id));
        selectAll.indeterminate =
            selectedStartable.length > 0 && selectedStartable.length < stoppable.length;
        selectAll.checked = selectedStartable.length === stoppable.length;
    } else if (selectAll) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
    }
}

/** Show POST /v1/modules/start per-module status pills. */
function renderInteropResult(response) {
    const box = el("interop-result");
    if (!box) return;

    const results = response.results || [];
    if (!results.length) {
        box.hidden = true;
        return;
    }

    box.hidden = false;
    box.innerHTML = `
        <h4>Start results</h4>
        <ul class="interop-result-list">
            ${results
                .map((r) => {
                    const pillClass = START_STATUS_PILL[r.status] || "neutral";
                    return `
                <li>
                    <span class="mono">${escHtml(r.moduleId)}</span>
                    <span class="pill ${pillClass}">${escHtml(r.status)}</span>
                    ${r.message ? `<span style="color:var(--c-label-secondary)">${escHtml(r.message)}</span>` : ""}
                </li>
            `;
                })
                .join("")}
        </ul>
    `;
}

/** Event delegation for row Start buttons and selection checkboxes. */
function setupInteropDelegation() {
    if (interopDelegationReady) return;
    interopDelegationReady = true;

    const section = el("section-interop");
    if (!section) return;

    section.addEventListener("click", (e) => {
        const startBtn = e.target.closest(".interop-start-one");
        if (startBtn && !startBtn.disabled) {
            e.preventDefault();
            const id = startBtn.dataset.id;
            if (id) startModules([id]);
        }
    });

    section.addEventListener("change", (e) => {
        const target = e.target;

        // Per-row checkbox toggles interopState.selectedIds.
        const rowCheck = target.closest?.(".interop-row-check");
        if (rowCheck && rowCheck.classList.contains("interop-row-check") && !rowCheck.disabled) {
            const id = rowCheck.dataset.id;
            if (!id) return;
            if (rowCheck.checked) interopState.selectedIds.add(id);
            else interopState.selectedIds.delete(id);
            updateInteropActionButtons(interopState.registry);
            return;
        }

        // Header checkbox selects all startable rows.
        if (target.id === "interop-select-all") {
            if (!interopState.registry) return;
            const running = getRunningIdSet(interopState.registry);
            interopState.selectedIds.clear();
            if (target.checked) {
                mergeInstalledRows(interopState.registry).forEach((m) => {
                    if (isStartableModule(m, running, interopState.callerId)) {
                        interopState.selectedIds.add(m.id);
                    }
                });
            }
            renderInstalledTable(interopState.registry);
        }
    });
}

/** Wire refresh, filter, bulk start, and auto-refresh timer (once). */
function setupInteropControls() {
    if (interopControlsReady) return;
    interopControlsReady = true;

    el("interop-refresh-btn")?.addEventListener("click", () => refreshInteropRegistry());

    el("interop-filter")?.addEventListener("input", (e) => {
        interopState.filter = e.target.value;
        if (interopState.registry) renderInstalledTable(interopState.registry);
    });

    el("interop-start-selected-btn")?.addEventListener("click", () => {
        startModules([...interopState.selectedIds]);
    });

    el("interop-start-stopped-btn")?.addEventListener("click", () => {
        if (!interopState.registry) return;
        const running = getRunningIdSet(interopState.registry);
        const ids = (interopState.registry.installedModules || [])
            .filter((m) => isStartableModule(m, running, interopState.callerId))
            .map((m) => m.id);
        startModules(ids);
    });

    el("interop-auto-refresh")?.addEventListener("change", async (e) => {
        if (interopState.autoRefreshTimer) {
            clearInterval(interopState.autoRefreshTimer);
            interopState.autoRefreshTimer = null;
        }
        if (e.target.checked) {
            const ms = await getInteropRefreshIntervalMs();
            interopState.autoRefreshTimer = setInterval(() => refreshInteropRegistry(), ms);
        }
    });
}

/** Proxy GET /api/interop and refresh installed/running tables + exchange log. */
async function refreshInteropRegistry() {
    const refreshBtn = el("interop-refresh-btn");
    if (refreshBtn) refreshBtn.disabled = true;

    try {
        const data = await fetchJson("/api/interop");
        if (!data.available) {
            renderInteropUnavailable(data);
            return;
        }

        showInteropAlert("", "info");
        interopState.registry = data;
        interopState.callerId = data.callerModuleId || interopState.callerId;

        // Reveal toolbar and panels after a successful registry fetch.
        el("interop-toolbar")?.removeAttribute("hidden");
        el("interop-panels")?.removeAttribute("hidden");

        updateInteropMeta(data);
        renderInstalledTable(data);
        renderRunningTable(data);

        if (data.hostExchange) {
            appendInteropExchange("GET /v1/registry → ASLM host", data.hostExchange);
        }

        if (el("interop-raw-json")) {
            el("interop-raw-json").textContent = JSON.stringify(data, null, 2);
        }
    } catch (err) {
        renderInteropUnavailable({ error: err.message });
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

/** POST /api/interop/start for the given module ids, then refresh registry. */
async function startModules(moduleIds) {
    if (!moduleIds.length) return;

    const startSelected = el("interop-start-selected-btn");
    const startStopped = el("interop-start-stopped-btn");
    if (startSelected) startSelected.disabled = true;
    if (startStopped) startStopped.disabled = true;

    showInteropAlert(`Starting: ${moduleIds.join(", ")}…`, "info");

    try {
        // Flask proxies to ASLM POST /v1/modules/start.
        const { ok, data: response } = await fetchJsonResponse("/api/interop/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ moduleIds }),
        });

        if (response.hostExchange) {
            appendInteropExchange("POST /v1/modules/start → ASLM host", response.hostExchange);
        }

        if (!ok) {
            const msg = response.error || response.message || `HTTP error`;
            const code =
                response.hostExchange?.responseBody?.code ||
                response.hostExchange?.responseBody?.message;
            throw new Error(code ? `${msg}: ${code}` : msg);
        }

        renderInteropResult(response);
        showInteropAlert("Start request completed.", "info");
        interopState.selectedIds.clear();
        await refreshInteropRegistry();
    } catch (err) {
        showInteropAlert(err.message, "error");
    } finally {
        updateInteropActionButtons(interopState.registry);
    }
}

/** Load API spec table and initial registry snapshot. */
async function loadInterop() {
    await loadInteropSpec();
    await refreshInteropRegistry();
}

// Boot

/** Load all dashboard sections in parallel after DOM ready. */
document.addEventListener("DOMContentLoaded", async () => {
    setupInteropControls();
    setupInteropDelegation();

    const sections = [
        { fn: loadInfo, label: "info" },
        { fn: loadSettings, label: "settings" },
        { fn: loadTheme, label: "theme" },
        { fn: loadLocale, label: "locale" },
        { fn: loadInterop, label: "interop" },
        { fn: loadDownloads, label: "downloads" },
    ];

    await Promise.all(
        sections.map(async ({ fn, label }) => {
            try {
                await fn();
            } catch (err) {
                console.error(`[ASLM-Example] ${label}:`, err);
            }
        })
    );
});
