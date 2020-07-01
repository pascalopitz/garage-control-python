sudo apt update
sudo apt upgrade -y
sudo apt install -y vim python3-gpio fswebcam python3-pip
pip3 install aiobotocore supervisor RPi.GPIO python-dotenv

sudo cp garage.service /etc/systemd/system/garage.service
sudo systemctl start garage.service