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

### See who logged in in the past x hours

```sh
sudo docker exec -it demo-db-1 psql -U postgres -d db -c "select events.id, events.created_on, events.code, users.id, users.email from events inner join users on events.uid = users.id where events.created_on > (NOW() - INTERVAL '15 hours' ) order by events.created_on;"
```

## Issues / TODO

- [ ] Can we provide the docker image for the simulator on the registry, include it in the simulator
      readme and also use it here? https://docs.github.com/en/actions/publishing-packages/publishing-docker-images#publishing-images-to-docker-hub
- [ ] Use https://github.com/docker/docker-py
- [ ] Use custom.css to hide notebook header. Create custom buttons for restart and stop. (include
      option for container as well)
- [ ] Share/fork/view.
