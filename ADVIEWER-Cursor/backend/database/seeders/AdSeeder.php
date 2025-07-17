<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use App\Models\Ad;
use App\Models\Quiz;

class AdSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        // Create sample ads with quizzes
        $ads = [
            [
                'title' => 'Nike - Just Do It',
                'description' => 'Nouvelle collection Nike Air Max',
                'video_url' => 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4',
                'duration' => 30,
                'thumbnail_url' => 'https://via.placeholder.com/640x360/007ACC/ffffff?text=Nike+Ad',
                'advertiser_name' => 'Nike',
                'advertiser_website' => 'https://www.nike.com',
                'category' => 'Sports',
                'points_reward' => 15,
                'budget' => 1000.00,
                'cost_per_view' => 0.05,
                'cost_per_completed_view' => 0.10,
                'remaining_budget' => 800.00,
                'start_date' => now()->subDays(7),
                'end_date' => now()->addDays(30),
                'target_countries' => ['FR', 'US', 'GB'],
                'target_languages' => ['fr', 'en'],
                'is_active' => true,
                'is_approved' => true,
                'quiz' => [
                    'question' => 'Quel est le slogan principal de Nike?',
                    'options' => ['Just Do It', 'Think Different', 'I\'m Lovin\' It', 'Have a Break'],
                    'correct_answer_index' => 0,
                    'explanation' => 'Le slogan emblématique de Nike est "Just Do It", créé en 1988.',
                    'difficulty' => 'easy',
                    'time_limit' => 30,
                    'points_reward' => 5,
                ],
            ],
            [
                'title' => 'McDonald\'s - Happy Meal',
                'description' => 'Découvrez les nouveaux jouets Happy Meal',
                'video_url' => 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_2mb.mp4',
                'duration' => 20,
                'thumbnail_url' => 'https://via.placeholder.com/640x360/FFC72C/ffffff?text=McDonald%27s+Ad',
                'advertiser_name' => 'McDonald\'s',
                'advertiser_website' => 'https://www.mcdonalds.com',
                'category' => 'Food & Beverage',
                'points_reward' => 12,
                'budget' => 800.00,
                'cost_per_view' => 0.04,
                'cost_per_completed_view' => 0.08,
                'remaining_budget' => 650.00,
                'start_date' => now()->subDays(5),
                'end_date' => now()->addDays(25),
                'target_countries' => ['FR', 'US', 'CA'],
                'target_languages' => ['fr', 'en'],
                'is_active' => true,
                'is_approved' => true,
                'quiz' => [
                    'question' => 'Quelle est la couleur principale du logo McDonald\'s?',
                    'options' => ['Rouge', 'Jaune', 'Bleu', 'Vert'],
                    'correct_answer_index' => 1,
                    'explanation' => 'Le logo McDonald\'s est principalement jaune avec les arches dorées.',
                    'difficulty' => 'easy',
                    'time_limit' => 25,
                    'points_reward' => 4,
                ],
            ],
            [
                'title' => 'Samsung Galaxy S24',
                'description' => 'Le nouveau smartphone Samsung Galaxy S24',
                'video_url' => 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_5mb.mp4',
                'duration' => 45,
                'thumbnail_url' => 'https://via.placeholder.com/640x360/1f1f1f/ffffff?text=Samsung+Galaxy',
                'advertiser_name' => 'Samsung',
                'advertiser_website' => 'https://www.samsung.com',
                'category' => 'Technology',
                'points_reward' => 20,
                'budget' => 1500.00,
                'cost_per_view' => 0.07,
                'cost_per_completed_view' => 0.15,
                'remaining_budget' => 1200.00,
                'start_date' => now()->subDays(3),
                'end_date' => now()->addDays(45),
                'target_countries' => ['FR', 'US', 'KR', 'GB'],
                'target_languages' => ['fr', 'en', 'ko'],
                'is_active' => true,
                'is_approved' => true,
                'quiz' => [
                    'question' => 'Quelle est la caractéristique principale mise en avant pour le Galaxy S24?',
                    'options' => ['Intelligence Artificielle', 'Appareil photo 200MP', 'Batterie 5000mAh', 'Écran pliable'],
                    'correct_answer_index' => 0,
                    'explanation' => 'Le Samsung Galaxy S24 met l\'accent sur les fonctionnalités d\'Intelligence Artificielle.',
                    'difficulty' => 'medium',
                    'time_limit' => 35,
                    'points_reward' => 8,
                ],
            ],
            [
                'title' => 'Coca-Cola - Share a Coke',
                'description' => 'Partagez un Coca-Cola avec vos amis',
                'video_url' => 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4',
                'duration' => 25,
                'thumbnail_url' => 'https://via.placeholder.com/640x360/FF0000/ffffff?text=Coca-Cola',
                'advertiser_name' => 'Coca-Cola',
                'advertiser_website' => 'https://www.coca-cola.com',
                'category' => 'Food & Beverage',
                'points_reward' => 10,
                'budget' => 600.00,
                'cost_per_view' => 0.03,
                'cost_per_completed_view' => 0.06,
                'remaining_budget' => 450.00,
                'start_date' => now()->subDays(10),
                'end_date' => now()->addDays(20),
                'target_countries' => ['FR', 'US', 'GB', 'ES'],
                'target_languages' => ['fr', 'en', 'es'],
                'is_active' => true,
                'is_approved' => true,
                'quiz' => [
                    'question' => 'En quelle année Coca-Cola a-t-il été inventé?',
                    'options' => ['1886', '1892', '1901', '1915'],
                    'correct_answer_index' => 0,
                    'explanation' => 'Coca-Cola a été inventé en 1886 par le pharmacien John Stith Pemberton.',
                    'difficulty' => 'medium',
                    'time_limit' => 30,
                    'points_reward' => 6,
                ],
            ],
            [
                'title' => 'Tesla Model 3',
                'description' => 'Découvrez la voiture électrique Tesla Model 3',
                'video_url' => 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_2mb.mp4',
                'duration' => 60,
                'thumbnail_url' => 'https://via.placeholder.com/640x360/000000/ffffff?text=Tesla+Model+3',
                'advertiser_name' => 'Tesla',
                'advertiser_website' => 'https://www.tesla.com',
                'category' => 'Automotive',
                'points_reward' => 25,
                'budget' => 2000.00,
                'cost_per_view' => 0.10,
                'cost_per_completed_view' => 0.20,
                'remaining_budget' => 1500.00,
                'start_date' => now()->subDays(1),
                'end_date' => now()->addDays(60),
                'target_countries' => ['FR', 'US', 'NO', 'NL'],
                'target_languages' => ['fr', 'en'],
                'is_active' => true,
                'is_approved' => true,
                'quiz' => [
                    'question' => 'Quelle est l\'autonomie maximale de la Tesla Model 3?',
                    'options' => ['350 km', '450 km', '550 km', '650 km'],
                    'correct_answer_index' => 2,
                    'explanation' => 'La Tesla Model 3 peut atteindre une autonomie d\'environ 550 km selon la version.',
                    'difficulty' => 'hard',
                    'time_limit' => 40,
                    'points_reward' => 10,
                ],
            ],
        ];

        foreach ($ads as $adData) {
            $quizData = $adData['quiz'];
            unset($adData['quiz']);

            // Create the ad
            $ad = Ad::create($adData);

            // Create the quiz for this ad
            $quiz = new Quiz($quizData);
            $quiz->ad_id = $ad->id;
            $quiz->save();

            echo "Created ad: {$ad->title} with quiz\n";
        }

        echo "Seeded " . count($ads) . " ads with quizzes\n";
    }
}
