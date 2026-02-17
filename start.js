const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");

const isWindows = os.platform() === "win32";
const pythonCmd = "python";
const venvPython = isWindows ? "venv\\Scripts\\python.exe" : "venv/bin/python";
const venvPip = isWindows ? "venv\\Scripts\\pip.exe" : "venv/bin/pip";

const requirementsFile = "requirements.txt";
const mainScript = "aisoal.py";
const hashFile = ".reqhash";
const port = 5680;

let appProcess = null;

function killPort(port) {
  console.log(`🔍 Checking for processes on port ${port}...`);
  if (isWindows) {
    spawnSync(
      "cmd",
      [
        "/c",
        `for /f "tokens=5" %a in ('netstat -aon ^| find ":${port}" ^| find "LISTENING"') do taskkill /f /pid %a`,
      ],
      { stdio: "inherit" },
    );
  } else {
    spawnSync("bash", ["-c", `kill -9 $(lsof -t -i :${port} || echo "")`], {
      stdio: "inherit",
    });
  }
}

function killAppProcess() {
  if (appProcess && !appProcess.killed) {
    console.log("🛑 Killing previous Python process...");
    appProcess.kill();
  }
}

function ensureVirtualEnv() {
  if (!fs.existsSync(venvPython)) {
    console.log("⚙️ Creating virtual environment...");
    const result = spawnSync(pythonCmd, ["-m", "venv", "venv"], {
      stdio: "inherit",
    });
    if (result.status !== 0) {
      console.error("❌ Failed to create virtual environment");
      process.exit(result.status);
    }
  }
}

function checkAndInstallDependencies() {
  if (!fs.existsSync(requirementsFile)) {
    console.warn(
      `⚠️ Requirements file "${requirementsFile}" not found, skipping install`,
    );
    return;
  }

  const content = fs.readFileSync(requirementsFile, "utf8");
  const currentHash = crypto.createHash("sha256").update(content).digest("hex");
  const previousHash = fs.existsSync(hashFile)
    ? fs.readFileSync(hashFile, "utf8")
    : null;

  if (currentHash !== previousHash) {
    console.log("📦 Installing/updating dependencies...");
    const install = spawnSync(venvPip, ["install", "-r", requirementsFile], {
      stdio: "inherit",
    });
    if (install.status !== 0) {
      console.error("❌ Dependency installation failed");
      process.exit(install.status);
    }
    fs.writeFileSync(hashFile, currentHash);
  } else {
    console.log("✅ Dependencies are up-to-date.");
  }
}

function startApp() {
  killAppProcess();
  killPort(port);

  const startTime = new Date().toLocaleString();
  console.log(`🚀 Starting Python app at ${startTime}...`);

  appProcess = spawn(venvPython, [mainScript], {
    stdio: "inherit",
    detached: false,
  });

  appProcess.on("exit", (code, signal) => {
    console.log(`👋 App exited cleanly (code=${code}, signal=${signal})`);
  });
}

function main() {
  ensureVirtualEnv();
  checkAndInstallDependencies();
  startApp();
}

main();
