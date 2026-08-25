<?php

use Illuminate\Foundation\Application;
use Illuminate\Http\Request;

define('LARAVEL_START', microtime(true));

// Register the Composer autoloader...
require __DIR__.'/../vendor/autoload.php';

// Bootstrap Laravel and handle the request...
// (Vercel invokes files under /api as serverless functions, so this mirrors
// public/index.php one directory level up. Writable paths — cache, compiled
// views, sessions, logs — are redirected to /tmp via env vars in vercel.json,
// since Vercel's function filesystem is read-only outside of /tmp.)
/** @var Application $app */
$app = require_once __DIR__.'/../bootstrap/app.php';

$app->handleRequest(Request::capture());
