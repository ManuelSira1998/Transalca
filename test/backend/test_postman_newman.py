import json
import shutil
import subprocess
from pathlib import Path

import pytest

POSTMAN_DIR = Path(__file__).resolve().parent / "postman"
COLLECTION = POSTMAN_DIR / "transalca.postman_collection.json"
ENVIRONMENT = POSTMAN_DIR / "transalca_local.postman_environment.json"


def test_la_coleccion_y_el_entorno_son_validos():
    coleccion = json.loads(COLLECTION.read_text(encoding="utf-8"))
    entorno = json.loads(ENVIRONMENT.read_text(encoding="utf-8"))
    assert coleccion["info"]["schema"].endswith("/v2.1.0/collection.json")
    peticiones = [item for carpeta in coleccion["item"] for item in carpeta["item"]]
    assert len(peticiones) >= 20
    for peticion in peticiones:
        assert peticion["request"]["url"].startswith("{{baseUrl}}/"), peticion["name"]
        assert any(e["listen"] == "test" for e in peticion["event"]), peticion["name"]
    assert {v["key"] for v in entorno["values"]} >= {"baseUrl", "adminEmail", "password"}


def test_coleccion_postman_con_newman(live_server, tmp_path):
    newman = shutil.which("newman")
    if not newman:
        pytest.skip("newman no esta instalado (npm install -g newman)")
    reporte = tmp_path / "newman.json"
    resultado = subprocess.run(
        [newman, "run", str(COLLECTION), "-e", str(ENVIRONMENT),
         "--env-var", f"baseUrl={live_server}",
         "--reporters", "cli,json", "--reporter-json-export", str(reporte),
         "--color", "off", "--disable-unicode"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    assert reporte.exists(), resultado.stdout + resultado.stderr
    stats = json.loads(reporte.read_text(encoding="utf-8"))["run"]["stats"]
    assert stats["requests"]["failed"] == 0, resultado.stdout
    assert stats["assertions"]["failed"] == 0, resultado.stdout
    assert stats["assertions"]["total"] >= 60
    assert resultado.returncode == 0, resultado.stdout
