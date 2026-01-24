# Environment Setup Guide

This guide will help you set up your environment variables for Terminal GPT.

## Quick Start

1. **Get your OpenRouter API Key**
   - Go to [https://openrouter.ai/keys](https://openrouter.ai/keys)
   - Sign up or log in to your account
   - Create a new API key

2. **Configure Environment Variables**
   - Open the `.env` file in the project root
   - Replace `your-api-key-here` with your actual OpenRouter API key
   - Save the file

3. **Install Dependencies**
   ```bash
   # Install python-dotenv if not already installed
   pip install python-dotenv
   
   # Install project dependencies
   pip install -e .
   ```

4. **Verify Setup**
   ```bash
   ./setup-env.sh
   ```

## Environment Variables

### Required
- `OPENROUTER_API_KEY` - Your OpenRouter API key (required)

### Optional
- `DEFAULT_MODEL` - LLM model to use (default: `openai/gpt-3.5-turbo`)
- `MAX_TOKENS` - Maximum response tokens (default: `4096`)
- `TEMPERATURE` - Response creativity (default: `0.7`)
- `MAX_CONVERSATION_LENGTH` - Max messages in history (default: `100`)
- `SLIDING_WINDOW_SIZE` - Context window size (default: `50`)
- `ENABLE_SUMMARIZATION` - Enable conversation summarization (default: `false`)

### Development
- `ENVIRONMENT` - Environment type (default: `development`)
- `DEBUG` - Enable debug mode (default: `false`)

## Usage

### CLI Interface
```bash
python demo.py --cli chat
```

### API Server
```bash
python demo.py --api
```


## Troubleshooting

### API Key Issues
- Ensure your API key is valid and not expired
- Check that you haven't exceeded your API quota
- Verify the key format (should be at least 32 characters)

### Environment Loading Issues
- Make sure `.env` file exists in project root
- Check that `python-dotenv` is installed
- Verify file permissions on `.env` file


## Security Notes

- Never commit `.env` files to version control
- Use different API keys for development and production
- Regularly rotate your API keys
- Monitor your API usage and set appropriate limits