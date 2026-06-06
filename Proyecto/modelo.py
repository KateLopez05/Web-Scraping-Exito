"""
modelo.py
─────────────────────────────────────────────────────────────────────────────
Enriquecimiento de datos del scraper de Éxito.com.
Compatible con extraccion.py v3 (precios ya limpios como int).

14 campos nuevos:
  precio_venta, precio_original, descuento_pct, ahorro_cop,
  tiene_descuento, rango_precio, subcategoria,
  almacenamiento_gb, ram_gb, conectividad_5g,
  marca_normalizada, nombre_limpio, fecha_extraccion, fuente

CORRECCIONES v3:
  - Lee precio_venta y precio_original directamente como int (no parsea texto)
  - Compatibilidad con JSON viejo (precio_actual como texto) como fallback
  - Todos los precios y ahorro guardados como int (sin .0)
  - 20+ subcategorías con fallbacks descriptivos (otro_tecnologia, etc.)
  - Umbral mínimo de precio = 500 COP (válido para frutas/verduras)
"""

import re
from datetime import date


# ─────────────────────────────────────────────────────────────────────────────
# PARSEO DE PRECIOS (fallback para JSON viejo)
# ─────────────────────────────────────────────────────────────────────────────

def _extraer_valores(texto: str) -> list[int]:
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
    m = re.match(r'-(\d+)%', str(texto).strip())
    if not m:
        return None
    d = int(m.group(1))
    return d if 1 <= d <= 99 else None


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTACIÓN DE PRECIO
# ─────────────────────────────────────────────────────────────────────────────

def _rango_precio(precio, categoria: str) -> str:
    if precio is None:
        return 'sin_precio'
    umbrales = {
        'celulares':        (400_000,  1_200_000, 2_500_000),
        'tecnologia':       (200_000,    800_000, 2_000_000),
        'hogar':            (50_000,     300_000, 1_000_000),
        'mercado':          (500,         15_000,    50_000),
        'bebes':            (30_000,     150_000,   500_000),
        'belleza':          (15_000,      60_000,   150_000),
        'cuidado-personal': (10_000,      40_000,   120_000),
    }
    bajo, medio, alto = umbrales.get(categoria, (50_000, 200_000, 800_000))
    if precio < bajo:    return 'bajo'
    elif precio < medio: return 'medio'
    elif precio < alto:  return 'alto'
    else:                return 'premium'


# ─────────────────────────────────────────────────────────────────────────────
# SUBCATEGORÍAS
# ─────────────────────────────────────────────────────────────────────────────

