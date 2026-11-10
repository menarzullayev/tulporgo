// Dark-mode fixes for TulporGo brand vectors (2026-11-09 decisions):
// 01, 07: remove stray specks outside the badge; 03: remove floor shadow + light gaps, add white sticker outline.
(function () {
  var D = "D:/Linux/coding/taxi-bot/brand/mascot/directions/vector";
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  var log = [];

  function hex(c) {
    try { if (c.typename == "RGBColor") { var h = function (v) { var s = Math.round(v).toString(16); return s.length < 2 ? "0" + s : s; }; return "#" + h(c.red) + h(c.green) + h(c.blue); } } catch (e) {}
    return "";
  }
  function fillOf(it) {
    if (it.typename == "PathItem") return hex(it.fillColor);
    if (it.typename == "CompoundPathItem" && it.pathItems.length) return hex(it.pathItems[0].fillColor);
    return "";
  }
  function box(it, ab) { var b = it.geometricBounds; return { x1: b[0] - ab[0], y1: ab[1] - b[1], x2: b[2] - ab[0], y2: ab[1] - b[3] }; }
  function topLevelShapes(doc) {
    var out = [], all = doc.pageItems;
    for (var i = 0; i < all.length; i++) {
      var it = all[i];
      if ((it.typename == "PathItem" || it.typename == "CompoundPathItem") && it.parent.typename != "CompoundPathItem") out.push(it);
    }
    return out;
  }
  function removeWhere(doc, pred) {
    var ab = doc.artboards[0].artboardRect, items = topLevelShapes(doc), kill = [];
    for (var i = 0; i < items.length; i++) if (pred(fillOf(items[i]), box(items[i], ab))) kill.push(items[i]);
    for (var j = 0; j < kill.length; j++) kill[j].remove();
    return kill.length;
  }
  function exportAll(doc, name) {
    doc.saveAs(new File(D + "/" + name + ".ai"));
    var so = new ExportOptionsSVG(); so.embedRasterImages = false; so.coordinatePrecision = 2;
    doc.exportFile(new File(D + "/" + name + ".svg"), ExportType.SVG, so);
    var po = new ExportOptionsPNG24(); po.horizontalScale = 114.4; po.verticalScale = 114.4; po.antiAliasing = true; po.transparency = true; po.artBoardClipping = true;
    doc.exportFile(new File(D + "/" + name + "-1024.png"), ExportType.PNG24, po);
  }
  function dist(b) { var cx = (b.x1 + b.x2) / 2 - 447.5, cy = (b.y1 + b.y2) / 2 - 447.5; return Math.sqrt(cx * cx + cy * cy); }

  // 01: white specks left of the circle
  var doc = app.open(new File(D + "/01-esport-emblema-brand.ai"));
  var n = removeWhere(doc, function (f, b) { return f == "#ffffff" && b.x2 < 70 && b.y1 > 425 && b.y2 < 460; });
  exportAll(doc, "01-esport-emblema-brand"); doc.close(SaveOptions.DONOTSAVECHANGES); log.push("01 removed " + n);

  // 07: specks outside the round badge (badge radius ~418)
  doc = app.open(new File(D + "/07-retro-70s-nishon-brand.ai"));
  n = removeWhere(doc, function (f, b) { return dist(b) > 440 && (b.x2 - b.x1) < 40 && (b.y2 - b.y1) < 40; });
  exportAll(doc, "07-retro-70s-nishon-brand"); doc.close(SaveOptions.DONOTSAVECHANGES); log.push("07 removed " + n);

  // 03: floor shadow (cream shapes low in the frame) + light background gaps below the head
  doc = app.open(new File(D + "/03-3d-haydovchi-maskot-brand.ai"));
  n = removeWhere(doc, function (f, b) {
    if ((f == "#e6d2bc" || f == "#cfb497") && b.y1 >= 824) return true;
    if (f == "#f4f3f3" && b.y1 > 350) return true;
    return false;
  });
  log.push("03 removed " + n);
  // white sticker outline: duplicate everything into a group, unite, offset outward, fill white, send to back
  var art = topLevelShapes(doc);
  var g = doc.groupItems.add();
  for (var i = 0; i < art.length; i++) art[i].duplicate(g, ElementPlacement.PLACEATEND);
  doc.selection = null; g.selected = true;
  app.executeMenuCommand("Live Pathfinder Add");
  app.executeMenuCommand("expandStyle");
  var base = doc.selection[0];
  base.applyEffect('<LiveEffect name="Adobe Offset Path"><Dict data="R mlim 4 R ofst 14 I jntp 0 "/></LiveEffect>');
  doc.selection = null; base.selected = true;
  app.executeMenuCommand("expandStyle");
  var outline = doc.selection[0];
  var white = new RGBColor(); white.red = 255; white.green = 255; white.blue = 255;
  function paint(it) {
    if (it.typename == "PathItem") { it.filled = true; it.fillColor = white; it.stroked = false; }
    else if (it.typename == "CompoundPathItem") { for (var k = 0; k < it.pathItems.length; k++) paint(it.pathItems[k]); }
    else if (it.typename == "GroupItem") { for (var k = 0; k < it.pageItems.length; k++) paint(it.pageItems[k]); }
  }
  paint(outline);
  outline.zOrder(ZOrderMethod.SENDTOBACK);
  log.push("03 outline " + outline.typename);
  exportAll(doc, "03-3d-haydovchi-maskot-brand"); doc.close(SaveOptions.DONOTSAVECHANGES);
  return log.join("\n");
})();
