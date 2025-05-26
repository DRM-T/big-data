#@title Dự đoán công suất tiêu thụ thiết bị điện bằng LightGBM
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
# import matplotlib.pyplot as plt # Not used, can be removed
from datetime import timedelta
import json
import numpy as np
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime
# from sklearn.tree import DecisionTreeClassifier # Not used, can be removed
# from sklearn.model_selection import train_test_split # Already imported above
# from sklearn.metrics import accuracy_score # Not used, can be removed
import time # Import time for polling timeout

# Consumer để nhận dữ liệu kiểm tra
consumer_test = KafkaConsumer(
    'smarthome-test-data', # <-- New topic
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='smarthome-test-consumer-group', # <-- New group_id
    auto_offset_reset='latest', # Bắt đầu đọc từ tin nhắn mới nhất khi nhóm consumer mới
    enable_auto_commit=True,
    auto_commit_interval_ms=1000
)

# Producer để gửi gợi ý kiểm tra
suggestion_producer_test = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Đảm bảo file data_2022.csv nằm trong thư mục 'data' hoặc điều chỉnh đường dẫn
try:
    df = pd.read_csv('data/data_2022.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
except FileNotFoundError:
    print("Lỗi: Không tìm thấy file data/data_2022.csv. Vui lòng đảm bảo file tồn tại.")
    # Tạo DataFrame rỗng hoặc xử lý lỗi phù hợp nếu không có file dữ liệu lịch sử
    df = pd.DataFrame()
except Exception as e:
    print(f"Lỗi khi đọc hoặc xử lý data_2022.csv: {e}")
    df = pd.DataFrame()


def info_(df):
    if df.empty:
        return pd.DataFrame() # Return empty if input df is empty
    df = df.copy()
    # Ensure timestamp is datetime before timedelta operation
    if 'timestamp' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
             df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
             df = df.dropna(subset=['timestamp']) # Drop rows where conversion failed
    else:
         # If timestamp column doesn't exist, return empty or handle as error
         print("Warning: 'timestamp' column not found in DataFrame passed to info_.")
         return pd.DataFrame()


    if df.empty:
         print("Warning: DataFrame is empty after timestamp processing in info_.")
         return pd.DataFrame()


    df['timestamp_yesterday'] = df['timestamp'] - pd.Timedelta(days=2)
    # Groupby operations are sensitive to empty groups, add checks if needed
    if not df.empty:
        df['total_power_home_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday'])['power_watt'].transform('sum')
        df['total_power_device_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday', 'device_type'])['power_watt'].transform('sum')
    else:
         df['total_power_home_yesterday'] = 0
         df['total_power_device_yesterday'] = 0

    return df

# Dung cho rcm 1 ban ghi (dữ liệu lịch sử tĩnh)
# Chỉ tính toán nếu df không rỗng
data_event = info_(df)
# Thêm cột lookup_key vào data_event ngay khi tạo để sử dụng sau này
if not data_event.empty:
     data_event['lookup_key'] = data_event['timestamp'].astype(str) + '_' + data_event['home_id'].astype(str) + '_' + data_event['device_type'].astype(str)


#-----------------------------------------
# Feature engineering function used for initial training and potentially real-time processing
def feature_engineering(df):
    df = df.copy()
    # Ensure 'timestamp' is datetime
    if 'timestamp' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
             df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        # Handle potential NaT values after conversion
        df = df.dropna(subset=['timestamp'])
    else:
         print("Warning: 'timestamp' column not found in DataFrame passed to feature_engineering.")
         # Decide how to handle: return empty or continue without timestamp features
         # For now, returning empty if timestamp is critical for subsequent steps
         # If timestamp is needed only for feature extraction dropped later, might proceed
         return pd.DataFrame() # Returning empty if timestamp is missing

    if df.empty:
        print("Warning: DataFrame is empty after timestamp processing in feature_engineering.")
        return pd.DataFrame()


    # In a real-time scenario, getting 'yesterday's' power from a static file
    # is problematic. For live data, this should ideally come from a real-time
    # state store or database summarizing historical data.
    # Keeping placeholders for compatibility with the model trained on static data.
    df['total_power_home_yesterday'] = 0.0 # Placeholder for real-time
    df['total_power_device_yesterday'] = 0.0 # Placeholder for real-time

    # Drop columns, keeping 'device_type' for potential encoding later if needed by the model
    cols_to_drop = ['status', 'timestamp', 'device_id', 'timestamp_yesterday', 'user_present', 'room', 'price_kWh', 'day_of_week', 'hour_of_day']
    df = df.drop(columns=[col for col in cols_to_drop if col in df.columns], errors='ignore')

    return df

