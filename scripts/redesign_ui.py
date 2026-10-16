from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / 'static/index.html'
old = path.read_text(encoding='utf-8')

def between(start, end):
    return old.split(start, 1)[1].split(end, 1)[0]

camera = '<label>Камера' + between('<label>Камера', '<label>Мікрофон')
microphone = '<label>Мікрофон' + between('<label>Мікрофон', '<label for="asrModel">')
recognition = '<label for="asrModel">' + between('<label for="asrModel">', '<label class="check"><input id="voice"')
voice = '<label class="check"><input id="voice"' + between('<label class="check"><input id="voice"', '<label class="check"><input id="initiative"')
initiative = '<label class="check"><input id="initiative"' + between('<label class="check"><input id="initiative"', '</section>')
onboarding = '<details id="onboarding">' + between('<details id="onboarding">', '</details>') + '</details>'
memory = '<div id="memories">' + between('<div id="memories">', '</section>')

icons = {
 'panel':'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18"/>',
 'chat':'<path d="M21 11a8 8 0 0 1-8 8H5l-3 3V11a8 8 0 0 1 8-8h3a8 8 0 0 1 8 8Z"/>',
 'memory':'<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M8 3v4m8-4v4M8 11h8m-8 4h5"/>',
 'settings':'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
 'plus':'<path d="M12 5v14M5 12h14"/>',
 'arrow':'<path d="M12 19V5m-6 6 6-6 6 6"/>',
 'camera':'<rect x="3" y="5" width="13" height="14" rx="3"/><path d="m16 9 5-3v12l-5-3"/>',
 'mic':'<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8"/>',
 'close':'<path d="m6 6 12 12M6 18 18 6"/>',
 'sun':'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
 'wave':'<path d="M4 10v4m4-8v12m4-15v18m4-15v12m4-8v4"/>',
}
def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icons[name]}</svg>'

