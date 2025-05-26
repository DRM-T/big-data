#@title Dự đoán công suất tiêu thụ thiết bị điện bằng LightGBM
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
import matplotlib.pyplot as plt
from datetime import timedelta
import json
import numpy as np
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from pathlib import Path

import re

current_day = None  # Biến theo dõi ngày hiện tại
data_dir = Path('data')
data_dir.mkdir(exist_ok=True)  # Tạo thư mục nếu chưa có

# Consumer để nhận dữ liệu
consumer = KafkaConsumer(
    'realtime-smarthome-data',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='smarthome-consumer-group'
)

# Producer để gửi gợi ý vào một topic khác
suggestion_producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


def read_data():
    import re
    from pathlib import Path
    data_dir = Path('data')
    data_files = list(data_dir.glob('data_*.csv'))

    file_years = []
    for file in data_files:
        match = re.search(r'data_(\d{4})\.csv', file.name)
        if match:
            year = int(match.group(1))
            file_years.append((year, file))

    file_years.sort(reverse=True)

    if len(file_years) >= 2:
        top_files = [file_years[0][1], file_years[1][1]]
        df = pd.concat([pd.read_csv(f) for f in top_files], ignore_index=True)
    elif len(file_years) == 1:
        df = pd.read_csv(file_years[0][1])
    else:
        df = pd.read_csv('data/data_2022.csv')

    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')




    for col in ['predicted_power', 'suggestion']:
        if col in df.columns:
            df = df.drop(columns=[col])
            print(f"[INFO] Đã loại bỏ cột phụ")
    
    return df

def info_(df):
    df = df.copy()
    df['timestamp_yesterday'] = df['timestamp'] - pd.Timedelta(days=2)
    df['total_power_home_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday'])['power_watt'].transform('sum')
    # df['total_power_device_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday', 'device_type'])['power_watt'].transform('sum')
    return df

# Dung cho rcm 1 ban ghi 
df = read_data()
data_event = info_(df)
#-----------------------------------------
def feature_engineering(df):
    df = df.copy()
    df['timestamp_yesterday'] = df['timestamp'] - pd.Timedelta(days=2)
    df['total_power_home_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday'])['power_watt'].transform('sum')
    # df['total_power_device_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday', 'device_type'])['power_watt'].transform('sum')
    #df = df.drop(columns=['status', 'timestamp', 'device_id', 'timestamp_yesterday', 'user_present', 'room', 'price_kWh', 'day_of_week', 'device_type', 'hour_of_day'])
    df = df.drop(columns=['status', 'timestamp', 'device_id', 'timestamp_yesterday', 'price_kWh'])
    return df
#-------------------------------------------------------------

def retrain_models():
    df = read_data()

    df_fe = feature_engineering(df)
    target = 'power_watt'
    X = df_fe.drop(columns=[target])
    y = df_fe[target]

    categorical_cols = X.select_dtypes(include='object').columns
    label_encoders = {}
    for col in categorical_cols:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = lgb.LGBMRegressor(objective='regression', n_estimators=100)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_pred = np.where(np.abs(y_pred) < 20, 0, y_pred)
    y_pred = np.maximum(y_pred, 0)
    print(f"[INFO] Retrained model:")
    print(f" - MSE: {mean_squared_error(y_test, y_pred):.2f}")

    return model, label_encoders

def xu_ly_ban_ghi_dau_vao(record):
    if isinstance(record, dict):
        record = pd.DataFrame([record])
    elif isinstance(record, pd.Series):
        record = record.to_frame().T
    record = record.copy()
    record = record.reset_index()
    ts_yesterday = record['timestamp'].iloc[0]
    if isinstance(ts_yesterday, str):
        ts_yesterday = pd.to_datetime(ts_yesterday)
    ts_yesterday = ts_yesterday - pd.Timedelta(days=1)


    # Giả sử ts_yesterday đã là kiểu datetime
    match_ts = data_event[
        (data_event['timestamp'].dt.month == ts_yesterday.month) &
        (data_event['timestamp'].dt.day == ts_yesterday.day) &
        (data_event['timestamp'].dt.hour == ts_yesterday.hour) &
        (data_event['timestamp'].dt.minute == ts_yesterday.minute) &
        (data_event['timestamp'].dt.second == ts_yesterday.second)
    ]

    if not match_ts.empty:
        max_year = match_ts['timestamp'].dt.year.max()
        ts_yesterday = ts_yesterday.replace(year=max_year)

    record['total_power_home_yesterday'] = 0
    # record['total_power_device_yesterday'] = 0

    for i in range(len(data_event)):
      if (
          data_event['timestamp'].iloc[i] == ts_yesterday and
          data_event['home_id'].iloc[i] == record['home_id'].iloc[0] and
          data_event['device_type'].iloc[i] == record['device_type'].iloc[0]
      ):
          record['total_power_home_yesterday'] = data_event['total_power_home_yesterday'].iloc[i]
          # record['total_power_device_yesterday'] = data_event['total_power_device_yesterday'].iloc[i]
          break 
    # cols_to_drop = [
    #     'index', 'status', 'timestamp', 'device_id', 'timestamp_yesterday',
    #     'user_present', 'room', 'price_kWh', 'day_of_week',
    #     'device_type', 'hour_of_day', 'power_watt'
    # ]
    cols_to_drop = [
        'index', 'status', 'timestamp', 'device_id', 'timestamp_yesterday', 'price_kWh', 'power_watt'
    ]
    # df = df.drop(columns=['status', 'timestamp', 'device_id', 'timestamp_yesterday', 'price_kWh'])
    
    record = record.drop(columns=[col for col in cols_to_drop if col in record.columns])

    return record

