class WalletBalance {
  final Points points;
  final Money money;
  final Conversion conversion;
  final WalletStatistics statistics;

  WalletBalance({
    required this.points,
    required this.money,
    required this.conversion,
    required this.statistics,
  });

  factory WalletBalance.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return WalletBalance(
      points: Points.fromJson(data['points'] as Map<String, dynamic>),
      money: Money.fromJson(data['money'] as Map<String, dynamic>),
      conversion: Conversion.fromJson(data['conversion'] as Map<String, dynamic>),
      statistics: WalletStatistics.fromJson(data['statistics'] as Map<String, dynamic>),
    );
  }
}

class Points {
  final int currentBalance;
  final int totalEarned;
  final int totalConverted;
  final int availableForConversion;

  Points({
    required this.currentBalance,
    required this.totalEarned,
    required this.totalConverted,
    required this.availableForConversion,
  });

  factory Points.fromJson(Map<String, dynamic> json) {
    return Points(
      currentBalance: json['current_balance'] as int,
      totalEarned: json['total_earned'] as int,
      totalConverted: json['total_converted'] as int,
      availableForConversion: json['available_for_conversion'] as int,
    );
  }
}

class Money {
  final double currentBalance;
  final double totalEarned;
  final double totalWithdrawn;

  Money({
    required this.currentBalance,
    required this.totalEarned,
    required this.totalWithdrawn,
  });

  factory Money.fromJson(Map<String, dynamic> json) {
    return Money(
      currentBalance: (json['current_balance'] as num).toDouble(),
      totalEarned: (json['total_earned'] as num).toDouble(),
      totalWithdrawn: (json['total_withdrawn'] as num).toDouble(),
    );
  }

  String get formattedBalance => '€${currentBalance.toStringAsFixed(2)}';
  String get formattedTotalEarned => '€${totalEarned.toStringAsFixed(2)}';
  String get formattedTotalWithdrawn => '€${totalWithdrawn.toStringAsFixed(2)}';
}

class Conversion {
  final int rate;
  final String rateDisplay;
  final int minimumConversion;
  final double estimatedEuroValue;

  Conversion({
    required this.rate,
    required this.rateDisplay,
    required this.minimumConversion,
    required this.estimatedEuroValue,
  });

  factory Conversion.fromJson(Map<String, dynamic> json) {
    return Conversion(
      rate: json['rate'] as int,
      rateDisplay: json['rate_display'] as String,
      minimumConversion: json['minimum_conversion'] as int,
      estimatedEuroValue: (json['estimated_euro_value'] as num).toDouble(),
    );
  }

  String get formattedEstimatedValue => '€${estimatedEuroValue.toStringAsFixed(2)}';
}

class WalletStatistics {
  final int totalTransactions;
  final int level;
  final List<String> achievementsUnlocked;

  WalletStatistics({
    required this.totalTransactions,
    required this.level,
    required this.achievementsUnlocked,
  });

  factory WalletStatistics.fromJson(Map<String, dynamic> json) {
    return WalletStatistics(
      totalTransactions: json['total_transactions'] as int,
      level: json['level'] as int,
      achievementsUnlocked: List<String>.from(json['achievements_unlocked'] ?? []),
    );
  }
}

class Transaction {
  final int id;
  final String type;
  final String typeDisplay;
  final int? pointsAmount;
  final double? moneyAmount;
  final String status;
  final String description;
  final DateTime createdAt;
  final DateTime? completedAt;
  final double? pointsToEuroRate;

  Transaction({
    required this.id,
    required this.type,
    required this.typeDisplay,
    this.pointsAmount,
    this.moneyAmount,
    required this.status,
    required this.description,
    required this.createdAt,
    this.completedAt,
    this.pointsToEuroRate,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      id: json['id'] as int,
      type: json['type'] as String,
      typeDisplay: json['type_display'] as String,
      pointsAmount: json['points_amount'] as int?,
      moneyAmount: json['money_amount'] != null 
        ? (json['money_amount'] as num).toDouble() 
        : null,
      status: json['status'] as String,
      description: json['description'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      completedAt: json['completed_at'] != null 
        ? DateTime.parse(json['completed_at'] as String) 
        : null,
      pointsToEuroRate: json['points_to_euro_rate'] != null 
        ? (json['points_to_euro_rate'] as num).toDouble() 
        : null,
    );
  }

  String get formattedAmount {
    if (pointsAmount != null) {
      return '${pointsAmount! > 0 ? '+' : ''}${pointsAmount} points';
    } else if (moneyAmount != null) {
      return '${moneyAmount! > 0 ? '+' : ''}€${moneyAmount!.toStringAsFixed(2)}';
    }
    return '';
  }

  String get statusDisplayName {
    switch (status) {
      case 'completed':
        return 'Terminé';
      case 'pending':
        return 'En attente';
      case 'processing':
        return 'En cours';
      case 'failed':
        return 'Échoué';
      case 'cancelled':
        return 'Annulé';
      default:
        return status;
    }
  }
}

class WithdrawalMethod {
  final String id;
  final String name;
  final String description;
  final double minAmount;
  final double maxAmount;
  final String processingTime;
  final double feePercentage;
  final bool isAvailable;

  WithdrawalMethod({
    required this.id,
    required this.name,
    required this.description,
    required this.minAmount,
    required this.maxAmount,
    required this.processingTime,
    required this.feePercentage,
    required this.isAvailable,
  });

  factory WithdrawalMethod.fromJson(Map<String, dynamic> json) {
    return WithdrawalMethod(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String,
      minAmount: (json['min_amount'] as num).toDouble(),
      maxAmount: (json['max_amount'] as num).toDouble(),
      processingTime: json['processing_time'] as String,
      feePercentage: (json['fee_percentage'] as num).toDouble(),
      isAvailable: json['is_available'] as bool,
    );
  }
}

class ConversionResult {
  final int pointsConverted;
  final double euroReceived;
  final int conversionRate;
  final int newPointsBalance;
  final double newMoneyBalance;

  ConversionResult({
    required this.pointsConverted,
    required this.euroReceived,
    required this.conversionRate,
    required this.newPointsBalance,
    required this.newMoneyBalance,
  });

  factory ConversionResult.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return ConversionResult(
      pointsConverted: data['points_converted'] as int,
      euroReceived: (data['euro_received'] as num).toDouble(),
      conversionRate: data['conversion_rate'] as int,
      newPointsBalance: data['new_points_balance'] as int,
      newMoneyBalance: (data['new_money_balance'] as num).toDouble(),
    );
  }
} 