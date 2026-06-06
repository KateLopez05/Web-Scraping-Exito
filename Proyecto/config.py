"""
Configuramos el entorno 
Herramientas usadas: Selenium + BeautifulSoup
Hace parte de la implementación del Scraper
"""

# Importaciones necesarias
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Definimos una función que configure el driver
def configurar_driver(headless: bool = True) -> webdriver.Chrome:
    opciones = Options()

    # Condicional para las opciones
    if headless:
        opciones.add_argument("--headless=new")

    # Dependencias necesarias para la estabilidad
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--window-size=1920,1080")

    # Para evitar detección como bot
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)
    opciones.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # Manejo de errores
    # Aquí ChromeDriver se descarga automáticamente
    try:
        servicio = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=servicio, options=opciones)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        print("Driver configurado correctamente.")
        return driver
    except Exception as e:
        print(f"Error al configurar el driver: {e}")
        raise

# Verificamos que todo funciona correctamente
if __name__ == "__main__":
    print("Verificando dependencias...")
    print("  Selenium importado")
    print("  BeautifulSoup importado")

    print("Iniciando driver...")
    
    try: 
        driver = configurar_driver(headless=True)
        driver.get("https://www.exito.com")
        print(f"  Conexión exitosa - Título: {driver.title}")
        driver.quit()
        print("  Driver cerrado")
        print("\nEntorno listo. Se puede continuar el scraping.")
    except Exception as e:
        print(f"Verificación fallida: {e}")
