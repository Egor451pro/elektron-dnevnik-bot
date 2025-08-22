import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from urllib.parse import quote
from aiogram.filters.state import StateFilter
import aiosqlite
from urllib.parse import quote, unquote
TOKEN = "7885652871:AAH6JxFq5Ecty7Bx7FDl2vasCbFXjOCT3Mo"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect("dnevnik.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    UNIQUE(user_id, name)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    subject TEXT,
    grade INTEGER
)
""")

conn.commit()

DEFAULT_SUBJECTS = [
    "Белорусский язык", "Белорусская литература", "Русский язык",
    "Русская литература", "Иностранный язык", "Математика",
    "Информатика", "Всемирная история", "История Беларуси",
    "Обществоведение", "География", "Биология", "Физика",
    "Химия", "Трудовое обучение", "Физкультура"
]

class GradeStates(StatesGroup):
    choosing_subject = State()
    choosing_grade = State()
    deleting_grade = State()
    viewing_grades = State()
    calculating_average = State()
    clearing_grades = State()
    confirming_clear = State()  # <-- добавь сюда
    adding_subject = State()
    managing_subjects = State()



def main_menu():
    kb = [
        [InlineKeyboardButton(text=" Добавить оценку", callback_data="add_grade")],
        [InlineKeyboardButton(text=" Удалить оценку", callback_data="delete_grade")],
        [InlineKeyboardButton(text=" Посмотреть все оценки", callback_data="view_grades")],
        [InlineKeyboardButton(text=" Средний балл по предмету", callback_data="average")],
        [InlineKeyboardButton(text=" Средний балл по всем предметам", callback_data="overall_average")],
        [InlineKeyboardButton(text=" Очистить все оценки", callback_data="clear_grades")],
        [InlineKeyboardButton(text=" Управление предметами", callback_data="manage_subjects")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(F.text.lower() == "/start")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    async with aiosqlite.connect("dnevnik.db") as db:
        # Для каждого предмета пытаемся вставить, игнорируя дубликаты
        for subject in DEFAULT_SUBJECTS:
            try:
                await db.execute(
                    "INSERT INTO subjects (user_id, name) VALUES (?, ?)",
                    (user_id, subject)
                )
            except aiosqlite.IntegrityError:
                continue
        await db.commit()

    instructions = (
        " <b>Привет! Добро пожаловать в Электронный Дневник!</b>\n\n"
        "Вот что ты можешь сделать с помощью этого бота:\n\n"
        " <b>Добавить оценку</b> — выбери предмет и укажи свою оценку.\n"
        " <b>Удалить оценку</b> — удаление конкретной оценки из предмета.\n"
        " <b>Посмотреть все оценки</b> — отображает все оценки по каждому предмету.\n"
        " <b>Средний балл по предмету</b> — выбираешь предмет, а бот считает среднюю оценку.\n"
        " <b>Средний балл по всем предметам</b> — считает общую среднюю оценку.\n"
        " <b>Очистить все оценки</b> — удаляет абсолютно все оценки. Будь осторожен!\n"
        " <b>Управление предметами</b> — добавление, удаление и просмотр всех доступных предметов.\n\n"
        "Выбери нужное действие с помощью кнопок ниже "
    )

    await message.answer(instructions, parse_mode=ParseMode.HTML, reply_markup=main_menu())
@dp.callback_query(F.data == "add_grade")
async def add_grade_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

    kb = [[InlineKeyboardButton(text=subj[0][:25], callback_data=f"subject_{subj[0]}")] for subj in subjects]
    kb.append([InlineKeyboardButton(text=" Назад в меню", callback_data="back_to_menu")])  # кнопка назад

    await callback.message.edit_text(" Выберите предмет:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(GradeStates.choosing_subject)
@dp.callback_query(F.data.startswith("subject_"))
async def choose_subject(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    subject = callback.data.split("subject_")[1]
    await state.update_data(subject=subject)

    kb = [[InlineKeyboardButton(text=str(i), callback_data=f"grade_{i}")] for i in range(10, 0, -1)]
    kb.append([InlineKeyboardButton(text=" Назад в меню", callback_data="back_to_menu")])  # кнопка назад
    
    await callback.message.edit_text(
        f" Вы выбрали: <b>{subject}</b>\nТеперь выберите оценку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(GradeStates.choosing_grade)

@dp.callback_query(F.data.startswith("grade_"))
async def save_grade(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    subject = data.get("subject")

    if not subject:
        await callback.message.answer(" Ошибка: не выбран предмет. Пожалуйста, начните заново.")
        await callback.message.answer(" Возврат в главное меню:", reply_markup=main_menu())
        await state.clear()
        return

    grade = int(callback.data.split("grade_")[1])

    async with aiosqlite.connect("dnevnik.db") as db:
        try:
            await db.execute(
                "INSERT INTO grades (user_id, subject, grade) VALUES (?, ?, ?)",
                (user_id, subject, grade)
            )
            await db.commit()
        except Exception as e:
            await callback.message.answer(f" Ошибка при добавлении оценки: {e}")
            return

    await callback.message.edit_text(
        f" Оценка <b>{grade}</b> по предмету <b>{subject}</b> успешно добавлена!",
        parse_mode=ParseMode.HTML
    )
    await callback.message.answer(" Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()
@dp.callback_query(F.data == "view_grades")
async def view_grades_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    result = []

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

        for subj in subjects:
            subject = subj[0]
            async with db.execute("SELECT grade FROM grades WHERE subject = ? AND user_id = ?", (subject, user_id)) as cursor:
                grades = await cursor.fetchall()

            if grades:
                grades_list = ", ".join(str(grade[0]) for grade in grades)
                result.append(f"<b>{subject}</b>: {grades_list}")
            else:
                result.append(f"<b>{subject}</b>:")

    response = "\n".join(result) or "У вас нет оценок по всем предметам."
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML)
    await callback.message.answer(" Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "delete_grade")
async def delete_grade_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    kb = []

    async with aiosqlite.connect("dnevnik.db") as db:
        # Выбираем id и имя предмета
        async with db.execute("SELECT id, name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

    if not subjects:
        await callback.message.edit_text("❗️У вас нет предметов для удаления оценок.")
        await state.clear()
        return

    for subj_id, subj_name in subjects:
        kb.append([
            InlineKeyboardButton(
                text=subj_name[:25],  # ограничиваем длину текста кнопки
                callback_data=f"delete_subject_{subj_id}"  # передаем id предмета
            )
        ])

    kb.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")])

    await callback.message.edit_text(
        "🗑 Выберите предмет, из которого хотите удалить оценку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(GradeStates.deleting_grade)


@dp.callback_query(F.data.startswith("delete_subject_"))
async def delete_subject_grades(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.replace("delete_subject_", ""))
    user_id = callback.from_user.id

    # Получаем имя предмета по id
    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE id = ? AND user_id = ?", (subject_id, user_id)) as cursor:
            row = await cursor.fetchone()

    if not row:
        await callback.message.edit_text("❌ Предмет не найден.")
        await state.clear()
        return

    subject = row[0]
    await state.update_data(subject=subject)

    # Получаем оценки для выбранного предмета
    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT id, grade FROM grades WHERE subject = ? AND user_id = ?", (subject, user_id)) as cursor:
            grades = await cursor.fetchall()

    if not grades:
        await callback.message.edit_text(
            f"⚠️ По предмету <b>{subject}</b> нет оценок для удаления.",
            parse_mode=ParseMode.HTML
        )
        await callback.message.answer("🏠 Возврат в главное меню:", reply_markup=main_menu())
        await state.clear()
        return

    kb = [
        [InlineKeyboardButton(text=f"{grade[1]}", callback_data=f"delete_grade_id_{grade[0]}")]
        for grade in grades
    ]
    kb.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")])

    await callback.message.edit_text(
        f"Выберите оценку для удаления из <b>{subject}</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(GradeStates.deleting_grade)


@dp.callback_query(F.data.startswith("delete_grade_id_"))
async def delete_grade(callback: CallbackQuery, state: FSMContext):
    grade_id = int(callback.data.replace("delete_grade_id_", ""))
    user_id = callback.from_user.id

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT subject, grade FROM grades WHERE id = ? AND user_id = ?", (grade_id, user_id)) as cursor:
            row = await cursor.fetchone()

        if not row:
            await callback.message.edit_text(
                "❌ Оценка не найдена или уже удалена.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]]
                )
            )
            await state.clear()
            return

        subject, grade = row
        await db.execute("DELETE FROM grades WHERE id = ? AND user_id = ?", (grade_id, user_id))
        await db.commit()

    await callback.message.edit_text(
        f"✅ Оценка <b>{grade}</b> по предмету <b>{subject}</b> удалена.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]]
        )
    )
    await state.clear()


@dp.callback_query(F.data.startswith("average_subject_"))
async def calculate_average(callback: CallbackQuery, state: FSMContext):
    encoded_subject = callback.data.split("average_subject_")[1]
    subject = unquote(encoded_subject)  # декодируем сюда

    # дальше работаешь с subject, например:
    user_id = callback.from_user.id
    await state.update_data(subject=subject)

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT grade FROM grades WHERE subject = ? AND user_id = ?", (subject, user_id)) as cursor:
            grades = await cursor.fetchall()

    if not grades:
        await callback.message.edit_text(
            f"❌ По предмету <b>{subject}</b> нет оценок.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]]
            )
        )
        await state.clear()
        return

    grades_list = [grade[0] for grade in grades]
    average = round(sum(grades_list) / len(grades_list), 3)

    await callback.message.edit_text(
        f"📊 Средний балл по предмету <b>{subject}</b>: {average}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]]
        )
    )
    await state.clear()


@dp.callback_query(F.data == "overall_average")
async def overall_average_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

        subject_averages = []

        for subj in subjects:
            subject = unquote(subj[0])  # если ты кодируешь предметы при создании, здесь - декодируем
            async with db.execute("SELECT grade FROM grades WHERE subject = ? AND user_id = ?", (subject, user_id)) as cur:
                grades = await cur.fetchall()

            if grades:
                grades_list = [grade[0] for grade in grades]
                subject_avg = sum(grades_list) / len(grades_list)
                subject_averages.append(subject_avg)

    if subject_averages:
        overall_avg = round(sum(subject_averages) / len(subject_averages), 3)
        text = f"📊 Средний балл по всем предметам: {overall_avg}"
    else:
        text = "⚠️ У вас нет оценок для расчёта среднего балла."

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
            ]
        )
    )
    await state.clear()

@dp.callback_query(F.data == "clear_grades")
async def clear_grades_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        " Вы уверены, что хотите очистить все оценки? Это действие невозможно отменить.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=" Да, удалить все оценки", callback_data="confirm_clear_grades")],
            [InlineKeyboardButton(text=" Отмена", callback_data="cancel_clear_grades")]
        ])
    )
    await state.set_state(GradeStates.confirming_clear)


@dp.callback_query(F.data == "confirm_clear_grades", StateFilter(GradeStates.confirming_clear))
async def confirm_clear_grades_handler(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect("dnevnik.db") as db:
        await db.execute("DELETE FROM grades WHERE user_id = ?", (callback.from_user.id,))      
        await db.commit()

    await callback.message.edit_text(" Все оценки успешно удалены.")
    await callback.message.answer(" Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "cancel_clear_grades", StateFilter(GradeStates.confirming_clear))
async def cancel_clear_grades_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(" Очистка оценок отменена.")
    await callback.message.answer(" Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()

async def main():
    print("Бот запущен. Ожидание сообщений...")
    await dp.start_polling(bot)

@dp.callback_query(F.data == "average")
async def average_grade_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

    if not subjects:
        await callback.message.edit_text(" Нет предметов для подсчёта среднего балла.")
        await callback.message.answer(" Возврат в главное меню:", reply_markup=main_menu())
        await state.clear()
        return

    kb = [[InlineKeyboardButton(text=subj[0][:25], callback_data=f"average_subject_{subj[0]}")] for subj in subjects]
    kb.append([InlineKeyboardButton(text=" Назад в меню", callback_data="back_to_menu")]) 

    await callback.message.edit_text(
        " Выберите предмет для подсчета среднего балла:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(GradeStates.calculating_average)

# Обработка "Управление предметами"
@dp.callback_query(F.data == "manage_subjects")
async def manage_subjects_handler(callback: CallbackQuery, state: FSMContext):
    kb = [
        [InlineKeyboardButton(text="📖 Просмотреть предметы", callback_data="view_subjects")],
        [InlineKeyboardButton(text="➕ Добавить новый предмет", callback_data="add_subject")],
        [InlineKeyboardButton(text="🗑 Удалить предмет", callback_data="delete_subject")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    await callback.message.edit_text(
        "📚 Управление предметами:\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(GradeStates.managing_subjects)


# Обработка кнопки "Назад"
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_menu())
    await state.clear()


# Обработка просмотра предметов
@dp.callback_query(F.data == "view_subjects")
async def view_subjects_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

    if subjects:
        subject_list = "\n".join([f"• {subj[0]}" for subj in subjects])
        await callback.message.edit_text(f"📋 Список всех предметов:\n{subject_list}")
    else:
        await callback.message.edit_text("⚠️ Нет доступных предметов.")
    
    await callback.message.answer("🏠 Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()


# Обработка кнопки "Добавить новый предмет"
@dp.callback_query(F.data == "add_subject")
async def add_subject_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите название нового предмета:")
    await state.set_state(GradeStates.adding_subject)


# Обработка ввода названия нового предмета
@dp.message(StateFilter(GradeStates.adding_subject))
async def add_subject_name_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    subject_name = message.text.strip()

    if not subject_name:
        await message.answer("❗️Название предмета не может быть пустым. Попробуйте ещё раз:")
        return

    async with aiosqlite.connect("dnevnik.db") as db:
        # Проверяем, существует ли предмет уже
        async with db.execute(
            "SELECT 1 FROM subjects WHERE user_id = ? AND name = ?", (user_id, subject_name)
        ) as cursor:
            exists = await cursor.fetchone()

        if exists:
            await message.answer("❗️Такой предмет уже существует. Введите другое название:")
            return

        # Если не существует — добавляем
        await db.execute(
            "INSERT INTO subjects (user_id, name) VALUES (?, ?)", (user_id, subject_name)
        )
        await db.commit()

    await message.answer(
        f"✅ Предмет <b>{subject_name}</b> успешно добавлен!", parse_mode=ParseMode.HTML
    )
    await message.answer("🔙 Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "delete_subject")
async def delete_subject_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE user_id = ?", (user_id,)) as cursor:
            subjects = await cursor.fetchall()

    if not subjects:
        await callback.message.edit_text("Нет доступных предметов для удаления.")
        await callback.message.answer("Возврат в главное меню:", reply_markup=main_menu())
        await state.clear()
        return

    kb = [[InlineKeyboardButton(text=subj[0], callback_data=f"delete_{subj[0]}")] for subj in subjects]
    kb.append([InlineKeyboardButton(text="Назад в меню", callback_data="back_to_menu")])

    await callback.message.edit_text(
        "Выберите предмет для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(GradeStates.deleting_subject)

@dp.callback_query(F.data.startswith("delete_"))
async def delete_subject_from_db(callback: CallbackQuery, state: FSMContext):
    subject_name = callback.data.split("delete_")[1]
    user_id = callback.from_user.id

    async with aiosqlite.connect("dnevnik.db") as db:
        async with db.execute("SELECT name FROM subjects WHERE name = ? AND user_id = ?", (subject_name, user_id)) as cursor:
            subject = await cursor.fetchone()

        if not subject:
            await callback.message.edit_text(f"Предмет '{subject_name}' не найден.")
            await callback.message.answer("Возврат в главное меню:", reply_markup=main_menu())
            await state.clear()
            return

        await db.execute("DELETE FROM grades WHERE subject = ? AND user_id = ?", (subject_name, user_id))
        await db.execute("DELETE FROM subjects WHERE name = ? AND user_id = ?", (subject_name, user_id))
        await db.commit()

    await callback.message.edit_text(f"Предмет '{subject_name}' и все связанные оценки были успешно удалены.")
    await callback.message.answer("Возврат в главное меню:", reply_markup=main_menu())
    await state.clear()
if __name__ == "__main__":
    asyncio.run(main())
