set -e

cd nb-docker

if [ ! -d "PyLabRobot" ]
then
  git clone http://github.com/PyLabRobot/PyLabRobot.git
fi

cd PyLabRobot
git pull
git checkout .
git apply ../simulator.diff
echo "Applied diff"
cd ..

docker image build -t nb-simple .
