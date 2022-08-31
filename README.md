# demo

The simulator server.

## Common tasks

### Starting the server

- Dev:

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Server will run at [http://localhost](http://localhost).

- Prod:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

After a change to web:

```sh
docker compose build web
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
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
./build.sh
```

## Issues / TODO

- [ ] Can we provide the docker image for the simulator on the registry, include it in the simulator
      readme and also use it here?
- [ ] Use https://github.com/docker/docker-py
