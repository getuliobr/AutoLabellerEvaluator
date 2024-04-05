mongoContainer=$(awk -F "=" '/CONTAINER_NAME/ {print $2}' config.ini)
username=$(awk -F "=" '/USERNAME/ {print $2}' config.ini)
password=$(awk -F "=" '/PASSWORD/ {print $2}' config.ini)

echo "Moving to container"
docker cp backup $mongoContainer:.
echo "Restoring database"
docker exec $mongoContainer mongorestore --verbose /backup
echo "Cleaning"
docker exec $mongoContainer rm -rf /backup
echo "Done"