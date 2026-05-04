(function () {
  function optsForStyle(style) {
    switch (style) {
      case "date":
        return { dateStyle: "short" };
      case "datetime_sec":
        return { dateStyle: "short", timeStyle: "medium" };
      case "datetime":
      default:
        return { dateStyle: "short", timeStyle: "short" };
    }
  }

  function formatSynLocalTimes() {
    document.querySelectorAll("time.syn-local-dt").forEach(function (el) {
      var iso = el.getAttribute("datetime");
      if (!iso) return;
      var d = new Date(iso);
      if (Number.isNaN(d.getTime())) return;
      var style = el.getAttribute("data-dt-style") || "datetime";
      try {
        el.textContent = new Intl.DateTimeFormat(undefined, optsForStyle(style)).format(d);
      } catch (e) {
        el.textContent = iso;
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", formatSynLocalTimes);
  } else {
    formatSynLocalTimes();
  }
})();
