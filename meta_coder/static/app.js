// Dropzone behavior for file inputs. Progressive enhancement: each dropzone is a
// <label> wrapping a real <input type="file">, so click-to-browse works with no JS
// at all. Choosing or dropping a file submits the zone's form immediately — no
// separate upload button — via requestSubmit() so any onsubmit confirm() dialog
// and native required-field validation still run (unlike the older .submit()).
(function () {
  function updateLabel(input, zone) {
    var preview = zone.querySelector("[data-dropzone-filename]");
    if (!preview) return;
    var files = input.files;
    if (!files || files.length === 0) {
      preview.textContent = "";
    } else if (files.length === 1) {
      preview.textContent = files[0].name;
    } else {
      preview.textContent = files.length + " files selected";
    }
  }

  function filesChosen(input, zone) {
    updateLabel(input, zone);
    if (!input.files || !input.files.length) return;
    var form = zone.closest("form");
    if (form) form.requestSubmit();
  }

  document.querySelectorAll("[data-dropzone]").forEach(function (zone) {
    var input = zone.querySelector('input[type="file"]');
    if (!input) return;

    updateLabel(input, zone);
    input.addEventListener("change", function () {
      filesChosen(input, zone);
    });

    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add("border-primary", "bg-primary/5");
      });
    });

    ["dragleave", "dragend", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove("border-primary", "bg-primary/5");
      });
    });

    zone.addEventListener("drop", function (e) {
      var files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length) {
        input.files = files;
        filesChosen(input, zone);
      }
    });
  });
})();

