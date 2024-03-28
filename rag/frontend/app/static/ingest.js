var ingestButton = null;
var serverOutput = null;
var spinner = null;

function startup() {
    ingestButton = document.getElementById('ingest-button');
    serverOutput = document.getElementById('server-output');
    spinner = document.getElementById('spinner');
}

function showIngestButton(show) {
    ingestButton.style.visibility = (show?'visible':'hidden');
}

function showSpinner(show) {
    spinner.style.display = (show?'block':'none');
}

// Function to read a stream line by line
async function readStreamLineByLine(stream) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let partialLine = '';
  
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
  
      const chunk = decoder.decode(value, { stream: true });
      const lines = (partialLine + chunk).split('\n');
      partialLine = lines.pop(); // Store incomplete line for the next iteration
  
      for (const line of lines) {
        // Process each line here
        appendOutput(line);
      }
    }
  
    // Process the remaining partial line, if any
    if (partialLine) {
      // Process the last line
      appendOutput(partialLine);
    }
  
    reader.releaseLock();
}

function ingest() {
    showIngestButton(false);
    showSpinner(true);
    appendOutput("sending request to server...");
    fetch('/api/ingest', {
        method: 'GET',
        headers: { 'Accept': 'text/plain'}
    })
    .then(response => response.body)
    .then(readStreamLineByLine)
    .catch(error => {
        appendOutput('error: ' + error);
    })
    .finally( () => {
        showSpinner(false);
        showIngestButton(true);
    });
}

function deletedb() {
    fetch('/api/deletedb')
    .then(response => {
        if (response.status >= 200 && response.status < 300)
            appendOutput('database deleted');
        else
            appendOutput('error deleting database - response status ' + response.status);
    })
    .catch(error => appendOutput(error));
}

function refreshdb() {
    fetch('/api/refreshdb')
    .then(response => {
        if (response.status >= 200 && response.status < 300)
            appendOutput('database refreshed');
        else
            appendOutput('error refreshing database - response status ' + response.status);
    })
    .catch(error => appendOutput(error));
}

function appendOutput(msg) {
    let line = document.createElement("div");
    line.className = "server-output-line";
    line.innerText = msg;
    serverOutput.appendChild(line);
    serverOutput.scrollIntoView(false);
}

window.addEventListener('load', startup, false);