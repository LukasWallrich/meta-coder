// Dropzone behavior for file inputs. Progressive enhancement: each dropzone is a
// <label> wrapping a real <input type="file">, so click-to-browse works with no JS
// at all — this script only adds drag-and-drop and the chosen-filename preview.
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

  document.querySelectorAll("[data-dropzone]").forEach(function (zone) {
    var input = zone.querySelector('input[type="file"]');
    if (!input) return;

    updateLabel(input, zone);
    input.addEventListener("change", function () {
      updateLabel(input, zone);
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
        updateLabel(input, zone);
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
  state.coding_sheet_fields = state.coding_sheet_fields || [];
  state.effects = state.effects || [];

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

  function renderCodingSheetField(field) {
    var row = cloneTemplate("tmpl-coding-sheet-field");
    bindText(row, "name", field);
    row.querySelector('[data-field="type"]').value = field.type || "string";
    row.querySelector('[data-field="type"]').addEventListener("change", function (e) {
      field.type = e.target.value;
    });
    bindText(row, "description", field);
    row.querySelector("[data-remove-row]").addEventListener("click", function () {
      var idx = state.coding_sheet_fields.indexOf(field);
      if (idx >= 0) state.coding_sheet_fields.splice(idx, 1);
      row.remove();
    });
    return row;
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

  function renderEffectField(field) {
    field.levels = field.levels || [];
    var block = cloneTemplate("tmpl-effect-field");
    bindText(block, "name", field);
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
    });

    field.levels.forEach(function (level) {
      renderLevel(field, level, levelsList);
    });
    refreshLevelsVisibility();

    block.querySelector("[data-add-level]").addEventListener("click", function () {
      var level = { value: "", description: "" };
      field.levels.push(level);
      renderLevel(field, level, levelsList);
    });

    block.querySelector("[data-remove-row]").addEventListener("click", function () {
      var idx = state.effects.indexOf(field);
      if (idx >= 0) state.effects.splice(idx, 1);
      block.remove();
    });

    return block;
  }

  var codingSheetList = document.getElementById("coding-sheet-fields-list");
  var effectsList = document.getElementById("effect-fields-list");

  state.coding_sheet_fields.forEach(function (f) {
    codingSheetList.appendChild(renderCodingSheetField(f));
  });
  state.effects.forEach(function (f) {
    effectsList.appendChild(renderEffectField(f));
  });

  document.getElementById("add-coding-sheet-field").addEventListener("click", function () {
    var field = { name: "", type: "string", description: "" };
    state.coding_sheet_fields.push(field);
    codingSheetList.appendChild(renderCodingSheetField(field));
  });

  document.getElementById("add-effect-field").addEventListener("click", function () {
    var field = { name: "", type: "string", required: false, evidence_required: true, description: "", levels: [] };
    state.effects.push(field);
    effectsList.appendChild(renderEffectField(field));
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
