import os
from dotenv import load_dotenv

from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import pytz
import logging
from telegram.ext import JobQueue

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADDING_MESSAGE = 1
ADDING_DELAY = 2

user_messages = {}

async def start(update, context):
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name

    if user_id not in user_messages:
        user_messages[user_id] = []

    logger.info(f"User {user_name} (ID: {user_id}) started the bot")
    await show_main_menu(update, context)
    return ConversationHandler.END

async def show_main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("Add message", callback_data='add_message')],
        [InlineKeyboardButton("View messages", callback_data='view_messages')],
        [InlineKeyboardButton("Delete messages", callback_data='delete_messages')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "What would you like to do?",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.edit_text(
            "What would you like to do?",
            reply_markup=reply_markup
        )

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    user_name = query.from_user.first_name

    if query.data == 'add_message':
        logger.info(f"User {user_name} is adding a new message")
        await query.message.edit_text(
            "Please enter the message you want to schedule.\n\n"
            "Example: 'Take 2 pills of medicine X with water'\n"
            "Or: 'Time for your evening walk!'"
        )
        return ADDING_MESSAGE
    elif query.data == 'view_messages':
        await view_messages(update, context)
        return ConversationHandler.END
    elif query.data == 'delete_messages':
        await show_delete_options(update, context)
        return ConversationHandler.END
    elif query.data == 'back_to_menu':
        await show_main_menu(update, context)
        return ConversationHandler.END

async def add_message_text(update, context):
    user_name = update.effective_user.first_name
    message_text = update.message.text
    context.user_data['temp_message'] = message_text

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

        new_message = {
            "message": context.user_data['temp_message'],
            "delay_minutes": delay
        }

        if user_id not in user_messages:
            user_messages[user_id] = []

        if len(user_messages[user_id]) >= 5:
            await update.message.reply_text(
                "You've reached the maximum limit of 5 messages. "
                "Please delete some messages before adding new ones."
            )
            keyboard = [[InlineKeyboardButton("Back to menu", callback_data='back_to_menu')]]
            await update.message.reply_text("What would you like to do?",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        user_messages[user_id].append(new_message)

        logger.info(f"User {user_name} scheduled message with {delay} minutes delay")

        await update.message.reply_text(
            f"✅ Message scheduled successfully!\n\n"
            f"Message: {new_message['message']}\n"
            f"Delay: {delay} minutes after trigger\n\n"
            f"Use 'start_day' when you want to start your reminder sequence."
        )

        keyboard = [[InlineKeyboardButton("Back to menu", callback_data='back_to_menu')]]
        await update.message.reply_text("What would you like to do next?",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number of minutes.")
        return ADDING_DELAY

async def view_messages(update, context):
    user_id = str(update.callback_query.from_user.id)
    user_name = update.callback_query.from_user.first_name

    logger.info(f"User {user_name} is viewing their messages")

    if not user_messages.get(user_id, []):
        message = "📝 You have no scheduled messages."
    else:
        message = "📋 Your scheduled messages:\n\n"
        for i, msg in enumerate(user_messages[user_id], 1):
            message += f"{i}. After {msg['delay_minutes']} minutes:\n   {msg['message']}\n\n"

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data='back_to_menu')]]
    await update.callback_query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_delete_options(update, context):
    user_id = str(update.callback_query.from_user.id)
    user_name = update.callback_query.from_user.first_name

    logger.info(f"User {user_name} is viewing delete options")

    if not user_messages.get(user_id, []):
        keyboard = [[InlineKeyboardButton("Back to menu", callback_data='back_to_menu')]]
        await update.callback_query.message.edit_text(
            "You have no messages to delete.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keyboard = []
    for i, msg in enumerate(user_messages[user_id], 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {msg['message'][:30]}...",
            callback_data=f'delete_{i-1}'
        )])
    keyboard.append([InlineKeyboardButton("Back to menu", callback_data='back_to_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Select a message to delete:",
        reply_markup=reply_markup
    )

async def delete_message(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == 'back_to_menu':
        await show_main_menu(update, context)
        return

    user_id = str(query.from_user.id)
    user_name = query.from_user.first_name
    index = int(query.data.split('_')[1])

    if user_id in user_messages and 0 <= index < len(user_messages[user_id]):
        deleted_message = user_messages[user_id].pop(index)
        logger.info(f"User {user_name} deleted message: {deleted_message['message']}")

        keyboard = [[InlineKeyboardButton("Back to menu", callback_data='back_to_menu')]]
        await query.message.edit_text(
            f"🗑️ Deleted message:\n"
            f"Message: {deleted_message['message']}\n"
            f"Delay: {deleted_message['delay_minutes']} minutes",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("Back to menu", callback_data='back_to_menu')]]
        await query.message.edit_text(
            "⚠️ Message not found.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_trigger(update, context):
    if update.message.text.lower() == 'start_day':
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name
        current_time = datetime.now(pytz.UTC)

        logger.info(f"User {user_name} triggered their daily reminder sequence")

        if user_id in user_messages and user_messages[user_id]:
            message = "🔔 Scheduling your reminders:\n\n"
            for msg in user_messages[user_id]:
                delay = msg['delay_minutes']
                reminder_time = current_time + timedelta(minutes=delay)
                message += f"• {msg['message']}\n  Will be sent at: {reminder_time.strftime('%H:%M')}\n"

                context.job_queue.run_once(
                    send_reminder,
                    delay * 60,
                    data={
                        "user_id": user_id,
                        "message": msg['message']
                    }
                )

            await update.message.reply_text(message)
        else:
            await update.message.reply_text("⚠️ You have no messages scheduled. Use /start to add messages.")

async def send_reminder(context):
    job = context.job
    user_id = job.data["user_id"]
    message = job.data["message"]

    logger.info(f"Sending reminder to user {user_id}: {message}")

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🔔 Reminder:\n{message}"
    )

def main():
    application = (
        Application.builder()
        .token(os.getenv('BOT_TOKEN'))
        .build()
    )

    job_queue = JobQueue()
    job_queue.set_application(application)
    job_queue.start()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler),
        ],
        states={
            ADDING_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_message_text)],
            ADDING_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_message_delay)],
        },
        fallbacks=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler),
        ]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trigger))
    application.add_handler(CallbackQueryHandler(delete_message, pattern='^delete_'))

    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()