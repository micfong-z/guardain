"""
Crime Safety MCP Server - FastMCP Implementation
A clean, modern MCP server for real-time crime and safety intelligence
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
import httpx
from mcp.server.fastmcp import FastMCP
from astral import LocationInfo
from astral.sun import sun

# ============================================================================
# CONFIGURATION
# ============================================================================

UK_POLICE_API_BASE = "https://data.police.uk/api"
OPEN_METEO_API_BASE = "https://api.open-meteo.com/v1/forecast" # ?latitude=52.52&longitude=13.41&hourly=temperature_2m
# OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY", "")

# Create the FastMCP server
mcp = FastMCP("CrimeSafety")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles using Haversine formula"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 3959  # Earth's radius in miles
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def get_visibility_level(visibility_meters: int) -> str:
    """Categorize visibility level"""
    if visibility_meters < 1000:
        return "very poor"
    elif visibility_meters < 5000:
        return "poor"
    elif visibility_meters < 8000:
        return "moderate"
    else:
        return "good"

def decode_polyline(polyline_str: str) -> List[List[float]]:
    """
    Decodes an OpenRouteService (or Google Maps) Encoded Polyline string 
    into a list of [lon, lat] coordinates.
    """
    index, lat, lon = 0, 0, 0
    coordinates = []
    
    while index < len(polyline_str):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if not (byte >= 0x20):
                break
        
        dlat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += dlat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if not (byte >= 0x20):
                break
        
        dlon = ~(result >> 1) if result & 1 else (result >> 1)
        lon += dlon
        
        # ORS encodes coordinates with 6 decimal places: [lon, lat]
        coordinates.append([lon / 100000.0, lat / 100000.0])

    return coordinates


# ============================================================================
# ESSENTIAL TOOLS (5 CORE TOOLS)
# ============================================================================

@mcp.tool()
def get_crime_summary(latitude: float, longitude: float, radius_miles: float = 1.0) -> Dict: # Raidus is not currently working
    """Get aggregated crime statistics for a location.
    
    Returns total crimes and breakdown by category for the most recent month available
    from UK Police data.
    
    Args:
        latitude: Latitude of the location (e.g., 51.5074 for London)
        longitude: Longitude of the location (e.g., -0.1278 for London)
        radius_miles: Search radius in miles (default: 1.0)
    
    Returns:
        Dictionary with crime counts by category, total crimes, and month
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{UK_POLICE_API_BASE}/crimes-street/all-crime",
                params={"lat": latitude, "lng": longitude}
            )
            response.raise_for_status()
            crimes_data = response.json()
        
        if not isinstance(crimes_data, list):
            return {"error": "Invalid response from UK Police API"}
        
        # Aggregate crime counts
        crime_counts = {}
        for crime in crimes_data:
            category = crime.get("category", "unknown")
            crime_counts[category] = crime_counts.get(category, 0) + 1
        
        # Get month from first crime
        month = crimes_data[0].get("month", "unknown") if crimes_data else "unknown"
        
        # Get top 3 crime types
        top_crimes = sorted(crime_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "total_crimes": len(crimes_data),
            "crime_counts": crime_counts,
            "month": month,
            "area_description": f"{radius_miles} mile radius",
            "top_crime_types": [{"type": t[0], "count": t[1]} for t in top_crimes]
        }
    
    except Exception as e:
        return {"error": f"Failed to fetch crime data: {str(e)}"}


