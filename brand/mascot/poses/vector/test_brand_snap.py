from brand_snap import snap, BRAND

def svg(*cols):
    return "".join(f'<path style="fill:{c};" d="M0 0"/>' for c in cols)

def test_near_brand_yellow_is_snapped():
    out, st = snap(svg("#FDC52E"))
    assert "fill:#FFC72C" in out and st["snapped"] == 1

def test_prop_green_is_kept():            # negative: a tree green must not become a brand colour
    out, st = snap(svg("#2E7D32"))
    assert "fill:#2E7D32" in out and st["snapped"] == 0

def test_confetti_purple_is_kept():       # negative
    out, st = snap(svg("#9B4DCA"))
    assert "#9B4DCA" in out and st["snapped"] == 0

def test_exact_brand_not_counted():
    out, st = snap(svg("#111214"))
    assert st["snapped"] == 0 and "#111214" in out

def test_white_bg_entry_not_in_brand():
    assert "#FFFFFF" not in BRAND
