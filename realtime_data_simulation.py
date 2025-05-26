import pandas as pd
import csv
import json
import time
import random
from kafka import KafkaProducer
import numpy as np
from datetime import datetime, timedelta

from logic_gen_data import generate_device_data  # có thể dùng trực tiếp generate_device_data_and_append

# Thiết lập random seed
random.seed(1510)

# --- Cấu hình thời gian ---
start_date = datetime(2023, 1, 1)
end_date = start_date + timedelta(days=365)
interval = timedelta(minutes=15)

def convert_np(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, datetime):
        return obj.isoformat()  # chuyển datetime thành chuỗi ISO: '2022-01-01T00:00:00'
    raise TypeError(f"Không thể chuyển kiểu: {type(obj)}")


# --- Cấu hình Kafka Producer ---
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v, default=convert_np).encode('utf-8')
)

try:
    timestamp = start_date
    while timestamp <= end_date:
        data = generate_device_data(timestamp, interval)
        for record in data:
            producer.send('realtime-smarthome-data', value=record)
            print(f"Sent: {record}")
            print()
            time.sleep(5)
        timestamp += interval

except KeyboardInterrupt:
    print("Dừng gửi dữ liệu.")
finally:
    producer.flush()