def du_doan_cong_suat(input_data, model, label_encoders):
    input_df = input_data.copy()
    for col in input_df.select_dtypes(include='object').columns:
        if col in label_encoders:
            le = label_encoders[col]
            val = input_df.at[0, col]
            if val in le.classes_:
                input_df[col] = le.transform([val])
            else:
                input_df[col] = -1  
    input_df = input_df.astype('float32')
    prediction = model.predict(input_df)[0]
    if prediction < 20:
        return 0
    return round(prediction, 2)


def recommend(series: pd.Series, predicted_power: float) -> str:
    device = str(series['device_type']).lower()
    room = str(series['room']).lower()
    status = str(series['status']).lower()
    user_present = int(series['user_present'])
    activity = str(series['activity']).lower()
    indoor_temp = float(series['indoor_temp'])
    outdoor_temp = float(series['outdoor_temp'])
    light_level = float(series['light_level'])
    timestamp = pd.to_datetime(series['timestamp'])
    hour = timestamp.hour
    power_actual = float(series['power_watt'])
    price_kWh = int(series['price_kWh'])
    home_id = int(series.get('home_id', -1))
    humidity = float(series['humidity'])

    time_str = timestamp.strftime("[%Y-%m-%d %H:%M:%S]")
    messages = []

    # ==== 1. Nhóm gợi ý TIẾT KIỆM ĐIỆN ====
    if device == 'light' and status == 'on' and light_level >= 500:
        messages.append(f"{time_str} Phòng {room} đang có đủ ánh sáng tự nhiên ({light_level} lux). Hãy tắt đèn để tiết kiệm điện.")

    if device == 'washer' and status == 'off' and 21 <= hour < 23 and price_kWh == 1500:
        messages.append(f"{time_str} Đây là giờ điện rẻ (sau 22h). Hãy tranh thủ giặt đồ để tiết kiệm chi phí.")

    # ==== 2. Nhóm gợi ý AN TOÀN & SỨC KHỎE ====
    if status == 'on' and activity == 'sleeping' and device not in ['fridge', 'air_conditioner']:
        messages.append(f"{time_str} Bạn đang ngủ nhưng thiết bị '{device}' tại {room} vẫn đang bật. Hãy tắt để ngủ ngon hơn và tiết kiệm điện.")

    if device == 'tv' and status == 'on' and hour >= 1 and user_present == 1:
        messages.append(f"{time_str} Đã quá khuya ({hour}h), bạn vẫn đang xem TV. Hãy nghỉ ngơi để đảm bảo sức khỏe.")

    if device == 'air_conditioner' and status == 'on' and activity == 'cooking':
        messages.append(f"{time_str} Bạn đang nấu ăn. Hạn chế dùng điều hòa khi nấu để tiết kiệm điện và tăng hiệu quả làm mát.")

    # ==== 3. Nhóm gợi ý HÀNH VI BẤT THƯỜNG ====
    if status == 'on' and predicted_power > 0 and power_actual > 1.5 * predicted_power:
        if device == 'fridge':
            messages.append(f"{time_str} Tủ lạnh tại {room} đang tiêu thụ điện cao bất thường ({power_actual:.0f}W). Hãy kiểm tra xem cửa tủ có bị hở không.")
        elif device == 'air_conditioner':
            messages.append(f"{time_str} Điều hòa tại {room} đang tiêu thụ công suất cao bất thường ({power_actual:.0f}W). Có thể do nhiệt độ cài đặt quá thấp hoặc lọc bụi bị bẩn.")
        elif device == 'light':
            messages.append(f"{time_str} Đèn tại {room} đang tiêu thụ điện bất thường ({power_actual:.0f}W). Hãy kiểm tra loại đèn và độ sáng hiện tại.")
        elif device == 'tv':
            messages.append(f"{time_str} TV tại {room} đang tiêu thụ công suất cao hơn bình thường ({power_actual:.0f}W). Có thể do âm lượng cao hoặc thiết bị ngoại vi đang dùng.")
        elif device == 'washer':
            messages.append(f"{time_str} Máy giặt tại {room} đang hoạt động với công suất cao bất thường ({power_actual:.0f}W). Kiểm tra chế độ giặt và tải trọng quần áo.")
        else:
            messages.append(f"{time_str} Thiết bị '{device}' tại {room} đang tiêu thụ công suất cao bất thường ({power_actual:.0f}W). Hãy kiểm tra thiết bị hoặc cài đặt.")

    if device == 'tv' and status == 'on' and activity != 'watching_tv':
            messages.append(f"{time_str} TV đang bật dù bạn không xem. Hãy tắt để tập trung và tiết kiệm điện.")

    if status == 'on' and user_present == 0:
            messages.append(f"{time_str} Thiết bị '{device}' tại {room} đang bật dù không có ai trong phòng. Hãy tắt thiết bị để tiết kiệm điện.")

    # ==== 4. Nhóm gợi ý theo MÔI TRƯỜNG ====
    if humidity > 70 and outdoor_temp < indoor_temp: # Giả sử ngưỡng là 70% độ ẩm cao. Điều chỉnh nếu cần.
        messages.append(f"{time_str} Độ ẩm đang cao ({humidity:.1f}%). Hãy đóng cửa sổ hoặc bật hút ẩm nếu thấy bí bách.")

    if device == 'air_conditioner' and status == 'on' and outdoor_temp < indoor_temp:
        messages.append(f"{time_str} Nhiệt độ ngoài trời ({outdoor_temp}°C) mát hơn trong phòng ({indoor_temp}°C). Cân nhắc tắt điều hòa và mở cửa sổ.")

    if device == 'light' and status == 'on' and light_level >= 100:
        messages.append(f"{time_str} Phòng {room} đang có nhiều ánh sáng tự nhiên ({light_level} lux). Bạn có thể tắt đèn '{device}' để tiết kiệm điện.")

    # ==== 5. Nhóm gợi ý BẬT thiết bị khi cần ====
    if status == 'off' and predicted_power > 100 and user_present == 1:
        if device == 'air_conditioner' and indoor_temp >= 25:
            messages.append(f"{time_str} Nhiệt độ trong phòng là {indoor_temp}°C. Bạn có thể bật điều hòa để mát hơn.")
        # elif device == 'tv' and activity == 'watching_tv':
        #     messages.append(f"{time_str} Có vẻ bạn đang muốn xem TV. Hãy bật TV tại {room} nếu cần.")
        elif device == 'light' and light_level < 500 and activity != 'sleeping':
            messages.append(f"{time_str} Phòng {room} đang thiếu sáng ({light_level} lux). Bật đèn để cải thiện ánh sáng nhé.")
        elif device == 'washer' and activity in ['idle', 'watching_tv'] and hour >= 21:
            messages.append(f"{time_str} Bạn có thể giặt đồ vào thời điểm này để tiết kiệm điện.")

 # Nếu không có gợi ý nào, không trả về nội dung
    if not messages:
        messages.append(f"{time_str} Thiết bị '{device}' tại {room} đang hoạt động bình thường.")

    return "\n".join(messages)




