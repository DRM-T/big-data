# Tối ưu hóa hành vi sử dụng thiết bị trong nhà thông minh với công nghệ dữ liệu lớn

## Mô tả dự án

Dự án này tập trung vào việc xây dựng một hệ thống ứng dụng công nghệ dữ liệu lớn để tối ưu hóa việc sử dụng các thiết bị điện trong môi trường nhà thông minh. Trong bối cảnh công nghệ IoT phát triển mạnh mẽ và nhu cầu tiết kiệm năng lượng ngày càng tăng, hệ thống này giải quyết vấn đề lãng phí năng lượng do thói quen sử dụng hoặc thiếu kiểm soát, đồng thời giúp người dùng giảm chi phí sinh hoạt và góp phần bảo vệ môi trường.

**Mục tiêu chính:**

* **Thu thập dữ liệu:** Thu thập và lưu trữ dữ liệu từ các cảm biến và thiết bị trong nhà thông minh, bao gồm trạng thái, thời gian sử dụng, và mức tiêu thụ điện.
* **Phân tích dữ liệu:** Sử dụng các mô hình học máy (cụ thể là LightGBM) để phân tích, phát hiện các mô hình tiêu thụ bất thường hoặc không hiệu quả.
* **Đưa ra gợi ý:** Cung cấp các gợi ý, khuyến nghị cho người dùng về cách sử dụng thiết bị hiệu quả hơn, đề xuất lịch hoạt động tối ưu nhằm tiết kiệm điện và chi phí.
* **Xử lý thời gian thực:** Tận dụng Apache Kafka để xử lý và phân tích dữ liệu theo thời gian thực, đảm bảo các gợi ý được đưa ra kịp thời.
* **Giao diện người dùng:** Cung cấp một giao diện web (sử dụng Flask) để người dùng có thể theo dõi gợi ý, xem thống kê chi phí, và nhập dữ liệu thủ công để kiểm tra hệ thống.

## Cách cài đặt

Để cài đặt và chạy dự án này, bạn cần thực hiện các bước sau:

### Yêu cầu tiên quyết

