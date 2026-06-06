# Web Scraping Éxito - Pipeline ETL

## Descripción

Este proyecto implementa un pipeline ETL desarrollado en Python para extraer, procesar y almacenar información de productos publicados en el portal de comercio electrónico Exito.com.

El sistema realiza Web Scraping utilizando Selenium y BeautifulSoup, procesa y limpia los datos obtenidos, y posteriormente los almacena en una base de datos SQLite mediante SQLAlchemy.

---

## Objetivo

Aplicar técnicas de Web Scraping para recolectar información relevante desde un sitio de comercio electrónico real, transformarla y almacenarla en una base de datos estructurada siguiendo la metodología ETL.

---

## Tecnologías utilizadas

- **Python** - Lenguaje de programación principal
- **Selenium** - Automatización del navegador y manejo de contenido dinámico
- **BeautifulSoup** - Análisis y extracción de datos HTML
- **Pandas** - Procesamiento y transformación de datos
- **SQLite** - Base de datos relacional
- **SQLAlchemy** - ORM para gestión de base de datos
- **webdriver-manager** - Gestión automática de ChromeDriver
- **lxml** - Parser HTML de alto rendimiento

---

## Estructura del proyecto

```text
## 📁 Estructura del Proyecto
Web Scraping Exito/
├── Proyecto/
│   ├── auditoria.txt               # Registro de ejecuciones y eventos
│   ├── config.py                   # Configuración general del proyecto
│   ├── consumo_masivo.db           # Base de datos SQLite
│   ├── ejecucion.py                # Punto de entrada principal
│   ├── extraccion.py               # Lógica de extracción de datos
│   ├── ingesta.py                  # Carga de datos a la BD
│   ├── limpiar_bd.py               # Limpieza y mantenimiento de la BD
│   ├── modelo.py                   # Definición de modelos de datos
│   ├── procesamiento.py            # Transformación y procesamiento
│   ├── scrapper.py                 # Scraper principal (Éxito)
│   ├── productos_exito.csv         # Datos crudos extraídos (CSV)
│   ├── productos_exito.json        # Datos crudos extraídos (JSON)
│   ├── productos_enriquecidos.csv  # Datos procesados (CSV)
│   ├── productos_enriquecidos.json # Datos procesados (JSON)
│   └── LopezKaterin_MezaBayron_Entendimiento_Necesidad_EA2.ipynb  # Notebook de análisis
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Flujo ETL

### 1. Extracción de datos

El módulo `extraccion.py` realiza:

- Navegación automática en Exito.com
- Extracción de información de productos mediante scroll infinito
- Manejo de carga dinámica de contenido
- Control de popups y modales de cookies
- Limitación configurable de productos por categoría
- Deduplicación en tiempo real
- Exportación a CSV y JSON

#### Datos extraídos

- Nombre del producto
- Precio actual
- Precio anterior (si aplica)
- Marca
- Categoría
- Enlace del producto
- URL de imagen

---

### 2. Procesamiento de datos

El módulo `procesamiento.py` se encarga de:

- Limpieza de precios (formato colombiano: $1.999.900)
- Normalización de categorías
- Generación de IDs únicos reproducibles (hash SHA-1)
- Extracción de contenido neto y unidad de medida
- Detección de duplicados por código de barras
- Validación de reglas de negocio (precio_promocion < precio_venta)
- Detección de outliers mediante IQR (factor 3)
- Transformación al modelo relacional

---

### 3. Ingesta de datos

El módulo `ingesta.py`:

- Conecta con SQLite mediante SQLAlchemy
- Crea tablas relacionales con PRIMARY KEYS y FOREIGN KEYS
- Inserta información masivamente usando INSERT OR IGNORE
- Evita registros duplicados (idempotencia)
- Mantiene integridad referencial
- Crea índices para optimizar consultas

---

## Base de datos

El proyecto utiliza SQLite como motor de base de datos relacional.

### Tablas principales

**productos**
- `id_producto` (PK)
- `codigo_barras`
- `nombre`
- `categoria`
- `marca`
- `contenido_neto`
- `unidad`

**tiendas**
- `id_tienda` (PK)
- `nombre`
- `tipo_canal`
- `ciudad`

**precios**
- `id_producto` (PK, FK → productos)
- `id_tienda` (PK, FK → tiendas)
- `fecha_registro` (PK)
- `precio_venta`
- `precio_promocion`
- `fuente`

**indicadores_economicos**
- `fecha` (PK)

---

## Instalación

### 1. Clonar o descargar el proyecto

Ubicarse en la carpeta del proyecto:

```bash
cd "Entrega_2"
```

---

### 2. Crear entorno virtual (opcional pero recomendado)

```bash
python -m venv venv
```

#### Activar entorno virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

---

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

#### Contenido de `requirements.txt`:

```
selenium
beautifulsoup4
requests
webdriver-manager
lxml
pandas
sqlalchemy
```

---

## Ejecución del proyecto

### Opción 1: Ejecutar módulos individuales

#### Paso 1: Ejecutar extracción

```bash
python extraccion.py
```

Este proceso:
- Navega automáticamente por categorías de Exito.com
- Extrae productos utilizando scroll infinito
- Genera archivos `productos_exito.csv` y `productos_exito.json`

#### Paso 2: Ejecutar ingesta

```bash
python ingesta.py
```

Este proceso:
- Limpia y transforma datos
- Crea tablas en SQLite con el esquema correcto
- Inserta registros en `consumo_masivo.db`

---

### Opción 2: Ejecutar notebook completo

Abrir y ejecutar el notebook Jupyter:

```bash
jupyter notebook LopezKaterin_MezaBayron_Entendimiento_Necesidad_EA2.ipynb
```

El notebook ejecuta el pipeline completo:
1. Configuración del entorno
2. Extracción de datos
3. Procesamiento
4. Ingesta a base de datos
5. Pruebas de verificación

---

## Archivos generados

El proyecto genera automáticamente:

- `productos_exito.csv` - Datos crudos en formato CSV
- `productos_exito.json` - Datos crudos en formato JSON
- `consumo_masivo.db` - Base de datos SQLite con datos procesados

---

## Consultas SQL de ejemplo

### Total de productos

```sql
SELECT COUNT(*) AS total_productos
FROM productos;
```

---

### Productos por categoría

```sql
SELECT categoria, COUNT(*) AS cantidad
FROM productos
GROUP BY categoria
ORDER BY cantidad DESC;
```

---

### Top 10 marcas

```sql
SELECT marca, COUNT(*) AS cantidad
FROM productos
GROUP BY marca
ORDER BY cantidad DESC
LIMIT 10;
```

---

### Estadísticas de precios

```sql
SELECT
    MIN(precio_venta) AS precio_minimo,
    MAX(precio_venta) AS precio_maximo,
    ROUND(AVG(precio_venta), 2) AS precio_promedio
