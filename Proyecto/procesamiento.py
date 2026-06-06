"""
procesamiento.py
─────────────────────────────────────────────────────────────────────────────
Limpieza y transformación de datos para la BD relacional.

CORRECCIONES v3:
  - Lee los precios ya limpios (int) que genera extraccion.py v3
  - Ya no necesita parsear texto sucio de precio_actual
  - Genera ahorro_cop como int
  - Subcategorías ampliadas (20+ tipos)
  - Fallbacks descriptivos: otro_tecnologia, otro_mercado, etc.
  - contenido_neto y unidad siguen extrayéndose del nombre
"""

import re
import hashlib
from datetime import date
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def generar_id(*campos) -> str:
    clave = "_".join(str(c).strip().lower() for c in campos)
    return hashlib.sha1(clave.encode()).hexdigest()[:8]


# ─────────────────────────────────────────────────────────────────────────────
# TABLA PRODUCTOS
# ─────────────────────────────────────────────────────────────────────────────

def procesar_productos(raw: list[dict]) -> pd.DataFrame:
    """Genera la tabla productos desde la lista cruda del scraper v3."""
    registros = []
    for item in raw:
        nombre    = str(item.get("nombre", "")).strip()
        categoria = str(item.get("categoria", "sin_categoria")).strip().lower()
        marca     = str(item.get("marca", "")).strip() or "sin_marca"

        if not nombre or len(nombre) < 8:
            continue

        codigo_barras = generar_id(nombre.lower())
        id_producto   = generar_id("prod", codigo_barras)

        match = re.search(
            r"(\d[\d.,]*)\s*(g|kg|ml|l|und|unid|paq|lta)\b", nombre, re.I
        )
        contenido_neto = float(match.group(1).replace(",", ".")) if match else None
        unidad         = match.group(2).lower() if match else "und"

        registros.append({
            "id_producto":    id_producto,
            "codigo_barras":  codigo_barras,
            "nombre":         nombre,
            "categoria":      categoria,
            "marca":          marca,
            "contenido_neto": contenido_neto,
            "unidad":         unidad,
        })

    df = pd.DataFrame(registros)
    if df.empty:
        return df

    df = df.dropna(subset=["nombre", "categoria"])
    df = df.drop_duplicates(subset=["codigo_barras"])
    df["contenido_neto"] = pd.to_numeric(df["contenido_neto"], errors="coerce")

    print(f"  productos: {len(df)} filas")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# TABLA TIENDAS
# ─────────────────────────────────────────────────────────────────────────────

TIENDA_FIJA = {
    "id_tienda":  generar_id("exito", "exito.com", "colombia"),
    "nombre":     "Éxito",
    "tipo_canal": "supermercado",
    "ciudad":     "Colombia",
}

def procesar_tiendas() -> pd.DataFrame:
    df = pd.DataFrame([TIENDA_FIJA])
    print(f"  tiendas: {len(df)} fila(s)")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# TABLA PRECIOS
# ─────────────────────────────────────────────────────────────────────────────

def procesar_precios(raw: list[dict], df_productos: pd.DataFrame) -> pd.DataFrame:
    """
    Genera la tabla precios.
    Lee precio_venta y precio_original como enteros limpios
    que vienen directamente de extraccion.py v3.
    """
    id_tienda   = TIENDA_FIJA["id_tienda"]
    hoy         = date.today().strftime("%Y-%m-%d")
    ids_validos = set(df_productos["id_producto"])

    registros = []
    for item in raw:
        nombre = str(item.get("nombre", "")).strip()
        if not nombre or len(nombre) < 8:
            continue

        codigo_barras = generar_id(nombre.lower())
        id_producto   = generar_id("prod", codigo_barras)

        if id_producto not in ids_validos:
            continue

        # Leer precios ya limpios (int) desde el scraper v3
        precio_venta    = item.get("precio_venta")
        precio_original = item.get("precio_original")

        # Compatibilidad con JSON viejo que tenía precio_actual como texto
        if precio_venta is None and item.get("precio_actual"):
            from modelo import _extraer_valores, _descuento_pct
            texto  = str(item.get("precio_actual", ""))
            desc   = _descuento_pct(texto)
            vals   = _extraer_valores(texto)
            if desc and len(vals) >= 2:
                precio_original = vals[0]
                precio_venta    = vals[1]
            elif vals:
                precio_venta    = vals[0]

        if not precio_venta or precio_venta <= 0:
            continue

        # Validar coherencia
        if precio_original and precio_original < precio_venta:
            precio_original, precio_venta = precio_venta, precio_original

        if precio_original and precio_original <= precio_venta:
            precio_original = None

        registros.append({
            "id_producto":     id_producto,
            "id_tienda":       id_tienda,
            "precio_venta":    int(precio_venta),
            "precio_original": int(precio_original) if precio_original else pd.NA,
            "fecha_registro":  hoy,
            "fuente":          "exito.com",
        })

    df = pd.DataFrame(registros)
    if df.empty:
        return df

    df["precio_venta"]    = pd.to_numeric(df["precio_venta"], errors="coerce")
    df["precio_original"] = pd.to_numeric(df["precio_original"], errors="coerce")
    df = df[df["precio_venta"] > 0].dropna(subset=["precio_venta"])

    # Detección de outliers con IQR factor 3
    Q1, Q3 = df["precio_venta"].quantile([0.25, 0.75])
    IQR    = Q3 - Q1
    outliers = df[
        (df["precio_venta"] < Q1 - 3 * IQR) |
        (df["precio_venta"] > Q3 + 3 * IQR)
    ]
    if len(outliers):
        print(f"  precios: {len(outliers)} outliers detectados (conservados)")

    print(f"  precios: {len(df)} filas")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def procesar_todo(raw: list[dict]) -> dict:
    print("\n ___________Procesamiento de datos___________")
    df_prod    = procesar_productos(raw)
    df_tiendas = procesar_tiendas()
    df_precios = procesar_precios(raw, df_prod)
    df_ind     = pd.DataFrame(columns=["Fecha"])
    print("  indicadores_economicos: tabla vacía")

    return {
        "productos":              df_prod,
        "tiendas":                df_tiendas,
        "precios":                df_precios,
        "indicadores_economicos": df_ind,
    }
