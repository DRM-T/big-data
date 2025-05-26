import json
from kafka import KafkaProducer
from datetime import datetime, time

# Cấu hình Kafka
KAFKA_BROKERS = 'localhost:9092'
# Topic đích là topic kiểm tra
KAFKA_DATA_TOPIC = 'smarthome-test-data' 

# Cấu hình Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Lấy thời gian hiện tại
now = datetime.now()

# --- Kịch bản cho các nhánh trong hàm recommend ---

# Rule 1.1 (Trùng với Rule 4.3): Tiết kiệm điện - Đèn sáng khi đủ sáng tự nhiên
# if device == 'light' and status == 'on' and light_level >= 500:
# messages.append(f"{time_str} Phòng {room} đang có đủ ánh sáng tự nhiên ({light_level} lux). Hãy tắt đèn để tiết kiệm điện.")
# messages.append(f"{time_str} Phòng {room} đang có nhiều ánh sáng tự nhiên ({light_level} lux). Bạn có thể tắt đèn '{device}' để tiết kiệm điện.")
sample_record_1_1 = {
    'home_id': 99,
    'timestamp': now.isoformat(),
    'device_id': 'TEST_LIGHT_0199',
    'device_type': 'light',
    'room': 'living_room',
    'status': 'on', # Quan trọng
    'power_watt': 10,
    'user_present': 1,
    'activity': 'idle',
    'indoor_temp': 25.0,
    'outdoor_temp': 28.0,
    'humidity': 60.0,
    'light_level': 550.0, # Quan trọng: >= 500
    'day_of_week': now.weekday(),
    'hour_of_day': now.hour,
    'price_kWh': 2500
}

# Rule 1.2: Tiết kiệm điện - Giặt đồ giờ rẻ
# if device == 'washer' and status == 'off' and 21 <= hour < 23 and price_kWh == 1500:
# messages.append(f"{time_str} Đây là giờ điện rẻ (sau 22h). Hãy tranh thủ giặt đồ để tiết kiệm chi phí.")
time_for_rule_1_2 = now.replace(hour=22, minute=15)
sample_record_1_2 = {
    'home_id': 99,
    'timestamp': time_for_rule_1_2.isoformat(),
    'device_id': 'TEST_WASHER_0199',
    'device_type': 'washer', # Quan trọng
    'room': 'laundry_room',
    'status': 'off', # Quan trọng
    'power_watt': 0,
    'user_present': 1, # Để có thể giặt
    'activity': 'idle',
    'indoor_temp': 25.0,
    'outdoor_temp': 22.0,
    'humidity': 60.0,
    'light_level': 50.0,
    'day_of_week': time_for_rule_1_2.weekday(),
    'hour_of_day': time_for_rule_1_2.hour, # Quan trọng: 21 <= hour < 23
    'price_kWh': 1500 # Quan trọng
}

# Rule 2.1: An toàn & Sức khỏe - Thiết bị (khác tủ lạnh, điều hòa) bật khi ngủ
# if status == 'on' and activity == 'sleeping' and device not in ['fridge', 'air_conditioner']:
# messages.append(f"{time_str} Bạn đang ngủ nhưng thiết bị '{device}' tại {room} vẫn đang bật. Hãy tắt để ngủ ngon hơn và tiết kiệm điện.")
time_for_rule_2_1 = now.replace(hour=2, minute=0) # Giờ ngủ
sample_record_2_1 = {
    'home_id': 99,
    'timestamp': time_for_rule_2_1.isoformat(),
    'device_id': 'TEST_TV_0199', # Ví dụ: TV
    'device_type': 'tv', # Quan trọng: không phải 'fridge', 'air_conditioner'
    'room': 'bedroom',
    'status': 'on', # Quan trọng
    'power_watt': 100,
    'user_present': 1,
    'activity': 'sleeping', # Quan trọng
    'indoor_temp': 26.0,
    'outdoor_temp': 24.0,
    'humidity': 60.0,
    'light_level': 10.0,
    'day_of_week': time_for_rule_2_1.weekday(),
    'hour_of_day': time_for_rule_2_1.hour,
    'price_kWh': 1500
}

# Rule 2.2: An toàn & Sức khỏe - Xem TV khuya
# if device == 'tv' and status == 'on' and hour >= 1 and user_present == 1:
# messages.append(f"{time_str} Đã quá khuya ({hour}h), bạn vẫn đang xem TV. Hãy nghỉ ngơi để đảm bảo sức khỏe.")
time_for_rule_2_2 = now.replace(hour=1, minute=30) # Quan trọng: >= 1h sáng
sample_record_2_2 = {
    'home_id': 99,
    'timestamp': time_for_rule_2_2.isoformat(),
    'device_id': 'TEST_TV_0199',
    'device_type': 'tv', # Quan trọng
    'room': 'living_room',
    'status': 'on', # Quan trọng
    'power_watt': 100,
    'user_present': 1, # Quan trọng
    'activity': 'watching_tv', # Để rõ ràng là đang xem TV
    'indoor_temp': 25.0,
    'outdoor_temp': 22.0,
    'humidity': 55.0,
    'light_level': 150.0,
    'day_of_week': time_for_rule_2_2.weekday(),
    'hour_of_day': time_for_rule_2_2.hour, # Quan trọng: >= 1
    'price_kWh': 1500
}

