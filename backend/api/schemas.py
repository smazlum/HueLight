from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..security import is_private
from ..yeelight import protocol

HEX = r"^#[0-9A-Fa-f]{6}$"


class AddDevice(BaseModel):
    ip: str
    port: int = Field(protocol.PORT, ge=1, le=65535)
    name: str = Field("", max_length=40)

    @field_validator("ip")
    @classmethod
    def private_only(cls, v: str) -> str:
        if not is_private(v):
            raise ValueError("Yalnızca yerel ağ adresi (192.168.x.x, 10.x.x.x …) eklenebilir")
        return v


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class Power(BaseModel):
    on: bool


class Color(BaseModel):
    hex: str = Field(pattern=HEX)


class Brightness(BaseModel):
    value: int = Field(ge=1, le=100)


class Temperature(BaseModel):
    kelvin: int = Field(ge=protocol.KELVIN_MIN, le=protocol.KELVIN_MAX)


class SceneRef(BaseModel):
    scene_id: str


class FlowRef(BaseModel):
    flow_id: str


class Timer(BaseModel):
    minutes: int = Field(ge=1, le=1440)


class NewScene(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    mode: Literal["rgb", "ct"]
    hex: str | None = Field(None, pattern=HEX)
    kelvin: int | None = Field(None, ge=protocol.KELVIN_MIN, le=protocol.KELVIN_MAX)
    brightness: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def value_for_mode(self):
        if (self.mode == "rgb" and not self.hex) or (self.mode == "ct" and not self.kelvin):
            raise ValueError("rgb sahnesi için hex, ct sahnesi için kelvin gerekli")
        return self


class Provision(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(max_length=63)
    force: bool = False  # kayıtlı şifreyle eşleşmese de gönder (kayıtlı şifre eski olabilir)

    @field_validator("password")
    @classmethod
    def wpa_length(cls, v: str) -> str:
        if v and not 8 <= len(v) <= 63:  # boş: şifresiz ağ
            raise ValueError("Wi-Fi şifresi 8–63 karakter olmalı")
        return v