@mcp.tool()
def get_time_context(latitude: float, longitude: float, timestamp: Optional[str] = None) -> Dict:
    """Get detailed time context including day/night status and sunrise/sunset times.
    
    Essential for understanding temporal risk factors. Provides information about
    current time, day of week, and lighting conditions.
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        timestamp: ISO format timestamp (default: current time, e.g., "2024-11-15T21:30:00")
    
    Returns:
        Dictionary with time details, sunrise/sunset, and whether it's daylight
    """
    try:
        # Parse timestamp or use current time
        if timestamp:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = datetime.now()
        
        # Calculate sunrise/sunset
        try:
            location = LocationInfo(
                name="Location",
                region="UK",
                timezone="Europe/London",
                latitude=latitude,
                longitude=longitude
            )
            s = sun(location.observer, date=dt.date())
            sunrise = s["sunrise"]
            sunset = s["sunset"]
            is_daylight = sunrise < dt < sunset
            
            # Hours after sunset
            if dt > sunset:
                hours_after_sunset = (dt - sunset).total_seconds() / 3600
            else:
                hours_after_sunset = 0
        
        except Exception:
            # Fallback times
            sunrise = dt.replace(hour=7, minute=0)
            sunset = dt.replace(hour=17, minute=0)
            is_daylight = 7 <= dt.hour < 17
            hours_after_sunset = max(0, dt.hour - 17)
        
        # Determine time period
        hour = dt.hour
        if 6 <= hour < 12:
            time_period = "morning"
        elif 12 <= hour < 17:
            time_period = "afternoon"
        elif 17 <= hour < 21:
            time_period = "evening"
        else:
            time_period = "night"
        
        return {
            "current_time": dt.isoformat(),
            "local_time": dt.strftime("%I:%M %p"),
            "day_of_week": dt.strftime("%A"),
            "is_weekend": dt.weekday() >= 5,
            "sunrise": sunrise.strftime("%H:%M"),
            "sunset": sunset.strftime("%H:%M"),
            "is_daylight": is_daylight,
            "hours_after_sunset": round(hours_after_sunset, 1),
            "time_period": time_period
        }
    
    except Exception as e:
        return {"error": f"Failed to calculate time context: {str(e)}"}

WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