model, label_encoders = retrain_models()
record_day = pd.DataFrame() 

try:
    for message in consumer:
        record = message.value
        new_row = pd.DataFrame([record])

        # Lấy ngày từ timestamp
        record_time = pd.to_datetime(new_row['timestamp'].iloc[0])
        record_date = record_time.date()

        # Nếu đã sang ngày mới
        if current_day is not None and record_date != current_day:
            output_file = data_dir / f"data_{current_day.year}.csv"

            if output_file.exists():
                record_day.to_csv(output_file, mode='a', header=False, index=False)
            else:
                record_day.to_csv(output_file, mode='w', header=True, index=False)

            print(f"[INFO] Đã lưu dữ liệu cho ngày {current_day}")
            record_day = pd.DataFrame()
            model, label_encoders = retrain_models()

        current_day = record_date

        # --- Xử lý và dự đoán ---
        sample_record = new_row.iloc[0]
        processed_record = xu_ly_ban_ghi_dau_vao(new_row)
        if isinstance(processed_record, pd.Series):
            processed_record = processed_record.to_frame().T

        a = du_doan_cong_suat(processed_record, model, label_encoders)
        print(a, sample_record['power_watt'])

        message_text = recommend(sample_record, a)

        # Chỉ xử lý nếu có gợi ý
        if message_text.strip():
            new_row['predicted_power'] = a
            new_row['suggestion'] = message_text

            # Thêm vào record_day
            record_day = pd.concat([record_day, new_row], ignore_index=True)

            # Gửi gợi ý lên Kafka
            suggestion_producer.send('smarthome-suggestions', value={
                "suggestion": message_text
            })

except KeyboardInterrupt:
    print("[INFO] KeyboardInterrupt - Dừng nhận dữ liệu.")

finally:
    if not record_day.empty and current_day is not None:
        output_file = data_dir / f"data_{current_day.year}.csv"
        if output_file.exists():
            record_day.to_csv(output_file, mode='a', header=False, index=False)
        else:
            record_day.to_csv(output_file, mode='w', header=True, index=False)
        print(f"[INFO] Đã lưu dữ liệu cuối cùng cho ngày {current_day}")
    
    print("[INFO] Đã dừng nhận dữ liệu và lưu hoàn tất.")

