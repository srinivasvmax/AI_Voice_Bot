# Voice AI Bot - Production Ready

> **Enterprise-grade multilingual voice AI bot powered by Twilio, Pipecat, and Sarvam AI**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Pipecat](https://img.shields.io/badge/Pipecat-0.0.95-orange.svg)](https://github.com/pipecat-ai/pipecat)
[![Sarvam AI](https://img.shields.io/badge/Sarvam_AI-Latest-purple.svg)](https://sarvam.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Overview

A production-ready voice AI bot enabling natural phone conversations in multiple Indian languages. Built with modern async Python architecture using the Pipecat framework with enterprise-grade reliability and monitoring.

### ✨ Key Features

- **🌐 Multilingual Support**: Telugu, Hindi, English with native Sarvam AI processing
- **⚡ Ultra-Low Latency**: Optimized pipeline with <1s response time
- **🎙️ Advanced Voice Processing**: VAD, interruption handling, real-time streaming
- **🧠 RAG-Enhanced Responses**: Contextual knowledge base with semantic search
- **📊 Production Ready**: Docker, Prometheus metrics, rate limiting, structured logging
- **🔧 Modular Architecture**: Clean frame-based processing, easily extensible
- **📞 Twilio Integration**: WebSocket streaming, multi-language IVR

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Twilio account with phone number
- Sarvam AI API key
- Public HTTPS URL (ngrok for development)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd voice-ai-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker Deployment

```bash
docker-compose up -d
docker-compose logs -f
```

## 📚 Documentation

### 🚀 Quick Links
- **[Production Ready Status](docs/PRODUCTION_READY.md)** - System status and readiness verification

### Getting Started
- [Project Overview](docs/PROJECT_OVERVIEW.md) - Complete project overview and features
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) - Pre-deployment verification

### Architecture & Design
- [System Architecture](docs/ARCHITECTURE.md) - High-level design and components
- [Pipecat Architecture](docs/PIPECAT_ARCHITECTURE.md) - Frame processing pipeline details
- [Audio Conversion](docs/AUDIO_CONVERSION.md) - Audio format handling

### Operations & Maintenance
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Language Selection](docs/LANGUAGE_SELECTION.md) - Multi-language IVR setup

### Advanced Topics
- [Pipecat Patches](docs/PIPECAT_PATCHES.md) - Internal library modifications for upstream PRs

## 🏗️ Architecture

```
┌─────────────┐
│ User Phone  │
└──────┬──────┘
       │
┌──────▼──────────┐
│ Twilio Platform │
└──────┬──────────┘
       │ WebSocket
┌──────▼──────────┐
│  FastAPI Server │
│  ┌───────────┐  │
│  │ Pipecat   │  │
│  │ Pipeline  │  │
│  └───────────┘  │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Sarvam AI APIs │
│  • STT (Saarika)│
│  • LLM (Sarvam-M│
│  • TTS (Bulbul) │
└─────────────────┘
```

**Pipeline Flow**: Audio → STT → Context Aggregator → LLM → TTS → Audio

See [Architecture Documentation](docs/ARCHITECTURE.md) for detailed diagrams.

## ⚙️ Configuration

### Minimal .env Setup

```env
SERVER_URL=https://your-domain.com
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
SARVAM_API_KEY=your_api_key
```

### config.yaml Highlights

```yaml
stt:
  model: saarika:v2.5
  sample_rate: 16000

llm:
  model: sarvam-m
  max_tokens: 512
  temperature: 0.7

tts:
  voice: bulbul:v2
  sample_rate: 8000
```

See [Configuration Guide](docs/CONFIGURATION.md) for all options.

## 📞 Usage

### Making a Call

1. Call your Twilio number
2. Select language (1=Telugu, 2=Hindi, 3=English)
3. Start natural conversation

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/incoming` | POST | Initial call webhook |
| `/voice/language-selected` | POST | Language selection |
| `/media-stream/{language}` | WebSocket | Audio streaming |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

## 🧪 Testing

```bash
# Run test call
python test_call.py

# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/
```

## 📊 Monitoring

- **Metrics**: Prometheus endpoint at `/metrics`
- **Logs**: Structured JSON logs in `logs/` directory
- **Health**: `/health` endpoint for uptime monitoring

## 🔧 Development

### Project Structure

```
voice-ai-bot/
├── app/                    # Application core
├── api/                    # API routes
├── services/               # AI services (STT, LLM, TTS)
├── pipeline/               # Pipecat pipeline
├── transport/              # WebSocket transport
├── knowledge/              # RAG knowledge base
├── docs/                   # Documentation
└── tests/                  # Test suite
```

### Adding New Features

1. Review [Development Guide](docs/DEVELOPMENT.md)
2. Follow [Contributing Guidelines](docs/CONTRIBUTING.md)
3. Submit pull request

## 🐛 Troubleshooting

Common issues and solutions:

- **No audio on calls**: Check [Troubleshooting Guide](docs/TROUBLESHOOTING.md#no-audio)
- **High latency**: See [Performance Tuning](docs/PERFORMANCE.md)
- **Connection errors**: Review [Deployment Guide](docs/DEPLOYMENT.md#networking)

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](docs/CONTRIBUTING.md) first.

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email**: support@your-domain.com

## 🙏 Acknowledgments

- [Pipecat Framework](https://github.com/pipecat-ai/pipecat) - Voice AI pipeline
- [Sarvam AI](https://sarvam.ai) - Indian language AI models
- [Twilio](https://twilio.com) - Telephony infrastructure
- [FastAPI](https://fastapi.tiangolo.com) - Web framework

---

**Built with ❤️ for production voice AI applications**
