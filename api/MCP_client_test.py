import asyncio
import os
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

import time

from datetime import datetime
import httpx
from astral import LocationInfo
from astral.sun import sun

load_dotenv()  # load environment variables from .env
UK_POLICE_API_BASE = "https://data.police.uk/api"
OPEN_METEO_API_BASE = "https://api.open-meteo.com/v1/forecast" # ?latitude=52.52&longitude=13.41&hourly=temperature_2m
# OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY", "")

_route_cache = {}  # Temporary storage for route data
_cache_counter = 0


def get_crime_summary(latitude: float, longitude: float,
                      radius_miles: float = 1.0) -> dict:  # Raidus is not currently working
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

def get_time_context(latitude: float, longitude: float, timestamp: Optional[str] = None) -> dict:
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

def get_weather_conditions(latitude: float, longitude: float) -> dict:
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
                    "temperature_2m",  # Temperature at 2m
                    "apparent_temperature",  # Feels like
                    "precipitation",  # Current precipitation
                    "weather_code",  # Weather condition code
                    "cloud_cover",  # Cloud cover %
                    "wind_speed_10m",  # Wind speed at 10m
                    "relative_humidity_2m",  # Humidity
                    "visibility"  # Visibility (if available)
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

def get_user_context(mode_of_transport: str = "walking",
                     traveling_alone: bool = True,
                     has_valuables: bool = False) -> dict:
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


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=os.environ.copy()
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        #print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self) -> str:

        current_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time()))
        latitude = 52.20641
        '''记得删掉！CHANGES_REQUIRED'''
        longitude = 0.12185
        '''记得删掉！CHANGES_REQUIRED'''

        # crime_context = get_crime_summary(latitude, longitude)
        time_context = get_time_context(latitude, longitude)
        weather_context = get_weather_conditions(latitude, longitude)
        user_context = get_user_context(traveling_alone=False)

        print(time_context)
        print(weather_context)
        print(user_context)

        # while True:
        #     pass


        SYSTEM_PROMPT = f"""# Real-Time Safety Assistant

You are a personal safety assistant that analyzes crime data and provides risk assessments with a **Risk Level (1-5)** and detailed crime summary.

## Pre-Loaded Context

Time & Lighting Context:
```json
[time_context]
```

Weather & Visibility Context:
```json
[weather_context]
```

User Situation Context:
```json
[user_context]
```

## Available Tools

- **get_crime_summary(lat, lon, radius_miles)**: Total crimes and breakdown by category
- **compare_crime_to_average(lat, lon)**: Compare to city average
- **get_crime_hotspots(lat, lon, radius_miles)**: Identify dangerous locations nearby
- **list_crime_types()**: Get valid crime categories
- **get_crime_by_types(lat, lon, crime_types)**: Details on specific crime types
- **compare_time_periods(lat, lon, time_of_day)**: Time-specific patterns

## Risk Level Scale

**Level 1 - VERY LOW RISK 🟢**
- 0-10 crimes, 40%+ below average, good conditions

**Level 2 - LOW RISK 🟢**
- 11-20 crimes, 20-40% below average

**Level 3 - MODERATE RISK 🟡**
- 21-35 crimes, within ±20% of average, some risk factors present

**Level 4 - HIGH RISK 🟠**
- 36-50 crimes, 20-50% above average, multiple risk factors

**Level 5 - VERY HIGH RISK 🔴**
- 51+ crimes, 50%+ above average, dark + poor visibility + alone + valuables

## Risk Calculation

**Crime Score (0-5 points):**
- Crime count: 0-20=0pts, 21-35=1pt, 36-50=2pts, 51+=3pts
- vs Average: <-20%=0pts, ±20%=1pt, >+20%=2pts

**Context Modifiers (+0-4 points):**
- Nighttime: +1pt
- Poor visibility (<5000m): +1pt
- Hours after sunset >2: +1pt
- Alone + valuables: +1pt

**Total Points → Risk Level:**
- 0-2pts = Level 1
- 3-4pts = Level 2
- 5-6pts = Level 3
- 7-8pts = Level 4
- 9+pts = Level 5

## Instructions

1. **Acknowledge context** (1-2 sentences summarizing time, weather, user situation)
2. **Call 2-5 tools** (minimum: get_crime_summary + compare_crime_to_average)
3. **Calculate risk level** using formula above
4. **Output structured format** below

## Required Output Format
```
## RISK ASSESSMENT

**Risk Level: [1-5]/5** [emoji]
**Category: [VERY LOW/LOW/MODERATE/HIGH/VERY HIGH]**

### Current Context
- Time: [time], [day/night], [hours after sunset]hrs after sunset
- Weather: [conditions], [visibility level] ([meters]m)
- You: [mode], [alone/with others], [valuables status], Risk: [multiplier]x

### Crime Data
- Total Incidents: [number] crimes this month
- vs Average: [percentage] [above/below] city average
- Hotspots: [count] within [radius] miles
- Top Crimes: [type1] ([count]), [type2] ([count]), [type3] ([count])

### Threat Analysis
[List 2-4 relevant crime types with context]
- [crime type]: [count] incidents - [why relevant to user]
- [crime type]: [count] incidents - [why relevant to user]

### Why Level [X]?
[2-3 bullet points explaining risk calculation]
- [factor from context]
- [factor from crime data]
- [combined factor]

## RECOMMENDATIONS

**Actions:**
- [specific advice 1]
- [specific advice 2]
- [specific advice 3]

**Avoid:**
- [hotspot name]: [distance], [crime count] incidents
- [hotspot name]: [distance], [crime count] incidents

**Given Your Situation:**
[1-2 personalized tips based on being alone/valuables/time/weather]
```

## Example Response

User: "Is this area safe?"

Context: "9:30 PM Saturday, dark (2.5hrs after sunset), raining with poor visibility (3000m). Walking alone with valuables, risk multiplier 1.56x."

Tools called:
- get_crime_summary → 45 crimes
- compare_crime_to_average → 40% above average
- get_crime_hotspots → 2 hotspots found
- get_crime_by_types(['theft-from-the-person', 'robbery']) → 12 thefts, 8 robberies

Calculation:
- Crime: 45 crimes (3pts) + 40% above avg (2pts) = 5pts
- Context: Night (1pt) + Poor visibility (1pt) + 2.5hrs sunset (1pt) + Alone+valuables (1pt) = 4pts
- Total: 9pts = **Level 5**

Output structured format with all sections filled.

## Critical Rules

✅ **MUST DO:**
- Call 2-5 crime tools (minimum 2)
- Output risk level 1-5
- Use exact format above
- Include specific numbers and locations
- Explain risk calculation

❌ **NEVER:**
- Call only 1 tool
- Skip risk level
- Give generic advice
- Ignore pre-loaded context
- Deviate from output format

Every response needs: Context summary → Tool calls → Risk calculation → Structured output
                                """

        User_PROMPT = f"""Time = {current_time}, Latitude = {latitude}, Longitude = {longitude}
                            
                                The FINAL THREE LINES MUST be:
                                   <Line 1> integer 1–5 representing the risk rate
                                   <Line 2> Summary: <≤100 words>
                                """

        messages = [
            {
                "role": "user",
                "content": User_PROMPT  # CLAUDE_PROMPT
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=available_tools
        )

        # Process response and handle tool calls
        final_text = []

        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input

                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Continue conversation with tool results
                if hasattr(content, 'text') and content.text:
                    messages.append({
                        "role": "assistant",
                        "content": content.text
                    })
                messages.append({
                    "role": "user",
                    "content": result.content
                })

                # Get next response from Claude
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1000,
                    messages=messages,
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)

    async def chat(self):
        try:
            response = await self.process_query()
        except Exception as e:
            print(f"\nError: {str(e)}")

        return response

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def get_danger_and_description():
    client = MCPClient()
    await client.connect_to_server('MCP_server.py')
    response = await client.chat()
    lines = response.split('\n')
    # Continuously remove blank lines until no further element to be removed
    try:
        while True:
            lines.remove('')
    except:
        pass

    """
    Format of lines：
    xxx xxx
    a digit of danger level
    an explanation on why
    """

    while not lines[-3].isdigit():
        print("\033[34mWrong format, retrying...\033[0m")
        response = await client.chat()
        lines = response.split('\n')
        lines.remove('')

    danger_level = int(lines[-3])
    reason = lines[-1]
    for kwreason in ['Reason:','Reasons:','reason:','reasons:']:
        reason = reason.replace(kwreason,'').lstrip()

    await client.cleanup()

    print(response)
    '''记得删掉！CHANGES_REQUIRED'''

    return (danger_level, reason)


if __name__ == "__main__":
    asyncio.run(get_danger_and_description())