# PyHamilton Platform

A place to store and share support files for PyHamilton methods.

The core data model is the `Project` object, which contains a `File` object in the `files` attribute for each source file.

## API

### Authentication

**Login**

```
curl -X POST --cookie-jar cookie.txt -H "Content-Type: application/json" -d '{"username":"username","password":"password"}' http://localhost:5000/auth/login
```

This will return a cookie named `cookie.txt` that can be used to authenticate future requests.

### Projects

**Create a new project**

```sh
curl -X POST --cookie cookie.txt localhost:5000/platform/projects -H "Content-Type: application/json" -d '{"name": "project"}'
```

```json
{
  "created_on": "2022-07-16T21:55:32.369039",
  "files": [],
  "id": "f910b63e-de3f-49a4-bb53-5533cabd9450",
  "name": "project",
  "updated_on": "2022-07-16T21:55:32.369039"
}
```

**Get a project by id**

```sh
curl -X GET localhost:5000/platform/projects/f910b63e-de3f-49a4-bb53-5533cabd9450
```

```json
{
  "created_on": "2022-07-16T21:55:32.369039",
  "files": [],
  "id": "f910b63e-de3f-49a4-bb53-5533cabd9450",
  "name": "project",
  "updated_on": "2022-07-16T21:55:32.369039"
}
```

### Files

**Add files to a project**

```sh
curl -X POST --cookie cookie.txt localhost:5000/platform/files -F 'project_id=f910b63e-de3f-49a4-bb53-5533cabd9450' -F 'files=@my_file.txt' -F 'files=@my_other_file.txt'
```

```json
{
  "files": [
    {
      "created_on": "2022-07-16T22:26:26.736501",
      "id": "38e02fd5-1179-4082-a85b-a530547a1a5e",
      "name": "my_file.txt",
      "project_id": "f910b63e-de3f-49a4-bb53-5533cabd9450",
      "updated_on": "2022-07-16T22:26:26.736501"
    },
    {
      "created_on": "2022-07-16T22:26:26.742258",
      "id": "1d4f2d5c-3262-43d1-8929-e915f9472310",
      "name": "my_other_file.txt",
      "project_id": "f910b63e-de3f-49a4-bb53-5533cabd9450",
      "updated_on": "2022-07-16T22:26:26.742258"
    }
  ],
  "success": true
}
```

**Get a file by id**

```sh
curl -X GET localhost:5000/platform/files/38e02fd5-1179-4082-a85b-a530547a1a5e
```

```json
{
  "created_on": "2022-07-16T22:17:09.404630",
  "id": "38e02fd5-1179-4082-a85b-a530547a1a5e",
  "name": "my_file.txt",
  "project_id": "f910b63e-de3f-49a4-bb53-5533cabd9450",
  "updated_on": "2022-07-16T22:17:09.404630"
}
```

**Download a file**

```sh
curl -X GET localhost:5000/platform/files/38e02fd5-1179-4082-a85b-a530547a1a5e/download > my_file.txt
```
