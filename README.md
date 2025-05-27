# Tối ưu hóa hành vi sử dụng thiết bị trong nhà thông minh với công nghệ dữ liệu lớn

## Mô tả tổng quan

Dự án hướng tới xây dựng một hệ thống sử dụng công nghệ dữ liệu lớn nhằm tối ưu hóa hành vi tiêu thụ điện năng trong môi trường nhà thông minh. Trong bối cảnh thiết bị IoT ngày càng phổ biến và nhu cầu tiết kiệm năng lượng gia tăng, hệ thống giúp người dùng điều chỉnh thói quen sử dụng thiết bị một cách hiệu quả, từ đó giảm chi phí sinh hoạt và góp phần bảo vệ môi trường.

## Mục tiêu

* **Tạo dữ liệu mô phỏng:**
  Do thiếu dữ liệu thực tế (thiếu các trường và mối tương quan đặc trưng), nhóm xây dựng một **bộ dữ liệu giả lập** mô phỏng hành vi sử dụng thiết bị, đặc điểm môi trường, và trạng thái tiêu thụ.
  → Chi tiết trong notebook `Generate_Analyze_SelectModel.ipynb`.

* **Huấn luyện mô hình ban đầu:**

  * Dữ liệu khởi tạo từ file `data/data_2022.csv`.
  * Sử dụng **LightGBM** để huấn luyện mô hình dự đoán công suất và sinh gợi ý.

* **Cập nhật mô hình định kỳ:**

  * Hệ thống tự động **train lại mỗi ngày** với **dữ liệu của 2 năm gần nhất** để đảm bảo tính chính xác và thích ứng.
  * Mô hình được nạp lại và sử dụng ngay trong các pipeline xử lý realtime.

* **Xử lý dữ liệu thời gian thực bằng Kafka:**

  * 10 hộ gia đình mô phỏng gửi dữ liệu 15 phút/lần.
  * Hệ thống xử lý và phản hồi gợi ý tức thời.

* **Giao diện người dùng:**

  * Flask-based Web UI cho phép theo dõi gợi ý, kiểm thử thủ công và xem thống kê tiêu thụ điện năng.

---
## Công nghệ sử dụng

* **Ngôn ngữ lập trình:** Python
* **Giao diện Web:** Flask, HTML, JavaScript (SSE, Chart.js)
* **Xử lý dữ liệu:** pandas, numpy, matplotlib
* **Tiền xử lý:** LabelEncoder, OneHotEncoder, StandardScaler
* **Mô hình học máy:** LightGBM, XGBoost, CatBoost, Linear Regression, Random Forest, Decision Tree
* **Đánh giá mô hình:** MSE, MAE, R² (sklearn.metrics)
* **Hệ thống xử lý luồng:** Apache Kafka (thông qua kafka-python)

---

## Cấu hình hệ thống Kafka
![image](https://github.com/user-attachments/assets/90e1d3a4-0b00-4586-975d-015ad029acd7)

Hệ thống sử dụng **1 Kafka broker** và **4 topic**, chia thành 2 nhóm:

### Dữ liệu thời gian thực (3 partitions/topic)

* `realtime-smarthome-data`: topic nhận dữ liệu từ các hộ gia đình (giả lập).
* `smarthome-suggestions`: topic lưu gợi ý tiêu thụ tương ứng.

### Dữ liệu kiểm thử (1 partition/topic)

* `smarthome-test-data`: nhận bản ghi từ người dùng gửi qua giao diện.
* `smarthome-test-suggestions`: chứa gợi ý tương ứng từ bản ghi kiểm thử.

---
## Cấu trúc thư mục dự án

```plaintext
.
├── app_ui.py                        # Giao diện người dùng (UI)
├── catboost_info/                  # Log huấn luyện CatBoost
├── data/
│   ├── data_2022.csv               # Dữ liệu huấn luyện ban đầu
│   └── ...                         # Các file dữ liệu khác theo thời gian
├── logic_gen_data.py              # Sinh dữ liệu giả lập cho 10 hộ gia đình
├── model_version1.py              # So sánh mô hình (chưa có feature lịch sử)
├── model_version2.py              # So sánh mô hình (có feature lịch sử tiêu thụ)
├── notification_suggest.py        # Consumer gợi ý → gửi đến frontend
├── realtime_data_simulation.py    # Kafka Producer gửi dữ liệu giả lập
├── send_single_record_test_model.py # Gửi bản ghi test từ terminal
├── suggesttion_model.py           # Train mô hình + xử lý dữ liệu realtime
├── test_notification_suggest.py   # Kiểm thử quá trình gửi gợi ý
├── test_suggesttion_model.py      # Kiểm thử dự đoán từ 1 bản ghi test
├── templates/
│   └── index.html                 # Giao diện HTML hiển thị trên web
└── README.md                      # Tài liệu mô tả dự án
```

---

## Cách sử dụng hệ thống

1. **Khởi động Kafka & Zookeeper.**

2. **Chạy các thành phần chính:**

   ```bash
   python suggesttion_model.py              # Train định kỳ + xử lý realtime
   python notification_suggest.py           # Gửi gợi ý đến giao diện người dùng
   python realtime_data_simulation.py       # Gửi dữ liệu giả lập vào Kafka
   python app_ui.py                         # Chạy giao diện Flask
   ```
![image](https://github.com/user-attachments/assets/1cffc1fc-105c-4cc6-ba8b-27c793d9edb3)
![image](https://github.com/user-attachments/assets/b3fda698-efbb-419a-904e-9b3627cc359a)
![image](https://github.com/user-attachments/assets/1322ed78-3d4e-4cca-9549-c01d6cd8381f)
![image](https://github.com/user-attachments/assets/e34917c3-658f-4527-992f-932246176c8a)
![image](https://github.com/user-attachments/assets/6806ec03-e61c-4ea4-8bb2-cd802e32be84)


3. **(Tùy chọn) Gửi bản ghi kiểm thử từ terminal:**

   ```bash
   python send_single_record_test_model.py  # Gửi 1 bản ghi kiểm tra
   ```

---


## Nhóm phát triển

* **Hoàng Đình Hoàn** – 22024577
* **Lưu Quang Khải** – 22024521
* **Phùng Khôi Nguyên** – 22024503
* **Nguyễn Thị Ánh Tuyết** – 22024523

> Sinh viên Trường Đại học Công nghệ – Đại học Quốc gia Hà Nội
> Dự án thực hiện trong khuôn khổ học phần **Kỹ thuật và Công nghệ Dữ liệu Lớn**

---
