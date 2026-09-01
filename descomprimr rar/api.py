import os
import re
import unicodedata
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
import pdfplumber
import pytesseract

# Configuración de Tesseract según el Sistema Operativo
if os.name == 'posix':
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
else:
    ruta_win = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(ruta_win):
        pytesseract.pytesseract.tesseract_cmd = ruta_win

app = FastAPI(
    title="API de Clasificación de Documentos",
    description="Analiza PDFs mediante extracción de texto y retorna el nombre estandarizado bajo cumplimiento normativo.",
    version="1.0.0"
)

MESES_NOMBRES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
]

MAPA_MESES_NUM = {
    "01": "ENERO", "02": "FEBRERO", "03": "MARZO", "04": "ABRIL",
    "05": "MAYO", "06": "JUNIO", "07": "JULIO", "08": "AGOSTO",
    "09": "SEPTIEMBRE", "10": "OCTUBRE", "11": "NOVIEMBRE", "12": "DICIEMBRE"
}

# (Mantenemos tus REGLAS_N8N intactas para la lógica de negocio)
REGLAS_N8N = [
    {"keywords": ["DECLARACION", "SALUD"], "resultado": "DPS"},
    {"keywords": ["DPS"], "resultado": "DPS"},
    {"keywords": ["SOLICITUD", "SUSCRIPCION"], "resultado": "SOLICITUD DE SUSCRIPCION"},
    {"keywords": ["SUSCRIPCION", "APROBADA"], "resultado": "SOLICITUD DE SUSCRIPCION APROBADA"},
    {"keywords": ["CORREO", "CREDITU"], "resultado": "CORREO CREDITU"},
    {"keywords": ["INICIO", "ACTIVIDADES"], "resultado": "SII INICIO ACTIVIDADES"},
    {"keywords": ["IMPUESTOS", "INTERNOS"], "resultado": "SII INICIO ACTIVIDADES"},
    {"keywords": ["ANTECEDENTES"], "resultado": "CERTIFICADO ANTECEDENTES"},
    {"keywords": ["MATRIMONIO"], "resultado": "CERTIFICADO MATRIMONIO"},
    {"keywords": ["DIVORCIO"], "resultado": "CERTIFICADO DIVORCIO"},
    {"keywords": ["DEFUNCION"], "resultado": "CERTIFICADO DEFUNCION"},
    {"keywords": ["CERTIFICADO", "NACIMIENTO"], "resultado": "CERTIFICADO NACIMIENTO"},
    {"keywords": ["DICOM", "CONYUGE"], "resultado": "DICOM CONYUGE"},
    {"keywords": ["DICOM", "CODEUDOR"], "resultado": "DICOM CODEUDOR"},
    {"keywords": ["DICOM"], "resultado": "DICOM"},
    {"keywords": ["SBIF", "CONYUGE"], "resultado": "SBIF CONYUGE"},
    {"keywords": ["SBIF", "CODEUDOR"], "resultado": "SBIF CODEUDOR"},
    {"keywords": ["SBIF"], "resultado": "SBIF"},
    {"keywords": ["CMF"], "resultado": "CMF"},
    {"keywords": ["GESINTEL"], "resultado": "GESINTEL"},
    {"keywords": ["RIESGO"], "resultado": "RESOLUCION DE RIESGO"},
    {"keywords": ["RISK"], "resultado": "RESOLUCION DE RIESGO"},
    {"keywords": ["WRITING"], "resultado": "ODE"},
    {"keywords": ["ORDER"], "resultado": "ODE"},
    {"keywords": ["ODE"], "resultado": "ODE"},
    {"keywords": ["DEPURACION"], "resultado": "DEPURACION DE INGRESOS"},
    {"keywords": ["LIQUIDACION"], "resultado": "LIQUIDACIONES DE SUELDO"},
    {"keywords": ["LIQUIDACIONES"], "resultado": "LIQUIDACIONES DE SUELDO"},
    {"keywords": ["LIQUIDAC"], "resultado": "LIQUIDACIONES DE SUELDO"},
    {"keywords": ["LQ"], "resultado": "LIQUIDACIONES DE SUELDO"},
    {"keywords": ["SUELDO"], "resultado": "LIQUIDACIONES DE SUELDO"},
    {"keywords": ["COTIZACION"], "resultado": "CERTIFICADO COTIZACIONES"},
    {"keywords": ["COTIZACIONES"], "resultado": "CERTIFICADO COTIZACIONES"},
    {"keywords": ["COTIZAC"], "resultado": "CERTIFICADO COTIZACIONES"},
    {"keywords": ["AFP"], "resultado": "CERTIFICADO COTIZACIONES"},
    {"keywords": ["CARTOLA", "AFP"], "resultado": "CERTIFICADO COTIZACIONES"},
    {"keywords": ["ANTIGUEDAD"], "resultado": "CERTIFICADO DE ANTIGUEDAD"},
    {"keywords": ["ESTUDIO"], "resultado": "EET"},
    {"keywords": ["EET"], "resultado": "INFORME DE TITULOS"},
    {"keywords": ["TASACION"], "resultado": "TASACION"},
    {"keywords": ["SUBSIDIO"], "resultado": "CERTIFICADO DE SUBSIDIO"},
    {"keywords": ["OFERTA"], "resultado": "CARTA OFERTA"},
    {"keywords": ["GASTOS"], "resultado": "COMPROBANTE PAGO GOP"},
    {"keywords": ["GOP"], "resultado": "COMPROBANTE PAGO GOP"},
    {"keywords": ["COMPROBANTE"], "resultado": "COMPROBANTE DE PAGO"},
    {"keywords": ["PAGO"], "resultado": "COMPROBANTE DE PAGO"},
    {"keywords": ["CODEUDOR", "CEDULA"], "resultado": "CI CODEUDOR"},
    {"keywords": ["CODEUDOR", "CI"], "resultado": "CI CODEUDOR"},
    {"keywords": ["CODEUDOR", "CARNET"], "resultado": "CI CODEUDOR"},
    {"keywords": ["CODEUDOR", "RUT"], "resultado": "CI CODEUDOR"},
    {"keywords": ["CODEUDOR"], "resultado": "CI CODEUDOR"},
    {"keywords": ["MANDATARIO"], "resultado": "CI MANDATARIO"},
    {"keywords": ["VENDEDOR"], "resultado": "CI VENDEDOR"},
    {"keywords": ["CEDULA"], "resultado": "CI DEUDOR"},
    {"keywords": ["CARNET"], "resultado": "CI DEUDOR"},
    {"keywords": ["CI"], "resultado": "CI DEUDOR"},
    {"keywords": ["FOTOCOPIA"], "resultado": "CI DEUDOR"}
]

