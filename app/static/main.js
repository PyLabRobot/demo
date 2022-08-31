var ws;

function hideSimulatorMessage() {
  var message = document.getElementById("simulator-not-loaded");
  message.style.display = "none";
}

function showSimulatorMessage() {
  var message = document.getElementById("simulator-not-loaded");
  message.style.display = "block";
}

function hideNotebookMessage() {
  var message = document.getElementById("notebook-not-loaded");
  message.style.display = "none";
}

function loadSimulator(simulator_iframe_url) {
  if (document.getElementById("simulator-iframe")) {
    document.getElementById("simulator-iframe").remove();
  }
  var simulator = document.getElementById("simulator");
  var simulator_iframe = document.createElement("iframe");
  simulator_iframe.src = simulator_iframe_url;
  simulator_iframe.id = "simulator-iframe";
  simulator.appendChild(simulator_iframe);
  hideSimulatorMessage();
}

function stopSimulator() {
  if (document.getElementById("simulator-iframe")) {
    document.getElementById("simulator-iframe").remove();
  }
  showSimulatorMessage();
}

function loadNotebook(notebook_iframe_url) {
  if (document.getElementById("notebook-iframe")) {
    document.getElementById("notebook-iframe").remove();
  }
  var notebook = document.getElementById("notebook");
  var notebook_iframe = document.createElement("iframe");
  notebook_iframe.id = "notebook-iframe";
  notebook_iframe.src = notebook_iframe_url;
  notebook.appendChild(notebook_iframe);
  hideNotebookMessage();
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
  const url = config["master_websocket_url"];
  ws = new WebSocket(url);
  ws.onopen = function () {
    console.log("Connected to master websocket");
    getSession();
  };

  ws.onmessage = function (event) {
    console.log("Received message from master websocket");
    console.log(event.data);
    var data = JSON.parse(event.data);
    if (data.type === "error") {
      console.log(data.error);
      alert(data.error);
    } else if (data.type === "set-session") {
      loadNotebook(data.notebook_iframe_url);

      if (data.hasOwnProperty("simulator_url")) {
        loadSimulator(data.simulator_url);
        console.log("Loaded simulator");
      }
    } else if (data.type === "start-simulator") {
      loadSimulator(data.url);
    } else if (data.type === "stop-simulator") {
      stopSimulator();
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
