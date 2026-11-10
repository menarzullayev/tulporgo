"""Send each swipe-cue variant (A-D) as a rich slideshow post via @tulporgobot."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_variants import call, owner_chat, HERE
from send_carousel_common import UZ_TITLE, UZ_LINES, RU, BTN_TAXI, BTN_DRV

LABELS = {"A": "A · O'ngda strelka + «Varaqlang»", "B": "B · Hisoblagiç «1/4 →»",
          "C": "C · Keyingi rasmning çeti ko'rinib turadi", "D": "D · «👉 Surib köring »»»"}

cid = owner_chat()
call("sendMessage", {"chat_id": cid, "text": "Slideshow uçun «keyingi rasm bor» belgisi: 4 xil variant. Har birini varaqlab ko'ring."})
for cue, label in LABELS.items():
    d = os.path.join(HERE, "carousel", f"cue-{cue}")
    files = {f"p{i}": os.path.join(d, f"f{i + 1}.png") for i in range(4)}
    rich = {"blocks": [
        {"type": "heading", "size": 2, "text": f"{label}"},
        {"type": "slideshow", "blocks": [{"type": "photo", "photo": {"type": "photo", "media": f"attach://p{i}"}} for i in range(4)]},
        {"type": "paragraph", "text": {"type": "bold", "text": UZ_TITLE}},
        *[{"type": "paragraph", "text": l} for l in UZ_LINES],
        {"type": "expandable_blockquote", "text": RU},
        {"type": "buttons", "buttons": [BTN_TAXI, BTN_DRV]},
    ]}
    m = call("sendRichMessage", {"chat_id": cid, "rich_message": json.dumps(rich)}, files)
    print(cue, "ok", m["message_id"])
