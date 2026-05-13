import os
import json
import random
import string
from flask import Flask, jsonify
import threading
import asyncio
import requests
import time
import qrcode
from io import BytesIO
from datetime import datetime
import asyncio

# Importações corretas para python-telegram-bot v20+
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========= CONFIGURAÇÕES =========
TELEGRAM_TOKEN = "8749925154:AAEJWRD7IGpULIvncMyDk-jusu5iPL6WJHE"
ADMIN_ID = 8467946444  # Coloque seu ID do Telegram aqui

# Configurações MisticPay
CLIENT_ID = "ci_libdweclsjyry50"
CLIENT_SECRET = "cs_kknlfy76fe2ir4nqjydf8ebee"
AUTH_URL = "https://api.misticpay.com/v1/oauth/token"
PIX_URL = "https://api.misticpay.com/v1/pix"

# URLs da sua API de checkout
CHECKOUT_API_URL = "http://localhost:8000/api.php"

# Arquivos de dados
USERS_FILE = "users.json"
CODES_FILE = "codes.json"
TRANSACTIONS_FILE = "transactions.json"
PENDING_PIX_FILE = "pending_pix.json"

# Cache do token
token_cache = {
    "access_token": None,
    "expires_at": 0
}

# ========= FUNÇÕES AUXILIARES =========
def load_json(file_path):
    """Carrega dados de um arquivo JSON"""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(file_path, data):
    """Salva dados em um arquivo JSON"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def init_user(user_id, username, first_name):
    """Inicializa um novo usuário"""
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
    """Atualiza o saldo do usuário e registra transação"""
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return False
    
    users[user_id_str]["balance"] += amount
    users[user_id_str]["last_activity"] = datetime.now().isoformat()
    save_json(USERS_FILE, users)
    
    # Registrar transação
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
    """Gera um código aleatório"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def check_card(card_data):
    """Verifica um cartão via API"""
    try:
        response = requests.get(
            CHECKOUT_API_URL,
            params={"lista": card_data},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('status') == 'LIVE', result
        return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}

