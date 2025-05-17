import network
import time
import urequests
from machine import Pin, ADC

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
MAX_HEIGHT_CM = 30  # Approximately 12 inches height container

# Initialize rain sensor
rain_sensor = ADC(Pin(RAIN_SENSOR_PIN))
rain_sensor.atten(ADC.ATTN_11DB)  # 0 - 3.3V range (0 to 4095)

# Initialize ultrasonic pins
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

# Classify rain level based on sensor value
def classify_rain(value):
    if value >= 3000:
        return "No Rain"
    elif value >= 2000:
        return "Light Rain"
    elif value >= 1000:
        return "Moderate Rain"
    elif value >= 0:
        return "Heavy Rain"
    else:
        return "Sensor Error"

# Ultrasonic distance measurement
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

# Regression-based estimation of rainfall
def estimate_rain_mm_regression(sensor_value):
    x1, y1 = 500, 10
    x2, y2 = 3500, 0
    a = (y2 - y1) / (x2 - x1)
    b = y1 - a * x1
    rainfall = a * sensor_value + b
    return max(0, round(rainfall, 2))

# Interpolation-based estimation
def estimate_rain_mm_interpolation(sensor_value):
    data = [
        (3500, 0), (3000, 1), (2500, 2.5),
        (2000, 4), (1500, 6.5), (1000, 8), (500, 10)
    ]
    for i in range(len(data) - 1):
        x0, y0 = data[i]
        x1, y1 = data[i + 1]
        if x0 >= sensor_value >= x1:
            m = (y1 - y0) / (x1 - x0)
            return round(y0 + m * (sensor_value - x0), 2)
    return 0  # default if out of range

# Main loop
def main():
    if connect_wifi():
        while True:
            rain_value = rain_sensor.read()
            rain_level = classify_rain(rain_value)
            distance = read_distance()

            rain_mm_reg = estimate_rain_mm_regression(rain_value)
            rain_mm_interp = estimate_rain_mm_interpolation(rain_value)
            distance_str = str(distance) if distance is not None else "Error"

            if distance is not None:
                water_level = round(MAX_HEIGHT_CM - distance, 2)
                distance_str = str(water_level)
            else:
                distance_str = "Error"

            # Debug
            print("Rain Value:", rain_value)
            print("Rain Level:", rain_level)
            print("Rain (regression):", rain_mm_reg, "mm/h")
            print("Rain (interpolation):", rain_mm_interp, "mm/h")
            print("Water Level:", distance_str, "cm")

            # Send to Google Sheets
            send_to_google_sheets(rain_value, time.time())

            # Send to Blynk
            send_to_blynk("V0", rain_value)              # Raw value
            send_to_blynk("V1", rain_level)              # Text level
            send_to_blynk("V2", distance_str)            # Water level
            send_to_blynk("V3", rain_mm_reg)             # Regression mm/h
            send_to_blynk("V4", rain_mm_interp)          # Interpolation mm/h

            time.sleep(10)

main()
