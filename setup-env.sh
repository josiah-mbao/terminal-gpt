#!/bin/bash

# Terminal GPT Environment Setup Script
# This script helps you set up your environment variables for Terminal GPT

echo "🚀 Setting up Terminal GPT Environment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create a .env file first."
    echo "You can copy the example from .env.example"
    exit 1
fi

# Check if OPENROUTER_API_KEY is set
if grep -q "your-api-key-here" .env; then
    echo "⚠️  Warning: OPENROUTER_API_KEY is set to 'your-api-key-here'"
    echo "Please replace it with your actual OpenRouter API key."
    echo ""
    echo "To get your API key:"
    echo "1. Go to https://openrouter.ai/keys"
    echo "2. Sign up or log in"
    echo "3. Create a new API key"
    echo "4. Replace 'your-api-key-here' in .env with your actual key"
    echo ""
    read -p "Do you want to open the OpenRouter website? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "https://openrouter.ai/keys"
    fi
    exit 1
fi

# Check if python-dotenv is installed
if ! python -c "import dotenv" 2>/dev/null; then
    echo "📦 Installing python-dotenv..."
    pip install python-dotenv
fi

# Validate the API key format (basic check)
API_KEY=$(grep "OPENROUTER_API_KEY=" .env | cut -d'=' -f2-)
if [ ${#API_KEY} -lt 32 ]; then
    echo "❌ API key appears to be too short. Please check your API key."
    exit 1
fi

echo "✅ Environment setup complete!"
echo ""
echo "📋 Configuration Summary:"
echo "   - OPENROUTER_API_KEY: $(echo $API_KEY | cut -c1-8)..."
echo "   - DEFAULT_MODEL: $(grep "DEFAULT_MODEL=" .env | cut -d'=' -f2-)"
echo ""
echo "🎯 Next Steps:"
echo "   1. Run: python demo.py --cli chat"
echo "   2. Or start the API server: python demo.py --api"
