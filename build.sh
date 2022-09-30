set -e

cd nb-docker

if [ ! -d "PyLabRobot" ]
then
  git clone http://github.com/PyLabRobot/PyLabRobot.git
fi

cd PyLabRobot
git checkout .
git pull
git apply ../simulator.diff
echo "Applied diff"
cd ..

docker image build -t nb-simple --platform linux/amd64 .