_SUBCAT_REGLAS = [
    # Tecnología / Celulares
    (r'\bcelular\b|\bsmartphone\b|\biphone\b|\bgalaxy\b|\bredmi\b|\bxiaomi\b|\bmotorola\b|\binfinix\b', 'celular'),
    (r'\bportátil\b|\bportatil\b|\blaptop\b|\bnotebook\b',  'portátil'),
    (r'\bmonitor\b',                                         'monitor'),
    (r'\bimpresora\b',                                       'impresora'),
    (r'\bmouse\b|\bteclado\b|\bwebcam\b|\baudífono\b|\baudfono\b|\bearbuds\b|\bheadphone\b|\bheadset\b|\bauricular\b', 'accesorio_pc'),
    (r'\btelevisor\b|\bsmart tv\b|\bqled\b|\boled\b|\buhd\b', 'televisor'),
    (r'\bparlante\b|\bbarra de sonido\b|\btorre de sonido\b', 'audio'),
    (r'\btablet\b|\bipad\b',                                  'tablet'),
    (r'\bcámara\b|\bcamara\b',                                'cámara'),
    (r'\bconsola\b|\bplaystation\b|\bxbox\b|\bnintendo\b',    'consola'),
    (r'\brouter\b|\bmodem\b|\binternet satelital\b',          'conectividad'),
    # Hogar
    (r'\bcolchón\b|\bcolchon\b',                              'colchón'),
    (r'\bsofá\b|\bsofa\b|\bsilla\b|\bcloset\b|\bcama\b|\bescritorio\b|\bmesa\b', 'mueble'),
    (r'\blavadora\b|\bnevera\b|\brefrigerador\b|\bsecadora\b', 'electrodoméstico'),
    (r'\baspiradora\b|\bplancha\b|\bcafetera\b|\baire acondicionado\b', 'electrodoméstico_peq'),
    (r'\bolla\b|\bsartén\b|\bsarten\b|\bcubiertos\b|\bvajilla\b|\bbatería de ollas\b', 'cocina'),
    (r'\btermo\b|\bvaso térmico\b|\bstanley\b',               'termo'),
    (r'\bespejo\b|\bluz led\b|\borganizador\b|\blampara\b',   'decoración'),
    # Mercado
    (r'\bjamón\b|\bjamon\b|\bsalchicha\b|\bpollo\b|\bcarne\b|\bpechuga\b|\bchorizo\b|\btilapia\b', 'carnes_y_embutidos'),
    (r'\bleche\b|\byogur\b|\bqueso\b|\bhuevo\b|\bkikes\b',    'lácteos_y_huevos'),
    (r'\barroz\b|\baceite\b|\bsalsa\b|\bsopa\b|\bpasta\b|\blentejas\b|\bfrijol\b', 'despensa'),
    (r'\blechuga\b|\bpera\b|\bpepino\b|\bmango\b|\btomate\b|\bpapa\b|\bajo\b|\blimón\b|\bfresa\b|\bbanano\b', 'frutas_y_verduras'),
    (r'\bdetergente\b|\bsuavizante\b|\blavaplatos\b|\bdesinfectante\b|\bescoba\b', 'limpieza_hogar'),
    (r'\bpañal\b|\btoalla húmeda\b|\bwinny\b',                'higiene_bebé'),
    # Bebés
    (r'\bbañera\b|\bbiberon\b|\bextractor de leche\b',        'cuidado_bebé'),
    (r'\bcoche\b|\bcarrito\b|\bsilla.*carro\b|\bsilla.*coche\b', 'movilidad_bebé'),
    (r'\bjuguete\b|\bjuego\b|\brompecabezas\b',               'juguetes'),
    (r'\bkit.*bebé\b|\bkit.*recién nacido\b',                 'kit_bebé'),
    # Belleza / Cuidado personal
    (r'\bperfume\b|\bcolonia\b|\bedt\b|\bedp\b',              'fragancias'),
    (r'\bcrema\b|\bsérum\b|\bsuero\b|\bácido\b|\btónico\b|\bniacinamida\b|\bretinol\b|\bcerave\b', 'cuidado_piel'),
    (r'\bchampú\b|\bshampoo\b|\bacondicionador\b|\bsecador\b|\bsavital\b', 'cuidado_capilar'),
    (r'\bmaquillaje\b|\bbase\b|\brimel\b|\blabial\b|\bsombra\b', 'maquillaje'),
    (r'\bminoxidil\b|\bmedicamento\b|\bvitamina\b|\bsuplemento\b|\btensiometro\b', 'salud'),
    (r'\bjabón\b|\bjabon\b|\bdesodorante\b|\bprotector solar\b|\bprotex\b', 'higiene_personal'),
]

_FALLBACKS = {
    'tecnologia':       'otro_tecnologia',
    'celulares':        'otro_celular',
    'hogar':            'otro_hogar',
    'mercado':          'otro_mercado',
    'bebes':            'otro_bebes',
    'belleza':          'otro_belleza',
    'cuidado-personal': 'otro_cuidado',
}

def _subcategoria(nombre: str, categoria: str) -> str:
    nombre_l = nombre.lower()
    for patron, subcat in _SUBCAT_REGLAS:
        if re.search(patron, nombre_l):
            return subcat
    return _FALLBACKS.get(categoria, 'otro')


# ─────────────────────────────────────────────────────────────────────────────
# ESPECIFICACIONES TÉCNICAS
# ─────────────────────────────────────────────────────────────────────────────

