// Head close-up emoji: crop clean/<n>.svg to the box in head_rects.txt (rounded square), add the same
// closing white border as the stickers, fit 94 % of the artboard, export emoji_head/<n>.svg + .png (1024).
// Names from vector/batch.txt.
(function () {
  var V = "D:/Linux/coding/taxi-bot/brand/mascot/poses/vector";
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  function rd(p, d) { var f = new File(p); if (!f.exists) return d; f.encoding = "UTF-8"; f.open("r"); var s = f.read(); f.close(); return s.replace(/\s+$/, ""); }
  var names = rd(V + "/batch.txt", "").replace(/\r/g, "").split("\n");
  var rects = {}, rl = rd(V + "/head_rects.txt", "").replace(/\r/g, "").split("\n");
  for (var r = 0; r < rl.length; r++) { var p = rl[r].split(" "); if (p.length == 4) rects[p[0]] = [parseFloat(p[1]), parseFloat(p[2]), parseFloat(p[3])]; }
  var bc = rd(V + "/border.txt", "14,24").split(",");
  var ofs = parseFloat(bc[0]) || 14, gap = bc.length > 1 ? parseFloat(bc[1]) : 24;
  // head_opts.txt: "<shape>,<outdir>"  shape = rr (rounded square) | circle; default rr,emoji_head
  var ho = rd(V + "/head_opts.txt", "rr,emoji_head").split(",");
  var SHAPE = ho[0], OUTD = ho.length > 1 ? ho[1] : "emoji_head";
  Folder(V + "/" + OUTD).create();
  var white = new RGBColor(); white.red = 255; white.green = 255; white.blue = 255;
  function paint(it) {
    if (it.typename == "PathItem") { it.filled = true; it.fillColor = white; it.stroked = false; }
    else if (it.typename == "CompoundPathItem") { for (var k = 0; k < it.pathItems.length; k++) paint(it.pathItems[k]); }
    else if (it.typename == "GroupItem") { for (var k = 0; k < it.pageItems.length; k++) paint(it.pageItems[k]); }
  }
  function menu(doc, it, cmds) { doc.selection = null; it.selected = true; for (var c = 0; c < cmds.length; c++) app.executeMenuCommand(cmds[c]); return doc.selection[0]; }
  function offsetExpand(doc, it, d) {
    doc.selection = null; it.selected = true;
    it.applyEffect('<LiveEffect name="Adobe Offset Path"><Dict data="R mlim 4 R ofst ' + d + ' I jntp 0 "/></LiveEffect>');
    return menu(doc, it, ["expandStyle"]);
  }
  var log = [];
  for (var i = 0; i < names.length; i++) {
    var nm = names[i]; if (!nm) continue;
    try {
      var box = rects[nm]; if (!box) throw "no head rect";
      var doc = app.open(new File(V + "/clean/" + nm + ".svg"));
      var ab = doc.artboards[0].artboardRect;
      var g = doc.groupItems.add(), tops = [];
      for (var t = 0; t < doc.layers[0].pageItems.length; t++) { var pi = doc.layers[0].pageItems[t]; if (pi !== g) tops.push(pi); }
      for (var t2 = tops.length - 1; t2 >= 0; t2--) tops[t2].move(g, ElementPlacement.PLACEATBEGINNING);
      // crop shape on top: rounded square, corner radius 22 % of the side
      var X = ab[0] + box[0], Y = ab[1] - box[1], S = box[2];
      var clip;
      if (SHAPE == "circle") clip = g.pathItems.ellipse(Y, X, S, S);
      else clip = g.pathItems.roundedRectangle(Y, X, S, S, S * 0.22, S * 0.22);
      clip.move(g, ElementPlacement.PLACEATBEGINNING);
      var art = menu(doc, g, ["Live Pathfinder Crop", "expandStyle"]);
      // border: same vector closing as the stickers
      var u = menu(doc, art.duplicate(), ["Live Pathfinder Add", "expandStyle"]);
      var border = menu(doc, offsetExpand(doc, u, ofs + gap), ["Live Pathfinder Add", "expandStyle"]);
      if (gap > 0) border = offsetExpand(doc, border, -gap);
      paint(border); border.zOrder(ZOrderMethod.SENDTOBACK); border.name = "sticker-border";
      doc.selection = null;
      var all2 = doc.groupItems.add(); border.move(all2, ElementPlacement.PLACEATEND); art.move(all2, ElementPlacement.PLACEATBEGINNING);
      var AW = ab[2] - ab[0], AH = ab[1] - ab[3], gb = all2.geometricBounds, gw = gb[2] - gb[0], gh = gb[1] - gb[3];
      var sc = Math.min(0.94 * AW / gw, 0.94 * AH / gh) * 100;
      all2.resize(sc, sc, true, true, true, true, sc, Transformation.CENTER);
      gb = all2.geometricBounds;
      all2.translate((ab[0] + AW / 2) - (gb[0] + gb[2]) / 2, (ab[3] + AH / 2) - (gb[1] + gb[3]) / 2);
      var so = new ExportOptionsSVG(); so.embedRasterImages = false; so.coordinatePrecision = 1;
      doc.exportFile(new File(V + "/" + OUTD + "/" + nm + ".svg"), ExportType.SVG, so);
      var po = new ExportOptionsPNG24(); po.horizontalScale = 114.4; po.verticalScale = 114.4;
      po.antiAliasing = true; po.transparency = true; po.artBoardClipping = true;
      doc.exportFile(new File(V + "/" + OUTD + "/" + nm + ".png"), ExportType.PNG24, po);
      doc.close(SaveOptions.DONOTSAVECHANGES);
      log.push(nm + " OK");
    } catch (e) {
      log.push(nm + " ERR " + e);
      try { app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
    }
  }
  return log.join("\n");
})();
