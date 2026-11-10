"""Save captured pose screenshots into the library: clean the ChatGPT icon corner, name by pose number.

Usage: python save_poses.py <map.txt> <first> <last>
map.txt lines: "<pose_no> <captured file name in tool-results>"
"""
import sys, os
from PIL import Image, ImageDraw

T = r"C:\Users\nsn\.claude\projects\D--Linux-coding\dc58134d-16a7-4ba8-8e44-906a5f840607\tool-results"
NAMES = {
    21: "navruz", 22: "ramazon-iftor", 23: "hayit-tabrigi", 24: "mustaqillik", 25: "yangi-yil",
    26: "qish-qor-odam", 27: "bahor", 28: "kuz", 29: "oqish-boshlanishi", 30: "8-mart",
    31: "tugilgan-kun", 32: "qovun-mavsumi", 33: "hayron", 34: "xafa", 35: "uyalgan",
    36: "jahli-chiqqan", 37: "sevgi-rahmat", 38: "kulgidan-yumalayapti", 39: "charchagan", 40: "qorqib-ketgan",
    41: "hayajon", 42: "kechirim", 43: "mashina-yuvadi", 44: "yoqilgi", 45: "tamirlaydi",
    46: "kutyapti", 47: "eshik-ochadi", 48: "sumka-kotaradi", 49: "kalkulyator", 50: "pochta",
}
HERE = os.path.dirname(os.path.abspath(__file__))
m = dict(l.split() for l in open(sys.argv[1]) if l.strip())
lo, hi = int(sys.argv[2]), int(sys.argv[3])
done = []
for n in range(lo, hi + 1):
    f = m.get(str(n))
    if not f:
        print(n, "MISSING")
        continue
    im = Image.open(os.path.join(T, f)).convert("RGB")
    w, h = im.size
    k = w / 895
    ImageDraw.Draw(im).rectangle((0, int(850 * k), int(104 * k), h), fill=im.getpixel((int(150 * k), int(880 * k))))
    out = f"09-{n:02d}-{NAMES[n]}.png"
    im.save(os.path.join(HERE, out))
    done.append(out)
    print(n, out, im.size)
W = 330
s = Image.new("RGB", (len(done) * (W + 10) + 10, W + 20), "#333")
for i, n in enumerate(done):
    s.paste(Image.open(os.path.join(HERE, n)).resize((W, W), Image.LANCZOS), (10 + i * (W + 10), 10))
s.save(os.path.join(HERE, f"set2-{lo}-{hi}-sheet.png"))
