const STORAGE_KEY = 'aol-live-language-preferences';
const languages = [
  { value: 'Bengali', label: 'Bengali · বাংলা', aliases: ['bengali', 'bangla', 'বাংলা', 'বাংলা ভাষা'] },
  { value: 'Hindi', label: 'Hindi · हिन्दी', aliases: ['hindi', 'हिंदी', 'हिन्दी'] },
  { value: 'Tamil', label: 'Tamil · தமிழ்', aliases: ['tamil', 'தமிழ்'] },
  { value: 'Malayalam', label: 'Malayalam · മലയാളം', aliases: ['malayalam', 'മലയാളം'] },
  { value: 'Kannada', label: 'Kannada · ಕನ್ನಡ', aliases: ['kannada', 'ಕನ್ನಡ'] },
  { value: 'Odia', label: 'Odia · ଓଡ଼ିଆ', aliases: ['odia', 'oriya', 'ଓଡ଼ିଆ'] },
  { value: 'Marathi', label: 'Marathi · मराठी', aliases: ['marathi', 'मराठी'] },
  { value: 'English', label: 'English', aliases: ['english', 'इंग्लिश', 'ஆங்கிலம்'] },
  { value: 'Other', label: 'Other', aliases: ['other'] },
];

const form = document.querySelector('#preferences-form');
const onboarding = document.querySelector('#onboarding');
const dashboard = document.querySelector('#dashboard');
const classroom = document.querySelector('#classroom');
const settingsDialog = document.querySelector('#settings-dialog');
const message = document.querySelector('#form-message');
const activeRecordings = new WeakMap();

for (const select of document.querySelectorAll('select')) {
  for (const language of languages) {
    const option = document.createElement('option');
    option.value = language.value;
    option.textContent = language.label;
    select.append(option);
  }
}

function readPreferences() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    const preferences = JSON.parse(stored);
    const validLanguages = languages.map(({ value }) => value);
    if (!validLanguages.includes(preferences.motherTongue) ||
        !validLanguages.includes(preferences.comfortableLanguage) ||
        !['voice', 'manual'].includes(preferences.interactionPreference)) return null;
    return {
      audioEnabled: true,
      subtitlesEnabled: true,
      darkMode: false,
      fontSize: 28,
      ...preferences,
    };
  } catch {
    return null;
  }
}

function savePreferences(preferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...preferences, updatedAt: new Date().toISOString() }));
    return true;
  } catch {
    return false;
  }
}

function applyTheme(darkMode) {
  document.body.dataset.theme = darkMode ? 'dark' : 'light';
  document.querySelector('#dark-mode').checked = darkMode;
}

function updateToggleButtons(preferences) {
  for (const button of document.querySelectorAll('[data-pref-toggle]')) {
    const key = button.dataset.prefToggle;
    const enabled = preferences[key];
    button.setAttribute('aria-pressed', String(enabled));
    const state = enabled ? 'On' : 'Off';
    const strong = button.querySelector('strong');
    if (strong) strong.textContent = state;
    const audioLabel = button.querySelector('.audio-control-label');
    const subtitleLabel = button.querySelector('.subtitle-control-label');
    if (audioLabel) audioLabel.textContent = `Audio ${state.toLowerCase()}`;
    if (subtitleLabel) subtitleLabel.textContent = `Subtitles ${state.toLowerCase()}`;
    if (button.classList.contains('icon-control')) {
      button.setAttribute('aria-label', `Turn ${key === 'audioEnabled' ? 'audio' : 'subtitles'} ${enabled ? 'off' : 'on'}`);
    }
  }
  document.querySelector('#transcript-panel')?.classList.toggle('subtitles-off', !preferences.subtitlesEnabled);
}

function displayDashboard(preferences) {
  const motherTongue = languages.find(({ value }) => value === preferences.motherTongue);
  const comfortable = languages.find(({ value }) => value === preferences.comfortableLanguage);
  document.querySelector('#dashboard-mother-tongue').textContent = motherTongue?.label || preferences.motherTongue;
  document.querySelector('#dashboard-comfortable-language').textContent = comfortable?.label || preferences.comfortableLanguage;
  document.querySelector('#classroom-language').textContent = comfortable?.label || preferences.comfortableLanguage;
  document.querySelector('#translation-language').textContent = comfortable?.label || preferences.comfortableLanguage;
  document.body.classList.toggle('voice-mode', preferences.interactionPreference === 'voice');
  applyTheme(preferences.darkMode);
  updateToggleButtons(preferences);
  document.documentElement.style.setProperty('--translation-size', `${preferences.fontSize}px`);
  onboarding.hidden = true;
  dashboard.hidden = false;
  classroom.hidden = true;
  document.querySelector('#settings-open').hidden = false;
  document.querySelector('.step-label').hidden = true;
  document.title = 'AOL Live | Student dashboard';
}

