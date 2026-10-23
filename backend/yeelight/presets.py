"""Hazır sahneler ve renk akışları."""
from .protocol import flow_expression

SCENES = [
    {"id": "calisma", "name": "Çalışma", "mode": "ct", "kelvin": 4000, "brightness": 100},
    {"id": "okuma", "name": "Okuma", "mode": "ct", "kelvin": 3500, "brightness": 80},
    {"id": "film", "name": "Film", "mode": "rgb", "hex": "#283CC8", "brightness": 20},
    {"id": "gece", "name": "Gece", "mode": "ct", "kelvin": 2700, "brightness": 5},
]

# start_cf: [tekrar (0 = sonsuz), bitince (0 = önceki duruma dön, 1 = son adımda kal), ifade]
FLOWS = [
    {"id": "disko", "name": "Disko", "description": "Hızlı renk geçişi", "count": 0, "action": 0,
     "steps": [(400, 1, 0xFF0040, 100), (400, 1, 0x00FF80, 100), (400, 1, 0x0080FF, 100), (400, 1, 0xFFEE00, 100)]},
    {"id": "mum", "name": "Mum ışığı", "description": "Titreyen sıcak ton", "count": 0, "action": 0,
     "steps": [(800, 2, 2700, 50), (800, 2, 1800, 30), (1200, 2, 2500, 45), (800, 2, 1700, 25)]},
    {"id": "gun_dogumu", "name": "Gün doğumu", "description": "15 dk yavaş aydınlanma", "count": 1, "action": 1,
     "steps": [(50, 1, 0xFF4D00, 1), (450_000, 2, 1700, 40), (450_000, 2, 3500, 100)]},
    {"id": "okyanus", "name": "Okyanus", "description": "Mavi-yeşil dalga", "count": 0, "action": 0,
     "steps": [(2000, 1, 0x0055FF, 70), (2000, 1, 0x00C2B8, 60), (2000, 1, 0x0A7AFF, 80)]},
    {"id": "polis", "name": "Polis", "description": "Kırmızı / mavi", "count": 0, "action": 0,
     "steps": [(250, 1, 0xFF0000, 100), (250, 1, 0x0000FF, 100)]},
]
FLOWS_BY_ID = {f["id"]: f for f in FLOWS}


def flow_params(flow: dict) -> list:
    return [flow["count"] * len(flow["steps"]), flow["action"], flow_expression(flow["steps"])]


def flow_public(flow: dict) -> dict:
    """API'de görünen hali: renkler arayüzdeki önizleme için hex olarak."""
    colors = [f"#{v:06X}" if m == 1 else None for _, m, v, _ in flow["steps"]]
    return {"id": flow["id"], "name": flow["name"], "description": flow["description"],
            "colors": [c for c in colors if c] or ["#FFB347", "#FF8A2A"]}
