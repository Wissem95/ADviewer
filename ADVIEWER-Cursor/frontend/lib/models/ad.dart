class Ad {
  final int id;
  final String title;
  final String description;
  final String videoUrl;
  final String thumbnailUrl;
  final String advertiserName;
  final String advertiserLogo;
  final int duration; // en secondes
  final int pointsReward;
  final bool hasQuiz;
  final String category;
  final DateTime createdAt;

  Ad({
    required this.id,
    required this.title,
    required this.description,
    required this.videoUrl,
    required this.thumbnailUrl,
    required this.advertiserName,
    required this.advertiserLogo,
    required this.duration,
    required this.pointsReward,
    required this.hasQuiz,
    required this.category,
    required this.createdAt,
  });

  factory Ad.fromJson(Map<String, dynamic> json) {
    return Ad(
      id: json['id'],
      title: json['title'] ?? '',
      description: json['description'] ?? '',
      videoUrl: json['video_url'] ?? '',
      thumbnailUrl: json['thumbnail_url'] ?? '',
      advertiserName: json['advertiser_name'] ?? '',
      advertiserLogo: json['advertiser_logo'] ?? '',
      duration: json['duration'] ?? 30,
      pointsReward: json['points_reward'] ?? 10,
      hasQuiz: json['has_quiz'] ?? false,
      category: json['category'] ?? '',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'video_url': videoUrl,
      'thumbnail_url': thumbnailUrl,
      'advertiser_name': advertiserName,
      'advertiser_logo': advertiserLogo,
      'duration': duration,
      'points_reward': pointsReward,
      'has_quiz': hasQuiz,
      'category': category,
      'created_at': createdAt.toIso8601String(),
    };
  }
} 