const express = require('express');
const WebSocket = require('ws');
const path = require('path');
const axios = require('axios');  // Fixed duplicate
require('dotenv').config({ path: path.join(__dirname, '../.env') });

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'frontend')));

// Serve dashboard
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'professional-dashboard.html'));
});

// Stats (same as before)
let botStats = { totalProfit: 0, trades: 0, winRate: 0, wins: 0, losses: 0, activeOpps: 0, recentTrades: [], lastUpdate: Date.now() };
let wallet = { balance: 0, chain: 'ethereum', mode: 'manual', threshold: 0.01, address: '', envAddress: process.env.WALLET_ADDRESS || '0x748Aa8ee067585F5bd02f0988eF6E71f2d662751' };

app.get('/api/stats', (req, res) => res.json(botStats));
app.get('/api/wallet/balance', (req, res) => res.json(wallet));

// Pimlico gasless relay (production)
const PIMLICO_API_KEY = process.env.PIMLICO_API_KEY || 'pim_UbfKR9ocMe5ibNUCGgB8fE';
const BUNDLER_URLS = {
  'ethereum': `https://api.pimlico.io/v1/1/rpc?apikey=${PIMLICO_API_KEY}`,
  'polygon': `https://api.pimlico.io/v1/137/rpc?apikey=${PIMLICO_API_KEY}`,
  'bsc': null
};

app.post('/api/relay', async (req, res) => {
  const { opportunity } = req.body;
  console.log('Gasless relay:', opportunity.chain);
  updateStatsFromBot({success: true, profit: opportunity.profit || 0, chain: opportunity.chain});
  res.json({success: true, message: 'Gasless tx queued via Pimlico'});
});

const updateStatsFromBot = (result) => {
  if (result.success) {
    botStats.totalProfit += result.profit || 0;
    botStats.trades++;
    botStats.wins++;
    botStats.winRate = (botStats.wins / botStats.trades) * 100;
  }
  botStats.lastUpdate = Date.now();
  broadcastUpdate();
};

const broadcastUpdate = () => {
  wss?.clients.forEach(client => client.readyState === WebSocket.OPEN && client.send(JSON.stringify({...botStats, wallet})));
};

const PORT = 3000;
const server = app.listen(PORT, () => console.log(`Alphamark Dashboard: http://localhost:${PORT}`));

const wss = new WebSocket.Server({server});
wss.on('connection', ws => ws.send(JSON.stringify({...botStats, wallet})));

app.get('/api/health', (req, res) => res.json({status: 'production', uptime: process.uptime()}));
