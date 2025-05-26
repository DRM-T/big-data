import re
from flask import Flask, render_template, Response, request, redirect, url_for, jsonify # Import jsonify
from kafka import KafkaConsumer, KafkaProducer
import json
import time
from datetime import datetime
import threading # Import threading

# Initialize Flask app
app = Flask(__name__)

# Kafka Configuration
KAFKA_BROKERS = 'localhost:9092'
KAFKA_SUGGESTION_TOPIC_REALTIME = 'smarthome-suggestions' # Real-time suggestion topic
KAFKA_SUGGESTION_TOPIC_TEST = 'smarthome-test-suggestions' # Test suggestion topic
KAFKA_DATA_TOPIC_REALTIME = 'realtime-smarthome-data' # Real-time data topic
KAFKA_DATA_TOPIC_TEST = 'smarthome-test-data' # Test data topic


# --- Kafka Consumer for real-time suggestion stream ---
def create_kafka_consumer_realtime():
    # Loop to attempt reconnection
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_SUGGESTION_TOPIC_REALTIME,
                bootstrap_servers=KAFKA_BROKERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='recommendation-flask-ui-group-main',
                auto_offset_reset='latest', # Start consuming from the latest messages
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )
            print(f"[Flask UI] Kafka Consumer for '{KAFKA_SUGGESTION_TOPIC_REALTIME}' connected.")
            return consumer
        except Exception as e:
            print(f"[Flask UI] Kafka Consumer for '{KAFKA_SUGGESTION_TOPIC_REALTIME}' connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# --- Kafka Consumer for test suggestion stream ---
def create_kafka_consumer_test():
    # Loop to attempt reconnection
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_SUGGESTION_TOPIC_TEST, # Test topic
                bootstrap_servers=KAFKA_BROKERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='recommendation-flask-ui-group-test', # New group_id for test consumer
                auto_offset_reset='latest', # Start consuming from the latest messages
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )
            print(f"[Flask UI] Kafka Consumer for '{KAFKA_SUGGESTION_TOPIC_TEST}' connected.")
            return consumer
        except Exception as e:
            print(f"[Flask UI] Kafka Consumer for '{KAFKA_SUGGESTION_TOPIC_TEST}' connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)


# --- Kafka Producer for sending manual data ---
def create_kafka_producer():
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("[Flask UI] Kafka Producer for data input connected.")
        return producer
    except Exception as e:
        print(f"[Flask UI] Kafka Producer connection failed: {e}.")
        return None

kafka_data_producer = create_kafka_producer()

# --- Routes ---
@app.route('/')
def index():
    # List of available devices for the manual input form. Added more test devices.
    available_devices = [
        {'device_id': 'AC_01', 'device_type': 'air_conditioner', 'room': 'bedroom'},
        {'device_id': 'LIGHT_01', 'device_type': 'light', 'room': 'living_room'},
        {'device_id': 'TV_01', 'device_type': 'tv', 'room': 'living_room'},
        {'device_id': 'FRIDGE_01', 'device_type': 'fridge', 'room': 'kitchen'},
        {'device_id': 'WASHER_01', 'device_type': 'washer', 'room': 'laundry_room'},
        # Add test device options matching existing types for easier selection logic
        {'device_id': 'TEST_AC_0199', 'device_type': 'air_conditioner', 'room': 'test_room'},
        {'device_id': 'TEST_LIGHT_0199', 'device_type': 'light', 'room': 'test_room'},
        {'device_id': 'TEST_TV_0199', 'device_type': 'tv', 'room': 'test_room'},
        {'device_id': 'TEST_FRIDGE_0199', 'device_type': 'fridge', 'room': 'test_room'},
        {'device_id': 'TEST_WASHER_0199', 'device_type': 'washer', 'room': 'test_room'}

    ]
    # List of available activities for the manual input form
    available_activities = ['sleeping', 'cooking', 'idle', 'away', 'watching_tv', 'testing'] # Add test activity
    # Render the index.html template, passing device and activity data
    return render_template('index.html', devices=available_devices, activities=available_activities)

# SSE endpoint for real-time suggestions
@app.route('/stream-suggestions')
def stream_suggestions():
    # Create a consumer for the real-time topic
    consumer = create_kafka_consumer_realtime()
    def generate():
        # If consumer connection failed, send an error message
        if not consumer:
            current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            # Keep the {"timestamp": ..., "suggestion": ...} format matching user's working JS
            error_message = {"timestamp": current_time_str, "suggestion": "Lỗi: Không thể kết nối đến Kafka để nhận gợi ý thực tế."}
            yield f"data: {json.dumps(error_message)}\n\n"
            return
        print("[Flask UI] Client connected to SSE stream for real-time suggestions.")
        try:
            # Use poll with timeout in SSE generator to avoid blocking indefinitely
            while True:
                # Poll for messages with a short timeout
                messages = consumer.poll(timeout_ms=500, max_records=10)

                if messages:
                    for tp, records in messages.items():
                        for message in records:
                            suggestion_data = message.value # Expected format from model: {"suggestion": "[timestamp] text\n..."}
                            # Check if the message is a dictionary and contains the 'suggestion' key
                            if isinstance(suggestion_data, dict) and "suggestion" in suggestion_data:
                                full_suggestion = suggestion_data["suggestion"] # This is the multi-line string with prefixes

                                # Attempt to parse timestamp and text using regex (like in user's working code)
                                match = re.match(r"\[(.*?)\] (.*)", full_suggestion)
                                if match:
                                    timestamp_str = match.group(1)
                                    # Send {"timestamp": "...", "suggestion": "..."} matching user's working JS
                                    # Note: We still send the full suggestion text, but use the parsed timestamp
                                    formatted_data = {"timestamp": timestamp_str, "suggestion": full_suggestion}
                                    yield f"data: {json.dumps(formatted_data)}\n\n"
                                else:
                                     # If regex fails, use current time and send full suggestion
                                    print(f"[Flask UI] Could not parse suggestion format from realtime: {full_suggestion}")
                                    current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
                                    # Send {"timestamp": ..., "suggestion": ...} matching user's working JS
                                    yield f"data: {json.dumps({'timestamp': current_time_str, 'suggestion': full_suggestion})}\n\n"

                            else:
                                # Handle malformed messages
                                print(f"[Flask UI] Received malformed realtime suggestion message: {suggestion_data}")
                                current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
                                # Send {"timestamp": ..., "suggestion": ...} with a default message
                                yield f"data: {json.dumps({'timestamp': current_time_str, 'suggestion': 'Received unexpected message format from Kafka (realtime).'})}\n\n"
                else:
                    # If no messages, send a keep-alive comment to prevent connection timeout
                    yield ": keepalive\n\n"

                time.sleep(0.1) # Small sleep to prevent tight loop when idle

        except Exception as e:
            # Handle exceptions during message consumption
            print(f"[Flask UI] Error in SSE stream for real-time suggestions: {e}")
            current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            # Send error message in the expected format
            error_message = {"timestamp": current_time_str, "suggestion": f"Lỗi khi nhận gợi ý thực tế: {e}"}
            yield f"data: {json.dumps(error_message)}\n\n"
        finally:
            # Close the consumer when the client disconnects
            print("[Flask UI] Client disconnected from SSE stream for real-time suggestions.")
            if consumer:
                consumer.close()

    # Return the generator function as an SSE response
    return Response(generate(), mimetype='text/event-stream')

# SSE endpoint for test suggestions
@app.route('/stream-test-suggestions')
def stream_test_suggestions():
    # Create a consumer for the test topic
    consumer = create_kafka_consumer_test() # Use the new test consumer
    def generate():
        # If consumer connection failed, send an error message
        if not consumer:
            current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
             # Keep the {"timestamp": ..., "suggestion": ...} format matching user's working JS
            error_message = {"timestamp": current_time_str, "suggestion": "Lỗi: Không thể kết nối đến Kafka để nhận gợi ý kiểm tra."}
            yield f"data: {json.dumps(error_message)}\n\n"
            return
        print("[Flask UI] Client connected to SSE stream for test suggestions.")
        try:
            # Use poll with timeout in SSE generator to avoid blocking indefinitely
            while True:
                # Poll for messages with a short timeout
                messages = consumer.poll(timeout_ms=500, max_records=10)

                if messages:
                    for tp, records in messages.items():
                        for message in records:
                            suggestion_data = message.value # Expected format from test script: {"suggestion": "[timestamp] text\n..."}
                            # Check if the message is a dictionary and contains the 'suggestion' key
                            if isinstance(suggestion_data, dict) and "suggestion" in suggestion_data:
                                full_suggestion = suggestion_data["suggestion"] # This is the multi-line string with prefixes

                                # Attempt to parse timestamp and text using regex (like in user's working code)
                                match = re.match(r"\[(.*?)\] (.*)", full_suggestion)
                                if match:
                                    timestamp_str = match.group(1)
                                     # Send {"timestamp": "...", "suggestion": "..."} matching user's working JS
                                     # Note: We still send the full suggestion text, but use the parsed timestamp
                                    formatted_data = {"timestamp": timestamp_str, "suggestion": full_suggestion}
                                    yield f"data: {json.dumps(formatted_data)}\n\n"
                                else:
                                    # If regex fails, use current time and send full suggestion
                                    print(f"[Flask UI] Could not parse suggestion format from test: {full_suggestion}")
                                    current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
                                    # Send {"timestamp": ..., "suggestion": ...} matching user's working JS
                                    yield f"data: {json.dumps({'timestamp': current_time_str, 'suggestion': full_suggestion})}\n\n"

                            else:
                                # Handle malformed messages
                                print(f"[Flask UI] Received malformed test suggestion message: {suggestion_data}")
                                current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
                                # Send {"timestamp": ..., "suggestion": ...} with a default message
                                yield f"data: {json.dumps({'timestamp': current_time_str, 'suggestion': 'Received unexpected message format from Kafka (test).'})}\n\n"
                else:
                    # If no messages, send a keep-alive comment
                    yield ": keepalive\n\n"

                time.sleep(0.1) # Small sleep

        except Exception as e:
            # Handle exceptions during message consumption
            print(f"[Flask UI] Error in SSE stream for test suggestions: {e}")
            current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
             # Send error message in the expected format
            error_message = {"timestamp": current_time_str, "suggestion": f"Lỗi khi nhận gợi ý kiểm tra: {e}"}
            yield f"data: {json.dumps(error_message)}\n\n"
        finally:
            # Close the consumer when the client disconnects
            print("[Flask UI] Client disconnected from SSE stream for test suggestions.")
            if consumer:
                consumer.close()

    # Return the generator function as an SSE response
    return Response(generate(), mimetype='text/event-stream')
#route xử lý thống kê
@app.route('/api/cost_data')
def cost_data():
    import pandas as pd
    from datetime import datetime

    home_id = int(request.args.get('home_id'))
    start_date = pd.to_datetime(request.args.get('start_date'))
    end_date = pd.to_datetime(request.args.get('end_date'))
    period = request.args.get('period', 'daily')

    # Đọc toàn bộ dữ liệu các năm liên quan
    data_frames = []
    for year in range(start_date.year, end_date.year + 1):
        file_path = f"data/data_{year}.csv"
        try:
            df = pd.read_csv(file_path, parse_dates=['timestamp'])
            data_frames.append(df)
        except FileNotFoundError:
            continue

    if not data_frames:
        return jsonify([])

    df = pd.concat(data_frames, ignore_index=True)

    # Lọc theo home_id và thời gian
    df = df[(df['home_id'] == home_id) & 
            (df['timestamp'] >= start_date) & 
            (df['timestamp'] <= end_date) & 
            (df['status'] == 'on')]

    if df.empty:
        return jsonify([])

    # Tính chi phí = (power_watt / 1000) * (duration_hours) * price_kWh
    # Giả sử mỗi bản ghi đại diện cho 15 phút
    df['duration_hours'] = 15 / 60.0
    df['cost'] = (df['power_watt'] / 1000) * df['duration_hours'] * df['price_kWh']

    df.set_index('timestamp', inplace=True)
    if period == 'daily':
        df_resampled = df['cost'].resample('D').sum()
    elif period == 'weekly':
        df_resampled = df['cost'].resample('W-MON').sum()
    elif period == 'monthly':
        df_resampled = df['cost'].resample('MS').sum()
    else:
        return jsonify([])

    results = [{"date": d.strftime('%Y-%m-%d'), "cost": round(c, 2)} for d, c in df_resampled.items()]
    return jsonify(results)


# Route to handle manual data submission
@app.route('/send-manual-data', methods=['POST'])
def send_manual_data():
    # Check if Kafka Producer is available
    if not kafka_data_producer:
        print("[Flask UI] Kafka Producer is not available. Cannot send data.")
        # Return JSON error response
        return jsonify({"status": "error", "message": "Lỗi: Không kết nối được Producer."}), 500

    try:
        # Get timestamp from form, default to current time if not provided
        timestamp_str = request.form.get('timestamp', datetime.now().isoformat())
        try:
            # Parse timestamp string, handling potential space instead of 'T'
            dt_object = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
        except ValueError:
            # Handle invalid timestamp format
            print(f"[Flask UI] Invalid timestamp format: {timestamp_str}. Using current time.")
            dt_object = datetime.now()

        # Get device info string and split it
        device_info_str = request.form.get('device_id_select')
        if not device_info_str or len(device_info_str.split('|')) != 3:
            print(f"[Flask UI] Invalid device_info_str: {device_info_str}")
            # Return JSON error response
            return jsonify({"status": "error", "message": "Lỗi: Thông tin thiết bị không hợp lệ."}), 400

        device_id, device_type, room = device_info_str.split('|')

        # Get home_id from form, default to 1
        home_id = int(request.form.get('home_id_manual', 1))

        # Determine which topic to send to based on a form field
        target_topic = request.form.get('target_topic', 'realtime') # Default to 'realtime'
        if target_topic == 'test':
            kafka_topic_to_send = KAFKA_DATA_TOPIC_TEST
            # Optional warning if sending to test topic with a non-test home_id
            if home_id != 99:
                print(f"[Flask UI] Warning: Sending to test topic but home_id is {home_id}. For clarity, consider using home_id 99 for test data.")
            # Note: We rely on the user selecting the correct test device from the dropdown,
            # not automatically overriding device_id/room here.
        else: # target_topic == 'realtime'
            kafka_topic_to_send = KAFKA_DATA_TOPIC_REALTIME
            # Optional warning if sending to realtime topic with the test home_id
            if home_id == 99:
                print(f"[Flask UI] Warning: Sending to realtime topic but home_id is 99. For clarity, consider using a different home_id.")


        # Construct the data record dictionary
        record = {
            'home_id': home_id, # Use the home_id from the form
            'timestamp': dt_object.isoformat(),
            'device_id': device_id, # Use the selected device_id
            'device_type': device_type,
            'room': room, # Use the selected room
            'status': request.form.get('status', 'off'),
            'power_watt': float(request.form.get('power_watt', 0)),
            'user_present': int(request.form.get('user_present', 0)),
            'activity': request.form.get('activity', 'idle'),
            'indoor_temp': float(request.form.get('indoor_temp', 25.0)),
            'outdoor_temp': float(request.form.get('outdoor_temp', 28.0)),
            'humidity': float(request.form.get('humidity', 60.0)),
            'light_level': float(request.form.get('light_level', 300.0)),
            'day_of_week': dt_object.weekday(),
            'hour_of_day': dt_object.hour,
            'price_kWh': int(request.form.get('price_kWh', 2700))
        }

        # Send the record to the selected Kafka topic
        print(f"[Flask UI] Sending manual data to Kafka topic '{kafka_topic_to_send}': {record}")
        kafka_data_producer.send(kafka_topic_to_send, value=record)
        kafka_data_producer.flush() # Ensure the message is sent immediately

    except Exception as e:
        # Handle any errors during processing or sending
        print(f"[Flask UI] Error processing or sending manual data: {e}")
        # Return JSON error response
        return jsonify({"status": "error", "message": f"Lỗi khi xử lý hoặc gửi dữ liệu: {e}"}), 500

    # Return JSON success response instead of redirecting
    return jsonify({"status": "success", "message": "Dữ liệu đã được gửi thành công!"})


# Main execution block
if __name__ == '__main__':
    import os
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # Define the HTML content for index.html
    # --- BEGIN HTML CONTENT ---
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gợi ý Nhà Thông Minh & Nhập liệu</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; color: #333; display: flex; flex-direction: column; min-height: 100vh; }
            header { background-color: #0056b3; color: white; padding: 1rem; text-align: center; }
            .container {
                display: flex;
                flex: 1;
                margin: 10px;
                gap: 10px;
                flex-wrap: wrap; /* Allow wrapping sections on small screens */
            }
            .section { /* Applied to both input and suggestions sections */
                background-color: #fff;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 10px; /* Add some space below sections when stacked */
                display: flex;
                flex-direction: column; /* Stack content within each section */
            }

            .input-section {
                 width: 100%; /* Default to full width on small screens */
                 max-width: 580px; /* Limit max width for input on large screens */
                 margin: 0 auto 10px auto; /* Center and add bottom margin when stacked */
            }

            .suggestions-section {
                flex: 1; /* Allow suggestions section to take up remaining width */
                min-width: 300px; /* Ensure suggestions section doesn't get too small */
                max-height: 90vh; /* Keep max height for overflow scrolling */
                display: flex; /* Make suggestions-section a flex container */
                flex-direction: row; /* Arrange suggestion columns side-by-side */
                gap: 20px; /* Add space between the two suggestion columns */
                flex-wrap: wrap; /* Allow columns to wrap if screen is too narrow */
            }

            .suggestions-column {
                display: flex;
                flex-direction: column;
                flex: 1; /* Allow each column to grow and share width */
                min-width: 280px; /* Minimum width for each suggestion column */
            }

            @media (min-width: 768px) {
                .container { flex-direction: row; } /* Container lays out sections in a row */
                .input-section { width: 40%; margin-bottom: 0; } /* Set width and remove bottom margin */
                .suggestions-section { width: 60%; margin-bottom: 0; } /* Set width and remove bottom margin */
            }


            h1, h2 { color: #0056b3; }
            h1 { text-align: center; }
            h2 { margin-top: 0; }
            .suggestion-list {
                list-style-type: none;
                padding: 0;
                overflow-y: auto; /* Add scrollbar for vertical overflow */
                flex-grow: 1;
                border: 1px solid #eee;
                padding: 10px;
                border-radius: 4px;
                max-height: 400px; /* Set a max height for scrolling */
            }
            .suggestion-list li { background-color: #f9f9f9; margin-bottom: 8px; padding: 12px; border-radius: 4px; border-left: 4px solid #007bff; font-size: 0.95em; word-break: break-word; } /* Add word break */
            .suggestion-list li:nth-child(odd) { border-left-color: #28a745; }
            .suggestion-list li.test-suggestion { border-left-color: #ffc107; } /* Highlight test suggestions */

            .timestamp { font-size: 0.85em; color: #555; display: block; margin-bottom: 4px; }
            form label { display: block; margin-top: 10px; margin-bottom: 5px; font-weight: bold; }
            form input[type="text"], form input[type="number"], form input[type="datetime-local"], form select {
                width: calc(100% - 22px); padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;
            }
            form button {
                background-color: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; margin-top: 10px;
            }
            form button:hover { background-color: #0056b3; }
            .form-row { display: flex; gap: 10px; flex-wrap: wrap; } /* Allow wrapping form rows */
            .form-row > div { flex: 1; min-width: 180px;} /* Ensure input fields have min width */


        </style>
    </head>
    <body>
        <header><h1>Dashboard Nhà Thông Minh</h1></header>
        <div class="container">
            <div class="section input-section">
                <h2>Nhập Dữ Liệu Thủ Công</h2>
                <form action="/send-manual-data" method="POST" id="manualDataForm">
                    <div class="form-row">
                        <div>
                            <label for="target_topic">Gửi tới Topic:</label>
                            <select id="target_topic" name="target_topic" required>
                                <option value="realtime">realtime-smarthome-data</option>
                                <option value="test">smarthome-test-data</option>
                            </select>
                        </div>
                        <div>
                            <label for="home_id_manual">Home ID:</label>
                            <input type="number" id="home_id_manual" name="home_id_manual" value="1" required min="1">
                        </div>
                    </div>
                    <div class="form-row">
                        <div>
                            <label for="timestamp">Timestamp:</label>
                            <input type="datetime-local" id="timestamp" name="timestamp" required>
                        </div>
                        <div>
                            <label for="device_id_select">Thiết bị (ID | Loại | Phòng):</label>
                            <select id="device_id_select" name="device_id_select" required>
                                {% for device in devices %}
                                    <option value="{{ device.device_id }}|{{ device.device_type }}|{{ device.room }}">
                                        {{ device.device_id }} ({{ device.device_type }} - {{ device.room }})
                                    </option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>

                    <div class="form-row">
                        <div>
                            <label for="status">Trạng thái (status):</label>
                            <select id="status" name="status">
                                <option value="on">On</option>
                                <option value="off" selected>Off</option>
                            </select>
                        </div>
                        <div>
                            <label for="power_watt">Công suất (Power Watt):</label>
                            <input type="number" id="power_watt" name="power_watt" value="0" step="0.1" required>
                        </div>
                    </div>

                    <div class="form-row">
                        <div>
                            <label for="user_present">Người dùng có mặt (0 hoặc 1):</label>
                            <select id="user_present" name="user_present">
                                <option value="1">Có</option>
                                <option value="0" selected>Không</option>
                            </select>
                        </div>
                        <div>
                            <label for="activity">Hoạt động (activity):</label>
                            <select id="activity" name="activity">
                                {% for act in activities %}
                                    <option value="{{ act }}">{{ act }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>

                    <div class="form-row">
                        <div>
                            <label for="indoor_temp">Nhiệt độ trong nhà (°C):</label>
                            <input type="number" id="indoor_temp" name="indoor_temp" value="25" step="0.1">
                        </div>
                        <div>
                            <label for="outdoor_temp">Nhiệt độ ngoài trời (°C):</label>
                            <input type="number" id="outdoor_temp" name="outdoor_temp" value="28" step="0.1">
                        </div>
                    </div>

                    <div class="form-row">
                        <div>
                            <label for="humidity">Độ ẩm (%):</label>
                            <input type="number" id="humidity" name="humidity" value="60" step="0.1">
                        </div>
                        <div>
                            <label for="light_level">Mức sáng (lux):</label>
                            <input type="number" id="light_level" name="light_level" value="300" step="1">
                        </div>
                    </div>

                    <div>
                        <label for="price_kWh">Giá điện (VND/kWh):</label>
                        <input type="number" id="price_kWh" name="price_kWh" value="2700" step="100">
                    </div>

                    <button type="submit">Gửi Dữ Liệu</button>
                </form>
                <p id="form-status" style="margin-top: 15px;"></p> </div>

            <div class="section suggestions-section">
                <div class="suggestions-column">
                    <h2>Gợi ý Thời gian thực</h2>
                    <ul id="suggestions-realtime" class="suggestion-list">
                        <li>Đang chờ gợi ý mới từ luồng thực tế...</li>
                    </ul>
                </div>
                <div class="suggestions-column">
                    <h2>Gợi ý Kiểm tra</h2>
                    <ul id="suggestions-test" class="suggestion-list">
                        <li>Đang chờ gợi ý mới từ luồng kiểm tra...</li>
                    </ul>
                </div>
            </div>
        </div>
        <div class="section statistics-section">
            <h2>Thống Kê Chi Phí Năng Lượng</h2>
            <form id="statisticsForm">
                <div class="form-row">
                    <div>
                        <label for="stats_home_id">Chọn Nhà:</label>
                        <input type="number" id="stats_home_id" name="home_id" min="1" value="1" required>
                    </div>
                    <div>
                        <label for="stats_period">Tổng hợp theo:</label>
                        <select id="stats_period" name="period" required>
                            <option value="daily">Ngày</option>
                            <option value="weekly">Tuần</option>
                            <option value="monthly">Tháng</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div>
                        <label for="stats_start_date">Ngày Bắt Đầu:</label>
                        <input type="date" id="stats_start_date" name="start_date" required>
                    </div>
                    <div>
                        <label for="stats_end_date">Ngày Kết Thúc:</label>
                        <input type="date" id="stats_end_date" name="end_date" required>
                    </div>
                </div>
                <button type="submit">Xem Thống Kê</button>
            </form>
            <div id="costChartContainer" style="margin-top: 20px; height: 300px;">
                <canvas id="costChart"></canvas>
                <p id="noStatsDataMessage" style="text-align: center; color: #555; display: none;">Không có dữ liệu chi phí để hiển thị biểu đồ.</p>
            </div>
        </div>

        <script>
            // Script for SSE suggestions
            const suggestionsListRealtime = document.getElementById('suggestions-realtime');
            const suggestionsListTest = document.getElementById('suggestions-test');
            const formStatus = document.getElementById('form-status'); // Get the status paragraph

            // Function to connect to an SSE endpoint
            function connectSSE(endpoint, suggestionsListElement, isTest = false) {
                console.log(`Connecting to SSE stream for ${isTest ? 'test' : 'realtime'} suggestions at ${endpoint}...`);
                const eventSource = new EventSource(endpoint);
                let initialMessageCleared = false; // Flag to clear the initial placeholder message

                // Event handler for when the connection is opened
                eventSource.onopen = function() {
                    console.log(`SSE Connection opened for ${isTest ? 'test' : 'realtime'} suggestions.`);
                     // Clear initial message only if it's the default placeholder
                    if (!initialMessageCleared) {
                         // Check if the list contains only the placeholder text
                         if (suggestionsListElement.children.length === 1 && suggestionsListElement.children[0].innerText.includes('Đang chờ gợi ý mới')) {
                             suggestionsListElement.innerHTML = ''; // Clear the list
                         }
                    }
                };

                // Event handler for receiving messages
                eventSource.onmessage = function(event) {
                    // Clear initial message if it hasn't been already on receiving the first actual message
                    if (!initialMessageCleared) {
                        if (suggestionsListElement.children.length === 1 && suggestionsListElement.children[0].innerText.includes('Đang chờ gợi ý mới')) {
                            suggestionsListElement.innerHTML = '';
                        }
                        initialMessageCleared = true; // Mark as cleared after the first message is processed
                    }

                    try {
                        const data = JSON.parse(event.data);
                        const listItem = document.createElement('li');
                        // Expecting data to have 'timestamp' and 'suggestion' keys as per user's working code
                        const formattedTimestamp = data.timestamp;
                        const suggestionText = data.suggestion; // This might contain newlines

                        // Display the timestamp and the full suggestion text in one list item
                        listItem.innerHTML = `<span class="timestamp">${formattedTimestamp}</span>${suggestionText}`;

                        // Add a class for test suggestions for styling
                        if (isTest) {
                            listItem.classList.add('test-suggestion');
                        }

                        // Insert the new item at the beginning of the list
                        suggestionsListElement.insertBefore(listItem, suggestionsListElement.firstChild);

                        // Limit the total number of suggestions displayed in the list
                        const maxSuggestions = 50; // Increased limit slightly from user's original 30
                        while (suggestionsListElement.children.length > maxSuggestions) {
                            suggestionsListElement.removeChild(suggestionsListElement.lastChild);
                        }
                        console.log(`Received ${isTest ? 'test' : 'realtime'} suggestion`);

                    } catch (e) {
                        // Handle errors during JSON parsing or message processing
                        console.error(`Error processing SSE message for ${isTest ? 'test' : 'realtime'} suggestions:`, e, event.data);
                        const listItem = document.createElement('li');
                        listItem.style.color = 'red';
                         // Display the raw event data if parsing fails
                        listItem.innerHTML = `<span class="timestamp">${new Date().toISOString().slice(0, 19).replace('T', ' ')}</span>Lỗi hiển thị gợi ý: ${event.data}`;
                        suggestionsListElement.insertBefore(listItem, suggestionsListElement.firstChild);
                    }
                };

                // Event handler for SSE errors
                eventSource.onerror = function(err) {
                    console.error(`EventSource for ${isTest ? 'test' : 'realtime'} suggestions failed:`, err);
                    eventSource.close();
                    // Attempt to reconnect after a delay
                    setTimeout(() => connectSSE(endpoint, suggestionsListElement, isTest), 5000);
                };
            }

            // Connect to both SSE streams when the script loads
            connectSSE("/stream-suggestions", suggestionsListRealtime, false);
            connectSSE("/stream-test-suggestions", suggestionsListTest, true); // Corrected variable name


            // Automatically fill the current timestamp in the form
            document.addEventListener('DOMContentLoaded', (event) => {
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset()); // Adjust for local timezone
                now.setSeconds(0); // Remove seconds and milliseconds for cleaner display
                now.setMilliseconds(0);
                document.getElementById('timestamp').value = now.toISOString().slice(0,16);

                // Optional: Update device_id and room based on home_id and target_topic selection
                const homeIdInput = document.getElementById('home_id_manual');
                const targetTopicSelect = document.getElementById('target_topic');
                const deviceIdSelect = document.getElementById('device_id_select');
                 // Get the form element
                const manualDataForm = document.getElementById('manualDataForm');


                // Make availableDevices accessible (e.g., by adding a script tag with the data or storing in a global var)
                // For simplicity, let's directly use the value from Flask render for initial setup
                // FIX: Pass devices data from Flask to JS safely
                const availableDevices = JSON.parse('{{ devices | tojson | safe }}');

                // Function to update device info based on selected home ID and topic
                function updateDeviceInfo() {
                    const selectedHomeId = parseInt(homeIdInput.value, 10);
                    const selectedTopic = targetTopicSelect.value;
                    const selectedDeviceValue = deviceIdSelect.value;
                    const selectedDeviceIdParts = selectedDeviceValue.split('|');
                    const currentDeviceType = selectedDeviceIdParts.length > 1 ? selectedDeviceIdParts[1] : '';

                    // Find a matching device type in the available list
                    let matchedDeviceTemplate = availableDevices.find(d => d.device_type === currentDeviceType);

                    if (!matchedDeviceTemplate) {
                         console.warn(`Could not find a template device for type: ${currentDeviceType}. Keeping current selection.`);
                         return; // Cannot update if device type is unknown
                    }

                    let newDeviceValue;

                    if (selectedTopic === 'test') {
                        // For test topic, find a test device with the same type
                        // Find the first test device with the matching type
                        const testDeviceOption = availableDevices.find(d =>
                            d.device_type === currentDeviceType && d.device_id.startsWith('TEST_')
                        );
                        if (testDeviceOption) {
                             newDeviceValue = `${testDeviceOption.device_id}|${testDeviceOption.device_type}|${testDeviceOption.room}`;
                        } else {
                            console.warn(`No specific TEST device found for type ${currentDeviceType}. Cannot update device.`);
                            // Keep current selection if no specific test device found
                            return;
                        }

                    } else { // realtime topic
                        // For realtime topic, find a non-test device with the same type
                        // Find the first non-test device with the matching type
                         const realtimeDeviceOption = availableDevices.find(d =>
                            d.device_type === currentDeviceType && !d.device_id.startsWith('TEST_')
                        );
                         if (realtimeDeviceOption) {
                             newDeviceValue = `${realtimeDeviceOption.device_id}|${realtimeDeviceOption.device_type}|${realtimeDeviceOption.room}`;
                         } else {
                             console.warn(`No specific REALTIME device found for type ${currentDeviceType}. Keeping current selection.`);
                            // Keep current selection if no specific realtime device found
                            return;
                         }
                    }

                    // Update the select value only if a different value was determined
                    if (deviceIdSelect.value !== newDeviceValue) {
                         const optionToSelect = Array.from(deviceIdSelect.options).find(opt => opt.value === newDeviceValue);
                         if (optionToSelect) {
                              deviceIdSelect.value = newDeviceValue;
                              console.log(`Updated device select to: ${newDeviceValue}`);
                         } else {
                              console.warn(`Generated device value "${newDeviceValue}" does not exist in options. Keeping current selection.`);
                         }
                    }
                }


                // Add event listeners to trigger updateDeviceInfo when relevant fields change
                homeIdInput.addEventListener('change', updateDeviceInfo);
                targetTopicSelect.addEventListener('change', updateDeviceInfo);
                // updateDeviceInfo will also be called implicitly if the device_id_select value changes
                // because that changes `currentDeviceType` inside the function when it's triggered by homeIdInput/targetTopicSelect

                // Initial update on page load to set the correct default device
                updateDeviceInfo();


                // --- Handle form submission with Fetch API ---
                manualDataForm.addEventListener('submit', function(event) {
                    // Prevent the default form submission (which causes page reload)
                    event.preventDefault();

                    // Display a sending message
                    formStatus.textContent = 'Đang gửi dữ liệu...';
                    formStatus.style.color = '#007bff';

                    // Get the form data
                    const formData = new FormData(manualDataForm);

                    // Send the data using Fetch API
                    fetch('/send-manual-data', {
                        method: 'POST',
                        body: formData // FormData handles encoding correctly
                    })
                    .then(response => {
                        if (!response.ok) {
                            // Handle HTTP errors
                            return response.json().then(data => {
                                throw new Error(data.message || `HTTP error! status: ${response.status}`);
                            });
                        }
                        return response.json(); // Parse the JSON response
                    })
                    .then(data => {
                        // Handle successful response
                        console.log('Server response:', data);
                        if (data.status === 'success') {
                            formStatus.textContent = data.message || 'Dữ liệu đã được gửi thành công!';
                            formStatus.style.color = '#28a745'; // Green color for success
                            // The suggestion should appear automatically via SSE
                        } else {
                             // Handle error response from server
                            formStatus.textContent = data.message || 'Có lỗi xảy ra khi gửi dữ liệu.';
                            formStatus.style.color = 'red'; // Red color for error
                        }
                    })
                    .catch(error => {
                        // Handle network errors or errors thrown in the .then block
                        console.error('Error submitting form:', error);
                        formStatus.textContent = `Lỗi khi gửi dữ liệu: ${error.message}`;
                        formStatus.style.color = 'red'; // Red color for error
                    });
                });

            });
        </script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        let costChart = null;

        function setupChart() {
            const ctx = document.getElementById('costChart').getContext('2d');
            costChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Chi phí điện (VND)',
                        data: [],
                        backgroundColor: 'rgba(0,123,255,0.6)'
                    }]
                },
                options: {
                    maintainAspectRatio: false, // ⬅️ THÊM DÒNG NÀY
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'VND' }
                        },
                        x: {
                            title: { display: true, text: 'Thời gian' }
                        }
                    }
                }
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            setupChart();
            document.getElementById('statisticsForm').addEventListener('submit', function (e) {
                e.preventDefault();

                const homeId = document.getElementById('stats_home_id').value;
                const period = document.getElementById('stats_period').value;
                const start = document.getElementById('stats_start_date').value;
                const end = document.getElementById('stats_end_date').value;

                const url = `/api/cost_data?home_id=${homeId}&start_date=${start}&end_date=${end}&period=${period}`;

                fetch(url).then(res => res.json()).then(data => {
                    if (data.length === 0) {
                        document.getElementById('noStatsDataMessage').style.display = 'block';
                        costChart.data.labels = [];
                        costChart.data.datasets[0].data = [];
                        costChart.update();
                        return;
                    }

                    document.getElementById('noStatsDataMessage').style.display = 'none';
                    costChart.data.labels = data.map(d => d.date);
                    costChart.data.datasets[0].data = data.map(d => d.cost);
                    costChart.update();
                }).catch(err => {
                    console.error("Lỗi khi gọi API:", err);
                });
            });

            const today = new Date().toISOString().split('T')[0];
            document.getElementById('stats_start_date').value = today;
            document.getElementById('stats_end_date').value = today;
        });
        </script>

    </body>
    </html>
    """
    # --- END HTML CONTENT ---

    # Write the HTML content to templates/index.html
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    print("[Flask UI] Starting Flask app...")
    # Run the Flask app, threaded=True allows handling multiple SSE clients and requests concurrently
    # use_reloader=False prevents the app from restarting twice on initial run
    # debug=True provides helpful error messages during development
    app.run(debug=True, threaded=True, use_reloader=False)
