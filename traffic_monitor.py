import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class TrafficMonitor:
    """Handles traffic data retrieval and route analysis"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"

    def get_route_with_traffic(
        self, origin: str, destination: str, waypoints: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Get route information with traffic data

        Args:
            origin: Starting location
            destination: Final destination
            waypoints: Optional list of stops along the way

        Returns:
            Dictionary with route and traffic information
        """
        params = {
            "origin": origin,
            "destination": destination,
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": self.api_key,
        }

        # Add waypoints if provided
        if waypoints:
            params["waypoints"] = "optimize:false|" + "|".join(waypoints)

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK":
                return self._parse_route_data(data, waypoints)
            else:
                print(
                    f"❌ API Error: {data['status']} - {data.get('error_message', '')}"
                )
                return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return None

    def _parse_route_data(self, data: Dict, waypoints: Optional[List[str]]) -> Dict:
        """Parse Google Maps API response"""
        route = data["routes"][0]
        legs = route["legs"]

        # Calculate total duration and distance
        total_duration = sum(leg["duration"]["value"] for leg in legs)
        total_duration_traffic = sum(
            leg.get("duration_in_traffic", leg["duration"])["value"] for leg in legs
        )
        total_distance = sum(leg["distance"]["value"] for leg in legs)

        # Parse waypoint information
        stops = []
        if waypoints:
            for i, leg in enumerate(legs[:-1]):  # All legs except the last
                stops.append(
                    {
                        "address": waypoints[i] if i < len(waypoints) else "Unknown",
                        "duration_to_next": leg["duration"]["value"],
                        "distance_to_next": leg["distance"]["value"],
                    }
                )

        return {
            "total_duration": total_duration,
            "total_duration_traffic": total_duration_traffic,
            "total_distance": total_distance,
            "distance_text": self._meters_to_text(total_distance),
            "summary": route["summary"],
            "waypoints": stops,
            "start_address": legs[0]["start_address"],
            "end_address": legs[-1]["end_address"],
            "traffic_ratio": total_duration_traffic / total_duration,
        }

    def _meters_to_text(self, meters: int) -> str:
        """Convert meters to readable text"""
        if meters < 1000:
            return f"{meters} m"
        else:
            km = meters / 1000
            return f"{km:.1f} km"

    def calculate_departure_time(
        self, traffic_data: Dict, arrival_time: str, buffer_minutes: int
    ) -> Tuple[datetime, int]:
        """
        Calculate when to leave based on traffic

        Returns:
            Tuple of (departure_time, travel_minutes)
        """
        # Parse desired arrival time
        arrival_hour, arrival_minute = map(int, arrival_time.split(":"))
        today = datetime.now().replace(
            hour=arrival_hour, minute=arrival_minute, second=0, microsecond=0
        )

        # If arrival time has passed today, use tomorrow
        if today < datetime.now():
            today += timedelta(days=1)

        # Calculate travel time with buffer
        travel_seconds = traffic_data["total_duration_traffic"]
        travel_minutes = (travel_seconds / 60) + buffer_minutes

        # Calculate departure time
        departure_time = today - timedelta(minutes=travel_minutes)

        return departure_time, int(travel_minutes)

    def analyze_traffic(self, traffic_data: Dict, threshold: float) -> str:
        """
        Analyze traffic conditions

        Returns:
            Traffic status emoji and text
        """
        ratio = traffic_data["traffic_ratio"]

        if ratio >= threshold:
            return "🔴 Heavy traffic"
        elif ratio >= 1.1:
            return "🟡 Moderate traffic"
        else:
            return "🟢 Light traffic"
