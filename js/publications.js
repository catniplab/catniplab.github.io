// Publications page: search, label filters, abstract toggle, URL state and
// copy buttons. Progressive enhancement: without this script the full list,
// the Abstract and Cite boxes, and the view radios (CSS :has) still work.
(function () {
  "use strict";
  var root = document.querySelector(".pubs");
  if (!root) return;

  var GROUPS = ["theme", "kind", "tag", "review"];
  var allView = document.getElementById("show-abstracts");
  var papersView = document.getElementById("show-papers");
  var showAll = document.getElementById("pubs-show-all");
  var q = document.getElementById("pubs-q");
  var count = document.getElementById("pubs-count");
  var years = Array.prototype.slice.call(root.querySelectorAll("section.pubs-year"));
  var chips = Array.prototype.slice.call(root.querySelectorAll(".pubs-controls button.chip"));
  var state = { q: "", abstracts: false, theme: [], kind: [], tag: [], review: [] };
  var fragment = location.hash;
  var urlTimer;

  function fold(s) {
    return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/\u0142/g, "l").replace(/\u0141/g, "L").toLowerCase();
  }
  function words(s) { return s ? s.split(/\s+/).filter(Boolean) : []; }

  var recs = Array.prototype.slice.call(root.querySelectorAll("li.pub")).map(function (li) {
    var parts = li.querySelectorAll(".pub-title, .pub-authors, .pub-venue, .pub-abstract p");
    var text = li.id + " " + li.getAttribute("data-year");
    for (var i = 0; i < parts.length; i++) text += " " + parts[i].textContent;
    return {
      li: li,
      kind: li.getAttribute("data-kind"),
      text: fold(text),
      labels: { theme: words(li.getAttribute("data-themes")),
                kind: [li.getAttribute("data-kind")],
                tag: words(li.getAttribute("data-tags")),
                review: li.dataset.refereed === "true" ? ["refereed"] : [] }
    };
  });

  function known(group) {
    return chips.filter(function (c) { return c.dataset.group === group; })
      .map(function (c) { return c.dataset.value; });
  }

  function visible(r) {
    if (!state.abstracts && r.kind === "abstract") return false;
    for (var g = 0; g < GROUPS.length; g++) {
      var want = state[GROUPS[g]];
      var have = r.labels[GROUPS[g]];
      if (want.length && !want.some(function (v) { return have.indexOf(v) >= 0; })) return false;
    }
    return words(fold(state.q)).every(function (t) { return r.text.indexOf(t) >= 0; });
  }

  function targetRecord() {
    var id;
    try { id = decodeURIComponent(fragment.slice(1)); }
    catch (err) {
      if (err instanceof URIError) return null;
      throw err;
    }
    return recs.filter(function (r) { return r.li.id === id; })[0] || null;
  }

  function writeUrl() {
    var p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.abstracts) p.set("abstracts", "1");
    GROUPS.forEach(function (g) { if (state[g].length) p.set(g, state[g].join(",")); });
    var s = p.toString();
    try {
      history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + fragment);
    } catch (err) {
      // History throttling must not interrupt filtering or fragment cleanup.
      if (err.name !== "SecurityError") throw err;
    }
  }

  function readUrl() {
    var p = new URLSearchParams(location.search);
    fragment = location.hash;
    state.q = p.get("q") || "";
    state.abstracts = p.get("abstracts") === "1";
    GROUPS.forEach(function (g) {
      var ok = known(g);
      state[g] = (p.get(g) || "").split(",").filter(function (v, i, all) {
        return ok.indexOf(v) >= 0 && all.indexOf(v) === i;
      });
    });
  }

  function apply(preserveTarget, delayUrl) {
    var shown = 0;
    var inView = 0;
    var target = targetRecord();
    if (!preserveTarget && target && !visible(target)) { fragment = ""; target = null; }
    recs.forEach(function (r) {
      if (state.abstracts || r.kind !== "abstract") inView++;
      var v = visible(r);
      r.li.hidden = !v;
      r.li.classList.toggle("pub-target", r === target && v);
      if (v) shown++;
    });
    years.forEach(function (s) { s.hidden = !s.querySelector("li.pub:not([hidden])"); });
    count.textContent = "Showing " + shown + " of " + recs.length;
    showAll.hidden = shown === inView;
    chips.forEach(function (c) {
      var active = state[c.dataset.group].indexOf(c.dataset.value) >= 0;
      c.setAttribute("aria-pressed", String(active));
      if (active && c.dataset.group === "tag") {
        root.querySelector(".pubs-topics").open = true;
        var more = c.closest(".more-tags");
        if (more) more.open = true;
      }
      c.querySelector(".n").textContent = recs.filter(function (r) {
        return (state.abstracts || r.kind !== "abstract") &&
          r.labels[c.dataset.group].indexOf(c.dataset.value) >= 0;
      }).length;
    });
    allView.checked = state.abstracts;
    papersView.checked = !state.abstracts;
    q.value = state.q;
    clearTimeout(urlTimer);
    if (delayUrl) urlTimer = setTimeout(writeUrl, 300); else writeUrl();
  }

  function reset() {
    state.q = "";
    GROUPS.forEach(function (g) { state[g] = []; });
  }

  function revealTarget() {
    var r = targetRecord();
    if (r) {
      if (r.kind === "abstract") state.abstracts = true;
      if (!visible(r)) reset();
    }
    apply(true);
    if (r) r.li.scrollIntoView();
  }

  function selectText(el) {
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  root.querySelectorAll("details.pub-cite").forEach(function (d) {
    [["Copy APA", ".cite-apa"], ["Copy BibTeX", ".cite-bibtex"]].forEach(function (pair) {
      var src = d.querySelector(pair[1]);
      if (!src) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "copy";
      b.textContent = pair[0];
      b.addEventListener("click", function () {
        var done = function () {
          b.textContent = "Copied";
          setTimeout(function () { b.textContent = pair[0]; }, 1500);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(src.textContent).then(done, function () { selectText(src); });
        } else {
          selectText(src);
        }
      });
      d.appendChild(b);
    });
  });

  q.addEventListener("input", function () { state.q = q.value; apply(false, true); });
  root.querySelector(".pubs-view").addEventListener("change", function () {
    state.abstracts = allView.checked;
    apply();
  });
  chips.forEach(function (c) {
    c.addEventListener("click", function () {
      var list = state[c.dataset.group];
      var i = list.indexOf(c.dataset.value);
      if (i >= 0) list.splice(i, 1); else list.push(c.dataset.value);
      apply();
    });
  });
  root.querySelectorAll(".pub-labels a.chip").forEach(function (a) {
    a.addEventListener("click", function (ev) {
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
      if (known(a.dataset.group).indexOf(a.dataset.value) < 0) return;
      ev.preventDefault();
      state[a.dataset.group] = [a.dataset.value];
      apply();
      root.querySelector(".pubs-controls").scrollIntoView();
    });
  });
  [document.getElementById("pubs-clear"), showAll].forEach(function (button) {
    button.addEventListener("click", function () {
      reset();
      if (button === showAll) state.abstracts = true;
      fragment = "";
      apply();
    });
  });
  window.addEventListener("hashchange", function () { fragment = location.hash; revealTarget(); });
  window.addEventListener("popstate", function () {
    readUrl();
    revealTarget();
  });

  root.classList.add("pubs-enhanced");
  root.querySelectorAll(".pubs-js").forEach(function (el) { el.hidden = false; });
  readUrl();
  // Retain an incoming fragment until revealTarget has made its entry visible.
  revealTarget();
})();
