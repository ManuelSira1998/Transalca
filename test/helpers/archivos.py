import base64
import io

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
EJECUTABLE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 48 + b"This program cannot be run in DOS mode."
SCRIPT_HTML = b"<html><script>alert(document.cookie)</script></html>"


def archivo(contenido, nombre, mime):
    return (io.BytesIO(contenido), nombre, mime)


def png(nombre="foto.png"):
    return archivo(PNG_1X1, nombre, "image/png")
