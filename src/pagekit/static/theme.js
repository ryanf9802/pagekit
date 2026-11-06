/* pagekit theme: follow the system's light or dark setting, or let the reader choose one.
   A page's dark values live in `@media screen and (prefers-color-scheme: dark)`, so a choice works by switching
   those media rules on or off. That covers any profile's theme with no second copy of it, and printing, which
   is never dark, is unaffected. */
(function () {
  "use strict";
  var KEY = "pagekit:theme";
  var MODES = ["system", "light", "dark"];
  var LABELS = { system: "Theme: follows system", light: "Theme: light", dark: "Theme: dark" };
  var ICONS = {
    system: '<i data-icon="monitor"></i>',
    light: '<i data-icon="sun"></i>',
    dark: '<i data-icon="moon"></i>',
  };
  var QUERY = /\(\s*prefers-color-scheme\s*:\s*(light|dark)\s*\)/i;
  var originals = new WeakMap();
  var schemeStyle = null;
  var button = null;

  function stored() {
    try {
      var value = localStorage.getItem(KEY);
      return value === "light" || value === "dark" ? value : "system";
    } catch (err) {
      return "system";
    }
  }

  function save(mode) {
    try {
      if (mode === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, mode);
    } catch (err) {
      /* The choice lasts until the page is closed. */
    }
  }

  /* The media query to use for a rule that was written as `original`, with the reader's choice applied. */
  function forced(original, mode) {
    var match = QUERY.exec(original);
    if (!match || mode === "system") return original;
    if (match[1].toLowerCase() !== mode) return "not all";
    /* The preference holds, so drop it and keep the rest, such as "screen". */
    var rest = original.replace(QUERY, "").replace(/\s+and\s*$/i, "").replace(/^\s*and\s+/i, "").trim();
    return rest || "all";
  }

  function eachMediaRule(rules, fn) {
    Array.prototype.forEach.call(rules, function (rule) {
      if (window.CSSMediaRule && rule instanceof window.CSSMediaRule) fn(rule);
      if (rule.cssRules) eachMediaRule(rule.cssRules, fn);
    });
  }

  function apply(mode) {
    Array.prototype.forEach.call(document.styleSheets, function (sheet) {
      var rules;
      try {
        rules = sheet.cssRules;
      } catch (err) {
        return; /* A sheet from another site cannot be read. */
      }
      eachMediaRule(rules, function (rule) {
        if (!originals.has(rule)) originals.set(rule, rule.media.mediaText);
        var original = originals.get(rule);
        var next = forced(original, mode);
        if (rule.media.mediaText !== next) rule.media.mediaText = next;
      });
    });
    /* The logo can have a dark version, chosen by the same preference. */
    Array.prototype.forEach.call(document.querySelectorAll("source[media]"), function (source) {
      if (!originals.has(source)) originals.set(source, source.getAttribute("media"));
      source.setAttribute("media", forced(originals.get(source), mode));
    });
    /* Browser-drawn parts, such as form controls and scrollbars. Screen only, because print is always light. */
    if (!schemeStyle) {
      schemeStyle = document.createElement("style");
      document.head.appendChild(schemeStyle);
    }
    schemeStyle.textContent = mode === "system" ? "" : "@media screen { :root { color-scheme: " + mode + "; } }";
    if (mode === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", mode);
    window.dispatchEvent(new CustomEvent("pagekit:theme", { detail: mode }));
  }

  function show(mode) {
    if (!button) return;
    button.innerHTML = ICONS[mode];
    button.setAttribute("data-label", LABELS[mode]);
    button.setAttribute("aria-label", LABELS[mode]);
  }

  var current = stored();
  if (current !== "system") apply(current);

  document.addEventListener("DOMContentLoaded", function () {
    /* The logo and the header are parsed by now. */
    if (current !== "system") apply(current);
    var bar = document.querySelector(".pk-header .pk-bar");
    if (!bar) return;
    button = document.createElement("button");
    button.type = "button";
    button.className = "pk-theme";
    /* First among the header controls. The others are added after it, or before the page index link. */
    bar.insertBefore(button, bar.querySelector(".pk-pdf, .pk-home"));
    show(current);
    button.addEventListener("click", function () {
      current = MODES[(MODES.indexOf(current) + 1) % MODES.length];
      save(current);
      apply(current);
      show(current);
    });
  });

  /* A choice made in another tab applies here too. */
  window.addEventListener("storage", function (event) {
    if (event.key !== KEY && event.key !== null) return;
    current = stored();
    apply(current);
    show(current);
  });
})();