const existingPreferences = readPreferences();
if (existingPreferences) displayDashboard(existingPreferences);

document.querySelectorAll('input[name="interactionPreference"]').forEach((input) => {
  input.addEventListener('change', () => {
    document.body.classList.toggle('voice-mode', input.value === 'voice' && input.checked);
    message.textContent = '';
  });
});

function normalize(text) {
  return text.toLocaleLowerCase().normalize('NFKC').replace(/[.,!?。！？]/g, '').trim();
}

function findLanguage(transcript) {
  const normalized = normalize(transcript);
  const words = normalized.split(/\s+/);
  return languages.find((language) => language.aliases.some((alias) => {
    const normalizedAlias = normalize(alias);
    return normalizedAlias === normalized || words.includes(normalizedAlias);
  }));
}

function showVoiceMessage(fieldId, text) {
  document.querySelector(`#${fieldId}-result`).textContent = text;
}

async function startLocalRecognition(fieldId, button) {
  const stopRecording = activeRecordings.get(button);
  if (stopRecording) {
    stopRecording();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    showVoiceMessage(fieldId, 'Microphone recording is not available in this browser. Please choose a language manually.');
    return;
  }

  const defaultLabel = button.getAttribute('aria-label');
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  showVoiceMessage(fieldId, 'Requesting microphone access…');
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    const chunks = [];
    const label = button.querySelector('span');
    let stopTimer;
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size) chunks.push(event.data);
    });
    recorder.addEventListener('error', () => {
      stream.getTracks().forEach((track) => track.stop());
      activeRecordings.delete(button);
      button.disabled = false;
      button.removeAttribute('aria-busy');
      label.textContent = 'Speak';
      button.setAttribute('aria-label', defaultLabel);
      showVoiceMessage(fieldId, 'Microphone recording failed. Please choose a language manually.');
    });
    recorder.addEventListener('stop', async () => {
      clearTimeout(stopTimer);
      stream.getTracks().forEach((track) => track.stop());
      activeRecordings.delete(button);
      button.disabled = false;
      button.removeAttribute('aria-busy');
      label.textContent = 'Speak';
      button.setAttribute('aria-label', defaultLabel);
      if (!chunks.length) {
        showVoiceMessage(fieldId, 'No speech was recorded. Please choose a language manually.');
        return;
      }

      const recording = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      const extension = recording.type.includes('ogg') ? 'ogg' : recording.type.includes('mp4') ? 'mp4' : 'webm';
      const payload = new FormData();
      payload.append('audio', recording, `language-preference.${extension}`);
      showVoiceMessage(fieldId, 'Recognizing speech with the local service…');
      try {
        const response = await fetch('/api/speech/transcribe', { method: 'POST', body: payload });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Local speech recognition is unavailable.');
        const transcript = result.text?.trim();
        const match = transcript && findLanguage(transcript);
        if (!match) {
          showVoiceMessage(fieldId, `Heard “${transcript || ''}”, but couldn’t match a listed language. Please choose manually.`);
          return;
        }
        document.getElementById(fieldId).value = match.value;
        const uncertain = Number(result.language_probability) < 0.65;
        const prompt = uncertain ? 'This result may be uncertain.' : 'Please confirm this result.';
        showVoiceMessage(fieldId, `Heard “${transcript}”. ${prompt} ${match.label}. Your selection is not saved until you continue.`);
      } catch (error) {
        const detail = error instanceof Error ? error.message : 'Local speech recognition is unavailable.';
        showVoiceMessage(fieldId, `${detail} Please choose a language manually.`);
      }
    });

    recorder.start();
    button.disabled = false;
    button.querySelector('span').textContent = 'Stop';
    button.setAttribute('aria-label', `Stop speaking for ${fieldId === 'mother-tongue' ? 'your mother tongue' : 'your most comfortable language'}`);
    showVoiceMessage(fieldId, 'Listening on this device. Tap Stop when finished.');
    const stop = () => {
      if (recorder.state === 'recording') recorder.stop();
    };
    activeRecordings.set(button, stop);
    stopTimer = setTimeout(stop, 8000);
  } catch {
    stream?.getTracks().forEach((track) => track.stop());
    button.disabled = false;
    button.removeAttribute('aria-busy');
    showVoiceMessage(fieldId, 'Microphone access failed. Please choose a language manually.');
  }
}