// Structured coding-manual editor. The manual is only ever edited through this
// UI — see plan.md "Problem 1": "I do not want the user to edit the yaml schema
// directly". This module renders form controls bound to an in-memory JS object
// (seeded from the server) and, on submit, serializes that object to JSON into a
// hidden field; the server rebuilds the CodingManual and writes the YAML file —
// this script never generates YAML itself.
(function () {
  var dataEl = document.getElementById("manual-editor-data");
  if (!dataEl) return; // manual couldn't be loaded — reset-to-default UI shown instead

  var state = JSON.parse(dataEl.textContent);
  state.effects = state.effects || [];

  // Matches meta_coder/manual.py's NOTES_FIELD_NAME — the server forces this
  // field onto every manual and discards any edits to it, so the editor locks
  // it too rather than letting a user "successfully" edit something that gets
  // silently reverted on save.
  var RESERVED_EFFECT_FIELD_NAME = "notes";

  function cloneTemplate(id) {
    return document.getElementById(id).content.firstElementChild.cloneNode(true);
  }

  function bindText(container, key, obj, multiline) {
    var input = container.querySelector('[data-field="' + key + '"]');
    if (!input) return;
    input.value = obj[key] == null ? "" : obj[key];
    input.addEventListener("input", function () {
      obj[key] = input.value;
    });
  }

  function bindCheckbox(container, key, obj, defaultValue) {
    var input = container.querySelector('[data-field="' + key + '"]');
    if (!input) return;
    input.checked = obj[key] === undefined ? defaultValue : !!obj[key];
    obj[key] = input.checked;
    input.addEventListener("change", function () {
      obj[key] = input.checked;
    });
  }

  function renderLevel(field, level, listEl) {
    var row = cloneTemplate("tmpl-level");
    bindText(row, "value", level);
    bindText(row, "description", level);
    row.querySelector("[data-remove-row]").addEventListener("click", function () {
      var idx = field.levels.indexOf(level);
      if (idx >= 0) field.levels.splice(idx, 1);
      row.remove();
    });
    listEl.appendChild(row);
  }

  // `openByDefault` is true only for a field just added this session — a manual
  // with dozens of fields (a real coding manual easily has 30+) should load with
  // every field collapsed, not one huge scroll of open blocks.
  function renderEffectField(field, openByDefault) {
    field.levels = field.levels || [];
    var block = cloneTemplate("tmpl-effect-field");
    var locked = field.name === RESERVED_EFFECT_FIELD_NAME;
    if (openByDefault) block.open = true;

    var summaryName = block.querySelector("[data-summary-name]");
    var summaryType = block.querySelector("[data-summary-type]");
    function syncSummary() {
      summaryName.textContent = field.name || "Untitled field";
      summaryType.textContent = field.type || "string";
    }

    bindText(block, "name", field);
    block.querySelector('[data-field="name"]').addEventListener("input", syncSummary);
    bindText(block, "description", field);
    bindCheckbox(block, "evidence_required", field, true);

    var typeSelect = block.querySelector('[data-field="type"]');
    typeSelect.value = field.type || "string";
    field.type = typeSelect.value;
    var levelsSection = block.querySelector("[data-levels-section]");
    var levelsList = block.querySelector("[data-levels-list]");

    function refreshLevelsVisibility() {
      if (typeSelect.value === "string") {
        levelsSection.classList.remove("hidden");
      } else {
        levelsSection.classList.add("hidden");
        field.levels = [];
        levelsList.innerHTML = "";
      }
    }

    typeSelect.addEventListener("change", function () {
      field.type = typeSelect.value;
      refreshLevelsVisibility();
      syncSummary();
    });

    field.levels.forEach(function (level) {
      renderLevel(field, level, levelsList);
    });
    refreshLevelsVisibility();
    syncSummary();

    var addLevelBtn = block.querySelector("[data-add-level]");
    addLevelBtn.addEventListener("click", function () {
      var level = { value: "", description: "" };
      field.levels.push(level);
      renderLevel(field, level, levelsList);
    });

    var removeBtn = block.querySelector("[data-remove-row]");
    if (locked) {
      [
        block.querySelector('[data-field="name"]'),
        block.querySelector('[data-field="description"]'),
        block.querySelector('[data-field="evidence_required"]'),
        typeSelect,
        addLevelBtn,
      ].forEach(function (el) {
        el.disabled = true;
      });
      levelsSection.classList.add("hidden");
      removeBtn.remove();

      var lockBadge = document.createElement("span");
      lockBadge.className = "badge badge-ghost badge-sm ml-2";
      lockBadge.textContent = "auto";
      summaryType.insertAdjacentElement("afterend", lockBadge);

      var lockNote = document.createElement("p");
      lockNote.className = "text-xs text-base-content/50 mt-2";
      lockNote.textContent =
        "Added automatically to every coding manual — the model uses it to explain " +
        "any issues it had coding this row. Can't be edited or removed.";
      block.querySelector(".collapse-content").appendChild(lockNote);
    } else {
      removeBtn.addEventListener("click", function (e) {
        e.preventDefault(); // inside a <summary> — don't toggle collapse on remove
        var idx = state.effects.indexOf(field);
        if (idx >= 0) state.effects.splice(idx, 1);
        block.remove();
      });
    }

    return block;
  }

  var effectsList = document.getElementById("effect-fields-list");

  document.getElementById("add-effect-field").addEventListener("click", function () {
    var field = { name: "", type: "string", evidence_required: true, description: "", levels: [] };
    state.effects.push(field);
    effectsList.appendChild(renderEffectField(field, true));
  });

  ["name", "description", "effect_definition"].forEach(function (key) {
    var input = document.getElementById("manual-" + key.replace(/_/g, "-"));
    if (!input) return;
    input.addEventListener("input", function () {
      state[key] = input.value;
    });
  });

  function replaceManualState(nextState) {
    state = nextState || {};
    state.effects = state.effects || [];
    effectsList.innerHTML = "";
    state.effects.forEach(function (field) {
      effectsList.appendChild(renderEffectField(field, false));
    });
    ["name", "description", "effect_definition"].forEach(function (key) {
      var input = document.getElementById("manual-" + key.replace(/_/g, "-"));
      if (input) input.value = state[key] || "";
    });
  }

  replaceManualState(state);

  var form = document.getElementById("manual-form");
  var hiddenInput = document.getElementById("manual-json-input");
  if (form) {
    form.addEventListener("submit", function () {
      hiddenInput.value = JSON.stringify(state);
    });
  }

  // PDF/DOCX drafting stays on this page: the generic dropzone above triggers
  // requestSubmit(), this handler uploads with fetch, and the validated candidate
  // replaces only the editor's in-memory state. The saved YAML remains untouched
  // until the user submits `manual-form`.
  var draftForm = document.getElementById("manual-draft-form");
  if (draftForm) {
    var draftInput = draftForm.querySelector('input[type="file"]');
    var draftZone = draftForm.querySelector("[data-dropzone]");
    var draftStatus = document.getElementById("manual-draft-status");
    var drafting = false;

    function showDraftStatus(kind, message) {
      if (!draftStatus) return;
      draftStatus.className = "alert alert-" + kind + " mt-2";
      draftStatus.textContent = message;
    }

    draftForm.addEventListener("submit", function (event) {
      event.preventDefault();
      if (drafting || !draftInput || !draftInput.files || !draftInput.files.length) return;
      drafting = true;
      var draftData = new FormData(draftForm);
      draftInput.disabled = true;
      if (draftZone) draftZone.setAttribute("aria-busy", "true");
      showDraftStatus("info", "Uploading and drafting the coding manual… This may take a minute.");

      fetch(draftForm.action, { method: "POST", body: draftData })
        .then(function (response) {
          return response.text().then(function (text) {
            var payload;
            try {
              payload = JSON.parse(text);
            } catch (_error) {
              payload = {};
            }
            if (!response.ok) {
              throw new Error(payload.error || payload.detail || "The coding-manual draft failed.");
            }
            return payload;
          });
        })
        .then(function (payload) {
          replaceManualState(payload.manual);

          var badge = document.getElementById("manual-status-badge");
          if (badge) {
            badge.className = "badge badge-info";
            badge.textContent = "Draft · not saved";
          }
          var sidebarBadge = document.getElementById("manual-sidebar-status");
          if (sidebarBadge) sidebarBadge.className = "badge badge-info badge-xs ml-auto";

          var notice = document.getElementById("manual-draft-notice");
          if (notice) {
            notice.classList.remove("hidden");
            var filename = notice.querySelector("[data-manual-draft-filename]");
            if (filename) filename.textContent = payload.filename || "manual document";
          }
          var incompleteWarning = document.getElementById("manual-incomplete-warning");
          if (incompleteWarning) incompleteWarning.classList.add("hidden");

          var saveButton = document.getElementById("manual-save-button");
          if (saveButton) saveButton.textContent = "Validate and save draft";
          var yamlKind = document.getElementById("manual-yaml-kind");
          if (yamlKind) yamlKind.textContent = "drafted";
          var yamlPreview = document.getElementById("manual-yaml-preview");
          if (yamlPreview) yamlPreview.textContent = payload.yaml || "";

          document.querySelectorAll("[data-requires-saved-manual]").forEach(function (button) {
            button.disabled = true;
          });
          var runWarning = document.getElementById("manual-draft-run-warning");
          if (runWarning) runWarning.classList.remove("hidden");

          showDraftStatus(
            "success",
            "Draft ready from " + (payload.filename || "the uploaded document") +
              ". Review it below; it has not been saved yet."
          );
        })
        .catch(function (error) {
          showDraftStatus("error", error.message || "The coding-manual draft failed.");
        })
        .finally(function () {
          drafting = false;
          draftInput.disabled = false;
          draftInput.value = "";
          if (draftZone) draftZone.removeAttribute("aria-busy");
          var filenamePreview = draftZone && draftZone.querySelector("[data-dropzone-filename]");
          if (filenamePreview) filenamePreview.textContent = "";
        });
    });
  }
})();

