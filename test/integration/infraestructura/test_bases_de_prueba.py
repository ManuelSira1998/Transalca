from config import config as app_config


def test_las_bases_de_prueba_existen_y_tienen_esquema(db, test_databases):
    with db["transalca"].cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_SCHEMA, COUNT(*) AS n FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA IN (%s, %s) GROUP BY TABLE_SCHEMA",
            (test_databases["transalca"], test_databases["mantenimiento"]),
        )
        tablas = {row["TABLE_SCHEMA"]: row["n"] for row in cursor.fetchall()}
    assert tablas[test_databases["transalca"]] >= 30
    assert tablas[test_databases["mantenimiento"]] >= 5


def test_la_app_apunta_a_las_bases_de_prueba(test_databases):
    assert app_config.DB_CONFIG_TRANSALCA["database"] == test_databases["transalca"]
    assert app_config.DB_CONFIG_MANTENIMIENTO["database"] == test_databases["mantenimiento"]
    assert app_config.DB_CONFIG_TRANSALCA["database"].endswith("_test")
    assert app_config.DB_CONFIG_MANTENIMIENTO["database"].endswith("_test")


def test_ningun_trigger_escribe_en_la_base_de_desarrollo(db, test_databases):
    with db["transalca"].cursor() as cursor:
        cursor.execute(
            "SELECT TRIGGER_NAME, ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = %s",
            (test_databases["transalca"],),
        )
        triggers = cursor.fetchall()
    assert triggers, "El esquema de prueba deberia incluir los triggers de bitacora"
    for trigger in triggers:
        assert "db_mantenimiento." not in trigger["ACTION_STATEMENT"], trigger["TRIGGER_NAME"]
    hacia_bitacora_de_prueba = [
        t for t in triggers if f"{test_databases['mantenimiento']}.bitacora" in t["ACTION_STATEMENT"]
    ]
    assert len(hacia_bitacora_de_prueba) >= 20


def test_un_trigger_registra_en_la_bitacora_de_prueba(db, test_databases):
    with db["mantenimiento"].cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM bitacora WHERE modulo = 'CATEGORIAS'")
        antes = cursor.fetchone()["n"]
    with db["transalca"].cursor() as cursor:
        cursor.execute(
            "INSERT INTO categorias (nombre_categoria, descripcion_categoria, estado) VALUES (%s, %s, 1)",
            ("Infra Trigger", "categoria creada por la prueba de triggers"),
        )
    with db["mantenimiento"].cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM bitacora WHERE modulo = 'CATEGORIAS'")
        assert cursor.fetchone()["n"] == antes + 1
