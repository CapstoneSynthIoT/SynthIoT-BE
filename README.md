# SynthIoT Backend

AI-powered synthetic IoT data generator using TimeGAN and CrewAI agents.

## 🚀 Quick Start

### Prerequisites
- Python 3.11
- PostgreSQL (local or Cloud SQL)
- [GROQ API Key](https://console.groq.com/keys)
- [Serper API Key](https://serper.dev)

### Local Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/your-org/SynthIoT-BE.git
   cd SynthIoT-BE
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   bash install_requirements.sh
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   nano .env   # fill in your API keys and DATABASE_URL
   ```

4. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Start the server:**
   ```bash
   python main.py
   ```

The API will be available at:
- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## ☁️ VM Deployment (Production)

Deploy to any Ubuntu 22.04+ VM (GCP, AWS, Azure, DigitalOcean) with a **single command**.
The `deploy.sh` script handles everything: system packages, Python venv, pip dependencies,
`.env` setup, Alembic migrations, and a systemd service that auto-restarts on reboot.

### Steps

1. **SSH into your VM and clone the repo:**
   ```bash
   git clone https://github.com/your-org/SynthIoT-BE.git
   cd SynthIoT-BE
   ```

2. **Fill in your secrets:**
   ```bash
   cp .env.example .env
   nano .env   # set GROQ_API_KEY, SERPER_API_KEY, DATABASE_URL
   ```

3. **Run the deployment script:**
   ```bash
   bash deploy.sh
   ```
   This will prompt you if `.env` is missing and pause for you to fill it in.

### Managing the Service

```bash
systemctl status synthiot       # check if running
journalctl -u synthiot -f       # live logs
systemctl restart synthiot      # restart after code changes
systemctl stop synthiot         # stop
```

### Updating the App

```bash
git pull                        # pull latest code
source ~/synthiot_venv/bin/activate
bash install_requirements.sh   # update deps if requirements changed
alembic upgrade head            # apply any new DB migrations
systemctl restart synthiot      # restart the service
```

### GCP Cloud SQL

If using Cloud SQL, set your `DATABASE_URL` in `.env` to the socket format:
```env
DATABASE_URL=postgresql://postgres:PASSWORD@/synthiot_db?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
```
Make sure the Cloud SQL Auth Proxy is running on the VM, or that the service account has Cloud SQL Client permissions.

## 📡 API Usage

### Generate Synthetic Data

**Endpoint:** `POST /generate`

**Request Body:**
```json
{
  "prompt": "Generate temperature and humidity data for a hot summer day in Phoenix, Arizona from 8 AM to 6 PM"
}
```

**Response:**
- Returns a CSV file with synthetic IoT sensor data
- Columns: Date, Time, Temperature(F), Humidity(%), Location

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate data for a rainy day in Seattle"}' \
  --output synthetic_data.csv
```

## 🏗️ Architecture

### Components

1. **FastAPI Application (`main.py`)**
   - REST API endpoint for data generation
   - Handles request validation and streaming responses
   - CORS middleware for frontend integration

2. **AI Agents (`agents.py`)**
   - **Climate Context Specialist:** Extracts environmental parameters from natural language
   - **Sensor Safety Engineer:** Validates parameters against AM2320 sensor specifications
   - Uses CrewAI for multi-agent orchestration

3. **Data Generation (`tools.py`)**
   - **SynthIoTSystem:** Core generator using TimeGAN
   - Physics-based temperature modeling (sine wave for daily cycles)
   - Humidity generation with temperature correlation
   - Configurable noise and environmental factors

4. **Configuration (`config.py`)**
   - Environment variable management using Pydantic
   - Model and scaler path configuration

### Data Flow

```
User Prompt → Climate Agent → Sensor Agent → Validation → TimeGAN → CSV Output
```

## 🛠️ Development

### Project Structure
```
SynthIoT-BE/
├── main.py                  # FastAPI app (routes)
├── config.py                # Pydantic settings (reads .env)
├── requirements.txt         # Pinned Python dependencies
├── install_requirements.sh  # Ordered pip install script
├── deploy.sh                # One-shot VM deployment script
├── synthiot.service         # Systemd unit file template
├── alembic.ini              # Alembic config
├── alembic/                 # DB migration scripts
├── AI/
│   ├── agents.py            # CrewAI agents
│   ├── tools.py             # TimeGAN data generation
│   ├── modify.py            # Gap-fill logic
│   ├── timegan_model.pkl    # Pre-trained TimeGAN model
│   └── scaler.joblib        # Data scaler
├── Database_files/
│   ├── database.py          # SQLAlchemy engine & session
│   └── models.py            # ORM models
├── User/                    # User-related routes
├── .env.example             # Environment variable template
└── .env                     # Your secrets (never commit!)
```

### Key Dependencies
- **FastAPI:** Web framework
- **CrewAI:** Multi-agent AI framework
- **LangChain-Groq:** LLM integration
- **TimeGAN:** Time-series GAN for synthetic data
- **TensorFlow:** Deep learning backend
- **Pandas/NumPy:** Data manipulation

## 🔧 Configuration Parameters

The AI agents extract and validate these parameters from natural language:

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `location` | string | Geographic location | - |
| `t_min` | float | Minimum temperature (°F) | - |
| `t_max` | float | Maximum temperature (°F) | 176 (sensor limit) |
| `humidity_base` | float | Base humidity percentage | - |
| `inertia` | float | Thermal inertia (1-4) | 2.0 |
| `noise_scale` | float | Noise amplitude | 1.0 |
| `ac_status` | bool | Air conditioning on/off | false |
| `fan_status` | bool | Fan on/off | false |
| `rain_status` | bool | Raining | false |
| `indoor_status` | bool | Indoor/outdoor | false |
| `start_time` | string | Start timestamp | Today 08:00 |
| `end_time` | string | End timestamp | Today 18:00 |

## 🐛 Troubleshooting

### Python Version Issues
If you see errors about `ydata-synthetic` not being available:
- Ensure you're using Python 3.11 (not 3.13+)
- Check with: `python --version`
- Recreate environment if needed

### Missing Dependencies
```bash
conda activate synthiot_env
pip install -r requirements.txt
```

### Model Loading Errors
- Ensure `timegan_model.pkl` and `scaler.joblib` are in the backend directory
- Check file permissions

### GROQ API Errors
- Verify your API key in `.env`
- Check API quota/limits

## 🚧 Known Limitations

1. **Sensor Constraints:** Currently hardcoded for AM2320 sensor (temp: -40°C to 80°C, humidity: 0-99.9%)
2. **Single Endpoint:** Only supports one-shot generation (no streaming progress)
3. **No Authentication:** API is open (suitable for development only)
4. **No Data Persistence:** Generated data is not stored server-side
5. **Limited Error Recovery:** No retry logic for LLM failures

## 📈 Future Improvements

See the main project documentation for planned enhancements including:
- Authentication & authorization
- Request caching
- Rate limiting
- Database integration
- WebSocket streaming
- Multiple sensor support
- Batch generation
- Comprehensive testing suite

## 📝 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]
