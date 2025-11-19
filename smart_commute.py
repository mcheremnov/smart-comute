import os
import schedule
import time
import asyncio
from datetime import datetime, timedelta
from config import CommuteConfig
from traffic_monitor import TrafficMonitor
from telegram_bot import TelegramCommuteBot

class SmartCommuteAssistant:
    """Main application orchestrating the commute assistant"""

    def __init__(self):
        # Load configuration
        self.config = CommuteConfig.from_env()

        # Initialize components
        self.traffic_monitor = TrafficMonitor(
            os.getenv('GOOGLE_MAPS_API_KEY')
        )
        self.telegram_bot = TelegramCommuteBot(
            token=os.getenv('TELEGRAM_BOT_TOKEN'),
            chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            config=self.config
        )

        # State tracking
        self.last_notification_time = None
        self.notification_sent_today = False

    def check_traffic_and_notify(self):
        """Main logic: Check traffic and send notification if needed"""
        current_time = datetime.now()
        print(f"\n🕐 Checking traffic at {current_time.strftime('%H:%M:%S')}")

        # Get route with all waypoints
        route = self.config.get_full_route()
        origin = route[0]
        destination = route[-1]
        waypoints = route[1:-1] if len(route) > 2 else None

        print(f"📍 Route: {origin}")
        if waypoints:
            for wp in waypoints:
                print(f"   ↓ via {wp}")
        print(f"   → {destination}")

        # Get current traffic data
        traffic_data = self.traffic_monitor.get_route_with_traffic(
            origin=origin,
            destination=destination,
            waypoints=waypoints
        )

        if not traffic_data:
            print("❌ Could not retrieve traffic data")
            return

        # Calculate when to leave
        departure_time, travel_minutes = self.traffic_monitor.calculate_departure_time(
            traffic_data,
            self.config.desired_arrival_time,
            self.config.buffer_minutes
        )

        # Analyze traffic
        traffic_status = self.traffic_monitor.analyze_traffic(
            traffic_data,
            self.config.heavy_traffic_threshold
        )

        # Format travel time
        travel_time_str = self._format_duration(
            traffic_data['total_duration_traffic']
        )

        # Calculate time until departure
        time_until_departure = (departure_time - current_time).total_seconds() / 60

        # Print status
        print(f"⏱️  Travel time: {travel_time_str}")
        print(f"🚦 Traffic: {traffic_status}")
        print(f"🏁 Recommended departure: {departure_time.strftime('%H:%M')}")
        print(f"⏰ Minutes until departure: {int(time_until_departure)}")

        # Send notifications based on timing
        if 0 <= time_until_departure <= 5 and not self.notification_sent_today:
            # Time to leave!
            asyncio.run(self._send_departure_notification(
                travel_time_str,
                traffic_data,
                traffic_status
            ))
            self.notification_sent_today = True
            self.last_notification_time = current_time

        elif (traffic_data['traffic_ratio'] >= self.config.heavy_traffic_threshold 
              and 5 < time_until_departure <= 20
              and not self.notification_sent_today):
            # Heavy traffic - send early warning
            asyncio.run(self._send_early_warning(
                travel_time_str,
                int(time_until_departure),
                traffic_status
            ))
            # Don't set notification_sent_today yet, still need to send main alert

        elif time_until_departure > 30:
            print("⏳ Too early to leave, continuing to monitor...")

        elif time_until_departure < 0:
            print("⚠️  You should have already left!")
            if not self.notification_sent_today:
                asyncio.run(self._send_late_warning(travel_time_str))
                self.notification_sent_today = True

    async def _send_departure_notification(self, 
                                          travel_time: str,
                                          traffic_data: dict,
                                          traffic_status: str):
        """Send the main departure notification"""
        await self.telegram_bot.send_departure_alert(
            travel_time=travel_time,
            route_summary=traffic_data['summary'],
            traffic_status=traffic_status,
            waypoints=traffic_data.get('waypoints', [])
        )

    async def _send_early_warning(self, 
                                 travel_time: str,
                                 minutes_early: int,
                                 traffic_status: str):
        """Send early warning for heavy traffic"""
        await self.telegram_bot.send_early_warning(
            travel_time,
            minutes_early,
            traffic_status
        )

    async def _send_late_warning(self, travel_time: str):
        """Send warning if user is late"""
        message = f"⚠️ *You're Running Late!*\n\n"
        message += f"⏱️ *Travel time:* {travel_time}\n\n"
        message += f"_Leave now to minimize delay!_"
        await self.telegram_bot.send_notification("Late Alert", message)

    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to readable string"""
        minutes = int(seconds / 60)
        if minutes < 60:
            return f"{minutes} min"
        else:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}min"

    def _check_if_in_monitoring_window(self):
        """Check if we're within the monitoring window"""
        now = datetime.now()

        # Reset daily flag at midnight
        if now.hour == 0 and now.minute < 5:
            self.notification_sent_today = False

        # Parse check time and arrival time
        check_hour, check_minute = map(int, self.config.check_time.split(':'))
        arrival_hour, arrival_minute = map(int, self.config.desired_arrival_time.split(':'))

        check_time = now.replace(hour=check_hour, minute=check_minute, second=0)
        arrival_time = now.replace(hour=arrival_hour, minute=arrival_minute, second=0)

        # Monitor from check_time until 30 minutes after arrival_time
        end_time = arrival_time + timedelta(minutes=30)

        if check_time <= now <= end_time:
            self.check_traffic_and_notify()

    def start(self):
        """Start the commute assistant"""
        print("\n" + "="*60)
        print("🚀 Smart Commute Assistant Started")
        print("="*60)
        print(f"\n📍 Work: {self.config.work_address}")
        print(f"📍 Home: {self.config.home_address}")
        print(f"⏰ Check time: {self.config.check_time}")
        print(f"🎯 Target arrival: {self.config.desired_arrival_time}")
        print(f"📊 Monitoring for traffic conditions...")

        # Schedule checks
        check_time = self.config.check_time

        # Main scheduled check
        schedule.every().day.at(check_time).do(self.check_traffic_and_notify)

        # Continuous monitoring during window (every 5 minutes)
        schedule.every(5).minutes.do(self._check_if_in_monitoring_window)

        # Run once immediately for testing
        print(f"\n🔍 Running initial check...")
        self.check_traffic_and_notify()

        # Start the scheduling loop
        print(f"\n✅ System is running. Press Ctrl+C to stop.")
        print("="*60 + "\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            print("\n\n👋 Smart Commute Assistant stopped")

def main():
    """Entry point"""
    assistant = SmartCommuteAssistant()
    assistant.start()

if __name__ == "__main__":
    main()