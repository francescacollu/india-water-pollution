/* =========================================================================
   Scroll engine
   -------------------------------------------------------------------------
   For every <section class="fo-iw-scrolly" data-graphic="NAME">:
     1. finds the graphic called NAME in FOIW.graphics and starts it,
     2. watches the step cards; when one crosses the middle of the screen,
        calls graphic.update(view) with that card's data-view.

   A graphic is just a function:
     FOIW.graphics["my-chart"] = function (el, ctx) {
       // draw something inside el
       return {
         update: function (view, info) { ... },   // required
         resize: function () { ... }              // optional
       };
     };
   ctx.data   = the JSON built by prepare_data.py
   info       = { index, direction: "down" | "up", previous }
   ========================================================================= */
(function () {
  var FOIW = window.FOIW;
  var root = document.getElementById("fo-iw");
  var dataEl = document.getElementById("fo-iw-data");
  var ctx = {
    data: dataEl ? JSON.parse(dataEl.textContent) : {},
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  };
  var instances = [];

  root.querySelectorAll(".fo-iw-scrolly").forEach(function (section) {
    var name = section.dataset.graphic;
    var factory = FOIW.graphics[name];
    var el = section.querySelector(".fo-iw-graphic");
    if (!factory) {
      el.innerHTML = '<p class="fo-iw-chart-ui" style="padding:2rem">Unknown graphic: "' + name + '"</p>';
      return;
    }
    var graphic = factory(el, ctx);
    instances.push(graphic);

    var steps = Array.prototype.slice.call(section.querySelectorAll(".fo-iw-step"));
    var current = -1;

    function activate(index) {
      if (index === current) return;
      var info = {
        index: index,
        direction: index > current ? "down" : "up",
        previous: current >= 0 ? steps[current].dataset.view : null,
      };
      steps.forEach(function (s, i) { s.classList.toggle("is-active", i === index); });
      current = index;
      graphic.update(steps[index].dataset.view, info);
    }

    // Show the first view straight away, before the reader starts scrolling.
    if (steps.length) activate(0);

    // rootMargin shrinks the "viewport" to a thin band across the middle of
    // the screen: a step is "intersecting" exactly when it covers that line.
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) activate(steps.indexOf(entry.target));
      });
    }, { rootMargin: "-49% 0px -50% 0px", threshold: 0 });
    steps.forEach(function (s) { observer.observe(s); });
  });

  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      instances.forEach(function (g) { if (g.resize) g.resize(); });
    }, 150);
  });
})();