# Rule 2.3: An toàn & Sức khỏe - Điều hòa bật khi nấu ăn
# if device == 'air_conditioner' and status == 'on' and activity == 'cooking':
# messages.append(f"{time_str} Bạn đang nấu ăn. Hạn chế dùng điều hòa khi nấu để tiết kiệm điện và tăng hiệu quả làm mát.")
sample_record_2_3 = {
    'home_id': 99,
    'timestamp': now.isoformat(),
    'device_id': 'TEST_AC_0199',
    'device_type': 'air_conditioner', # Quan trọng
    'room': 'kitchen', # Giả sử điều hòa có thể ở bếp hoặc phòng ăn liền bếp
    'status': 'on', # Quan trọng
    'power_watt': 800,
    'user_present': 1,
    'activity': 'cooking', # Quan trọng
    'indoor_temp': 27.0,
    'outdoor_temp': 30.0,
    'humidity': 65.0,
    'light_level': 300.0,
    'day_of_week': now.weekday(),
    'hour_of_day': now.hour,
    'price_kWh': 2500
}

# --- Nhóm Rule 3.1.x: Hành vi bất thường - Tiêu thụ điện cao ---
# Chung: status == 'on' and predicted_power > 0 and power_actual > 1.5 * predicted_power
# Giả định: predicted_power của các thiết bị này thường < 200W trong điều kiện bình thường.
# Ta đặt power_actual (power_watt) = 600W để đảm bảo điều kiện được kích hoạt.

# Rule 3.1.1: Tủ lạnh
sample_record_3_1_1 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_FRIDGE_0199', 'device_type': 'fridge',
    'room': 'kitchen', 'status': 'on', 'power_watt': 600, 'user_present': 1, 'activity': 'idle',
    'indoor_temp': 27.0, 'outdoor_temp': 30.0, 'humidity': 65.0, 'light_level': 200.0,
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 2500
}
# Rule 3.1.2: Điều hòa
sample_record_3_1_2 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_AC_0199', 'device_type': 'air_conditioner',
    'room': 'bedroom', 'status': 'on', 'power_watt': 2000, 'user_present': 1, 'activity': 'idle', # Điều hòa có thể > 600W
    'indoor_temp': 26.0, 'outdoor_temp': 30.0, 'humidity': 60.0, 'light_level': 100.0,
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 3000
}
# Rule 3.1.3: Đèn
sample_record_3_1_3 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_LIGHT_0199', 'device_type': 'light',
    'room': 'living_room', 'status': 'on', 'power_watt': 300, 'user_present': 1, 'activity': 'idle',
    'indoor_temp': 25.0, 'outdoor_temp': 28.0, 'humidity': 60.0, 'light_level': 400.0, # Dưới 500 để không trigger rule 1.1
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 2500
}
# Rule 3.1.4: TV
sample_record_3_1_4 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_TV_0199', 'device_type': 'tv',
    'room': 'living_room', 'status': 'on', 'power_watt': 500, 'user_present': 1, 'activity': 'watching_tv', # Để không trigger rule 3.2
    'indoor_temp': 25.0, 'outdoor_temp': 28.0, 'humidity': 60.0, 'light_level': 150.0,
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 2500
}
# Rule 3.1.5: Máy giặt
time_for_rule_3_1_5 = now.replace(hour=10) # Giờ không phải giờ rẻ
sample_record_3_1_5 = {
    'home_id': 99, 'timestamp': time_for_rule_3_1_5.isoformat(), 'device_id': 'TEST_WASHER_0199', 'device_type': 'washer',
    'room': 'laundry_room', 'status': 'on', 'power_watt': 1500, 'user_present': 1, 'activity': 'washing', # Hoạt động giặt
    'indoor_temp': 27.0, 'outdoor_temp': 30.0, 'humidity': 70.0, 'light_level': 200.0,
    'day_of_week': time_for_rule_3_1_5.weekday(), 'hour_of_day': time_for_rule_3_1_5.hour, 'price_kWh': 2500
}
# Rule 3.1.6: Thiết bị khác (ví dụ: 'fan')
sample_record_3_1_6 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_FAN_0199', 'device_type': 'fan', # Thiết bị khác
    'room': 'bedroom', 'status': 'on', 'power_watt': 200, 'user_present': 1, 'activity': 'idle',
    'indoor_temp': 26.0, 'outdoor_temp': 29.0, 'humidity': 60.0, 'light_level': 100.0,
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 2500
}

