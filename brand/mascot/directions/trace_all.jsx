(function(){
// Batch Image Trace for TulporGo mascot directions (Illustrator 2025).
// Output per item: vector/<nm>.ai, vector/<nm>.svg, vector/<nm>-preview.png
var BASE = "D:/Linux/coding/taxi-bot/brand/mascot/directions";
var ITEMS = [
  // [file, colors, pathFidelity, cornerFidelity, noiseFidelity]
  ["01-esport-emblema", 6, 85, 75, 20],
  ["02-uchayotgan-minimal", 3, 90, 75, 20],
  ["03-3d-haydovchi-maskot", 16, 85, 60, 15],
  ["06-samarqand-islimi", 8, 90, 75, 15],
  ["07-retro-70s-nishon", 8, 80, 70, 40],
  ["08-ilova-ikonka", 2, 90, 80, 25],
  ["09-chibi-stiker", 10, 85, 70, 15],
  ["10-taksi-haydovchi", 10, 85, 75, 15]
];
var outDir = new Folder(BASE + "/vector");
if (!outDir.exists) outDir.create();
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var log = [];
for (var i = 0; i < ITEMS.length; i++) {
  var it = ITEMS[i], nm = it[0];
  try {
    var src = new File(BASE + "/" + nm + ".png");
    var doc = app.documents.add(DocumentColorSpace.RGB, 895, 895);
    var p = doc.placedItems.add();
    p.file = src;
    p.width = 895; p.height = 895;
    p.position = [0, 895];
    var plugin = p.trace();
    var o = plugin.tracing.tracingOptions;
    o.tracingMode = TracingModeType.TRACINGMODECOLOR;
    o.tracingColorTypeValue = TracingColorType.TRACINGLIMITEDCOLOR;
    o.colors = it[1];
    o.pathFidelity = it[2]; o.cornerFidelity = it[3]; o.noiseFidelity = it[4];
    o.fills = true; o.strokes = false; o.ignoreWhite = false;
    o.tracingMethod = TracingMethodType.TRACINGMETHODABUTTING;
    app.redraw();
    plugin.tracing.expandTracing();
    var nPaths = doc.pathItems.length + doc.compoundPathItems.length;
    doc.saveAs(new File(BASE + "/vector/" + nm + ".ai"));
    var so = new ExportOptionsSVG();
    so.embedRasterImages = false; so.coordinatePrecision = 2;
    doc.exportFile(new File(BASE + "/vector/" + nm + ".svg"), ExportType.SVG, so);
    var po = new ExportOptionsPNG24();
    po.horizontalScale = 100; po.verticalScale = 100; po.antiAliasing = true; po.transparency = false; po.artBoardClipping = true;
    doc.exportFile(new File(BASE + "/vector/" + nm + "-preview.png"), ExportType.PNG24, po);
    doc.close(SaveOptions.DONOTSAVECHANGES);
    log.push(nm + " OK paths=" + nPaths);
  } catch (e) {
    log.push(nm + " ERR " + e);
    try { app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
  }
}
return log.join("\n");

})();
