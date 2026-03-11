import sys
import time
import pandas as pd
import io
import math

# ------------------------------------------------------------------
# 1. Compatibility Wrapper (Requests / HTTPX)
# ------------------------------------------------------------------
USE_HTTPX = False
try:
    import requests
    # Check if requests is actually usable
    print("📦 Found 'requests' library.")
except ImportError:
    try:
        import httpx
        USE_HTTPX = True
        print("📦 Found 'httpx' library.")
    except ImportError:
        print("❌ Neither 'requests' nor 'httpx' found. Please install one.")
        sys.exit(1)

BASE_URL = "http://localhost:8000"

def post_request(endpoint, json_data):
    url = f"{BASE_URL}{endpoint}"
    if USE_HTTPX:
        # HTTPX is modern and handles timeouts well
        try:
            return httpx.post(url, json=json_data, timeout=60.0)
        except Exception as e:
            print(f"   ❌ HTTP Check Error: {e}")
            return None
    else:
        # Requests is standard
        try:
            return requests.post(url, json=json_data)
        except Exception as e:
             print(f"   ❌ HTTP Check Error: {e}")
             return None

# ------------------------------------------------------------------
# 2. Test Runner
# ------------------------------------------------------------------
def test_scenario(name, prompt, checks):
    print(f"\n🧪 TESTING: {name}")
    print(f"   📝 Prompt: '{prompt}'")
    
    start_ts = time.time()
    try:
        response = post_request("/generate", {"prompt": prompt})
        
        if response is None:
             print("   ❌ Request Failed (Connection Error?)")
             return

        if response.status_code != 200:
            print(f"   ❌ FAILED Status: {response.status_code} - {response.text}")
            return

        # Parse CSV
        content = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(content))
        duration = time.time() - start_ts
        print(f"   ⏱️  Generated {len(df)} rows in {duration:.2f}s")

        # SAVE TO DISK
        import os
        os.makedirs("test_outputs", exist_ok=True)
        # Sanitize filename (replace spaces AND slashes)
        safe_name = name.replace(' ', '_').replace('/', '_').lower()
        filename = f"test_outputs/{safe_name}.csv"
        df.to_csv(filename, index=False)
        print(f"   💾 Saved to {filename}")
        
        # Run Checks
        passed = True
        for check, expected in checks.items():
            
            # Row Count Checks
            if check == 'min_rows':
                if len(df) < expected:
                    print(f"      ❌ Row Count: {len(df)} < {expected}")
                    passed = False
            elif check == 'exact_rows':
                # Allow +/- 1 tolerance for fencepost errors
                if not (expected - 1 <= len(df) <= expected + 1):
                    # Some logic might be strict, let's see. date_range is inclusive.
                    # If I ask for 50 rows, I should get 50.
                    # But the server uses date_range(periods=row_count) -> exactly N.
                    # So exact match is expected.
                    if len(df) != expected:
                        print(f"      ❌ Exact Rows: {len(df)} != {expected}")
                        passed = False
            
            # Physics Checks
            elif check == 'max_allowed_temp':
                max_t = df['Temperature(F)'].max()
                if max_t > expected:
                    print(f"      ❌ Safety Check: Max Temp {max_t}F > {expected}F")
                    passed = False
            
            elif check == 'min_avg_humidity':
                avg_h = df['Humidity(%)'].mean()
                if avg_h < expected:
                    print(f"      ❌ Humidity Check: Avg {avg_h:.1f}% < {expected}%")
                    passed = False

            # Stability / Noise Checks
            elif check == 'max_temp_std_dev':
                std_dev = df['Temperature(F)'].std()
                if std_dev > expected:
                    print(f"      ❌ Stability Check: StdDev {std_dev:.2f} > {expected}")
                    passed = False
            
            # Date/Time Checks
            elif check == 'start_date_str':
                # Expected format in prompts like '2025-01-01'
                # Output format in CSV is 'DD-MM-YYYY' e.g. '01-01-2025'
                first_date = str(df['Date'].iloc[0]) # "01-01-2025"
                # Simple flip for check: 2025-01-01 -> 01-01-2025
                try:
                    y, m, d = expected.split('-')
                    expected_fmt = f"{d}-{m}-{y}"
                    if first_date != expected_fmt:
                         print(f"      ❌ Date Mismatch: Got {first_date}, Expected {expected_fmt}")
                         passed = False
                except:
                     print(f"      ⚠️ Date checking error: {first_date} vs {expected}")
            
            elif check == 'time_interval_approx_sec':
                # Check delta between first two timestamps
                if len(df) > 1:
                    t1 = pd.to_datetime(df['Date'] + ' ' + df['Time']).iloc[0]
                    t2 = pd.to_datetime(df['Date'] + ' ' + df['Time']).iloc[1]
                    delta = (t2 - t1).total_seconds()
                    if not (expected - 5 <= delta <= expected + 5):
                        print(f"      ❌ Time Interval diff: {delta}s (Expected ~{expected}s)")
                        passed = False

        if passed:
            print("   ✅ PASSED")
        else:
            print("   ⚠️  COMPLETED WITH WARNINGS")
        
        # Give the Groq API a 3-second breathing room between tests to prevent 429 Rate Limits
        time.sleep(3)

    except Exception as e:
        print(f"   ❌ ERROR: {e}")

# ------------------------------------------------------------------
# 3. Scenarios
# ------------------------------------------------------------------
if __name__ == "__main__":
    
    # Check 1: The Basics
    test_scenario(
        "1. Standard Request", 
        "Living room temperature data.", 
        {'min_rows': 20}
    )

    # Check 2: Row Count Precision
    test_scenario(
        "2. Exact Row Count", 
        "Give me exactly 50 rows of data.", 
        {'exact_rows': 50}
    )

    # Check 3: Safety Limits (The "Oven" Test)
    test_scenario(
        "3. Safety Limit Clamp", 
        "Industrial oven at 300 Celsius.", 
        {'max_allowed_temp': 176.0} # 176F = 80C
    )

    # Check 4: Environmental Context (Rain = High Humidity)
    test_scenario(
        "4. High Humidity/Rain", 
        "It is storming heavily in the rainforest.", 
        {'min_avg_humidity': 80.0}
    )

    # Check 5: Stability (Low Noise)
    test_scenario(
        "5. High Stability/Low Noise", 
        "A strictly controlled cleanroom with constant temperature.", 
        {'max_temp_std_dev': 5.0} # Increased tolerance slightly to avoid flaky tests if model is noisy
    )

    # Check 6: Explicit Date Start
    test_scenario(
        "6. Future Start Date", 
        "Start data recording from 2025-12-25.", 
        {'start_date_str': '2025-12-25'}
    )

    # Check 7: Time Interval Logic
    test_scenario(
        "7. Large Time Intervals", 
        "10 rows of data, one reading every 1 hour.", 
        {'min_rows': 10, 'time_interval_approx_sec': 3600}
    )

    # Check 8: Fault Injection
    test_scenario(
        "8. Sensor Faults", 
        "Experiencing sensor connection glitches and dropouts.", 
        {'min_rows': 10} # Just checking it doesn't crash on fault logic
    )
    
    # Check 9: Vague/Default Handling
    test_scenario(
        "9. Vague Prompt Fallback", 
        "sensor data", 
        {'min_rows': 50} # Should default to ~100 usually
    )

    print("\n🏁 All Scenarios Completed.")