# Rule 3.2: Hành vi bất thường - TV bật nhưng không xem
# if device == 'tv' and status == 'on' and activity != 'watching_tv':
# messages.append(f"{time_str} TV đang bật dù bạn không xem. Hãy tắt để tập trung và tiết kiệm điện.")
sample_record_3_2 = {
    'home_id': 99,
    'timestamp': now.isoformat(),
    'device_id': 'TEST_TV_0199',
    'device_type': 'tv', # Quan trọng
    'room': 'living_room',
    'status': 'on', # Quan trọng
    'power_watt': 100, # Công suất bình thường
    'user_present': 1,
    'activity': 'cooking', # Quan trọng: không phải 'watching_tv' (và không phải 'sleeping' để tránh rule 2.1)
    'indoor_temp': 26.0,
    'outdoor_temp': 29.0,
    'humidity': 60.0,
    'light_level': 300.0,
    'day_of_week': now.weekday(),
    'hour_of_day': now.hour, # Đảm bảo không phải giờ khuya để không trigger rule 2.2
    'price_kWh': 2500
}

# Rule 3.3: Hành vi bất thường - Thiết bị bật khi không có ai
# if status == 'on' and user_present == 0:
# messages.append(f"{time_str} Thiết bị '{device}' tại {room} đang bật dù không có ai trong phòng. Hãy tắt thiết bị để tiết kiệm điện.")
sample_record_3_3 = {
    'home_id': 99,
    'timestamp': now.isoformat(),
    'device_id': 'TEST_LIGHT_0199', # Ví dụ: Đèn
    'device_type': 'light',
    'room': 'office',
    'status': 'on', # Quan trọng
    'power_watt': 60,
    'user_present': 0, # Quan trọng
    'activity': 'away', # Thường đi kèm user_present = 0
    'indoor_temp': 28.0,
    'outdoor_temp': 30.0,
    'humidity': 70.0,
    'light_level': 400.0, # Đảm bảo < 500 để không trigger rule 1.1
    'day_of_week': now.weekday(),
    'hour_of_day': now.hour,
    'price_kWh': 2500
}

# Rule 4.1: Môi trường - Độ ẩm cao
# if humidity > 70 and outdoor_temp < indoor_temp:
# messages.append(f"{time_str} Độ ẩm đang cao ({humidity:.1f}%). Hãy đóng cửa sổ hoặc bật hút ẩm nếu thấy bí bách.")
sample_record_4_1 = {
    'home_id': 99,
    'timestamp': now.isoformat(),
    'device_id': 'TEST_SENSOR_0199', # Thiết bị không quan trọng cho rule này
    'device_type': 'sensor',
    'room': 'living_room',
    'status': 'on', # Trạng thái không quan trọng
    'power_watt': 1,
    'user_present': 1,
    'activity': 'idle',
    'indoor_temp': 27.0, # Quan trọng: outdoor_temp < indoor_temp
    'outdoor_temp': 26.0,
    'humidity': 75.0, # Quan trọng: > 70
    'light_level': 200.0,
    'day_of_week': now.weekday(),
    'hour_of_day': now.hour,
    'price_kWh': 3000
}

# Rule 4.2: Môi trường - Tắt điều hòa khi trời mát
# if device == 'air_conditioner' and status == 'on' and outdoor_temp + 2 < indoor_temp:
# messages.append(f"{time_str} Nhiệt độ ngoài trời ({outdoor_temp}°C) mát hơn trong phòng ({indoor_temp}°C). Cân nhắc tắt điều hòa và mở cửa sổ.")
sample_record_4_2 = {
    'home_id': 99,
    'timestamp': now.isoformat(),
    'device_id': 'TEST_AC_0199',
    'device_type': 'air_conditioner', # Quan trọng
    'room': 'bedroom',
    'status': 'on', # Quan trọng
    'power_watt': 750,
    'user_present': 1,
    'activity': 'idle',
    'indoor_temp': 26.0, # Quan trọng
    'outdoor_temp': 23.0, # Quan trọng: outdoor_temp + 2 < indoor_temp (23+2=25 < 26)
    'humidity': 60.0,
    'light_level': 100.0,
    'day_of_week': now.weekday(),
    'hour_of_day': now.hour,
    'price_kWh': 3000
}

# Rule 4.3 (Trùng với Rule 1.1, đã có sample_record_1_1)

# --- Nhóm Rule 5.1.x: Bật thiết bị khi cần ---
# Chung: status == 'off' and predicted_power > 100 and user_present == 1
# Giả định: Mô hình sẽ dự đoán predicted_power > 100W cho các tình huống này nếu thiết bị được bật.

