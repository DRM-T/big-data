import random
import pandas as pd
import numpy as np
# Tạo home_id từ 1 đến 10
home_ids = list(range(1, 11))

# Tạo mảng delta_time với các giá trị ngẫu nhiên từ 0 đến 60 cho mỗi home_id
delta_times = [random.randint(0, 60) for _ in home_ids]

# Tạo DataFrame từ home_id và delta_time
home_data = pd.DataFrame({
    'home_id': home_ids,
    'delta_time': delta_times
})



# --- Cấu hình thiết bị ---
devices = [
    {'device_id': 'AC_01', 'device_type': 'air_conditioner', 'room': 'bedroom'},
    {'device_id': 'LIGHT_01', 'device_type': 'light', 'room': 'living_room'},
    {'device_id': 'TV_01', 'device_type': 'tv', 'room': 'living_room'},
    {'device_id': 'FRIDGE_01', 'device_type': 'fridge', 'room': 'kitchen'},
    {'device_id': 'WASHER_01', 'device_type': 'washer', 'room': 'laundry_room'},
]

import random

# --- Hàm xác định hành vi người dùng có biến đổi theo ngày ---
def get_user_state(timestamp, delta_m, home_id):
    hour = timestamp.hour + timestamp.minute/60 + delta_m/60 + random.uniform(-1, 0.5)
    weekday = timestamp.weekday()  # 0=Thứ 2, 6=Chủ nhật

    # Tạo sự dao động theo ngày trong tuần (vd: thứ 2 dậy sớm hơn, CN dậy muộn)
    daily_offset = {
        0: -0.5,  # Monday: dậy sớm hơn
        1: -0.2,
        2: 0.0,
        3: 0.2,
        4: 0.3,
        5: 0.5,
        6: 0.7   # Sunday: dậy muộn hơn
    }
    hour += daily_offset.get(weekday, 0)

    # 20% nhà luôn có người
    always_home = [1, 2]
    if home_id in always_home:
        if 0 <= hour < 6.5 or hour >= 22.5:
            return 1, 'sleeping'
        elif 6.5 <= hour < 8 or 17 <= hour < 19.5:
            return 1, 'cooking'
        elif 9 <= hour < 22.5:
            return 1, 'watching_tv'
        else:
            return 1, 'idle'

    # Các nhà còn lại
    if weekday >= 5:  # Cuối tuần
        if 0 <= hour < 7.5 or hour >= 23:
            return 1, 'sleeping'
        elif 7.5 <= hour < 9 or 17 <= hour < 20:
            return 1, 'cooking'
        elif 19 <= hour < 23:
            return 1, 'watching_tv'
        else:
            return 1, 'idle'
    else:  # Trong tuần
        if 0 <= hour < 6.5 or hour >= 22.5:
            return 1, 'sleeping'
        elif 6.5 <= hour < 8 or 17 <= hour < 19.5:
            return 1, 'cooking'
        elif 8 <= hour < 17:
            return 0, 'away'
        elif 19 <= hour < 22.5:
            return 1, 'watching_tv'
        else:
            return 1, 'idle'


# Thời gian mặt trời mọc và lặn (theo tháng)
sun_times = {
    1: (6.5, 17.5), 2: (6.33, 17.75), 3: (6.0, 18.0), 4: (5.5, 18.25),
    5: (5.33, 18.5), 6: (5.25, 18.67), 7: (5.42, 18.58), 8: (5.58, 18.33),
    9: (5.75, 18.0), 10: (6.0, 17.75), 11: (6.25, 17.5), 12: (6.5, 17.33)
}

