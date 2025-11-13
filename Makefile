mqtt-to-email: mqtt-to-email.cpp
	$(CXX) mqtt-to-email.cpp -o mqtt-to-email -lmosquitto

install:
	sudo cp bambu-relay.service.sh /usr/local/bin/
	sudo cp bambu.cert /usr/local/etc/
	sudo cp bambu-relay.service /etc/systemd/system/
	sudo sudo systemctl enable bambu-relay.service
	sudo sudo systemctl restart bambu-relay.service
