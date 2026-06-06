"""
scrapper.py
─────────────────────────────────────────────────────────────────────────────
Orquesta el enriquecimiento:
  1. Carga productos_exito.json
  2. Aplica modelo.py
  3. Guarda productos_enriquecidos.csv (para Power BI) y .json
  4. Carga tabla productos_enriquecidos en SQLite

CORRECCIONES:
  - Columnas numéricas guardadas como Int64 (entero que acepta NaN)
  - Sin decimales .0 en precios ni ahorro
  - utf-8-sig para compatibilidad directa con Power BI
"""

import json
import pandas as pd
from sqlalchemy import create_engine, text
from modelo import enriquecer

ARCHIVO_JSON_CRUDO = "productos_exito.json"
ARCHIVO_CSV_SALIDA = "productos_enriquecidos.csv"
ARCHIVO_JSON_SALIDA = "productos_enriquecidos.json"
DB_PATH = "consumo_masivo.db"
TABLA_BD = "productos_enriquecidos"

DDL_TABLA = f"""
CREATE TABLE IF NOT EXISTS {TABLA_BD} (
    nombre_limpio       TEXT NOT NULL,
    marca_normalizada   TEXT,
    categoria           TEXT,
    subcategoria        TEXT,
    precio_venta        INTEGER,
    precio_original     INTEGER,
    descuento_pct       INTEGER,
    ahorro_cop          INTEGER,
    tiene_descuento     INTEGER,
    rango_precio        TEXT,
    almacenamiento_gb   INTEGER,
    ram_gb              INTEGER,
    conectividad_5g     INTEGER,
    fecha_extraccion    TEXT,
    fuente              TEXT,
    enlace              TEXT,
    nombre              TEXT,
    PRIMARY KEY (nombre_limpio, categoria)
)
"""

COLUMNAS_CSV = [
    "nombre_limpio",
    "marca_normalizada",
    "categoria",
    "subcategoria",
    "precio_venta",
    "precio_original",
    "descuento_pct",
    "ahorro_cop",
    "tiene_descuento",
    "rango_precio",
    "almacenamiento_gb",
    "ram_gb",
    "conectividad_5g",
    "fecha_extraccion",
    "fuente",
    "enlace",
]

COLUMNAS_BD = COLUMNAS_CSV + ["nombre"]

COLS_INT = [
    "precio_venta",
    "precio_original",
    "ahorro_cop",
    "descuento_pct",
    "almacenamiento_gb",
    "ram_gb",
]


def cargar_json(ruta: str) -> list[dict]:
    print(f"\n[1/4] Cargando {ruta}...")
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)
    print(f"      {len(data)} registros crudos.")
    return data


def aplicar_enriquecimiento(raw: list[dict]) -> pd.DataFrame:
    print("\n[2/4] Enriqueciendo datos...")
    datos = enriquecer(raw)
    df = pd.DataFrame(datos)

    df = df.drop_duplicates(subset=["nombre_limpio", "categoria"])

    # Convertir columnas numéricas a Int64 (soporta NaN, sin decimales)
    for col in COLS_INT:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(0).astype("Int64")

    df["tiene_descuento"] = df["tiene_descuento"].astype(int)
    df["conectividad_5g"] = df["conectividad_5g"].astype(int)

    print(f"      {len(df)} productos enriquecidos.")
    print(f'      precio_venta promedio:  ${df["precio_venta"].mean():,.0f}')
    print(f'      descuento_pct promedio: {df["descuento_pct"].mean():.1f}%')
    print(f'      ahorro_cop promedio:    ${df["ahorro_cop"].mean():,.0f}')
    print(f'      con descuento:          {df["tiene_descuento"].sum()}')
    print(f'      con 5G:                 {df["conectividad_5g"].sum()}')
    return df


def guardar_archivos(df: pd.DataFrame):
    print("\n[3/4] Guardando archivos...")

    # Crear copia para exportación
    df_export = df.copy()

    # Forzar columnas numéricas a texto sin decimales
    columnas_enteras = [
        "precio_venta",
        "precio_original",
        "ahorro_cop",
        "descuento_pct",
        "almacenamiento_gb",
        "ram_gb",
    ]

    for col in columnas_enteras:
        if col in df_export.columns:
            df_export[col] = df_export[col].apply(
                lambda x: "" if pd.isna(x) else str(int(x))
            )

    # Guardar CSV
    df_export[COLUMNAS_CSV].to_csv(
        ARCHIVO_CSV_SALIDA, index=False, encoding="utf-8-sig"
    )

    print(f"      CSV: {ARCHIVO_CSV_SALIDA}")

    # Guardar JSON original
    df.to_json(ARCHIVO_JSON_SALIDA, orient="records", force_ascii=False, indent=2)

    print(f"      JSON: {ARCHIVO_JSON_SALIDA}")

    # Guardar JSON original
    df.to_json(ARCHIVO_JSON_SALIDA, orient="records", force_ascii=False, indent=2)

    print(f"      JSON: {ARCHIVO_JSON_SALIDA}")


def cargar_a_sqlite(df: pd.DataFrame):
    print(f"\n[4/4] Cargando a SQLite...")
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLA_BD}"))
        conn.execute(text(DDL_TABLA))

    filas = [tuple(r) for r in df[COLUMNAS_BD].itertuples(index=False, name=None)]
    cols = ", ".join(COLUMNAS_BD)
    holders = ", ".join(["?"] * len(COLUMNAS_BD))
    sql = f"INSERT OR IGNORE INTO {TABLA_BD} ({cols}) VALUES ({holders})"

    with engine.begin() as conn:
        conn.exec_driver_sql(sql, filas)

    indices = [
        f"CREATE INDEX IF NOT EXISTS idx_enr_categoria ON {TABLA_BD}(categoria);",
        f"CREATE INDEX IF NOT EXISTS idx_enr_subcat    ON {TABLA_BD}(subcategoria);",
        f"CREATE INDEX IF NOT EXISTS idx_enr_rango     ON {TABLA_BD}(rango_precio);",
        f"CREATE INDEX IF NOT EXISTS idx_enr_marca     ON {TABLA_BD}(marca_normalizada);",
    ]
    with engine.begin() as conn:
        for idx in indices:
            conn.execute(text(idx))

    with engine.connect() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM {TABLA_BD}")).scalar()
    print(f'      {n} registros en tabla "{TABLA_BD}".')


if __name__ == "__main__":
    print("=" * 55)
    print("  ENRIQUECIMIENTO — ÉXITO.COM")
    print("=" * 55)

    raw = cargar_json(ARCHIVO_JSON_CRUDO)
    df = aplicar_enriquecimiento(raw)
    guardar_archivos(df)
    cargar_a_sqlite(df)

    print("\n" + "=" * 55)
    print(f"  Archivo para Power BI: {ARCHIVO_CSV_SALIDA}")
    print("=" * 55)
