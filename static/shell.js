// Presentation controls are separate from media/session lifecycle.
const $ = id => document.getElementById(id);
const tabs = [...document.querySelectorAll('[data-panel]')];
const panels = ['context', 'voice', 'memory'];
const narrow = () => window.matchMedia('(max-width: 960px)').matches;
function inspector(open) {
  document.body.classList.toggle('inspector-closed', !open);
  $('toggleInspector').setAttribute('aria-expanded', String(open));
}
function selectPanel(name, focus = false) {
  if (!panels.includes(name)) return;
  inspector(true);
  for (const tab of tabs) {
    const selected = tab.dataset.panel === name;
    tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
    $('panel-' + tab.dataset.panel).hidden = !selected;
    if (selected && focus) tab.focus();
  }
}
for (const tab of tabs) {
  tab.addEventListener('click', () => selectPanel(tab.dataset.panel));
  tab.addEventListener('keydown', event => {
    let index = panels.indexOf(tab.dataset.panel);
    if (event.key === 'ArrowRight') index = (index + 1) % panels.length;
    else if (event.key === 'ArrowLeft') index = (index + panels.length - 1) % panels.length;
    else if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = panels.length - 1;
    else return;
    event.preventDefault(); selectPanel(panels[index], true);
  });
}
document.querySelectorAll('[data-open-panel]').forEach(button => button.addEventListener('click', () => {
  selectPanel(button.dataset.openPanel, true);
  if (window.matchMedia('(max-width: 700px)').matches) document.body.classList.add('sidebar-collapsed');
}));
$('toggleInspector').onclick = () => inspector(document.body.classList.contains('inspector-closed'));
$('closeInspector').onclick = () => { inspector(false); $('toggleInspector').focus(); };
$('hideSidebar').onclick = () => document.body.classList.add('sidebar-collapsed');
$('showSidebar').onclick = () => document.body.classList.remove('sidebar-collapsed');
$('navChat').onclick = () => { if(narrow())inspector(false); $('text').focus(); };
if (narrow()) inspector(false);
if (window.matchMedia('(max-width: 700px)').matches) document.body.classList.add('sidebar-collapsed');
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('themeLabel').textContent = theme === 'dark' ? 'Світла тема' : 'Темна тема';
  $('themeToggle').setAttribute('aria-label', $('themeLabel').textContent);
}
try { setTheme(localStorage.getItem('assistantTheme') === 'light' ? 'light' : 'dark'); } catch { setTheme('dark'); }
$('themeToggle').onclick = () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(theme); try { localStorage.setItem('assistantTheme', theme); } catch {}
};
const input = $('text');
function resizeInput() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 150) + 'px'; }
input.addEventListener('input', resizeInput);
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault(); if(!input.disabled) $('chat').requestSubmit();
  }
});
$('chat').addEventListener('submit', () => requestAnimationFrame(resizeInput));
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => {
  input.value = button.dataset.prompt; resizeInput();
  if(input.disabled) $('start').click(); else input.focus();
}));
$('newChat').onclick = () => {
  if (!$('stop').disabled || !$('messages').querySelector('.welcome')) $('newChatDialog').showModal();
  else $('start').click();
};
$('cancelNewChat').onclick = () => $('newChatDialog').close();
$('confirmNewChat').onclick = () => {
  $('stop').click(); $('newChatDialog').close(); location.reload();
};
document.addEventListener('keydown', event => {
  if(event.key === 'Escape' && !$('newChatDialog').open) {
    inspector(false); if(window.matchMedia('(max-width: 700px)').matches) document.body.classList.add('sidebar-collapsed');
  }
});
