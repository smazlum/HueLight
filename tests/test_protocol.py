import os

import pytest

from backend.yeelight import discovery, miio, presets, protocol


def test_encode_is_newline_terminated_json():
    assert protocol.encode(7, "set_power", ["on", "smooth", 300]) == b'{"id": 7, "method": "set_power", "params": ["on", "smooth", 300]}\r\n'


def test_hex_roundtrip():
    assert protocol.hex_to_int("#FF8A3D") == 0xFF8A3D
    assert protocol.int_to_hex(0xFF8A3D) == "#FF8A3D"


def test_parse_props_maps_fields():
    s = protocol.parse_props({"power": "on", "bright": "42", "color_mode": "1", "rgb": "16711680",
                              "ct": "2700", "flowing": "1", "delayoff": "15", "name": "Ofis"})
    assert s == {"power": True, "brightness": 42, "mode": "rgb", "hex": "#FF0000", "kelvin": 2700,
                 "flowing": True, "timer_minutes_left": 15, "bulb_name": "Ofis"}
    assert protocol.parse_props({"delayoff": "0"}) == {"timer_minutes_left": None}


def test_parse_props_accepts_numeric_notification_values():
    # Gerçek ampulden yakalanan bildirimler: get_prop metin, props bildirimi sayı döndürüyor.
    assert protocol.parse_props({"color_mode": 1, "rgb": 16736256, "hue": 23, "sat": 100}) == {"mode": "rgb", "hex": "#FF6000"}
    assert protocol.parse_props({"color_mode": 2, "ct": 3000}) == {"mode": "ct", "kelvin": 3000}


def test_flow_expression_enforces_min_duration():
    assert protocol.flow_expression([(10, 1, 255, 50), (500, 2, 2700, 10)]) == "50,1,255,50,500,2,2700,10"


def test_flow_params_counts_steps():
    disko = presets.FLOWS_BY_ID["disko"]
    assert presets.flow_params(disko)[:2] == [0, 0]  # sonsuz, eski duruma dön
    sunrise = presets.FLOWS_BY_ID["gun_dogumu"]
    assert presets.flow_params(sunrise)[:2] == [3, 1]  # bir tur, son adımda kal


def test_discovery_parses_ssdp_reply():
    reply = ("HTTP/1.1 200 OK\r\nCache-Control: max-age=3600\r\nLocation: yeelight://192.168.1.50:55443\r\n"
             "id: 0x0000000012345678\r\nmodel: colorb\r\nname: \r\npower: on\r\n")
    bulb = discovery.parse_response(reply)
    assert (bulb["id"], bulb["ip"], bulb["port"], bulb["model"]) == ("0x0000000012345678", "192.168.1.50", 55443, "colorb")
    assert discovery.parse_response("HTTP/1.1 200 OK\r\nLocation: http://x\r\n") is None


def test_miio_packet_roundtrip_and_checksum():
    token = os.urandom(16)
    packet = miio.build_packet(token, 0x1234, 99, {"id": 1, "method": "set_ps", "params": ["cfg_lan_ctrl", "1"]})
    assert packet[:2] == b"\x21\x31" and int.from_bytes(packet[2:4], "big") == len(packet)
    assert miio.parse_packet(token, packet)["params"] == ["cfg_lan_ctrl", "1"]
    with pytest.raises(miio.MiioError):
        miio.parse_packet(os.urandom(16), packet)


def test_miio_hello_hidden_token():
    header = miio._HEADER.pack(0x2131, 32, 0, 0xABC, 5)
    assert miio.parse_hello(header + b"\xff" * 16) == (0xABC, 5, None)
    token = os.urandom(16)
    assert miio.parse_hello(header + token)[2] == token
