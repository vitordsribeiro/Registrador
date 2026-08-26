from flask import Flask, render_template, jsonify
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from collections import defaultdict

app = Flask(__name__)

SPREADSHEET_ID = "16C_b6OELaSHVB9q-mxJ4jiMEdwEmlr_mxZqk_rN3On4"
SHEET_NAME = "Registros"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

import json
import os

def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def get_all_records():
    sheet = get_sheet()
    return sheet.get_all_values()[1:]  # pula o cabeçalho

def get_today_str():
    return date.today().strftime("%Y-%m-%d")

def get_status_hoje():
    """Decide se o próximo clique é 'inicio' ou 'fim' e retorna o contador do dia."""
    records = get_all_records()
    hoje = get_today_str()
    registros_hoje = [r for r in records if r[0] == hoje]

    contador = len(registros_hoje)
    if not registros_hoje or registros_hoje[-1][2] == "fim":
        proximo_tipo = "inicio"
    else:
        proximo_tipo = "fim"

    return proximo_tipo, contador

def calcular_medias():
    """Calcula duração de cada sessão (inicio->fim) agrupada por dia, e a média geral."""
    records = get_all_records()
    sessoes_por_dia = defaultdict(list)
    inicio_pendente = {}

    for data, hora, tipo in records:
        if tipo == "inicio":
            inicio_pendente[data] = hora
        elif tipo == "fim" and data in inicio_pendente:
            fmt = "%H:%M:%S"
            t_inicio = datetime.strptime(inicio_pendente[data], fmt)
            t_fim = datetime.strptime(hora, fmt)
            duracao = (t_fim - t_inicio).total_seconds()
            if duracao > 0:
                sessoes_por_dia[data].append(duracao)
            del inicio_pendente[data]

    medias_por_dia = {
        d: sum(s) / len(s) for d, s in sessoes_por_dia.items()
    }
    todas_duracoes = [dur for sessoes in sessoes_por_dia.values() for dur in sessoes]
    media_geral = sum(todas_duracoes) / len(todas_duracoes) if todas_duracoes else 0

    return medias_por_dia, media_geral

def segundos_para_hms(segundos):
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

@app.route("/")
def index():
    proximo_tipo, contador = get_status_hoje()
    return render_template("index.html", proximo_tipo=proximo_tipo, contador=contador)

@app.route("/registrar", methods=["POST"])
def registrar():
    sheet = get_sheet()
    proximo_tipo, _ = get_status_hoje()
    agora = datetime.now()
    sheet.append_row([
        agora.strftime("%Y-%m-%d"),
        agora.strftime("%H:%M:%S"),
        proximo_tipo
    ])
    novo_tipo, contador = get_status_hoje()
    return jsonify({
        "tipo_registrado": proximo_tipo,
        "proximo_tipo": novo_tipo,
        "contador": contador
    })

@app.route("/api/media")
def api_media():
    medias_por_dia, media_geral = calcular_medias()
    historico = [
        {"data": d, "media": segundos_para_hms(v)}
        for d, v in sorted(medias_por_dia.items(), reverse=True)
    ]
    return jsonify({
        "media_geral": segundos_para_hms(media_geral),
        "historico": historico
    })

if __name__ == "__main__":
    app.run(debug=True)