1.  **Python 3.x:** Đảm bảo bạn đã cài đặt Python phiên bản 3 trở lên.
2.  **Apache Kafka:**
    * Tải và cài đặt Apache Kafka từ [trang chủ Kafka](https://kafka.apache.org/downloads).
    * Khởi chạy Zookeeper và Kafka Server theo hướng dẫn. Đảm bảo Kafka đang chạy trên `localhost:9092` (hoặc cấu hình lại trong các file Python nếu bạn sử dụng địa chỉ khác).
    * Hệ thống sẽ sử dụng các topic sau (thường sẽ được tự động tạo nếu chưa có, nhưng bạn nên kiểm tra):
        * `smarthome-suggestions`
        * `smarthome-test-suggestions`
        * `realtime-smarthome-data`
        * `smarthome-test-data`

### Cài đặt thư viện Python

1.  **Tạo môi trường ảo (khuyến nghị):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Trên Linux/macOS
    # hoặc
    venv\Scripts\activate  # Trên Windows
    ```
2.  **Cài đặt các thư viện cần thiết:**
    Tạo một file `requirements.txt` với nội dung sau:
    ```
    flask
    kafka-python
    pandas
    numpy
    lightgbm
    scikit-learn
    matplotlib
    ```
    Sau đó chạy lệnh:
    ```bash
    pip install -r requirements.txt
    ```

### Chạy dự án

Bạn cần chạy các thành phần sau theo thứ tự, mỗi thành phần trong một cửa sổ terminal riêng:

1.  **Chạy Zookeeper & Kafka Server.**
2.  **Chạy mô hình xử lý gợi ý thời gian thực:**
    ```bash
    python suggesttion_model.py
    ```
3.  **Chạy mô hình xử lý gợi ý kiểm tra:**
    ```bash
    python test_suggesttion_model.py
    ```
4.  **Chạy bộ sinh dữ liệu thời gian thực (tùy chọn):** Nếu bạn muốn có luồng dữ liệu liên tục.
    ```bash
    python realtime_data_simulation.py
    ```
5.  **Chạy ứng dụng Web UI:**
    ```bash
    python app_ui.py
    ```

Sau khi chạy `app_ui.py`, ứng dụng web sẽ có sẵn tại `http://127.0.0.1:5000/`.

## Cách sử dụng

Sau khi khởi chạy thành công các thành phần, bạn có thể truy cập giao diện web tại `http://127.0.0.1:5000/`:

1.  **Xem gợi ý:**
    * Mục **Gợi ý Thời gian thực** sẽ tự động cập nhật các gợi ý được tạo ra từ luồng dữ liệu `realtime-smarthome-data` (nếu `realtime_data_simulation.py` đang chạy).
    * Mục **Gợi ý Kiểm tra** sẽ hiển thị các gợi ý được tạo ra khi bạn gửi dữ liệu thủ công tới topic `smarthome-test-data`.
2.  **Nhập dữ liệu thủ công:**
    * Sử dụng form **Nhập Dữ Liệu Thủ Công** để gửi một bản ghi dữ liệu mô phỏng.
    * Bạn có thể chọn gửi tới topic `realtime` hoặc `test`(lưu ý nên chọn test vì realtime đang cập nhật xử lý từ luồng dữ liệu mô phỏng, lựa chọn realtime sẽ khó nhận ra đâu là câu gợi ý hệ thống đưa ra cho bản ghi mô phỏng tương ứng của mình).
    * Điền các thông tin về thiết bị, trạng thái, môi trường,...
    * Nhấn **Gửi Dữ Liệu**. Nếu bạn gửi tới topic `test`, kết quả gợi ý sẽ xuất hiện ở mục **Gợi ý Kiểm tra**.
3.  **Xem thống kê:**
    * Sử dụng mục **Thống Kê Chi Phí Năng Lượng**.
    * Chọn nhà (Home ID), khoảng thời gian và chu kỳ (ngày/tuần/tháng).
    * Nhấn **Xem Thống Kê** để xem biểu đồ chi phí năng lượng.

## Cấu trúc thư mục/mã nguồn

* `app_ui.py`: Chứa mã nguồn Flask cho giao diện người dùng, xử lý các yêu cầu HTTP, cung cấp Server-Sent Events (SSE) để hiển thị gợi ý thời gian thực và xử lý việc gửi dữ liệu thủ công.
* `logic_gen_data.py`: Định nghĩa logic để sinh dữ liệu giả lập cho nhà thông minh, bao gồm hành vi người dùng, môi trường, trạng thái thiết bị.
* `realtime_data_simulation.py`: Một Kafka Producer, sử dụng `logic_gen_data.py` để sinh dữ liệu và gửi liên tục đến topic `realtime-smarthome-data`.
* `suggesttion_model.py`: Một Kafka Consumer/Producer. Nhận dữ liệu từ `realtime-smarthome-data`, sử dụng mô hình LightGBM để dự đoán công suất, tạo gợi ý và gửi đến topic `smarthome-suggestions`. Đồng thời, lưu dữ liệu đã xử lý vào file CSV và có khả năng huấn luyện lại mô hình.
* `test_suggesttion_model.py`: Tương tự `suggesttion_model.py` nhưng hoạt động với các topic `smarthome-test-data` và `smarthome-test-suggestions`, dùng để xử lý dữ liệu được gửi từ form thủ công.
* `Báo cáo dự án.txt`: File báo cáo chi tiết về dự án (định dạng LaTeX).
* `data/`: Thư mục chứa các file dữ liệu lịch sử (`.csv`) được lưu trữ theo năm.
* `templates/index.html`: File HTML (được `app_ui.py` tạo ra) cho giao diện người dùng.

## Công nghệ sử dụng

* **Ngôn ngữ lập trình:** Python
* **Nền tảng xử lý dữ liệu:** Apache Kafka
* **Web Framework:** Flask
* **Thư viện học máy:** LightGBM, Scikit-learn
* **Thư viện xử lý dữ liệu:** Pandas, Numpy
* **Thư viện Kafka Python:** `kafka-python`
* **Giao diện người dùng:** HTML, CSS, JavaScript (với Server-Sent Events và Chart.js)

## Tác giả / Nhóm phát triển

* Hoàng Đình Hoàn (22024577)
* Lưu Quang Khải (22024521)
* Phùng Khôi Nguyên (22024503)
* Nguyễn Thị Ánh Tuyết (22024523)

Nhóm sinh viên Trường Đại học Công nghệ – Đại học Quốc gia Hà Nội, thực hiện đề tài trong khuôn khổ học phần Kỹ thuật và công nghệ dữ liệu lớn.

## Giấy phép

Dự án này không có giấy phép được chỉ định.