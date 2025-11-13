#!/usr/bin/python3

import json
import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, rc, properties):
    print(f"{userdata.name}: Connected with result code: {rc}")

def bambu_on_connect(client, userdata, flags, rc, properties):
    on_connect(client, userdata, flags, rc, properties)
    if rc == mqtt.MQTT_ERR_SUCCESS:
        client.subscribe("#")

def on_disconnect(client, userdata, disconnect_flags, rc, properties):
    print(f"{userdata.name}: Disconnected with result code: {rc}")

def on_log(client, userdata, log_level, msg):
    if log_level <= userdata.log_level:
        print(f"{userdata.name}: [{log_level}]: {msg}");

def normalize_bambu_json(userdata, json):
    if "print" not in json:
        json["print"] = { }
    printing = json["print"]
    if "err" not in printing:
        printing["err"] = userdata.current_err
    if "gcode_state" not in printing:
        printing["gcode_state"] = userdata.current_state
    if "subtask_name" not in printing:
        if "gcode_file" in printing:
            printing["subtask_name"] = printing["gcode_file"]
        if "file" in printing:
            printing["subtask_name"] = printing["file"]
        else:
            printing["subtask_name"] = "<unknown>"

def bambu_on_message(client, userdata, msg):
    response = json.loads(msg.payload.decode('utf-8'))

    normalize_bambu_json(userdata, response)
    new_state = response["print"]["gcode_state"]
    new_err = response["print"]["err"]

    if userdata.current_state != new_state:
        print(f"state transition: {userdata.current_state} => {new_state}")
        if new_state == "FINISH":
            email_server.publish(userdata.topic, f"Print completed: {response["print"]["subtask_name"]}")
        userdata.current_state = new_state
    if userdata.current_err != new_err:
        print(f"error transition: {userdata.current_err} => {new_err}")
        email_server.publish(userdata.topic, f"ERORR in print: {response["print"]["subtask_name"]} (err {new_err})")
        userdata.current_err = new_err

class EmailServerUserData:
    name = "email-server"
    log_level = mqtt.MQTT_LOG_INFO

email_server = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
email_server.user_data_set(EmailServerUserData())

email_server.on_connect = on_connect
email_server.on_disconnect = on_disconnect
email_server.on_log = on_log

email_server.username_pw_set("mqtt-to-email", "mqtt-to-email")
email_server.connect("mqtt.crpalmer.org", 1883)
email_server.loop_start()

class BambuUserData:
    name = "bambu"
    current_state = "FINISH"
    current_err = "0"
    log_level = mqtt.MQTT_LOG_INFO
    email = email_server
    topic = "alerts/h2d"

bambu_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
bambu_client.user_data_set(BambuUserData())

bambu_client.on_connect = bambu_on_connect
bambu_client.on_disconnect = on_disconnect
bambu_client.on_log = on_log
bambu_client.on_message = bambu_on_message

bambu_client.tls_set("/usr/local/etc/bambu.cert")
bambu_client.tls_insecure_set(True)
with open("/usr/local/etc/bambu-access-code.txt") as file:
    bambu_client.username_pw_set("bblp", file.read().strip())

bambu_client.connect("h2d", 8883) # Connect to a local broker on port 1883
bambu_client.loop_forever() # Keep the connection alive
