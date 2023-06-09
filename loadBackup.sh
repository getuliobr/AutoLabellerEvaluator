mongoContainer=$(awk -F "=" '/CONTAINER_NAME/ {print $2}' config.ini)
username=$(awk -F "=" '/USERNAME/ {print $2}' config.ini)
password=$(awk -F "=" '/PASSWORD/ {print $2}' config.ini)

docker cp backup $mongoContainer:.
docker exec $mongoContainer mongorestore --username $username --password $password --verbose /backup
docker exec $mongoContainer rm -rf /backup