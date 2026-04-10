const { contextBridge } = require("electron");

// Exponemos una API segura al renderer si fuera necesario en el futuro
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
});
