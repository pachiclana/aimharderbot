git checkout master
git pull
docker rm aimharderbot:v1
docker rmi aimharderbot:v1
docker build -t aimharderbot:v1 .
