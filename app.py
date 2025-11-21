import json
import os
import random
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
# REMOVIDO: from flask_mail import Mail, Message

app = Flask(__name__)

# ================================
# CONFIGURAÇÕES DE E-MAIL (REMOVIDAS)
# ================================
# As configurações de e-mail foram totalmente removidas.

# ================================
# ARQUIVOS DE DADOS
# ================================
DATA_FILE = "manifestacoes.json"
MATRICULAS_FILE = "matriculas_validas.json"

# ================================
# ADMINISTRAÇÃO - LENDO VARIÁVEIS DE AMBIENTE
# ================================
# **IMPORTANTE:** Estas variáveis serão lidas do Render (ADMIN_USER e ADMIN_PASS).
# O segundo valor ("admin_local" e "1234_local") é um padrão (fallback)
# caso você execute o app localmente sem as variáveis de ambiente.
admin_user = os.environ.get("ADMIN_USER", "admin_local")
admin_pass = os.environ.get("ADMIN_PASS", "1234_local")


# ================================
# FUNÇÕES DE ARQUIVO/MANIPULAÇÃO
# ================================
def carregar_manifestacoes():
    """Carrega a lista de manifestações do arquivo JSON."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # Retorna lista vazia se o arquivo estiver corrompido ou vazio
                return []
    return []

def salvar_manifestacoes(manifestacoes):
    """Salva a lista de manifestações no arquivo JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(manifestacoes, f, indent=4, ensure_ascii=False)

def carregar_matriculas_validas():
    """Carrega a lista de matrículas válidas do arquivo JSON."""
    if os.path.exists(MATRICULAS_FILE):
        with open(MATRICULAS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


# ================================
# FUNÇÕES AUXILIARES
# ================================
def gerar_protocolo():
    return str(random.randint(1000000000, 9999999999))

def validar_matricula(matricula):
    lista = carregar_matriculas_validas()
    return matricula in lista

def enviar_email(protocolo, tipo):
    """Função de e-mail desativada conforme solicitado."""
    print(f"E-mail de notificação (Protocolo {protocolo}, Tipo {tipo}) desativado.")
    pass


# ================================
# ROTAS PRINCIPAIS
# ================================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/registrar', methods=['POST'])
def registrar():
    try:
        nome = request.form.get('nome', 'Anônimo').strip()
        cpf = re.sub(r'[^0-9]', '', request.form.get('cpf', '').strip())
        matricula = re.sub(r'[^0-9]', '', request.form.get('matricula', '').strip())
        tipo = request.form.get('tipo', '').strip()
        descricao = request.form.get('descricao', '').strip()

        # Validações
        if len(cpf) != 11:
            return jsonify({'erro': 'CPF inválido (11 dígitos).'}), 400

        if len(matricula) != 8:
            return jsonify({'erro': 'Matrícula inválida (8 dígitos).'}), 400

        if not validar_matricula(matricula):
            return jsonify({'erro': 'Matrícula não encontrada.'}), 400

        if not tipo or not descricao:
            return jsonify({'erro': 'Preencha todos os campos obrigatórios.'}), 400

        protocolo = gerar_protocolo()
        manifestacoes = carregar_manifestacoes()

        nova = {
            "protocolo": protocolo,
            "nome": nome,
            "cpf": cpf,
            "matricula": matricula,
            "tipo": tipo,
            "descricao": descricao,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "resposta": None # Novo campo para a resposta do admin
        }

        manifestacoes.append(nova)
        salvar_manifestacoes(manifestacoes)

        enviar_email(protocolo, tipo) # A função não faz mais nada

        return jsonify({"protocolo": protocolo})

    except Exception as e:
        print("ERRO:", e)
        return jsonify({"erro": f"Erro ao registrar: {e}"}), 500


@app.route('/consultar', methods=['POST'])
def consultar():
    protocolo = request.form.get('protocolo', '').strip()

    if not protocolo.isdigit():
        return jsonify({'erro': 'Protocolo inválido.'}), 400

    manifestacoes = carregar_manifestacoes()
    for m in manifestacoes:
        if m['protocolo'] == protocolo:
            return jsonify(m)

    return jsonify({'erro': 'Manifestação não encontrada.'}), 404


@app.route('/consultar_cpf', methods=['POST'])
def consultar_cpf():
    cpf = re.sub(r'[^0-9]', '', request.form.get('cpfBusca', '').strip())

    if len(cpf) != 11:
        return jsonify({'erro': 'CPF inválido.'}), 400

    manifestacoes = carregar_manifestacoes()
    resultados = [m for m in manifestacoes if m['cpf'] == cpf]

    return jsonify(resultados)


@app.route('/consultar_matricula', methods=['POST'])
def consultar_matricula():
    matricula = re.sub(r'[^0-9]', '', request.form.get('matriculaBusca', '').strip())

    if len(matricula) != 8:
        return jsonify({'erro': 'Matrícula inválida.'}), 400

    manifestacoes = carregar_manifestacoes()
    resultados = [m for m in manifestacoes if m['matricula'] == matricula]

    return jsonify(resultados)


# ================================
# ADMINISTRAÇÃO
# ================================
@app.route('/admin')
def admin_page():
    return render_template('admin.html')


@app.route('/admin_login', methods=['POST'])
def admin_login():
    usuario = request.form.get('usuarioAdmin')
    senha = request.form.get('senhaAdmin')

    # A partir de agora, verifica as credenciais definidas nas V. de Ambiente do Render
    if usuario == admin_user and senha == admin_pass:
        return jsonify({'redirect': url_for('listar_manifestacoes')})
    else:
        return jsonify({'erro': 'Credenciais inválidas.'}), 401


@app.route('/listar_manifestacoes')
def listar_manifestacoes():
    # A dashboard busca os dados via API, não precisa passar aqui
    return render_template('admin_dashboard.html')


@app.route('/api/manifestacoes')
def api_manifestacoes():
    # Esta API é chamada pelo JavaScript na dashboard
    return jsonify(carregar_manifestacoes())


@app.route('/responder', methods=['POST'])
def responder_manifestacao():
    protocolo = request.form.get('protocolo')
    resposta = request.form.get('resposta')

    if not protocolo or not resposta:
        return jsonify({'erro': 'Campos obrigatórios.'}), 400

    manifestacoes = carregar_manifestacoes()

    for m in manifestacoes:
        if m['protocolo'] == protocolo:
            m['resposta'] = resposta
            salvar_manifestacoes(manifestacoes)
            return jsonify({'mensagem': 'Resposta salva com sucesso.'})

    return jsonify({'erro': 'Protocolo não encontrado.'}), 404


# ================================
# EXECUÇÃO LOCAL (Apenas para testes)
# ================================
if __name__ == '__main__':
    # Se rodar localmente, o login será com admin_local / 1234_local
    app.run(debug=True)
