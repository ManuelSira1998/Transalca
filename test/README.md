# Pruebas automatizadas de Transalca

```
test/
├── conftest.py              # BD de prueba (fixtures de sesión), servidor HTTP real, stubs de servicios externos
├── helpers/                 # cargador de esquema, datos de prueba, clientes HTTP y archivos de muestra
├── unit/                    # unitarias con mocks (pytest-mock / unittest.mock), sin BD ni red
│   ├── conftest.py          # clientes Flask y sesiones compartidos
│   ├── <modulo>/            # controladores y modelos por módulo
│   ├── core/                # validación, guards, constructores SQL, cabeceras y errores de app.py
│   └── api_simulada/        # flujos HTTP completos sobre una BD simulada en memoria
├── integration/             # integración real contra db_transalca_test y db_mantenimiento_test
│   ├── negocio/             # venta→pago→stock, crédito, compras, comisiones, predicciones, facturas QR
│   ├── archivos/            # subida de imágenes, comprobantes y respaldos
│   └── <modulo>/            # auth, usuarios, roles, catálogo, vehículos, tickets, empresas, promociones, QR...
├── backend/                 # API por HTTP real (pytest + requests) contra un servidor sobre las BD _test
│   ├── autorizacion/        # matrices de permisos: cliente, empleado sin rol, vendedor, mecánico
│   ├── postman/             # colección y entorno Postman (se ejecutan con newman)
│   └── <modulo>/
├── smoke/                   # humo: servicios, BD, flujos vitales y pantallas en Chromium (Playwright)
└── sqlmap/ zap/ bandit/     # artefactos de escaneos de seguridad (no se ejecutan con pytest)
```

Las pruebas de `componente_ia/tests/` se mantienen en su ubicación original.

## Dependencias

```powershell
.\.venv\Scripts\python.exe -m pip install pytest pytest-mock pytest-cov coverage requests playwright
.\.venv\Scripts\python.exe -m playwright install chromium
npm install -g newman
```

Las pruebas de integración, backend y humo necesitan MariaDB/MySQL (XAMPP). Las bases
`db_transalca_test` y `db_mantenimiento_test` se crean solas y reciben el esquema de `db/`.

## Ejecutar

```powershell
.\.venv\Scripts\python.exe -m pytest                     # todo (unos 4 minutos)
.\.venv\Scripts\python.exe -m pytest -m unit             # unitarias (segundos, sin MySQL)
.\.venv\Scripts\python.exe -m pytest -m integration      # integración
.\.venv\Scripts\python.exe -m pytest -m backend          # API por HTTP + colección Postman
.\.venv\Scripts\python.exe -m pytest -m smoke            # humo
.\.venv\Scripts\python.exe -m pytest --cov=app --cov=routes --cov=config --cov=controller --cov=model --cov-report=html
```

Variables opcionales: `TEST_DB_HOST`, `TEST_DB_PORT`, `TEST_DB_USER`, `TEST_DB_PASSWORD`,
`TEST_DB_TRANSALCA`, `TEST_DB_MANTENIMIENTO` (deben terminar en `_test`) y `TEST_DB_KEEP=1`.

Resultado de referencia: 2398 pasan y 140 xfail (40 bugs conocidos); cobertura 79 %.

## Bugs conocidos (marcados con `xfail(strict=True)`)

Si un bug se corrige, su prueba pasa y pytest la reporta como `XPASS(strict)`: hay que quitar la marca.

