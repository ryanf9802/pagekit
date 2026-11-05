/* pagekit export: copies every control's state as a block an agent can read. */
(function () {
  "use strict";
  var metaEl = document.getElementById("pagekit-meta");
  var meta = metaEl ? JSON.parse(metaEl.textContent) : {};
  var custom = {};
  var SELECTOR = "input, select, textarea, [contenteditable], details[id], details[data-pk-name]";
  var SKIP = { button: 1, submit: 1, reset: 1, image: 1, hidden: 1, password: 1 };
  var STORE_KEY = "pagekit:" + meta.profile + "/" + meta.slug + ":" + meta.rev;
  var labelTimer;

  function nameOf(el) {
    return el.getAttribute("data-pk-name") || el.getAttribute("name") || el.id || "";
  }

  function elements() {
    return Array.prototype.filter.call(document.querySelectorAll(SELECTOR), function (el) {
      if (el.closest("[data-pk-ignore]") || !nameOf(el)) return false;
      if (el.tagName === "INPUT" && SKIP[el.type]) return false;
      if (el.hasAttribute("contenteditable") && el.getAttribute("contenteditable") === "false") return false;
      return true;
    });
  }

  function collect() {
    var names = [];
    var values = {};
    var boxes = {};
    function ensure(name, value) {
      if (!(name in values)) {
        names.push(name);
        values[name] = value;
      }
    }
    elements().forEach(function (el) {
      var name = nameOf(el);
      if (el.tagName === "DETAILS") {
        ensure(name, el.open ? "open" : "closed");
      } else if (el.hasAttribute("contenteditable")) {
        ensure(name, el.innerText.trim());
      } else if (el.type === "radio") {
        ensure(name, "");
        if (el.checked) values[name] = el.value;
      } else if (el.type === "checkbox") {
        ensure(name, "");
        (boxes[name] = boxes[name] || []).push(el);
      } else if (el.type === "file") {
        ensure(name, Array.prototype.map.call(el.files, function (f) { return f.name; }).join(", "));
      } else if (el.multiple && el.tagName === "SELECT") {
        ensure(name, Array.prototype.map.call(el.selectedOptions, function (o) { return o.value; }).join(", "));
      } else {
        ensure(name, el.value);
      }
    });
    Object.keys(boxes).forEach(function (name) {
      var group = boxes[name];
      values[name] = group.length === 1
        ? String(group[0].checked)
        : group.filter(function (b) { return b.checked; }).map(function (b) { return b.value; }).join(", ");
    });
    Object.keys(custom).forEach(function (name) {
      var value;
      try {
        value = custom[name]();
      } catch (err) {
        value = "(error: " + err.message + ")";
      }
      if (name in values === false) names.push(name);
      values[name] = typeof value === "string" ? value : JSON.stringify(value);
    });
    return names.map(function (name) { return [name, values[name]]; });
  }

  function line(key, value) {
    value = String(value == null ? "" : value);
    if (value.indexOf("\n") === -1) return value ? key + ": " + value : key + ":";
    return key + ": |\n" + value.split("\n").map(function (l) { return "    " + l; }).join("\n");
  }

  function text() {
    var fields = collect();
    var body = [
      line("page", meta.slug),
      line("title", meta.title),
      line("profile", meta.profile),
      line("source", meta.source),
      line("built", meta.built),
      "fields:" + (fields.length ? "" : " none"),
    ].concat(fields.map(function (f) { return "  " + line(f[0], f[1]); })).join("\n");
    var longest = (body.match(/`+/g) || []).reduce(function (n, run) { return Math.max(n, run.length); }, 2);
    var fence = new Array(longest + 2).join("`");
    return fence + "pagekit-response\n" + body + "\n" + fence;
  }

  /* The button itself shows the result, so the footer never shifts. */
  function status(message, label, done) {
    var el = document.getElementById("pk-export-status");
    var labelEl = document.getElementById("pk-export-label");
    var button = document.getElementById("pk-export");
    if (el) el.textContent = message;
    if (!labelEl || !button) return;
    var original = labelEl.getAttribute("data-label") || labelEl.textContent;
    labelEl.setAttribute("data-label", original);
    labelEl.textContent = label;
    button.classList.toggle("pk-button-done", !!done);
    clearTimeout(labelTimer);
    labelTimer = setTimeout(function () {
      labelEl.textContent = original;
      button.classList.remove("pk-button-done");
    }, 2500);
  }

  function legacyCopy(value) {
    var area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("data-pk-ignore", "");
    area.className = "pk-export-fallback";
    document.body.appendChild(area);
    area.select();
    var copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (err) {
      copied = false;
    }
    if (copied) {
      area.remove();
    } else {
      /* Leave it on screen, selected, so nothing is lost. */
      area.classList.add("pk-export-fallback-visible");
      status("Clipboard blocked: copy the selected text.", "Clipboard blocked: copy the text");
    }
    return copied;
  }

  function copied() {
    var count = collect().length;
    var fields = count + (count === 1 ? " field" : " fields");
    status("Copied " + fields + ". Paste it into Claude Code.", "Copied " + fields + ", paste into Claude", true);
  }

  function copy() {
    var value = text();
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(value).then(copied, function () {
        if (legacyCopy(value)) copied();
      });
    }
    if (legacyCopy(value)) copied();
    return Promise.resolve();
  }

  /* Answers survive a reload and a restyle. Changed content is a new round, so it starts clean. */
  function persist() {
    var state = {};
    elements().forEach(function (el) {
      var name = nameOf(el);
      if (el.tagName === "DETAILS") state[name] = el.open;
      else if (el.hasAttribute("contenteditable")) state[name] = el.innerHTML;
      else if (el.type === "radio" || el.type === "checkbox") state[name + "|" + el.value] = el.checked;
      else if (el.multiple && el.tagName === "SELECT") {
        state[name] = Array.prototype.map.call(el.selectedOptions, function (o) { return o.value; });
      } else if (el.type !== "file") state[name] = el.value;
    });
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(state));
    } catch (err) {
      /* Storage can be blocked; the page still works. */
    }
  }

  function restore() {
    var state;
    try {
      state = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    } catch (err) {
      return;
    }
    if (!state) return;
    elements().forEach(function (el) {
      var name = nameOf(el);
      if (el.tagName === "DETAILS") {
        if (name in state) el.open = state[name];
        return;
      }
      if (el.hasAttribute("contenteditable")) {
        if (name in state) el.innerHTML = state[name];
        return;
      }
      if (el.type === "radio" || el.type === "checkbox") {
        var key = name + "|" + el.value;
        if (key in state) el.checked = state[key];
      } else if (el.multiple && el.tagName === "SELECT") {
        if (name in state) {
          Array.prototype.forEach.call(el.options, function (o) { o.selected = state[name].indexOf(o.value) !== -1; });
        }
      } else if (el.type !== "file" && name in state) {
        el.value = state[name];
      }
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  window.pagekit = {
    /* For bespoke widgets: pagekit.register("order", function () { return ids; }). */
    register: function (name, getter) { custom[name] = getter; },
    collect: collect,
    text: text,
    copy: copy,
  };

  restore();
  document.addEventListener("input", persist);
  document.addEventListener("change", persist);
  document.addEventListener("toggle", persist, true);
  document.addEventListener("submit", function (event) { event.preventDefault(); });
  var button = document.getElementById("pk-export");
  if (button) button.addEventListener("click", copy);

  /* The header shows the page title once the main heading has scrolled away. */
  var heading = document.querySelector("h1");
  if (heading && window.IntersectionObserver) {
    new IntersectionObserver(function (entries) {
      document.body.classList.toggle("pk-scrolled", !entries[0].isIntersecting);
    }, { rootMargin: "-60px 0px 0px 0px" }).observe(heading);
  }
})();
