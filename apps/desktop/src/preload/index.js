const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sigos', {
  getHealth: () => ipcRenderer.invoke('sigos:get-health'),
  apiRequest: (payload) => ipcRenderer.invoke('sigos:api-request', payload),
  loadSession: () => ipcRenderer.invoke('sigos:session:load'),
  saveSession: (session) => ipcRenderer.invoke('sigos:session:save', session),
  clearSession: () => ipcRenderer.invoke('sigos:session:clear'),
});
