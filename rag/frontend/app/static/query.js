var prompt = null;
var queryButton = null;
var llmResponse = null;
var spinner = null;

function startup() {
    prompt = document.getElementById('prompt');
    queryButton = document.getElementById('query-button');
    llmResponse = document.getElementById('llm-response');
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

function appendToLLMResponse(text) {
    llmResponse.innerText += text;
    llmResponse.scrollIntoView(false);
}

function lookForEnter() {
    if (event.key === 'Enter') query();
}

// Function to read a stream line by line
async function readStream(stream) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
  
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
  
      const chunk = decoder.decode(value, { stream: true });
      appendToLLMResponse(chunk);
    }
  
    reader.releaseLock();
}

function query() {
    showQueryButton(false);
    showSpinner(true);
    clearLLMResponse();
    showLLMResponse(true);
    fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify({ prompt: prompt.value })
    })
    .then(response => response.body)
    .then(readStream)
    .catch(error => appendToLLMResponse('\n\nerror: ' + error))
    .finally( () => {
        showSpinner(false);
        showQueryButton(true);
    });
}

window.addEventListener('load', startup, false);
