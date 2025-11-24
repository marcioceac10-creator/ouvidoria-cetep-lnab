import json
import os
import random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'chave_de_fallback_padrao_mude_isso') 

MANIFESTACOES_FILE = 'manifestacoes.json'
MATRICULAS_FILE = 'matriculas_validas.json'
ADMIN_CREDS_FILE = 'admin_creds.json'

SENDER_EMAIL = os.getenv('SENDER_EMAIL') 
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL') 
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY') 

def carregar_dados(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON em {filepath}. Retornando lista vazia.")
        return []
    except Exception as e:
        print(f"Erro inesperado ao carregar dados de {filepath}: {e}")
        return []

def salvar_dados(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar dados em {filepath}: {e}")

def gerar_protocolo():
    return str(random.randint(100000, 999999))

def enviar_email(destinatario, assunto, corpo):
    if not destinatario or not SENDER_EMAIL or not SENDGRID_API_KEY:
        print("Aviso: Configurações de e-mail incompletas. E-mail não enviado.")
        return False
    
    try:
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=destinatario,
            subject=assunto,
            html_content=corpo
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code == 202:
            print(f"E-mail enviado via SendGrid com sucesso para {destinatario}")
            return True
        else:
            print(f"Erro ao enviar e-mail (SendGrid Status {response.status_code}): {response.body}")
            return False

    except Exception as e:
        print(f"Erro ao enviar email via SendGrid: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registrar', methods=['POST'])
def registrar_manifestacao():
    dados = request.form.to_dict()
    
    matriculas_validas = carregar_dados(MATRICULAS_FILE)
    matricula = dados.get('matricula', '').strip()
    
    if matricula and matricula not in matriculas_validas:
        return jsonify({'erro': 'Matrícula inválida. Verifique se digitou os 8 números corretamente.'}), 400

    cpf_sanitizado = dados.get('cpf', '').replace(' ', '').replace('-', '').replace('.', '')
    matricula_sanitizada = matricula.replace(' ', '')

    protocolo = gerar_protocolo()
    nova_manifestacao = {
        'protocolo': protocolo,
        'nome': dados.get('nome', '').strip() or 'Anônimo',
        'cpf': cpf_sanitizado,
        'matricula': matricula_sanitizada,
        'email': dados.get('email', '').strip(),
        'tipo': dados['tipo'],
        'descricao': dados['descricao'],
        'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'resposta': None 
    }

    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    manifestacoes.append(nova_manifestacao)
    salvar_dados(MANIFESTACOES_FILE, manifestacoes)

    assunto_admin = f"NOVA MANIFESTAÇÃO REGISTRADA - Protocolo {protocolo}"
    corpo_admin = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>Uma nova manifestação foi registrada na Ouvidoria!</h2>
        <p><strong>Protocolo:</strong> {protocolo}</p>
        <p><strong>Tipo:</strong> {nova_manifestacao['tipo'].capitalize()}</p>
        <p><strong>Nome:</strong> {nova_manifestacao['nome']}</p>
        <p><strong>Matrícula:</strong> {nova_manifestacao['matricula'] or 'N/A'}</p>
        
        <h3 style="color: #007bff;">Descrição:</h3>
        <div style="border: 1px solid #ccc; padding: 15px; border-radius: 5px; background-color: #f9f9f9;">
            <p>{nova_manifestacao['descricao'].replace('\n', '<br>')}</p>
        </div>
        
        <p>Acesse o painel administrativo para visualizar e responder.</p>
        <p>Atenciosamente,<br>Sistema de Ouvidoria</p>
    </body>
    </html>
    """
    enviar_email(ADMIN_EMAIL, assunto_admin, corpo_admin) 
    
    return jsonify({'mensagem': 'Manifestação registrada com sucesso', 'protocolo': protocolo})

@app.route('/consultar', methods=['POST'])
def consultar_protocolo():
    protocolo = request.form.get('protocolo')
    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    
    for m in manifestacoes:
        if m['protocolo'] == protocolo:
            return jsonify(m)
    
    return jsonify({'erro': 'Protocolo não encontrado.'}), 404

@app.route('/consultar_cpf', methods=['POST'])
def consultar_cpf():
    cpf = request.form.get('cpfBusca', '').replace(' ', '').replace('-', '').replace('.', '')
    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    
    resultados = [m for m in manifestacoes if m['cpf'] == cpf]
    
    if resultados:
        return jsonify(resultados)
    
    return jsonify({'erro': 'Nenhuma manifestação encontrada para este CPF.'}), 404

@app.route('/consultar_matricula', methods=['POST'])
def consultar_matricula():
    matricula = request.form.get('matriculaBusca', '').replace(' ', '')
    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    
    resultados = [m for m in manifestacoes if m['matricula'] == matricula]
    
    if resultados:
        return jsonify(resultados)
    
    return jsonify({'erro': 'Nenhuma manifestação encontrada para esta Matrícula.'}), 404

@app.route('/admin_login')
def admin_login():
    return render_template('admin.html') 

@app.route('/admin_login', methods=['POST'])
def admin_autenticar():
    usuario = request.form.get('usuarioAdmin')
    senha = request.form.get('senhaAdmin')
    
    admin_creds = carregar_dados(ADMIN_CREDS_FILE)
    
    if any(cred['usuario'] == usuario and cred['senha'] == senha for cred in admin_creds):
        session['admin_logado'] = True
        return jsonify({'redirect': url_for('admin_dashboard')})
    
    return jsonify({'erro': 'Credenciais inválidas'}), 401

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logado'):
        return redirect(url_for('admin_login'))

    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    return render_template('admin_dashboard.html', manifestacoes=manifestacoes)

@app.route('/responder', methods=['POST'])
def responder_manifestacao():
    if not session.get('admin_logado'):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    protocolo = request.form.get('protocolo')
    resposta = request.form.get('resposta')
    
    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    encontrado = False
    manifestante_email = None
    m = None 

    for item in manifestacoes:
        if item['protocolo'] == protocolo:
            m = item 
            m['resposta'] = resposta
            manifestante_email = m.get('email') 
            encontrado = True
            break
            
    if encontrado:
        salvar_dados(MANIFESTACOES_FILE, manifestacoes)
        
        if manifestante_email and m: 
            assunto = f"Ouvidoria CETEP LNAB - Resposta ao Protocolo {protocolo}"
            corpo = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2>Sua manifestação foi respondida!</h2>
                <p><strong>Protocolo:</strong> {protocolo}</p>
                <p><strong>Tipo:</strong> {m['tipo'].capitalize()}</p>
                <p><strong>Descrição original:</strong> {m['descricao']}</p>
                
                <h3 style="color: #007bff;">Resposta da Ouvidoria:</h3>
                <div style="border: 1px solid #ccc; padding: 15px; border-radius: 5px; background-color: #f9f9f9;">
                    <p>{resposta.replace('\n', '<br>')}</p>
                </div>
                
                <p>Agradecemos seu contato.</p>
                <p>Atenciosamente,<br>Ouvidoria CETEP LNAB</p>
            </body>
            </html>
            """
            enviar_email(manifestante_email, assunto, corpo)

        return jsonify({'mensagem': 'Resposta salva com sucesso e notificação enviada.'})
    
    return jsonify({'erro': 'Protocolo não encontrado para responder.'}), 404

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logado', None)
    return redirect(url_for('index'))

@app.route('/limpar_respondidas', methods=['POST'])
def limpar_respondidas():
    if not session.get('admin_logado'):
        return jsonify({'erro': 'Não autorizado'}), 401

    try:
        manifestacoes_atuais = carregar_dados(MANIFESTACOES_FILE)
        
        manifestacoes_pendentes = [m for m in manifestacoes_atuais if m['resposta'] is None]
        
        removidas_count = len(manifestacoes_atuais) - len(manifestacoes_pendentes)
        
        salvar_dados(MANIFESTACOES_FILE, manifestacoes_pendentes)
        
        return jsonify({
            'mensagem': f'{removidas_count} manifestações respondidas foram removidas com sucesso.',
            'removidas': removidas_count,
            'pendentes': len(manifestacoes_pendentes)
        })
    except Exception as e:
        print(f"Erro ao processar a limpeza de manifestações: {e}")
        return jsonify({'erro': 'Erro interno ao limpar manifestações.'}), 500

if __name__ == '__main__':
    if not os.path.exists(MANIFESTACOES_FILE):
        salvar_dados(MANIFESTACOES_FILE, [])
    if not os.path.exists(MATRICULAS_FILE):
        salvar_dados(MATRICULAS_FILE, ["12345678", "87654321"])
    if not os.path.exists(ADMIN_CREDS_FILE):
        salvar_dados(ADMIN_CREDS_FILE, [{"usuario": "admin", "senha": "123"}])

    app.run(debug=True)
