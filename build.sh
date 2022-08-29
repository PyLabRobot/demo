cd nb-docker

if [ ! -d "PyLabRobot" ]
then
  git clone http://github.com/PyLabRobot/PyLabRobot.git
fi

cd PyLabRobot
git pull
cd ..

docker image build -t nb-simple .
