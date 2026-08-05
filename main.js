const { app, BrowserWindow, ipcMain, screen } = require('electron');

function createWindow () {
  const win = new BrowserWindow({
    width: 500,
    height: 800,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: false,       // frameless 視窗若可調大小，上緣會變 resize 把手、擋住往上拖曳
    maximizable: false,
    fullscreenable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, 
      webSecurity: false       
    }
  });
  win.loadFile('index.html');

  // 每 16ms：跟著游標移動視窗（拖曳中）＋ 送游標正規化座標給 renderer 做視線追蹤。
  // （renderer 端拿不到 electron.screen，只能由 main process 取全域游標。）
  let dragging = false;
  let dragOffset = { x: 0, y: 0 };
  let dragSize = { width: 0, height: 0 };
  const cursorTimer = setInterval(() => {
    if (win.isDestroyed()) return;
    const cur = screen.getCursorScreenPoint();
    if (dragging) {
      // 用 setBounds 並鎖定固定寬高，避免透明視窗在縮放環境下每次移動就長大 1px
      win.setBounds({ x: cur.x - dragOffset.x, y: cur.y - dragOffset.y, width: dragSize.width, height: dragSize.height });
    }
    const b = win.getContentBounds();
    const nx = (cur.x - b.x) / b.width * 2 - 1;
    const ny = -((cur.y - b.y) / b.height * 2 - 1);   // focusController 的 Y 是上正，需反轉螢幕座標
    win.webContents.send('cursor', { nx, ny });
  }, 16);
  win.on('closed', () => clearInterval(cursorTimer));

  // 手動拖曳（取代 -webkit-app-region: drag，讓滾輪/事件全視窗可用）
  ipcMain.on('drag-start', () => {
    const cur = screen.getCursorScreenPoint();
    const b = win.getBounds();
    dragOffset = { x: cur.x - b.x, y: cur.y - b.y };
    dragSize = { width: b.width, height: b.height };   // 鎖定拖曳期間的尺寸
    dragging = true;
  });
  ipcMain.on('drag-end', () => { dragging = false; });

  // 縮放視窗。resizable:false 的視窗 setSize 無法縮小到比初始還小，故 resize 時暫時解鎖。
  const doResize = (factor) => {
    if (win.isDestroyed()) return;
    const [w, h] = win.getSize();
    win.setResizable(true);
    win.setSize(Math.max(200, Math.round(w * factor)), Math.max(300, Math.round(h * factor)));
    win.setResizable(false);
  };
  ipcMain.on('resize-window', (_e, factor) => doResize(factor));
  // 備用：鍵盤 Ctrl + ↑/↓ 也能縮放（main 端攔截，不受焦點影響）
  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown' || !input.control) return;
    if (input.code === 'ArrowUp') { doResize(1.05); event.preventDefault(); }
    else if (input.code === 'ArrowDown') { doResize(0.95); event.preventDefault(); }
  });
}

app.commandLine.appendSwitch('log-level', '3');

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});