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
    if (!notes) {
      status("Copied " + fields + ". Paste it into Claude Code.", "Copied " + fields + ", paste into Claude", true);
      return;
    }
    var both = fields + ", " + notes + (notes === 1 ? " comment" : " comments");
    status("Copied " + both + ". Paste it into Claude Code.", "Copied " + both, true);
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

  function refreshComments() {
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
    commentBox.hidden = false;
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
    register: function (name, getter) { custom[name] = getter; },
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
  initComments();
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

  document.addEventListener("input", persist);
  document.addEventListener("change", persist);
  document.addEventListener("toggle", persist, true);
  document.addEventListener("submit", function (event) { event.preventDefault(); });
  var button = document.getElementById("pk-export");
  if (button) button.addEventListener("click", copy);

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

  /* A way back to the index, only when served by pagekit: a downloaded copy has no index. */
  var headerBar = document.querySelector(".pk-header .pk-bar");
  if (headerBar && /^https?:$/.test(location.protocol) && /^\/(p|saved)\//.test(location.pathname)) {
    var home = document.createElement("a");
    home.className = "pk-home";
    home.href = "/";
    home.textContent = "All pages";
    /* Answers are saved in the browser and this stays in the same tab, so no prompt. */
    home.addEventListener("click", function () { leavingForIndex = true; });
    headerBar.appendChild(home);
  }

  /* The header shows the page title once the main heading has scrolled away. */
  var heading = document.querySelector("h1");
  if (heading && window.IntersectionObserver) {
    new IntersectionObserver(function (entries) {
      document.body.classList.toggle("pk-scrolled", !entries[0].isIntersecting);
    }, { rootMargin: "-60px 0px 0px 0px" }).observe(heading);
  }
})();
