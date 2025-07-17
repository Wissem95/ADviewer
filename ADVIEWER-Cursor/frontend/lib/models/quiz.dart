class Quiz {
  final int id;
  final String question;
  final List<String> options;
  final String difficulty;
  final int timeLimit;
  final int pointsReward;
  final String? explanation;
  final int? correctAnswerIndex; // Only shown after answering
  final int attemptsRemaining;

  Quiz({
    required this.id,
    required this.question,
    required this.options,
    required this.difficulty,
    required this.timeLimit,
    required this.pointsReward,
    this.explanation,
    this.correctAnswerIndex,
    required this.attemptsRemaining,
  });

  factory Quiz.fromJson(Map<String, dynamic> json) {
    return Quiz(
      id: json['id'] as int,
      question: json['question'] as String,
      options: List<String>.from(json['options'] ?? []),
      difficulty: json['difficulty'] as String,
      timeLimit: json['time_limit'] as int,
      pointsReward: json['points_reward'] as int,
      explanation: json['explanation'] as String?,
      correctAnswerIndex: json['correct_answer_index'] as int?,
      attemptsRemaining: json['attempts_remaining'] ?? 3,
    );
  }

  String get difficultyDisplayName {
    switch (difficulty) {
      case 'easy':
        return 'Facile';
      case 'medium':
        return 'Moyen';
      case 'hard':
        return 'Difficile';
      default:
        return difficulty;
    }
  }

  String get timeDisplayText {
    if (timeLimit < 60) {
      return '${timeLimit}s';
    } else {
      final minutes = timeLimit ~/ 60;
      final seconds = timeLimit % 60;
      if (seconds == 0) {
        return '${minutes}min';
      }
      return '${minutes}min ${seconds}s';
    }
  }
}

class QuizAnswer {
  final int answerIndex;
  final double timeTaken;
  final bool isCorrect;
  final DateTime attemptedAt;

  QuizAnswer({
    required this.answerIndex,
    required this.timeTaken,
    required this.isCorrect,
    required this.attemptedAt,
  });

  factory QuizAnswer.fromJson(Map<String, dynamic> json) {
    return QuizAnswer(
      answerIndex: json['answer_index'] as int,
      timeTaken: (json['time_taken'] as num).toDouble(),
      isCorrect: json['is_correct'] as bool,
      attemptedAt: DateTime.parse(json['attempted_at'] as String),
    );
  }
}

class QuizResult {
  final bool isCorrect;
  final int correctAnswerIndex;
  final String? explanation;
  final int pointsEarned;
  final int totalPoints;
  final int attemptsRemaining;

  QuizResult({
    required this.isCorrect,
    required this.correctAnswerIndex,
    this.explanation,
    required this.pointsEarned,
    required this.totalPoints,
    required this.attemptsRemaining,
  });

  factory QuizResult.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return QuizResult(
      isCorrect: data['is_correct'] as bool,
      correctAnswerIndex: data['correct_answer_index'] as int,
      explanation: data['explanation'] as String?,
      pointsEarned: data['points_earned'] as int,
      totalPoints: data['total_points'] as int,
      attemptsRemaining: data['attempts_remaining'] as int,
    );
  }
}

class QuizStats {
  final int totalQuizzesAttempted;
  final int quizzesPassed;
  final double successRate;
  final int totalQuizPoints;

  QuizStats({
    required this.totalQuizzesAttempted,
    required this.quizzesPassed,
    required this.successRate,
    required this.totalQuizPoints,
  });

  factory QuizStats.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return QuizStats(
      totalQuizzesAttempted: data['total_quizzes_attempted'] as int,
      quizzesPassed: data['quizzes_passed'] as int,
      successRate: (data['success_rate'] as num).toDouble(),
      totalQuizPoints: data['total_quiz_points'] as int,
    );
  }
} 