# Train model lan dau chi khi df huấn luyện không rỗng
model = None # Initialize model
label_encoders = {} # Initialize label_encoders
if not df.empty:
    df_fe = feature_engineering(df.copy()) # Use a copy
    target = 'power_watt'
    # Handle case where df_fe might become empty after feature engineering (e.g., no valid timestamps)
    if not df_fe.empty and target in df_fe.columns:
        X = df_fe.drop(columns=[target])
        y = df_fe[target]

        # Handle potential empty X after dropping target
        if not X.empty:
            categorical_cols = X.select_dtypes(include='object').columns
            label_encoders = {}
            for col in categorical_cols:
                le = LabelEncoder()
                # Handle potential empty or uniform data in a categorical column
                try:
                    X[col] = le.fit_transform(X[col].astype(str))
                    label_encoders[col] = le
                except ValueError as e:
                    print(f"Warning: Could not fit LabelEncoder on column '{col}'. Skipping or handling as non-categorical. Error: {e}")
                    # Optionally drop the column or handle it differently if encoding fails
                    # X = X.drop(columns=[col])
                    pass # Continue without encoding this column


            # Handle potential empty X after encoding issues
            if not X.empty:
                # Ensure X and y have the same number of samples after dropping NaNs etc.
                # This is implicitly handled by train_test_split if X and y are aligned
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                model = lgb.LGBMRegressor(objective='regression', n_estimators=100)
                model.fit(X_train, y_train)

                # Evaluation only if test sets are not empty
                if not X_test.empty:
                    y_pred = model.predict(X_test)
                    print(f"Initial Model Training Complete.")
                    print(f"MSE: {mean_squared_error(y_test, y_pred):.2f}")
                    print(f"R2: {r2_score(y_test, y_pred):.2f}")
                else:
                    print("Warning: Test set is empty. Skipping model evaluation.")
                    print(f"Initial Model Training Complete.") # Indicate training finished
            else:
                 print("Lỗi: X train rỗng sau khi xử lý đặc trưng và mã hóa.")
        else:
             print("Lỗi: X train rỗng sau khi bỏ cột target.")
    else:
         print("Lỗi: DataFrame sau xử lý đặc trưng rỗng hoặc thiếu cột target.")
else:
    print("Warning: Dữ liệu lịch sử (data_2022.csv) trống hoặc không thể đọc. Model sẽ không được train.")


#-------------------------------------------------------------
# Retraining function (currently unused in main loop)
# Keep for completeness, assuming it might be used later
def retrain_models(df):
    if df.empty:
        print("Warning: Input DataFrame for retraining is empty.")
        return None, {} # Return None model and empty encoders

    df_fe = feature_engineering(df.copy())
    target = 'power_watt'
    if df_fe.empty or target not in df_fe.columns:
         print("Warning: DataFrame after feature engineering is empty or missing target for retraining.")
         return None, {}

    X = df_fe.drop(columns=[target])
    y = df_fe[target]

    if X.empty:
         print("Warning: X for retraining is empty after dropping target.")
         return None, {}

    categorical_cols = X.select_dtypes(include='object').columns
    label_encoders_retrain = {}
    for col in categorical_cols:
        le = LabelEncoder()
        try:
            X[col] = le.fit_transform(X[col].astype(str))
            label_encoders_retrain[col] = le
        except ValueError as e:
             print(f"Warning: Could not fit LabelEncoder on column '{col}' during retraining. Error: {e}")
             pass # Continue

    if X.empty:
         print("Warning: X for retraining is empty after encoding.")
         return None, {}


    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    retrained_model = lgb.LGBMRegressor(objective='regression', n_estimators=100)
    retrained_model.fit(X_train, y_train)
    # Evaluation only if test set is not empty
    if not X_test.empty:
        y_pred = retrained_model.predict(X_test)
        print(f"Retrained Model MSE: {mean_squared_error(y_test, y_pred):.2f}")
    else:
         print("Warning: Test set for retraining evaluation is empty.")

    return retrained_model, label_encoders_retrain # Return updated model and encoders


