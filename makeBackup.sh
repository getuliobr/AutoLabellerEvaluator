mongoContainer=$(awk -F "=" '/CONTAINER_NAME/ {print $2}' config.ini)
username=$(awk -F "=" '/USERNAME/ {print $2}' config.ini)
password=$(awk -F "=" '/PASSWORD/ {print $2}' config.ini)

echo "Dumping mongo data"
docker exec $mongoContainer mongodump --username=$username --password=$password --db=evaluator --out=/opt/backup
echo "Done dumping data, retrieving it from container"
docker cp $mongoContainer:/opt/backup/evaluator backup
echo "Cleaning container"
docker exec mongo rm -rf /opt/backup/evaluator
echo "Compacting data"
cd backup
tar czf evaluator_$(date +%Y%m%d-%H%M%S).tar.gz evaluator
echo "Cleaning up"
rm -rf evaluator
echo "Done"