def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r'([a-z])([A-Z])', r'\1 \2', texto)
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    texto = texto.upper()
    texto = re.sub(r'C\.\s*I\.', ' CI ', texto)
    texto = re.sub(r'C\.I\.', ' CI ', texto)
    texto = re.sub(r'C\s+I\s+', ' CI ', texto)
    texto = re.sub(r'[^A-Z0-9]', ' ', texto)
    return texto

def extraer_mes_anio(texto_normalizado: str) -> str:
    anio_match = re.search(r'202[0-9]', texto_normalizado)
    anio = anio_match.group(0) if anio_match else ""

    for mes in MESES_NOMBRES:
        if re.search(r'\b' + mes + r'\b', texto_normalizado):
            return f"{mes} {anio}".strip()

    match_num = re.search(r'\b(0[1-9]|1[0-2])[\/\-](202[0-9])\b', texto_normalizado)
    if match_num:
        mes_num = match_num.group(1)
        anio_num = match_num.group(2)
        mes_nombre = MAPA_MESES_NUM.get(mes_num, "")
        return f"{mes_nombre} {anio_num}".strip()

    return ""

def evaluar_texto(texto_normalizado: str, reglas: list) -> str:
    if not texto_normalizado:
        return None

    for regla in reglas:
        match = True
        for kw in regla["keywords"]:
            if len(kw) <= 2:
                pattern = r'\b' + re.escape(kw) + r'\b'
                if not re.search(pattern, texto_normalizado):
                    match = False
                    break
            else:
                if kw not in texto_normalizado:
                    match = False
                    break
        if match:
            resultado_base = regla["resultado"]
            if resultado_base == "LIQUIDACIONES DE SUELDO":
                mes_anio = extraer_mes_anio(texto_normalizado)
                if mes_anio:
                    return f"LIQUIDACIONES DE SUELDO {mes_anio}"
            return resultado_base
    return None


@app.post("/clasificar")
async def clasificar_documento(file: UploadFile = File(...)):
    # 1. Validación estricta del tipo de archivo (Restringido solo a PDF para tu flujo)
    extension = os.path.splitext(file.filename)[1].lower()
    if extension != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Formato no soportado. Este endpoint solo procesa archivos PDF."
        )

    texto_extraido = ""
    pdf = None

    try:
        # 2. Abrir el PDF directamente desde el flujo de bytes en memoria RAM
        # pdfplumber acepta un objeto tipo 'BytesIO' o similar a través del file de FastAPI
        pdf = pdfplumber.open(file.file)
        
        # Extraer texto de las páginas de forma segura
        for pagina in pdf.pages:
            texto_pag = pagina.extract_text()
            if texto_pag:
                texto_extraido += " " + texto_pag
            # 3. Normalizar y clasificar el documento
        texto_norm = normalizar_texto(texto_extraido)
        tipo_documento = evaluar_texto(texto_norm, REGLAS_N8N) or "NO_IDENTIFICADO"

        # 4. Construcción de respuesta minimizada
        respuesta = {
            "filename_original": file.filename,
            "tipo_documento": tipo_documento,
            "filename_sugerido": f"{tipo_documento}.pdf" if tipo_documento != "NO_IDENTIFICADO" else file.filename,
            "extension": ".pdf"
        }
        return JSONResponse(content=respuesta)

    except Exception as e:
        # 5. Seguridad de Logs: No imprimimos el valor de 'texto_extraido' en el error
        print(f"⚠️ Error interno en procesamiento OCR: Ocurrido durante la clasificación.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar e identificar el archivo."
        )

    finally:
        # 6. Garantía de Destrucción: Cerrar recursos abiertos para liberar RAM en Render
        if pdf:
            pdf.close()
        await file.close()

