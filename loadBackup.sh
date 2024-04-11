mongoContainer=$(awk -F "=" '/CONTAINER_NAME/ {print $2}' config.ini)

echo $mongoContainer

echo "Moving backup data to container"
docker cp backup $mongoContainer:.
echo "Restoring backup"
docker exec $mongoContainer mongorestore --verbose /backup
echo "Cleaning up container"
docker exec $mongoContainer rm -rf /backup
echo "Done"