import pandas as pd
import numpy as np
import joblib
import tensorflow as tf
from ydata_synthetic.synthesizers.timeseries.timegan.model import TimeGAN
from config import settings
from pydantic import BaseModel, Field, field_validator
from typing import Union, Optional
from datetime import datetime

# --- CONFIGURATION MODEL (KEPT FROM NEW VERSION) ---
class GenerationConfig(BaseModel):
    """Validates parameters with robust type coercion."""
    location: str
    
    t_min: Union[float, str] = Field(alias='t_min')
    t_max: Union[float, str] = Field(alias='t_max')
    humidity_base: Union[float, str] = Field(description="Base humidity %")
    inertia: Union[float, str] = Field(default=2.0)
    noise_scale: Union[float, str] = Field(default=1.0)
    
    ac_status: Union[bool, str] = False
    fan_status: Union[bool, str] = False
    rain_status: Union[bool, str] = False
    indoor_status: Union[bool, str] = False
    
    start_time: str
    end_time: Optional[str] = None
    time_interval: str = Field(default='30s')
    sensor_faults: Union[bool, str] = Field(default=False)
    row_count: Union[int, str, None] = Field(default=None)

    # Validators to fix "String" inputs from LLM
    @field_validator('t_min', 't_max', 'humidity_base', 'inertia', 'noise_scale', mode='before')
    @classmethod
    def to_float(cls, v):
        if v is None or v == 'null': return 75.0 # SAFE DEFAULT (Room Temp)
        if isinstance(v, str):
            try: return float(v)
            except: return 75.0
        return v

    @field_validator('ac_status', 'fan_status', 'rain_status', 'indoor_status', 'sensor_faults', mode='before')
    @classmethod
    def to_bool(cls, v):
        if isinstance(v, str): return v.lower() == 'true'
        return v

    @field_validator('row_count', mode='before')
    @classmethod
    def to_int(cls, v):
        if v == 'null' or v is None: return None
        if isinstance(v, str):
            if v.strip() == '' or v == 'null': return None
            try: return int(v)
            except: return None
        return v

    @field_validator('start_time', mode='before')
    @classmethod
    def validate_start_time(cls, v):
        if not v or v == 'null' or v == '':
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return v

    @field_validator('location', mode='before')
    @classmethod
    def validate_location(cls, v):
        if not v or v == 'null':
            return "Unknown Location"
        return v

    @field_validator('t_max')
    @classmethod
    def clamp_temp_max(cls, v: float) -> float:
        return min(float(v), 176.0) # Safety clamp

    @field_validator('t_min')
    @classmethod
    def clamp_temp_min(cls, v: float) -> float:
        return min(float(v), 176.0)


