const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;

let mainWindow;
let pythonProcess;

// ------------------------------------------------------------------
// LANZAR SERVIDOR PYTHON
// ------------------------------------------------------------------

function startPythonServer() {
  const scriptPath = isDev
    ? path.join(__dirname, "../python/server.py")
    : path.join(process.resourcesPath, "python/server.py");

  // Rutas de Python a intentar en orden
  const pythonCandidates = [
    "/opt/anaconda3/bin/python3",       // Anaconda (tu caso)
    "/opt/homebrew/bin/python3",        // Homebrew Apple Silicon
    "/usr/local/bin/python3",           // Homebrew Intel
    "/usr/bin/python3",                 // macOS sistema
    "python3",                          // PATH genérico
  ];

  // Usar la primera que exista
  const fs = require("fs");
  let pythonBin = "python3";
  for (const candidate of pythonCandidates) {
    if (candidate === "python3" || fs.existsSync(candidate)) {
      pythonBin = candidate;
      break;
    }
  }

  console.log(`Lanzando Python: ${pythonBin} ${scriptPath}`);

  pythonProcess = spawn(pythonBin, [scriptPath], {
    stdio: ["pipe", "pipe", "pipe"],
    // Pasar el PATH de Anaconda para que encuentre las librerías
    env: {
      ...process.env,
      PATH: `/opt/anaconda3/bin:/opt/anaconda3/condabin:${process.env.PATH}`,
      PYTHONPATH: "",
    },
  });

  pythonProcess.stdout.on("data", (d) => console.log(`[Python] ${d.toString().trim()}`));
  pythonProcess.stderr.on("data", (d) => console.error(`[Python ERR] ${d.toString().trim()}`));
  pythonProcess.on("close", (code) => console.log(`Python terminado: código ${code}`));
  pythonProcess.on("error", (err) => console.error(`Python error: ${err.message}`));
}

// ------------------------------------------------------------------
// ESPERAR A QUE LA API ESTÉ LISTA
// ------------------------------------------------------------------

function waitForServer(url, retries = 30, delay = 500) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http.get(url, (res) => {
        if (res.statusCode === 200) resolve();
        else if (retries-- > 0) setTimeout(attempt, delay);
        else reject(new Error("Servidor Python no responde"));
      }).on("error", () => {
        if (retries-- > 0) setTimeout(attempt, delay);
        else reject(new Error("No se pudo conectar"));
      });
    };
    attempt();
  });
}

// ------------------------------------------------------------------
// VENTANA PRINCIPAL
// ------------------------------------------------------------------

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: "hiddenInset",
    backgroundColor: "#080c18",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
    show: false,
  });

  const startUrl = isDev
    ? "http://localhost:5173"
    : `file://${path.join(__dirname, "../dist-react/index.html")}`;

  mainWindow.loadURL(startUrl);
  mainWindow.once("ready-to-show", () => {
  mainWindow.show();
  mainWindow.webContents.openDevTools();
});
  mainWindow.on("closed", () => { mainWindow = null; });
}

// ------------------------------------------------------------------
// CICLO DE VIDA
// ------------------------------------------------------------------

app.whenReady().then(async () => {
  startPythonServer();

  try {
    await waitForServer("http://127.0.0.1:5050/status");
    console.log("Servidor Python listo ✓");
  } catch (err) {
    console.error("Advertencia:", err.message);
  }

  createWindow();
});

app.on("window-all-closed", () => {
  if (pythonProcess) pythonProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (mainWindow === null) createWindow();
});

app.on("before-quit", () => {
  if (pythonProcess) pythonProcess.kill();
});
