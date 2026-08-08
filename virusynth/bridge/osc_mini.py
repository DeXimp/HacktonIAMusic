"""Codec OSC 1.0 mínimo en stdlib puro — plan B si python-osc no está instalado.

Soporta lo único que ViruSynth necesita: mensajes con argumentos i (int32),
f (float32) y s (string), big-endian con padding a 4 bytes, y desempaquetado
plano de bundles (#bundle). Suficiente para hablar con [oscparse]/[oscformat]
de Pure Data vanilla.
"""
from __future__ import annotations

import struct
from typing import Any, Iterator


def _pad4(data: bytes) -> bytes:
    return data + b"\x00" * ((4 - len(data) % 4) % 4)


def _osc_string(s: str) -> bytes:
    return _pad4(s.encode("utf-8", errors="replace") + b"\x00")


def encode(address: str, *args: Any) -> bytes:
    """Serializa un mensaje OSC. Tipos: bool/int->i, float->f, str->s."""
    tags = ","
    payload = b""
    for a in args:
        if isinstance(a, bool):
            a = int(a)
        if isinstance(a, int):
            tags += "i"
            payload += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            payload += struct.pack(">f", a)
        else:
            tags += "s"
            payload += _osc_string(str(a))
    return _osc_string(address) + _osc_string(tags) + payload


def _read_string(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\x00", pos)
    s = data[pos:end].decode("utf-8", errors="replace")
    end += 1
    end += (4 - end % 4) % 4
    return s, end


def _decode_message(data: bytes) -> tuple[str, list[Any]]:
    address, pos = _read_string(data, 0)
    args: list[Any] = []
    if pos >= len(data):
        return address, args
    tags, pos = _read_string(data, pos)
    for tag in tags.lstrip(","):
        if tag == "i":
            args.append(struct.unpack(">i", data[pos:pos + 4])[0])
            pos += 4
        elif tag == "f":
            args.append(struct.unpack(">f", data[pos:pos + 4])[0])
            pos += 4
        elif tag == "s":
            s, pos = _read_string(data, pos)
            args.append(s)
        elif tag in ("T", "F", "N"):
            args.append({"T": True, "F": False, "N": None}[tag])
        else:  # tipo no soportado: abortar el resto con lo ya parseado
            break
    return address, args


def decode(data: bytes) -> Iterator[tuple[str, list[Any]]]:
    """Itera (address, args) de un datagrama; aplana bundles anidados."""
    if data.startswith(b"#bundle\x00"):
        pos = 16  # "#bundle\0" + timetag de 8 bytes
        while pos + 4 <= len(data):
            size = struct.unpack(">i", data[pos:pos + 4])[0]
            pos += 4
            yield from decode(data[pos:pos + size])
            pos += size
    elif data:
        yield _decode_message(data)
