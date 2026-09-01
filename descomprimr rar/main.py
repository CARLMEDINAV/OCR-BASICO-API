import os
import re
import unicodedata
from PIL import Image
import pdfplumber
import pytesseract

DIRECTORIO_ENTRADA = "."

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
    {"keywords": ["FOTOCOPIA"], "resultado": "CI DEUDOR"},

    {"keywords": ["DICOM", "CONYUGE"], "resultado": "DICOM CONYUGE"},
    {"keywords": ["DICOM", "CODEUDOR"], "resultado": "DICOM CODEUDOR"},
    {"keywords": ["DICOM"], "resultado": "DICOM"},
    {"keywords": ["SBIF", "CONYUGE"], "resultado": "SBIF CONYUGE"},
    {"keywords": ["SBIF", "CODEUDOR"], "resultado": "SBIF CODEUDOR"},
    {"keywords": ["SBIF"], "resultado": "SBIF"},
    {"keywords": ["CMF"], "resultado": "CMF"},
    {"keywords": ["GESINTEL"], "resultado": "GESINTEL"},

    {"keywords": ["DEPURACION"], "resultado": "DEPURACION DE INGRESOS"},
    
    # REGLAS DE LIQUIDACIONES
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

    {"keywords": ["MATRIMONIO"], "resultado": "CERTIFICADO MATRIMONIO"},
    {"keywords": ["DIVORCIO"], "resultado": "CERTIFICADO DIVORCIO"},
    {"keywords": ["DEFUNCION"], "resultado": "CERTIFICADO DEFUNCION"},
    {"keywords": ["NACIMIENTO"], "resultado": "CERTIFICADO NACIMIENTO"},

    {"keywords": ["INICIO", "ACTIVIDADES"], "resultado": "SII INICIO ACTIVIDADES"},
    {"keywords": ["IMPUESTOS", "INTERNOS"], "resultado": "SII INICIO ACTIVIDADES"},

    {"keywords": ["GASTOS"], "resultado": "COMPROBANTE PAGO GOP"},
    {"keywords": ["GOP"], "resultado": "COMPROBANTE PAGO GOP"},
    {"keywords": ["PAGO"], "resultado": "COMPROBANTE DE PAGO"},
    {"keywords": ["COMPROBANTE"], "resultado": "COMPROBANTE DE PAGO"},
    {"keywords": ["ESTUDIO"], "resultado": "EET"},
    {"keywords": ["EET"], "resultado": "INFORME DE TITULOS"},
    {"keywords": ["TASACION"], "resultado": "TASACION"},
    {"keywords": ["SUBSIDIO"], "resultado": "CERTIFICADO DE SUBSIDIO"},
    {"keywords": ["OFERTA"], "resultado": "CARTA OFERTA"},
    {"keywords": ["RIESGO"], "resultado": "RESOLUCION DE RIESGO"},
    {"keywords": ["RISK"], "resultado": "RESOLUCION DE RIESGO"},
    {"keywords": ["WRITING"], "resultado": "ODE"},
    {"keywords": ["ORDER"], "resultado": "ODE"},
    {"keywords": ["ODE"], "resultado": "ODE"}
]


def normalizar_texto(texto):
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


def extraer_mes_anio(texto_normalizado):
    """
    Busca patrones de mes y año dentro del texto del documento.
    Ejemplos detectados: "AGOSTO 2026", "08/2026", "08-2026", "SEPTIEMBRE"
    """
    anio_match = re.search(r'202[0-9]', texto_normalizado)
    anio = anio_match.group(0) if anio_match else ""

    # 1. Buscar si la palabra del mes está explícita (ej. AGOSTO)
    for mes in MESES_NOMBRES:
        if re.search(r'\b' + mes + r'\b', texto_normalizado):
            return f"{mes} {anio}".strip()

    # 2. Buscar si viene en formato numérico MM/YYYY o MM-YYYY (ej. 08/2026)
    match_num = re.search(r'\b(0[1-9]|1[0-2])[\/\-](202[0-9])\b', texto_normalizado)
    if match_num:
        mes_num = match_num.group(1)
        anio_num = match_num.group(2)
        mes_nombre = MAPA_MESES_NUM.get(mes_num, "")
        return f"{mes_nombre} {anio_num}".strip()

    return ""


def evaluar_texto(texto_normalizado, reglas):
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
            
            # SI ES LIQUIDACIÓN, EXTRAER MES Y AÑO DINÁMICAMENTE
            if resultado_base == "LIQUIDACIONES DE SUELDO":
                mes_anio = extraer_mes_anio(texto_normalizado)
                if mes_anio:
                    return f"LIQUIDACIONES DE SUELDO {mes_anio}"

            return resultado_base

    return None


def extraer_texto_pdf(ruta_archivo):
    texto = ""
    try:
        with pdfplumber.open(ruta_archivo) as pdf:
            for pagina in pdf.pages[:3]:
                contenido = pagina.extract_text()
                if contenido:
                    texto += contenido + "\n"
    except Exception as e:
        print(f"  [PDF Error] {ruta_archivo}: {e}")
    return texto


def extraer_texto_imagen(ruta_archivo):
    try:
        imagen = Image.open(ruta_archivo)
        texto = pytesseract.image_to_string(imagen, lang='spa+eng')
        return texto
    except Exception as e:
        print(f"  [OCR Error] {ruta_archivo}: {e}")
        return ""


def procesar_archivos(carpeta):
    if not os.path.exists(carpeta):
        print(f"La carpeta '{carpeta}' no existe.")
        return

    extensiones_permitidas = {".pdf", ".jpg", ".jpeg", ".png"}

    for nombre_archivo in os.listdir(carpeta):
        ruta_completa = os.path.join(carpeta, nombre_archivo)

        if os.path.isdir(ruta_completa) or nombre_archivo.endswith('.py'):
            continue

        ext_original = os.path.splitext(nombre_archivo)[1].lower()
        if ext_original not in extensiones_permitidas:
            continue

        print(f"Analizando: {nombre_archivo}...")

        texto_crudo = ""
        if ext_original == ".pdf":
            texto_crudo = extraer_texto_pdf(ruta_completa)
        else:
            texto_crudo = extraer_texto_imagen(ruta_completa)

        texto_a_evaluar = f"{nombre_archivo} {texto_crudo}"
        texto_normalizado = normalizar_texto(texto_a_evaluar)

        nombre_resultado = evaluar_texto(texto_normalizado, REGLAS_N8N)

        if nombre_resultado:
            nombre_limpio = nombre_resultado.replace("_", " ")
            nuevo_nombre_base = nombre_limpio
            nuevo_nombre = f"{nuevo_nombre_base}{ext_original}"
            nueva_ruta = os.path.join(carpeta, nuevo_nombre)

            contador = 1
            while os.path.exists(nueva_ruta) and nueva_ruta != ruta_completa:
                nuevo_nombre = f"{nuevo_nombre_base} ({contador}){ext_original}"
                nueva_ruta = os.path.join(carpeta, nuevo_nombre)
                contador += 1

            if nueva_ruta != ruta_completa:
                os.rename(ruta_completa, nueva_ruta)
                print(f"  [RENOMBRADO] -> {nuevo_nombre}")
            else:
                print("  -> El archivo ya posee el nombre correcto.")
        else:
            print("  -> No se encontró coincidencia en las reglas.")


if __name__ == "__main__":
    procesar_archivos(DIRECTORIO_ENTRADA)