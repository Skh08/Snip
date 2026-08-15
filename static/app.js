const form = document.querySelector('#question-form');
const input = document.querySelector('#question');
const conversation = document.querySelector('#conversation');
const submitButton = form.querySelector('button[type="submit"]');

function addMessage(text, type, sources = [], options = {}) {
  const item = document.createElement('article');
  item.className = `message ${type}`;
  if (options.clarification) item.classList.add('clarification');

  const label = document.createElement('span');
  label.className = 'message-label';
  label.textContent = type === 'user' ? 'თქვენ' : 'ასისტენტი';
  item.append(label, document.createTextNode(text));

  if (sources.length) {
    const source = document.createElement('div');
    source.className = 'sources';
    const heading = document.createElement('span');
    heading.textContent = 'წყარო:';
    source.append(heading);
    [...new Set(sources.map(item => item.chunk.source_label))].forEach(label => {
      const chip = document.createElement('span');
      chip.className = 'source-label';
      chip.textContent = label;
      source.append(chip);
    });
    item.append(source);
  }

  conversation.append(item);
  item.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return item;
}

function addTypingIndicator() {
  const item = document.createElement('div');
  item.className = 'message assistant';
  item.setAttribute('aria-label', 'პასუხი მზადდება');
  item.innerHTML = '<span class="message-label">ასისტენტი</span><span class="typing"><span></span><span></span><span></span></span>';
  conversation.append(item);
  item.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return item;
}

document.querySelectorAll('[data-question]').forEach(button => {
  button.addEventListener('click', () => {
    input.value = button.dataset.question;
    input.focus();
  });
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const query = input.value.trim();
  if (!query) return;

  addMessage(query, 'user');
  input.value = '';
  submitButton.disabled = true;
  form.setAttribute('aria-busy', 'true');
  const indicator = addTypingIndicator();

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    const body = await response.text();
    let data;
    try { data = JSON.parse(body); } catch { data = { detail: body }; }
    indicator.remove();
    const sources = data.grounded ? (data.sources || []) : [];
    addMessage(
      data.answer || data.detail || 'შეცდომა მოხდა. სცადეთ ხელახლა.',
      'assistant',
      sources,
      { clarification: data.grounded === false }
    );
  } catch {
    indicator.remove();
    addMessage('სერვერთან კავშირი ვერ დამყარდა. სცადეთ ხელახლა.', 'assistant');
  } finally {
    submitButton.disabled = false;
    form.removeAttribute('aria-busy');
    input.focus();
  }
});
