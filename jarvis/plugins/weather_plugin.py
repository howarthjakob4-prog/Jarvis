"""Weather. Try: "what's the weather", "what's the weather in Paris".

Key-free via Open-Meteo: its geocoding API resolves the city, then the
forecast API returns current conditions. Default city comes from the
`weather_city` config key (set it in config.yaml or config/local.yaml).
"""
import re

import requests

from .base import Plugin

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_MATCH_RX = re.compile(
    r"\bweather\b|\bforecast\b|\btemperature outside\b"
    r"|\bhow (hot|cold|warm) is it\b"
)
_CITY_RX = re.compile(r"\bin\s+([a-zA-Z][a-zA-Z\s\-']*?)(?:\s+today|\s+right now|\s+outside)?\s*$")
_STRIP_TAIL = re.compile(r"\s+(today|right now|outside|please)$", re.IGNORECASE)
# Words that look like "in <city>" but are really time words.
_TIME_WORDS = {"morning", "afternoon", "evening", "tonight", "today", "tomorrow"}

# Open-Meteo WMO weather codes -> plain words.
_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy with ice",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers",
    85: "light snow showers", 86: "snow showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail", 99: "a thunderstorm with hail",
}


class WeatherPlugin(Plugin):
    name = "weather"
    description = "Current weather: \"what's the weather in Paris\"."

    def match(self, text):
        return bool(_MATCH_RX.search(text))

    def _city(self, text):
        m = _CITY_RX.search(text)
        if m:
            city = _STRIP_TAIL.sub("", m.group(1)).strip().rstrip(".")
            city = re.sub(r"^the\s+", "", city, flags=re.IGNORECASE)
            if city and city.lower() not in _TIME_WORDS:
                return city
        brain = getattr(self, "brain", None)
        if brain is not None:
            return (brain.config.get("weather_city") or "").strip()
        return ""

    def _geocode(self, city):
        resp = requests.get(_GEO_URL, params={
            "name": city, "count": 1, "language": "en", "format": "json",
        }, timeout=12)
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        r = results[0]
        label = ", ".join(p for p in (r.get("name"), r.get("country")) if p)
        return r["latitude"], r["longitude"], label

    def _current(self, lat, lon):
        resp = requests.get(_FORECAST_URL, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "temperature_unit": "fahrenheit", "timezone": "auto",
        }, timeout=12)
        return resp.json()["current"]

    def run(self, text):
        city = self._city(text)
        if not city:
            return ("Which city? Say \"what's the weather in Paris\", "
                    "or set a default with weather_city in config.yaml.")
        try:
            geo = self._geocode(city)
        except requests.RequestException:
            return "I couldn't reach the weather service — are you offline?"
        if not geo:
            return f"I couldn't find a place called {city}."
        lat, lon, label = geo
        try:
            cur = self._current(lat, lon)
        except requests.RequestException:
            return "I couldn't reach the weather service — are you offline?"
        desc = _CODES.get(cur.get("weather_code"), "changing conditions")
        temp = round(cur.get("temperature_2m", 0))
        wind = round(cur.get("wind_speed_10m", 0))
        return (f"In {label} it's {desc}, {temp} degrees, "
                f"with wind around {wind} miles per hour.")


plugin = WeatherPlugin()