FROM precios;
```

---

### Productos con descuento

```sql
SELECT 
    p.nombre,
    pr.precio_venta,
    pr.precio_promocion,
    ROUND((1 - pr.precio_venta / pr.precio_promocion) * 100, 2) AS descuento_porcentaje
FROM productos p
JOIN precios pr ON p.id_producto = pr.id_producto
WHERE pr.precio_promocion IS NOT NULL
ORDER BY descuento_porcentaje DESC
LIMIT 20;
```

---

### Integridad referencial

```sql
-- Verificar que todos los precios tienen producto asociado
SELECT COUNT(*) AS registros_huerfanos
FROM precios
WHERE id_producto NOT IN (SELECT id_producto FROM productos);
```

---

## Validaciones implementadas

El sistema incluye múltiples capas de validación:

### Durante la extracción:
- Manejo de errores con try/except
- Control de timeouts
- Cierre automático del driver Selenium
- Deduplicación por par (nombre, enlace)

### Durante el procesamiento:
- Validación de precios positivos
- Limpieza de formato colombiano ($1.999.900)
- Validación: precio_promocion < precio_venta
- Detección de outliers mediante IQR
- Eliminación de filas sin nombre o categoría

### Durante la ingesta:
- INSERT OR IGNORE para prevenir duplicados
- Verificación de esquema antes de insertar
- Creación de índices para optimización
- Validación de integridad referencial

---

## Resultados

El scraper permite automatizar la extracción masiva de productos desde Exito.com, transformando los datos obtenidos y almacenándolos en una base de datos estructurada para posteriores análisis.

### Métricas de ejemplo (tecnología):
- **Productos extraídos:** 37+
- **Rango de precios:** $69.900 - $3.999.900
- **Precio promedio:** ~$1.736.835
- **Categorías:** Tecnología, celulares, electrodomésticos, etc.

---

## Pruebas de verificación

El proyecto incluye 5 pruebas automatizadas:

1. **Conteo de registros por tabla** - Verifica que datos fueron insertados
2. **Integridad referencial** - Valida FKs entre precios y productos
3. **Validación de precios** - Confirma rangos lógicos
4. **Ausencia de duplicados** - Ejecuta pipeline 2 veces sin duplicar
5. **Comparación con fuente original** - Verifica 5 productos manualmente

---

## Problemas conocidos y soluciones

### Problema: Scroll infinito no detecta más productos
**Causa:** Exito.com usa carga dinámica lazy loading  
**Solución:** Implementado scroll gradual con MAX_SCROLLS_SIN_NUEVOS=5

### Problema: INSERT OR IGNORE no previene duplicados
**Causa:** BD heredaba esquema sin PRIMARY KEYS de EA1  
**Solución:** crear_tablas() recrea esquema con PKs correctas

### Problema: Error "List argument must consist only of tuples"
**Causa:** exec_driver_sql requiere tuplas, no listas  
**Solución:** Usar itertuples() en lugar de values.tolist()

---

## Conclusiones

El proyecto permitió implementar exitosamente un pipeline ETL aplicando técnicas de Web Scraping sobre un sitio de comercio electrónico real.

Se logró automatizar la extracción, procesamiento y almacenamiento de datos utilizando Selenium, BeautifulSoup y SQLite, garantizando la integridad y consistencia de la información obtenida.

Además, se implementaron mecanismos de validación, control de errores y prevención de duplicados para mejorar la calidad de los datos almacenados.

### Aprendizajes clave:

1. **Selenium + BeautifulSoup** es la combinación óptima para sitios con JavaScript dinámico
2. **Scroll infinito** requiere estrategia diferente a paginación con botones
3. **Idempotencia** del pipeline es crítica para ambientes de producción
4. **PKs compuestas** en precios permiten histórico sin duplicados
5. **Detección temprana** de cambios en estructura HTML del sitio fuente

---

## Autores

- **Katerin Vanesa Lopez Moros**
- **Bayron Meza Guzman**

**Curso:** Programación para análisis de datos  
**Docente:** Ana Lopez  
**Institución:** IUDIGITAL  
**Fecha:** Mayo 2026

---

## Observaciones técnicas

El sitio Exito.com utiliza contenido dinámico cargado mediante JavaScript, por lo que fue necesario implementar Selenium junto con BeautifulSoup para lograr una extracción correcta de los datos.

El formato de precios colombiano ($1.999.900) requirió expresiones regulares específicas para convertir correctamente a tipo numérico.

---

## Licencia

Este proyecto fue desarrollado con fines académicos como parte de la evidencia de aprendizaje 2 del curso de Programación para Análisis de Datos.

---

## Soporte

Para reportar problemas o sugerencias, contactar a los autores mediante la plataforma del curso.
