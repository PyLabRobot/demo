# demo

The simulator server.

## tasks

### Starting the server

```sh
docker compose up -d
```

After a change to web:

```sh
docker-compose up -d --build web
```

### Generating a new activation code

```sh
./create-act.sh
```

### Logging into the database

```sh
sudo docker exec -ti demo-db-1 psql -U postgres -d db
```

### Rebuilding a change in the simulator

```sh
cd nb-docker
./build.sh
```
