import logging
import asyncio
import gspread
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from oauth2client.service_account import ServiceAccountCredentials
from aiogram.fsm.storage.memory import MemoryStorage


# Токен бота
TOKEN = "7683024748:AAFMr0LajbNAvuwP0P4M7Saa8zuF5J6_AyQ"

# Настройка Google Sheets API
SHEET_NAME = "Баланс пользователей"
CREDENTIALS_FILE = "credentials.json"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ID групп для заявок
admin_group_deposit = -1002466018405
admin_group_withdraw = -1002374951392
admin_group_support = -1002471642873

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Настройка клавиатуры
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Recharger le dépôt"), KeyboardButton(text="📤 Retirer des fonds")],
        [KeyboardButton(text="💳 Solde"), KeyboardButton(text="📞 Contactez l'administrateur")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


payment_methods_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Revolut"), KeyboardButton(text="Wise")],
        [KeyboardButton(text="Virement bancaire"), KeyboardButton(text="Skrill")],
        [KeyboardButton(text="Paypal")]
    ],
    resize_keyboard=True
)

# Создаем состояния
class DepositState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_method = State()

class WithdrawState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_method = State()

class SupportState(StatesGroup):
    waiting_for_reason = State()

# Создаем роутер
router = Router()
dp.include_router(router)


@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Bonjour ! Choisissez une action :", reply_markup=main_kb)

# Связь с администратором
@router.message(F.text == "📞 Contactez l'administrateur")
async def contact_admin(message: types.Message, state: FSMContext):
    await message.answer("✏️ Veuillez décrire votre problème et inclure votre @username.")
    await state.set_state(SupportState.waiting_for_reason)

@router.message(SupportState.waiting_for_reason)
async def send_admin_request(message: types.Message, state: FSMContext):
    if not message.from_user.username:
        await message.answer("❌ Vous devez avoir un @username pour contacter l'administrateur.")
        return
    
    support_message = (
        f"📩 Nouvelle demande de support 📩\n"
        f"👤 Utilisateur : @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"📝 Raison : {message.text}"
    )
    
    await bot.send_message(admin_group_support, support_message)
    await message.answer("✅ Votre demande a été envoyée à l'administrateur.")
    await state.clear()

# Запрос на пополнение депозита
@router.message(F.text == "💰 Recharger le dépôt")
async def deposit_request(message: types.Message, state: FSMContext):
    await message.answer("💵 Veuillez entrer le montant (minimum 10 EUR, sans centimes) :")
    await state.set_state(DepositState.waiting_for_amount)

@router.message(DepositState.waiting_for_amount)
async def choose_deposit_payment_method(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 10:
        await message.answer("❌ Veuillez entrer un montant valide (minimum 10 EUR, sans centimes)")
        return
    
    await state.update_data(amount=message.text)
    await message.answer("💳 Choisissez un mode de paiement :", reply_markup=payment_methods_kb)
    await state.set_state(DepositState.waiting_for_payment_method)

@router.message(DepositState.waiting_for_payment_method)
async def confirm_deposit(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    deposit_request_text = (
        f"🔔 Nouvelle demande de dépôt 🔔\n"
        f"👤 Utilisateur : @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"💰 Montant : {user_data['amount']} EUR\n"
        f"💳 Méthode de paiement : {message.text}\n"
        "\n📌 Règles de paiement :\n"
        "1️⃣ Après réception des coordonnées, vous avez 15 minutes pour effectuer le paiement.\n"
        "2️⃣ Après paiement, envoyez une capture d'écran ou un fichier PDF de confirmation.\n"
        "3️⃣ Envoyez exactement le montant indiqué. En cas de modification, remplissez une nouvelle demande."
    )
    
    await bot.send_message(admin_group_deposit, deposit_request_text)
    await message.answer("✅ Votre demande a été acceptée. Un administrateur vous contactera bientôt.")
    await state.clear()


# Запрос на вывод средств
@router.message(F.text == "📤 Retirer des fonds")
async def withdraw_request(message: types.Message, state: FSMContext):
    await message.answer("💵 Veuillez entrer le montant que vous souhaitez retirer (minimum 10 EUR) :")
    await state.set_state(WithdrawState.waiting_for_amount)

@router.message(WithdrawState.waiting_for_amount)
async def choose_withdraw_payment_method(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 10:
        await message.answer("❌ Veuillez entrer un montant valide (minimum 10 EUR, sans centimes)")
        return
    
    await state.update_data(amount=message.text)
    await message.answer("💳 Choisissez un mode de paiement :", reply_markup=payment_methods_kb)
    await state.set_state(WithdrawState.waiting_for_payment_method)

@router.message(WithdrawState.waiting_for_payment_method)
async def confirm_withdraw(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    withdraw_request_text = (
        f"🔔 Nouvelle demande de retrait 🔔\n"
        f"👤 Utilisateur : @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"💰 Montant : {user_data['amount']} EUR\n"
        f"💳 Méthode de paiement : {message.text}\n"
        "\n📌 Règles de retrait :\n"
        "1️⃣ Restez disponible pendant 30 minutes après la demande.\n"
        "2️⃣ Après réception du paiement, envoyez une capture d'écran de confirmation.\n"
        "3️⃣ Vous êtes responsable des coordonnées fournies."
    )
    
    await bot.send_message(admin_group_withdraw, withdraw_request_text)
    await message.answer("✅ Votre demande a été acceptée. Un administrateur vous contactera bientôt.")
    await state.clear()

# Баланс
@router.message(F.text == "💳 Solde")
async def check_balance(message: types.Message):
    user_id = str(message.from_user.id)
    try:
        full_table = sheet.get_all_values()
        headers = full_table[0]
        records = [dict(zip(headers, row)) for row in full_table[1:] if any(row)]
        user_data = next((row for row in records if str(row.get('ID', '')).strip() == user_id), None)
        if user_data:
            balance_message = (
                f"💳 Votre solde : {user_data.get('Баланс', 'N/A')} EUR\n"
                f"📅 Date du dernier dépôt : {user_data.get('Дата поплнения', 'N/A')}\n"
                f"⏳ Retrait disponible à partir du : {user_data.get('Вывод будет доступен', 'N/A')}"
            )
            await message.answer(balance_message)
        else:
            await message.answer("❌ Vous n'avez pas encore de solde enregistré.")
    except Exception as e:
        logging.error(f"🚨 Erreur lors de la récupération du solde: {e}")
        await message.answer("⚠ Une erreur s'est produite lors de la récupération de votre solde.")


# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

