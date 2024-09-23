from flask import Flask, render_template, request
import csv
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# Rutas de los archivos itinerario y pedidos
ruta_csv_vuelos_nueva = 'itinerary_int_ag - Hoja 4.csv'
ruta_pedidos = 'pedidos_spml.csv'

# URL del Web App de Google Sheets "solicitudes spml conex" el cual guarda los pedidos dinámicamente
google_sheets_web_app_url = 'https://script.google.com/macros/s/AKfycby3gnYSfCwSfPoKppeRE_VX4qDtRA2NP1D_MsID4024lnFb_YaH5xx4Fyq8PJSMNvQ1/exec'

def obtener_demora_y_verificar(flt_desg, origen, destino):
    try:
        with open(ruta_csv_vuelos_nueva, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                vuelo = row['Flt Desg'].strip().upper()  # Cambiado a 'Flt Desg'
                dept_arp = row['Dept Arp'].strip().upper()  # Columna de aeropuerto de origen
                arvl_arp = row['Arvl Arp'].strip().upper()  # Columna de aeropuerto de destino

                # Verificar coincidencia en número de vuelo, origen y destino
                if vuelo == flt_desg.strip().upper() and dept_arp == origen and arvl_arp == destino:
                    tiempo_demora = row['demora'].strip()
                    try:
                        # Convertir tiempo en formato HH:MM:SS a timedelta
                        horas, minutos, segundos = map(int, tiempo_demora.split(':'))
                        demora = timedelta(hours=horas, minutes=minutos, seconds=segundos)
                        print(f"Vuelo encontrado: {vuelo}, Origen: {dept_arp}, Destino: {arvl_arp}, Demora: {demora}")
                        return demora
                    except ValueError:
                        print(f"Error al convertir el tiempo de demora: {tiempo_demora}")
                        return None
            print(f"No se encontró coincidencia de vuelo, origen y destino para el vuelo {flt_desg}")
            return None
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        return None

def validar_tiempo_salida(fecha_salida):
    ahora = datetime.now()
    fecha_salida_dt = datetime.strptime(fecha_salida, '%Y-%m-%dT%H:%M')
    diferencia = fecha_salida_dt - ahora
    return diferencia >= timedelta(hours=24)

def validar_ruta_vuelo(duracion_vuelo, origen, destino):
    if (origen == "SCL" and destino == "IPC") or (origen == "IPC" and destino == "SCL"):
        return True
    elif duracion_vuelo > timedelta(hours=3, minutes=30):
        return True
    else:
        return False

def pedido_duplicado(rut_dni, flt_desg):
    try:
        with open(ruta_pedidos, mode='r', newline='') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] == rut_dni and row[1] == flt_desg:
                    return row[5]  # Retorna el código de comida si está duplicado
        return None
    except FileNotFoundError:
        return None

def guardar_pedido(rut_dni, flt_desg, fecha_hora_salida, origen, destino, codigo_comida):
    with open(ruta_pedidos, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([rut_dni, flt_desg, fecha_hora_salida, origen, destino, codigo_comida])

    # Enviar datos a Google Sheets
    data = {
        'rut_dni': rut_dni,
        'numero_vuelo': flt_desg,  # Cambiado a 'flt_desg'
        'fecha_salida': fecha_hora_salida,
        'origen': origen,
        'destino': destino,
        'codigo_comida': codigo_comida
    }
    response = requests.post(google_sheets_web_app_url, json=data)
    if response.status_code != 200:
        print("Error al enviar datos a Google Sheets:", response.text)

@app.route('/')
def index():
    return render_template('formulario.html')

@app.route('/procesar_pedido', methods=['POST'])
def procesar_pedido():
    rut_dni = request.form['rut_dni']
    flt_desg = request.form['Flt Desg']  # Cambiado a 'Flt Desg'
    fecha_salida = request.form['fecha_salida']
    origen = request.form['origen'].upper()
    destino = request.form['destino'].upper()
    codigo_comida = request.form['codigo_comida'].upper()

    codigos_validos = ["CHML", "BLML", "DBML", "GFML", "KSML", "LCML", "LFML", "LSML", "NLML", "VGML", "VLML"]

    if codigo_comida not in codigos_validos:
        return render_template('confirmacion.html', rut_dni=rut_dni, numero_vuelo=flt_desg, codigo_comida=codigo_comida, mensaje="Código de comida no válido. Por favor, intente de nuevo.", error=True)

    if not validar_tiempo_salida(fecha_salida):
        return render_template('confirmacion.html', rut_dni=rut_dni, numero_vuelo=flt_desg, codigo_comida=codigo_comida, mensaje="El vuelo está a menos de 24 horas de salida. No se puede procesar el pedido de SPML.", error=True)

    demora = obtener_demora_y_verificar(flt_desg, origen, destino)
    if demora is None:
        return render_template('confirmacion.html', rut_dni=rut_dni, numero_vuelo=flt_desg, codigo_comida=codigo_comida, mensaje="No se pudo obtener la demora del vuelo.", error=True)

    if not validar_ruta_vuelo(demora, origen, destino):
        return render_template('confirmacion.html', rut_dni=rut_dni, numero_vuelo=flt_desg, codigo_comida=codigo_comida, mensaje="Ruta no cumple con los requisitos de duración o es nacional. No se puede procesar el pedido de SPML.", error=True)

    comida_existente = pedido_duplicado(rut_dni, flt_desg)
    if comida_existente:
        return render_template('confirmacion.html', rut_dni=rut_dni, numero_vuelo=flt_desg, codigo_comida=comida_existente, duplicado=True)

    guardar_pedido(rut_dni, flt_desg, fecha_salida, origen, destino, codigo_comida)

    return render_template('confirmacion.html', rut_dni=rut_dni, numero_vuelo=flt_desg, codigo_comida=codigo_comida)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)