def xu_ly_ban_ghi_dau_vao(record, history_data_event):
    """
    Processes a single record for prediction.
    Looks up historical data from history_data_event (which is static data_event here).
    Note: This lookup logic might be inefficient/incorrect for real-time streaming.
    A real-time system would likely use a state store or database for historical lookups.
    """
    if isinstance(record, dict):
        record_df = pd.DataFrame([record])
    elif isinstance(record, pd.Series):
        record_df = record.to_frame().T
    else:
         # Assume it's already a DataFrame or similar structure
         record_df = record.copy()

    record_df = record_df.reset_index(drop=True) # Reset index

    # Ensure timestamp is datetime for operations
    if 'timestamp' in record_df.columns:
        if not pd.api.types.is_datetime64_any_dtype(record_df['timestamp']):
            record_df['timestamp'] = pd.to_datetime(record_df['timestamp'], errors='coerce')
        record_df = record_df.dropna(subset=['timestamp']) # Drop rows where conversion failed
    else:
        print("Error: 'timestamp' column not found in record.")
        return pd.DataFrame()


    if record_df.empty:
        print("Warning: Record DataFrame is empty after timestamp processing.")
        return pd.DataFrame() # Return empty if timestamp conversion failed

    ts_original = record_df['timestamp'].iloc[0]
    # For lookup in data_event (which is 2022 data), adjust timestamp
    # This lookup is flawed for non-2022 real-time data
    ts_lookup = ts_original.replace(year=2022)


    # Initialize historical power columns
    record_df['total_power_home_yesterday'] = 0.0 # Use float for consistency
    record_df['total_power_device_yesterday'] = 0.0 # Use float for consistency

    # Perform lookup in the static historical data_event
    # Use .get() to safely access columns
    if not history_data_event.empty and 'lookup_key' in history_data_event.columns:
        # Format lookup_key consistently
        # Ensure home_id and device_type exist before creating lookup_key
        home_id_val = record_df['home_id'].iloc[0] if 'home_id' in record_df.columns else 'unknown_home_id'
        device_type_val = record_df['device_type'].iloc[0] if 'device_type' in record_df.columns else 'unknown_device_type'
        lookup_key = ts_lookup.strftime('%Y-%m-%d %H:%M:%S') + '_' + str(home_id_val) + '_' + str(device_type_val)

        # Attempt lookup using the key
        match = history_data_event[history_data_event['lookup_key'] == lookup_key]

        if not match.empty:
            # Found a match for the historical timestamp, home_id, and device_type
            # Use .iloc[0] to get the scalar value, and .fillna(0.0) for safety
            # Check if columns exist in the match DataFrame before accessing
            if 'total_power_home_yesterday' in match.columns:
                 record_df['total_power_home_yesterday'] = match['total_power_home_yesterday'].iloc[0].fillna(0.0)
            if 'total_power_device_yesterday' in match.columns:
                 record_df['total_power_device_yesterday'] = match['total_power_device_yesterday'].iloc[0].fillna(0.0)
        # else: historical data not found for this specific timestamp/device 2 days ago in the static file


    cols_to_drop = [
        'index', 'status', 'timestamp', 'device_id', 'timestamp_yesterday',
        'user_present', 'room', 'price_kWh', 'day_of_week',
        'hour_of_day', 'power_watt' # Keep device_type for feature engineering later
    ]
    # Drop columns, ignoring errors if columns don't exist
    record_processed = record_df.drop(columns=[col for col in cols_to_drop if col in record_df.columns], errors='ignore')

    # Ensure device_type is still present if it's used by feature_engineering or model directly
    # Looking at feature_engineering, it drops device_type.
    # Looking at du_doan_cong_suat, it expects columns from model.booster_.feature_name()
    # which might include device_type if it was categorical during training.
    # Re-add device_type if it was dropped but needed for encoding
    if 'device_type' not in record_processed.columns and 'device_type' in record_df.columns:
         record_processed['device_type'] = record_df['device_type']


    return record_processed