def _almacenamiento_gb(nombre: str):
    m = re.search(r'(\d+)\s*[Gg][Bb](?!\s*[Rr][Aa][Mm])', nombre)
    return int(m.group(1)) if m else None

def _ram_gb(nombre: str):
    m = re.search(r'(\d+)\s*[Gg][Bb]\s*[Rr][Aa][Mm]', nombre)
    return int(m.group(1)) if m else None

def _tiene_5g(nombre: str) -> bool:
    return bool(re.search(r'\b5[Gg]\b', nombre))


# ─────────────────────────────────────────────────────────────────────────────
# LIMPIEZA GENERAL
# ─────────────────────────────────────────────────────────────────────────────

_BASURA = re.compile(
    r'^(agregar|ver\s+\d|o\s+\d+\s+cuotas|medios\s+de\s+pago)', re.I
)

def _es_valido(nombre: str) -> bool:
    nombre = str(nombre).strip()
    return len(nombre) >= 8 and not _BASURA.match(nombre)

def _nombre_limpio(nombre: str) -> str:
    return re.sub(r'\s{2,}', ' ', str(nombre).strip())

def _marca_normalizada(marca: str) -> str:
    marca = str(marca).strip()
    return marca.title() if marca else 'Sin marca'


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def enriquecer(raw: list[dict]) -> list[dict]:
    """
    Recibe la lista cruda del scraper v3 y retorna lista enriquecida.
    Compatible con JSON viejo (precio_actual texto) como fallback.
    Todos los precios se guardan como int para Power BI.
    """
    hoy = date.today().isoformat()
    resultado = []

    for item in raw:
        nombre    = str(item.get('nombre', '')).strip()
        categoria = str(item.get('categoria', '')).strip().lower()

        if not _es_valido(nombre):
            continue

        # Leer precios limpios del scraper v3
        precio_venta    = item.get('precio_venta')
        precio_original = item.get('precio_original')
        desc            = item.get('descuento_pct')

        # Fallback para JSON viejo con precio_actual como texto
        if precio_venta is None and item.get('precio_actual'):
            texto  = str(item.get('precio_actual', ''))
            desc   = _descuento_pct(texto)
            vals   = _extraer_valores(texto)
            if desc and len(vals) >= 2:
                precio_original = vals[0]
                precio_venta    = vals[1]
            elif str(texto).strip().lower().startswith('price') and len(vals) >= 2:
                precio_venta    = vals[0]
                precio_original = vals[1]
            elif vals:
                precio_venta    = vals[0]

        # Convertir a int
        precio_venta    = int(precio_venta)    if precio_venta    else None
        precio_original = int(precio_original) if precio_original else None

        # Corregir inversión
        if precio_original and precio_venta and precio_original < precio_venta:
            precio_original, precio_venta = precio_venta, precio_original

        ahorro     = int(precio_original - precio_venta) if (precio_original and precio_venta) else None
        tiene_desc = 1 if (precio_original and precio_original != precio_venta) else 0

        resultado.append({
            'nombre':             nombre,
            'marca':              item.get('marca', ''),
            'categoria':          categoria,
            'enlace':             item.get('enlace', ''),
            'imagen':             item.get('imagen', ''),
            # Campos enriquecidos
            'precio_venta':       precio_venta,
            'precio_original':    precio_original,
            'descuento_pct':      desc,
            'ahorro_cop':         ahorro,
            'tiene_descuento':    tiene_desc,
            'rango_precio':       _rango_precio(precio_venta, categoria),
            'subcategoria':       _subcategoria(nombre, categoria),
            'almacenamiento_gb':  _almacenamiento_gb(nombre),
            'ram_gb':             _ram_gb(nombre),
            'conectividad_5g':    int(_tiene_5g(nombre)),
            'marca_normalizada':  _marca_normalizada(item.get('marca', '')),
            'nombre_limpio':      _nombre_limpio(nombre),
            'fecha_extraccion':   hoy,
            'fuente':             'exito.com',
        })

    return resultado
