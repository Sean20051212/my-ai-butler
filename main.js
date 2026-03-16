const { app, BrowserWindow, ipcMain } = require('electron');

function createWindow () {
  const win = new BrowserWindow({
    width: 400,
    height: 600,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: false,       
    maximizable: false,     
    fullscreenable: false,  
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, 
      webSecurity: false       
    }
  });
  win.loadFile('index.html');
  
}

app.commandLine.appendSwitch('log-level', '3');

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});