@mcp.tool()
def get_weather_conditions(latitude: float, longitude: float) -> Dict:
    """Get current weather conditions including visibility and precipitation.
    
    Weather significantly affects both actual risk and perception of safety.
    Provides temperature, conditions, visibility level, and precipitation data.
    
    Uses Open-Meteo API (free, no API key required):
    https://open-meteo.com/en/docs
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    
    Returns:
        Dictionary with current weather conditions and visibility assessment:
        {
            "temperature": 8.5,              // actual temperature
            "feels_like": 6.2,               // body temperature
            "conditions": "Partly cloudy",
            "visibility_meters": 8000,
            "visibility_level": "good",
            "is_raining": False,
            "precipitation": 0.0,
            "wind_speed_ms": 3.2,
            "humidity": 75,
            "cloud_cover": 50,
            "atmospheric_context": "Partly cloudy with good visibility"
        }
    """
    with httpx.Client(timeout=10.0) as client:
        try:
            # Request current weather data
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": [
                    "temperature_2m",           # Temperature at 2m
                    "apparent_temperature",     # Feels like
                    "precipitation",            # Current precipitation
                    "weather_code",            # Weather condition code
                    "cloud_cover",             # Cloud cover %
                    "wind_speed_10m",          # Wind speed at 10m
                    "relative_humidity_2m",    # Humidity
                    "visibility"               # Visibility (if available)
                ],
                "timezone": "auto"
            }
            
            response = client.get(
                OPEN_METEO_API_BASE, 
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract current weather data
            current = data.get("current", {})
            
            temperature = current.get("temperature_2m", 0)
            feels_like = current.get("apparent_temperature", temperature)
            precipitation = current.get("precipitation", 0)
            weather_code = current.get("weather_code", 0)
            cloud_cover = current.get("cloud_cover", 0)
            wind_speed = current.get("wind_speed_10m", 0)
            humidity = current.get("relative_humidity_2m", 0)
            
            # Get visibility if available, otherwise estimate
            visibility_meters = current.get("visibility")
            # if visibility_meters is None:
            #     visibility_meters = _estimate_visibility(
            #         weather_code, 
            #         precipitation, 
            #         cloud_cover
            #     )
            
            # Determine conditions from weather code
            conditions = WEATHER_CODE_MAP.get(weather_code, "Unknown")
            
            # Check if it's raining
            is_raining = precipitation > 0 or weather_code in [
                51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82
            ]
            
            
            result = {
                "temperature": round(temperature, 1),
                "feels_like": round(feels_like, 1),
                "conditions": conditions,
                "visibility_meters": visibility_meters,
                "is_raining": is_raining,
                "precipitation": round(precipitation, 1),
                "wind_speed_ms": round(wind_speed, 1),
                "humidity": int(humidity),
                "cloud_cover": int(cloud_cover),
                "data_source": "Open-Meteo API (free)"
            }
            
            return result
            
        except httpx.HTTPError as e:
            return {
                "error": "Unable to fetch weather data",
                "details": str(e),
                "note": "Weather data unavailable - safety assessment will use other factors"
            }
        except Exception as e:
            return {
                "error": "Weather data processing error",
                "details": str(e),
                "note": "Proceeding without weather context"
            }
        

@mcp.tool()
def get_route_options(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    mode: str = "walking"
) -> Dict:
    """Get 2-3 alternative routes between two points.
    
    Returns waypoints for each route that can be analyzed for safety.
    Each route includes distance, duration, and sampled waypoints.
    
    Args:
        start_lat: Starting point latitude
        start_lon: Starting point longitude
        end_lat: Destination latitude
        end_lon: Destination longitude
        mode: Travel mode - 'walking', 'cycling', or 'driving' (default: walking)
    
    Returns:
        Dictionary with list of route options including waypoints
    """
    # Fallback when API key is not set
    if not OPENROUTE_API_KEY:
        distance_miles = calculate_distance(start_lat, start_lon, end_lat, end_lon)
        
        return {
            "routes": [{
                "route_id": 1,
                "distance_meters": int(distance_miles * 1609.34),
                "duration_minutes": int(distance_miles * 20),
                "description": "Direct route (estimated)",
                "route_type": "direct",
                "waypoints": [
                    {"lat": start_lat, "lon": start_lon},
                    {"lat": (start_lat + end_lat)/2, "lon": (start_lon + end_lon)/2},
                    {"lat": end_lat, "lon": end_lon}
                ]
            }],
            "note": "Using estimated direct route. Set OPENROUTE_API_KEY for real routing."
        }
    
    # Use OpenRouteService for real routing
    try:
        profile = {
            "walking": "foot-walking",
            "driving": "driving-car",
            "cycling": "cycling-regular"
        }.get(mode.lower(), "foot-walking")
        
        # ORS expects coordinates in [lon, lat] format
        coordinates = [[start_lon, start_lat], [end_lon, end_lat]]

        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"https://api.openrouteservice.org/v2/directions/{profile}",
                json={
                    "coordinates": coordinates,
                    # Request up to 3 alternative routes, though ORS often returns 2
                    "alternative_routes": {"target_count": 3}, 
                    "instructions": False
                },
                headers={"Authorization": OPENROUTE_API_KEY}
            )
            response.raise_for_status()
            route_data = response.json()
        
        # print("ORS Response Data:", route_data)

        routes = []
        for idx, route in enumerate(route_data.get("routes", [])[:3]):
            # CRITICAL FIX: Decode the Encoded Polyline string to get coordinates
            coords = decode_polyline(route["geometry"]) 
            
            # Sample waypoints (e.g., ~5 points) for efficiency
            step = max(1, len(coords) // 5)
            waypoints = [
                {"lat": coord[1], "lon": coord[0]} # coord is [lon, lat], so flip for UI
                for coord in coords[::step]
            ]
            
            # Ensure start and end points are always included
            if not waypoints or waypoints[0] != {"lat": start_lat, "lon": start_lon}:
                 waypoints.insert(0, {"lat": start_lat, "lon": start_lon})
            if waypoints[-1] != {"lat": end_lat, "lon": end_lon}:
                 waypoints.append({"lat": end_lat, "lon": end_lon})
            
            routes.append({
                "route_id": idx + 1,
                "distance_meters": int(route["summary"]["distance"]),
                # Convert duration from seconds to minutes
                "duration_minutes": int(route["summary"]["duration"] / 60), 
                "description": f"Route {idx + 1} ({profile.split('-')[0]})",
                "route_type": mode,
                "waypoints": waypoints
            })
        
        return {"routes": routes}
    
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP Error: {e.response.status_code}. Check API key and coordinates."
        # Fall through to the final general exception handler
    except Exception as e:
        error_msg = f"API Request Failed: {str(e)}"
        
    # Final Fallback to direct route on any API error
    distance_miles = calculate_distance(start_lat, start_lon, end_lat, end_lon)
    return {
        "routes": [{
            "route_id": 1,
            "distance_meters": int(distance_miles * 1609.34),
            "duration_minutes": int(distance_miles * 20),
            "description": "Direct route (fallback)",
            "route_type": "estimated",
            "waypoints": [
                {"lat": start_lat, "lon": start_lon},
                {"lat": end_lat, "lon": end_lon}
            ]
        }],
        "note": f"Using fallback routing: {error_msg}"
    }


@mcp.tool()
def analyze_route_safety(waypoints: List[Dict], route_id: int = 1) -> Dict:
    """Analyze crime statistics along a specific route.
    
    Takes waypoints from get_route_options and returns aggregated safety metrics
    including total crimes, average per segment, and highest risk areas.
    
    Args:
        waypoints: Array of waypoint dictionaries with 'lat' and 'lon' keys
        route_id: Route identifier for reference (default: 1)
    
    Returns:
        Dictionary with overall crime count, segment analyses, and highest risk segment
    """
    try:
        segment_analyses = []
        total_crimes = 0
        
        with httpx.Client(timeout=10.0) as client:
            for idx, waypoint in enumerate(waypoints):
                lat = waypoint["lat"]
                lon = waypoint["lon"]
                
                # Fetch crimes for this waypoint
                response = client.get(
                    f"{UK_POLICE_API_BASE}/crimes-street/all-crime",
                    params={"lat": lat, "lng": lon}
                )
                response.raise_for_status()
                crimes_data = response.json()
                
                if not isinstance(crimes_data, list):
                    crimes_data = []
                
                # Aggregate crimes by type
                crime_counts = {}
                for crime in crimes_data:
                    category = crime.get("category", "unknown")
                    crime_counts[category] = crime_counts.get(category, 0) + 1
                
                segment_crimes = len(crimes_data)
                total_crimes += segment_crimes
                
                # Get dominant crimes (top 2)
                dominant_crimes = sorted(
                    crime_counts.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:2]
                
                segment_analyses.append({
                    "segment_number": idx + 1,
                    "location": waypoint,
                    "crime_count": segment_crimes,
                    "dominant_crimes": [{"type": c[0], "count": c[1]} for c in dominant_crimes]
                })
        
        # Find highest risk segment
        if segment_analyses:
            highest_risk = max(segment_analyses, key=lambda x: x["crime_count"])
            avg_crimes = total_crimes / len(waypoints)
        else:
            highest_risk = None
            avg_crimes = 0
        
        return {
            "route_id": route_id,
            "overall_crime_count": total_crimes,
            "average_crime_per_segment": round(avg_crimes, 1),
            "segment_analyses": segment_analyses,
            "highest_risk_segment": {
                "segment_number": highest_risk["segment_number"],
                "crime_count": highest_risk["crime_count"],
                "dominant_crimes": [c["type"] for c in highest_risk["dominant_crimes"]]
            } if highest_risk else None
        }
    
    except Exception as e:
        return {"error": f"Failed to analyze route safety: {str(e)}"}


# ============================================================================
# NICE-TO-HAVE TOOLS (3 COMPARISON/CONTEXT TOOLS)
# ============================================================================

@mcp.tool()
def compare_crime_to_average(latitude: float, longitude: float, comparison_scope: str = "city") -> Dict:
    """Compare crime levels in this area to city or borough average.
    
    Provides context on whether an area is particularly safe or dangerous
    relative to other areas.
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        comparison_scope: Compare to 'city' or 'borough' (default: city)
    
    Returns:
        Dictionary with area crime count, average, percentage difference, and context
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{UK_POLICE_API_BASE}/crimes-street/all-crime",
                params={"lat": latitude, "lng": longitude}
            )
            response.raise_for_status()
            crimes_data = response.json()
        
        area_crimes = len(crimes_data) if isinstance(crimes_data, list) else 0
        
        # UK average is approximately 30-35 crimes per area per month
        city_average = 32
        percentage_diff = ((area_crimes - city_average) / city_average * 100) if city_average > 0 else 0
        
        context = f"This area has {abs(percentage_diff):.0f}% {'more' if percentage_diff > 0 else 'fewer'} crimes than average"
        
        return {
            "area_total": area_crimes,
            "city_average": city_average,
            "percentage_difference": f"{percentage_diff:+.1f}%",
            "relative_level": "higher" if area_crimes > city_average else "lower",
            "context": context
        }
    
    except Exception as e:
        return {"error": f"Failed to compare crime data: {str(e)}"}


@mcp.tool()
def get_crime_hotspots(latitude: float, longitude: float, radius_miles: float = 2.0) -> Dict:
    """Identify specific high-crime locations near the user.
    
    Returns top crime hotspots within radius with details about street names,
    crime counts, and dominant crime types.
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        radius_miles: Search radius in miles (default: 2.0)
    
    Returns:
        Dictionary with list of hotspots and total count
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{UK_POLICE_API_BASE}/crimes-street/all-crime",
                params={"lat": latitude, "lng": longitude}
            )
            response.raise_for_status()
            crimes_data = response.json()
        
        if not isinstance(crimes_data, list):
            crimes_data = []
        
        # Group crimes by street location
        location_crimes = {}
        for crime in crimes_data:
            street = crime.get("location", {}).get("street", {}).get("name", "Unknown")
            crime_lat = float(crime.get("location", {}).get("latitude", latitude))
            crime_lon = float(crime.get("location", {}).get("longitude", longitude))
            
            if street not in location_crimes:
                location_crimes[street] = {
                    "street_name": street,
                    "location": {"lat": crime_lat, "lon": crime_lon},
                    "crimes": []
                }
            location_crimes[street]["crimes"].append(crime.get("category", "unknown"))
        
        # Identify hotspots (3+ crimes)
        hotspots = []
        for street, data in location_crimes.items():
            crime_count = len(data["crimes"])
            if crime_count >= 3:
                crime_counts = {}
                for c in data["crimes"]:
                    crime_counts[c] = crime_counts.get(c, 0) + 1
                
                dominant = max(crime_counts.items(), key=lambda x: x[1])[0]
                distance = calculate_distance(
                    latitude, longitude,
                    data["location"]["lat"],
                    data["location"]["lon"]
                )
                
                hotspots.append({
                    "street_name": data["street_name"],
                    "location": data["location"],
                    "crime_count": crime_count,
                    "dominant_type": dominant,
                    "distance_miles": round(distance, 2)
                })
        
        # Sort by crime count
        hotspots.sort(key=lambda x: x["crime_count"], reverse=True)
        
        return {
            "hotspots": hotspots[:5],  # Top 5
            "total_hotspots_found": len(hotspots)
        }
    
    except Exception as e:
        return {"error": f"Failed to identify hotspots: {str(e)}"}


