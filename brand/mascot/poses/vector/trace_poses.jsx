// Trace pose PNGs (895 px) into raw SVGs. Reads names from vector/batch.txt (one per line).
// Settings come from vector/settings.txt: colors,pathFidelity,cornerFidelity,noiseFidelity
(function () {
  var V = "D:/Linux/coding/taxi-bot/brand/mascot/poses/vector";
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  function readLines(p) { var f = new File(p); f.encoding = "UTF-8"; f.open("r"); var s = f.read(); f.close(); return s.replace(/\r/g, "").split("\n"); }
  var names = readLines(V + "/batch.txt"), sl = readLines(V + "/settings.txt"), cfg = sl[0].split(",");
  var OUT = (sl.length > 1 && sl[1]) ? sl[1] : "raw";   // optional 2nd line: output folder (experiments)
  Folder(V + "/" + OUT).create(); var PREP = (sl.length > 2 && sl[2]) ? sl[2] : "prep"; Folder(V + "/" + OUT + "png").create();
  var log = [];
  for (var i = 0; i < names.length; i++) {
    var nm = names[i]; if (!nm) continue;
    var t0 = new Date().getTime();
    try {
      var doc = app.documents.add(DocumentColorSpace.RGB, 895, 895);
      var p = doc.placedItems.add(); p.file = new File(V + "/" + PREP + "/" + nm + ".png");
      p.width = 895; p.height = 895; p.position = [0, 895];
      var plugin = p.trace(), o = plugin.tracing.tracingOptions;
      o.tracingMode = TracingModeType.TRACINGMODECOLOR;
      o.tracingColorTypeValue = TracingColorType.TRACINGLIMITEDCOLOR;
      o.colors = parseInt(cfg[0], 10); o.pathFidelity = parseInt(cfg[1], 10);
      o.cornerFidelity = parseInt(cfg[2], 10); o.noiseFidelity = parseInt(cfg[3], 10);
      o.fills = true; o.strokes = false; o.ignoreWhite = false;
      o.tracingMethod = TracingMethodType.TRACINGMETHODABUTTING;
      app.redraw(); plugin.tracing.expandTracing();
      var n = doc.pathItems.length;
      var so = new ExportOptionsSVG(); so.embedRasterImages = false; so.coordinatePrecision = 2;
      doc.exportFile(new File(V + "/" + OUT + "/" + nm + ".svg"), ExportType.SVG, so);
      // 1:1 raster of the trace, for measuring fidelity against src/ (compare_trace.py)
      var po = new ExportOptionsPNG24(); po.antiAliasing = true; po.transparency = false; po.artBoardClipping = true;
      doc.exportFile(new File(V + "/" + OUT + "png/" + nm + ".png"), ExportType.PNG24, po);
      doc.close(SaveOptions.DONOTSAVECHANGES);
      log.push(nm + " OK paths=" + n + " " + Math.round((new Date().getTime() - t0) / 1000) + "s");
    } catch (e) {
      log.push(nm + " ERR " + e);
      try { app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
    }
  }
  return log.join("\n");
})();