def du_doan_cong_suat(input_data, model, label_encoders):
    # Check if model was successfully trained
    if model is None:
        print("Error: Model not trained. Cannot make prediction.")
        return 0.0

    input_df = input_data.copy()
    if input_df.empty:
        print("Warning: Input data for prediction is empty.")
        return 0.0 # Return 0 power if input data is empty

    # Ensure 'device_type' is treated as object if present before encoding
    if 'device_type' in input_df.columns:
         input_df['device_type'] = input_df['device_type'].astype(str)


    # Get expected features from the training data
    try:
        # Check if model has booster_ attribute
        if not hasattr(model, 'booster_') or not hasattr(model.booster_, 'feature_name'):
             print("Error: Model object does not have expected structure for feature names.")
             return 0.0

        expected_features = model.booster_.feature_name()
    except Exception as e:
        print(f"Error getting expected features from model: {e}")
        return 0.0 # Cannot proceed if model structure is inaccessible


    # Add missing columns and ensure order
    processed_input_df = pd.DataFrame(index=input_df.index) # Create a new df with the same index

    for col in expected_features:
        if col in input_df.columns:
            processed_input_df[col] = input_df[col]
        else:
            # Add missing columns with a default value (0 for numerical, '' for categorical)
             if col in label_encoders: # Assume categorical if in label_encoders
                 processed_input_df[col] = '' # Use empty string for unseen categorical? Or a specific indicator
             else:
                processed_input_df[col] = 0.0 # Assume numerical default


    # Ensure columns are in the same order as training data
    input_df_ordered = processed_input_df[expected_features].copy() # Use .copy() to avoid SettingWithCopyWarning


    # Apply label encoding to categorical columns
    for col in input_df_ordered.select_dtypes(include='object').columns:
        if col in label_encoders:
            le = label_encoders[col]
            # Handle unseen values during inference
            # Use .apply with lambda and a default value if transform fails
            input_df_ordered[col] = input_df_ordered[col].apply(
                lambda x: le.transform([str(x)])[0] if str(x) in le.classes_ else -1
            )
        else:
             # Handle object columns that were not encoded during training?
             # Convert to string to prevent errors during astype(float32) if they remain objects
             input_df_ordered[col] = input_df_ordered[col].astype(str)


    # Ensure correct dtype for prediction (all numerical after encoding)
    # Coerce all columns to numeric, handling potential errors by turning them into NaN, then fill NaN
    for col in input_df_ordered.columns:
         input_df_ordered[col] = pd.to_numeric(input_df_ordered[col], errors='coerce').fillna(0.0) # Coerce to numeric, fill NaNs


    input_df_final = input_df_ordered.astype('float32') # Ensure correct final dtype


    try:
        prediction = model.predict(input_df_final)[0]
        # Ensure prediction is non-negative
        prediction = max(0.0, prediction) # Use 0.0 for float consistency
    except Exception as e:
        print(f"Error during prediction: {e}")
        prediction = 0.0 # Default to 0 on error


    return round(prediction, 2)


# recommend function remains the same
def recommend(series: pd.Series, predicted_power: float) -> str:
    """
    Gợi ý sử dụng thiết bị điện dựa trên ngữ cảnh và kết quả dự đoán công suất.

    Parameters:
        series: pandas.Series - Một bản ghi thiết bị (dòng dữ liệu).
        predicted_power: float - Giá trị công suất dự đoán của thiết bị.

    Returns:
        str - Thông điệp gợi ý cho người dùng (có thể rỗng nếu không có gợi ý).
    """

    # Trích xuất các giá trị cần thiết
    # Use .get() with default values to handle missing keys gracefully
    device = str(series.get('device_type', 'unknown_device')).lower()
    room = str(series.get('room', 'unknown_room')).lower()
    status = str(series.get('status', 'off')).lower()  # "on" / "off"
    user_present = int(series.get('user_present', 0))
    activity = str(series.get('activity', 'unknown')).lower()
    indoor_temp = float(series.get('indoor_temp', 25.0))
    outdoor_temp = float(series.get('outdoor_temp', 28.0))
    light_level = float(series.get('light_level', 300.0))
    humidity = float(series['humidity'])
    # Attempt to parse timestamp, use current time if fails
    timestamp_str = series.get('timestamp')
    try:
        timestamp = pd.to_datetime(timestamp_str)
    except (ValueError, TypeError):
        timestamp = datetime.now()
        print(f"Warning: Could not parse timestamp '{timestamp_str}'. Using current time.")

    hour = timestamp.hour
    power_actual = float(series.get('power_watt', 0.0))
    price_kWh = int(series.get('price_kWh', 2700))

    time_str = timestamp.strftime("[%Y-%m-%d %H:%M:%S]")
    device_id = series.get('device_id', 'unknown_id')
    home_id = series.get('home_id', series.get('home_id_manual', 'unknown_home')) # Try getting from home_id_manual if present


    messages = []

    # Add prefix to easily identify test suggestions
    prefix = f"[TEST - Home {home_id} - Device {device_id}]"

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
            messages.append(f"{time_str} Tủ lạnh tại {room} đang tiêu thụ điện cao bất thường ({power_actual:.0f}W). Hãy kiểm tra xem cửa tủ có bị mở hoặc kín không.")
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

    if device == 'air_conditioner' and status == 'on' and outdoor_temp + 2 < indoor_temp:
        messages.append(f"{time_str} Nhiệt độ ngoài trời ({outdoor_temp}°C) mát hơn trong phòng ({indoor_temp}°C). Cân nhắc tắt điều hòa và mở cửa sổ.")

    # ==== 5. Nhóm gợi ý BẬT thiết bị khi cần ====
    if status == 'off' and predicted_power > 100 and user_present == 1:
        if device == 'air_conditioner' and indoor_temp >= 28:
            messages.append(f"{time_str} Nhiệt độ trong phòng là {indoor_temp}°C. Bạn có thể bật điều hòa để mát hơn.")
        elif device == 'tv' and activity == 'watching_tv':
            messages.append(f"{time_str} Có vẻ bạn đang muốn xem TV. Hãy bật TV tại {room} nếu cần.")
        elif device == 'light' and light_level < 100 and activity != 'sleeping':
            messages.append(f"{time_str} Phòng {room} đang thiếu sáng ({light_level} lux). Bật đèn để cải thiện ánh sáng nhé.")
        elif device == 'washer' and activity in ['idle', 'watching_tv'] and hour >= 21:
            messages.append(f"{time_str} Bạn có thể giặt đồ vào thời điểm này để tiết kiệm điện.")

    # 10. Không có gợi ý phù hợp - Chỉ thêm nếu không có gợi ý nào khác
    if not messages:
        messages.append(f"{prefix} Thiết bị '{device}' tại {room} đang hoạt động bình thường (Công suất: {power_actual:.0f}W, Dự đoán: {predicted_power:.0f}W).")

    return "\n".join(messages)


