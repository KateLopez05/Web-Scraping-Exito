"""
Ingesta en la Base de Datos
SQLAlchemy + insercion masiva evitando duplicados
Modelo: productos, tiendas, precios, indicadores_economicos

CORRECCIONES v3:
  1. DDL de precios incluye precio_original (antes era precio_promocion)
  2. columnas_viejas ampliada para detectar esquemas de EA1 y EA2
  3. PK compuesta (id_producto, id_tienda, fecha_registro) en precios
  4. itertuples() en lugar de values.tolist()
"""

import pandas as pd
from sqlalchemy import create_engine, text
from procesamiento import procesar_todo

DB_PATH = "consumo_masivo.db"

ESQUEMAS = {
    "productos": """
        CREATE TABLE IF NOT EXISTS productos (
            id_producto    TEXT PRIMARY KEY,
            codigo_barras  TEXT NOT NULL,
            nombre         TEXT NOT NULL,
            categoria      TEXT NOT NULL,
            marca          TEXT,
            contenido_neto REAL,
            unidad         TEXT
        )
    """,
    "tiendas": """
        CREATE TABLE IF NOT EXISTS tiendas (
            id_tienda  TEXT PRIMARY KEY,
            nombre     TEXT NOT NULL,
            tipo_canal TEXT,
            ciudad     TEXT
        )
    """,
    "precios": """
        CREATE TABLE IF NOT EXISTS precios (
            id_producto      TEXT NOT NULL,
            id_tienda        TEXT NOT NULL,
            precio_venta     INTEGER NOT NULL,
            precio_original  INTEGER,
            fecha_registro   TEXT NOT NULL,
            fuente           TEXT,
            PRIMARY KEY (id_producto, id_tienda, fecha_registro),
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
            FOREIGN KEY (id_tienda)   REFERENCES tiendas(id_tienda)
        )
    """,
    "indicadores_economicos": """
        CREATE TABLE IF NOT EXISTS indicadores_economicos (
            fecha TEXT PRIMARY KEY
        )
    """,
}

INDICES = {
    "precios": [
        "CREATE INDEX IF NOT EXISTS idx_precio_producto ON precios(id_producto);",
        "CREATE INDEX IF NOT EXISTS idx_precio_tienda   ON precios(id_tienda);",
        "CREATE INDEX IF NOT EXISTS idx_precio_fecha    ON precios(fecha_registro);",
    ],
    "productos": [
        "CREATE INDEX IF NOT EXISTS idx_prod_categoria ON productos(categoria);",
    ],
}


def conectar():
    try:
        engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        print("  Conexion establecida:", DB_PATH)
        return engine
    except Exception as e:
        print(f"  Error al conectar a la BD: {e}")
        raise


def crear_tablas(engine) -> None:
    """
    Crea las tablas con el esquema correcto.
    Si detecta columnas incompatibles (de EA1 o EA2 anterior), recrea la tabla.
    """
    # Columnas que indican esquemas viejos incompatibles
    columnas_viejas = {
        # EA1 dataset de prueba
        "date", "prod_name_long", "prod_id", "prod_name", "prod_brand",
        "category", "subcategory", "tags", "prod_unit_price", "prod_units",
        "prod_icon", "prod_source", "source_type",
        # EA2 version anterior (precio_promocion reemplazado por precio_original)
        "precio_promocion",
    }

    with engine.begin() as conn:
        for nombre, ddl in ESQUEMAS.items():
            info = conn.execute(
                text(f"PRAGMA table_info({nombre})")
            ).fetchall()

            if info:
                columnas_actuales = {col[1] for col in info}
                if columnas_actuales & columnas_viejas:
                    print(f"  [{nombre}] Esquema incompatible -> se recrea la tabla")
                    conn.execute(text(f"DROP TABLE IF EXISTS {nombre}"))

            conn.execute(text(ddl))

    print("  Tablas verificadas/creadas correctamente.")


def cargar_tabla(df: pd.DataFrame, nombre_tabla: str, engine) -> None:
    """Inserta filas nuevas ignorando duplicados por PK."""
    if df.empty:
        print(f"  {nombre_tabla}: vacia, se omite.")
        return

    try:
        filas   = [tuple(r) for r in df.itertuples(index=False, name=None)]
        cols    = ", ".join(df.columns)
        holders = ", ".join(["?"] * len(df.columns))
        sql     = f"INSERT OR IGNORE INTO {nombre_tabla} ({cols}) VALUES ({holders})"

        with engine.begin() as conn:
            conn.exec_driver_sql(sql, filas)

    except Exception as e:
        print(f"  Error insertando en {nombre_tabla}: {e}")
        raise

    if nombre_tabla in INDICES:
        with engine.begin() as conn:
            for idx_sql in INDICES[nombre_tabla]:
                conn.execute(text(idx_sql))

    with engine.connect() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM {nombre_tabla}")).scalar()
    print(f"  {nombre_tabla:<30} {n:>6,} registros totales en BD")


def ingestar(tablas: dict) -> None:
    """
    Carga las 4 tablas en SQLite respetando el orden de FK:
    tiendas -> productos -> precios -> indicadores_economicos
    """
    print("\n___________Ingesta a la base de datos___________")
    engine = conectar()

    crear_tablas(engine)

    cargar_tabla(tablas["tiendas"],                "tiendas",                engine)
    cargar_tabla(tablas["productos"],              "productos",              engine)
    cargar_tabla(tablas["precios"],                "precios",                engine)
    cargar_tabla(tablas["indicadores_economicos"], "indicadores_economicos", engine)

    print("\n  Pipeline de ingesta completado.")


if __name__ == "__main__":
    import json

    print("Cargando datos del scraper...")
    with open("productos_exito.json", encoding="utf-8") as f:
        raw = json.load(f)

    tablas = procesar_todo(raw)
    ingestar(tablas)

    print("\n___________Verificacion post-ingesta___________")
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    with engine.connect() as conn:
        for tabla in ["productos", "tiendas", "precios"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
            print(f"  {tabla:<30} {n:>6,} registros")

        stats = conn.execute(text(
            "SELECT MIN(precio_venta), MAX(precio_venta), ROUND(AVG(precio_venta),0) FROM precios"
        )).fetchone()
        print(f"\n  Precio minimo:   ${stats[0]:>12,}")
        print(f"  Precio maximo:   ${stats[1]:>12,}")
        print(f"  Precio promedio: ${int(stats[2]):>12,}")

        # Idempotencia
        print("\n  Prueba idempotencia (segunda insercion)...")
        ingestar(tablas)
        n2 = conn.execute(text("SELECT COUNT(*) FROM productos")).scalar()
        print(f"  productos tras 2da insercion: {n2} (debe ser igual)")