// Generic tab switching, reused for both the project page's sidebar and the
// coding manual's Metadata/Coding sheet fields/Effect fields sub-tabs. Every
// tab's content is already server-rendered on the page (no fetch/partial-load)
// — this just shows one panel at a time within `root`.
function initTabGroup(root, opts) {
  if (!root) return;
  var panels = root.querySelectorAll("[" + opts.panelAttr + "]");
  var links = root.querySelectorAll("[" + opts.linkAttr + "]");
  if (!panels.length) return;

  function activate(tab) {
    var match = null;
    panels.forEach(function (panel) {
      if (panel.getAttribute(opts.panelAttr) === tab) match = panel;
    });
    if (!match) match = panels[0];
    tab = match.getAttribute(opts.panelAttr);
    panels.forEach(function (panel) {
      panel.classList.toggle("hidden", panel !== match);
    });
    links.forEach(function (link) {
      link.classList.toggle(opts.activeClass, link.getAttribute(opts.linkAttr) === tab);
    });
    if (tab && opts.storageKey) {
      try {
        sessionStorage.setItem(opts.storageKey, tab);
      } catch (e) {
        /* private browsing / storage disabled — tab memory just won't persist */
      }
    }
  }

  links.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      activate(link.getAttribute(opts.linkAttr));
    });
  });

  // A server-forced tab (e.g. a validation error on this exact response) always
  // wins over whatever was remembered from before.
  var remembered = null;
  if (opts.storageKey) {
    try {
      remembered = sessionStorage.getItem(opts.storageKey);
    } catch (e) {
      /* ignore */
    }
  }
  activate(opts.forceTab || remembered || links[0] && links[0].getAttribute(opts.linkAttr));
}

