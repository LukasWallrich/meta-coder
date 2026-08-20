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
    bindCheckbox(block, "required", field, false);
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
        block.querySelector('[data-field="required"]'),
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

  state.effects.forEach(function (f) {
    effectsList.appendChild(renderEffectField(f, false));
  });

  document.getElementById("add-effect-field").addEventListener("click", function () {
    var field = { name: "", type: "string", required: false, evidence_required: true, description: "", levels: [] };
    state.effects.push(field);
    effectsList.appendChild(renderEffectField(field, true));
  });

  ["name", "description", "effect_definition"].forEach(function (key) {
    var input = document.getElementById("manual-" + key.replace(/_/g, "-"));
    if (!input) return;
    input.value = state[key] || "";
    input.addEventListener("input", function () {
      state[key] = input.value;
    });
  });

  var form = document.getElementById("manual-form");
  var hiddenInput = document.getElementById("manual-json-input");
  if (form) {
    form.addEventListener("submit", function () {
      hiddenInput.value = JSON.stringify(state);
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
