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
  var narrowScreen = window.matchMedia("(max-width: 640px)");

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

  function collect(skipDetails) {
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
        if (!skipDetails) ensure(name, el.open ? "open" : "closed");
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
    ].concat(fields.map(function (f) { return "  " + line(f[0], f[1]); }));
    var ids = commentedIds();
    if (ids.length) {
      body = body.concat("comments:", ids.map(function (id) { return "  " + line(id, comments[id]); }));
    }
    body = body.join("\n");
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
    markCopied();
    var count = collect().length;
    var fields = count + (count === 1 ? " field" : " fields");
    var notes = commentedIds().length;
    var summary = notes ? fields + ", " + notes + (notes === 1 ? " comment" : " comments") : fields;
    status("Copied " + summary + ".", "Copied " + summary, true);
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
  function snapshot() {
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
    return state;
  }

  function persist() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(snapshot()));
    } catch (err) {
      /* Storage can be blocked; the page still works. */
    }
  }

  function restore() {
    /* A generated PDF has no browser storage, so the server hands it the answers directly. */
    var state = window.pagekitPrintState || null;
    try {
      state = state || JSON.parse(localStorage.getItem(STORE_KEY) || "null");
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

  /* Browsers without CSS field-sizing still get text boxes that grow as you type. */
  function fitTextarea(area) {
    if (area.tagName !== "TEXTAREA" || (window.CSS && CSS.supports("field-sizing", "content"))) return;
    area.style.height = "auto";
    var border = area.offsetHeight - area.clientHeight;
    area.style.height = area.scrollHeight + border + "px";
  }

  /* Comments on item IDs: any .pk-id opens a floating box. Stored like answers, so changed
     content resets them too. The same ID appearing twice shares one comment. */
  var COMMENT_KEY = STORE_KEY + ":comments";
  var comments = {};
  var commentBox = null;
  var commentArea = null;
  var commentTitle = null;
  var commentAnchor = null;
  var commentCount = null;

  function idMarks() {
    return Array.prototype.slice.call(document.querySelectorAll(".pk-id"));
  }

  function idOf(el) {
    return el.textContent.trim();
  }

  function commentedIds() {
    var ordered = [];
    idMarks().forEach(function (el) {
      var id = idOf(el);
      if (comments[id] && ordered.indexOf(id) === -1) ordered.push(id);
    });
    return ordered;
  }

  /* The copy button shows only when there is something to copy. Opening a section is not an
     answer, so details do not count. */
  function hasState() {
    return Object.keys(custom).length > 0 || commentedIds().length > 0 ||
      elements().some(function (el) { return el.tagName !== "DETAILS"; });
  }

  function refreshExportButton() {
    var exportButton = document.getElementById("pk-export");
    if (exportButton) exportButton.hidden = !!meta.readonly || !hasState();
  }

  function refreshComments() {
    refreshExportButton();
    idMarks().forEach(function (el) {
      var has = !!comments[idOf(el)];
      el.classList.toggle("pk-has-comment", has);
      el.setAttribute("aria-label", (has ? "Edit comment on " : "Comment on ") + idOf(el));
    });
    if (!commentCount) return;
    var count = commentedIds().length;
    commentCount.hidden = !count;
    commentCount.textContent = count + (count === 1 ? " comment" : " comments");
  }

  function saveComments() {
    try {
      localStorage.setItem(COMMENT_KEY, JSON.stringify(comments));
    } catch (err) {
      /* Storage can be blocked; comments still export until the page closes. */
    }
  }

  function closeComment(returnFocus) {
    if (!commentBox || commentBox.hidden) return;
    commentBox.hidden = true;
    if (returnFocus && commentAnchor) commentAnchor.focus();
  }

  function buildCommentBox() {
    commentBox = document.createElement("div");
    commentBox.className = "pk-comment";
    commentBox.hidden = true;
    commentBox.setAttribute("data-pk-ignore", "");
    commentBox.setAttribute("role", "dialog");
    var head = document.createElement("div");
    head.className = "pk-comment-head";
    commentTitle = document.createElement("span");
    commentTitle.className = "pk-comment-title";
    var done = document.createElement("button");
    done.type = "button";
    done.className = "pk-comment-done";
    done.textContent = "Done";
    done.addEventListener("click", function () { closeComment(true); });
    head.appendChild(commentTitle);
    head.appendChild(done);
    commentArea = document.createElement("textarea");
    commentArea.placeholder = "Add a comment";
    commentArea.addEventListener("input", function () {
      var id = idOf(commentAnchor);
      var value = commentArea.value.trim();
      if (value) comments[id] = value;
      else delete comments[id];
      saveComments();
      refreshComments();
    });
    commentArea.addEventListener("keydown", function (event) {
      if (event.key === "Escape" || (event.key === "Enter" && (event.ctrlKey || event.metaKey))) {
        event.preventDefault();
        closeComment(true);
      }
    });
    commentBox.appendChild(head);
    commentBox.appendChild(commentArea);
    document.body.appendChild(commentBox);
  }

  function openComment(el) {
    if (!commentBox) buildCommentBox();
    commentAnchor = el;
    var id = idOf(el);
    commentTitle.textContent = "Comment on " + id;
    commentBox.setAttribute("aria-label", "Comment on " + id);
    commentArea.value = comments[id] || "";
    commentArea.rows = 1;
    commentBox.hidden = false;
    fitTextarea(commentArea);
    var rect = el.getBoundingClientRect();
    var width = commentBox.offsetWidth;
    var height = commentBox.offsetHeight;
    var maxLeft = document.documentElement.clientWidth - width - 8;
    var top = rect.bottom + 6;
    /* The footer bar covers the bottom of the window, so flip above when there is no room. */
    if (top + height > window.innerHeight - 64) top = Math.max(rect.top - height - 6, 8);
    commentBox.style.setProperty("--pk-x", Math.max(8, Math.min(rect.left, maxLeft)) + window.scrollX + "px");
    commentBox.style.setProperty("--pk-y", top + window.scrollY + "px");
    commentArea.focus();
    if (narrowScreen.matches) el.scrollIntoView({ block: "center" });
    placeCommentSheet();
  }

  /* On a phone the box is a bottom sheet, and the keyboard covers the page without resizing it. */
  function placeCommentSheet() {
    var view = window.visualViewport;
    if (!commentBox || commentBox.hidden || !view) return;
    var covered = Math.max(0, window.innerHeight - view.height - view.offsetTop);
    commentBox.style.setProperty("--pk-keyboard", covered + "px");
  }

  function nextCommented() {
    var marks = idMarks().filter(function (el, index, all) {
      var id = idOf(el);
      return comments[id] && all.findIndex(function (other) { return idOf(other) === id; }) === index;
    });
    if (!marks.length) return;
    var el = marks[(marks.indexOf(commentAnchor) + 1) % marks.length];
    var parent = el.closest("details");
    if (parent) parent.open = true;
    el.scrollIntoView({ block: "center" });
    openComment(el);
  }

  function initComments() {
    try {
      comments = JSON.parse(localStorage.getItem(COMMENT_KEY) || "{}") || {};
    } catch (err) {
      comments = {};
    }
    idMarks().forEach(function (el) {
      el.setAttribute("role", "button");
      el.setAttribute("tabindex", "0");
    });
    var exportButton = document.getElementById("pk-export");
    if (exportButton) {
      commentCount = document.createElement("button");
      commentCount.type = "button";
      commentCount.className = "pk-comment-count";
      commentCount.hidden = true;
      commentCount.addEventListener("click", function (event) {
        event.stopPropagation();
        nextCommented();
      });
      exportButton.parentNode.insertBefore(commentCount, exportButton);
    }
    refreshComments();
    document.addEventListener("click", function (event) {
      if (commentBox && commentBox.contains(event.target)) return;
      var mark = event.target.closest(".pk-id");
      if (!mark) {
        closeComment(false);
        return;
      }
      /* An ID inside a label or link must not also toggle or navigate. */
      event.preventDefault();
      openComment(mark);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeComment(true);
      var mark = event.target.closest && event.target.closest(".pk-id");
      if (mark && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        openComment(mark);
      }
    });
  }

  window.pagekit = {
    /* For bespoke widgets: pagekit.register("order", function () { return ids; }). */
    register: function (name, getter) {
      custom[name] = getter;
      refreshExportButton();
    },
    collect: collect,
    text: text,
    copy: copy,
  };

  /* Warn before leaving only when there are answers or comments the user has not copied.
     Browsers do not let a page cancel Ctrl+W, so this prompt is the only guard available. */
  var COPIED_KEY = STORE_KEY + ":copied";
  var leavingForIndex = false;
  var copiedState = null;

  function currentState() {
    var sorted = {};
    Object.keys(comments).sort().forEach(function (id) { sorted[id] = comments[id]; });
    /* Opening a section is not an answer, so details do not count. */
    return JSON.stringify([collect(true), sorted]);
  }

  function markCopied() {
    copiedState = currentState();
    try {
      localStorage.setItem(COPIED_KEY, copiedState);
    } catch (err) {
      /* Storage can be blocked; this only affects the prompt after a reload. */
    }
  }

  /* With no copy yet, the baseline is the page as it was built. */
  copiedState = currentState();
  restore();
  if (!meta.readonly) initComments();
  /* A script can add controls after load. */
  new MutationObserver(refreshExportButton).observe(document.body, { childList: true, subtree: true });
  try {
    copiedState = localStorage.getItem(COPIED_KEY) || copiedState;
  } catch (err) {
    /* Keep the baseline. */
  }

  window.addEventListener("beforeunload", function (event) {
    if (leavingForIndex || currentState() === copiedState) return;
    event.preventDefault();
    event.returnValue = "";
  });

  /* Clicking the selected radio option clears it. The browser checks a radio before the click
     event, so this remembers each group's selection to tell a repeat click from a new one. */
  var selectedRadios = {};
  Array.prototype.forEach.call(document.querySelectorAll('input[type="radio"]:checked'), function (radio) {
    if (radio.name) selectedRadios[radio.name] = radio;
  });
  function isNamedRadio(el) {
    return el.tagName === "INPUT" && el.type === "radio" && !!el.name;
  }
  function clearRadio(radio) {
    radio.checked = false;
    delete selectedRadios[radio.name];
    radio.dispatchEvent(new Event("input", { bubbles: true }));
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }
  document.addEventListener("click", function (event) {
    var radio = event.target;
    if (!isNamedRadio(radio)) return;
    if (selectedRadios[radio.name] === radio) clearRadio(radio);
    else selectedRadios[radio.name] = radio;
  });
  /* Space on a selected radio fires no click, so the keyboard needs its own path. */
  document.addEventListener("keyup", function (event) {
    var radio = event.target;
    if (event.key === " " && isNamedRadio(radio) && selectedRadios[radio.name] === radio && radio.checked) {
      event.preventDefault();
      clearRadio(radio);
    }
  });

  Array.prototype.forEach.call(document.querySelectorAll("textarea"), function (area) {
    area.rows = 1;
    fitTextarea(area);
  });
  document.addEventListener("input", function (event) { fitTextarea(event.target); });
  document.addEventListener("input", persist);
  document.addEventListener("change", persist);
  document.addEventListener("toggle", persist, true);
  document.addEventListener("submit", function (event) { event.preventDefault(); });
  var button = document.getElementById("pk-export");
  if (button) button.addEventListener("click", copy);

  /* A link to something inside a collapsed section opens that section, then scrolls to it. */
  function revealLinkTarget() {
    var target = null;
    try {
      target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    } catch (err) {
      return;
    }
    if (!target) return;
    var opened = false;
    for (var node = target; node; node = node.parentElement) {
      if (node.tagName === "DETAILS" && !node.open) {
        node.open = true;
        opened = true;
      }
    }
    if (opened) target.scrollIntoView();
  }
  window.addEventListener("hashchange", revealLinkTarget);
  window.addEventListener("load", revealLinkTarget);

  /* A heading row becomes a real <thead>, so it repeats on every printed sheet. */
  Array.prototype.forEach.call(document.querySelectorAll("table"), function (table) {
    var first = table.rows[0];
    if (table.tHead || !first) return;
    var allHeadings = Array.prototype.every.call(first.cells, function (c) { return c.tagName === "TH"; });
    if (allHeadings) table.createTHead().appendChild(first);
  });

  /* Collapsed sections print open, then return to how they were. */
  var closedForPrint = [];
  window.addEventListener("beforeprint", function () {
    /* Added to, not replaced: print can fire this twice before afterprint. */
    Array.prototype.forEach.call(document.querySelectorAll("details"), function (d) {
      if (!d.open) {
        closedForPrint.push(d);
        d.open = true;
      }
    });
  });
  window.addEventListener("afterprint", function () {
    closedForPrint.forEach(function (d) { d.open = false; });
    closedForPrint = [];
  });

  /* Header controls are icons: this is both the hover label and the accessible name. */
  function setBarLabel(control, label) {
    control.setAttribute("data-label", label);
    control.setAttribute("aria-label", label);
  }

  /* The server can build a bookmarked PDF, including answers typed on this page. */
  function addPdfButton(bar, before) {
    var parts = location.pathname.split("/");
    if (parts[1] !== "p") return;
    fetch("/api/pdf").then(function (r) { return r.json(); }).then(function (info) {
      if (!info.available) return;
      var pdf = document.createElement("button");
      pdf.type = "button";
      pdf.className = "pk-pdf";
      setBarLabel(pdf, "Download PDF");
      pdf.innerHTML = '<i data-icon="download"></i>';
      bar.insertBefore(pdf, before);
      pdf.addEventListener("click", function () {
        pdf.disabled = true;
        pdf.classList.remove("pk-pdf-failed");
        setBarLabel(pdf, "Generating PDF...");
        fetch("/api/pdf/" + parts[2] + "/" + parts[3], {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(snapshot()),
        }).then(function (response) {
          if (!response.ok) throw new Error("PDF failed");
          return response.blob();
        }).then(function (blob) {
          var link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = parts[3] + ".pdf";
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(function () { URL.revokeObjectURL(link.href); }, 10000);
          setBarLabel(pdf, "Download PDF");
        }).catch(function () {
          pdf.classList.add("pk-pdf-failed");
          setBarLabel(pdf, "PDF failed, try again");
        }).finally(function () {
          pdf.disabled = false;
        });
      });
    }).catch(function () {
      /* No button without a server that can make PDFs. */
    });
  }

  /* A way back to the index, only when served by pagekit: a downloaded copy has no index. */
  var headerBar = document.querySelector(".pk-header .pk-bar");
  if (headerBar && /^https?:$/.test(location.protocol) && /^\/(p|saved)\//.test(location.pathname)) {
    var home = document.createElement("a");
    home.className = "pk-home";
    home.href = "/";
    setBarLabel(home, "All pages");
    home.innerHTML = '<i data-icon="layout-grid"></i>';
    /* Answers are saved in the browser and this stays in the same tab, so no prompt. */
    home.addEventListener("click", function () { leavingForIndex = true; });
    headerBar.appendChild(home);
    addPdfButton(headerBar, home);
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", placeCommentSheet);
    window.visualViewport.addEventListener("scroll", placeCommentSheet);
  }

  /* On a phone the bars step aside while reading down, and return on any scroll up. */
  var lastScroll = window.scrollY;
  function isTyping() {
    var active = document.activeElement;
    return !!active && (active.tagName === "TEXTAREA" || active.tagName === "SELECT" || active.tagName === "INPUT" || active.isContentEditable);
  }
  function showBars() {
    document.body.classList.remove("pk-bars-hidden");
  }
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    if (!narrowScreen.matches) return showBars();
    if (Math.abs(y - lastScroll) < 8) return;
    var atEnd = y + window.innerHeight >= document.documentElement.scrollHeight - 40;
    var reading = y > lastScroll && y > 80 && !atEnd && !isTyping();
    document.body.classList.toggle("pk-bars-hidden", reading);
    lastScroll = y;
  }, { passive: true });
  document.addEventListener("focusin", function () { if (isTyping()) showBars(); });
  narrowScreen.addEventListener("change", showBars);
  window.addEventListener("beforeprint", showBars);

  /* The phone's address bar matches the page's own bars. */
  var barColor = document.createElement("meta");
  barColor.name = "theme-color";
  document.head.appendChild(barColor);
  function matchBarColor() {
    barColor.content = getComputedStyle(document.documentElement).getPropertyValue("--pk-surface").trim();
  }
  matchBarColor();
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", matchBarColor);

  /* Tap any image or diagram for a full-screen preview. Built on the native dialog, which
     handles focus, Esc, and stacking above the sticky bars. */
  var PREVIEWABLE = "main img, .pk-diagram svg";
  var preview = null;
  var previewItems = [];
  var previewIndex = 0;
  var previewPushedHistory = false;
  var previewClosingFromHistory = false;

  function previewCaption(item) {
    var figure = item.closest("figure");
    var caption = figure && figure.querySelector("figcaption");
    return (caption && caption.textContent.trim()) || item.getAttribute("alt") || "";
  }

  function showPreviewItem(index) {
    previewIndex = (index + previewItems.length) % previewItems.length;
    var item = previewItems[previewIndex];
    var stage = preview.querySelector(".pk-preview-stage");
    var copy = item.cloneNode(true);
    /* A copy must not repeat the original's ids, or labels would point at the wrong element. */
    copy.removeAttribute("id");
    copy.removeAttribute("tabindex");
    copy.removeAttribute("loading");
    copy.removeAttribute("aria-labelledby");
    copy.classList.remove("pk-previewable");
    copy.classList.add("pk-preview-item");
    Array.prototype.forEach.call(copy.querySelectorAll("title[id], desc[id]"), function (el) { el.removeAttribute("id"); });
    if (item.tagName !== "IMG") copy.setAttribute("aria-label", previewCaption(item));
    stage.classList.remove("pk-preview-zoomed");
    stage.classList.toggle("pk-preview-drawing", item.tagName !== "IMG");
    stage.replaceChildren(copy);
    stage.scrollTo(0, 0);
    /* A chart's legend sits beside its drawing on the page, so it comes along. */
    var legend = preview.querySelector(".pk-preview-legend");
    var plot = item.closest(".pk-chart-plot");
    var list = plot && plot.querySelector(".pk-chart-legend");
    legend.replaceChildren();
    if (list) legend.appendChild(list.cloneNode(true));
    preview.querySelector(".pk-preview-caption").textContent = previewCaption(item);
    preview.querySelector(".pk-preview-count").textContent = previewItems.length > 1 ? previewIndex + 1 + " of " + previewItems.length : "";
    preview.classList.toggle("pk-preview-single", previewItems.length < 2);
  }

  function togglePreviewZoom(event) {
    var stage = preview.querySelector(".pk-preview-stage");
    var item = stage.firstElementChild;
    var rect = item.getBoundingClientRect();
    var x = (event.clientX - rect.left) / rect.width;
    var y = (event.clientY - rect.top) / rect.height;
    stage.classList.toggle("pk-preview-zoomed");
    if (stage.classList.contains("pk-preview-zoomed")) {
      /* Keep the tapped spot under the finger. */
      var zoomed = item.getBoundingClientRect();
      stage.scrollLeft = x * zoomed.width - stage.clientWidth / 2;
      stage.scrollTop = y * zoomed.height - stage.clientHeight / 2;
    }
  }

  function buildPreview() {
    preview = document.createElement("dialog");
    preview.className = "pk-preview";
    preview.setAttribute("aria-label", "Image preview");
    preview.setAttribute("data-pk-ignore", "");
    preview.innerHTML =
      '<div class="pk-preview-bar"><span class="pk-preview-count"></span>' +
      '<button type="button" class="pk-preview-close" aria-label="Close preview"><i data-icon="x"></i></button></div>' +
      '<div class="pk-preview-stage"></div>' +
      '<div class="pk-preview-legend"></div>' +
      '<button type="button" class="pk-preview-nav pk-preview-prev" aria-label="Previous image"><i data-icon="chevron-left"></i></button>' +
      '<button type="button" class="pk-preview-nav pk-preview-next" aria-label="Next image"><i data-icon="chevron-right"></i></button>' +
      '<p class="pk-preview-caption"></p>';
    document.body.appendChild(preview);
    preview.querySelector(".pk-preview-close").addEventListener("click", function () { preview.close(); });
    preview.querySelector(".pk-preview-prev").addEventListener("click", function () { showPreviewItem(previewIndex - 1); });
    preview.querySelector(".pk-preview-next").addEventListener("click", function () { showPreviewItem(previewIndex + 1); });
    var stage = preview.querySelector(".pk-preview-stage");
    /* The image zooms, the buttons do their jobs, and a tap anywhere else closes. */
    preview.addEventListener("click", function (event) {
      if (event.target.closest(".pk-preview-item")) togglePreviewZoom(event);
      else if (!event.target.closest("button")) preview.close();
    });
    preview.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") showPreviewItem(previewIndex - 1);
      if (event.key === "ArrowRight") showPreviewItem(previewIndex + 1);
    });
    var swipeStart = null;
    stage.addEventListener("touchstart", function (event) {
      swipeStart = event.touches.length === 1 ? event.touches[0].clientX : null;
    }, { passive: true });
    stage.addEventListener("touchend", function (event) {
      var pinched = window.visualViewport && window.visualViewport.scale > 1.01;
      if (swipeStart === null || pinched || stage.classList.contains("pk-preview-zoomed") || previewItems.length < 2) return;
      var moved = event.changedTouches[0].clientX - swipeStart;
      if (Math.abs(moved) > 50) showPreviewItem(previewIndex + (moved < 0 ? 1 : -1));
    }, { passive: true });
    /* Android's back button closes the preview rather than leaving the page. */
    preview.addEventListener("close", function () {
      preview.querySelector(".pk-preview-stage").replaceChildren();
      if (previewPushedHistory && !previewClosingFromHistory) history.back();
      previewPushedHistory = false;
      previewClosingFromHistory = false;
    });
    window.addEventListener("popstate", function () {
      if (preview.open) {
        previewClosingFromHistory = true;
        preview.close();
      }
    });
  }

  function openPreview(item) {
    if (!preview) buildPreview();
    hideTip();
    /* A chart opens from its own button, since a tap on a chart shows a tooltip. It joins the others here. */
    previewItems = Array.prototype.slice.call(document.querySelectorAll(PREVIEWABLE + ", .pk-chart-svg")).filter(function (el) {
      return !el.closest("a");
    });
    showPreviewItem(Math.max(previewItems.indexOf(item), 0));
    preview.showModal();
    try {
      history.pushState({ pkPreview: true }, "");
      previewPushedHistory = true;
    } catch (err) {
      previewPushedHistory = false;
    }
  }

  function previewableFrom(target) {
    var item = target.closest && target.closest(PREVIEWABLE);
    return item && !item.closest("a") && !item.closest(".pk-preview") ? item : null;
  }

  Array.prototype.forEach.call(document.querySelectorAll(PREVIEWABLE), function (item) {
    if (item.closest("a")) return;
    item.setAttribute("tabindex", "0");
    item.classList.add("pk-previewable");
  });
  document.addEventListener("click", function (event) {
    var item = previewableFrom(event.target);
    if (item) openPreview(item);
    var expand = event.target.closest && event.target.closest(".pk-chart-expand");
    var figure = expand && expand.closest(".pk-chart");
    var chart = figure && figure.querySelector(".pk-chart-svg");
    if (chart) openPreview(chart);
  });
  document.addEventListener("keydown", function (event) {
    var item = (event.key === "Enter" || event.key === " ") && previewableFrom(event.target);
    if (item) {
      event.preventDefault();
      openPreview(item);
    }
  });
  window.addEventListener("beforeprint", function () {
    if (preview && preview.open) preview.close();
  });

  /* Chart tooltips. The build writes each tooltip's text into the chart as data-tip, so this only shows it:
     on hover, on a tap, and with the arrow keys while a chart has focus. A chart still reads without it. */
  var tip = null;
  var tipTarget = null;

  function tipSwatch(number) {
    var key = document.createElement("span");
    key.className = "pk-tip-key pk-chart-s" + number;
    key.setAttribute("aria-hidden", "true");
    return key;
  }

  function tipElement() {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "pk-tip";
      tip.setAttribute("role", "status");
      tip.setAttribute("data-pk-ignore", "");
      tip.hidden = true;
    }
    /* A modal dialog sits above everything else, so a tooltip over a full-screen chart must live inside it. */
    var host = document.querySelector("dialog.pk-preview[open]") || document.body;
    if (tip.parentNode !== host) host.appendChild(tip);
    return tip;
  }

  function fillTip(el, data) {
    el.textContent = "";
    var title = document.createElement("div");
    title.className = "pk-tip-title";
    if (data.s) title.appendChild(tipSwatch(data.s));
    title.appendChild(document.createTextNode(data.t));
    el.appendChild(title);
    (data.r || []).forEach(function (row) {
      var line = document.createElement("div");
      var name = document.createElement("span");
      var value = document.createElement("span");
      line.className = "pk-tip-row";
      name.className = "pk-tip-name";
      value.className = "pk-tip-value";
      if (row[2]) name.appendChild(tipSwatch(row[2]));
      name.appendChild(document.createTextNode(row[0]));
      value.textContent = row[1];
      line.appendChild(name);
      line.appendChild(value);
      el.appendChild(line);
    });
  }

  function markTip(target) {
    var old = tipTarget && (tipTarget.closest(".pk-chart-point") || tipTarget);
    if (old) old.classList.remove("pk-chart-on");
    tipTarget = target;
    var now = target && (target.closest(".pk-chart-point") || target);
    if (now) now.classList.add("pk-chart-on");
  }

  function placeTip(x, y) {
    var box = tip.getBoundingClientRect();
    var margin = 8;
    var left = x + 14;
    var top = y + 14;
    if (left + box.width + margin > window.innerWidth) left = x - box.width - 14;
    if (top + box.height + margin > window.innerHeight) top = y - box.height - 14;
    tip.style.left = Math.max(margin, left) + "px";
    tip.style.top = Math.max(margin, top) + "px";
  }

  function showTip(target, x, y) {
    var el = tipElement();
    if (target !== tipTarget || el.hidden) {
      var data;
      try {
        data = JSON.parse(target.getAttribute("data-tip"));
      } catch (err) {
        return;
      }
      fillTip(el, data);
      markTip(target);
      el.hidden = false;
    }
    placeTip(x, y);
  }

  function hideTip() {
    if (tip) tip.hidden = true;
    markTip(null);
  }

  function tipTargetFrom(node) {
    return node && node.closest ? node.closest("[data-tip]") : null;
  }

  /* A mouse follows the pointer; a finger or pen shows the tip where it lands and keeps it until the next tap. */
  document.addEventListener("pointermove", function (event) {
    if (event.pointerType !== "mouse") return;
    var target = tipTargetFrom(event.target);
    if (target) showTip(target, event.clientX, event.clientY);
    else if (tipTarget) hideTip();
  });
  document.addEventListener("pointerdown", function (event) {
    if (event.pointerType === "mouse") return;
    var target = tipTargetFrom(event.target);
    if (target) showTip(target, event.clientX, event.clientY);
    else hideTip();
  });
  document.addEventListener("pointerout", function (event) {
    if (event.pointerType === "mouse" && !event.relatedTarget) hideTip();
  });
  window.addEventListener("scroll", hideTip, { passive: true });
  document.addEventListener("focusout", function (event) {
    if (event.target.closest && event.target.closest(".pk-chart-svg")) hideTip();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") hideTip();
    var chart = event.target.closest && event.target.closest(".pk-chart-svg");
    var steps = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!chart || !(event.key in steps || event.key === "Home" || event.key === "End")) return;
    var targets = chart.querySelectorAll("[data-tip]");
    if (!targets.length) return;
    var at = Array.prototype.indexOf.call(targets, tipTarget);
    var next;
    if (event.key === "Home") next = 0;
    else if (event.key === "End") next = targets.length - 1;
    else if (at < 0) next = steps[event.key] > 0 ? 0 : targets.length - 1;
    else next = Math.min(targets.length - 1, Math.max(0, at + steps[event.key]));
    event.preventDefault();
    var box = targets[next].getBoundingClientRect();
    showTip(targets[next], box.left + box.width / 2, box.top + Math.min(box.height / 2, 40));
  });

  /* The header shows the page title once the main heading has scrolled away. */
  var heading = document.querySelector("h1");
  if (heading && window.IntersectionObserver) {
    new IntersectionObserver(function (entries) {
      document.body.classList.toggle("pk-scrolled", !entries[0].isIntersecting);
    }, { rootMargin: "-60px 0px 0px 0px" }).observe(heading);
  }
})();
