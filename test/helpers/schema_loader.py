import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILES = {
    "transalca": REPO_ROOT / "db" / "db_transalca.sql",
    "mantenimiento": REPO_ROOT / "db" / "db_mantenimiento.sql",
}
DEV_DATABASE_NAMES = {
    "transalca": "db_transalca",
    "mantenimiento": "db_mantenimiento",
}


def assert_test_database_name(name):
    if not name or not name.endswith("_test"):
        raise RuntimeError(
            f"Nombre de base de datos de prueba no permitido: {name!r}. "
            "Debe terminar en '_test' para evitar tocar la base de desarrollo."
        )


def rewrite_database_names(sql, mapping):
    for dev_name, test_name in mapping.items():
        sql = re.sub(rf"(?<![\w`]){re.escape(dev_name)}(?=\s*\.)", test_name, sql)
        sql = re.sub(rf"`{re.escape(dev_name)}`(?=\s*\.)", f"`{test_name}`", sql)
    return sql


def split_statements(sql):
    statements = []
    delimiter = ";"
    buffer = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1]
            continue
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            statement = "\n".join(buffer).rstrip()
            statement = statement[: len(statement) - len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer = []
    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def load_schema(connection, schema_key, mapping):
    sql = SCHEMA_FILES[schema_key].read_text(encoding="utf-8")
    sql = rewrite_database_names(sql, mapping)
    for name in DEV_DATABASE_NAMES.values():
        if re.search(rf"(?<![\w`]){name}\s*\.", sql):
            raise RuntimeError(f"El esquema aun referencia la base de desarrollo {name}.")
    with connection.cursor() as cursor:
        for statement in split_statements(sql):
            cursor.execute(statement)
    connection.commit()


def drop_all_tables(connection, database):
    assert_test_database_name(database)
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute(
            "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s",
            (database,),
        )
        for row in cursor.fetchall():
            kind = "VIEW" if row["TABLE_TYPE"] == "VIEW" else "TABLE"
            cursor.execute(f"DROP {kind} IF EXISTS `{database}`.`{row['TABLE_NAME']}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    connection.commit()
