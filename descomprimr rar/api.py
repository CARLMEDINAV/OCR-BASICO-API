import os
import re
import unicodedata
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import Image
import pdfplumber
import pytesseract

# Si estás en Windows y Tesseract no está en el PATH, desmarca y ajusta esta línea:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = FastAPI(
    title="API de Clasificación de Documentos",
    description="Analiza PDFs e imágenes mediante OCR/Texto y retorna el nombre estandarizado.",
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

REGLAS_N8N = [
    # 1. DOCUMENTOS ESPECÍFICOS DEL SII / CERTIFICADOS (Máxima prioridad)
    {"keywords": ["INICIO", "ACTIVIDADES"], "resultado": "SII INICIO ACTIVIDADES"},
    {"keywords": ["IMPUESTOS", "INTERNOS"], "resultado": "SII INICIO ACTIVIDADES"},
    {"keywords": ["ANTECEDENTES"], "resultado": "CERTIFICADO ANTECEDENTES"},

    # 2. DOCUMENTOS DE ESTADO CIVIL Y PERSONALES
    {"keywords": ["MATRIMONIO"], "resultado": "CERTIFICADO MATRIMONIO"},
    {"keywords": ["DIVORCIO"], "resultado": "CERTIFICADO DIVORCIO"},
    {"keywords": ["DEFUNCION"], "resultado": "CERTIFICADO DEFUNCION"},
    {"keywords": ["NACIMIENTO"], "resultado": "CERTIFICADO NACIMIENTO"},

    # 3. EVALUACIÓN FINANCIERA / RIESGO
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

    # 4. INGRESOS Y LABORALES
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

    # 5. OPERACIONALES / TASACIÓN / PROPIEDAD
    {"keywords": ["ESTUDIO"], "resultado": "EET"},
    {"keywords": ["EET"], "resultado": "INFORME DE TITULOS"},
    {"keywords": ["TASACION"], "resultado": "TASACION"},
    {"keywords": ["SUBSIDIO"], "resultado": "CERTIFICADO DE SUBSIDIO"},
    {"keywords": ["OFERTA"], "resultado": "CARTA OFERTA"},
    {"keywords": ["GASTOS"], "resultado": "COMPROBANTE PAGO GOP"},
    {"keywords": ["GOP"], "resultado": "COMPROBANTE PAGO GOP"},
    {"keywords": ["COMPROBANTE"], "resultado": "COMPROBANTE DE PAGO"},
    {"keywords": ["PAGO"], "resultado": "COMPROBANTE DE PAGO"},

    # 6. IDENTIFICACIONES (Baja prioridad por palabras genéricas como RUT/CARNET)
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
    {"keywords": ["RUT"], "resultado": "CI DEUDOR"},
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
    """
    Endpoint que recibe un archivo multipart/form-data,
    analiza su contenido y devuelve el tipo de documento y el nombre sugerido.
    """
    extension = os.path.splitext(file.filename)[1].lower()
    
    if extension not in [".pdf", ".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Formato no soportado. Debe ser PDF, JPG o PNG.")

    # Guardar archivo temporal para procesarlo
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    texto_crudo = ""
    try:
        if extension == ".pdf":
            with pdfplumber.open(temp_path) as pdf:
                for pagina in pdf.pages[:3]:
                    contenido = pagina.extract_text()
                    if contenido:
                        texto_crudo += contenido + "\n"
        else:
            imagen = Image.open(temp_path)
            texto_crudo = pytesseract.image_to_string(imagen, lang='spa+eng')
    except Exception as e:
        os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Evaluación de texto
    texto_a_evaluar = f"{file.filename} {texto_crudo}"
    texto_normalizado = normalizar_texto(texto_a_evaluar)
    tipo_detectado = evaluar_texto(texto_normalizado, REGLAS_N8N)

    if not tipo_detectado:
        # Fallback si no encuentra ninguna regla
        nombre_base = os.path.splitext(file.filename)[0]
        tipo_detectado = nombre_base.upper()

    nuevo_nombre = f"{tipo_detectado}{extension}"

    return {
        "filename_original": file.filename,
        "tipo_documento": tipo_detectado,
        "filename_sugerido": nuevo_nombre,
        "extension": extension
    }