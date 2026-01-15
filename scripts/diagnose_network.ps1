<#
.SYNOPSIS
    Diagnostico de rede para problemas de HTTP/2 no DOU SnapTrack
.DESCRIPTION
    Coleta informacoes sobre o ambiente de rede do usuario para 
    identificar causas de ERR_HTTP2_PROTOCOL_ERROR
#>

param(
    [switch]$Verbose
)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  DOU SnapTrack - Diagnostico de Rede" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------
# 1. Informacoes do Sistema
# -----------------------------------------------------
Write-Host "[1/8] Sistema Operacional..." -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "  OS: $($os.Caption) - Build $($os.BuildNumber)"
Write-Host "  Arquitetura: $($env:PROCESSOR_ARCHITECTURE)"
Write-Host ""

# -----------------------------------------------------
# 2. Verificar Antivirus com Inspecao SSL
# -----------------------------------------------------
Write-Host "[2/8] Antivirus/Security Software..." -ForegroundColor Yellow

$avProducts = @()

# Windows Security Center (WMI)
$wmiAV = Get-CimInstance -Namespace "root\SecurityCenter2" -ClassName AntiVirusProduct 2>$null
if ($wmiAV) {
    foreach ($av in $wmiAV) {
        $avProducts += $av.displayName
        Write-Host "  Detectado: $($av.displayName)" -ForegroundColor White
    }
}

# Verificar processos conhecidos de AV com SSL inspection
$sslInspectors = @{
    "avp"          = "Kaspersky (ALTO RISCO - SSL Inspection)"
    "ekrn"         = "ESET (ALTO RISCO - SSL Inspection)"
    "avgnt"        = "Avira (medio risco)"
    "avguard"      = "Avira Guard"
    "bdagent"      = "Bitdefender (medio risco)"
    "avastsvc"     = "Avast (medio risco)"
    "ZSATunnel"    = "Zscaler (ALTO RISCO - Proxy corporativo)"
    "FortiClient"  = "FortiClient (ALTO RISCO - SSL Inspection)"
    "TaniumClient" = "Tanium (enterprise security)"
    "CSFalcon"     = "CrowdStrike Falcon"
}

$foundInspectors = @()
foreach ($procName in $sslInspectors.Keys) {
    $found = Get-Process -Name $procName -ErrorAction SilentlyContinue
    if ($found) {
        $foundInspectors += $sslInspectors[$procName]
        Write-Host "  [!] $($sslInspectors[$procName])" -ForegroundColor Red
    }
}

if ($foundInspectors.Count -eq 0) {
    Write-Host "  Nenhum software com SSL inspection conhecido detectado" -ForegroundColor Green
}
Write-Host ""

# -----------------------------------------------------
# 3. Verificar Proxy do Sistema
# -----------------------------------------------------
Write-Host "[3/8] Configuracao de Proxy..." -ForegroundColor Yellow

$proxyEnabled = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings").ProxyEnable
$proxyServer = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings").ProxyServer
$autoConfig = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings").AutoConfigURL

if ($proxyEnabled -eq 1) {
    Write-Host "  [!] Proxy HABILITADO: $proxyServer" -ForegroundColor Red
} else {
    Write-Host "  Proxy direto: Desabilitado" -ForegroundColor Green
}

if ($autoConfig) {
    Write-Host "  [!] PAC/AutoConfig: $autoConfig" -ForegroundColor Yellow
}

# Variaveis de ambiente de proxy
$envProxy = @($env:HTTP_PROXY, $env:HTTPS_PROXY, $env:ALL_PROXY) | Where-Object { $_ }
if ($envProxy) {
    Write-Host "  [!] Variaveis de proxy definidas: $($envProxy -join ', ')" -ForegroundColor Yellow
}
Write-Host ""

# -----------------------------------------------------
# 4. Verificar VPN
# -----------------------------------------------------
Write-Host "[4/8] Conexoes VPN..." -ForegroundColor Yellow

