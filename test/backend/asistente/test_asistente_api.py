import pytest


def test_health_responde_json(anon):
    response = anon.get("/api/asistente/health")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/json")


@pytest.mark.parametrize("method, path", [("POST", "/api/asistente/shadow/candidate"), ("GET", "/api/asistente/shadow/health")])
def test_endpoints_obsoletos_responden_410(anon, method, path):
    response = anon.request(method, path, json={})
    assert response.status_code == 410
    assert response.json()["status"] == "deprecated"


@pytest.mark.parametrize("path", ["/api/asistente/metrics", "/api/asistente/learning-metrics", "/api/asistente/admin/ia-learning"])
def test_metricas_cerradas_para_anonimos(anon, path):
    assert anon.get(path).status_code == 403


def test_feedback_cerrado_para_anonimos(anon):
    assert anon.post("/api/asistente/feedback", json={"case_id": "FB-" + "A" * 20, "rating": "good"}).status_code == 403


@pytest.mark.xfail(strict=True, reason="BUG-IA-01: _metrics_allowed no reconoce la sesion real de un administrador y responde 403")
def test_administrador_ve_las_metricas(admin):
    assert admin.get("/api/asistente/metrics").status_code == 200
