import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class CommuteConfig:
    """Configuration for commute monitoring"""

    work_address: str
    home_address: str
    check_time: str  # HH:MM format
    desired_arrival_time: str  # HH:MM format
    buffer_minutes: int = 10
    heavy_traffic_threshold: float = 1.3
    waypoints: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            work_address=os.getenv("WORK_ADDRESS"),
            home_address=os.getenv("HOME_ADDRESS"),
            check_time=os.getenv("CHECK_TIME", "17:00"),
            desired_arrival_time=os.getenv("DESIRED_ARRIVAL_TIME", "18:00"),
            buffer_minutes=int(os.getenv("BUFFER_MINUTES", "10")),
            heavy_traffic_threshold=float(os.getenv("TRAFFIC_THRESHOLD", "1.3")),
        )

    def add_waypoint(self, address: str):
        """Add a stop on the way home"""
        if address not in self.waypoints:
            self.waypoints.append(address)
            return True
        return False

    def remove_waypoint(self, address: str):
        """Remove a stop"""
        if address in self.waypoints:
            self.waypoints.remove(address)
            return True
        return False

    def clear_waypoints(self):
        """Clear all waypoints"""
        self.waypoints.clear()

    def get_full_route(self) -> List[str]:
        """Get complete route: work → waypoints → home"""
        return [self.work_address] + self.waypoints + [self.home_address]
