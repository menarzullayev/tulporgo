// Open cleaned SVGs (vector/clean), add a uniform white sticker border, write final files.
// Names from vector/batch.txt.
// border.txt: "<offset>,<gap>" in points (default 14,24). The border is a vector CLOSING:
//   union -> offset(+offset+gap) -> offset(-gap). Nearby confetti/snowflakes merge into one outline
//   instead of getting their own border islands (problem B).
// variant.txt: "full" (default) -> svg/ ai/ png/;  "ns" (no ground shadow, for emoji) -> svg_ns/ png_ns/;
//   "em" (emoji TGS: simplified trace from clean_em/, no shadow) -> svg_em/ png_em/.
(function () {
  var V = "D:/Linux/coding/taxi-bot/brand/mascot/poses/vector";
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  function rd(p, d) { var f = new File(p); if (!f.exists) return d; f.encoding = "UTF-8"; f.open("r"); var s = f.read(); f.close(); return s.replace(/\s+$/, ""); }
  var names = rd(V + "/batch.txt", "").replace(/\r/g, "").split("\n");
  var bc = rd(V + "/border.txt", "14,24").split(",");
  var ofs = parseFloat(bc[0]) || 14, gap = bc.length > 1 ? parseFloat(bc[1]) : 24;
  var variant = rd(V + "/variant.txt", "full");
  // no nested ternary: ExtendScript evaluates `a ? b : c ? d : e` wrongly (gave "_em" for "ns")
  var sfx = "";
  if (variant == "ns") sfx = "_ns";
  else if (variant == "em") sfx = "_em";
  var noShadow = variant == "ns" || variant == "em";
  var CLEAN = variant == "em" ? "clean_em" : "clean";
  Folder(V + "/svg" + sfx).create(); Folder(V + "/png" + sfx).create(); Folder(V + "/ai").create();
  var white = new RGBColor(); white.red = 255; white.green = 255; white.blue = 255;
  function paint(it) {
    if (it.typename == "PathItem") { it.filled = true; it.fillColor = white; it.stroked = false; }
    else if (it.typename == "CompoundPathItem") { for (var k = 0; k < it.pathItems.length; k++) paint(it.pathItems[k]); }
    else if (it.typename == "GroupItem") { for (var k = 0; k < it.pageItems.length; k++) paint(it.pageItems[k]); }
  }
  function fillRGB(it) {
    var p = it.typename == "CompoundPathItem" ? (it.pathItems.length ? it.pathItems[0] : null) : it;
    if (!p || !p.filled || p.fillColor.typename != "RGBColor") return null;
    return [p.fillColor.red, p.fillColor.green, p.fillColor.blue];
  }
  function offsetExpand(doc, it, d) {
    doc.selection = null; it.selected = true;
    it.applyEffect('<LiveEffect name="Adobe Offset Path"><Dict data="R mlim 4 R ofst ' + d + ' I jntp 0 "/></LiveEffect>');
    doc.selection = null; it.selected = true;   // reselect: expandStyle ignores the effect otherwise
    app.executeMenuCommand("expandStyle");
    return doc.selection[0];
  }
  function unite(doc, it) {   // merge overlapping pieces into one shape (Pathfinder Add)
    doc.selection = null; it.selected = true;
    app.executeMenuCommand("Live Pathfinder Add"); app.executeMenuCommand("expandStyle");
    return doc.selection[0];
  }
  var log = [];
  for (var i = 0; i < names.length; i++) {
    var nm = names[i]; if (!nm) continue;
    try {
      var doc = app.open(new File(V + "/" + CLEAN + "/" + nm + ".svg"));
      var art = [], all = doc.pageItems;
      for (var a = 0; a < all.length; a++) {
        var it = all[a];
        if ((it.typename == "PathItem" || it.typename == "CompoundPathItem") && it.parent.typename != "CompoundPathItem") art.push(it);
      }
      // art bounds (top, bottom in Illustrator y-up coordinates)
      var T = -1e9, B = 1e9, L = 1e9, R = -1e9;
      for (var q = 0; q < art.length; q++) { var gb0 = art[q].geometricBounds; L = Math.min(L, gb0[0]); T = Math.max(T, gb0[1]); R = Math.max(R, gb0[2]); B = Math.min(B, gb0[3]); }
      var dropped = 0;
      if (noShadow) {
        // ground shadow: flat, low-saturation light grey or lavender shapes in the bottom 18 % of the art
        var keep = [];
        for (var s = 0; s < art.length; s++) {
          var c = fillRGB(art[s]), g = art[s].geometricBounds, w = g[2] - g[0], h = g[1] - g[3], cy = (g[1] + g[3]) / 2;
          var isShadow = c && (Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]) < 40) &&
                         ((c[0] + c[1] + c[2]) / 3 > 150) && ((c[0] + c[1] + c[2]) / 3 < 233) &&
                         (cy < B + 0.18 * (T - B)) && (w > 1.8 * h);
          if (isShadow) { art[s].remove(); dropped++; } else keep.push(art[s]);
        }
        art = keep;
      }
      var g = doc.groupItems.add();
      for (var b = 0; b < art.length; b++) art[b].duplicate(g, ElementPlacement.PLACEATEND);
      doc.selection = null; g.selected = true;
      app.executeMenuCommand("Live Pathfinder Add"); app.executeMenuCommand("expandStyle");
      var border = unite(doc, offsetExpand(doc, doc.selection[0], ofs + gap));
      if (gap > 0) border = offsetExpand(doc, border, -gap);
      // small border holes are filled afterwards in the SVG (fill_holes.py)
      var btype = border.typename; paint(border); border.zOrder(ZOrderMethod.SENDTOBACK); border.name = "sticker-border";
      doc.selection = null;
      // normalise: fit everything (border included) into 94 % of the artboard, centred -> no clipped borders, equal sizes
      var abr = doc.artboards[0].artboardRect, AW = abr[2] - abr[0], AH = abr[1] - abr[3];
      var all2 = doc.groupItems.add(), tops = [];
      for (var t = 0; t < doc.layers[0].pageItems.length; t++) { var pi = doc.layers[0].pageItems[t]; if (pi !== all2) tops.push(pi); }
      for (var t2 = tops.length - 1; t2 >= 0; t2--) tops[t2].move(all2, ElementPlacement.PLACEATBEGINNING);
      var gb = all2.geometricBounds, gw = gb[2] - gb[0], gh = gb[1] - gb[3];
      var sc = Math.min(0.94 * AW / gw, 0.94 * AH / gh) * 100;
      all2.resize(sc, sc, true, true, true, true, sc, Transformation.CENTER);
      gb = all2.geometricBounds;
      all2.translate((abr[0] + AW / 2) - (gb[0] + gb[2]) / 2, (abr[3] + AH / 2) - (gb[1] + gb[3]) / 2);
      var so = new ExportOptionsSVG(); so.embedRasterImages = false; so.coordinatePrecision = 1;
      doc.exportFile(new File(V + "/svg" + sfx + "/" + nm + ".svg"), ExportType.SVG, so);
      if (variant == "full") doc.saveAs(new File(V + "/ai/" + nm + ".ai"));
      var po = new ExportOptionsPNG24(); po.horizontalScale = 114.4; po.verticalScale = 114.4;
      po.antiAliasing = true; po.transparency = true; po.artBoardClipping = true;
      doc.exportFile(new File(V + "/png" + sfx + "/" + nm + ".png"), ExportType.PNG24, po);
      doc.close(SaveOptions.DONOTSAVECHANGES);
      log.push(nm + " OK border=" + btype + (noShadow ? " shadow-shapes=" + dropped : ""));
    } catch (e) {
      log.push(nm + " ERR " + e);
      try { app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
    }
  }
  return log.join("\n");
})();
