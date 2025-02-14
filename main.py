import argparse
import logging
import random
from datetime import datetime, timedelta

import pytz
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    JobQueue,
    MessageHandler,
    filters,
)

from utils import COMPLETION_MESSAGES, get_user_data, update_user_data

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


MAIN_MENU_COMMAND = "Main Menu 📋"
START_DAY_COMMAND = "Start Day ▶️"

ADDING_MESSAGE = 1
ADDING_DELAY = 2

user_messages = {}
user_active_days = {}


async def set_timezone(update, context):
    user_id = str(update.effective_user.id)

    if not context.args:
        await update.message.reply_text(
            "Please provide a timezone. Example: /set_timezone Europe/London"
        )
        return

    timezone_str = context.args[0]
    try:
        pytz.timezone(timezone_str)
        user_data = get_user_data(user_id)
        user_data["timezone"] = timezone_str
        update_user_data(user_id, user_data)
        await update.message.reply_text(f"Timezone successfully set to {timezone_str}")
    except pytz.exceptions.UnknownTimeZoneError:
        await update.message.reply_text(
            "Invalid timezone. Please use a valid timezone name."
        )


async def start(update, context):
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name

    logger.info(f"User {user_name} (ID: {user_id}) started the bot")

    keyboard = [
        [KeyboardButton(START_DAY_COMMAND)],
        [KeyboardButton(MAIN_MENU_COMMAND)],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome! The main buttons are now available at the bottom.",
        reply_markup=reply_markup,
    )
    await show_main_menu(update, context)
    return ConversationHandler.END


async def send_reminder(context):
    job = context.job
    user_id = job.data["user_id"]
    message = job.data["message"]
    is_last = job.data.get("is_last", False)

    logger.info(f"Sending reminder to user {user_id}: {message}")
    await context.bot.send_message(chat_id=user_id, text=f"🔔 Reminder:\n{message}")

    if is_last:
        completion_message = random.choice(COMPLETION_MESSAGES)
        await context.bot.send_message(chat_id=user_id, text=completion_message)