| ID | Gravedad | Descripción |
|---|---|---|
| BUG-AUTHZ-01 | Alta | 22 lecturas y 14 escrituras de administración solo exigen sesión; un cliente pasa el control de acceso |
| BUG-AUTHZ-02 | Alta | Pagos: un cliente lista todos los comprobantes y puede aprobar pagos |
| BUG-AUTHZ-03 | Alta | Respaldos: descargar y borrar solo exigen sesión |
| BUG-AUTHZ-04 | Alta | Los permisos por módulo no se aplican: empleados sin el permiso (sin rol, vendedor, mecánico, operador) acceden igual; un mecánico cambia el porcentaje de su propia comisión |
| BUG-USR-01 | Alta | Listado, detalle y búsqueda de usuarios devuelven `password_hash` |
| BUG-EXP-01 | Alta | `/componente_ia/<ruta>` entrega código fuente y datos internos sin sesión |
| BUG-QR-01 | Alta | Un cliente puede leer, borrar y generar la imagen de QR de otro cliente |
| BUG-STK-01 | Alta | El carrito y el checkout no comprueban el stock disponible |
| BUG-STK-02 | Alta | Aprobar un pago antes rechazado deja la orden aprobada sin descontar stock |
| BUG-STK-03 | Alta | Una orden sin sucursal descuenta el producto en todas las sucursales al aprobarse |
| BUG-COM-01 | Alta | Al completar un servicio, el porcentaje de comisión no se valida (negativos o >100) |
| BUG-AUTH-01 | Media | `/auth/do_recover` revela si un correo está registrado |
| BUG-AUTH-02 | Media | El parámetro `next` del login acepta `/\dominio` (redirección abierta) |
| BUG-UPL-01 | Media | No se verifica el contenido de los archivos: un ejecutable con nombre y tipo de imagen se guarda |
| BUG-UPL-02 | Media | El carnet del vehículo acepta el archivo si la extensión **o** el MIME parecen de imagen |
| BUG-NET-01 | Media | Las tasas del BCV se consultan con `verify=False` (sin verificar TLS) |
| BUG-PROMO-03 | Media | El frontend elimina promociones con `DELETE /api/promotions/<id>`, ruta inexistente (405) |
| BUG-VLOG-01 | Media | El kilometraje de la bitácora no se valida (texto da 500, negativos se guardan) |
| BUG-PRC-02 | Media | `/api/pricing/calculate` acepta precios negativos o cero |
| BUG-PRC-03 | Media | `/api/pricing/rates/manual` no valida `monto` (texto da 500, negativos se guardan) |
| BUG-IA-01 | Media | Las métricas del asistente leen claves de sesión que el login nunca crea |
| BUG-IA-02 | Media | Las métricas del asistente quedan abiertas cuando `TESTING=True` |
| BUG-CART-01 | Baja | `cantidad: 0` en el carrito se convierte en 1 sin error |
| BUG-SRV-01 | Baja | `duracion_estimada: 0` en servicios se convierte en 60 sin error |
| BUG-PROMO-01 | Baja | `puntos_requeridos: 0` se convierte en 1 sin error |
| BUG-PROMO-02 | Baja | Asignar una tarjeta a una promoción inexistente responde 500 |
| BUG-INV-01 | Baja | Ajustar stock de un producto inexistente responde 500 |
| BUG-PM-01 | Baja | Una moneda no textual en métodos de pago responde 500 |
| BUG-API-01 | Baja | Cuerpo no JSON, JSON malformado o mayor a 16 MB responde 500 en vez de 400/413/415 |
| BUG-API-02 | Baja | Un JSON escalar (texto, número, booleano) en vez de objeto responde 500 |
| BUG-API-03 | Baja | `/api/orders/cart/count` devuelve el conteo como texto |
| BUG-HTTP-01 | Baja | Con el servidor de `app.py` la respuesta lleva dos cabeceras `Server` |
| BUG-PRD-01 | Baja | `GET /api/products/?page<=0` o `per_page<0` responde 500 |
| BUG-PRD-02 | Baja | `GET /api/products/` no limita `per_page` |
| BUG-BIT-01 | Baja | `/api/bitacora/` no valida `page` (0 o texto responden 500) |
| BUG-BIT-02 | Baja | `/api/bitacora/` no limita `limit` |
| BUG-BAK-01 | Baja | Un nombre de respaldo inválido en la descarga responde 500 |
| BUG-VAL-01 | Baja | `normalize_decimal("NaN")` lanza `InvalidOperation` |
| BUG-VAL-02 | Baja | Un abono de crédito `"NaN"` responde 500 |
| BUG-PRC-01 | Baja | `/api/pricing/calculate` con precio no numérico responde 500 |