# Hàm sinh môi trường có yếu tố thay đổi theo mùa
def generate_environment(timestamp):

    noise_rain = random.uniform(0, 1)
    month = timestamp.month
    hour = timestamp.hour
    day_of_year = timestamp.timetuple().tm_yday

    base_month = [0, 15, 16, 19, 23, 28, 30, 31, 30, 28, 25, 21, 17]
    delta_month = [0, 4, 4.5, 5.2, 6, 7.8, 9.2, 9.3, 8.5, 7.9, 6.4, 5, 4]
    random_factors = [0, 6.2, 5.5, 6.4, 7.3, 7.9, 8.4, 9.6, 9.4, 8.9, 7.5, 7, 6.6]


    outdoor_temp = 23 + 8 * np.sin(2 * np.pi * (day_of_year - 98) / 365) + \
                   delta_month[month] * np.sin(((hour - random_factors[month]) / 24) * 2 * np.pi) + \
                   random.uniform(-1, 1)
    if noise_rain > 0.7:
          outdoor_temp -= 6

    indoor_temp = outdoor_temp + random.uniform(-2, 2)
    humidity = 60 - 0.4 * outdoor_temp + random.uniform(-20, 20)
    if noise_rain > 0.7:
          humidity = min(100, humidity + 30)

    sunrise, sunset = sun_times[month]
    if sunrise <= hour <= sunset:
        day_length = sunset - sunrise
        time_since_sunrise = hour - sunrise
        sun_ratio = np.sin((time_since_sunrise / day_length) * np.pi)
        light_level = 100 * (7 + 3*np.sin(2 * np.pi * (day_of_year - 98) / 365)) * sun_ratio
        light_level = max(0, light_level)
    else:
        light_level = random.uniform(0, 100)

    return round(indoor_temp, 1), round(outdoor_temp, 1), round(humidity, 1), round(light_level, 1)

# --- Hàm tính giá điện ---
def get_price_per_kWh(hour):
    if 22 <= hour or hour < 6:
        return 1500
    elif 17 <= hour < 21:
        return 3000
    else:
        return 2500

def get_device_status(home_id, device_type, timestamp, user_present, activity, indoor_temp, light_level):
    power = 0
    status = 'off'
    a = [6, 7, 8, 12, 13, 19, 20, 21, 22, 23]
    noise_on_prob = 0.05
    noise_off_prob = 0.05
    if device_type == 'air_conditioner':
        should_be_on = user_present and indoor_temp >= 28 + random.uniform(-1, 2)
        if (should_be_on and random.random() > noise_off_prob) or \
           (not should_be_on and random.random() < noise_on_prob):
            status = 'on'
            power = random.uniform(700, 800)
            if  indoor_temp >= 28:
                power += ( indoor_temp - 28) * random.uniform(25, 30)

    elif device_type == 'light':
        should_be_on = user_present and light_level < 120 and activity != 'sleeping'
        if (should_be_on and random.random() > noise_off_prob) or \
           (not should_be_on and random.random() < noise_on_prob):
            status = 'on'
            power = random.uniform(100, 200)

    elif device_type == 'tv':
        should_be_on = user_present and activity == 'watching_tv'
        if (should_be_on and random.random() > noise_off_prob) or \
           (not should_be_on and random.random() < noise_on_prob):
            status = 'on'
            power = random.uniform(300, 410)

    elif device_type == 'fridge':
        status = 'on'
        power = random.uniform(200, 310)
        if  indoor_temp >= 28:
                power -= ( indoor_temp - 28) * random.uniform(5, 10)

    elif device_type == 'washer':
        should_be_on = user_present and (timestamp.hour == a[home_id - 1])
        if (should_be_on and random.random() > noise_off_prob) or \
           (not should_be_on and random.random() < noise_on_prob):
            status = 'on'
            power = random.uniform(650, 760)

    return status, round(power, 2)



def generate_device_data(start_time, interval):
    # --- Sinh dữ liệu ---
    data = []
    timestamp = start_time
    for i in range(len(home_data)):
        home_id = home_data['home_id'][i]
        delta_m = home_data['delta_time'][i]

        user_present, activity = get_user_state(timestamp, delta_m, home_id)
        indoor_temp, outdoor_temp, humidity, light_level = generate_environment(timestamp)
        price_kWh = get_price_per_kWh(timestamp.hour)

        for device in devices:
            status, power = get_device_status(
                home_id, device['device_type'], timestamp,
                user_present, activity, indoor_temp, light_level
            )

            data.append({
                'home_id': home_id,
                'timestamp': timestamp,
                'device_id': device['device_type'] + str(home_id),
                'device_type': device['device_type'],
                'room': device['room'],


                'status': status,
                'power_watt': power,       

   
                'user_present': user_present,
                'activity': activity,
                'indoor_temp': indoor_temp,
                'outdoor_temp': outdoor_temp,
                'humidity': humidity,
                'light_level': light_level,
                'day_of_week': timestamp.weekday(),
                'hour_of_day': timestamp.hour,
                'price_kWh': price_kWh
            })
    return data

