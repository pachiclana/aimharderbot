git fetch
git pull
git checkout develop
docker rm aimharderbot_test:v1
docker rmi aimharderbot_test:v1
docker build -t aimharderbot_test:v1 .
