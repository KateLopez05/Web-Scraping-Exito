"""
Aquí limpiamos la BD creada en la EA1 (ya que se tomo un dataset
de prueba para hacer ingesta en la BD), antes de cargar los datos 
del web Scraping a Exito.com 
"""


from sqlalchemy import create_engine, text

# =========================================================
# CONFIGURACIÓN
# =========================================================

DB_PATH = "consumo_masivo.db"

engine = create_engine(f"sqlite:///{DB_PATH}")

TABLAS = [

    "precios",
    "productos",
    "tiendas",
    "indicadores_economicos"

]

# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================

def limpiar_base_datos():

    print("\n" + "=" * 60)
    print("LIMPIANDO BASE DE DATOS")
    print("=" * 60)

    with engine.begin() as conn:

        for tabla in TABLAS:

            conn.execute(
                text(f"DELETE FROM {tabla}")
            )

            print(f" Tabla '{tabla}' limpia")

    print("\n Base de datos lista para recibir datos")
    print("\n Estado de la BD tras limpieza\n")

    with engine.connect() as conn:

        for tabla in TABLAS:

            n = conn.execute(

                text(f"SELECT COUNT(*) FROM {tabla}")

            ).scalar()

            estado = (

                " vacía"
                if n == 0
                else f" {n} registros restantes"

            )

            print(f"{tabla:<30} {estado}")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    limpiar_base_datos()