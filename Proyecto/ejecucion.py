"""
ejecucion.py
─────────────────────────────────────────────────────────────────────────────
Ejecuta el pipeline completo y genera auditoria.txt.
Uso: python ejecucion.py
"""

import json
import sys
import traceback
from datetime import datetime
from io import StringIO

import pandas as pd
from sqlalchemy import create_engine, text

from modelo import enriquecer
from scrapper import (
    cargar_json, aplicar_enriquecimiento,
    guardar_archivos, cargar_a_sqlite,
    ARCHIVO_JSON_CRUDO, DB_PATH, TABLA_BD,
)

ARCHIVO_AUDITORIA = 'auditoria.txt'


class _Tee:
    def __init__(self, stream):
        self._stream = stream
        self._buf    = StringIO()
    def write(self, data):
        self._stream.write(data)
        self._buf.write(data)
    def flush(self):
        self._stream.flush()
    def getvalue(self):
        return self._buf.getvalue()


def validar(df: pd.DataFrame) -> int:
    print('\n' + '─' * 55)
    print('  VALIDACIONES DE CALIDAD')
    print('─' * 55)
    errores = 0

    # V1: nombre_limpio sin nulos
    n = df['nombre_limpio'].isna().sum()
    print(f'  V1 nombre_limpio sin nulos       {"✓ PASS" if n==0 else f"✗ FAIL ({n})"}')
    errores += n > 0

    # V2: precio_venta > 0
    n = (df['precio_venta'].notna() & (df['precio_venta'] <= 0)).sum()
    print(f'  V2 precio_venta > 0              {"✓ PASS" if n==0 else f"✗ FAIL ({n})"}')
    errores += n > 0

    # V3: precio_original >= precio_venta
    mask = df['precio_venta'].notna() & df['precio_original'].notna()
    n = (df[mask]['precio_original'] < df[mask]['precio_venta']).sum()
    print(f'  V3 precio_original >= precio_venta {"✓ PASS" if n==0 else f"✗ FAIL ({n})"}')
    errores += n > 0

    # V4: sin duplicados
    n = df.duplicated(subset=['nombre_limpio', 'categoria']).sum()
    print(f'  V4 sin duplicados (nombre+cat)   {"✓ PASS" if n==0 else f"✗ FAIL ({n})"}')
    errores += n > 0

    # V5: rango_precio completo
    n = (df['rango_precio'] == 'sin_precio').sum()
    print(f'  V5 rango_precio completo         INFO ({n} sin precio)')

    # V6: descuento_pct en [1-99]
    mask2 = df['descuento_pct'].notna()
    n = ((df[mask2]['descuento_pct'] < 1) | (df[mask2]['descuento_pct'] > 99)).sum()
    print(f'  V6 descuento_pct en [1-99]       {"✓ PASS" if n==0 else f"✗ FAIL ({n})"}')
    errores += n > 0

    # V7: precios como enteros (sin decimales)
    tiene_decimales = (
        df['precio_venta'].dropna().astype(str).str.contains(r'\.')
    ).sum()
    print(f'  V7 precios sin decimales (.0)    {"✓ PASS" if tiene_decimales==0 else f"✗ FAIL ({tiene_decimales})"}')
    errores += tiene_decimales > 0

    print(f'\n  Resultado: {7 - errores}/7 validaciones pasadas.')
    return errores


def analisis_bd(engine):
    print('\n' + '─' * 55)
    print('  ANÁLISIS DE LA BASE DE DATOS')
    print('─' * 55)
    with engine.connect() as conn:
        consultas = {
            'Total productos enriquecidos':
                f'SELECT COUNT(*) FROM {TABLA_BD}',
            'Con descuento':
                f'SELECT COUNT(*) FROM {TABLA_BD} WHERE tiene_descuento=1',
            'Descuento promedio (%)':
                f'SELECT ROUND(AVG(descuento_pct),1) FROM {TABLA_BD} WHERE descuento_pct IS NOT NULL',
            'Ahorro promedio (COP)':
                f'SELECT ROUND(AVG(ahorro_cop),0) FROM {TABLA_BD} WHERE ahorro_cop IS NOT NULL',
            'Precio mínimo':
                f'SELECT MIN(precio_venta) FROM {TABLA_BD}',
            'Precio máximo':
                f'SELECT MAX(precio_venta) FROM {TABLA_BD}',
            'Precio promedio':
                f'SELECT ROUND(AVG(precio_venta),0) FROM {TABLA_BD}',
            'Productos con 5G':
                f'SELECT COUNT(*) FROM {TABLA_BD} WHERE conectividad_5g=1',
        }
        for desc, sql in consultas.items():
            r = conn.execute(text(sql)).scalar()
            if isinstance(r, (int, float)) and r > 999:
                print(f'  {desc:<35} {r:>15,.0f}')
            else:
                print(f'  {desc:<35} {r}')

        print('\n  Por categoría:')
        rows = conn.execute(text(
            f'SELECT categoria, COUNT(*), ROUND(AVG(precio_venta),0) '
            f'FROM {TABLA_BD} GROUP BY categoria ORDER BY COUNT(*) DESC'
        )).fetchall()
        for cat, n, avg in rows:
            avg_str = f'${avg:,.0f}' if avg else 'sin precio'
            print(f'    {cat:<22} {n:>4} productos   prom: {avg_str}')


def main():
    inicio = datetime.now()
    tee    = _Tee(sys.stdout)
    sys.stdout = tee

    try:
        print('=' * 55)
        print('  PIPELINE ETL — ÉXITO.COM')
        print(f'  Fecha: {inicio.strftime("%Y-%m-%d %H:%M:%S")}')
        print('=' * 55)

        raw     = cargar_json(ARCHIVO_JSON_CRUDO)
        df      = aplicar_enriquecimiento(raw)
        errores = validar(df)
        guardar_archivos(df)
        cargar_a_sqlite(df)

        engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
        analisis_bd(engine)

        fin      = datetime.now()
        duracion = (fin - inicio).total_seconds()

        print('\n' + '=' * 55)
        print(f'  COMPLETADO EN {duracion:.1f} segundos')
        print(f'  Validaciones fallidas: {errores}')
        print('  Archivos generados:')
        print('    productos_enriquecidos.csv  ← Power BI')
        print('    productos_enriquecidos.json')
        print(f'    consumo_masivo.db  (tabla: {TABLA_BD})')
        print('    auditoria.txt')
        print('=' * 55)

    except Exception:
        print('\n[ERROR CRÍTICO]')
        traceback.print_exc()
    finally:
        sys.stdout = tee._stream
        with open(ARCHIVO_AUDITORIA, 'w', encoding='utf-8') as f:
            f.write(tee.getvalue())
        print(f'\nAuditoría guardada en: {ARCHIVO_AUDITORIA}')


if __name__ == '__main__':
    main()
