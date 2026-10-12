/* =========================================================================
   Graphic: "sewage-map"
   India map, states coloured by sewage-treatment figures.

   Views (use these names in story.md  [[step view="..."]]):
     india           plain map of India
     madhya-pradesh  zoom to Madhya Pradesh
     indore          zoom closer, with a marker on Indore
     generation      sewage generated per day (MLD)
     capacity        installed treatment capacity, % of sewage generated
     treated         sewage actually treated, % of sewage generated
     efficiency      sewage treated, % of installed capacity

   To add a view: add an entry to VIEWS below.
   ========================================================================= */
(function () {
  var SOURCE = "Source: CPCB, National Inventory of Sewage Treatment Plants"; // TODO confirm year
  var INDORE = [75.8577, 22.7196]; // [longitude, latitude]

  // Each view says: which column colours the map (or none), and where to zoom.
  //   metric.max  -> values above this get the darkest colour ("100%+")
  var VIEWS = {
    "india":          { zoom: null },
    "madhya-pradesh": { zoom: "Madhya Pradesh", highlight: "Madhya Pradesh" },
    "indore":         { zoom: "Madhya Pradesh", highlight: "Madhya Pradesh", marker: true, zoomScale: 1.4 },
    "generation":     { metric: { column: "sewage_generation_mld", label: "Sewage generated (million litres/day)", max: 9200, unit: " MLD", sqrt: true } },
    "capacity":       { metric: { column: "installed_capacity_pct_of_generation", label: "Treatment capacity, % of sewage generated", max: 100, unit: "%" } },
    "treated":        { metric: { column: "actual_treated_pct_of_generation", label: "Sewage actually treated, % of generated", max: 100, unit: "%" } },
    "efficiency":     { metric: { column: "actual_treated_pct_of_installed_capacity", label: "Plant use, % of installed capacity", max: 100, unit: "%" } },
  };

  window.FOIW.graphics["sewage-map"] = function (el, ctx) {
    var d3 = window.d3;
    var features = ctx.data.features;
    var duration = ctx.reducedMotion ? 0 : 900;
    var css = getComputedStyle(el);
    var C = {
      orange: css.getPropertyValue("--fo-iw-orange").trim(),
      purple: css.getPropertyValue("--fo-iw-purple").trim(),
      pale: css.getPropertyValue("--fo-iw-pale").trim(),
      line: css.getPropertyValue("--fo-iw-line").trim(),
      neutral: "#dedcd4",
      faded: "#ecebe6",
    };
    var currentView = "india";

    // ---- build the DOM once -------------------------------------------
    var svg = d3.select(el).append("svg").attr("role", "img").attr("aria-label", "Map of India by state");
    var g = svg.append("g");
    var statePaths = g.selectAll("path").data(features).join("path")
      .attr("stroke", "#fff")
      .attr("vector-effect", "non-scaling-stroke")
      .attr("stroke-width", 0.8);
    var marker = g.append("g").attr("opacity", 0);
    marker.append("circle").attr("r", 5).attr("fill", C.orange).attr("stroke", "#fff").attr("vector-effect", "non-scaling-stroke").attr("stroke-width", 2);
    var markerLabel = marker.append("text").text("Indore").attr("class", "fo-iw-chart-ui").attr("font-weight", 700).attr("fill", "#0b0b0b");

    var legend = d3.select(el).append("div").attr("class", "fo-iw-legend fo-iw-chart-ui").style("opacity", 0);
    var legendTitle = legend.append("div").attr("class", "fo-iw-legend-title");
    legend.append("div").attr("class", "fo-iw-legend-bar")
      .style("background", "linear-gradient(to right," + C.pale + "," + C.orange + "," + C.purple + ")");
    var legendTicks = legend.append("div").attr("class", "fo-iw-legend-ticks");
    d3.select(el).append("div").attr("class", "fo-iw-source fo-iw-chart-ui").text(SOURCE);
    var tooltip = d3.select(el).append("div").attr("class", "fo-iw-tooltip fo-iw-chart-ui");

    var projection = d3.geoMercator();
    var path = d3.geoPath(projection);

    // ---- sizing: re-fit the map whenever the container changes size ----
    function layout() {
      var w = el.clientWidth, h = el.clientHeight;
      svg.attr("width", w).attr("height", h).attr("viewBox", [0, 0, w, h]);
      projection.fitExtent([[20, 70], [w - 20, h - 40]], ctx.data);
      statePaths.attr("d", path);
      var p = projection(INDORE);
      marker.attr("transform", "translate(" + p + ")");
      markerLabel.attr("x", 9).attr("y", 4);
    }

    function colorFor(metric) {
      var scale = d3.scaleLinear()
        .domain([0, metric.max / 2, metric.max])
        .range([C.pale, C.orange, C.purple])
        .interpolate(d3.interpolateLab)
        .clamp(true);
      return function (v) { return scale(metric.sqrt ? Math.sqrt(v / metric.max) * metric.max : v); };
    }

    // Zoom = a transform on the whole map group, computed from a state's bounds.
    function zoomTransform(view) {
      if (!view.zoom) return d3.zoomIdentity;
      var w = el.clientWidth, h = el.clientHeight;
      var target = features.find(function (f) { return f.properties.name === view.zoom; });
      var b = path.bounds(target);
      var k = 0.8 / Math.max((b[1][0] - b[0][0]) / w, (b[1][1] - b[0][1]) / h);
      var cx = (b[0][0] + b[1][0]) / 2, cy = (b[0][1] + b[1][1]) / 2;
      if (view.marker) {             // centre on Indore instead of the state
        var p = projection(INDORE);
        cx = p[0]; cy = p[1]; k *= view.zoomScale || 1;
      }
      return d3.zoomIdentity.translate(w / 2, h / 2).scale(k).translate(-cx, -cy);
    }

    // ---- the important part: draw a view --------------------------------
    function render(name, animate) {
      var view = VIEWS[name] || VIEWS.india;
      var t = svg.transition().duration(animate ? duration : 0);
      var metric = view.metric;
      var color = metric ? colorFor(metric) : null;

      statePaths.transition(t).attr("fill", function (d) {
        var s = d.properties.sewage;
        if (metric) return s ? color(s[metric.column]) : C.line;
        if (view.highlight) return d.properties.name === view.highlight ? C.orange : C.faded;
        return C.neutral;
      });

      var tf = zoomTransform(view);
      g.transition(t).attr("transform", tf.toString());
      marker.transition(t).attr("opacity", view.marker ? 1 : 0)
        .attr("transform", "translate(" + projection(INDORE) + ") scale(" + 1 / tf.k + ")");

      legend.style("opacity", metric ? 1 : 0);
      if (metric) {
        legendTitle.text(metric.label);
        legendTicks.html("<span>0</span><span>" + (metric.max === 100 ? "100%+" : d3.format(",")(metric.max) + metric.unit) + "</span>");
      }
    }

    // ---- hover tooltip -------------------------------------------------
    statePaths
      .on("pointermove", function (event, d) {
        var metric = (VIEWS[currentView] || {}).metric;
        var s = d.properties.sewage;
        var value = !metric ? "" : s ? " — " + d3.format(",")(s[metric.column]) + metric.unit : " — no data";
        var xy = d3.pointer(event, el);
        tooltip.text(d.properties.name + value).style("opacity", 1)
          .style("left", xy[0] + 12 + "px").style("top", xy[1] - 28 + "px");
      })
      .on("pointerleave", function () { tooltip.style("opacity", 0); });

    layout();
    render(currentView, false);

    return {
      update: function (view) { currentView = view; render(view, true); },
      resize: function () { layout(); render(currentView, false); },
    };
  };
})();
