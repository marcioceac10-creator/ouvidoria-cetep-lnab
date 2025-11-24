import json
import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, session

app = Flask(__name__)
# LENDO DA VARIÁVEL DE AMBIENTE: FLASK_SECRET_KEY
# Se a variável não for definida, ele usa um valor padrão (fallback).
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'chave_de_fallback_padrao_mude_isso') 

# Arquivos de dados
MANIFESTACOES_FILE = 'manifestacoes.json'
MATRICULAS_FILE = 'matriculas_validas.json'
ADMIN_CREDS_FILE = 'admin_creds.json'

# --- CONFIGURAÇÃO DE E-MAIL (AGORA LIDA DAS VARIÁVEIS DE AMBIENTE NO RENDER) ---
# LENDO DA VARIÁVEL DE AMBIENTE: SENDER_EMAIL
SENDER_EMAIL = os.getenv('SENDER_EMAIL') 
# LENDO DA VARIÁVEL DE AMBIENTE: EMAIL_PASSWORD (DEVE SER A SENHA DE APP DO GMAIL)
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD') 
# LENDO DA VARIÁVEL DE AMBIENTE: ADMIN_EMAIL
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL') 
# 3. O e-mail do MANIFESTANTE é coletado no formulário e usado na rota /responder

# --- Funções de Ajuda ---

def carregar_dados(filepath):
    """Carrega dados de um arquivo JSON. Se o arquivo não existir, retorna uma lista vazia."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Tenta ler o conteúdo; se estiver vazio, retorna lista vazia.
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        # Se houver erro de decodificação JSON, retorna lista vazia e imprime erro (para debug)
        print(f"Erro ao decodificar JSON em {filepath}. Retornando lista vazia.")
        return []
    except Exception as e:
        print(f"Erro inesperado ao carregar dados de {filepath}: {e}")
        return []

def salvar_dados(filepath, data):
    """Salva dados em um arquivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar dados em {filepath}: {e}")

def gerar_protocolo():
    """Gera um número de protocolo único e curto."""
    # Gera um número de 6 dígitos
    return str(random.randint(100000, 999999))

def enviar_email(destinatario, assunto, corpo):
    """Envia um email de notificação usando o SENDER_EMAIL."""
    # Garante que as configurações essenciais para o envio estejam presentes
    if not destinatario or not SENDER_EMAIL or not EMAIL_PASSWORD:
        print("Aviso: Configurações de e-mail incompletas (Destinatário, Remetente ou Senha). E-mail não enviado.")
        return False
    
    try:
        msg = MIMEText(corpo, 'html')
        msg['Subject'] = assunto
        msg['From'] = SENDER_EMAIL
        msg['To'] = destinatario

        # Conexão com o servidor SMTP do Gmail
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, destinatario, msg.as_string())
        
        print(f"E-mail enviado com sucesso para {destinatario}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERRO DE AUTENTICAÇÃO SMTP: Verifique se o SENDER_EMAIL e a Senha de App estão corretos.")
        return False
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

# --- Rotas Públicas ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registrar', methods=['POST'])
def registrar_manifestacao():
    dados = request.form.to_dict()
    
    # Validação da matrícula
    matriculas_validas = carregar_dados(MATRICULAS_FILE)
    matricula = dados.get('matricula', '').strip()
    
    if matricula and matricula not in matriculas_validas:
        return jsonify({'erro': 'Matrícula inválida. Verifique se digitou os 8 números corretamente.'}), 400

    # Sanitiza CPF e Matrícula (apenas números)
    cpf_sanitizado = dados.get('cpf', '').replace(' ', '').replace('-', '').replace('.', '')
    matricula_sanitizada = matricula.replace(' ', '')

    # Cria o novo registro
    protocolo = gerar_protocolo()
    nova_manifestacao = {
        'protocolo': protocolo,
        'nome': dados.get('nome', '').strip() or 'Anônimo',
        'cpf': cpf_sanitizado,
        'matricula': matricula_sanitizada,
        'email': dados.get('email', '').strip(), # E-mail do Manifestante
        'tipo': dados['tipo'],
        'descricao': dados['descricao'],
        'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'resposta': None 
    }

    manifestacoes = carregar_dados(MANIFESTACOES_FILE)
    manifestacoes.append(nova_manifestacao)
    salvar_dados(MANIFESTACOES_FILE, manifestacoes)

    # =================================================================
    # PASSO 1: Notificação do Administrador (Nova Manifestação)
    # O ADMIN_EMAIL é lido da variável de ambiente.
    # =================================================================
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
    # Envia para o ADMIN_EMAIL (variável de ambiente)
    enviar_email(ADMIN_EMAIL, assunto_admin, corpo_admin) 
    # =================================================================
    
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

# --- Rotas Admin ---

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
            # Captura o email do manifestante registrado
            manifestante_email = m.get('email') 
            encontrado = True
            break
            
    if encontrado:
        salvar_dados(MANIFESTACOES_FILE, manifestacoes)
        
        # =================================================================
        # PASSO 2: Notificação do Manifestante (Resposta)
        # O SENDER_EMAIL e EMAIL_PASSWORD são lidos das variáveis de ambiente.
        # =================================================================
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
            # Envia para o email do manifestante
            enviar_email(manifestante_email, assunto, corpo)
        # =================================================================

        return jsonify({'mensagem': 'Resposta salva com sucesso e notificação enviada.'})
    
    return jsonify({'erro': 'Protocolo não encontrado para responder.'}), 404

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logado', None)
    return redirect(url_for('index'))

@app.route('/limpar_respondidas', methods=['POST'])
def limpar_respondidas():
    """Remove permanentemente do arquivo todas as manifestações que já possuem uma resposta."""
    if not session.get('admin_logado'):
        return jsonify({'erro': 'Não autorizado'}), 401

    try:
        manifestacoes_atuais = carregar_dados(MANIFESTACOES_FILE)
        
        # Filtra: mantém APENAS as manifestações onde 'resposta' é None (Aguardando Resposta)
        manifestacoes_pendentes = [m for m in manifestacoes_atuais if m['resposta'] is None]
        
        # Calcula quantas foram removidas
        removidas_count = len(manifestacoes_atuais) - len(manifestacoes_pendentes)
        
        # Salva o novo array (apenas pendentes) no arquivo
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
    # Cria os arquivos se não existirem
    if not os.path.exists(MANIFESTACOES_FILE):
        salvar_dados(MANIFESTACOES_FILE, [])
    if not os.path.exists(MATRICULAS_FILE):
        # Exemplo de matrículas válidas (apenas para teste)
        salvar_dados(MATRICULAS_FILE, ["12345678", "87654321"])
    if not os.path.exists(ADMIN_CREDS_FILE):
        # Credenciais de admin padrão
        salvar_dados(ADMIN_CREDS_FILE, [{"usuario": "admin", "senha": "123"}])

    app.run(debug=True)