// Live run progress: polls the /status JSON endpoint (already existed for the
// old <meta http-equiv="refresh"> era's status-line; nothing previously read
// it client-side) instead of reloading the whole page every 2s. Only updates
// rows already present in the DOM — sort/pagination stay server-rendered, so a
// PDF on another page of the run table just won't visibly update until the
// page reloads at the end of the run.
(function () {
  var root = document.getElementById("run-progress");
  if (!root || root.dataset.running !== "true") return;

  var statusUrl = root.dataset.statusUrl;
  var bar = root.querySelector("[data-progress-bar]");
  var summary = root.querySelector("[data-progress-summary]");
  var rowsByPdf = {};
  root.querySelectorAll("[data-run-row]").forEach(function (tr) {
    rowsByPdf[tr.getAttribute("data-run-row")] = tr;
  });

  var STATUS_BADGE = {
    ok: '<span class="badge badge-success">ok</span>',
    needs_review: '<span class="badge badge-warning">needs review</span>',
    error: '<span class="badge badge-error">error</span>',
    running: '<span class="badge badge-info">running</span>',
    cancelled: '<span class="badge badge-ghost">cancelled</span>',
    pending: '<span class="badge badge-ghost">pending</span>',
  };

  function applySnapshot(data) {
    if (bar) {
      bar.max = data.total || 1;
      bar.value = data.processed || 0;
    }
    if (summary) {
      summary.textContent = data.processed + " / " + data.total + " PDFs processed — " + data.status;
    }
    (data.pdfs || []).forEach(function (pdf) {
      var tr = rowsByPdf[pdf.source_pdf];
      if (!tr) return;
      var statusCell = tr.querySelector("[data-run-status-cell]");
      if (statusCell) {
        var badge = STATUS_BADGE[pdf.status] || pdf.status;
        if (pdf.status === "ok" && pdf.json_repaired) badge = badge.replace("</span>", " · repaired</span>");
        statusCell.innerHTML = badge;
      }
      var inTok = tr.querySelector("[data-run-input-tokens]");
      if (inTok) inTok.textContent = pdf.input_tokens != null ? pdf.input_tokens : "—";
      var outTok = tr.querySelector("[data-run-output-tokens]");
      if (outTok) outTok.textContent = pdf.output_tokens != null ? pdf.output_tokens : "—";
      var detail = tr.querySelector("[data-run-detail]");
      if (detail) {
        var parts = [];
        if (pdf.error) parts.push(pdf.error);
        if (pdf.missing_ids && pdf.missing_ids.length) parts.push("missing: " + pdf.missing_ids.join(", "));
        if (pdf.extra_ids && pdf.extra_ids.length) parts.push("unexpected: " + pdf.extra_ids.join(", "));
        detail.textContent = parts.join(" ");
      }
    });
  }

  function poll() {
    fetch(statusUrl, { headers: { Accept: "application/json" } })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        applySnapshot(data);
        if (data.status === "running" || data.status === "cancelling") {
          setTimeout(poll, 1500);
        } else {
          // Terminal state reached (complete/failed/cancelled) — reload once
          // to pick up the freshly server-rendered table (correct sort/paging,
          // retry buttons, the Results tab appearing, etc.) rather than trying
          // to replicate all of that in JS.
          window.location.reload();
        }
      })
      .catch(function () {
        setTimeout(poll, 3000); // transient fetch failure — keep trying
      });
  }

  setTimeout(poll, 1000);
})();

(function () {
  var provider = document.getElementById("run-provider");
  if (!provider) return;

  function updateProviderSettings() {
    document.querySelectorAll("[data-provider-setting]").forEach(function (setting) {
      setting.hidden = setting.getAttribute("data-provider-setting") !== provider.value;
    });
  }

  provider.addEventListener("change", updateProviderSettings);
  updateProviderSettings();
})();

(function () {
  var tabRoot = document.getElementById("tab-root");
  if (tabRoot) {
    // Sidebar-level tabs survive this app's full-page-reload actions (form
    // submits, the in-progress-run auto-refresh) without any server plumbing —
    // remembered per project so switching projects doesn't leak the tab choice.
    initTabGroup(tabRoot, {
      linkAttr: "data-tab-link",
      panelAttr: "data-tab-panel",
      activeClass: "menu-active",
      storageKey: "metaCoderActiveTab:" + (tabRoot.dataset.projectId || "default"),
      forceTab: tabRoot.dataset.forceTab,
    });
  }

  var manualSubtabs = document.getElementById("manual-subtabs");
  if (manualSubtabs) {
    initTabGroup(manualSubtabs, {
      linkAttr: "data-subtab-link",
      panelAttr: "data-subtab-panel",
      activeClass: "tab-active",
      storageKey: "metaCoderManualSubtab:" + (tabRoot ? tabRoot.dataset.projectId : "default"),
    });
  }
})();
