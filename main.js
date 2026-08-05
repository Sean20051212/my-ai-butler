const { app, BrowserWindow, ipcMain } = require('electron');

function createWindow () {
  const win = new BrowserWindow({
    width: 500,
    height: 800,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: true,        // 除錯期間允許調整視窗大小，方便觀察模型
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