# Superteam Telegram Gatekeeper Bot 🚀

A production-ready Telegram bot for verifying Solana wallet holdings and managing group access based on SPL tokens and NFTs. Built for Superteam communities worldwide.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Telegram      │    │   Bot        │    │   Solana RPC    │
│   Users/Groups  │◄──►│   Server     │◄──►│   Network       │
└─────────────────┘    └──────┬───────┘    └─────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │    PostgreSQL      │
                    │   (User State)     │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │      Redis         │
                    │  (Rate Limiting)   │
                    └────────────────────┘
```

## ✨ Features

- **Multi-criteria Verification**: SPL tokens, NFTs, transaction history
- **Wallet Connection Flow**: Secure signature-based verification via DM
- **Rate Limiting**: Redis-powered anti-spam protection
- **Admin Dashboard**: Commands for managing requirements and users
- **Webhook Support**: Production-ready with proper error handling
- **Database Persistence**: PostgreSQL for reliable state management
- **Docker Support**: Easy deployment and scaling

## 🔧 Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis 6+
- Solana RPC endpoint (Helius/QuickNode recommended)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)

## 🚀 Installation

1. **Clone and setup environment:**
```bash
git clone <repository-url>
cd telegram-gatekeeper-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Setup databases:**
```bash
# PostgreSQL
createdb superteam_gatekeeper

# Redis (if not using Docker)
redis-server
```

4. **Initialize database:**
```bash
python src/database/init_db.py
```

## 🏃 Running

### Development
```bash
python src/main.py
```

### Production (Docker)
```bash
docker-compose up -d
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run specific test suite
python -m pytest tests/test_verification.py -v
```

## 🔐 Security Considerations

- **Wallet Verification**: Uses message signing to prevent address spoofing
- **Rate Limiting**: Redis-based protection against spam and DoS
- **Input Validation**: All user inputs are sanitized and validated
- **Database Security**: Parameterized queries prevent SQL injection
- **Admin Authorization**: Multi-factor admin verification system

## 📖 Usage Examples

### User Flow
1. User joins Telegram group
2. Bot sends welcome message with verification instructions
3. User DMs bot to start verification process
4. Bot requests wallet signature for proof of ownership
5. Bot checks wallet holdings against configured requirements
6. User gains access or receives detailed rejection reason

### Admin Commands
```
/set_token_requirement <mint_address> <minimum_amount>
/set_nft_requirement <collection_address>
/list_requirements
/ban_user <user_id>
/stats
```

## 🔧 Configuration

Key environment variables:
- `TELEGRAM_BOT_TOKEN`: Your bot token from BotFather
- `SOLANA_RPC_URL`: Solana RPC endpoint
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `WEBHOOK_URL`: Public webhook URL for production

## 🤝 Contributing

Built for the Superteam community. Submit issues and PRs to improve functionality.

## 📚 References

- [Solana Web3.py Documentation](https://solana-py.readthedocs.io/)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Superteam Global](https://superteam.fun/)

## 📄 License

MIT License - Built with ❤️ by SuperDev