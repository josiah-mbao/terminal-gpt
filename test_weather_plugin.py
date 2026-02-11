#!/usr/bin/env python3
"""Test script for the get_weather plugin."""

import asyncio
from src.terminal_gpt.infrastructure.builtin_plugins import (
    GetWeatherPlugin,
    WeatherInput,
    PluginError,
)


async def test_weather_plugin():
    """Test the get_weather plugin functionality."""
    print("🧪 Testing get_weather plugin...")

    plugin = GetWeatherPlugin()

    # Test 1: Invalid API key
    print("\n1. Testing with invalid API key...")
    try:
        input_data = WeatherInput(location="London", units="metric")
        result = await plugin.run(input_data)
        print(f"❌ Expected error but got result: {result}")
    except PluginError as e:
        print(f"✅ Expected error caught: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    # Test 2: Valid input format (would need real API key to test fully)
    print("\n2. Testing valid input format...")
    try:
        input_data = WeatherInput(location="London", units="metric")
        print(f"✅ Input validation passed for: {input_data}")
        print(f"   Location: {input_data.location}")
        print(f"   Units: {input_data.units}")
    except Exception as e:
        print(f"❌ Input validation failed: {e}")

    print("\n✅ Weather plugin tests completed!")
    print("\n📝 Notes:")
    print("   - Plugin requires OPENWEATHER_API_KEY environment variable")
    print("   - Full testing requires a valid API key from OpenWeatherMap")
    print("   - Plugin includes proper error handling for network issues")
    print("   - Supports metric, imperial, and kelvin temperature units")


if __name__ == "__main__":
    asyncio.run(test_weather_plugin())
