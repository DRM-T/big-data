# rcm.py - Recommendation Consumer
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'smarthome-suggestions',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='recommendation-ui-group'
)

print("[SUGGESTION LISTENER STARTED]")
try:
    for msg in consumer:
        data = msg.value
        print(f"[{data['suggestion']}")
except KeyboardInterrupt:
    print("[STOPPED] Suggestion listener stopped.")