$vpnConnections = Get-VpnConnection -ErrorAction SilentlyContinue | Where-Object { $_.ConnectionStatus -eq 'Connected' }
if ($vpnConnections) {
    foreach ($vpn in $vpnConnections) {
        Write-Host "  [!] VPN ativa: $($vpn.Name)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Nenhuma VPN Windows conectada" -ForegroundColor Green
}

# Verificar adaptadores de VPN terceiros
$vpnAdapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { 
    $_.InterfaceDescription -match "VPN|Cisco|GlobalProtect|FortiClient|Zscaler|Tunnel"
}
if ($vpnAdapters) {
    foreach ($adapter in $vpnAdapters) {
        if ($adapter.Status -eq 'Up') {
            Write-Host "  [!] Adaptador VPN ativo: $($adapter.InterfaceDescription)" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# -----------------------------------------------------
# 5. Teste de Conectividade HTTP/2
# -----------------------------------------------------
Write-Host "[5/8] Teste de Conectividade aos Sites..." -ForegroundColor Yellow

$sites = @(
    @{ Name = "DOU (in.gov.br)"; URL = "https://www.in.gov.br" },
    @{ Name = "E-Agendas (cgu.gov.br)"; URL = "https://eagendas.cgu.gov.br" }
)

foreach ($site in $sites) {
    $testResult = $null
    try {
        $response = Invoke-WebRequest -Uri $site.URL -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 0 -ErrorAction Stop
        $testResult = "OK (HTTP $($response.StatusCode))"
        Write-Host "  [OK] $($site.Name): $testResult" -ForegroundColor Green
    }
    catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        if ($statusCode) {
            Write-Host "  [OK] $($site.Name): OK (HTTP $statusCode - redirect esperado)" -ForegroundColor Green
        } else {
            Write-Host "  [ERRO] $($site.Name): FALHOU - $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}
Write-Host ""

# -----------------------------------------------------
# 6. Verificar Versao do Chrome/Edge
# -----------------------------------------------------
Write-Host "[6/8] Versoes de Browser..." -ForegroundColor Yellow

$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$edgePaths = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)

$foundChrome = $false
foreach ($path in $chromePaths) {
    if (Test-Path $path) {
        $version = (Get-Item $path).VersionInfo.ProductVersion
        Write-Host "  Chrome: v$version" -ForegroundColor White
        $foundChrome = $true
        break
    }
}
if (-not $foundChrome) {
    Write-Host "  Chrome: Nao encontrado" -ForegroundColor Gray
}

$foundEdge = $false
foreach ($path in $edgePaths) {
    if (Test-Path $path) {
        $version = (Get-Item $path).VersionInfo.ProductVersion
        Write-Host "  Edge: v$version" -ForegroundColor White
        $foundEdge = $true
        break
    }
}
if (-not $foundEdge) {
    Write-Host "  Edge: Nao encontrado" -ForegroundColor Gray
}
Write-Host ""

# -----------------------------------------------------
# 7. Verificar Certificados Root Suspeitos
# -----------------------------------------------------
Write-Host "[7/8] Certificados Root (SSL Inspection)..." -ForegroundColor Yellow

$suspiciousCerts = @(
    "*Kaspersky*", "*ESET*", "*Avast*", "*Bitdefender*",
    "*Zscaler*", "*FortiGate*", "*BlueCoat*", "*Symantec*Class*",
    "*Corporate*", "*Enterprise*Root*", "*Proxy*"
)

$rootCerts = Get-ChildItem -Path Cert:\LocalMachine\Root -ErrorAction SilentlyContinue
$foundSuspicious = @()

foreach ($cert in $rootCerts) {
    foreach ($pattern in $suspiciousCerts) {
        if ($cert.Subject -like $pattern -or $cert.Issuer -like $pattern) {
            $foundSuspicious += $cert.Subject
        }
    }
}

if ($foundSuspicious.Count -gt 0) {
    Write-Host "  [!] Certificados de SSL Inspection detectados:" -ForegroundColor Red
    foreach ($cert in ($foundSuspicious | Select-Object -Unique)) {
        Write-Host "      - $cert" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Nenhum certificado de interceptacao SSL obvio encontrado" -ForegroundColor Green
}
Write-Host ""

# -----------------------------------------------------
# 8. Informacoes de Rede
# -----------------------------------------------------
Write-Host "[8/8] Configuracao de Rede..." -ForegroundColor Yellow

$activeAdapter = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notmatch 'Virtual|VPN|Loopback' } | Select-Object -First 1
if ($activeAdapter) {
    Write-Host "  Adaptador: $($activeAdapter.InterfaceDescription)"
    
    $ipConfig = Get-NetIPAddress -InterfaceIndex $activeAdapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    if ($ipConfig) {
        Write-Host "  IPv4: $($ipConfig.IPAddress)"
    }
    
    # MTU
    $mtu = (Get-NetIPInterface -InterfaceIndex $activeAdapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).NlMtu
    Write-Host "  MTU: $mtu"
    if ($mtu -and $mtu -lt 1400) {
        Write-Host "  [!] MTU baixo pode causar problemas com HTTP/2" -ForegroundColor Yellow
    }
}

# DNS
$dnsConfig = Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.ServerAddresses } | Select-Object -First 1
if ($dnsConfig) {
    Write-Host "  DNS: $($dnsConfig.ServerAddresses -join ', ')"
}
Write-Host ""

# -----------------------------------------------------
# Resumo e Recomendacoes
# -----------------------------------------------------
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  RESUMO E RECOMENDACOES" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

$issues = @()

if ($foundInspectors.Count -gt 0) {
    $issues += "ANTIVIRUS: Desabilitar temporariamente a inspecao SSL/HTTPS no antivirus"
}

if ($proxyEnabled -eq 1 -or $autoConfig) {
    $issues += "PROXY: Tentar com proxy desabilitado ou adicionar excecao para *.gov.br"
}

if ($vpnConnections -or $vpnAdapters) {
    $issues += "VPN: Testar com VPN desconectada se possivel"
}

if ($foundSuspicious.Count -gt 0) {
    $issues += "CERTIFICADOS: Certificados de interceptacao SSL detectados - provavel causa do problema"
}

if ($issues.Count -gt 0) {
    Write-Host "Possiveis causas do ERR_HTTP2_PROTOCOL_ERROR:" -ForegroundColor Yellow
    Write-Host ""
    $i = 1
    foreach ($issue in $issues) {
        Write-Host "  $i. $issue" -ForegroundColor White
        $i++
    }
} else {
    Write-Host "Nenhuma causa obvia detectada. O problema pode ser:" -ForegroundColor Green
    Write-Host "  - Firewall de rede (nao detectavel localmente)"
    Write-Host "  - Configuracao especifica do roteador/gateway"
    Write-Host "  - ISP fazendo deep packet inspection"
}

Write-Host ""
Write-Host "SOLUCAO APLICADA NO DOU SNAPTRACK:" -ForegroundColor Cyan
Write-Host "  O programa ja desabilita HTTP/2 e QUIC por padrao para evitar este erro."
Write-Host "  Se ainda ocorrer, verifique os itens acima." -ForegroundColor Gray
Write-Host ""
Write-Host "Para forcar HTTP/1.1, defina estas variaveis antes de executar:" -ForegroundColor Gray
Write-Host '  $env:DOU_DISABLE_HTTP2 = "1"' -ForegroundColor DarkGray
Write-Host '  $env:DOU_DISABLE_QUIC = "1"' -ForegroundColor DarkGray
Write-Host ""
