const form = document.querySelector('#question-form');
const input = document.querySelector('#question');
const conversation = document.querySelector('#conversation');

function addMessage(text, type, sources = []) {
  const item = document.createElement('div');
  item.className = `message ${type}`;
  item.textContent = text;
  if (sources.length) {
    const source = document.createElement('div');
    source.className = 'sources';
    source.textContent = `წყარო: ${sources.map(x => x.chunk.source_label).join(' · ')}`;
    item.append(source);
  }
  conversation.append(item);
  item.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const query = input.value.trim();
  if (!query) return;
  addMessage(query, 'user'); input.value = '';
  const button = form.querySelector('button'); button.disabled = true;
  try {
    const response = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }) });
    const body = await response.text();
    let data;
    try { data = JSON.parse(body); } catch { data = { detail: body }; }
    addMessage(data.answer || data.detail || 'შეცდომა მოხდა.', 'assistant', data.sources || []);
  } catch { addMessage('სერვერთან კავშირი ვერ დამყარდა.', 'assistant'); }
  finally { button.disabled = false; input.focus(); }
});
