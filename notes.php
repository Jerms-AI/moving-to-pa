<?php
// Tiny notes/ratings store for the live site, so notes sync across devices.
// GET  -> returns the saved notes JSON ({} if none)
// PUT/POST -> body is the full notes JSON; validated and saved (last write wins,
//             matching the local serve.py behavior).
// No auth by design (personal tool). Same-origin only is assumed.

header('Content-Type: application/json');
header('Cache-Control: no-store');

$file = __DIR__ . '/notes_data.json';
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'GET') {
    echo is_file($file) ? file_get_contents($file) : '{}';
    exit;
}

if ($method === 'PUT' || $method === 'POST') {
    $body = file_get_contents('php://input');
    if (strlen($body) > 1048576) {            // 1 MB cap
        http_response_code(413);
        echo '{"error":"too large"}';
        exit;
    }
    $data = json_decode($body, true);
    if (!is_array($data)) {                    // must be a JSON object/array
        http_response_code(400);
        echo '{"error":"invalid json"}';
        exit;
    }
    file_put_contents($file, $body, LOCK_EX);
    http_response_code(204);
    exit;
}

http_response_code(405);
echo '{"error":"method not allowed"}';
