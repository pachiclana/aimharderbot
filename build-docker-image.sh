git fetch
git pull
git checkout master
docker rm aimharderbot:v1
docker rmi aimharderbot:v1
docker build -t aimharderbot:v1 .
