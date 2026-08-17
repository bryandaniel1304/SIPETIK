<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title') - SIPETIK</title>
    <link rel="icon" type="image/svg+xml" href="{{ asset('favicon.svg') }}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    @if (file_exists(public_path('hot')) || file_exists(public_path('build/manifest.json')))
        @vite(['resources/js/app.js'])
    @endif
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background-color: #f5f5f5;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        /* Sidebar */
        .sidebar {
            min-height: 100vh;
            background: linear-gradient(135deg, #2d5f47 0%, #3a7d5a 100%);
            color: white;
            padding: 30px 0;
            position: fixed;
            left: 0;
            top: 0;
            width: 250px;
            overflow-y: auto;
        }

        .sidebar .logo {
            padding: 0 20px 30px;
            font-size: 18px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .sidebar .logo i {
            font-size: 30px;
        }

        .sidebar .nav-menu {
            list-style: none;
        }

        .sidebar .nav-menu li {
            margin: 0;
        }

        .sidebar .nav-menu a {
            display: block;
            padding: 15px 20px;
            color: rgba(255, 255, 255, 0.8);
            text-decoration: none;
            transition: all 0.3s ease;
            border-left: 4px solid transparent;
        }

        .sidebar .nav-menu a:hover,
        .sidebar .nav-menu a.active {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border-left-color: #90ee90;
        }

        .sidebar .nav-menu a i {
            margin-right: 12px;
            width: 20px;
        }

        .sidebar .user-profile {
            position: absolute;
            bottom: 0;
            width: 100%;
            padding: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .sidebar .user-profile img {
            width: 40px;
            height: 40px;
            border-radius: 50%;
        }

        /* Main Content */
        .main-content {
            margin-left: 250px;
            padding: 30px;
            min-height: 100vh;
        }

        /* Splash Screen */
        #splash-screen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #2d5f47 0%, #3a7d5a 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            color: white;
            transition: opacity 0.8s ease, visibility 0.8s;
        }

        .splash-logo {
            font-size: 80px;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }

        .splash-text {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 2px;
        }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.8; }
            100% { transform: scale(1); opacity: 1; }
        }

        .hidden {
            opacity: 0;
            visibility: hidden;
        }

        /* Header */
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }

        .page-header h1 {
            font-size: 28px;
            font-weight: 400;
            color: #222;
            margin: 0;
        }

        .breadcrumb {
            font-size: 13px;
            color: #999;
            margin-top: 5px;
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .user-info .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #90ee90;
        }

        .user-info img {
            width: 45px;
            height: 45px;
            border-radius: 50%;
        }

        /* Cards */
        .metric-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            text-align: center;
            min-height: 178px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        /* Status icon colors */
        .status-icon {
            font-size: 36px;
            display: inline-block;
            line-height: 1;
            margin-bottom: 12px;
        }

        .status-icon.high {
            color: #ff4757; /* red for tinggi */
        }

        .status-icon.normal {
            color: #4caf50; /* green for normal */
        }

        .status-icon.low {
            color: #ffb300; /* yellow for rendah */
        }

        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
        }

        .metric-card .icon {
            font-size: 32px;
            margin-bottom: 15px;
        }

        .metric-card .label {
            font-size: 13px;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }

        .metric-card .value {
            font-size: 36px;
            font-weight: 700;
            color: #222;
            margin-bottom: 15px;
        }

        .metric-card .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            background: #e8f5e9;
            color: #3a7d5a;
        }

        .metric-card.alert-card {
            background: linear-gradient(135deg, #ff4757 0%, #ff6348 100%);
            color: white;
        }

        .metric-card.alert-card .label {
            color: rgba(255, 255, 255, 0.8);
        }

        .metric-card.alert-card .value {
            color: white;
        }

        #camera-confidence:empty,
        #camera-time:empty {
            display: none;
        }

        /* Chart */
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            margin-bottom: 30px;
        }

        .chart-container h5 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #222;
        }

        /* Tables */
        .table-container {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            margin-bottom: 30px;
        }

        .table-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            gap: 15px;
        }

        .table-controls input {
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            width: 250px;
        }

        .filter-btn {
            background: white;
            border: 1px solid #ddd;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .filter-btn:hover {
            background: #f5f5f5;
        }

        .badge-success {
            background: #4caf50;
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
        }

        .badge-warning {
            background: #ffb300;
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
        }

        .badge-danger {
            background: #ff4757;
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
        }

        /* Alerts Section */
        .alerts-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }

        .alerts-section h5 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #222;
        }

        .alert-item {
            background: #fff4e6;
            border-left: 4px solid #ffb300;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .alert-item i {
            font-size: 24px;
            color: #ff6b35;
        }

        .alert-item-text h6 {
            margin: 0 0 5px;
            font-weight: 600;
            color: #333;
        }

        .alert-item-text p {
            margin: 0;
            font-size: 13px;
            color: #666;
            line-height: 1.4;
        }

        /* Notification Settings */
        .settings-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            margin-bottom: 30px;
        }

        .settings-section h5 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #222;
        }

        .settings-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid #f0f0f0;
        }

        .settings-row:last-child {
            border-bottom: none;
        }

        .toggle-switch {
            width: 50px;
            height: 24px;
            background: #ddd;
            border-radius: 12px;
            cursor: pointer;
            position: relative;
            transition: background 0.3s;
        }

        .toggle-switch.active {
            background: #4caf50;
        }

        .toggle-switch::after {
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: left 0.3s;
        }

        .toggle-switch.active::after {
            left: 28px;
        }

        /* Buttons */
        .btn-primary-custom {
            background: #3a7d5a;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.3s;
        }

        .btn-primary-custom:hover {
            background: #2d5f47;
        }

        /* Pagination */
        .pagination-custom {
            display: flex;
            gap: 5px;
            justify-content: center;
            margin-top: 20px;
        }

        .pagination-custom a, .pagination-custom span {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
            color: #333;
        }

        .pagination-custom .active {
            background: #3a7d5a;
            color: white;
            border-color: #3a7d5a;
        }

        .pagination-custom a:hover {
            background: #f0f0f0;
        }

        /* Bootstrap Pagination Override */
        .pagination {
            display: flex !important;
            gap: 5px !important;
            justify-content: center !important;
            margin: 20px 0 !important;
            flex-wrap: wrap;
            padding: 0 !important;
        }

        .pagination .page-item {
            margin: 0 !important;
        }

        .pagination .page-link {
            padding: 8px 12px !important;
            border: 1px solid #ddd !important;
            border-radius: 4px !important;
            color: #333 !important;
            cursor: pointer;
            font-size: 14px !important;
            background: white !important;
            transition: all 0.3s;
            min-width: auto !important;
        }

        .pagination .page-link:hover {
            background: #f0f0f0 !important;
            color: #333 !important;
        }

        .pagination .active .page-link {
            background: #3a7d5a !important;
            color: white !important;
            border-color: #3a7d5a !important;
        }

        .pagination .page-item.disabled .page-link {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                width: 200px;
            }

            .main-content {
                margin-left: 200px;
                padding: 15px;
            }

            .metric-card .value {
                font-size: 28px;
            }

            .table-controls {
                flex-direction: column;
                align-items: stretch;
            }

            .table-controls input {
                width: 100%;
            }
        }

        /* Dark Mode */
        body.dark-mode {
            background-color: #1a1a1a;
            color: #e0e0e0;
        }

        body.dark-mode .sidebar {
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
        }

        body.dark-mode .main-content {
            background-color: #1a1a1a;
        }

        body.dark-mode .metric-card {
            background: #2d2d2d;
            color: #e0e0e0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        body.dark-mode .metric-card .label,
        body.dark-mode .metric-card h5 {
            color: #999;
        }

        body.dark-mode .metric-card .value {
            color: #e0e0e0;
        }

        body.dark-mode .chart-container {
            background: #2d2d2d;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        body.dark-mode .chart-container h5 {
            color: #e0e0e0;
        }

        body.dark-mode .alerts-section {
            background: #2d2d2d;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        body.dark-mode .alerts-section h5 {
            color: #e0e0e0;
        }

        body.dark-mode .alert-item {
            background: #3d3d2d;
            border-left-color: #ffb300;
        }

        body.dark-mode .alert-item-text h6 {
            color: #e0e0e0;
        }

        body.dark-mode .alert-item-text p {
            color: #999;
        }

        body.dark-mode .settings-section {
            background: #2d2d2d;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        body.dark-mode .settings-section h5 {
            color: #e0e0e0;
        }

        body.dark-mode .settings-row {
            border-bottom-color: #3d3d3d;
        }

        body.dark-mode .settings-row h6 {
            color: #e0e0e0;
        }

        body.dark-mode .settings-row p {
            color: #999;
        }

        body.dark-mode .table-container {
            background: #2d2d2d;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        body.dark-mode .table {
            color: #e0e0e0;
        }

        body.dark-mode table thead {
            background: #3d3d3d;
        }

        body.dark-mode table thead th {
            color: #e0e0e0;
            border-bottom-color: #4d4d4d;
        }

        body.dark-mode table tbody tr {
            border-bottom-color: #3d3d3d;
        }

        body.dark-mode table tbody td {
            color: #e0e0e0;
        }

        body.dark-mode .page-header h1 {
            color: #e0e0e0;
        }

        body.dark-mode .page-header .breadcrumb {
            color: #999;
        }

        body.dark-mode .filter-btn {
            background: #3d3d3d;
            border-color: #4d4d4d;
            color: #e0e0e0;
        }

        body.dark-mode .filter-btn:hover {
            background: #4d4d4d;
        }

        body.dark-mode input,
        body.dark-mode select,
        body.dark-mode textarea {
            background: #3d3d3d;
            color: #e0e0e0;
            border-color: #4d4d4d;
        }

        body.dark-mode input[type="text"]::placeholder,
        body.dark-mode input[type="email"]::placeholder {
            color: #666;
        }

        body.dark-mode #profileModal {
            background: rgba(0, 0, 0, 0.7);
        }

        body.dark-mode #profileModal > div {
            background: #2d2d2d;
            color: #e0e0e0;
        }

        body.dark-mode #editProfileModal {
            background: rgba(0, 0, 0, 0.7);
        }

        body.dark-mode #editProfileModal > div {
            background: #2d2d2d;
            color: #e0e0e0;
        }

        body.dark-mode label {
            color: #ccc;
        }

        body.dark-mode .btn-primary-custom {
            background: #4a9d6f;
        }

        body.dark-mode .btn-primary-custom:hover {
            background: #3a7d5a;
        }

        /* Dark Mode Text Colors */
        body.dark-mode p,
        body.dark-mode span,
        body.dark-mode a,
        body.dark-mode li,
        body.dark-mode div,
        body.dark-mode small,
        body.dark-mode td,
        body.dark-mode th {
            color: #ffffff;
        }

        body.dark-mode h1,
        body.dark-mode h2,
        body.dark-mode h3,
        body.dark-mode h4,
        body.dark-mode h5,
        body.dark-mode h6 {
            color: #ffffff;
        }

        body.dark-mode .description,
        body.dark-mode .text-muted {
            color: #aaa !important;
        }

        body.dark-mode .breadcrumb-item.active {
            color: #aaa;
        }

        body.dark-mode input::placeholder,
        body.dark-mode textarea::placeholder,
        body.dark-mode select option:not([selected]) {
            color: #888;
        }

        body.dark-mode input[type="text"],
        body.dark-mode input[type="email"],
        body.dark-mode input[type="date"],
        body.dark-mode input[type="number"],
        body.dark-mode textarea,
        body.dark-mode select {
            color: #ffffff !important;
            background: #3d3d3d !important;
            border-color: #4d4d4d !important;
        }

        body.dark-mode select option {
            background: #3d3d3d;
            color: #ffffff;
        }

        body.dark-mode .badge,
        body.dark-mode .badge-success,
        body.dark-mode .badge-warning,
        body.dark-mode .badge-danger {
            color: #ffffff;
        }

        body.dark-mode button,
        body.dark-mode .btn,
        body.dark-mode .btn-primary,
        body.dark-mode .btn-secondary,
        body.dark-mode .btn-success,
        body.dark-mode .btn-warning,
        body.dark-mode .btn-danger {
            color: #ffffff;
        }

        body.dark-mode .pagination a,
        body.dark-mode .pagination .page-link {
            color: #ffffff;
            background: #3d3d3d;
            border-color: #4d4d4d;
        }

        body.dark-mode .pagination .page-link:hover {
            color: #ffffff;
            background: #4d4d4d;
        }

        body.dark-mode .pagination .active .page-link {
            color: #ffffff;
            background: #3a7d5a;
            border-color: #3a7d5a;
        }

        body.dark-mode .table-controls {
            color: #ffffff;
        }

        body.dark-mode .table,
        body.dark-mode table {
            color: #ffffff;
            background: #2d2d2d;
        }

        body.dark-mode table thead th {
            color: #ffffff;
            background: #3d3d3d;
            border-bottom-color: #4d4d4d !important;
        }

        body.dark-mode table thead tr {
            background: #3d3d3d;
        }

        body.dark-mode table tbody tr {
            background: #2d2d2d;
            border-bottom-color: #3d3d3d !important;
        }

        body.dark-mode table tbody tr:hover {
            background: #3d3d3d;
        }

        body.dark-mode table tbody td {
            color: #ffffff;
            background: #2d2d2d;
            border-bottom-color: #3d3d3d !important;
        }

        body.dark-mode tbody tr[style*="background: white"] {
            background: #2d2d2d !important;
        }

        body.dark-mode tbody tr[style*="background:white"] {
            background: #2d2d2d !important;
        }

        body.dark-mode tbody tr[style*="background: #f9f9f9"] {
            background: #2d2d2d !important;
        }

        body.dark-mode tbody tr[style*="background:#f9f9f9"] {
            background: #2d2d2d !important;
        }

        body.dark-mode tbody tr[style*="background: #f5f5f5"] {
            background: #3d3d3d !important;
        }

        body.dark-mode tbody tr[style*="background:#f5f5f5"] {
            background: #3d3d3d !important;
        }

        body.dark-mode .modal-header {
            color: #ffffff;
            border-bottom-color: #4d4d4d;
        }

        body.dark-mode .modal-title {
            color: #ffffff;
        }

        body.dark-mode .modal-body {
            color: #ffffff;
        }

        body.dark-mode .modal-footer {
            border-top-color: #4d4d4d;
        }

        body.dark-mode .breadcrumb {
            color: #ffffff;
        }

        body.dark-mode .breadcrumb-item,
        body.dark-mode .breadcrumb-item.active {
            color: #ffffff;
        }

        body.dark-mode .breadcrumb-item::before {
            color: #aaa;
        }

        /* Override all inline styles in dark mode */
        body.dark-mode [style*="color: #666"] {
            color: #ffffff !important;
        }

        body.dark-mode [style*="color: #999"] {
            color: #aaa !important;
        }

        body.dark-mode [style*="color: #333"] {
            color: #ffffff !important;
        }

        body.dark-mode [style*="color:#666"] {
            color: #ffffff !important;
        }

        body.dark-mode [style*="color:#999"] {
            color: #aaa !important;
        }

        body.dark-mode [style*="color:#333"] {
            color: #ffffff !important;
        }

        body.dark-mode [style*="background: white"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background:white"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background: #f5f5f5"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background:#f5f5f5"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background: #eee"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background:#eee"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background: #f9f9f9"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background:#f9f9f9"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background: #f0f0f0"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="background:#f0f0f0"] {
            background: #3d3d3d !important;
        }

        body.dark-mode [style*="border: 1px solid #ddd"] {
            border: 1px solid #4d4d4d !important;
        }

        body.dark-mode [style*="border:1px solid #ddd"] {
            border: 1px solid #4d4d4d !important;
        }

        body.dark-mode [style*="border-bottom: 1px solid #eee"] {
            border-bottom: 1px solid #3d3d3d !important;
        }

        body.dark-mode [style*="border-bottom:1px solid #eee"] {
            border-bottom: 1px solid #3d3d3d !important;
        }

        body.dark-mode [style*="border-bottom: 2px solid #eee"] {
            border-bottom: 2px solid #3d3d3d !important;
        }

        body.dark-mode [style*="border-bottom:2px solid #eee"] {
            border-bottom: 2px solid #3d3d3d !important;
        }

        /* Checkbox styling in dark mode */
        body.dark-mode input[type="checkbox"] {
            appearance: none;
            -webkit-appearance: none;
            -moz-appearance: none;
            width: 18px;
            height: 18px;
            border: 2px solid #4d4d4d;
            border-radius: 3px;
            background: #3d3d3d;
            cursor: pointer;
            transition: all 0.3s;
        }

        body.dark-mode input[type="checkbox"]:checked {
            background: #3a7d5a;
            border-color: #3a7d5a;
        }

        body.dark-mode input[type="checkbox"]:checked::after {
            content: '✓';
            color: white;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Enhanced table styling for dark mode */
        body.dark-mode thead tr[style*="background: #f5f5f5"] {
            background: #3d3d3d !important;
        }

        body.dark-mode thead tr[style*="background:#f5f5f5"] {
            background: #3d3d3d !important;
        }

        body.dark-mode thead tr[style*="border-bottom: 2px solid #eee"] {
            border-bottom: 2px solid #3d3d3d !important;
        }

        body.dark-mode thead tr[style*="border-bottom:2px solid #eee"] {
            border-bottom: 2px solid #3d3d3d !important;
        }

        body.dark-mode tbody tr[style*="border-bottom: 1px solid #eee"] {
            border-bottom: 1px solid #3d3d3d !important;
            background: #2d2d2d !important;
        }

        body.dark-mode tbody tr[style*="border-bottom:1px solid #eee"] {
            border-bottom: 1px solid #3d3d3d !important;
            background: #2d2d2d !important;
        }

        body.dark-mode tbody td[style*="color: #333"] {
            color: #ffffff !important;
        }

        body.dark-mode tbody td[style*="color:#333"] {
            color: #ffffff !important;
        }

        body.dark-mode tbody th[style*="color: #333"] {
            color: #ffffff !important;
        }

        body.dark-mode tbody th[style*="color:#333"] {
            color: #ffffff !important;
        }
    </style>
</head>
<body>
    @if(session('show_splash'))
    <div id="splash-screen">
        <div class="splash-logo"><i class="fas fa-seedling"></i></div>
        <div class="splash-text">SIPETIK</div>
        <div class="mt-3">Memuat sistem...</div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                const splash = document.getElementById('splash-screen');
                if (splash) {
                    splash.classList.add('hidden');
                    setTimeout(() => splash.remove(), 800);
                }
            }, 2000);
        });
    </script>
    @endif

    <!-- Sidebar -->
    <aside class="sidebar">
        <div class="logo">
            <i class="fas fa-leaf"></i>
            <div>
                <div style="font-size: 20px; line-height: 1.1; letter-spacing: 0.5px;">SIPETIK</div>
            </div>
        </div>

        <ul class="nav-menu">
            <li>
                <a href="{{ route('app.dashboard') }}" class="@if(Route::currentRouteName() == 'app.dashboard') active @endif">
                    <i class="fas fa-home"></i> Dasbor
                </a>
            </li>
            <li>
                <a href="{{ route('app.sensor-data') }}" class="@if(Route::currentRouteName() == 'app.sensor-data') active @endif">
                    <i class="fas fa-database"></i> Data Sensor
                </a>
            </li>
            <li>
                <a href="{{ route('app.hama-alerts') }}" class="@if(Route::currentRouteName() == 'app.hama-alerts') active @endif">
                    <i class="fas fa-exclamation-triangle"></i> Peringatan Hama
                </a>
            </li>
            <li>
                <a href="{{ route('app.settings') }}" class="@if(Route::currentRouteName() == 'app.settings') active @endif">
                    <i class="fas fa-cog"></i> Pengaturan
                </a>
            </li>
        </ul>

        <div class="user-profile" onclick="showProfileModal()" style="cursor: pointer;">
            <img src="https://ui-avatars.com/api/?name={{ $user['name'] ?? 'Andi' }}&background=3a7d5a&color=fff" alt="User">
            <div>
                <div style="font-size: 13px; font-weight: 600;">{{ $user['name'] ?? 'Andi' }}</div>
                <div style="font-size: 11px; opacity: 0.8;">Lihat Profil</div>
            </div>
        </div>
    </aside>

    <!-- Main Content -->
    <div class="main-content">
        <!-- Page Header -->
        <div class="page-header">
            <div>
                <h1>@yield('page-title')</h1>
                <div class="breadcrumb">
                    @yield('breadcrumb')
                </div>
            </div>
            <div class="user-info">
                <span class="status-dot"></span>
                <span>{{ $user['name'] ?? 'Andi' }}</span>
                <img src="https://ui-avatars.com/api/?name={{ $user['name'] ?? 'Andi' }}&background=3a7d5a&color=fff" alt="User" style="width: 40px; height: 40px; border-radius: 50%; cursor: pointer;" onclick="showProfileModal()">
            </div>
        </div>

    <!-- Page Content -->
        @yield('content')
    </div>

    <!-- Profile Modal -->
    <div id="profileModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: white; padding: 40px; border-radius: 12px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
                <h3 style="margin: 0; font-size: 24px; font-weight: 600; color: #333;">Profil Saya</h3>
                <button onclick="closeProfileModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999;">&times;</button>
            </div>

            <div style="text-align: center; margin-bottom: 30px;">
                <img id="profileAvatar" src="https://ui-avatars.com/api/?name=Andi&background=3a7d5a&color=fff" alt="User" style="width: 100px; height: 100px; border-radius: 50%; margin-bottom: 15px;">
                <h4 id="profileName" style="margin: 10px 0; font-size: 20px; font-weight: 600; color: #333;">Loading...</h4>
                <p id="profileEmail" style="margin: 5px 0; color: #666; font-size: 14px;">Loading...</p>
            </div>

            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #999; text-transform: uppercase; margin-bottom: 5px;">Telepon</label>
                    <p id="profilePhone" style="margin: 0; color: #333;">-</p>
                </div>
                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #999; text-transform: uppercase; margin-bottom: 5px;">Alamat</label>
                    <p id="profileAddress" style="margin: 0; color: #333;">-</p>
                </div>
                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #999; text-transform: uppercase; margin-bottom: 5px;">Nama Kedai</label>
                    <p id="profileFarmName" style="margin: 0; color: #333;">-</p>
                </div>
                <div style="margin-bottom: 15px;">
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #999; text-transform: uppercase; margin-bottom: 5px;">Luas Lahan</label>
                    <p id="profileFarmArea" style="margin: 0; color: #333;">-</p>
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #999; text-transform: uppercase; margin-bottom: 5px;">Jenis Tanaman</label>
                    <p id="profileCropType" style="margin: 0; color: #333;">-</p>
                </div>
            </div>

            <div style="display: flex; gap: 10px;">
                <button onclick="showEditProfileModal()" style="flex: 1; background: #3a7d5a; color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.3s;" onmouseover="this.style.background='#2d5f47'" onmouseout="this.style.background='#3a7d5a';">Edit Profil</button>
                <button onclick="logoutUser()" style="flex: 1; background: #ff6b35; color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.3s;" onmouseover="this.style.background='#ff5722'" onmouseout="this.style.background='#ff6b35';">Keluar</button>
            </div>
        </div>
    </div>

    <!-- Edit Profile Modal -->
    <div id="editProfileModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: white; padding: 40px; border-radius: 12px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
                <h3 style="margin: 0; font-size: 24px; font-weight: 600; color: #333;">Edit Profil</h3>
                <button onclick="closeEditProfileModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999;">&times;</button>
            </div>

            <form id="editProfileForm" onsubmit="updateProfile(event)" style="display: flex; flex-direction: column; gap: 15px;">
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Nama</label>
                    <input type="text" id="editName" name="name" required placeholder="Nama Lengkap" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Email</label>
                    <input type="email" id="editEmail" name="email" required placeholder="Alamat Email" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Telepon</label>
                    <input type="text" id="editPhone" name="phone" placeholder="Nomor Telepon" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Alamat</label>
                    <input type="text" id="editAddress" name="address" placeholder="Alamat" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Nama Kedai</label>
                    <input type="text" id="editFarmName" name="farm_name" placeholder="Nama Kedai" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Luas Lahan</label>
                    <input type="text" id="editFarmArea" name="farm_area" placeholder="e.g., 2.5 Hektar" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 5px;">Jenis Tanaman</label>
                    <input type="text" id="editCropType" name="crop_type" placeholder="e.g., Padi" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; font-family: inherit;">
                </div>
                <div style="display: flex; gap: 10px;">
                    <button type="submit" style="flex: 1; background: #3a7d5a; color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.3s;" onmouseover="this.style.background='#2d5f47'" onmouseout="this.style.background='#3a7d5a';">Simpan Perubahan</button>
                    <button type="button" onclick="closeEditProfileModal()" style="flex: 1; background: #ddd; color: #333; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.3s;" onmouseover="this.style.background='#ccc'" onmouseout="this.style.background='#ddd';">Batal</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // Show profile modal
        function showProfileModal() {
            document.getElementById('profileModal').style.display = 'flex';
            loadProfileData();
        }

        // Close profile modal
        function closeProfileModal() {
            document.getElementById('profileModal').style.display = 'none';
        }

        // Show edit profile modal
        function showEditProfileModal() {
            closeProfileModal();
            document.getElementById('editProfileModal').style.display = 'flex';
            loadProfileDataForEdit();
        }

        // Close edit profile modal
        function closeEditProfileModal() {
            document.getElementById('editProfileModal').style.display = 'none';
        }

        // Load profile data
        function loadProfileData() {
            fetch('/profile/show')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('profileName').textContent = data.name || 'User';
                    document.getElementById('profileEmail').textContent = data.email || '';
                    document.getElementById('profilePhone').textContent = data.phone || '-';
                    document.getElementById('profileAddress').textContent = data.address || '-';
                    document.getElementById('profileFarmName').textContent = data.farm_name || '-';
                    document.getElementById('profileFarmArea').textContent = data.farm_area || '-';
                    document.getElementById('profileCropType').textContent = data.crop_type || '-';
                })
                .catch(error => console.error('Error:', error));
        }

        // Load profile data for edit form
        function loadProfileDataForEdit() {
            fetch('/profile/edit')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('editName').value = data.name || '';
                    document.getElementById('editEmail').value = data.email || '';
                    document.getElementById('editPhone').value = data.phone || '';
                    document.getElementById('editAddress').value = data.address || '';
                    document.getElementById('editFarmName').value = data.farm_name || '';
                    document.getElementById('editFarmArea').value = data.farm_area || '';
                    document.getElementById('editCropType').value = data.crop_type || '';
                })
                .catch(error => console.error('Error:', error));
        }

        // Update profile
        function updateProfile(event) {
            event.preventDefault();
            
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            const formData = {
                name: document.getElementById('editName').value,
                email: document.getElementById('editEmail').value,
                phone: document.getElementById('editPhone').value,
                address: document.getElementById('editAddress').value,
                farm_name: document.getElementById('editFarmName').value,
                farm_area: document.getElementById('editFarmArea').value,
                crop_type: document.getElementById('editCropType').value,
            };

            fetch('/profile/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfToken
                },
                body: JSON.stringify(formData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('Profile updated successfully!');
                    closeEditProfileModal();
                    // Reload page to reflect changes
                    location.reload();
                } else {
                    alert('Failed to update profile: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while updating profile');
            });
        }

        // Logout user
        function logoutUser() {
            if(confirm('Apakah Anda yakin ingin keluar?')) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = "{{ route('logout') }}";
                const token = document.createElement('input');
                token.type = 'hidden';
                token.name = '_token';
                token.value = "{{ csrf_token() }}";
                form.appendChild(token);
                document.body.appendChild(form);
                form.submit();
            }
        }

        // Close modals when clicking outside
        document.getElementById('profileModal').addEventListener('click', function(event) {
            if (event.target === this) {
                closeProfileModal();
            }
        });

        document.getElementById('editProfileModal').addEventListener('click', function(event) {
            if (event.target === this) {
                closeEditProfileModal();
            }
        });

        // Dark Mode Toggle
        function toggleDarkMode() {
            const body = document.body;
            body.classList.toggle('dark-mode');
            
            // Save preference to localStorage
            const isDarkMode = body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', isDarkMode);
            
            // Update toggle switch state in settings
            const toggleSwitch = document.querySelector('.toggle-switch[data-dark-mode]');
            if (toggleSwitch) {
                if (isDarkMode) {
                    toggleSwitch.classList.add('active');
                } else {
                    toggleSwitch.classList.remove('active');
                }
            }
        }

        // Apply dark mode on page load if previously enabled
        document.addEventListener('DOMContentLoaded', function() {
            const isDarkModeEnabled = localStorage.getItem('darkMode') === 'true';
            if (isDarkModeEnabled) {
                document.body.classList.add('dark-mode');
                const toggleSwitch = document.querySelector('.toggle-switch[data-dark-mode]');
                if (toggleSwitch) {
                    toggleSwitch.classList.add('active');
                }
            }
        });
    </script>
