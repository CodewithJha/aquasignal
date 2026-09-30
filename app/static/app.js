/* AquaSignal — progressive enhancement only. Every page works without this file. */
(function () {
  "use strict";

  /* Authority chain starts collapsed on narrow screens (open by default without JS). */
  var chain = document.querySelector("details.chain");
  if (chain && window.matchMedia("(max-width: 760px)").matches) {
    chain.open = false;
  }

  /* Hash targets inside closed <details> (exhibits, agreeing pairs) are revealed. */
  function revealHash() {
    if (!location.hash || location.hash.length < 2) return;
    var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!target) return;
    var inner = target.querySelector(":scope > details");
    if (inner) inner.open = true;
    for (var el = target.parentElement; el; el = el.parentElement) {
      if (el.tagName === "DETAILS") el.open = true;
    }
  }
  window.addEventListener("hashchange", revealHash);
  revealHash();

  var dossier = document.querySelector("[data-dossier]");
  if (!dossier) return;

  /* ---- Relationship tracing: hover / focus lights an observation and its relations. ---- */
  var arcs = Array.prototype.slice.call(dossier.querySelectorAll(".arc"));
  var marks = Array.prototype.slice.call(dossier.querySelectorAll(".mark[data-ev]"));
  var exhibits = Array.prototype.slice.call(dossier.querySelectorAll(".exhibit[data-ev]"));
  var pairEls = Array.prototype.slice.call(
    dossier.querySelectorAll(".pair-card[data-a], .pair-lines li[data-a], .rel-index li[data-a]")
  );
  var lit = [];

  function clear() {
    dossier.classList.remove("is-tracing");
    lit.forEach(function (el) { el.classList.remove("is-lit"); });
    lit = [];
  }

  function light(el) {
    el.classList.add("is-lit");
    lit.push(el);
  }

  function trace(ids, pairOnly) {
    clear();
    if (!ids.length) return;
    dossier.classList.add("is-tracing");
    var focus = {};
    ids.forEach(function (id) { focus[id] = true; });
    var set = {};
    ids.forEach(function (id) { set[id] = true; });
    arcs.concat(pairEls).forEach(function (el) {
      var a = el.getAttribute("data-a");
      var b = el.getAttribute("data-b");
      var hit = pairOnly ? focus[a] && focus[b] : focus[a] || focus[b];
      if (hit) {
        light(el);
        set[a] = true;
        set[b] = true;
      }
    });
    marks.concat(exhibits).forEach(function (el) {
      if (set[el.getAttribute("data-ev")]) light(el);
    });
  }

  function bind(el, idsFor, pairOnly) {
    var on = function () { trace(idsFor(el), pairOnly); };
    el.addEventListener("mouseenter", on);
    el.addEventListener("focusin", on);
    el.addEventListener("mouseleave", clear);
    el.addEventListener("focusout", clear);
  }

  marks.forEach(function (el) {
    bind(el, function (m) { return [m.getAttribute("data-ev")]; }, false);
  });
  dossier.querySelectorAll(".arc-label, .rel-index li, .pair-card, .pair-lines li").forEach(function (el) {
    bind(el, function (p) { return [p.getAttribute("data-a"), p.getAttribute("data-b")]; }, true);
  });
  dossier.querySelectorAll(".event[data-evs]").forEach(function (el) {
    bind(el, function (e) { return e.getAttribute("data-evs").split(/\s+/).filter(Boolean); }, false);
  });
})();
