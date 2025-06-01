import network
import time
import urequests
from machine import Pin, ADC, deepsleep

# Wi-Fi credentials
SSID = ""
PASSWORD = ""

# Blynk Auth Token
BLYNK_TOKEN = "bKgSUP8YVAuiZPGUA7atE1pKKXBM323i"

# Google Sheets Webhook URL (Apps Script)
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxixJuGQwzMK4JcliVNPBnKLUnZi8YHHLZHu90yG1GacaF8Je6RbZPG2o5dr2at_j6YiA/exec"

# Pins
RAIN_SENSOR_PIN = 34
TRIG_PIN = 32
ECHO_PIN = 33

# Container height in cm
MAX_HEIGHT_CM = 19.5

# Initialize sensors
rain_sensor = ADC(Pin(RAIN_SENSOR_PIN))
rain_sensor.atten(ADC.ATTN_11DB)
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

# Connect to Wi-Fi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    for _ in range(10):
        if wlan.isconnected():
            print("Wi-Fi connected:", wlan.ifconfig())
            return True
        time.sleep(1)
    print("Wi-Fi failed to connect.")
    return False

# URL encode for text with spaces
def url_encode(value):
    return value.replace(" ", "%20")

# Send to Blynk
def send_to_blynk(pin, value):
    encoded_value = url_encode(str(value))
    url = "http://blynk.cloud/external/api/update?token={}&{}={}".format(BLYNK_TOKEN, pin, encoded_value)
    print("Request URL:", url)
    try:
        response = urequests.get(url)
        print("Status Code:", response.status_code)
        response.close()
    except Exception as e:
        print("Error sending to Blynk:", e)

# Send to Google Sheets
def send_to_google_sheets(rain_value, timestamp):
    try:
        sheet_url = f"{WEBHOOK_URL}?value={rain_value}&time={timestamp}"
        response = urequests.get(sheet_url)
        print("Sent to Google Sheets:", response.text)
        response.close()
    except Exception as e:
        print("Error sending to Google Sheets:", e)

def classify_rain(value):
    if value >= 3000:
        return "No Rain"
    elif value >= 2000:
        return "Light Rain"
    elif value >= 1000:
        return "Moderate Rain"
    elif value >= 1:
        return "Heavy Rain"
    else:
        return "Sensor Error"

def read_distance():
    trig.off()
    time.sleep_us(2)
    trig.on()
    time.sleep_us(10)
    trig.off()

    start = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > 30000:
            return None
    signal_on = time.ticks_us()

    start = time.ticks_us()
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), start) > 30000:
            return None
    signal_off = time.ticks_us()

    duration = time.ticks_diff(signal_off, signal_on)
    distance_cm = (duration / 2) / 29.1
    return round(distance_cm, 2)

def estimate_rain_mm_regression(sensor_value):
    x1, y1 = 500, 10
    x2, y2 = 3500, 0
    a = (y2 - y1) / (x2 - x1)
    b = y1 - a * x1
    rainfall = a * sensor_value + b
    return max(0, round(rainfall, 2))

def load_interpolation_data():
    data = []
    try:
        with open("interpolation_data.txt") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    x, y = float(parts[0]), float(parts[1])
                    data.append((x, y))
    except:
        print("Failed to load interpolation data")
    return data

# Interpolation-based estimation of rainfall
def estimate_rain_mm_interpolation(sensor_value):
    data = load_interpolation_data()
    for i in range(len(data) - 1):
        x0, y0 = data[i]
        x1, y1 = data[i + 1]
        if x0 >= sensor_value >= x1:
            m = (y1 - y0) / (x1 - x0)
            return round(y0 + m * (sensor_value - x0), 2)
    return 0

def main():
    if connect_wifi():
        while True:
            rain_value = rain_sensor.read()
            distance = read_distance()

            has_error = False
            ultrasonic_status = "OK"

            if rain_value is None or rain_value < 0 or rain_value > 4095:
                print("Rain sensor error!")
                has_error = True

            # Prepare water level value (with fallback to 9999 on ultrasonic error)
            if distance is not None and 0 <= distance <= MAX_HEIGHT_CM:
                water_level = round(MAX_HEIGHT_CM - distance, 2)
            else:
                print("Ultrasonic sensor error!")
                water_level = 0  # Send error flag to Blynk
                ultrasonic_status = "Sensor Error"

            if not has_error:
                rain_level = classify_rain(rain_value)
                rain_mm_reg = estimate_rain_mm_regression(rain_value)
                rain_mm_interp = estimate_rain_mm_interpolation(rain_value)

                print("Rain Value:", rain_value)
                print("Rain Level:", rain_level)
                print("Rain (regression):", rain_mm_reg, "mm/h")
                print("Rain (interpolation):", rain_mm_interp, "mm/h")
                print("Water Level:", water_level, "cm")
            
                # Send to Google Sheets
                send_to_google_sheets(rain_value, time.time())
            
                # Send to Blynk
                send_to_blynk("V0", rain_value)
                send_to_blynk("V1", rain_level)
                send_to_blynk("V2", water_level)
                send_to_blynk("V3", rain_mm_reg)
                send_to_blynk("V4", rain_mm_interp)
                send_to_blynk("V5", ultrasonic_status)
            else:
                print("Skipping Blynk update due to rain sensor error.")

            # Dynamic deep sleep
            if rain_value is not None and rain_value >= 3200:
                time.sleep(10)  # No rain → sleep 10 sec
            else:
                time.sleep(5)  # Rain → sleep 5 sec

main()