async def handle_trigger(update, context):
    user_id = str(update.effective_user.id)

    is_button = bool(update.callback_query)
    if is_button:
        trigger_type = update.callback_query.data
    else:
        trigger_type = update.message.text

    if trigger_type == START_DAY_COMMAND or trigger_type == "start_day":
        if user_id in user_active_days and user_active_days[user_id]:
            keyboard = [
                [
                    InlineKeyboardButton("Yes", callback_data="confirm_restart"),
                    InlineKeyboardButton("No", callback_data="back_to_menu"),
                ]
            ]
            if is_button:
                await update.callback_query.message.edit_text(
                    "A day is already in progress. Do you want to restart?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            else:
                await update.message.reply_text(
                    "A day is already in progress. Do you want to restart?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            return

        await start_day_sequence(update, context)
    elif trigger_type == MAIN_MENU_COMMAND:
        if update.message:
            await show_main_menu(update, context)


async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    user_name = query.from_user.first_name

    if query.data == "add_message":
        logger.info(f"User {user_name} is adding a new message")
        await query.message.edit_text(
            "Please enter the message you want to schedule.\n\n"
            "Example: 'Take 2 pills of medicine X with water'\n"
            "Or: 'Time for your evening walk!'"
        )
        return ADDING_MESSAGE
    elif query.data == "view_messages":
        await view_messages(update, context)
        return ConversationHandler.END
    elif query.data == "delete_messages":
        await show_delete_options(update, context)
        return ConversationHandler.END
    elif query.data == "back_to_menu":
        await show_main_menu(update, context)
        return ConversationHandler.END
    elif query.data == "confirm_restart":
        await start_day_sequence(update, context)
        return ConversationHandler.END
    elif query.data == "start_day":
        await handle_trigger(update, context)
        return ConversationHandler.END


async def show_main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("Add message", callback_data="add_message")],
        [InlineKeyboardButton("View messages", callback_data="view_messages")],
        [InlineKeyboardButton("Delete messages", callback_data="delete_messages")],
        [InlineKeyboardButton("Start day", callback_data="start_day")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "What would you like to do?", reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.edit_text(
            "What would you like to do?", reply_markup=reply_markup
        )


async def start_day_sequence(update, context):
    user_id = str(update.effective_user.id)

    user_data = get_user_data(user_id)
    user_tz = pytz.timezone(user_data["timezone"])
    current_time = datetime.now(user_tz)

    if user_data["messages"]:
        if hasattr(context, "job_queue"):
            for job in context.job_queue.get_jobs_by_name(user_id):
                job.schedule_removal()

        message = "🔔 Scheduling your reminders:\n\n"
        sorted_messages = sorted(
            user_data["messages"], key=lambda x: x["delay_minutes"]
        )

        for i, msg in enumerate(sorted_messages):
            delay = msg["delay_minutes"]
            reminder_time = current_time + timedelta(minutes=delay)
            message += f"• {msg['message']}\n  Will be sent at: {reminder_time.strftime('%H:%M')}\n"

            is_last = i == len(sorted_messages) - 1
            context.job_queue.run_once(
                send_reminder,
                delay * 60,
                data={
                    "user_id": user_id,
                    "message": msg["message"],
                    "is_last": is_last,
                },
                name=user_id,
            )

        user_data["active_day"] = True
        update_user_data(user_id, user_data)

        keyboard = [
            [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
        ]

        if update.callback_query:
            await update.callback_query.message.reply_text(
                message, reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                message, reply_markup=InlineKeyboardMarkup(keyboard)
            )


async def add_message_text(update, context):
    user_name = update.effective_user.first_name
    message_text = update.message.text
    context.user_data["temp_message"] = message_text

    logger.info(f"User {user_name} added message: {message_text}")

    await update.message.reply_text(
        "Message saved! Now, please enter the delay in minutes after the trigger word 'start_day'.\n\n"
        "Example: '30' for 30 minutes after trigger\n"
        "Or: '120' for 2 hours after trigger"
    )
    return ADDING_DELAY


async def add_message_delay(update, context):
    try:
        delay = int(update.message.text)
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name

        user_data = get_user_data(user_id)

        new_message = {
            "message": context.user_data["temp_message"],
            "delay_minutes": delay,
        }

        if len(user_data["messages"]) >= 5:
            await update.message.reply_text(
                "You've reached the maximum limit of 5 messages. "
                "Please delete some messages before adding new ones."
            )
            keyboard = [
                [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
            ]
            await update.message.reply_text(
                "What would you like to do?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return ConversationHandler.END

        user_data["messages"].append(new_message)
        update_user_data(user_id, user_data)
        logger.info(f"User {user_name} scheduled message with {delay} minutes delay")

        await update.message.reply_text(
            f"✅ Message scheduled successfully!\n\n"
            f"Message: {new_message['message']}\n"
            f"Delay: {delay} minutes after trigger\n\n"
            f"Use 'start_day' when you want to start your reminder sequence."
        )

        keyboard = [
            [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
        ]
        await update.message.reply_text(
            "What would you like to do next?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number of minutes.")
        return ADDING_DELAY


async def view_messages(update, context):
    user_id = str(update.callback_query.from_user.id)

    user_data = get_user_data(user_id)
    messages = user_data.get("messages", [])

    if not messages:
        message = "📝 You have no scheduled messages."
    else:
        message = "📋 Your scheduled messages:\n\n"
        for i, msg in enumerate(messages, 1):
            message += (
                f"{i}. After {msg['delay_minutes']} minutes:\n   {msg['message']}\n\n"
            )

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]]

    try:
        await update.callback_query.message.edit_text(
            message, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in view_messages: {e}")
        await update.callback_query.message.reply_text(
            message, reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_delete_options(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)
    user_name = query.from_user.first_name

    logger.info(f"User {user_name} is viewing delete options")

    user_data = get_user_data(user_id)
    messages = user_data.get("messages", [])

    if not messages:
        keyboard = [
            [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
        ]
        await query.message.edit_text(
            "You have no messages to delete.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    keyboard = []
    for i, msg in enumerate(messages, 1):
        display_msg = msg["message"][:30] + ("..." if len(msg["message"]) > 30 else "")
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{i}. {display_msg}", callback_data=f"delete_{i - 1}"
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
    )

    await query.message.edit_text(
        "Select a message to delete:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_message(update, context):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    user_name = query.from_user.first_name

    try:
        index = int(query.data.split("_")[1])

        user_data = get_user_data(user_id)
        messages = user_data.get("messages", [])

        if 0 <= index < len(messages):
            deleted_message = messages.pop(index)
            user_data["messages"] = messages
            update_user_data(user_id, user_data)

            logger.info(
                f"User {user_name} deleted message: {deleted_message['message']}"
            )

            keyboard = [
                [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
            ]
            await query.message.edit_text(
                f"✅ Message deleted successfully:\n\n"
                f"Message: {deleted_message['message']}\n"
                f"Delay: {deleted_message['delay_minutes']} minutes",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            keyboard = [
                [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
            ]
            await query.message.edit_text(
                "⚠️ Message not found.", reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except (ValueError, IndexError) as e:
        logger.error(f"Error deleting message: {e}")
        keyboard = [
            [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")]
        ]
        await query.message.edit_text(
            "⚠️ Error deleting message.", reply_markup=InlineKeyboardMarkup(keyboard)
        )


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot")
    parser.add_argument("--token", required=True, help="Telegram Bot Token")
    args = parser.parse_args()

    application = Application.builder().token(args.token).build()

    job_queue = JobQueue()
    job_queue.set_application(application)
    job_queue.start()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler, pattern="^(?!(delete_\d+)$).*$"),
        ],
        states={
            ADDING_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_message_text)
            ],
            ADDING_DELAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_message_delay)
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler, pattern="^(?!(delete_\d+)$).*$"),
        ],
    )

    application.add_handler(
        CallbackQueryHandler(delete_message, pattern="^delete_\d+$")
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("set_timezone", set_timezone))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trigger)
    )
    application.add_handler(
        MessageHandler(
            filters.Regex(f"^({START_DAY_COMMAND}|{MAIN_MENU_COMMAND})$"),
            handle_trigger,
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trigger)
    )

    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
