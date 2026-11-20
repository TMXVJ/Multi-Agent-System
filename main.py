"""main.py
Punto de entrada principal para la ejecución del Sistema Multiagente Basado en IA.
Proporciona la interfaz de línea de comandos (CLI) interactiva para el usuario.
"""
import os
from src.config import EMAIL_USER, EMAIL_PASS
from src.supervisor import (
    supervisor,
    clasificador_intencion,
    agente_clasificador
)


def main():
    print("\n" + "-" * 65)
    print("Sistema de agentes basados en IA - CLI")
    print("-" * 65)
    print("\nDescribe la tarea a realizar.")
    print("Ejemplos: 'clasifica este correo', 'genera un reporte de excel', 'organiza este pdf'")
    print("(Escribe 'demo' para ejecutar los ejemplos automáticos o 'salir' para terminar)\n")

    while True:
        try:
            solicitud = input("\n¿Qué deseas hacer?: ").strip()
            if not solicitud:
                continue
            if solicitud.lower() in ["salir", "exit", "quit"]:
                print("Cerrando el sistema. Interaccion terminada")
                break

            if solicitud.lower() == "demo":
                print("\n--- Ejecutando Demo ---")
                res1 = supervisor("clasifica este correo", {"contenido": "Estimado cliente, adjunto factura por $500,000"})
                print(f"Resultado:\n{res1}\n")
                if os.path.exists("Disney456_modified.xlsx"):
                    res2 = supervisor("genera un reporte", {"archivos": "Disney456_modified.xlsx"})
                    print(f"Resultado:\n{res2}\n")
                continue

            # 1. El supervisor detecta la intención
            intencion = clasificador_intencion.predecir(solicitud)

            # 2. Según la intención detectada, se piden los datos al usuario
            if intencion == 0:
                print("Intención: Clasificación de Correo.")
                print("Opciones:")
                print("[1] Escribir o pegar asunto/cuerpo de un correo manualmente")
                print("[2] Conectar y leer correos reales de mi cuenta (Gmail / Outlook vía IMAP)")
                opcion_mail = input("Elige una opción (1 o 2) [default 1]: ").strip()

                if opcion_mail == "2":
                    print("\n Conexión IMAP a Gmail/Outlook:")
                    print("[G] Gmail (imap.gmail.com) - Requiere 'Contraseña de Aplicación'")
                    print("[O] Outlook / Hotmail (outlook.office365.com)")
                    tipo_serv = input("   Proveedor (G/O) [default G]: ").strip().lower()

                    servidor = "outlook.office365.com" if tipo_serv == "o" else "imap.gmail.com"

                    user_env = os.getenv("EMAIL_USER", EMAIL_USER)
                    pass_env = os.getenv("EMAIL_PASS", EMAIL_PASS)

                    user = input(f"   Correo electrónico [{user_env if user_env else 'escribe tu email'}]: ").strip() or user_env
                    if not pass_env:
                        clave = input("Contraseña / Contraseña de aplicación: ").strip()
                    else:
                        clave = pass_env
                        print("   (Usando EMAIL_PASS configurado en .env)")

                    if not user or not clave:
                        print("Debes proporcionar usuario y clave.")
                        continue

                    num_mails = input("¿Cuántos correos recientes deseas clasificar? [default 3]: ").strip()
                    try:
                        max_m = int(num_mails) if num_mails else 3
                    except ValueError:
                        max_m = 3

                    resultado = agente_clasificador.leer_correos_reales(servidor, user, clave, max_correos=max_m)
                    print(f"\n{resultado}\n")
                else:
                    contenido = input("Escribe o佩ga el asunto/cuerpo del correo: ".replace("佩", "")).strip()
                    if not contenido:
                        print("No ingresaste contenido para el correo.")
                        continue
                    resultado = supervisor(solicitud, {"contenido": contenido})
                    print(f"\n{resultado}\n")

            elif intencion == 1:
                print("Intención: Consolidación y Reporte de Archivos Excel.")
                print("Ingresa la ruta o rutas de archivos Excel (separadas por coma):")
                archivos = input("Rutas: ").strip()
                if not archivos:
                    print("No ingresaste ninguna ruta.")
                    continue
                resultado = supervisor(solicitud, {"archivos": archivos})
                print(f"\n{resultado}\n")

            elif intencion == 2:
                print("Intención: Organización y Resumen de Documento PDF.")
                ruta_pdf = input("Ingresa la ruta del archivo PDF: ").strip()
                if not ruta_pdf:
                    print("No ingresaste la ruta del PDF.")
                    continue
                resultado = supervisor(solicitud, {"ruta_pdf": ruta_pdf})
                print(f"\n{resultado}\n")

        except KeyboardInterrupt:
            print("\nOperación cancelada por el usuario.")
            break
        except Exception as e:
            print(f"Error inesperado: {e}")


if __name__ == "__main__":
    main()
