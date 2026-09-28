import os
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


from src.azure_client import (
    get_work_item,
    get_work_item_relations_data,
    get_total_user_stories_by_sprint,
    get_user_stories_by_sprint,
    get_sprints
)
from src.pdf_generator import generate_pdf
from src.docx_generator import generate_docx
from src.supabase_client import (
    eliminar_pdf_supabase,
    subir_pdf_supabase,
    subir_docx_supabase,
    supabase_client,
    BUCKET_NAME
)

app = FastAPI(
    title="Azure DevOps Automation API",
    description="API para procesar historias de usuario,generar HU por sprint y exportar a PDF vía Supabase",
    version="1.1.0"
)

# Configuración de CORS para el entorno local y el despliegue en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://nueva-celula.vercel.app/"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    """Ruta base para verificar el estado de la API."""
    return {
        "status": "ok",
        "mensaje": "API generadora de PDFs funcionando con Supabase"
    }


@app.get("/generar-pdf/{id_hu}")
def crear_pdf(id_hu: int):
    """
    Endpoint principal:
    1. Consulta la HU en Azure DevOps.
    2. Identifica su Sprint y calcula el total de HUs del mismo.
    3. Extrae las relaciones (Predecesor y Relacionados) usando get_work_item_relations_data.
    4. Generar el PDF temporalmente y lo sube a Supabase Storage.
    """
    try:
        # 1. Obtener la Historia de Usuario (incluye el árbol de 'relations')
        work_item = get_work_item(id_hu)

        # 2. Obtener el Sprint (IterationPath) al que pertenece la HU
        iteration_path = work_item["fields"]["System.IterationPath"]

        # 3. Obtener el total de historias de usuario asociadas a ese Sprint
        total_historias_sprint = get_total_user_stories_by_sprint(iteration_path)

        # 4. Obtener el diccionario unificado de relaciones (Predecesor + Relacionado)
        datos_requerimiento = get_work_item_relations_data(work_item)

        # 5. Generar el PDF pasándole la metadata de las relaciones
        ruta_pdf = generate_pdf(
            work_item,
            total_historias_sprint,
            datos_requerimiento  # Enviamos el objeto con la estructura unificada de relaciones
        )
        # 6. Obtener el nombre del Sprint
        nombre_sprint = (
            iteration_path.split("\\")[-1]
            .replace(" ", "_")
            )
        # Construir el nombre del archivo
        nombre_archivo = f"Historia_Usuario_Proyecto_Rummi_{id_hu}.pdf"
        # Subir a Supabase
        url_pdf = subir_pdf_supabase(
            ruta_pdf,
            nombre_archivo
            )

        # 7. Limpieza: Eliminar el archivo PDF local temporal para liberar espacio en el entorno
        if os.path.exists(ruta_pdf):
            os.remove(ruta_pdf)

        return {
            "mensaje": "PDF generado correctamente y guardado en Supabase Storage",
            "archivo": nombre_archivo,
            "url_archivo": url_pdf,
            "total_historias_sprint": total_historias_sprint
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/generar-docx/{id_hu}")
def crear_docx(id_hu: int):
    """
    Endpoint para generar documento Word (.docx):
    1. Consulta la HU en Azure DevOps.
    2. Identifica su Sprint y calcula el total de HUs del mismo.
    3. Extrae las relaciones (Predecesor y Relacionados).
    4. Genera el DOCX y lo sube a Supabase Storage.
    """
    try:
        # 1. Obtener la Historia de Usuario
        work_item = get_work_item(id_hu)

        # 2. Obtener el Sprint (IterationPath)
        iteration_path = work_item["fields"]["System.IterationPath"]

        # 3. Obtener el total de historias de usuario del Sprint
        total_historias_sprint = get_total_user_stories_by_sprint(iteration_path)

        # 4. Obtener las relaciones
        datos_requerimiento = get_work_item_relations_data(work_item)

        # 5. Generar el DOCX
        ruta_docx = generate_docx(
            work_item,
            total_historias_sprint,
            datos_requerimiento
        )

        # 6. Subir a Supabase
        nombre_archivo = f"Historia_Usuario_Proyecto_Rummi_{id_hu}.docx"
        url_docx = subir_docx_supabase(ruta_docx, nombre_archivo)

        # 7. Limpiar archivo temporal
        if os.path.exists(ruta_docx):
            os.remove(ruta_docx)

        return {
            "mensaje": "DOCX generado correctamente y guardado en Supabase Storage",
            "archivo": nombre_archivo,
            "url_archivo": url_docx,
            "total_historias_sprint": total_historias_sprint
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/sprints")
def obtener_sprints():
    return get_sprints()

@app.get("/generar-pdfs-sprint")
def generar_pdfs_sprint(iteration_path: str):
    """
    Genera un PDF para todas las Historias de Usuario de un Sprint.
    """

    try:

        # Obtener todas las HU del Sprint
        historias = get_user_stories_by_sprint(iteration_path)

        if not historias:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron Historias de Usuario para el Sprint indicado."
            )

        total_historias_sprint = len(historias)

        pdfs_generados = []
        errores = []

        # Recorrer todas las HU
        for id_hu in historias:

            try:

                # Obtener la HU
                work_item = get_work_item(id_hu)

                # Obtener las relaciones
                datos_requerimiento = get_work_item_relations_data(work_item)

                # Generar el PDF
                ruta_pdf = generate_pdf(
                    work_item,
                    total_historias_sprint,
                    datos_requerimiento
                )

                nombre_sprint = (
                    iteration_path.split("\\")[-1]
                    .replace(" ", "_")
                    )

                nombre_archivo = f"Historia_Usuario_Proyecto_Rummi_{id_hu}.pdf"

                # Subir a Supabase
                url_pdf = subir_pdf_supabase(
                    ruta_pdf,
                    nombre_archivo
                )

                # Eliminar el PDF temporal
                if os.path.exists(ruta_pdf):
                    os.remove(ruta_pdf)

                pdfs_generados.append({
                    "id_hu": id_hu,
                    "archivo": nombre_archivo,
                    "url_archivo": url_pdf
                })

            except Exception as e:

                errores.append({
                    "id_hu": id_hu,
                    "error": str(e)
                })

        return {
            "mensaje": f"Se generaron {len(pdfs_generados)} PDFs.",
            "sprint": iteration_path,
            "total_historias": total_historias_sprint,
            "pdfs_generados": pdfs_generados,
            "errores": errores
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/generar-docx-sprint")
def generar_docx_sprint(iteration_path: str):
    """
    Genera un documento Word (.docx) para todas las Historias de Usuario de un Sprint.
    """

    try:

        # Obtener todas las HU del Sprint
        historias = get_user_stories_by_sprint(iteration_path)

        if not historias:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron Historias de Usuario para el Sprint indicado."
            )

        total_historias_sprint = len(historias)

        docxs_generados = []
        errores = []

        # Recorrer todas las HU
        for id_hu in historias:

            try:

                # Obtener la HU
                work_item = get_work_item(id_hu)

                # Obtener las relaciones
                datos_requerimiento = get_work_item_relations_data(work_item)

                # Generar el DOCX
                ruta_docx = generate_docx(
                    work_item,
                    total_historias_sprint,
                    datos_requerimiento
                )

                nombre_archivo = f"Historia_Usuario_Proyecto_Rummi_{id_hu}.docx"

                # Subir a Supabase
                url_docx = subir_docx_supabase(
                    ruta_docx,
                    nombre_archivo
                )

                # Eliminar el DOCX temporal
                if os.path.exists(ruta_docx):
                    os.remove(ruta_docx)

                docxs_generados.append({
                    "id_hu": id_hu,
                    "archivo": nombre_archivo,
                    "url_archivo": url_docx
                })

            except Exception as e:

                errores.append({
                    "id_hu": id_hu,
                    "error": str(e)
                })

        return {
            "mensaje": f"Se generaron {len(docxs_generados)} DOCXs.",
            "sprint": iteration_path,
            "total_historias": total_historias_sprint,
            "docxs_generados": docxs_generados,
            "errores": errores
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/obtener-sprint/{id_hu}")
def obtener_sprint(id_hu: int):
    """
    Obtiene el Sprint al que pertenece una Historia de Usuario
    consultando Azure DevOps.
    """

    try:
        # Obtener la Historia de Usuario desde Azure DevOps
        work_item = get_work_item(id_hu)

        # Obtener los campos de la HU
        fields = work_item.get("fields", {})

        # Obtener el Iteration Path
        iteration_path = fields.get(
            "System.IterationPath",
            ""
        )

        if not iteration_path:
            raise HTTPException(
                status_code=404,
                detail=f"La HU {id_hu} no tiene un Iteration Path asignado."
            )

        # Obtener únicamente el nombre del Sprint
        nombre_sprint = iteration_path.split("\\")[-1]

        return {
            "id_hu": id_hu,
            "iteration_path": iteration_path,
            "nombre_sprint": nombre_sprint
        }

    except HTTPException:
        raise

    except Exception as e:
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar Azure DevOps: {str(e)}"
        )
        
@app.get("/historial")
def obtener_historial():
    """
    Devuelve la lista de PDFs generados ordenados desde el más reciente.
    El Sprint se obtiene consultando Azure DevOps mediante el ID de la HU.
    """

    try:
        # Listar todos los archivos dentro del bucket
        archivos = supabase_client.storage.from_(BUCKET_NAME).list()

        historial = []

        for i, archivo in enumerate(archivos):

            nombre = archivo.get("name")

            # Procesar únicamente archivos PDF y DOCX
            if not nombre or not (
                nombre.lower().endswith(".pdf")
                or nombre.lower().endswith(".docx")
            ):
                continue

            # URL pública del archivo
            url_publica = (
                supabase_client.storage
                .from_(BUCKET_NAME)
                .get_public_url(nombre)
            )

            # Valores por defecto
            id_hu = 0
            sprint = ""

            # =====================================================
            # 1. EXTRAER ID DE LA HU DESDE EL NOMBRE DEL PDF
            # =====================================================

            try:
                # Ejemplo:
                # Historia_Usuario_Proyecto_Rummi_34139.pdf

                nombre_sin_extension = nombre.rsplit(".", 1)[0]

                partes = nombre_sin_extension.split("_")

                # El ID de la HU está al final
                id_hu = int(partes[-1])

            except (ValueError, IndexError):
                print(
                    f"No fue posible obtener el ID de la HU "
                    f"desde el archivo: {nombre}"
                )

            # =====================================================
            # 2. CONSULTAR AZURE DEVOPS
            # =====================================================

            if id_hu:
                try:

                    work_item = get_work_item(id_hu)

                    fields = work_item.get("fields", {})

                    # Obtener Iteration Path
                    iteration_path = fields.get(
                        "System.IterationPath",
                        ""
                    )

                    # Obtener nombre del Sprint
                    if iteration_path:
                        sprint = iteration_path.split("\\")[-1]

                except Exception as e:
                    # Si Azure DevOps falla, NO detener el historial
                    print(
                        f"No fue posible obtener el Sprint "
                        f"de la HU {id_hu}: {str(e)}"
                    )

                    sprint = ""

            # =====================================================
            # 3. AGREGAR INFORMACIÓN AL HISTORIAL
            # =====================================================

            # Determinar tipo de archivo
            tipo = "DOCX" if nombre.lower().endswith(".docx") else "PDF"

            historial.append({
                "id": i + 1,
                "idHu": id_hu,
                "sprint": sprint,
                "nombre": nombre,
                "tipo": tipo,
                "fecha": archivo.get(
                    "created_at",
                    "Fecha desconocida"
                )[:10],
                "url_archivo": url_publica
            })

        # Mostrar primero los más recientes
        return historial[::-1]

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Error al obtener el historial de Supabase: "
                f"{str(e)}"
            )
        )
        
@app.delete("/historial/{nombre_archivo}")
def eliminar_pdf(nombre_archivo: str):

    eliminado = eliminar_pdf_supabase(nombre_archivo)

    if not eliminado:
        raise HTTPException(
            status_code=404,
            detail="No fue posible eliminar el archivo"
        )

    return {
        "mensaje": "Archivo eliminado correctamente"
    }