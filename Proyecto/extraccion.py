"""
extraccion.py
─────────────────────────────────────────────────────────────────────────────
Web Scraping de Éxito.com usando Selenium + BeautifulSoup.

CORRECCIONES v3:
  - Precios parseados y guardados como int limpios desde el scraper
  - precio_venta y precio_original separados desde el inicio
  - Filtro de nombres basura antes de guardar
  - Deduplicación robusta por (nombre_normalizado, enlace)
  - Scroll infinito con detección de fin de página
"""

import time
import csv
import json
import re

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from config import configurar_driver


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

LIMITE_CATEGORIA       = 150
MAX_SCROLLS_SIN_NUEVOS = 5
PAUSA_SCROLL           = 2.5

URL_OBJETIVO = [
    "https://www.exito.com/tecnologia",
    "https://www.exito.com/mercado",
    "https://www.exito.com/hogar",
    "https://www.exito.com/bebes",
    "https://www.exito.com/cuidado-personal",
    "https://www.exito.com/belleza",
    "https://www.exito.com/celulares",
]


# ─────────────────────────────────────────────────────────────────────────────
# PARSEO DE PRECIOS EN TIEMPO DE SCRAPING
# ─────────────────────────────────────────────────────────────────────────────

def _extraer_valores(texto: str) -> list[int]:
    """
    Extrae todos los valores numéricos > 500 del texto de precio.
    Convierte formato colombiano (puntos como miles) a enteros limpios.
    """
    if not texto:
        return []
    texto = re.sub(r'^-?\d+%', '', str(texto)).strip()
    candidatos = re.findall(r'\d[\d.]+', texto)
    valores = []
    for c in candidatos:
        try:
            v = int(float(c.replace('.', '')))
            if v > 500:
                valores.append(v)
        except ValueError:
            pass
    return valores


def _descuento_pct(texto: str):
    """Extrae porcentaje de descuento. Solo acepta 1-99."""
    m = re.match(r'-(\d+)%', str(texto).strip())
    if not m:
        return None
    d = int(m.group(1))
    return d if 1 <= d <= 99 else None


def _parsear_precios(texto: str) -> tuple:
    """
    Retorna (precio_venta: int|None, precio_original: int|None, descuento_pct: int|None)

    Formatos que maneja:
      '-56%$ 2.099.900price$ 923.906...' → original=2099900, venta=923906, desc=56
      'price$ 902.405$ 949.900'          → venta=902405,    original=949900, desc=None
      '$ 69.900'                         → venta=69900,     original=None,   desc=None
      '$ 800.000o 12 cuotas...'          → venta=800000,    original=None,   desc=None
    """
    desc    = _descuento_pct(texto)
    valores = _extraer_valores(texto)

    if not valores:
        return None, None, None

    if desc and len(valores) >= 2:
        # Con descuento explícito: primer valor=original, segundo=venta
        precio_original = valores[0]
        precio_venta    = valores[1]
    elif str(texto).strip().lower().startswith('price') and len(valores) >= 2:
        # Formato price$ X$ Y sin %: primer valor=venta, segundo=original
        precio_venta    = valores[0]
        precio_original = valores[1]
    else:
        precio_venta    = valores[0]
        precio_original = None

    # Corregir si quedaron invertidos
    if precio_original and precio_venta and precio_original < precio_venta:
        precio_original, precio_venta = precio_venta, precio_original

    return precio_venta, precio_original, desc


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────

_REGEX_BASURA = re.compile(
    r'^(agregar|ver\s+\d|o\s+\d+\s+cuotas|medios\s+de\s+pago|sin\s+interés)',
    re.I
)

def _es_nombre_valido(nombre: str) -> bool:
    nombre = str(nombre).strip()
    return len(nombre) >= 8 and not _REGEX_BASURA.match(nombre)


def _extraer_texto(elemento, selectores: list) -> str:
    for selector in selectores:
        try:
            nodo = elemento.select_one(selector)
            if nodo:
                texto = nodo.get_text(strip=True)
                if texto:
                    return texto
        except Exception:
            pass
    return ""


def esperar_carga(driver, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "article, div[class*='product']")
            )
        )
    except TimeoutException:
        print("  Timeout esperando productos")


def cerrar_popups(driver):
    selectores = [
        "button[class*='close']",
        "button[aria-label*='Cerrar']",
        "[class*='fsCookiesModal'] button",
        "[class*='modal'] button",
    ]
    for selector in selectores:
        try:
            botones = driver.find_elements(By.CSS_SELECTOR, selector)
            for boton in botones:
                if boton.is_displayed():
                    driver.execute_script("arguments[0].click();", boton)
                    time.sleep(0.5)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN DE TARJETAS
# ─────────────────────────────────────────────────────────────────────────────

