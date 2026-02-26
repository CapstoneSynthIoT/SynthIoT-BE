# SynthIoT Backend

AI-powered synthetic IoT data generator using TimeGAN and CrewAI agents.

## 🚀 Quick Start

### Prerequisites
- Python 3.11 (required for ydata-synthetic compatibility)
- Conda or Miniconda
- GROQ API Key

### Setup

1. **Clone and navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create environment and install dependencies:**
   ```bash
   # Option A: Use the setup script (recommended)
   bash setup.sh
   
   # Option B: Manual setup
   conda create -n synthiot_env python=3.11 -y
   conda activate synthiot_env
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the backend directory:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   MODEL_PATH=timegan_model.pkl
   SCALER_PATH=scaler.joblib
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

The API will be available at:
- **API Endpoint:** http://localhost:8000
- **Interactive Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

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
backend/
├── main.py              # FastAPI application
├── agents.py            # CrewAI agents
├── tools.py             # Data generation logic
├── config.py            # Configuration management
├── requirements.txt     # Python dependencies
├── setup.sh            # Setup automation script
├── .env                # Environment variables (create this)
├── timegan_model.pkl   # Pre-trained TimeGAN model
└── scaler.joblib       # Data scaler
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
