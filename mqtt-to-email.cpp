#include <mosquitto.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

void
on_connect(struct mosquitto *mosq, void *obj, int reason_code) {
    int rc;

    fprintf(stderr, "on_connect: %s\n", mosquitto_connack_string(reason_code));

    if (reason_code != 0) {
	/* do nothing and then connection will be retried */
	return;
    }

    rc = mosquitto_subscribe(mosq, NULL, "alerts", 1);
    if (rc != MOSQ_ERR_SUCCESS) {
	fprintf(stderr, "Error subscribing: %s\n", mosquitto_strerror(rc));
	exit(1);
    }
}


void
on_subscribe(struct mosquitto *mosq, void *obj, int mid, int qos_count, const int *granted_qos) {
    bool have_subscription = false;

    for (int i = 0; i < qos_count; i++) {
	printf("on_subscribe: %d:granted qos = %d\n", i, granted_qos[i]);
	if (granted_qos[i] <= 2) {
	    have_subscription = true;
	}
    }

    if (! have_subscription) {
	/* The broker rejected all of our subscriptions, we know we only sent
	 * the one SUBSCRIBE, so there is no point remaining connected. */
	fprintf(stderr, "Error: All subscriptions rejected.\n");
	exit(1);
    }
}

#define EMAIL "crpalmer@gmail.com"

void
on_message(struct mosquitto *mosq, void *obj, const struct mosquitto_message *msg) {
    //FILE *pipe = popen("cat", "w");
    FILE *pipe = popen("ssmtp -au crpalmer@gmail.com " EMAIL, "w");
    if (! pipe) {
	perror("popen");
	exit(1);
    }
    fprintf(pipe, "To: " EMAIL "\nFrom: crpalmer@gmail.com\nSubject: MQTT Alert\n\n%s", (char *) msg->payload);
    fclose(pipe);
    printf("sent alert: %s\n", (char *) msg->payload);
}

int
main(int argc, char *argv[]) {
    int rc;

    /* Required before calling other mosquitto functions */
    mosquitto_lib_init();

    /* Create a new client instance.
     * id = NULL -> ask the broker to generate a client id for us
     * clean session = true -> the broker should remove old sessions when we connect
     * obj = NULL -> we aren't passing any of our private data for callbacks
     */
    struct mosquitto *mosq = mosquitto_new(NULL, true, NULL);
    if (mosq == NULL) {
	fprintf(stderr, "Error: Out of memory.\n");
	exit(1);
    }

    /* Configure callbacks. This should be done before connecting ideally. */
    mosquitto_connect_callback_set(mosq, on_connect);
    mosquitto_subscribe_callback_set(mosq, on_subscribe);
    mosquitto_message_callback_set(mosq, on_message);

    rc = mosquitto_connect(mosq, "mqtt.crpalmer.org", 1883, 60);
    if (rc != MOSQ_ERR_SUCCESS) {
	fprintf(stderr, "Error: %s\n", mosquitto_strerror(rc));
	exit(1);
    }

    mosquitto_loop_forever(mosq, -1, 1);

    return 0;
}

