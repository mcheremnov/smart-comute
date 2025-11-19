import os
from typing import Optional
from telegram import Update, Bot
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
import asyncio

class TelegramCommuteBot:
    """Telegram bot for commute notifications and commands"""

    def __init__(self, token: str, chat_id: str, config):
        self.token = token
        self.chat_id = chat_id
        self.config = config
        self.bot = Bot(token=token)
        self.application = None

    async def send_notification(self, title: str, message: str, parse_mode: str = 'Markdown'):
        """Send notification message"""
        try:
            full_message = f"*{title}*\n\n{message}"
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=full_message,
                parse_mode=parse_mode
            )
            print(f"✅ Telegram notification sent: {title}")
            return True
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False

    async def send_departure_alert(self, 
                                   travel_time: str,
                                   route_summary: str,
                                   traffic_status: str,
                                   waypoints: list):
        """Send main departure notification"""
        message = f"🏠 *Time to Head Home!*\n\n"
        message += f"⏱️ *Travel time:* {travel_time}\n"
        message += f"🚦 *Traffic:* {traffic_status}\n"
        message += f"🗺️ *Best route:* {route_summary}\n"

        if waypoints:
            message += f"\n📍 *Your stops:*\n"
            for i, stop in enumerate(waypoints, 1):
                message += f"   {i}. {stop['address']}\n"

        message += f"\n_Have a safe trip home!_ 🚗"

        await self.send_notification("Commute Alert", message)

    async def send_early_warning(self, 
                                travel_time: str,
                                minutes_early: int,
                                traffic_status: str):
        """Send early warning for heavy traffic"""
        message = f"⚠️ *Heavy Traffic Detected*\n\n"
        message += f"Consider leaving *{minutes_early} minutes early*\n\n"
        message += f"⏱️ *Current travel time:* {travel_time}\n"
        message += f"🚦 {traffic_status}\n\n"
        message += f"_I'll notify you again when it's time to leave._"

        await self.send_notification("Traffic Warning", message)

    def setup_commands(self):
        """Setup bot command handlers"""
        self.application = Application.builder().token(self.token).build()

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("add", self.cmd_add_stop))
        self.application.add_handler(CommandHandler("remove", self.cmd_remove_stop))
        self.application.add_handler(CommandHandler("stops", self.cmd_list_stops))
        self.application.add_handler(CommandHandler("clear", self.cmd_clear_stops))
        self.application.add_handler(CommandHandler("check", self.cmd_check_now))

        # Message handler for natural language
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        message = (
            "🏠 *Welcome to Your Commute Assistant!*\n\n"
            "I'll help you get home on time by monitoring traffic "
            "and notifying you when to leave.\n\n"
            "*Available Commands:*\n"
            "• `/status` - Current commute info\n"
            "• `/add ` - Add stop on your way\n"
            "• `/remove ` - Remove a stop\n"
            "• `/stops` - List all stops\n"
            "• `/clear` - Clear all stops\n"
            "• `/check` - Check traffic now\n\n"
            "*Natural Language:*\n"
            "You can also say:\n"
            "• 'Add gym'\n"
            "• 'Stop at grocery store'\n"
            "• 'Clear all stops'\n\n"
            f"I'll check traffic daily at *{self.config.check_time}* "
            f"and notify you when it's time to leave!"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        message = f"📊 *Current Configuration*\n\n"
        message += f"🏢 *Work:* {self.config.work_address}\n"
        message += f"🏠 *Home:* {self.config.home_address}\n"
        message += f"⏰ *Check time:* {self.config.check_time}\n"
        message += f"🎯 *Target arrival:* {self.config.desired_arrival_time}\n"
        message += f"⏱️ *Buffer:* {self.config.buffer_minutes} min\n\n"

        if self.config.waypoints:
            message += f"📍 *Active stops:*\n"
            for i, stop in enumerate(self.config.waypoints, 1):
                message += f"   {i}. {stop}\n"
        else:
            message += f"📍 *No stops configured*\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def cmd_add_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command"""
        if not context.args:
            await update.message.reply_text(
                "Please specify a location.\n"
                "Example: `/add Whole Foods Market`",
                parse_mode='Markdown'
            )
            return

        stop = ' '.join(context.args)
        if self.config.add_waypoint(stop):
            await update.message.reply_text(
                f"✅ Added stop: *{stop}*\n\n"
                f"You now have {len(self.config.waypoints)} stop(s).",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"⚠️ Stop *{stop}* already exists!",
                parse_mode='Markdown'
            )

    async def cmd_remove_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove command"""
        if not context.args:
            await update.message.reply_text(
                "Please specify which stop to remove.\n"
                "Use `/stops` to see your stops.",
                parse_mode='Markdown'
            )
            return

        stop = ' '.join(context.args)
        if self.config.remove_waypoint(stop):
            await update.message.reply_text(
                f"✅ Removed stop: *{stop}*",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"⚠️ Stop *{stop}* not found!",
                parse_mode='Markdown'
            )

    async def cmd_list_stops(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stops command"""
        if not self.config.waypoints:
            await update.message.reply_text("You have no stops configured.")
            return

        message = f"📍 *Your stops ({len(self.config.waypoints)}):*\n\n"
        for i, stop in enumerate(self.config.waypoints, 1):
            message += f"{i}. {stop}\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def cmd_clear_stops(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        count = len(self.config.waypoints)
        self.config.clear_waypoints()
        await update.message.reply_text(
            f"✅ Cleared {count} stop(s).",
            parse_mode='Markdown'
        )

    async def cmd_check_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check command - trigger immediate traffic check"""
        await update.message.reply_text(
            "🔍 Checking traffic now...",
            parse_mode='Markdown'
        )
        # This will be called by the main app
        # Store the update context for callback
        context.user_data['check_requested'] = True

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages"""
        text = update.message.text.lower()

        # Pattern matching for natural commands
        if any(word in text for word in ['add', 'stop at', 'stop by']):
            # Extract location (simple approach)
            for keyword in ['add', 'stop at', 'stop by']:
                if keyword in text:
                    location = text.split(keyword, 1)[1].strip()
                    if location:
                        self.config.add_waypoint(location)
                        await update.message.reply_text(
                            f"✅ Added: *{location}*",
                            parse_mode='Markdown'
                        )
                        return

        elif 'clear' in text and 'stop' in text:
            count = len(self.config.waypoints)
            self.config.clear_waypoints()
            await update.message.reply_text(
                f"✅ Cleared {count} stop(s)."
            )
            return

        elif 'status' in text or 'info' in text:
            await self.cmd_status(update, context)
            return

        # Default response
        await update.message.reply_text(
            "I'm not sure what you mean. Try:\n"
            "• `/status` - See your settings\n"
            "• `/add ` - Add a stop\n"
            "• `/help` - See all commands"
        )

    def run_bot(self):
        """Start the bot (blocking)"""
        self.setup_commands()
        print("🤖 Telegram bot started")
        self.application.run_polling()