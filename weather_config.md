# Weather Plugin Configuration

## OpenWeatherMap API Setup

The `get_weather` plugin requires an API key from OpenWeatherMap to function properly.

### Getting an API Key

1. **Sign up for a free account**: Visit [OpenWeatherMap](https://openweathermap.org/api) and create a free account
2. **Get your API key**: After registration, navigate to the API keys section in your account dashboard
3. **Set the environment variable**: Add the following to your shell configuration file (`.bashrc`, `.zshrc`, etc.):

```bash
export OPENWEATHER_API_KEY="your_api_key_here"
```

4. **Reload your shell**: Run `source ~/.bashrc` (or `source ~/.zshrc`)

### Usage

Once configured, you can use the weather plugin with commands like:

- `What's the weather in London?`
- `Get weather for New York`
- `Show me the temperature in Tokyo`

### Supported Units

- **metric**: Celsius, meters/sec (default)
- **imperial**: Fahrenheit, miles/hour
- **kelvin**: Kelvin, meters/sec

### Example Usage

```bash
# Get weather in metric units (Celsius)
What's the weather in Paris?

# Get weather in imperial units (Fahrenheit)
What's the weather in New York in Fahrenheit?

# Get weather with specific units
Get weather for Tokyo with units=metric
```

### Error Handling

The plugin includes comprehensive error handling for:

- **Invalid API keys**: Clear error messages when API key is not configured
- **Network issues**: Timeout handling and network error messages
- **Invalid locations**: Clear feedback when location is not found
- **API errors**: Proper handling of OpenWeatherMap API errors

### Security Notes

- Never commit your API key to version control
- Use environment variables to store sensitive configuration
- The plugin validates input to prevent directory traversal and other security issues