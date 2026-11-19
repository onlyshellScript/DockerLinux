// preload/index.js: puente seguro renderer-proceso principal.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sigos', {
  getHealth: () => ipcRenderer.invoke('sigos:get-health'),
  getApiBaseUrl: () => ipcRenderer.invoke('sigos:get-api-base-url'),
  openApp: () => ipcRenderer.invoke('sigos:open-app'),
  apiRequest: (payload) => ipcRenderer.invoke('sigos:api-request', payload),
  uploadFile: (payload) => ipcRenderer.invoke('sigos:upload-file', payload),
  downloadFile: (payload) => ipcRenderer.invoke('sigos:download-file', payload),
  loadSession: () => ipcRenderer.invoke('sigos:session:load'),
  saveSession: (session) => ipcRenderer.invoke('sigos:session:save', session),
  clearSession: () => ipcRenderer.invoke('sigos:session:clear'),
  endSession: (payload) => ipcRenderer.invoke('sigos:session:end', payload),
  saveFile: (payload) => ipcRenderer.invoke('sigos:save-file', payload),
  openFolder: (folderPath) => ipcRenderer.invoke('sigos:open-folder', folderPath),
  exportDownload: (payload) => ipcRenderer.invoke('sigos:export-download', payload),
  apiBinary: (payload) => ipcRenderer.invoke('sigos:api-binary', payload),
  getPrefs: () => ipcRenderer.invoke('sigos:prefs:get'),
  setPrefs: (patch) => ipcRenderer.invoke('sigos:prefs:set', patch),
});
