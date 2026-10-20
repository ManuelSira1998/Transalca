import pytest


class TestProductCatalogIntegration:
    """Pruebas de integración para el Clúster de Catálogo, Productos y Stock.

    Valida la orquestación e integridad referencial entre:
    - Categorías (/api/categories/)
    - Marcas (/api/brands/)
    - Productos (/api/products/)
    - Inventario y Sedes (stock y sucursales)
    """

    def test_unauthenticated_catalog_management_rejected(self, client):
        """Verifica que las rutas administrativas y no públicas exijan sesión activa."""
        # Categorías
        res_cat = client.post("/api/categories/", json={"nombre": "Cat Test"})
        assert res_cat.status_code == 401

        # Marcas
        res_brand = client.post("/api/brands/", json={"nombre": "Brand Test"})
        assert res_brand.status_code == 401

        # Marcas activas (no está en PUBLIC_API_PREFIXES por diseño de app.py)
        res_brand_act = client.get("/api/brands/active")
        assert res_brand_act.status_code == 401

        # Productos creación
        res_prod = client.post("/api/products/", json={"codigo": "TST-001", "nombre": "Prod Test"})
        assert res_prod.status_code == 401

        res_update = client.put("/api/products/update", json={"old_codigo": "CAU-001", "codigo": "CAU-001"})
        assert res_update.status_code == 401

        res_toggle = client.put("/api/products/toggle", json={"codigo": "CAU-001"})
        assert res_toggle.status_code == 401

        # Check unique y filtros internos requieren login
        res_chk = client.get("/api/products/check-unique?value=CAU-001")
        assert res_chk.status_code == 401

        res_flt = client.get("/api/products/category/Cauchos")
        assert res_flt.status_code == 401

    def test_public_catalog_active_views(self, client):
        """Verifica los catálogos públicos (/api/products/active y /api/categories/active)."""
        # Categorías activas
        res_cat = client.get("/api/categories/active")
        assert res_cat.status_code == 200
        cats = res_cat.get_json()["data"]
        cat_names = [c["nombre"] for c in cats]
        assert "Cauchos" in cat_names
        assert "Baterías" in cat_names
        assert "Inactiva" not in cat_names

        # Productos activos
        res_prod = client.get("/api/products/active")
        assert res_prod.status_code == 200
        prods = res_prod.get_json()["data"]
        prod_codes = [p["codigo"] for p in prods]
        assert "CAU-001" in prod_codes
        assert "BAT-001" in prod_codes
        assert "PROD-INACTIVO" not in prod_codes

    def test_category_product_count_aggregation(self, auth_client):
        """Verifica que el listado de categorías calcule dinámicamente el conteo de productos asociados."""
        response = auth_client.get("/api/categories/")
        assert response.status_code == 200
        data = response.get_json()["data"]

        cauchos_cat = next((c for c in data if c["nombre"] == "Cauchos"), None)
        assert cauchos_cat is not None
        assert "total_productos" in cauchos_cat
        assert cauchos_cat["total_productos"] >= 1

    def test_create_category_and_brand_success(self, auth_client):
        """Prueba el registro de una nueva categoría y una nueva marca con persistencia."""
        # Crear categoría
        res_c = auth_client.post("/api/categories/", json={"nombre": "Frenos", "descripcion": "Pastillas y discos de freno"})
        assert res_c.status_code == 200
        assert res_c.get_json()["status"] == "success"

        # Crear marca
        res_m = auth_client.post("/api/brands/", json={"nombre": "Brembo", "descripcion": "Frenos italianos de alta gama"})
        assert res_m.status_code == 200
        assert res_m.get_json()["status"] == "success"

        # Consultar detalle individual autenticado
        res_c_det = auth_client.get("/api/categories/Frenos")
        assert res_c_det.status_code == 200
        assert res_c_det.get_json()["data"]["nombre"] == "Frenos"

        res_m_det = auth_client.get("/api/brands/Brembo")
        assert res_m_det.status_code == 200
        assert res_m_det.get_json()["data"]["nombre"] == "Brembo"

        # Consultar marcas activas autenticado
        res_brand = auth_client.get("/api/brands/active")
        assert res_brand.status_code == 200
        brands = res_brand.get_json()["data"]
        brand_names = [m["nombre"] for m in brands]
        assert "Brembo" in brand_names
        assert "Pirelli" in brand_names
        assert "Marca Inactiva" not in brand_names

    def test_create_product_referential_integrity_rules(self, auth_client):
        """Valida las reglas de negocio de integridad referencial:

        No se puede registrar un producto con categoría o marca inexistente,
        ni sin al menos una sucursal asignada.
        """
        # 1. Categoría no existente
        payload_bad_cat = {
            "codigo": "FRE-001",
            "nombre": "Pastillas de Freno",
            "precio": 45.0,
            "categoria": "CategoriaFantasma",
            "marca": "Pirelli",
            "sucursal_ids": [1]
        }
        res_bad_cat = auth_client.post("/api/products/", json=payload_bad_cat)
        assert res_bad_cat.status_code == 400
        assert "categoria" in res_bad_cat.get_json().get("errors", {})

        # 2. Marca no existente
        payload_bad_brand = {
            "codigo": "FRE-001",
            "nombre": "Pastillas de Freno",
            "precio": 45.0,
            "categoria": "Cauchos",
            "marca": "MarcaInexistente",
            "sucursal_ids": [1]
        }
        res_bad_brand = auth_client.post("/api/products/", json=payload_bad_brand)
        assert res_bad_brand.status_code == 400
        assert "marca" in res_bad_brand.get_json().get("errors", {})

        # 3. Sin sucursales asignadas
        payload_no_suc = {
            "codigo": "FRE-001",
            "nombre": "Pastillas de Freno",
            "precio": 45.0,
            "categoria": "Cauchos",
            "marca": "Pirelli",
            "sucursal_ids": []
        }
        res_no_suc = auth_client.post("/api/products/", json=payload_no_suc)
        assert res_no_suc.status_code == 400

    def test_create_product_full_integration_with_stock(self, auth_client, mock_db):
        """Prueba la creación exitosa de un producto enlazado a Categoría, Marca y Sedes con Stock."""
        payload = {
            "codigo": "BAT-002",
            "nombre": "Batería 1000 AMP Heavy Duty",
            "descripcion": "Batería sellada para camiones",
            "precio": 120.00,
            "categoria": "Baterías",
            "marca": "Duncan",
            "sucursal_ids": [1, 2]
        }
        response = auth_client.post("/api/products/", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["codigo"] == "BAT-002"

        # Verificar detalle del producto consultado vía API autenticada
        res_det = auth_client.get("/api/products/detail/BAT-002")
        assert res_det.status_code == 200
        prod = res_det.get_json()["data"]
        assert prod["codigo"] == "BAT-002"
        assert prod["categoria"] == "Baterías"
        assert prod["marca"] == "Duncan"
        assert "Sede Central" in prod["sucursal_nombre"]
        assert "Sede Norte" in prod["sucursal_nombre"]

        # Verificar que se crearon registros en la tabla stock para ambas sedes
        stock_branches = [st["sucursal_id"] for st in mock_db.stock if st.get("producto_codigo") == "BAT-002"]
        assert 1 in stock_branches
        assert 2 in stock_branches

    def test_check_unique_product_code(self, auth_client):
        """Verifica la validación autenticada de código de producto único."""
        # Código existente
        res_ex = auth_client.get("/api/products/check-unique?value=CAU-001")
        assert res_ex.status_code == 200
        assert res_ex.get_json()["exists"] is True

        # Excluyendo el propio código
        res_self = auth_client.get("/api/products/check-unique?value=CAU-001&exclude=CAU-001")
        assert res_self.status_code == 200
        assert res_self.get_json()["exists"] is False

        # Código nuevo
        res_free = auth_client.get("/api/products/check-unique?value=COD-NUEVO-999")
        assert res_free.status_code == 200
        assert res_free.get_json()["exists"] is False

    def test_catalog_filtering_by_category_brand_and_sucursal(self, auth_client):
        """Verifica los filtros cruzados del catálogo comercial autenticado."""
        # 1. Filtro por categoría
        res_cat = auth_client.get("/api/products/category/Cauchos")
        assert res_cat.status_code == 200
        cat_items = res_cat.get_json()["data"]
        assert len(cat_items) >= 1
        assert all(p["categoria"] == "Cauchos" for p in cat_items)

        # 2. Filtro por marca
        res_brand = auth_client.get("/api/products/brand/Pirelli")
        assert res_brand.status_code == 200
        brand_items = res_brand.get_json()["data"]
        assert len(brand_items) >= 1
        assert all(p["marca"] == "Pirelli" for p in brand_items)

        # 3. Filtro por sucursal
        res_suc = auth_client.get("/api/products/sucursal/1")
        assert res_suc.status_code == 200
        suc_items = res_suc.get_json()["data"]
        assert len(suc_items) >= 1

    def test_update_product_and_sync_sucursales(self, auth_client, mock_db):
        """Prueba la actualización de un producto y la sincronización de sus sedes en stock."""
        # Modificar CAU-001 para que solo esté en sucursal 1 (retirando sucursal 2)
        payload = {
            "old_codigo": "CAU-001",
            "codigo": "CAU-001",
            "nombre": "Caucho 185/65 R15 Plus",
            "descripcion": "Versión mejorada",
            "precio": 70.00,
            "categoria": "Cauchos",
            "marca": "Pirelli",
            "sucursal_ids": [1]
        }
        res_update = auth_client.put("/api/products/update", json=payload)
        assert res_update.status_code == 200
        assert res_update.get_json()["status"] == "success"

        # Verificar detalle actualizado
        res_get = auth_client.get("/api/products/detail/CAU-001")
        assert res_get.status_code == 200
        prod = res_get.get_json()["data"]
        assert prod["nombre"] == "Caucho 185/65 R15 Plus"
        assert prod["precio"] == 70.0

        # Verificar sincronización de stock: sucursal 2 debe haberse desvinculado
        active_branch_ids = [st["sucursal_id"] for st in mock_db.stock if st.get("producto_codigo") == "CAU-001"]
        assert 1 in active_branch_ids
        assert 2 not in active_branch_ids

    def test_soft_delete_product_toggle(self, auth_client, client):
        """Verifica la desactivación lógica de un producto y su ocultamiento en el catálogo activo."""
        # Desactivar BAT-001
        res_toggle = auth_client.put("/api/products/toggle", json={"codigo": "BAT-001"})
        assert res_toggle.status_code == 200
        assert res_toggle.get_json()["status"] == "success"

        # Verificar que ya no aparece en /api/products/active
        res_active = client.get("/api/products/active")
        active_codes = [p["codigo"] for p in res_active.get_json()["data"]]
        assert "BAT-001" not in active_codes