path.write_text(f'''<!doctype html>
<html lang="uk" data-theme="dark">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light">
<title>Поруч — домашній асистент</title><link rel="stylesheet" href="/static/style.css"></head>
<body>
<div class="app-shell">
<nav class="sidebar" id="sidebar" aria-label="Головна навігація">
  <div class="sidebar-brand"><a class="brand" href="/" aria-label="Поруч — головна">{icon('wave')}<span>Поруч</span></a><button id="hideSidebar" class="icon-button" aria-label="Згорнути бічну панель" title="Згорнути панель">{icon('panel')}</button></div>
  <button id="newChat" class="new-chat">{icon('plus')}<span>Нова розмова</span><kbd>↗</kbd></button>
  <div class="nav-group"><span class="section-label">Простір</span>
    <button class="nav-item selected" id="navChat" aria-current="page">{icon('chat')}Розмова</button>
    <button class="nav-item" data-open-panel="memory">{icon('memory')}Пам’ять</button>
    <button class="nav-item" data-open-panel="voice">{icon('settings')}Налаштування голосу</button>
  </div>
  <div class="session-list"><span class="section-label">Поточна сесія</span><div class="session-item"><span class="status-dot"></span><span id="sessionName">Домашній асистент</span></div><p class="sidebar-note">Історія цієї розмови зберігається лише до завершення сесії.</p></div>
  <div class="sidebar-bottom"><button id="themeToggle" class="nav-item">{icon('sun')}<span id="themeLabel">Світла тема</span></button><div class="profile"><div class="avatar">Т</div><div><strong>Твій асистент</strong><small><span class="status-dot"></span>Локальний простір</small></div><span class="local-badge">LOCAL</span></div></div>
</nav>
<div class="workspace">
  <header class="topbar"><div class="topbar-left"><button id="showSidebar" class="icon-button" aria-label="Показати бічну панель" title="Бічна панель">{icon('panel')}</button><span class="breadcrumb">Особистий простір</span><span class="separator">/</span><strong>Домашній асистент</strong></div><div class="topbar-actions"><button id="start" class="primary compact">Почати сесію</button><button id="stop" class="secondary compact" disabled>Зупинити</button><button id="toggleInspector" class="icon-button" aria-label="Показати панель асистента" aria-expanded="true" aria-controls="inspector" title="Панель асистента">{icon('settings')}</button></div></header>
  <div class="workspace-body">
    <main class="conversation" aria-label="Розмова з асистентом">
      <div class="conversation-status"><span class="status-dot"></span><span id="status" role="status">Готовий до розмови</span></div>
      <div id="messages" aria-live="polite" aria-relevant="additions text"><div class="welcome"><div class="welcome-icon">{icon('wave')}</div><h1>Я поруч.</h1><p>Про що поговоримо сьогодні?</p><div class="suggestions"><button data-prompt="Розкажи, що ти вмієш.">{icon('chat')}<span>Познайомимося<small>Можливості асистента</small></span></button><button data-prompt="Що ти зараз бачиш на камері?">{icon('camera')}<span>Подивись навколо<small>Поговоримо про побачене</small></span></button><button data-prompt="Що ти про мене знаєш?">{icon('memory')}<span>Що ти пам’ятаєш?<small>Мій особистий контекст</small></span></button></div></div></div>
      <div class="composer-area"><div id="heard" class="heard"></div><form id="chat" class="composer"><textarea id="text" rows="1" maxlength="2000" placeholder="Запитай або поділися думкою…" aria-label="Повідомлення" disabled></textarea><div class="composer-tools"><button id="ptt" type="button" class="ptt" disabled>Утримуй, щоб звернутися</button><span class="composer-spacer"></span><span class="key-hint">Enter ↵</span><button id="send" class="send-button" aria-label="Надіслати" title="Надіслати" disabled>{icon('arrow')}</button></div></form><p class="hint" id="inputHint">Кнопка перериває відповідь. Під час озвучування фонове слухання призупинене.</p></div>
    </main>
    <aside class="inspector" id="inspector" aria-label="Панель асистента"><div class="inspector-header"><h2>Асистент</h2><button id="closeInspector" class="icon-button" aria-label="Закрити панель асистента">{icon('close')}</button></div>
      <div class="tabs" role="tablist" aria-label="Розділи асистента"><button id="tab-context" role="tab" aria-selected="true" aria-controls="panel-context" data-panel="context">Огляд</button><button id="tab-voice" role="tab" aria-selected="false" aria-controls="panel-voice" data-panel="voice" tabindex="-1">Голос</button><button id="tab-memory" role="tab" aria-selected="false" aria-controls="panel-memory" data-panel="memory" tabindex="-1">Пам’ять</button></div>
      <div class="inspector-content">
        <section id="panel-context" role="tabpanel" aria-labelledby="tab-context"><div class="section-heading"><h3>Камера</h3><span class="tag">Локально</span></div><div class="preview"><video id="video" autoplay muted playsinline></video><div id="cameraPlaceholder">{icon('camera')}<span>Камера вимкнена</span><small>Увімкни, щоб я бачив оточення</small></div></div><div class="scene-description"><p id="scene">Поки немає спостережень.</p><small id="sceneTime"></small></div>{camera}<div class="divider"></div><h3>Поведінка</h3>{initiative}<div class="privacy-note">Медіа обробляються на цьому комп’ютері. Камера й мікрофон активні лише протягом сесії.</div></section>
        <section id="panel-voice" role="tabpanel" aria-labelledby="tab-voice" hidden><h3>Мікрофон</h3>{microphone}<div class="divider"></div><h3>Режим розмови</h3>{recognition}<div class="divider"></div><h3>Голос асистента</h3>{voice}<a class="text-link" href="/asr-test" target="_blank" rel="noopener">Перевірити розпізнавання голосу ↗</a></section>
        <section id="panel-memory" role="tabpanel" aria-labelledby="tab-memory" hidden><h3>Знайомство</h3><p class="muted">Допоможи мені краще тебе розуміти.</p>{onboarding}<div class="divider"></div><h3>Збережені факти</h3><p class="muted">Натисни факт, щоб виправити його.</p>{memory}<details class="memory-note"><summary>Як працює пам’ять</summary><p>Команди: «Запам’ятай тема: факт», «Забудь тема», «Що ти про мене знаєш». Видалення або виправлення факту очищає збережені підсумки, щоб старі дані не повернулися.</p></details><div class="divider"></div><h3>Підсумки розмов</h3><p class="muted">Оновлюються після чотирьох прямих повідомлень. Можуть містити неточності.</p><div id="summaries"></div></section>
      </div><footer class="inspector-footer"><span class="section-label">Система</span><div id="health">Перевіряю моделі…</div></footer>
    </aside>
  </div>
</div>
</div><div id="error" role="alert" hidden title="Натисни, щоб закрити"></div>
<dialog id="newChatDialog"><h2>Почати нову розмову?</h2><p>Поточну сесію буде завершено. Текст розмови зникне, а збережені факти й підсумки залишаться.</p><div class="dialog-actions"><button id="cancelNewChat" class="secondary">Скасувати</button><button id="confirmNewChat" class="primary">Нова розмова</button></div></dialog>
<script type="module" src="/static/app.js"></script><script type="module" src="/static/shell.js"></script>
</body></html>''', encoding='utf-8')
