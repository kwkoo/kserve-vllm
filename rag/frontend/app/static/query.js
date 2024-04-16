var prompt = null;
var queryButton = null;
var llmResponse = null;
var sources = null;
var spinner = null;

function startup() {
    prompt = document.getElementById('prompt');
    queryButton = document.getElementById('query-button');
    llmResponse = document.getElementById('llm-response');
    sources = document.getElementById('sources');
    spinner = document.getElementById('spinner');

    prompt.focus();
}

function showQueryButton(show) {
    queryButton.style.visibility = (show?'visible':'hidden');
}

function showLLMResponse(show) {
    llmResponse.style.display = (show?'block':'none');
}

function showSpinner(show) {
    spinner.style.display = (show?'block':'none');
}

function clearLLMResponse() {
    llmResponse.innerText = '';
}

function clearSources() {
    while (sources.firstChild) {
        sources.removeChild(sources.lastChild);
        sources.scrollIntoView(false);
    }
}

function appendError(text) {
    let d = document.createElement('div');
    d.className = 'error';
    d.innerText = text;
    sources.appendChild(d);
    d.scrollIntoView(false);
}

function appendSource(path, contents) {
    let p = document.createElement('div');
    p.className = 'path';
    p.innerText = path;
    let c = document.createElement('div');
    c.className = 'contents';
    c.innerText = contents;

    let s = document.createElement('div');
    s.className = 'source';
    s.appendChild(p);
    s.appendChild(c);

    sources.appendChild(s);
    s.scrollIntoView(false);
}

function appendToLLMResponse(text) {
    llmResponse.innerText += text;
    llmResponse.scrollIntoView(false);
}

function processLine(text) {
    let obj = null;
    try {
        obj = JSON.parse(text);
    }
    catch (e) {
        appendError(e);
        console.log('error parsing json, offending text = "' + text + '"');
        return
    }
    if (obj == null) return;
    if (obj.text != null) {
        appendToLLMResponse(obj.text);
        return
    }
    if (obj.source != null) {
        appendSource(obj.source.path, obj.source.contents);
    }
}

function lookForEnter() {
    if (event.key === 'Enter') query();
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
        processLine(line);
      }
    }
  
    // Process the remaining partial line, if any
    if (partialLine) {
      // Process the last line
      processLine(partialLine);
    }
  
    reader.releaseLock();
  }

function query() {
    showQueryButton(false);
    showSpinner(true);
    clearLLMResponse();
    clearSources();
    showLLMResponse(true);
    fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify({ prompt: prompt.value })
    })
    .then(response => response.body)
    .then(readStreamLineByLine)
    .catch(error => appendToLLMResponse('\n\nerror: ' + error))
    .finally( () => {
        showSpinner(false);
        showQueryButton(true);
    });
}

window.addEventListener('load', startup, false);
