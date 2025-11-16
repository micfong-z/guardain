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

_route_cache = {}  # Temporary storage for route data
_cache_counter = 0

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
# ESSENTIAL TOOLS (6 CORE TOOLS)
# ============================================================================

@mcp.tool()
def get_crime_summary(latitude: float, longitude: float):
    """Get aggregated crime statistics for a location.

    Returns total crimes and breakdown by category for the most recent month available
    from UK Police data.

    Args:
        latitude: Latitude of the location (e.g., 51.5074 for London)
        longitude: Longitude of the location (e.g., -0.1278 for London)

    Returns:
        A text message containing:
        1. Calculated Risk Index (WITHOUT weights from the weather and time)
        2. Total number of crimes last month
        3. Top 3 types of crime with the highest individual risk index
    """

    CRIME_FACTOR = {"robbery": 9,
                    "violent-crime": 9,
                    "burglary": 5,
                    "possession-of-weapons": 5,
                    "vehicle-crime": 3,
                    "theft-from-the-person": 3}

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

        crime_score = {}
        risk_index = 0
        for key, val in  crime_counts.items():
            if key in CRIME_FACTOR:
                crime_score[key] = val * CRIME_FACTOR[key]
                risk_index += val * CRIME_FACTOR[key]
            else:
                crime_score[key] = val * 2
                risk_index += val * 2

        # Get top 3 crime scores
        top_crimes = sorted(crime_score.items(), key=lambda x: x[1], reverse=True)[:3]

        match len(top_crimes):
            case 0: top_info = "No crime in this region"
            case 1: top_info = f"""{top_crimes[0][0]}: {crime_counts[top_crimes[0][0]]} times"""
            case 2: top_info = f"""{top_crimes[0][0]}: {crime_counts[top_crimes[0][0]]} times
{top_crimes[1][0]}: {crime_counts[top_crimes[1][0]]} times"""
            case 3: top_info = f"""{top_crimes[0][0]}: {crime_counts[top_crimes[0][0]]} times
{top_crimes[1][0]}: {crime_counts[top_crimes[1][0]]} times
{top_crimes[2][0]}: {crime_counts[top_crimes[2][0]]} times"""

        combined_info = f"""**Calculated risk_index is {risk_index}**
There are **{len(crimes_data)}** criminals in total.
A few types (max 3) of criminals with top criminal scores and corresponding number of occurrence this month:
{top_info}"""

        return combined_info

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
def get_user_context(mode_of_transport: str = "walking", 
                     traveling_alone: bool = True,
                     has_valuables: bool = False) -> Dict:
    """Get user's current situation context.
    
    Personalizes advice based on how the user is traveling and their situation.
    
    Args:
        mode_of_transport: 'walking', 'cycling', 'driving'
        traveling_alone: Whether user is alone or with others
        has_valuables: Whether carrying valuable items
    
    Returns:
        Risk modifiers based on user's specific situation
    """
    risk_multiplier = 1.0
    factors = []
    
    if traveling_alone:
        risk_multiplier *= 1.2
        factors.append("traveling alone increases vulnerability")
    
    if has_valuables:
        risk_multiplier *= 1.3
        factors.append("carrying valuables increases theft risk")
    
    if mode_of_transport == "cycling":
        factors.append("vehicle crime risk relevant")
    
    return {
        "mode": mode_of_transport,
        "alone": traveling_alone,
        "risk_multiplier": round(risk_multiplier, 2),
        "relevant_factors": factors,
        "advice_modifier": "extra caution" if risk_multiplier > 1.3 else "normal caution"
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
    
    Returns route IDs that can be used with analyze_route_safety_by_id().
    Waypoints are cached server-side to avoid data copying errors between tools.
    
    Args:
        start_lat: Starting point latitude
        start_lon: Starting point longitude
        end_lat: Destination latitude
        end_lon: Destination longitude
        mode: Travel mode - 'walking', 'cycling', or 'driving' (default: walking)
    
    Returns:
        Dictionary with route options. Use route_id with analyze_route_safety_by_id()
    """
    global _cache_counter, _route_cache
    
    # Fallback when API key is not set
    if not OPENROUTE_API_KEY:
        distance_miles = calculate_distance(start_lat, start_lon, end_lat, end_lon)
        
        # Generate route ID and cache waypoints
        route_id = f"route_{_cache_counter}_0"
        _cache_counter += 1
        
        waypoints = [
            {"lat": start_lat, "lon": start_lon},
            {"lat": (start_lat + end_lat)/2, "lon": (start_lon + end_lon)/2},
            {"lat": end_lat, "lon": end_lon}
        ]
        _route_cache[route_id] = waypoints
        
        return {
            "routes": [{
                "route_id": route_id,  # String ID instead of integer
                "distance_meters": int(distance_miles * 1609.34),
                "duration_minutes": int(distance_miles * 20),
                "description": "Direct route (estimated)",
                "route_type": "direct",
                "waypoint_count": len(waypoints)  # Show count, not actual waypoints
            }],
            "note": "Using estimated direct route. Set OPENROUTE_API_KEY for real routing.",
            "usage": f"Use analyze_route_safety_by_id('{route_id}') to analyze safety"
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
                    "alternative_routes": {"target_count": 3}, 
                    "instructions": False
                },
                headers={"Authorization": OPENROUTE_API_KEY}
            )
            response.raise_for_status()
            route_data = response.json()

        routes = []
        for idx, route in enumerate(route_data.get("routes", [])[:3]):
            # Generate unique route ID
            route_id = f"route_{_cache_counter}_{idx}"
            _cache_counter += 1
            
            # Decode the Encoded Polyline string to get coordinates
            coords = decode_polyline(route["geometry"]) 
            
            # Sample waypoints (e.g., ~5 points) for efficiency
            step = max(1, len(coords) // 5)
            waypoints = [
                {"lat": coord[1], "lon": coord[0]}
                for coord in coords[::step]
            ]
            
            # Ensure start and end points are always included
            if not waypoints or waypoints[0] != {"lat": start_lat, "lon": start_lon}:
                waypoints.insert(0, {"lat": start_lat, "lon": start_lon})
            if waypoints[-1] != {"lat": end_lat, "lon": end_lon}:
                waypoints.append({"lat": end_lat, "lon": end_lon})
            
            # CACHE THE WAYPOINTS
            _route_cache[route_id] = waypoints
            
            routes.append({
                "route_id": route_id,  # String ID
                "distance_meters": int(route["summary"]["distance"]),
                "duration_minutes": int(route["summary"]["duration"] / 60), 
                "description": f"Route {idx + 1} ({profile.split('-')[0]})",
                "route_type": mode,
                "waypoint_count": len(waypoints)  # Show count instead of waypoints
            })
        
        return {
            "routes": routes,
            "usage": "Use analyze_route_safety_by_id(route_id) to analyze each route's safety"
        }
    
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP Error: {e.response.status_code}. Check API key and coordinates."
    except Exception as e:
        error_msg = f"API Request Failed: {str(e)}"
        
    # Final Fallback to direct route on any API error
    route_id = f"route_{_cache_counter}_fallback"
    _cache_counter += 1
    
    waypoints = [
        {"lat": start_lat, "lon": start_lon},
        {"lat": end_lat, "lon": end_lon}
    ]
    _route_cache[route_id] = waypoints
    
    distance_miles = calculate_distance(start_lat, start_lon, end_lat, end_lon)
    return {
        "routes": [{
            "route_id": route_id,
            "distance_meters": int(distance_miles * 1609.34),
            "duration_minutes": int(distance_miles * 20),
            "description": "Direct route (fallback)",
            "route_type": "estimated",
            "waypoint_count": len(waypoints)
        }],
        "note": f"Using fallback routing: {error_msg}",
        "usage": f"Use analyze_route_safety_by_id('{route_id}') to analyze safety"
    }


@mcp.tool()
def analyze_route_safety_by_id(route_id: str) -> Dict:
    """Analyze crime statistics for a route using its ID.
    
    Use the route_id returned by get_route_options(). Waypoints are retrieved
    from server-side cache automatically, avoiding float precision issues.
    
    Args:
        route_id: Route identifier from get_route_options (e.g., "route_0_1")
    
    Returns:
        Dictionary with overall crime count, segment analyses, and highest risk segment
    """
    # Retrieve cached waypoints
    if route_id not in _route_cache:
        return {
            "error": f"Route ID '{route_id}' not found in cache",
            "note": "Route may have expired. Call get_route_options() again.",
            "available_routes": list(_route_cache.keys())
        }
    
    waypoints = _route_cache[route_id]
    
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
            "segment_count": len(waypoints),
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
# HELPER TOOLS FOR CACHE MANAGEMENT
# ============================================================================

@mcp.tool()
def list_cached_routes() -> Dict:
    """List all currently cached routes.
    
    Useful for debugging or seeing which routes are available for analysis.
    
    Returns:
        Dictionary with list of cached route IDs
    """
    return {
        "cached_routes": list(_route_cache.keys()),
        "total_cached": len(_route_cache),
        "note": "Use analyze_route_safety_by_id() with any of these route IDs"
    }


@mcp.tool()
def clear_route_cache() -> Dict:
    """Clear the route cache to free memory.
    
    Call this after you're done analyzing routes, or if you want to start fresh.
    
    Returns:
        Status of cache clearing operation
    """
    global _route_cache, _cache_counter
    
    cache_size = len(_route_cache)
    _route_cache = {}
    # Don't reset counter to keep IDs unique across cache clears
    
    return {
        "status": "success",
        "cleared_routes": cache_size,
        "message": "Route cache cleared successfully"
    }


# ============================================================================
# NICE-TO-HAVE TOOLS (4 COMPARISON/CONTEXT TOOLS)
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
def list_crime_types() -> Dict:
    """Get all valid crime type categories from UK Police data.
    
    Use this to see what crime types you can filter with get_crime_by_types().
    
    Returns:
        Dictionary with crime types, descriptions, and common aliases
    """
    return {
        "crime_types": [
            {
                "id": "anti-social-behaviour",
                "name": "Anti-Social Behaviour",
                "aliases": ["antisocial", "asb", "nuisance"]
            },
            {
                "id": "bicycle-theft",
                "name": "Bicycle Theft",
                "aliases": ["bike theft", "stolen bike", "bicycle"]
            },
            {
                "id": "burglary",
                "name": "Burglary",
                "aliases": ["breaking and entering", "break-in"]
            },
            {
                "id": "criminal-damage-arson",
                "name": "Criminal Damage & Arson",
                "aliases": ["vandalism", "arson", "property damage"]
            },
            {
                "id": "drugs",
                "name": "Drugs",
                "aliases": ["drug offences", "narcotics"]
            },
            {
                "id": "other-theft",
                "name": "Other Theft",
                "aliases": ["theft", "stealing"]
            },
            {
                "id": "possession-of-weapons",
                "name": "Possession of Weapons",
                "aliases": ["weapons", "knife crime"]
            },
            {
                "id": "public-order",
                "name": "Public Order",
                "aliases": ["public disorder", "disturbance"]
            },
            {
                "id": "robbery",
                "name": "Robbery",
                "aliases": ["mugging", "armed robbery"]
            },
            {
                "id": "shoplifting",
                "name": "Shoplifting",
                "aliases": ["retail theft", "shop theft"]
            },
            {
                "id": "theft-from-the-person",
                "name": "Theft from the Person",
                "aliases": ["pickpocketing", "purse snatching", "personal theft"]
            },
            {
                "id": "vehicle-crime",
                "name": "Vehicle Crime",
                "aliases": ["car theft", "vehicle theft", "auto crime"]
            },
            {
                "id": "violent-crime",
                "name": "Violent Crime",
                "aliases": ["violence", "assault", "violent offences"]
            },
            {
                "id": "other-crime",
                "name": "Other Crime",
                "aliases": ["miscellaneous", "other offences"]
            }
        ],
        "note": "Use the 'id' field when calling get_crime_by_types()"
    }

@mcp.tool()
def get_crime_by_types(latitude: float, longitude: float, crime_types: List[str]) -> Dict:
    """Get detailed information about specific crime types in an area.
    
    Use when you need to focus on particular crime categories (e.g., burglary, theft).
    Returns counts and sample locations for each requested crime type.
    Please first call list_crime_types() before use.
    
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
def compare_routes_by_id(route_ids: List[str]) -> Dict:
    """Compare multiple routes by their IDs (RECOMMENDED).
    
    Automatically analyzes each route and provides a ranked safety comparison.
    Use this after calling get_route_options() to compare all routes at once.
    
    Args:
        route_ids: List of route IDs from get_route_options (e.g., ["route_0_0", "route_0_1"])
    
    Returns:
        Dictionary with recommended route, detailed comparison, and reasoning
    
    Example:
        routes = get_route_options(51.53, -0.12, 51.54, -0.14)
        route_ids = [r["route_id"] for r in routes["routes"]]
        comparison = compare_routes_by_id(route_ids)
    """
    if not route_ids:
        return {"error": "No route IDs provided"}
    
    # Analyze each route automatically
    route_analyses = []
    failed_routes = []
    
    for route_id in route_ids:
        analysis = analyze_route_safety_by_id(route_id)
        if "error" in analysis:
            failed_routes.append({"route_id": route_id, "error": analysis["error"]})
        else:
            route_analyses.append(analysis)
    
    if not route_analyses:
        return {
            "error": "No valid routes to compare",
            "failed_routes": failed_routes,
            "note": "All route analyses failed. Check if route IDs are valid."
        }
    
    # Calculate safety scores (inverse of crime count, normalized)
    max_crimes = max(r.get("overall_crime_count", 1) for r in route_analyses)
    min_crimes = min(r.get("overall_crime_count", 0) for r in route_analyses)
    
    comparisons = []
    for route in route_analyses:
        crime_count = route.get("overall_crime_count", 0)
        avg_crime = route.get("average_crime_per_segment", 0)
        
        # Calculate safety score (0-100, higher is safer)
        if max_crimes > 0:
            safety_score = int(100 * (1 - crime_count / max_crimes))
        else:
            safety_score = 100  # No crimes on any route
        
        # Determine risk level
        if safety_score >= 80:
            risk_level = "low"
        elif safety_score >= 60:
            risk_level = "moderate"
        elif safety_score >= 40:
            risk_level = "elevated"
        else:
            risk_level = "high"
        
        # Get highest risk segment info
        highest_risk = route.get("highest_risk_segment", {})
        
        comparisons.append({
            "route_id": route.get("route_id"),
            "safety_score": safety_score,
            "risk_level": risk_level,
            "crime_count": crime_count,
            "avg_crime_per_segment": avg_crime,
            "segment_count": route.get("segment_count", 0),
            "highest_risk_segment": highest_risk.get("segment_number") if highest_risk else None,
            "most_dangerous_segment_crimes": highest_risk.get("crime_count", 0) if highest_risk else 0
        })
    
    # Sort by safety score (highest first)
    comparisons.sort(key=lambda x: x["safety_score"], reverse=True)
    
    # Generate detailed reasoning
    best_route = comparisons[0]
    worst_route = comparisons[-1]
    
    crime_diff = worst_route["crime_count"] - best_route["crime_count"]
    crime_diff_pct = int((crime_diff / max(worst_route["crime_count"], 1)) * 100)
    
    reasoning_parts = [
        f"Route {best_route['route_id']} is the safest option with {best_route['crime_count']} total incidents",
        f"({best_route['risk_level']} risk level, safety score: {best_route['safety_score']}/100)"
    ]
    
    if len(comparisons) > 1:
        reasoning_parts.append(
            f"It has {crime_diff} fewer incidents than the riskiest route ({crime_diff_pct}% reduction)"
        )
    
    if best_route["most_dangerous_segment_crimes"] > 0:
        reasoning_parts.append(
            f"Watch out for segment {best_route['highest_risk_segment']} "
            f"which has {best_route['most_dangerous_segment_crimes']} incidents"
        )
    
    return {
        "recommendation": best_route["route_id"],
        "recommended_route": {
            "route_id": best_route["route_id"],
            "safety_score": best_route["safety_score"],
            "risk_level": best_route["risk_level"],
            "total_crimes": best_route["crime_count"]
        },
        "comparison": comparisons,
        "reasoning": ". ".join(reasoning_parts) + ".",
        "summary": {
            "total_routes_compared": len(comparisons),
            "safest_route": best_route["route_id"],
            "riskiest_route": worst_route["route_id"],
            "crime_count_range": {
                "min": min_crimes,
                "max": max_crimes
            }
        },
        "failed_routes": failed_routes if failed_routes else None
    }

@mcp.tool()
def get_and_compare_routes(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    mode: str = "walking"
) -> Dict:
    """Get routes and compare their safety in one call (CONVENIENCE FUNCTION).
    
    This is a convenience function that combines get_route_options() and 
    compare_routes_by_id() into a single call. Perfect for quick safety checks.
    
    Args:
        start_lat: Starting point latitude
        start_lon: Starting point longitude  
        end_lat: Destination latitude
        end_lon: Destination longitude
        mode: Travel mode - 'walking', 'cycling', or 'driving'
    
    Returns:
        Dictionary with routes, safety comparison, and recommendation
    
    Example:
        result = get_and_compare_routes(51.5308, -0.1238, 51.5390, -0.1426)
        recommended_route = result["recommendation"]
    """
    # Step 1: Get routes
    routes_result = get_route_options(start_lat, start_lon, end_lat, end_lon, mode)
    
    if "error" in routes_result:
        return routes_result
    
    routes = routes_result.get("routes", [])
    
    if not routes:
        return {"error": "No routes found"}
    
    # Step 2: Extract route IDs
    route_ids = [route["route_id"] for route in routes]
    
    # Step 3: Compare routes
    comparison_result = compare_routes_by_id(route_ids)
    
    if "error" in comparison_result:
        return comparison_result
    
    # Step 4: Combine results with route details
    route_details = {}
    for route in routes:
        route_details[route["route_id"]] = {
            "distance_meters": route["distance_meters"],
            "duration_minutes": route["duration_minutes"],
            "description": route["description"],
            "route_type": route["route_type"]
        }
    
    # Add route details to comparison
    for comparison in comparison_result["comparison"]:
        route_id = comparison["route_id"]
        if route_id in route_details:
            comparison.update(route_details[route_id])
    
    return {
        "routes": comparison_result["comparison"],  # Routes with full details + safety
        "recommendation": comparison_result["recommendation"],
        "recommended_route_details": route_details.get(comparison_result["recommendation"]),
        "reasoning": comparison_result["reasoning"],
        "summary": comparison_result["summary"],
        "note": "This is a combined result of route finding and safety analysis"
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
