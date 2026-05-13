import os
import json
import random
import string
import threading
import asyncio
import requests
import time
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
CHECKOUT_API_URL = "https://seu-dominio.com/api_checkout_batch.php"

# Arquivos de dados
USERS_FILE = "users.json"
CODES_FILE = "codes.json"
TRANSACTIONS_FILE = "transactions.json"
PENDING_PIX_FILE = "pending_pix.json"

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
def create_pix_qrcode(amount):
    print(f"[MisticPay] Criando PIX de R$ {amount}")
    
    headers = {
        "ci": CLIENT_ID,
        "cs": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": amount,
        "description": f"Recarga de saldo - R$ {amount:.2f}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/pix/create",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            return {
                "success": True,
                "qr_code": data.get("qr_code") or data.get("qrcode"),
                "copy_paste": data.get("copy_paste") or data.get("brcode"),
                "transaction_id": data.get("id") or data.get("transaction_id"),
                "amount": amount
            }
        else:
            return {"success": False, "error": f"Erro {response.status_code}"}
    except Exception as e:
        print(f"[MisticPay] Erro: {e}")
        return {"success": False, "error": str(e)}

def check_pix_status(transaction_id):
    headers = {"ci": CLIENT_ID, "cs": CLIENT_SECRET}
    try:
        response = requests.get(f"{BASE_URL}/pix/status/{transaction_id}", headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            return status in ["paid", "confirmed"], data
        return False, {}
    except Exception as e:
        return False, {"error": str(e)}

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
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ Uso correto: /pix 10\n\nValor mínimo: R$ 10,00")
        return
    
    try:
        amount = float(context.args[0])
        if amount < 10:
            await update.message.reply_text("❌ Valor mínimo é R$ 10,00")
            return
        
        await update.message.reply_text(f"⏳ Gerando QR Code PIX...\n💰 Valor: R$ {amount:.2f}")
        
        pix_data = create_pix_qrcode(amount)
        
        if not pix_data["success"]:
            await update.message.reply_text(f"❌ Erro ao gerar PIX:\n{pix_data.get('error', 'Erro desconhecido')}")
            return
        
        pending_tx = load_json(PENDING_PIX_FILE)
        pending_tx[pix_data["transaction_id"]] = {
            "user_id": user.id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        save_json(PENDING_PIX_FILE, pending_tx)
        
        message = (
            f"💳 PIX Gerado com Sucesso!\n\n"
            f"💰 Valor: R$ {amount:.2f}\n"
            f"🆔 Transação: {pix_data['transaction_id']}\n\n"
            f"📱 Código PIX (Copia e Cola):\n{pix_data['copy_paste']}\n\n"
            f"⏰ O QR Code expira em 30 minutos"
        )
        
        try:
            img = qrcode.make(pix_data["copy_paste"])
            bio = BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            await update.message.reply_photo(photo=bio, caption=message)
        except:
            await update.message.reply_text(message)
        
        asyncio.create_task(check_pix_payment(pix_data["transaction_id"], user.id, amount, context))
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido!")

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

def main():
    print("🤖 Bot iniciando...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("pix", pix_command))
    application.add_handler(CommandHandler("chk", chk_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot pronto!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🌐 Servidor keep-alive rodando na porta 8080")
    time.sleep(2)
    main()