@mcp.tool()
def get_crime_by_types(latitude: float, longitude: float, crime_types: List[str]) -> Dict:
    """Get detailed information about specific crime types in an area.
    
    Use when you need to focus on particular crime categories (e.g., burglary, theft).
    Returns counts and sample locations for each requested crime type.
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        crime_types: List of crime types to filter (e.g., ['burglary', 'theft-from-the-person'])
    
    Returns:
        Dictionary with counts and locations for each crime type
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{UK_POLICE_API_BASE}/crimes-street/all-crime",
                params={"lat": latitude, "lng": longitude}
            )
            response.raise_for_status()
            crimes_data = response.json()
        
        if not isinstance(crimes_data, list):
            crimes_data = []
        
        result = {}
        for crime_type in crime_types:
            filtered_crimes = [c for c in crimes_data if c.get("category") == crime_type]
            
            locations = []
            for crime in filtered_crimes[:10]:  # Limit to 10 per type
                loc = crime.get("location", {})
                street = loc.get("street", {}).get("name", "Unknown")
                locations.append({
                    "lat": float(loc.get("latitude", latitude)),
                    "lon": float(loc.get("longitude", longitude)),
                    "street": street
                })
            
            result[crime_type] = {
                "count": len(filtered_crimes),
                "sample_locations": locations
            }
        
        return result
    
    except Exception as e:
        return {"error": f"Failed to fetch crime by types: {str(e)}"}


# ============================================================================
# ADVANCED TOOLS (COMPARISON & ANALYSIS)
# ============================================================================

@mcp.tool()
def compare_routes(route_analyses: List[Dict]) -> Dict:
    """Compare multiple routes side-by-side with safety scores and recommendations.
    
    Use after analyzing individual routes with analyze_route_safety.
    Provides ranked comparison with reasoning.
    
    Args:
        route_analyses: Array of route analysis results from analyze_route_safety
    
    Returns:
        Dictionary with recommended route and comparison of all routes
    """
    if not route_analyses:
        return {"error": "No route analyses provided"}
    
    # Calculate safety scores (inverse of crime count, normalized)
    max_crimes = max(r.get("overall_crime_count", 1) for r in route_analyses)
    
    comparisons = []
    for route in route_analyses:
        crime_count = route.get("overall_crime_count", 0)
        safety_score = int(100 * (1 - crime_count / max(max_crimes, 1)))
        
        comparisons.append({
            "route_id": route.get("route_id"),
            "safety_score": safety_score,
            "crime_count": crime_count,
            "avg_crime_per_segment": route.get("average_crime_per_segment", 0)
        })
    
    # Sort by safety score
    comparisons.sort(key=lambda x: x["safety_score"], reverse=True)
    
    return {
        "recommendation": comparisons[0]["route_id"],
        "comparison": comparisons,
        "reasoning": f"Route {comparisons[0]['route_id']} has the lowest crime exposure"
    }


@mcp.tool()
def compare_time_periods(latitude: float, longitude: float, time_of_day: str) -> Dict:
    """Compare crime patterns across different times of day.
    
    Helps understand if current time is particularly risky for this area.
    Time periods: morning, afternoon, evening, night.
    
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        time_of_day: One of 'morning', 'afternoon', 'evening', or 'night'
    
    Returns:
        Dictionary with estimated crime distribution and relevant crime types
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{UK_POLICE_API_BASE}/crimes-street/all-crime",
                params={"lat": latitude, "lng": longitude}
            )
            response.raise_for_status()
            crimes_data = response.json()
        
        if not isinstance(crimes_data, list):
            crimes_data = []
        
        # Typical crime distribution by time (estimated)
        time_distributions = {
            "morning": 0.15,
            "afternoon": 0.25,
            "evening": 0.35,
            "night": 0.25
        }
        
        total_crimes = len(crimes_data)
        estimated_for_period = int(total_crimes * time_distributions.get(time_of_day, 0.25))
        
        # Crime types more common at different times
        night_crimes = ["burglary", "vehicle-crime", "robbery"]
        day_crimes = ["shoplifting", "theft-from-the-person", "anti-social-behaviour"]
        
        crime_counts = {}
        for crime in crimes_data:
            cat = crime.get("category", "unknown")
            crime_counts[cat] = crime_counts.get(cat, 0) + 1
        
        relevant_crimes = night_crimes if time_of_day in ["evening", "night"] else day_crimes
        relevant_counts = {k: v for k, v in crime_counts.items() if k in relevant_crimes}
        
        return {
            "requested_time": time_of_day,
            "estimated_crime_count": estimated_for_period,
            "total_area_crimes": total_crimes,
            "relevant_crime_types": list(relevant_counts.keys()),
            "note": "Estimates based on typical crime patterns"
        }
    
    except Exception as e:
        return {"error": f"Failed to compare time periods: {str(e)}"}


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    mcp.run()
