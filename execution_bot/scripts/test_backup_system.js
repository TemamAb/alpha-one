const fs = require('fs');
const path = require('path');
const http = require('http');

// Configuration
const TEST_PORT = 3000;
const BACKUP_DIR = path.join(__dirname, '../../backups');
const ENV_FILE = path.join(__dirname, '../../.env');

const mockEnvContent = `
# TEST CONFIGURATION ${Date.now()}
NODE_ENV=test
MAX_SLIPPAGE=0.02
TEST_VAR=true
`;

function testBackupSystem() {
    console.log("🧪 Starting Dashboard Backup System Test...");

    // 1. Prepare Request
    const options = {
        hostname: 'localhost',
        port: TEST_PORT,
        path: '/api/settings/upload-env',
        method: 'POST',
        headers: {
            'Content-Type': 'text/plain',
            'Content-Length': Buffer.byteLength(mockEnvContent)
        }
    };

    const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
            console.log(`\nResponse Status: ${res.statusCode}`);
            console.log(`Response Body: ${data}`);

            if (res.statusCode === 200) {
                verifyFilesystem();
            } else {
                console.error("❌ API Request Failed. Is the server running?");
                process.exit(1);
            }
        });
    });

    req.on('error', (e) => {
        console.error(`❌ Connection Error: ${e.message}`);
        console.log("ℹ️  Ensure server is running: 'node frontend/server-dashboard.js'");
    });

    // 2. Send Data
    req.write(mockEnvContent);
    req.end();
}

function verifyFilesystem() {
    console.log("\n🔍 Verifying Filesystem Artifacts...");
    
    // Check Backup Creation
    if (fs.existsSync(BACKUP_DIR)) {
        const files = fs.readdirSync(BACKUP_DIR);
        const recentBackup = files.find(f => f.startsWith('config_backup_'));
        if (recentBackup) {
            console.log(`✅ Backup verified: ${recentBackup}`);
            
            // Verify Content
            const currentEnv = fs.readFileSync(ENV_FILE, 'utf8');
            if (currentEnv === mockEnvContent) {
                console.log("✅ .env file successfully updated.");
            } else {
                console.error("❌ .env file content mismatch!");
            }
        } else {
            console.error("❌ No backup file found in backups directory.");
        }
    } else {
        console.error("❌ Backups directory not created.");
    }
}

// Run Test
testBackupSystem();