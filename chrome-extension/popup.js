document.querySelector('#connect').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
  const status = document.querySelector('#status');
  try {
    if (!tab?.url || new URL(tab.url).hostname !== 'shopee.co.id') throw new Error('Aktifkan tab shopee.co.id terlebih dahulu.');
    const token = document.querySelector('#token').value.trim();
    if (token.length < 32) throw new Error('Salin kode pairing dari dashboard.');
    const result = await chrome.runtime.sendMessage({type:'connect', tabId:tab.id, token});
    status.textContent = result.error || 'Terhubung. Kembali ke dashboard dan klik Periksa login.';
    if (!result.error) document.querySelector('#token').value = '';
  } catch (error) { status.textContent = error.message; }
});
document.querySelector('#disconnect').addEventListener('click', async () => {
  await chrome.runtime.sendMessage({type:'disconnect'});
  document.querySelector('#status').textContent = 'Koneksi diputus. Tab Shopee tetap terbuka.';
});