document.querySelectorAll('[data-voice-for]').forEach((button) => {
  button.addEventListener('click', () => startLocalRecognition(button.dataset.voiceFor, button));
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const motherTongue = document.querySelector('#mother-tongue').value;
  const comfortableLanguage = document.querySelector('#comfortable-language').value;
  const interactionPreference = document.querySelector('input[name="interactionPreference"]:checked').value;
  if (!motherTongue || !comfortableLanguage) {
    message.textContent = 'Please answer both language questions before continuing.';
    (!motherTongue ? document.querySelector('#mother-tongue') : document.querySelector('#comfortable-language')).focus();
    return;
  }
  const preferences = { motherTongue, comfortableLanguage, interactionPreference, audioEnabled: true, subtitlesEnabled: true, darkMode: false, fontSize: 28 };
  if (!savePreferences(preferences)) {
    message.textContent = 'Preferences could not be saved on this device. Check browser storage settings and try again.';
    return;
  }
  displayDashboard(preferences);
});

function openSettings() {
  const preferences = readPreferences();
  if (!preferences) return;
  document.querySelector('#settings-mother-tongue').value = preferences.motherTongue;
  document.querySelector('#settings-comfortable-language').value = preferences.comfortableLanguage;
  document.querySelector(`input[name="settingsInteractionPreference"][value="${preferences.interactionPreference}"]`).checked = true;
  applyTheme(preferences.darkMode);
  document.querySelector('#settings-message').textContent = '';
  settingsDialog.showModal();
}

document.querySelector('#settings-open').addEventListener('click', openSettings);
document.querySelector('#dashboard-settings').addEventListener('click', openSettings);
document.querySelector('#change-language').addEventListener('click', openSettings);
document.querySelector('#settings-close').addEventListener('click', () => settingsDialog.close());
settingsDialog.addEventListener('click', (event) => {
  if (event.target === settingsDialog) settingsDialog.close();
});
document.querySelector('#dark-mode').addEventListener('change', (event) => applyTheme(event.target.checked));

document.querySelector('#settings-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const current = readPreferences();
  const preferences = {
    ...current,
    motherTongue: document.querySelector('#settings-mother-tongue').value,
    comfortableLanguage: document.querySelector('#settings-comfortable-language').value,
    interactionPreference: document.querySelector('input[name="settingsInteractionPreference"]:checked').value,
    darkMode: document.querySelector('#dark-mode').checked,
  };
  if (!savePreferences(preferences)) {
    document.querySelector('#settings-message').textContent = 'Settings could not be saved on this device. Check browser storage settings and try again.';
    return;
  }
  displayDashboard(preferences);
  settingsDialog.close();
});

for (const button of document.querySelectorAll('[data-pref-toggle]')) {
  button.addEventListener('click', () => {
    const preferences = readPreferences();
    const key = button.dataset.prefToggle;
    preferences[key] = !preferences[key];
    if (savePreferences(preferences)) updateToggleButtons(preferences);
  });
}

document.querySelector('#join-classroom').addEventListener('click', () => {
  dashboard.hidden = true;
  classroom.hidden = false;
  document.querySelector('#settings-open').hidden = false;
  document.querySelector('.step-label').hidden = true;
  document.title = 'AOL Live | Live classroom';
  document.querySelector('#classroom-error').textContent = 'Classroom service is not configured. No live session has been joined.';
  document.querySelector('#classroom-title').focus();
});

document.querySelector('#back-dashboard').addEventListener('click', () => {
  const preferences = readPreferences();
  if (preferences) displayDashboard(preferences);
});

let fontSize = existingPreferences?.fontSize || 28;
document.querySelector('#font-smaller').addEventListener('click', () => {
  fontSize = Math.max(20, fontSize - 2);
  document.documentElement.style.setProperty('--translation-size', `${fontSize}px`);
  const preferences = readPreferences();
  if (preferences) savePreferences({ ...preferences, fontSize });
});
document.querySelector('#font-larger').addEventListener('click', () => {
  fontSize = Math.min(42, fontSize + 2);
  document.documentElement.style.setProperty('--translation-size', `${fontSize}px`);
  const preferences = readPreferences();
  if (preferences) savePreferences({ ...preferences, fontSize });
});
document.querySelector('#volume').addEventListener('input', (event) => {
  document.querySelector('#volume-value').textContent = `${event.target.value}%`;
});