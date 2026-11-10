from drop_magenta import drop, is_mag
svg='<svg><path style="fill:#FF00FF;" d="M0,0z"/><path style="fill:#F208EE;" d="M1,1z"/><path style="fill:#E91E63;" d="M2,2z"/><path style="fill:#FFC72C;" d="M3,3z"/></svg>'
out, st = drop(svg)
assert st["removed"] == 2 and "#E91E63" in out and "#FFC72C" in out, (st, out)   # pink-red heart colour must stay
assert not is_mag("#FCA082") and not is_mag("#EF6B5D")                             # character cheeks/blush stay
print("PASS drop_magenta")


def test_islands_counts_separate_pieces():
    import numpy as np
    from check_final import islands
    a = np.zeros((200, 200), dtype=int)
    a[20:120, 20:120] = 255
    assert islands(a) == 1
    for i in range(5):                      # negative: 5 detached confetti blobs are counted
        a[150:160, 10 + i * 35:20 + i * 35] = 255
    assert islands(a) == 6
