import http.server
import socketserver
import sys

PORT = int(sys.argv[1])
HTML = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SnapTrack DOU - Carregando...</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: \'Segoe UI\', Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #0b2545 0%, #13315c 50%, #134074 100%);
            color: white;
            overflow: hidden;
        }
        
        .container { text-align: center; padding: 40px; }
        
        .logo {
            font-size: 3em;
            font-weight: bold;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
            margin-bottom: 50px;
            font-weight: 300;
        }
        
        .plane-container {
            position: relative;
            width: 300px;
            height: 220px;
            margin: 0 auto 40px;
        }
        
        .plane-svg {
            width: 280px;
            height: 200px;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }
        
        .plane-outline {
            fill: rgba(255,255,255,0.12);
            stroke: rgba(255,255,255,0.4);
            stroke-width: 1;
        }
        
        .plane-fill {
            fill: #ffd700;
            clip-path: inset(0 100% 0 0);
            animation: fillPlane 3s ease-in-out infinite;
        }
        
        @keyframes fillPlane {
            0% { clip-path: inset(0 100% 0 0); }
            50% { clip-path: inset(0 0 0 0); }
            100% { clip-path: inset(0 100% 0 0); }
        }
        
        .plane-glow {
            fill: none;
            stroke: #ffd700;
            stroke-width: 2;
            opacity: 0;
            animation: glow 3s ease-in-out infinite;
        }
        
        @keyframes glow {
            0%, 100% { opacity: 0; }
            50% { opacity: 0.6; }
        }
        
        .trail {
            position: absolute;
            right: 5%;
            top: 50%;
            transform: translateY(-50%);
        }
        
        .trail-line {
            position: absolute;
            height: 5px;
            background: linear-gradient(90deg, rgba(255,215,0,0.8), transparent);
            border-radius: 3px;
            animation: trailMove 1.2s ease-out infinite;
        }
        
        .trail-line:nth-child(1) { width: 70px; top: -3px; }
        .trail-line:nth-child(2) { width: 50px; top: 8px; animation-delay: 0.2s; }
        
        @keyframes trailMove {
            0% { opacity: 0.9; transform: scaleX(1); }
            100% { opacity: 0; transform: scaleX(0.2); }
        }
        
        .progress-container { width: 300px; margin: 0 auto 30px; }
        
        .progress-bar {
            height: 6px;
            background: rgba(255,255,255,0.2);
            border-radius: 3px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #ffd700, #ffed4a, #ffd700);
            background-size: 200% 100%;
            width: 0%;
            border-radius: 3px;
            animation: progressMove 10s ease-out forwards, shimmer 1.5s linear infinite;
        }
        
        @keyframes progressMove {
            0% { width: 5%; }
            30% { width: 40%; }
            60% { width: 70%; }
            90% { width: 90%; }
            100% { width: 95%; }
        }
        
        @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        
        .status { font-size: 1.1em; opacity: 0.9; min-height: 1.5em; }
        .status-text { animation: pulse 2s ease-in-out infinite; }
        
        @keyframes pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
        
        .particles {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            pointer-events: none;
            overflow: hidden;
            z-index: -1;
        }
        
        .particle {
            position: absolute;
            width: 4px; height: 4px;
            background: rgba(255,255,255,0.3);
            border-radius: 50%;
            animation: float 15s linear infinite;
        }
        
        @keyframes float {
            0% { transform: translateY(100vh); opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { transform: translateY(-100vh); opacity: 0; }
        }
    </style>
</head>
<body>
    <div class="particles" id="particles"></div>
    
    <div class="container">
        <div class="logo">&#128240; SnapTrack DOU</div>
        <div class="subtitle">Diario Oficial da Uniao - Sistema de Monitoramento</div>
        
        <div class="plane-container">
            <div class="trail">
                <div class="trail-line"></div>
                <div class="trail-line"></div>
            </div>
            
            <!-- Aviao comercial top-down view - nariz para ESQUERDA, asas swept-back -->
            <svg class="plane-svg" viewBox="0 0 200 140">
                <!-- CONTORNO -->
                <!-- Fuselagem - cilindro longo e fino -->
                <ellipse class="plane-outline" cx="100" cy="70" rx="90" ry="8"/>
                
                <!-- Asa superior (swept back) - triangulo alongado -->
                <path class="plane-outline" d="
                    M 80 62
                    L 130 20
                    L 145 22
                    L 145 28
                    L 95 62
                    Z
                "/>
                
                <!-- Asa inferior (swept back) -->
                <path class="plane-outline" d="
                    M 80 78
                    L 130 120
                    L 145 118
                    L 145 112
                    L 95 78
                    Z
                "/>
                
                <!-- Estabilizador vertical (cauda - visto de cima eh fino) -->
                <rect class="plane-outline" x="175" y="68" width="15" height="4" rx="1"/>
                
                <!-- Estabilizador horizontal superior -->
                <path class="plane-outline" d="
                    M 170 66
                    L 185 55
                    L 190 56
                    L 178 66
                    Z
                "/>
                
                <!-- Estabilizador horizontal inferior -->
                <path class="plane-outline" d="
                    M 170 74
                    L 185 85
                    L 190 84
                    L 178 74
                    Z
                "/>
                
                <!-- Motor esquerdo -->
                <ellipse class="plane-outline" cx="105" cy="50" rx="12" ry="4"/>
                
                <!-- Motor direito -->
                <ellipse class="plane-outline" cx="105" cy="90" rx="12" ry="4"/>
                
                <!-- PREENCHIMENTO ANIMADO -->
                <ellipse class="plane-fill" cx="100" cy="70" rx="90" ry="8"/>
                
                <path class="plane-fill" d="
                    M 80 62
                    L 130 20
                    L 145 22
                    L 145 28
                    L 95 62
                    Z
                "/>
                
                <path class="plane-fill" d="
                    M 80 78
                    L 130 120
                    L 145 118
                    L 145 112
                    L 95 78
                    Z
                "/>
                
                <rect class="plane-fill" x="175" y="68" width="15" height="4" rx="1"/>
                
                <path class="plane-fill" d="M 170 66 L 185 55 L 190 56 L 178 66 Z"/>
                <path class="plane-fill" d="M 170 74 L 185 85 L 190 84 L 178 74 Z"/>
                
                <ellipse class="plane-fill" cx="105" cy="50" rx="12" ry="4"/>
                <ellipse class="plane-fill" cx="105" cy="90" rx="12" ry="4"/>
                
                <!-- BRILHO -->
                <ellipse class="plane-glow" cx="100" cy="70" rx="90" ry="8"/>
            </svg>
        </div>
        
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
        </div>
        
        <div class="status">
            <span class="status-text" id="status">Iniciando aplicacao...</span>
        </div>
    </div>
    
    <script>
        // Particulas
        const particles = document.getElementById(\'particles\');
        for (let i = 0; i < 15; i++) {
            const p = document.createElement(\'div\');
            p.className = \'particle\';
            p.style.left = Math.random() * 100 + \'%\';
            p.style.animationDelay = Math.random() * 15 + \'s\';
            p.style.animationDuration = (10 + Math.random() * 10) + \'s\';
            particles.appendChild(p);
        }
        
        // Mensagens rotativas
        const msgs = [\'Iniciando aplicacao...\', \'Carregando modulos...\', \'Preparando interface...\', \'Conectando servicos...\', \'Quase pronto...\'];
        let idx = 0;
        const statusEl = document.getElementById(\'status\');
        
        setInterval(() => {
            idx = (idx + 1) % msgs.length;
            statusEl.style.opacity = 0;
            setTimeout(() => { statusEl.textContent = msgs[idx]; statusEl.style.opacity = 1; }, 200);
        }, 2000);
        
        // Detectar porta - SE nao tiver porta configurada, nao tenta conectar
        const rawPort = \'8501\';
        const port = rawPort.includes(\'{{\') ? 0 : parseInt(rawPort);
        
        if (port > 0) {
            function check() {
                fetch(\'http://localhost:\' + port + \'/_stcore/health\')
                    .then(r => { if (r.ok) { statusEl.textContent = \'Pronto!\'; setTimeout(() => location.href = \'http://localhost:\' + port, 300); } else setTimeout(check, 300); })
                    .catch(() => setTimeout(check, 300));
            }
            setTimeout(check, 1000);
        }
    </script>
</body>
</html>
'''

class SplashHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(HTML.encode('utf-8'))

with socketserver.TCPServer(('127.0.0.1', PORT), SplashHandler) as httpd:
    httpd.handle_request()  # Serve apenas uma requisicao
