var ws;

function hideSimulatorMessage() {
  var message = document.getElementById("simulator-not-loaded");
  message.style.display = "none";
}

function loadSimulator(simulator_iframe_url) {
  var simulator = document.getElementById("simulator");
  var simulator_iframe = document.createElement("iframe");
  simulator_iframe.src = simulator_iframe_url;
  simulator_iframe.id = "simulator-iframe";
  simulator.appendChild(simulator_iframe);
  hideSimulatorMessage();
}

function loadNotebook(notebook_iframe_url) {
  var notebook = document.getElementById("notebook");
  var notebook_iframe = document.createElement("iframe");
  notebook_iframe.id = "notebook-iframe";
  notebook_iframe.src = notebook_iframe_url;
  notebook.appendChild(notebook_iframe);
}

function getSession() {
  fetch("/get-session")
    .then((r) => r.json())
    .then((r) => {
      ws.send(
        JSON.stringify({
          type: "set-session",
          session_id: r.session_id,
        })
      );
      document.getElementById("session-id").textContent = r.session_id;
    })
    .catch((e) => {
      console.log(e);
    });
}

function startMasterWebsocket() {
  ws = new WebSocket(`ws://${window.location.host}/master`);
  ws.onopen = function () {
    console.log("Connected to master websocket");
    getSession();
  };

  ws.onmessage = function (event) {
    console.log("Received message from master websocket");
    console.log(event.data);
    var data = JSON.parse(event.data);
    if (data.type === "set-session") {
      loadNotebook(data.notebook_iframe_url);

      if (data.hasOwnProperty("simulator_url")) {
        loadSimulator(data.simulator_url);
        console.log("Loaded simulator");
      }
    } else if (data.type === "set-file-server") {
      loadSimulator(data.simulator_url);
    }
  };

  ws.onclose = function () {
    console.log("Disconnected from master websocket");
  };
}

function start() {
  startMasterWebsocket();
}

window.onload = start;
