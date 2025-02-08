git checkout develop
git pull
docker rm aimharderbot_test:v1
docker rmi aimharderbot_test:v1
docker build -t aimharderbot_test:v1 .