def extraer_tarjetas(soup: BeautifulSoup, url: str) -> list[dict]:
    """
    Extrae productos del HTML actual.
    Precios se parsean aquí y se guardan como enteros limpios.
    """
    categoria = url.rstrip("/").split("/")[-1]
    tarjetas  = soup.select(
        "article, div[class*='product'], div[data-fs-product-card]"
    )
    productos = []

    for tarjeta in tarjetas:
        try:
            nombre = _extraer_texto(tarjeta, [
                "[class*='product-name']", "[class*='ProductName']",
                "h3", "h2", "a"
            ])

            if not _es_nombre_valido(nombre):
                continue

            precio_raw = _extraer_texto(tarjeta, [
                "[class*='price']", "[class*='Price']"
            ])

            marca = _extraer_texto(tarjeta, [
                "[class*='brand']", "[class*='Brand']"
            ])

            enlace_tag = tarjeta.select_one("a[href]")
            enlace = enlace_tag.get("href", "") if enlace_tag else ""
            if enlace.startswith("/"):
                enlace = "https://www.exito.com" + enlace

            imagen_tag = tarjeta.select_one("img")
            imagen = imagen_tag.get("src", "") if imagen_tag else ""

            # Parsear precios → int limpios desde el scraper
            precio_venta, precio_original, descuento = _parsear_precios(precio_raw)

            productos.append({
                "nombre":          nombre.strip(),
                "precio_venta":    precio_venta,
                "precio_original": precio_original,
                "descuento_pct":   descuento,
                "marca":           marca.strip(),
                "categoria":       categoria,
                "enlace":          enlace,
                "imagen":          imagen,
            })

        except Exception as e:
            print(f"  Error procesando tarjeta: {e}")

    return productos


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING CON SCROLL INFINITO
# ─────────────────────────────────────────────────────────────────────────────

def obtener_productos(driver, url: str) -> list[dict]:
    """Navega a una URL de Éxito.com y extrae productos por scroll infinito."""
    print(f"\n{'='*60}")
    print(f"CATEGORÍA: {url.split('/')[-1].upper()}")
    print(f"{'='*60}")

    try:
        driver.get(url)
        time.sleep(4)
        cerrar_popups(driver)
        esperar_carga(driver)
    except Exception as e:
        print(f"  Error al cargar {url}: {e}")
        return []

    todos  = []
    vistos = set()
    scrolls_sin_nuevos = 0
    scroll_num = 0

    while True:
        soup    = BeautifulSoup(driver.page_source, "lxml")
        parcial = extraer_tarjetas(soup, url)

        nuevos = []
        for p in parcial:
            clave = (p["nombre"].strip().lower(), p["enlace"])
            if clave not in vistos:
                vistos.add(clave)
                nuevos.append(p)

        if nuevos:
            todos.extend(nuevos)
            scrolls_sin_nuevos = 0
            print(f"  Scroll {scroll_num:>3} → {len(nuevos):>3} nuevos | total: {len(todos)}")
        else:
            scrolls_sin_nuevos += 1
            print(f"  Scroll {scroll_num:>3} → sin nuevos ({scrolls_sin_nuevos}/{MAX_SCROLLS_SIN_NUEVOS})")

        if len(todos) >= LIMITE_CATEGORIA:
            todos = todos[:LIMITE_CATEGORIA]
            print(f"  Límite de {LIMITE_CATEGORIA} alcanzado.")
            break

        if scrolls_sin_nuevos >= MAX_SCROLLS_SIN_NUEVOS:
            print(f"  Fin de página detectado.")
            break

        altura_antes = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(PAUSA_SCROLL)

        try:
            WebDriverWait(driver, 8).until(
                lambda d: d.execute_script(
                    "return document.body.scrollHeight"
                ) > altura_antes
            )
        except TimeoutException:
            scrolls_sin_nuevos += 1

        scroll_num += 1

    print(f"  Total extraídos: {len(todos)}")
    return todos


# ─────────────────────────────────────────────────────────────────────────────
# GUARDAR ARCHIVOS
# ─────────────────────────────────────────────────────────────────────────────

def guardar_csv(productos: list[dict], archivo: str = "productos_exito.csv"):
    if not productos:
        print("  No hay productos para guardar.")
        return
    try:
        campos = list(productos[0].keys())
        with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(productos)
        print(f"  CSV guardado: {archivo} ({len(productos)} productos)")
    except Exception as e:
        print(f"  Error guardando CSV: {e}")


def guardar_json(productos: list[dict], archivo: str = "productos_exito.json"):
    """Guarda JSON con precios como enteros — None se convierte a null."""
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
        print(f"  JSON guardado: {archivo} ({len(productos)} productos)")
    except Exception as e:
        print(f"  Error guardando JSON: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    driver = configurar_driver(headless=True)
    todos_los_productos = []

    try:
        for i, url in enumerate(URL_OBJETIVO, 1):
            print(f"\n{'#'*60}")
            print(f"CATEGORÍA {i}/{len(URL_OBJETIVO)}: {url}")
            print(f"{'#'*60}")
            try:
                productos = obtener_productos(driver, url)
                todos_los_productos.extend(productos)
                print(f"  Acumulado global: {len(todos_los_productos)}")
            except Exception as e:
                print(f"  Error en categoría: {e}")
            time.sleep(3)

        print(f"\n{'='*60}")
        print(f"SCRAPING FINALIZADO — {len(todos_los_productos)} productos")
        print(f"{'='*60}")

        guardar_csv(todos_los_productos)
        guardar_json(todos_los_productos)

    except Exception as e:
        print(f"\nERROR GENERAL: {e}")
    finally:
        driver.quit()
        print("Driver cerrado correctamente.")