# ========= FUNÇÕES MISTICPAY =========
def get_access_token():
    """Obtém um novo token usando Client ID e Secret"""
    global token_cache
    
    # Se o token ainda estiver válido, reaproveita
    if token_cache["access_token"] and token_cache["expires_at"] > time.time():
        return token_cache["access_token"]
    
    # Solicita novo token
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    try:
        response = requests.post(AUTH_URL, data=data, headers=headers, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        
        token_cache["access_token"] = access_token
        token_cache["expires_at"] = time.time() + expires_in
        
        return access_token
        
    except Exception as e:
        print(f"Erro na autenticação MisticPay: {e}")
        return None

def create_pix_qrcode(amount):
    """Gera QR Code PIX via MisticPay"""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "Falha na autenticação com a MisticPay"}
    
    payload = {
        "amount": amount,
        "description": f"Recarga de saldo - R$ {amount:.2f}",
        "notification_url": "https://seuwebhook.com/pix_callback"  # Configure seu webhook
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(PIX_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code in [200, 201]:
            data = response.json()
            return {
                "success": True,
                "qr_code": data.get("qr_code_image") or data.get("qrCode"),
                "copy_paste": data.get("copy_paste") or data.get("brCode"),
                "transaction_id": data.get("id") or data.get("transactionId"),
                "amount": amount
            }
        else:
            return {"success": False, "error": f"Erro {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_pix_status(transaction_id):
    """Verifica status do PIX"""
    token = get_access_token()
    if not token:
        return False, {"error": "Falha na autenticação"}
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{PIX_URL}/{transaction_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            return status == "paid" or status == "confirmed", data
        return False, {}
    except Exception as e:
        return False, {"error": str(e)}

# ========= COMANDOS DO BOT =========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
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
    
    welcome_message = (
        f"🤖 *Bem-vindo ao Checkout Bot!*\n\n"
        f"👤 *Usuário:* {user.first_name}\n"
        f"💰 *Saldo atual:* R$ {user_data['balance']:.2f}\n"
        f"📊 *Total de verificações:* {user_data['total_checked']}\n\n"
        f"✅ *Live:* {user_data['live_checks']}\n"
        f"❌ *Die:* {user_data['die_checks']}\n\n"
        f"Use os botões abaixo para navegar:"
    )
    
    await update.message.reply_text(
        welcome_message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pix + valor"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "❌ *Uso correto:* `/pix 10`\n\nValor mínimo: R$ 10,00",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = float(context.args[0])
        
        if amount < 10:
            await update.message.reply_text(
                "❌ *Valor mínimo é R$ 10,00*",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text(
            f"⏳ *Gerando QR Code PIX...*\n💰 Valor: R$ {amount:.2f}",
            parse_mode='Markdown'
        )
        
        pix_data = create_pix_qrcode(amount)
        
        if not pix_data["success"]:
            await update.message.reply_text(
                f"❌ *Erro ao gerar PIX:*\n{pix_data.get('error', 'Erro desconhecido')}",
                parse_mode='Markdown'
            )
            return
        
        # Salvar transação pendente
        pending_tx = load_json(PENDING_PIX_FILE)
        pending_tx[pix_data["transaction_id"]] = {
            "user_id": user.id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        save_json(PENDING_PIX_FILE, pending_tx)
        
        message = (
            f"💳 *PIX Gerado com Sucesso!*\n\n"
            f"💰 *Valor:* R$ {amount:.2f}\n"
            f"🆔 *Transação:* `{pix_data['transaction_id']}`\n\n"
            f"📱 *Código PIX (Copia e Cola):*\n"
            f"`{pix_data['copy_paste']}`\n\n"
            f"⏰ *O QR Code expira em 30 minutos*"
        )
        
        # Enviar QR Code
        try:
            if pix_data["qr_code"].startswith("http"):
                await update.message.reply_photo(
                    photo=pix_data["qr_code"],
                    caption=message,
                    parse_mode='Markdown'
                )
            else:
                img = qrcode.make(pix_data["copy_paste"])
                bio = BytesIO()
                img.save(bio, 'PNG')
                bio.seek(0)
                await update.message.reply_photo(
                    photo=bio,
                    caption=message,
                    parse_mode='Markdown'
                )
        except:
            await update.message.reply_text(message, parse_mode='Markdown')
        
        # Iniciar verificação de pagamento
        asyncio.create_task(check_pix_payment(pix_data["transaction_id"], user.id, amount, context))
        
    except ValueError:
        await update.message.reply_text("❌ *Valor inválido!*", parse_mode='Markdown')

async def check_pix_payment(transaction_id, user_id, amount, context):
    """Verifica pagamento PIX em background"""
    await asyncio.sleep(10)
    
    for i in range(36):  # 30 minutos
        paid, _ = check_pix_status(transaction_id)
        
        if paid:
            update_balance(user_id, amount, "pix_recarga", f"PIX {transaction_id}")
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ *Pagamento Confirmado!*\n\n💰 R$ {amount:.2f} adicionados ao saldo!",
                parse_mode='Markdown'
            )
            
            pending = load_json(PENDING_PIX_FILE)
            if transaction_id in pending:
                pending[transaction_id]["status"] = "paid"
                save_json(PENDING_PIX_FILE, pending)
            return
        
        await asyncio.sleep(50)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"⏰ *Tempo esgotado!* O PIX não foi pago.",
        parse_mode='Markdown'
    )

async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /chk + cartão"""
    user = update.effective_user
    user_data = init_user(user.id, user.username, user.first_name)
    
    if not context.args:
        await update.message.reply_text(
            "❌ *Uso:* `/chk NUMERO|MES|ANO|CVV|NOME|CPF`",
            parse_mode='Markdown'
        )
        return
    
    card_data = ' '.join(context.args)
    
    if user_data['balance'] < 0.5:
        await update.message.reply_text(
            f"❌ *Saldo insuficiente!* R$ {user_data['balance']:.2f}",
            parse_mode='Markdown'
        )
        return
    
    msg = await update.message.reply_text("⏳ *Verificando...*", parse_mode='Markdown')
    
    is_live, result = check_card(card_data)
    cost = 1.0 if is_live else 0.5
    
    update_balance(user.id, -cost, "check", f"Resultado: {'LIVE' if is_live else 'DIE'}")
    
    # Atualizar estatísticas
    users = load_json(USERS_FILE)
    user_id_str = str(user.id)
    users[user_id_str]['total_checked'] += 1
    if is_live:
        users[user_id_str]['live_checks'] += 1
    else:
        users[user_id_str]['die_checks'] += 1
    users[user_id_str]['balance'] -= cost
    save_json(USERS_FILE, users)
    
    status_text = "✅ *LIVE*" if is_live else "❌ *DIE*"
    
    await msg.edit_text(
        f"{status_text}\n\n"
        f"💰 Custo: R$ {cost:.2f}\n"
        f"💵 Saldo: R$ {users[user_id_str]['balance']:.2f}",
        parse_mode='Markdown'
    )

async def mchk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mchk com arquivo"""
    user = update.effective_user
    
    if not update.message.document:
        await update.message.reply_text(
            "❌ *Envie um arquivo .txt junto com o comando*",
            parse_mode='Markdown'
        )
        return
    
    file = await update.message.document.get_file()
    file_path = f"temp_{user.id}_{int(time.time())}.txt"
    await file.download_to_drive(file_path)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        cards = [line.strip() for line in f if line.strip()]
    
    os.remove(file_path)
    
    if not cards:
        await update.message.reply_text("❌ Arquivo vazio!")
        return
    
    user_data = init_user(user.id, user.username, user.first_name)
    
    if user_data['balance'] < 0.5:
        await update.message.reply_text(f"❌ Saldo insuficiente! R$ {user_data['balance']:.2f}")
        return
    
    msg = await update.message.reply_text(
        f"📁 Processando {len(cards)} cartões...\n💰 Saldo: R$ {user_data['balance']:.2f}",
        parse_mode='Markdown'
    )
    
    live_cards = []
    processed = 0
    
    for i, card in enumerate(cards):
        current_user = load_json(USERS_FILE).get(str(user.id), {})
        if current_user.get('balance', 0) < 0.5:
            break
        
        is_live, _ = check_card(card)
        cost = 1.0 if is_live else 0.5
        
        update_balance(user.id, -cost, "bulk_check", f"Cartão {i+1}")
        
        if is_live:
            live_cards.append(card)
        
        processed += 1
        
        if (i + 1) % 10 == 0:
            await msg.edit_text(
                f"📊 Progresso: {processed}/{len(cards)}\n✅ Live: {len(live_cards)}\n"
                f"💰 Saldo: R$ {current_user.get('balance', 0):.2f}",
                parse_mode='Markdown'
            )
        
        await asyncio.sleep(0.5)
    
    if live_cards:
        output_file = f"live_cards_{user.id}_{int(time.time())}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(live_cards))
        
        await update.message.reply_document(
            document=open(output_file, 'rb'),
            filename=f"live_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            caption=f"✅ {len(live_cards)} cartões LIVE encontrados!"
        )
        os.remove(output_file)

async def resgatar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resgatar + codigo"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ *Uso:* `/resgatar CODIGO`", parse_mode='Markdown')
        return
    
    code = context.args[0]
    codes = load_json(CODES_FILE)
    
    if code not in codes:
        await update.message.reply_text("❌ *Código inválido!*", parse_mode='Markdown')
        return
    
    code_data = codes[code]
    
    if code_data.get("used", False):
        await update.message.reply_text("❌ *Código já usado!*", parse_mode='Markdown')
        return
    
    amount = code_data["value"]
    update_balance(user.id, amount, "resgate", f"Código: {code}")
    
    codes[code]["used"] = True
    codes[code]["used_by"] = user.id
    codes[code]["used_at"] = datetime.now().isoformat()
    save_json(CODES_FILE, codes)
    
    await update.message.reply_text(
        f"✅ *Resgatado R$ {amount:.2f}!\n💰 Saldo: R$ {load_json(USERS_FILE)[str(user.id)]['balance']:.2f}",
        parse_mode='Markdown'
    )

async def gerarcod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /gerarcod + valor (APENAS ADMIN)"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ *Acesso negado!*", parse_mode='Markdown')
        return
    
    if not context.args:
        await update.message.reply_text("❌ *Uso:* `/gerarcod 50`", parse_mode='Markdown')
        return
    
    try:
        amount = float(context.args[0])
        code = generate_code(20)
        
        codes = load_json(CODES_FILE)
        codes[code] = {
            "value": amount,
            "created_by": user.id,
            "created_at": datetime.now().isoformat(),
            "used": False
        }
        save_json(CODES_FILE, codes)
        
        await update.message.reply_text(
            f"✅ *Código gerado!*\n💰 Valor: R$ {amount:.2f}\n🎫 `{code}`",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Valor inválido!", parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa botões inline"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_data = init_user(user.id, user.username, user.first_name)
    
    if query.data == "balance":
        await query.edit_message_text(
            f"💰 *Saldo:* R$ {user_data['balance']:.2f}",
            parse_mode='Markdown'
        )
    elif query.data == "stats":
        await query.edit_message_text(
            f"📊 *Estatísticas*\n\n✅ Live: {user_data['live_checks']}\n"
            f"❌ Die: {user_data['die_checks']}\n"
            f"📈 Total: {user_data['total_checked']}",
            parse_mode='Markdown'
        )
    elif query.data == "check":
        await query.edit_message_text(
            f"💳 *Verificar Cartão*\n\n`/chk NUMERO|MES|ANO|CVV|NOME|CPF`",
            parse_mode='Markdown'
        )
    elif query.data == "pix_recharge":
        await query.edit_message_text(
            f"💸 *Recarregar*\n\n`/pix valor`\nMínimo: R$ 10,00",
            parse_mode='Markdown'
        )
    elif query.data == "redeem":
        await query.edit_message_text(
            f"🎫 *Resgatar*\n\n`/resgatar CODIGO`",
            parse_mode='Markdown'
        )

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Endpoint para o UptimeRobot verificar se o bot está vivo"""
    return jsonify({'status': 'alive', 'message': 'Bot funcionando!'}), 200

def run_flask():
    """Roda o servidor Flask em uma thread separada"""
    app.run(host='0.0.0.0', port=8080)

# ========= MAIN =========
def main():
    """Função principal"""
    print("🤖 Bot iniciando...")
    
    # Criar aplicação
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Adicionar handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("pix", pix_command))
    application.add_handler(CommandHandler("chk", chk_command))
    application.add_handler(CommandHandler("mchk", mchk_command))
    application.add_handler(CommandHandler("resgatar", resgatar_command))
    application.add_handler(CommandHandler("gerarcod", gerarcod_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Iniciar bot (apenas uma vez!)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Iniciar Flask em thread separada (KEEP ALIVE)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Iniciar o bot do Telegram
    main()  # ← Chama a função main() apenas uma vez
