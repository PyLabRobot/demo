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

function showNotebookStoppedMessage() {
  hideNotebookMessage();
  var message = document.getElementById("notebook-stopped");
  message.style.display = "block";
}

function hideNotebookStoppedMessage() {
  var message = document.getElementById("notebook-stopped");
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
  hideNotebookStoppedMessage();
}

function stopNotebook() {
  if (document.getElementById("notebook-iframe")) {
    document.getElementById("notebook-iframe").remove();
  }
  showNotebookStoppedMessage();
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

var waitingOnUpdateRestart = false;
function displayUpdateAvailable() {
  const updateAvailable = document.getElementById("update-available");
  updateAvailable.style.display = "block";
  alert("An update is available. Please click the button in the top right.");
}

function hideUpdateAvailable() {
  const updateAvailable = document.getElementById("update-available");
  updateAvailable.style.display = "none";
}

function sendUpdateRequest(e) {
  ws.send(
    JSON.stringify({
      event: "update",
    })
  );

  e.target.disabled = true;

  document.getElementById("update-loader").style.display = "block";
  waitingOnUpdateRestart = true;
}

function startMasterWebsocket() {
  const url = config["master_websocket_url"];
  ws = new WebSocket(url);
  ws.onopen = function () {
    console.log("Connected to master websocket");
    getSession();

    heartbeat();
  };

  ws.onmessage = function (event) {
    console.log("Received message from master websocket");
    console.log(event.data);
    var data = JSON.parse(event.data);
    if (data.type === "error") {
      console.log(data.error);
      alert(data.error);
    } else if (data.type === "set-session") {
      if (
        !(
          data.notebook_iframe_url === undefined ||
          data.notebook_iframe_url === null
        )
      ) {
        loadNotebook(data.notebook_iframe_url);
      }

      if (data.hasOwnProperty("simulator_url")) {
        loadSimulator(data.simulator_url);
        console.log("Loaded simulator");
      }
    } else if (data.type === "start-container") {
      if (data.update_available === true) {
        displayUpdateAvailable();
      }

      if (waitingOnUpdateRestart) {
        hideUpdateAvailable();
      }
    } else if (data.type === "start-notebook") {
      loadNotebook(data.url);
    } else if (data.type === "stop-notebook") {
      stopNotebook();
    } else if (data.type === "start-simulator") {
      loadSimulator(data.url);
    } else if (data.type === "stop-simulator") {
      stopSimulator();
    }
  };

  ws.onclose = function () {
    console.log("Disconnected from master websocket. Retrying in 1 sec...");

    setTimeout(function () {
      startMasterWebsocket();
    }, 1000);
  };
}

function heartbeat() {
  if (!ws) return;
  ws.send(JSON.stringify({ event: "ping" }));
  setTimeout(heartbeat, 5000);
}

var firstTimeMessage = document.getElementById("first-time-window");
firstTimeMessage.onclick = function (event) {
  if (event.target.id === "first-time-window") {
    closeSettings();
  }
};
var canCloseFirstTimeMessage = false;

function openFirstTimeMessage() {
  firstTimeMessage.style.display = "block";

  // Wait 10 seconds before allowing the user to close the message
  var waited = 0;
  var interval;
  const waitDuration = 10;

  function updateWaiting() {
    waited += 1;

    if (waited >= waitDuration) {
      canCloseFirstTimeMessage = true;
      clearInterval(interval);
    }

    const button = document.getElementById("first-time-close");
    button.textContent = `Close (${waitDuration - waited}s)`;
    button.disabled = !canCloseFirstTimeMessage;
  }

  interval = setInterval(updateWaiting, 1000);
  updateWaiting();
}

function closeFirstTimeMessage() {
  if (canCloseFirstTimeMessage) {
    firstTimeMessage.style.display = "none";
    localStorage.setItem("shown-first-time-message", "true");
  }
}

function displayFirstTimeMessageIfNecessary() {
  if (localStorage.getItem("shown-first-time-message") === null) {
    openFirstTimeMessage();
  }
}

function start() {
  startMasterWebsocket();

  displayFirstTimeMessageIfNecessary();
}

window.onload = start;
