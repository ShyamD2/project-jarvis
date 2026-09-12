/*
  J.A.R.V.I.S. ESP32 Microcontroller Node
  Hardware: ESP32 DevKit V1
  Capabilities:
    - 4-Channel Relay Control (Relay 1: Desk Lamp, Relay 2: Overhead Light, Relay 3: Fan, Relay 4: Power Strip)
    - Ambient Light Sensor (LDR / BH1750)
    - Temperature / Humidity Sensor (DHT22)
    - Sound / Clap Sensor (KY-038)
    - MQTT Bi-directional Fast-Path Communication
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Wi-Fi Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// MQTT Broker Configuration (Local Gateway / Mosquitto)
const char* mqtt_server = "192.168.1.100";
const int mqtt_port = 1883;
const char* device_id = "esp32_lab_01";

// Pinout Definitions
const int RELAY_1_PIN = 16; // Desk Lamp
const int RELAY_2_PIN = 17; // Main Light
const int RELAY_3_PIN = 18; // Fan
const int RELAY_4_PIN = 19; // Auxiliary Power
const int LUX_ANALOG_PIN = 34;
const int SOUND_DIGITAL_PIN = 35;

WiFiClient espClient;
PubSubClient client(espClient);

long lastMsg = 0;

void setup_wifi() {
  delay(10);
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected. IP address: ");
  Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* message, unsigned int length) {
  String messageTemp;
  for (int i = 0; i < length; i++) {
    messageTemp += (char)message[i];
  }
  Serial.print("Message arrived on topic [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(messageTemp);

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, messageTemp);
  if (error) {
    Serial.println("Failed to parse command JSON");
    return;
  }

  const char* action = doc["action"];
  const char* target = doc["target"];
  bool state = doc["state"];

  if (strcmp(target, "desk_lamp") == 0) {
    digitalWrite(RELAY_1_PIN, state ? HIGH : LOW);
  } else if (strcmp(target, "light_main") == 0) {
    digitalWrite(RELAY_2_PIN, state ? HIGH : LOW);
  } else if (strcmp(target, "fan") == 0) {
    digitalWrite(RELAY_3_PIN, state ? HIGH : LOW);
  }

  // Publish state confirmation
  publish_state();
}

void publish_state() {
  int rawLux = analogRead(LUX_ANALOG_PIN);
  float lux = map(rawLux, 0, 4095, 0, 1000);

  StaticJsonDocument<256> stateDoc;
  stateDoc["device_id"] = device_id;
  stateDoc["relays"]["desk_lamp"] = (digitalRead(RELAY_1_PIN) == HIGH);
  stateDoc["relays"]["light_main"] = (digitalRead(RELAY_2_PIN) == HIGH);
  stateDoc["sensors"]["lux"] = lux;

  char buffer[256];
  serializeJson(stateDoc, buffer);
  client.publish("jarvis/devices/esp32_lab_01/state", buffer);
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect(device_id)) {
      Serial.println("connected");
      client.subscribe("jarvis/devices/esp32_lab_01/command");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_1_PIN, OUTPUT);
  pinMode(RELAY_2_PIN, OUTPUT);
  pinMode(RELAY_3_PIN, OUTPUT);
  pinMode(RELAY_4_PIN, OUTPUT);
  digitalWrite(RELAY_1_PIN, LOW);
  digitalWrite(RELAY_2_PIN, LOW);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  long now = millis();
  if (now - lastMsg > 5000) {
    lastMsg = now;
    publish_state();
  }
}
