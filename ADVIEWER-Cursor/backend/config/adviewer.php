<?php

return [
    /*
    |--------------------------------------------------------------------------
    | AdViewer Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration for the AdViewer application including points system,
    | rewards, and conversion rates.
    |
    */

    'points_to_euro_rate' => env('POINTS_TO_EURO_RATE', 100), // 100 points = 1 euro

    'rewards' => [
        'ad_viewing' => env('AD_VIEWING_POINTS', 10), // Points per completed ad
        'quiz_correct' => env('QUIZ_CORRECT_POINTS', 5), // Additional points for correct quiz answer
        'referral_bonus' => env('REFERRAL_BONUS_POINTS', 50), // Points for successful referral
        'daily_login' => env('DAILY_LOGIN_POINTS', 5), // Points for daily login
    ],

    'limits' => [
        'daily_ad_views' => env('MAX_DAILY_AD_VIEWS', 50),
        'daily_points_conversion' => env('MAX_DAILY_POINTS_CONVERSION', 500),
        'quiz_attempts_per_ad' => env('MAX_QUIZ_ATTEMPTS', 3),
        'min_conversion_points' => env('MIN_CONVERSION_POINTS', 50),
        'max_conversion_points' => env('MAX_CONVERSION_POINTS', 10000),
    ],

    'withdrawal' => [
        'min_amount' => env('MIN_WITHDRAWAL_AMOUNT', 5.00),
        'max_amount' => env('MAX_WITHDRAWAL_AMOUNT', 1000.00),
        'methods' => [
            'paypal' => [
                'enabled' => env('PAYPAL_ENABLED', true),
                'fee_percentage' => env('PAYPAL_FEE', 0.0),
                'processing_days' => '1-3',
            ],
            'bank_transfer' => [
                'enabled' => env('BANK_TRANSFER_ENABLED', true),
                'fee_percentage' => env('BANK_TRANSFER_FEE', 0.0),
                'processing_days' => '3-5',
            ],
            'crypto' => [
                'enabled' => env('CRYPTO_ENABLED', false),
                'fee_percentage' => env('CRYPTO_FEE', 1.0),
                'processing_days' => '1-24 heures',
            ],
        ],
    ],

    'anti_fraud' => [
        'max_session_duration' => env('MAX_SESSION_DURATION', 240), // minutes
        'suspicious_viewing_rate' => env('SUSPICIOUS_VIEWING_RATE', 2.0), // ads per minute
        'ip_change_threshold' => env('IP_CHANGE_THRESHOLD', 3), // changes per day
        'device_change_threshold' => env('DEVICE_CHANGE_THRESHOLD', 2), // changes per day
    ],

    'levels' => [
        'points_per_level' => env('POINTS_PER_LEVEL', 1000),
        'max_level' => env('MAX_LEVEL', 100),
        'level_bonuses' => [
            10 => 100, // Level 10: 100 bonus points
            25 => 250, // Level 25: 250 bonus points
            50 => 500, // Level 50: 500 bonus points
            75 => 750, // Level 75: 750 bonus points
            100 => 1000, // Level 100: 1000 bonus points
        ],
    ],

    'achievements' => [
        'first_100_points' => [
            'threshold' => 100,
            'reward' => 10,
            'title' => 'Premier 100 points',
            'description' => 'Gagnez vos premiers 100 points',
        ],
        'collector' => [
            'threshold' => 500,
            'reward' => 25,
            'title' => 'Collectionneur',
            'description' => 'Accumulez 500 points',
        ],
        'expert' => [
            'threshold' => 1000,
            'reward' => 50,
            'title' => 'Expert',
            'description' => 'Atteignez 1000 points',
        ],
        'master' => [
            'threshold' => 5000,
            'reward' => 100,
            'title' => 'Maître',
            'description' => 'Devenez un maître avec 5000 points',
        ],
        'first_conversion' => [
            'threshold' => 1,
            'reward' => 20,
            'title' => 'Première conversion',
            'description' => 'Convertissez vos premiers points en argent',
        ],
        'regular_converter' => [
            'threshold' => 5,
            'reward' => 50,
            'title' => 'Convertisseur régulier',
            'description' => 'Effectuez 5 conversions',
        ],
    ],
];
