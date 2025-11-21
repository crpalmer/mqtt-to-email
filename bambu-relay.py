#!/usr/bin/python3

import json
import paho.mqtt.client as mqtt
import time

ignored_errors = [
    "0",            # no error
    "0300-400C",     # print was cancelled
    "0500-400E",     # print was cancelled
]

class ErrorString:
    def __init__(this, errors, string):
        this.errors = errors
        this.string = string

    def matches(this, error):
        return error in this.errors

error_strings = [
    # Unknown errors that I've hit:
    ErrorString([ "0300-801E" ], "The extruder motor is overloaded."),
    ErrorString([ "0500-806E" ], "A foreign object on the build plate was detected."),
    ErrorString([ "0500-808C" ], "Could not identify build plate or invalid build plate was specified."),
    ErrorString([ "0700-8011" ], "AMS reports filament ran out."),
    ErrorString([ "07FF-8020" ], "Failed to change nozzles"),
    ErrorString([ "0500-8051" ], "Build plate specified by the task is different than the detected build plate."),

    # From the Bambu Error List
    ErrorString([ "0300-800A" ], "A Filament pile-up was detected by the AI Print Monitoring. Please clean the filament from the waste chute."),
    ErrorString([ "0300-8003" ], "Spaghetti defects were detected by the AI Print Monitoring. Please check the quality of the printed model before continuing your print."),
    ErrorString([ "0700-8010", "0701-8010" ], "The AMS assist motor is overloaded. This could be due to entangled filament or a stuck spool."),
    ErrorString([ "07FF-8010", "0702-8010", "0703-8010"], "AMS assist motor is overloaded. Please check if the spool or filament is stuck. After troubleshooting, click the \"Retry\" button."),
    ErrorString([ "0300-4008" ], "The AMS failed to change filament."),
    ErrorString([ "0700-8001", "0701-8001", "0702-8001", "0703-8001" ], "The AMS failed to change filament."),
    ErrorString([ "0300-800B" ], "The cutter is stuck. Please make sure the cutter handle is out."),
    ErrorString([ "1200-8001" ], "Cutting the filament failed. Please check to see if the cutter is stuck. Refer to the Assistant for solutions."),
    ErrorString([ "0300-4006" ], "The nozzle is clogged."),
    ErrorString([ "0300-8008" ], "Printing Stopped because nozzle temperature problem.")
]

def error_to_string(error):
    for error_string in error_strings:
        if error_string.matches(error):
            return error_string.string
    return f"Unknown error: {error}"

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
    elif len(printing["err"]) >= 8:
        err = printing["err"]
        printing["err"] = err[len(err) - 8 : len(err)-4] + "-" + err[len(err)-4:]
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
    try:
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
            if new_err != "0":
                if new_err in ignored_errors:
                    print("[error is ignored]")
                else:
                    email_server.publish(userdata.topic, f"ERORR in print: {error_to_string(new_err)} (err {new_err})")
            userdata.current_err = new_err
    except JSONDecodeError as error:
        print(f"Failed to decode JSON: {error}")
        print(msg.payload)
    except Exception as error:
        print(f"Exception ocurred: {error}")

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