# --- THE GENERATOR CLASS (MERGED VERSION) ---
class SynthIoTSystem:
    SEQUENCE_LENGTH = 120
    ROLLING_WINDOW = 20 # From Old Version
    HUMIDITY_TEMP_SENSITIVITY = 20.0
    MIN_HUMIDITY = 5.0
    MAX_HUMIDITY = 100.0
    
    COL_DATE = 'Date'
    COL_TIME = 'Time'
    COL_TEMP = 'Temperature(F)'
    COL_HUMIDITY = 'Humidity(%)'
    COL_LOCATION = 'Location'

    def __init__(self, model_path: str, scaler_path: str):
        print(f"⚡ Loading TimeGAN from {model_path}...")
        try:
            # GPU Optimization (From Old Version)
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                try:
                    for gpu in gpus: tf.config.experimental.set_memory_growth(gpu, True)
                except RuntimeError as e: print(e)

            self.model = TimeGAN.load(model_path)
            self.scaler = joblib.load(scaler_path)
            print("✅ Model & Scaler Loaded Successfully.")
        except Exception as e:
            print(f"⚠️ Physics-Only Mode (Model failed): {e}")
            self.model = None
            self.scaler = None

    def _generate_physics_trend(self, time_index, t_min, t_max, inertia):
        # Using the nice math from the New Version
        n = len(time_index)
        hours = time_index.hour + time_index.minute / 60.0
        daily_cycle = -np.cos((hours - 2) * (2 * np.pi / 24)) 
        daily_cycle = (daily_cycle + 1) / 2
        if t_min > t_max: t_min = t_max 
        temp_trend = t_min + (daily_cycle * (t_max - t_min))
        return temp_trend

    def _generate_fresh_texture(self, n_points, config: GenerationConfig):
        # --- THE KEY FIX: USING TIMEGAN (From Old Version) ---
        if self.model is None or self.scaler is None:
            # Fallback if model failed to load
            white_noise = np.random.normal(0, 1, n_points)
            return white_noise * 0.5, white_noise * 0.5

        try:
            # 1. Rejection Sampling: Over-generate to filter for specific contexts
            n_needed = n_points
            n_buffer = n_points * 3 
            n_sequences = (n_buffer // self.SEQUENCE_LENGTH) + 2
            
            synth_data = np.array(self.model.sample(n_sequences))
            
            # 2. Inverse Transform
            flat_data = synth_data.reshape(-1, synth_data.shape[2])
            real_data = self.scaler.inverse_transform(flat_data)
            
            # The Model generates 12 cols (including Season/Time), but we only need the first 8.
            real_data = real_data[:, :8]
            
            # Columns: [Temp, Hum, AC, Window, Fan, Rain, Coastal, Indoor]
            df_synth = pd.DataFrame({
                'Temp': real_data[:, 0],
                'Hum': real_data[:, 1],
                'AC': real_data[:, 2],
                'Window': real_data[:, 3],
                'Fan': real_data[:, 4],
                'Rain': real_data[:, 5],
                'Coastal': real_data[:, 6],
                'Indoor': real_data[:, 7]
            })
            
            # Apply Filters (Latent Rejection Sampling)
            if config.ac_status:
                df_synth = df_synth[df_synth['AC'] >= 0.5]
            if config.fan_status:
                df_synth = df_synth[df_synth['Fan'] >= 0.5]
            if config.rain_status:
                df_synth = df_synth[df_synth['Rain'] >= 0.5]
            if config.indoor_status:
                df_synth = df_synth[df_synth['Indoor'] >= 0.5]

            # Fallback: If filtering removed everything (rare), use unfiltered data
            if len(df_synth) < n_points:
                df_synth = pd.DataFrame(real_data, columns=['Temp', 'Hum', 'AC', 'Window', 'Fan', 'Rain', 'Coastal', 'Indoor'])

            # 3. Extract Noise via Rolling Average
            temp_series = df_synth['Temp'].reset_index(drop=True)
            hum_series = df_synth['Hum'].reset_index(drop=True)
            
            t_noise = (temp_series - temp_series.rolling(self.ROLLING_WINDOW, center=True).mean()).fillna(0).values
            h_noise = (hum_series - hum_series.rolling(self.ROLLING_WINDOW, center=True).mean()).fillna(0).values
            
            # 4. Noise Amplification — scale proportionally to the config's temp range.
            # A fixed multiplier (8.0) causes massive overshoots on narrow ranges (e.g. 18°F).
            # Normalize noise to zero-mean/unit-variance, then scale so std dev is exactly
            # 10% of the temp range: an 18°F range gets ±1.8°F noise, 100°F gets ±10°F.
            t_noise_std = np.std(t_noise) if np.std(t_noise) > 0 else 1.0
            h_noise_std = np.std(h_noise) if np.std(h_noise) > 0 else 1.0
            target_temp_noise_std = max(0.5, (float(config.t_max) - float(config.t_min)) * 0.10)
            target_hum_noise_std  = max(0.3, target_temp_noise_std * 0.5)
            t_noise = (t_noise / t_noise_std) * target_temp_noise_std
            h_noise = (h_noise / h_noise_std) * target_hum_noise_std

            # Trim to exact length needed; tile if shortage due to aggressive filtering
            if len(t_noise) < n_points:
                tile_n = (n_points // len(t_noise)) + 1
                t_noise = np.tile(t_noise, tile_n)
                h_noise = np.tile(h_noise, tile_n)
                
            return t_noise[:n_points], h_noise[:n_points]
        except Exception as e:
            print(f"⚠️ GAN Sampling Failed: {e}. Using fallback noise.")
            white_noise = np.random.normal(0, 1, n_points)
            return white_noise * 0.5, white_noise * 0.5

    def _inject_planned_anomalies(self, df: pd.DataFrame, plan) -> pd.DataFrame:
        """Applies a structured AnomalyPlan to the dataframe."""
        df = df.copy()
        n = len(df)
        temp_col = self.COL_TEMP

        if plan.inject_spike and n > 5:
            spike_idx = np.random.randint(0, n)
            df.iloc[spike_idx, df.columns.get_loc(temp_col)] += plan.spike_magnitude

        if plan.inject_dropout and plan.dropout_duration_rows > 0:
            start = np.random.randint(0, max(1, n - plan.dropout_duration_rows))
            end = min(start + plan.dropout_duration_rows, n)
            df.iloc[start:end, df.columns.get_loc(temp_col)] = np.nan

        if plan.inject_drift and plan.drift_rate_per_row != 0:
            drift = np.arange(n) * plan.drift_rate_per_row
            df[temp_col] = df[temp_col] + drift

        if plan.inject_frozen and plan.frozen_duration_rows > 0:
            start = np.random.randint(0, max(1, n - plan.frozen_duration_rows))
            frozen_val = df.iloc[start, df.columns.get_loc(temp_col)]
            end = min(start + plan.frozen_duration_rows, n)
            df.iloc[start:end, df.columns.get_loc(temp_col)] = frozen_val

        return df

    def _inject_sensor_faults(self, df):
        df = df.copy()
        n_rows = len(df)
        
        if np.random.rand() < 0.80 and n_rows > 20: 
            start = np.random.randint(0, n_rows - 10)
            df.iloc[start:start+10, df.columns.get_loc(self.COL_TEMP)] = np.nan 
            
        if np.random.rand() < 0.90:
            spike = np.random.randint(0, n_rows)
            df.iloc[spike, df.columns.get_loc(self.COL_TEMP)] += 80.0
            
        return df

    def generate(self, config: GenerationConfig):
        # 1. Robust Time Logic
        try:
            # Normalize start_time: strip ISO 8601 'T' separator if present
            start_time_str = str(config.start_time).replace('T', ' ')

            if config.row_count and config.row_count > 0:
                time_index = pd.date_range(start=start_time_str, periods=config.row_count, freq=config.time_interval)
            elif config.end_time:
                time_index = pd.date_range(start=start_time_str, end=config.end_time, freq=config.time_interval)
            else:
                time_index = pd.date_range(start=start_time_str, periods=100, freq=config.time_interval)
        except Exception:
            time_index = pd.date_range(start=pd.Timestamp.now(), periods=100, freq='30s')
            
        n_points = len(time_index)
        
        # 2. Physics Base
        t_max_val = float(config.t_max)
        t_min_val = float(config.t_min)
        temp_range = t_max_val - t_min_val
        
        # Enforce minimum 5°F range to preserve physics correlation
        if temp_range <= 5.0:
            if t_max_val >= 170.0:
                pass  # CASE 1: OVEN — keep as-is
            elif t_min_val < 0 or (t_max_val > 0 and t_max_val < 35.0 and t_min_val < 20.0):
                # CASE 2: LEGITIMATE FREEZER
                center = (t_max_val + t_min_val) / 2.0
                if temp_range < 3.0:
                    config.t_min = center - 2.5
                    config.t_max = center + 2.5
            elif abs(t_max_val) < 2.0 and abs(t_min_val) < 2.0:
                # CASE 3: BAD DEFAULT — agent returned garbage
                import logging
                logging.getLogger("SynthIoT").warning(f"⚠️ Bad default detected (t_min={t_min_val}, t_max={t_max_val}). Defaulting to room temp.")
                config.t_min = 67.0
                config.t_max = 77.0
            else:
                # CASE 4: GENERIC LOW RANGE
                center = (t_max_val + t_min_val) / 2.0
                if center < 40.0:
                    center = 72.0
                config.t_min = center - 5.0
                config.t_max = center + 5.0
        
        # HUMIDITY SAFETY NET: Default to 60% if agent returns unrealistically low value
        if float(config.humidity_base) < 30.0:
            config.humidity_base = 60.0
        
        base_temp = self._generate_physics_trend(time_index, float(config.t_min), float(config.t_max), float(config.inertia))
        
        if config.rain_status:
            base_temp -= 5.0 

        # 3. AI Texture
        t_noise, h_noise = self._generate_fresh_texture(n_points, config)
        
        # Adaptive Measurement Noise
        temp_range = float(config.t_max) - float(config.t_min)
        measurement_noise_scale = max(0.3, max(0.0, temp_range) * 0.08) 
        measurement_noise = np.random.normal(0, measurement_noise_scale, n_points)
        
        final_temp = base_temp + (t_noise * float(config.noise_scale)) + measurement_noise

        # HARD CLAMP: Always enforce config bounds + 2°F jitter buffer.
        # Prevents wild GAN overshoots (e.g. -8°F when t_min=68°F) on every config.
        t_min_val = float(config.t_min)
        t_max_val = float(config.t_max)
        buffer = 2.0
        final_temp = np.clip(final_temp, t_min_val - buffer, t_max_val + buffer)
        
        # 4. Humidity Logic
        if float(config.t_max) <= float(config.t_min):
            norm_temp = 0.5
        else:
            norm_temp = (final_temp - float(config.t_min)) / (float(config.t_max) - float(config.t_min))
            norm_temp = np.clip(norm_temp, 0.0, 1.0)

        hum_base = float(config.humidity_base)
        if config.rain_status:
            hum_base = max(hum_base, 90.0)

        # Sensitivity 8.0: humidity inversely correlates with temp but stays near base
        HUM_TEMP_SENSITIVITY = 8.0
        final_hum = hum_base - (norm_temp * HUM_TEMP_SENSITIVITY) + (h_noise * 3.0)

        # EWMA span=5: preserves natural short-term variance
        final_hum = pd.Series(final_hum).ewm(span=5).mean().values
        final_hum = np.clip(final_hum, self.MIN_HUMIDITY, self.MAX_HUMIDITY)
        
        # 5. DataFrame Construction
        df = pd.DataFrame(index=time_index)
        df[self.COL_DATE] = df.index.strftime('%d-%m-%Y')
        df[self.COL_TIME] = df.index.strftime('%H:%M:%S')
        df[self.COL_TEMP] = np.round(final_temp, 2)
        df[self.COL_HUMIDITY] = np.round(final_hum, 1)
        df[self.COL_LOCATION] = config.location

        # NOTE: Anomaly injection is handled externally by main.py via _inject_planned_anomalies.
        return df

_sys_instance = None
def get_system_instance():
    global _sys_instance
    if _sys_instance is None:
        _sys_instance = SynthIoTSystem(settings.MODEL_PATH, settings.SCALER_PATH)
    return _sys_instance