# --- Nhận dữ liệu từ Kafka ---
print("[INFO] Starting Kafka consumer for test data...")

# Check if model was trained successfully before starting consumer loop
if model is None:
    print("[ERROR] Model was not trained due to errors or missing data. Cannot process test data. Exiting.")
else:
    try:
        # Infinite loop to continuously poll for messages
        while True:
            # Poll for messages from the test topic with a very short timeout
            # This makes the consumer check for new messages almost constantly
            # Set timeout_ms to a small value (e.g., 50ms)
            # Set max_records to a small value as we expect single records
            messages_test = consumer_test.poll(timeout_ms=50, max_records=10)

            if messages_test:
                # If messages are received (even just one), process them
                print("[INFO] Received test message(s), processing immediately...")
                for tp, records in messages_test.items():
                    for message in records:
                        record = message.value
                        try:
                            print(f"[TEST Data Received] Home: {record.get('home_id')}, Device: {record.get('device_type')}, Power: {record.get('power_watt')}")
                            sample_record_series = pd.Series(record)
                            # For test data, the lookup in data_event might not yield results
                            # but the processing function is designed to handle this.
                            processed_record = xu_ly_ban_ghi_dau_vao(sample_record_series, data_event)

                            if not processed_record.empty:
                                # Ensure label_encoders are passed correctly
                                predicted_power = du_doan_cong_suat(processed_record, model, label_encoders)
                                message_suggestion = recommend(sample_record_series, predicted_power) # Recommend using the same function

                                # Send test suggestion to the new test topic
                                suggestion_producer_test.send('smarthome-test-suggestions', value={
                                    "suggestion": message_suggestion
                                })
                                # Flush the producer to send the message without waiting for batching
                                suggestion_producer_test.flush()
                                print(f"[TEST Suggestion Sent] {message_suggestion.splitlines()[0]}...") # Print first line
                            else:
                                print(f"[TEST Data] Skipping record due to processing error or missing timestamp.")

                        except Exception as e:
                            print(f"[TEST Data Error] Could not process test record {record}: {e}")

                # After processing received messages, immediately poll again
                # No need for a sleep here if messages were processed
                continue # Go to the next iteration of the while loop immediately

            # If no messages were received in the last poll, wait for a very short time
            # This prevents a tight loop and high CPU usage when no messages are arriving
            time.sleep(0.01) # Sleep for 10ms if no messages were found

    except KeyboardInterrupt:
        print("[INFO] Stopped receiving test data.")
    finally:
        # Ensure consumer and producer are closed properly
        if 'consumer_test' in locals() and consumer_test is not None:
            consumer_test.close()
        if 'suggestion_producer_test' in locals() and suggestion_producer_test is not None:
             suggestion_producer_test.flush()

        print("[INFO] Test Consumer and Producer closed.")