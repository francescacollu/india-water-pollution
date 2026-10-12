/* =========================================================================
   Graphic: "placeholder"
   Stand-in for charts that don't exist yet. It shows the view name of the
   active step, so you can plan a scrolly section in story.md first and
   build the real chart later (then just change graphic="..." in story.md).
   ========================================================================= */
(function () {
  window.FOIW.graphics["placeholder"] = function (el) {
    el.innerHTML =
      '<div class="fo-iw-placeholder"><div>' +
      '<div class="fo-iw-placeholder-name fo-iw-chart-ui">Chart to come — current view:</div>' +
      '<div class="fo-iw-placeholder-view"></div>' +
      "</div></div>";
    var label = el.querySelector(".fo-iw-placeholder-view");

    return {
      update: function (view) { label.textContent = view; },
    };
  };
})();
