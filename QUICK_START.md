# 🚀 Quick Start Guide

## Simplified Setup & Usage

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd terminal-gpt

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### 2. Running the Application (Simplified Workflow)

#### Terminal 1: Start the Server
```bash
python -m terminal_gpt server
# OR
python -m terminal_gpt-server
```

#### Terminal 2: Start the Enhanced Chat Interface (Recommended)
```bash
python -m terminal_gpt streaming
# OR
python -m terminal_gpt-streaming
```

#### Alternative: Standard Terminal Interface
```bash
python -m terminal_gpt chat
# OR
python -m terminal_gpt-chat
```

### 3. Available Commands

```bash
# Main CLI interface
python -m terminal_gpt

# Individual commands
python -m terminal_gpt server      # Start FastAPI server
python -m terminal_gpt chat        # Start terminal chat
python -m terminal_gpt streaming   # Start streaming chat (enhanced UI)
python -m terminal_gpt setup       # Show setup instructions
python -m terminal_gpt info        # Show project information
```

### 4. Configuration

Edit the `.env` file to configure your LLM provider:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Alternative: Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

## 🎨 Enhanced UI Features

The streaming client provides:
- ✅ **Rich color-coded status messages** (✅, ⚠️, ❌, ℹ️)
- ✅ **Professional welcome screens** with features and tips
- ✅ **Real-time thinking indicators** during AI processing
- ✅ **Plugin output with syntax highlighting**
- ✅ **Terminal size validation** and accessibility features
- ✅ **Enhanced error handling** with rich formatting

## 📋 Workflow Summary

1. **Start Server**: `python -m terminal_gpt server` (Terminal 1)
2. **Start Chat**: `python -m terminal_gpt streaming` (Terminal 2)
3. **Enjoy Enhanced UI**: Rich formatting and professional interface
4. **Use Commands**: Type `/help` for available commands

## 🔧 Troubleshooting

### Common Issues

**"Command not found"**
```bash
# Make sure you're in the project directory
cd terminal-gpt

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**"API connection failed"**
```bash
# Check if server is running
python -m terminal_gpt server

# Verify API key in .env file
cat .env
```

**"Enhanced UI not visible"**
```bash
# Use the streaming client for enhanced UI
python -m terminal_gpt streaming

# Check terminal compatibility
python -m terminal_gpt setup
```

## 🎯 Key Benefits

- **Simplified Commands**: Easy-to-remember CLI commands
- **Enhanced UI**: Professional interface with rich formatting
- **Streamlined Setup**: Single requirements.txt file
- **Clean Project**: Removed unused demo files
- **Production Ready**: Enterprise-grade quality