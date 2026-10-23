import pytest

from helpers.api_client import unique_letters

BUG_PRD_01 = pytest.mark.xfail(strict=True, reason="BUG-PRD-01: GET /api/products/?page<=0 o per_page<0 genera un OFFSET/LIMIT negativo y responde 500")
BUG_PRD_02 = pytest.mark.xfail(strict=True, reason="BUG-PRD-02: GET /api/products/ no limita per_page (acepta 100000); /active si lo limita a 100")


def _fila(db, sql, params):
    with db["transalca"].cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


class TestMarcas:

    def test_admin_crea_marca_y_se_persiste(self, admin, db):
        nombre = "Marca " + unique_letters()
        response = admin.post("/api/brands/", json={"nombre": nombre, "descripcion": "Marca de prueba"})
        assert response.status_code == 200
        assert _fila(db, "SELECT descripcion_marca, estado FROM marcas WHERE nombre_marca = %s", (nombre,)) == {
            "descripcion_marca": "Marca de prueba", "estado": 1,
        }

    def test_consulta_por_nombre_devuelve_la_marca(self, admin):
        nombre = "Marca " + unique_letters()
        admin.post("/api/brands/", json={"nombre": nombre})
        response = admin.get(f"/api/brands/{nombre}")
        assert response.status_code == 200
        assert response.get_json()["data"]["nombre"] == nombre

    def test_marca_inexistente_devuelve_404(self, admin):
        assert admin.get("/api/brands/NoExiste" + unique_letters()).status_code == 404

    def test_marca_duplicada_devuelve_400(self, admin):
        nombre = "Marca " + unique_letters()
        assert admin.post("/api/brands/", json={"nombre": nombre}).status_code == 200
        response = admin.post("/api/brands/", json={"nombre": nombre})
        assert response.status_code == 400
        assert "nombre" in response.get_json()["errors"]

    @pytest.mark.parametrize("nombre", ["", "   ", None, "A", "M" * 31, "<b>marca</b>"])
    def test_nombre_invalido_devuelve_400(self, admin, nombre):
        response = admin.post("/api/brands/", json={"nombre": nombre})
        assert response.status_code == 400
        assert "nombre" in response.get_json()["errors"]

    def test_toggle_desactiva_y_reactiva(self, admin, db):
        nombre = "Marca " + unique_letters()
        admin.post("/api/brands/", json={"nombre": nombre})
        assert admin.put("/api/brands/toggle", json={"nombre": nombre}).status_code == 200
        assert _fila(db, "SELECT estado FROM marcas WHERE nombre_marca = %s", (nombre,))["estado"] == 0
        assert nombre not in [m["nombre"] for m in admin.get("/api/brands/active").get_json()["data"]]

    def test_crear_sin_sesion_devuelve_401(self, anon):
        assert anon.post("/api/brands/", json={"nombre": "Anonima"}).status_code == 401

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/brands solo exige sesion; un cliente puede crear marcas")
    def test_cliente_no_puede_crear_marcas(self, cliente_a, db):
        nombre = "Marca " + unique_letters()
        response = cliente_a.post("/api/brands/", json={"nombre": nombre})
        assert response.status_code == 403
        assert _fila(db, "SELECT nombre_marca FROM marcas WHERE nombre_marca = %s", (nombre,)) is None


class TestCategorias:

    def test_admin_crea_categoria_y_se_persiste(self, admin, db):
        nombre = "Categoria " + unique_letters()
        response = admin.post("/api/categories/", json={"nombre": nombre, "descripcion": "Categoria de prueba"})
        assert response.status_code == 200
        assert _fila(db, "SELECT estado FROM categorias WHERE nombre_categoria = %s", (nombre,)) == {"estado": 1}

    def test_check_unique_detecta_categoria_existente(self, admin):
        nombre = "Categoria " + unique_letters()
        admin.post("/api/categories/", json={"nombre": nombre})
        assert admin.get("/api/categories/check-unique", query_string={"value": nombre}).get_json()["unique"] is False
        assert admin.get("/api/categories/check-unique", query_string={"value": nombre + "x"}).get_json()["unique"] is True

    @pytest.mark.parametrize("nombre", ["", "ab", "C" * 31, None])
    def test_nombre_invalido_devuelve_400(self, admin, nombre):
        assert admin.post("/api/categories/", json={"nombre": nombre}).status_code == 400

    @pytest.mark.xfail(strict=True, reason="BUG-AUTHZ-01: /api/categories solo exige sesion; un cliente puede crear categorias")
    def test_cliente_no_puede_crear_categorias(self, cliente_a):
        response = cliente_a.post("/api/categories/", json={"nombre": "Categoria " + unique_letters()})
        assert response.status_code == 403


class TestProductos:

    def test_listado_publico_de_productos_activos_sin_sesion(self, anon):
        response = anon.get("/api/products/active")
        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

    @pytest.mark.parametrize("q", ["' OR '1'='1", "%", "_", "\\", "caucho' UNION SELECT 1 --", "🚗🔧"])
    def test_busqueda_con_caracteres_especiales_no_falla(self, admin, q):
        response = admin.get("/api/products/search", query_string={"q": q})
        assert response.status_code == 200
        assert isinstance(response.get_json()["data"], list)

    @pytest.mark.parametrize("params", [
        pytest.param({"page": "0"}, marks=BUG_PRD_01),
        pytest.param({"page": "-5"}, marks=BUG_PRD_01),
        {"page": "abc"},
        pytest.param({"page": "1", "per_page": "100000"}, marks=BUG_PRD_02),
        pytest.param({"page": "1", "per_page": "-1"}, marks=BUG_PRD_01),
    ])
    def test_paginacion_con_valores_limite_responde_200_acotado(self, admin, params):
        response = admin.get("/api/products/", query_string=params)
        assert response.status_code == 200
        body = response.get_json()
        if "per_page" in body:
            assert 1 <= body["per_page"] <= 100
            assert len(body["data"]) <= body["per_page"]

    def test_crear_producto_sin_sesion_devuelve_401(self, anon):
        assert anon.post("/api/products/", json={"codigo": "X1"}).status_code == 401
