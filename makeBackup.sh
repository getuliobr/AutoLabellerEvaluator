mongoContainer=$(awk -F "=" '/CONTAINER_NAME/ {print $2}' config.ini)
db=$(awk -F "=" '/^NAME/ {print $2}' config.ini)

echo "Dumping mongo data"
docker exec $mongoContainer mongodump --db=$db --out=/opt/backup
echo "Done dumping data, retrieving it from container"
docker cp $mongoContainer:/opt/backup/$db backup
echo "Cleaning container"
docker exec mongo rm -rf /opt/backup/$db
# Em caso de querer compactar
# echo "Compacting data"
# cd backup
# tar czf evaluator_$(date +%Y%m%d-%H%M%S).tar.gz evaluator
# echo "Cleaning up"
# rm -rf evaluator
echo "Done"