
from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests
import hashlib
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor
import threading
import time

app = Flask(__name__)

# Configuración de la API SMS
apiaccount = "cs_hd6xbr"
apipassword = "iXwRbB96"
senderid = "teddy"
url = "http://sms.yx19999.com:20003/sendsmsV2"
max_sms_per_second = 5.0

# Control de tráfico
rate_limit_lock = threading.Semaphore(int(max_sms_per_second))
rate_interval = 1 / max_sms_per_second

def generar_sign(apiaccount, apipassword):
    zona = pytz.timezone("Asia/Shanghai")
    ahora = datetime.now(zona).strftime('%Y%m%d%H%M%S')
    texto = apiaccount + apipassword + ahora
    sign = hashlib.md5(texto.encode()).hexdigest()
    return sign, ahora

def enviar_sms(numero, deuda, mensaje_template):
    mensaje = mensaje_template.replace("{numero}", numero).replace("{deuda}", deuda)
    with rate_limit_lock:
        sign, fecha_actual = generar_sign(apiaccount, apipassword)
        params = {
            "account": apiaccount,
            "sign": sign,
            "datetime": fecha_actual
        }
        data = {
            "senderid": senderid,
            "numbers": "57" + numero,
            "content": mensaje
        }
        try:
            response = requests.post(url, params=params, json=data, timeout=10)
            print("Enviado a", numero, "=>", response.text)
            return True
        except Exception as e:
            print("Error:", e)
            return False
        finally:
            time.sleep(rate_interval)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/enviar", methods=["POST"])
def enviar():
    archivo = request.files["archivo"]
    mensaje = request.form["mensaje"]
    filename = archivo.filename.lower()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(archivo, dtype=str)
        elif filename.endswith(".txt"):
            df = pd.read_csv(archivo, sep="\t|,", engine="python", dtype=str)
        else:
            return jsonify({"status": "error", "message": "Formato de archivo no soportado."})

        if "numero" not in df.columns or "deuda" not in df.columns:
            return jsonify({"status": "error", "message": "Faltan columnas 'numero' y/o 'deuda'."})

        enviados = 0
        total = len(df)
        resultados = []

        def procesar():
            nonlocal enviados
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for _, row in df.iterrows():
                    numero = row["numero"].strip()
                    deuda = row["deuda"].strip()
                    future = executor.submit(enviar_sms, numero, deuda, mensaje)
                    futures.append(future)

                for future in futures:
                    if future.result():
                        enviados += 1

        procesar()
        return jsonify({"status": "ok", "enviados": enviados, "total": total})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