# Rule 5.1.1: Bật điều hòa khi nóng
# if device == 'air_conditioner' and indoor_temp >= 28:
sample_record_5_1_1 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_AC_0199', 'device_type': 'air_conditioner',
    'room': 'bedroom', 'status': 'off', 'power_watt': 0, 'user_present': 1, 'activity': 'idle',
    'indoor_temp': 29.0, 'outdoor_temp': 32.0, 'humidity': 65.0, 'light_level': 300.0, # indoor_temp >= 28
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 3000
}
# Rule 5.1.2: Bật TV khi muốn xem
# elif device == 'tv' and activity == 'watching_tv':
sample_record_5_1_2 = {
    'home_id': 99, 'timestamp': now.isoformat(), 'device_id': 'TEST_TV_0199', 'device_type': 'tv',
    'room': 'living_room', 'status': 'off', 'power_watt': 0, 'user_present': 1, 'activity': 'watching_tv', # activity == 'watching_tv'
    'indoor_temp': 25.0, 'outdoor_temp': 28.0, 'humidity': 60.0, 'light_level': 150.0,
    'day_of_week': now.weekday(), 'hour_of_day': now.hour, 'price_kWh': 2500
}
# Rule 5.1.3: Bật đèn khi tối & không ngủ
# elif device == 'light' and light_level < 100 and activity != 'sleeping':
time_for_rule_5_1_3 = now.replace(hour=19) # Buổi tối
sample_record_5_1_3 = {
    'home_id': 99, 'timestamp': time_for_rule_5_1_3.isoformat(), 'device_id': 'TEST_LIGHT_0199', 'device_type': 'light',
    'room': 'study_room', 'status': 'off', 'power_watt': 0, 'user_present': 1, 'activity': 'studying', # activity != 'sleeping'
    'indoor_temp': 26.0, 'outdoor_temp': 24.0, 'humidity': 60.0, 'light_level': 50.0, # light_level < 100
    'day_of_week': time_for_rule_5_1_3.weekday(), 'hour_of_day': time_for_rule_5_1_3.hour, 'price_kWh': 2500
}
# Rule 5.1.4: Giặt đồ vào buổi tối
# elif device == 'washer' and activity in ['idle', 'watching_tv'] and hour >= 21:
time_for_rule_5_1_4 = now.replace(hour=21, minute=30) # hour >= 21
sample_record_5_1_4 = {
    'home_id': 99, 'timestamp': time_for_rule_5_1_4.isoformat(), 'device_id': 'TEST_WASHER_0199', 'device_type': 'washer',
    'room': 'laundry_room', 'status': 'off', 'power_watt': 0, 'user_present': 1, 'activity': 'idle', # activity in ['idle', 'watching_tv']
    'indoor_temp': 25.0, 'outdoor_temp': 22.0, 'humidity': 60.0, 'light_level': 50.0,
    'day_of_week': time_for_rule_5_1_4.weekday(), 'hour_of_day': time_for_rule_5_1_4.hour, # hour >= 21
    'price_kWh': 1500 # Có thể là giờ điện rẻ
}


# CHỌN KỊCH BẢN ĐỂ GỬI (BỎ COMMENT 1 KỊCH BẢN)
# current_sample_record = sample_record_1_1
current_sample_record = sample_record_1_2
# current_sample_record = sample_record_2_1
# current_sample_record = sample_record_2_2
# current_sample_record = sample_record_2_3
# current_sample_record = sample_record_3_1_1
# current_sample_record = sample_record_3_1_2
# current_sample_record = sample_record_3_1_3
# current_sample_record = sample_record_3_1_4
# current_sample_record = sample_record_3_1_5
# current_sample_record = sample_record_3_1_6
# current_sample_record = sample_record_3_2
# current_sample_record = sample_record_3_3 # Ví dụ: chọn kịch bản 3.3 để test
# current_sample_record = sample_record_4_1
# current_sample_record = sample_record_4_2
# current_sample_record = sample_record_5_1_1
# current_sample_record = sample_record_5_1_2
# current_sample_record = sample_record_5_1_3
# current_sample_record = sample_record_5_1_4


try:
    print(f"Đang gửi bản ghi mẫu tới topic '{KAFKA_DATA_TOPIC}': {current_sample_record}")

    # Gửi bản ghi đến Kafka Topic mới
    future = producer.send(KAFKA_DATA_TOPIC, value=current_sample_record)

    # Chờ tin nhắn được gửi thành công (tùy chọn, hữu ích cho debug)
    result = future.get(timeout=10)
    print(f"Đã gửi bản ghi thành công tới topic '{result.topic}' partition {result.partition} offset {result.offset}")

except Exception as e:
    print(f"Lỗi khi gửi bản ghi: {e}")

finally:
    producer.flush() # Đảm bảo tất cả tin nhắn đang chờ được gửi
    producer.close() # Đóng producer
    print("Producer đã đóng.")