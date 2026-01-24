#!/usr/bin/env python3
"""Test script to validate configuration setup."""

from src.terminal_gpt.config import get_application_config, validate_config


def test_configuration():
    """Test that configuration loads and validates correctly."""
    try:
        # Test configuration loading
        config = get_application_config()
        print("✅ Configuration loaded successfully!")

        # Test validation
        validate_config()
        print("✅ Configuration validation passed!")

        # Show configuration summary
        print("\n📋 Configuration Summary:")
        print(f"   - API Key: {config['openrouter']['api_key'][:8]}...")
        print(f"   - Default Model: {config['openrouter']['default_model']}")
        print(f"   - Max Tokens: {config['openrouter']['max_tokens']}")
        print(f"   - Temperature: {config['openrouter']['temperature']}")
        print(f"   - Environment: {config['environment']}")
        print(f"   - Debug Mode: {config['debug']}")

        return True

    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False


if __name__ == "__main__":
    success = test_configuration()
    if success:
        print(
            "\n🎉 Your environment is ready! Replace 'your-api-key-here' "
            "with your actual OpenRouter API key to get started."
        )
    else:
        print("\n🔧 Please check your .env file and try again.")
