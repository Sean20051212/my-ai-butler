const { app, BrowserWindow } = require('electron');

function createWindow () {
  const win = new BrowserWindow({
    width: 400,
    height: 600,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, // 確保舊版 Node 整合順暢
      webSecurity: false       // 核心關鍵：允許 file:// 協議讀取本地模型檔案
    }
  });

  win.loadFile('index.html');

  // 啟動時自動彈出開發者工具 (DevTools)，這是桌機除錯必備！
  win.webContents.openDevTools({ mode: 'detach' });
}

// 抑制 Chromium 底層的煩人警告
app.commandLine.appendSwitch('log-level', '3');
//app.disableHardwareAcceleration();

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});