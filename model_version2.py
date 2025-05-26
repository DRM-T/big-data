import pandas as pd
import lightgbm as lgb
import xgboost as xgb
import catboost
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
import matplotlib.pyplot as plt
from datetime import timedelta
import time  # Thêm thư viện time để đo thời gian
import pandas as pd
import time
import lightgbm as lgb
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import numpy as np

# Models
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
import catboost
import pandas as pd
import lightgbm as lgb
import xgboost as xgb
import catboost
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
import matplotlib.pyplot as plt
from datetime import timedelta
import time  # Thêm thư viện time để đo thời gian

# --- 1. Đọc dữ liệu ---
df = pd.read_csv('data/data_2022.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# --- 2. Hàm feature engineering ---
def feature_engineering(df):
    df = df.copy()
    df['timestamp_yesterday'] = df['timestamp'] - pd.Timedelta(days=2)
    df['total_power_home_yesterday'] = df.groupby(['home_id', 'timestamp_yesterday'])['power_watt'].transform('sum')
    df = df.drop(columns=['status', 'timestamp', 'device_id', 'timestamp_yesterday', 'price_kWh'])
    return df

# --- 3. Áp dụng feature engineering ---
df_fe = feature_engineering(df)

# --- 4. Chuẩn bị dữ liệu ---
target = 'power_watt'
X = df_fe.drop(columns=[target])
y = df_fe[target]

# Mã hoá các cột phân loại
categorical_cols = X.select_dtypes(include='object').columns
label_encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    X[col] = le.fit_transform(X[col].astype(str))
    label_encoders[col] = le

# --- 5. Tách tập train/test ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 6. Khởi tạo các mô hình ---
models = {
    'LightGBM': lgb.LGBMRegressor(objective='regression', n_estimators=100, random_state=42),
    'Linear Regression': LinearRegression(),
    'Decision Tree': DecisionTreeRegressor(random_state=42),
    'XGBoost': xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100, random_state=42),
    'CatBoost': catboost.CatBoostRegressor(iterations=100, random_seed=42, verbose=0)  # CatBoost không cần chuyển đổi nhãn như LightGBM
}

# --- 6. Hàm huấn luyện và đánh giá mô hình ---
def train_and_evaluate_model(name, model):
    start_time = time.time()  # Bắt đầu thời gian huấn luyện
    model.fit(X_train, y_train)
    training_time = time.time() - start_time  # Thời gian huấn luyện

    start_time_pred = time.time()  # Bắt đầu thời gian dự đoán
    y_pred = model.predict(X_test)
    prediction_time = time.time() - start_time_pred  # Thời gian dự đoán

    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mse)  # Root Mean Squared Error
    
    # In ra thời gian và các chỉ số
    print(f"{name} | MSE: {mse:.2f} | R2: {r2:.4f} | MAE: {mae:.2f} | RMSE: {rmse:.2f} | Training Time: {training_time:.2f}s | Prediction Time: {prediction_time:.2f}s")
    
    return mse, r2, mae, rmse, training_time, prediction_time

# --- 8. Huấn luyện và đánh giá các mô hình ---
results = {}
for name, model in models.items():
    mse, r2, mae, rmse, training_time, prediction_time = train_and_evaluate_model(name, model)
    results[name] = {'MSE': mse, 'R2': r2, 'MAE': mae, 'RMSE': rmse, 'Training Time': training_time, 'Prediction Time': prediction_time}

# --- 9. Hiển thị kết quả ---
results_df = pd.DataFrame(results).T
print("\nTổng hợp kết quả các mô hình:")
print(results_df)

# --- 10. Vẽ biểu đồ so sánh các mô hình ---
results_df[['MSE', 'R2', 'MAE', 'RMSE']].plot(kind='bar', figsize=(10, 6))
plt.title("So sánh hiệu suất các mô hình")
plt.ylabel("Giá trị")
plt.xticks(rotation=0)
plt.tight_layout()
plt.show()

# --- 11. Vẽ biểu đồ thời gian huấn luyện và dự đoán ---
results_df[['Training Time', 'Prediction Time']].plot(kind='bar', figsize=(10, 6))
plt.title("So sánh thời gian huấn luyện và dự đoán của các mô hình")
plt.ylabel("Thời gian (giây)")
plt.xticks(rotation=0)
plt.tight_layout()
plt.show()
