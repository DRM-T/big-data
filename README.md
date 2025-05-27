# Tối ưu hóa hành vi sử dụng thiết bị trong nhà thông minh với công nghệ dữ liệu lớn

## Mô tả tổng quan

Dự án tập trung phát triển một hệ thống ứng dụng công nghệ dữ liệu lớn nhằm tối ưu hóa hành vi tiêu thụ điện năng trong môi trường nhà thông minh. Trước sự phát triển mạnh mẽ của thiết bị IoT và nhu cầu tiết kiệm năng lượng ngày càng cao, hệ thống cung cấp giải pháp giúp người dùng điều chỉnh thói quen sử dụng thiết bị một cách thông minh và hiệu quả, góp phần giảm chi phí sinh hoạt đồng thời bảo vệ môi trường.

## Mục tiêu

* **Tạo dữ liệu mô phỏng:**
  Do thiếu dữ liệu thực tế chứa đầy đủ các trường và mối tương quan đặc trưng, nhóm phát triển xây dựng bộ dữ liệu giả lập mô phỏng hành vi sử dụng thiết bị, đặc điểm môi trường và trạng thái tiêu thụ.
  *Xem chi tiết tại notebook* `Generate_Analyze_SelectModel.ipynb`.

* **Huấn luyện mô hình ban đầu:**

  * Sử dụng dữ liệu gốc từ file `data/data_2022.csv`.
  * Áp dụng thuật toán **LightGBM** để huấn luyện mô hình dự đoán công suất và tạo gợi ý tiêu thụ.

* **Cập nhật mô hình định kỳ:**

  * Tự động huấn luyện lại mô hình mỗi ngày dựa trên dữ liệu hai năm gần nhất nhằm duy trì độ chính xác và khả năng thích ứng.
  * Mô hình mới được nạp và áp dụng ngay vào pipeline xử lý dữ liệu thời gian thực.

* **Xử lý dữ liệu thời gian thực bằng Kafka:**

  * Mô phỏng 10 hộ gia đình gửi dữ liệu 15 phút/lần.
  * Hệ thống xử lý, phân tích và phản hồi gợi ý một cách tức thời.

* **Giao diện người dùng:**

  * Ứng dụng web xây dựng trên nền Flask cho phép người dùng theo dõi gợi ý, kiểm thử thủ công và xem báo cáo thống kê tiêu thụ điện năng.

---

## Công nghệ sử dụng

* **Ngôn ngữ lập trình:** Python
* **Giao diện Web:** Flask, HTML, JavaScript (SSE, Chart.js)
* **Xử lý dữ liệu:** pandas, numpy, matplotlib
* **Tiền xử lý dữ liệu:** LabelEncoder, OneHotEncoder, StandardScaler
* **Thuật toán học máy:** LightGBM, XGBoost, CatBoost, Linear Regression, Random Forest, Decision Tree
* **Đánh giá mô hình:** MSE, MAE, R² (sklearn.metrics)
* **Xử lý luồng dữ liệu:** Apache Kafka (thông qua kafka-python)

---

## Cấu hình hệ thống Kafka

![Kafka System Architecture](https://github.com/user-attachments/assets/90e1d3a4-0b00-4586-975d-015ad029acd7)

Hệ thống vận hành với **1 Kafka broker** và 4 topic, chia thành hai nhóm:

* **Dữ liệu thời gian thực (3 partitions/topic):**

  * `realtime-smarthome-data`: nhận dữ liệu giả lập từ các hộ gia đình.
  * `smarthome-suggestions`: lưu trữ các gợi ý tiêu thụ tương ứng.

* **Dữ liệu kiểm thử (1 partition/topic):**

  * `smarthome-test-data`: nhận bản ghi kiểm thử gửi từ giao diện người dùng.
  * `smarthome-test-suggestions`: chứa gợi ý phản hồi dựa trên bản ghi kiểm thử.

---

## Cấu trúc thư mục dự án

```plaintext
.
├── app_ui.py                        # Giao diện người dùng (UI)
├── catboost_info/                  # Log huấn luyện CatBoost
├── data/
│   ├── data_2022.csv               # Dữ liệu huấn luyện ban đầu
│   └── ...                         # Các file dữ liệu bổ sung
├── logic_gen_data.py               # Sinh dữ liệu giả lập cho 10 hộ gia đình
├── model_version1.py               # So sánh mô hình (không có feature lịch sử)
├── model_version2.py               # So sánh mô hình (có feature lịch sử tiêu thụ)
├── notification_suggest.py         # Consumer xử lý gợi ý gửi đến frontend
├── realtime_data_simulation.py     # Producer gửi dữ liệu giả lập vào Kafka
├── send_single_record_test_model.py # Gửi bản ghi kiểm thử từ terminal
├── suggesttion_model.py            # Huấn luyện mô hình + xử lý realtime
├── test_notification_suggest.py    # Kiểm thử gửi gợi ý
├── test_suggesttion_model.py       # Kiểm thử dự đoán từ 1 bản ghi test
├── templates/
│   └── index.html                  # Giao diện web
└── README.md                      # Tài liệu mô tả dự án
```

---

## Hướng dẫn sử dụng hệ thống

1. **Khởi động Kafka và Zookeeper**.

2. **Chạy các thành phần chính:**
   Khởi chạy lần lượt hoặc song song các module sau:

   ```bash
   python suggestion_model.py           # Huấn luyện định kỳ và xử lý realtime
   python notification_suggest.py       # Gửi gợi ý đến giao diện người dùng
   python realtime_data_simulation.py   # Gửi dữ liệu giả lập vào Kafka
   ```

   ![Minh họa chạy mô hình](https://github.com/user-attachments/assets/1cffc1fc-105c-4cc6-ba8b-27c793d9edb3)
   ![Minh họa gửi dữ liệu](https://github.com/user-attachments/assets/b3fda698-efbb-419a-904e-9b3627cc359a)
   ![Minh họa giao diện realtime](https://github.com/user-attachments/assets/1322ed78-3d4e-4cca-9549-c01d6cd8381f)

3. **Khởi chạy giao diện người dùng Flask:**

   ```bash
   python app_ui.py                    # Khởi động giao diện web
   ```

   ![Giao diện Flask 1](https://github.com/user-attachments/assets/e34917c3-658f-4527-992f-932246176c8a)
   ![Giao diện Flask 2](https://github.com/user-attachments/assets/6806ec03-e61c-4ea4-8bb2-cd802e32be84)

4. **(Tùy chọn) Gửi bản ghi kiểm thử từ terminal:**

   Để kiểm thử nhanh, gửi 1 bản ghi mẫu bằng lệnh:

   ```bash
   python send_single_record_test_model.py
   ```

---

## Kết luận

Dự án **Tối ưu hóa hành vi sử dụng thiết bị trong nhà thông minh với công nghệ dữ liệu lớn** đã phát triển thành công một hệ thống tích hợp các kỹ thuật phân tích dữ liệu lớn và học máy nhằm nâng cao hiệu quả tiêu thụ điện năng trong nhà thông minh.

Thông qua việc mô phỏng dữ liệu, huấn luyện và cập nhật mô hình định kỳ cùng xử lý thời gian thực với Kafka, hệ thống cung cấp các gợi ý thiết thực, kịp thời, đồng thời linh hoạt thích ứng với thay đổi thói quen sử dụng của người dùng. Giao diện thân thiện giúp người dùng dễ dàng theo dõi và kiểm soát mức tiêu thụ điện năng, góp phần thúc đẩy tiết kiệm năng lượng và bảo vệ môi trường.

Dự án mở ra nhiều cơ hội ứng dụng công nghệ dữ liệu lớn trong phát triển nhà thông minh, đặc biệt trong bối cảnh IoT và dữ liệu ngày càng phát triển đa dạng và phong phú.

---

## Nhóm phát triển

* **Hoàng Đình Hoàn** – 22024577
* **Lưu Quang Khải** – 22024521
* **Phùng Khôi Nguyên** – 22024503
* **Nguyễn Thị Ánh Tuyết** – 22024523

> Sinh viên Trường Đại học Công nghệ – Đại học Quốc gia Hà Nội
> Dự án thực hiện trong khuôn khổ học phần **Kỹ thuật và Công nghệ Dữ liệu Lớn**

---
