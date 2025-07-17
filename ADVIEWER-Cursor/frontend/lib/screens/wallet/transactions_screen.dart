import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/wallet.dart';
import '../../services/api_service.dart';

class TransactionsScreen extends ConsumerStatefulWidget {
  const TransactionsScreen({super.key});

  @override
  ConsumerState<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends ConsumerState<TransactionsScreen> {
  List<Transaction> transactions = [];
  bool isLoading = true;
  bool isLoadingMore = false;
  String? error;
  String? selectedType;
  int currentPage = 1;
  bool hasMoreData = true;

  final ScrollController _scrollController = ScrollController();

  final Map<String, String> transactionTypes = {
    'points_earned': 'Points gagnés',
    'points_converted': 'Points convertis',
    'withdrawal': 'Retraits',
    'referral_bonus': 'Bonus parrainage',
  };

  @override
  void initState() {
    super.initState();
    _loadTransactions();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= 
        _scrollController.position.maxScrollExtent - 200) {
      _loadMoreTransactions();
    }
  }

  Future<void> _loadTransactions({bool refresh = false}) async {
    try {
      setState(() {
        if (refresh) {
          isLoading = true;
          currentPage = 1;
          hasMoreData = true;
        }
        error = null;
      });

      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.getTransactions(
        type: selectedType,
        page: currentPage,
        perPage: 20,
      );

      final newTransactions = (response['data']['transactions'] as List)
          .map((json) => Transaction.fromJson(json))
          .toList();

      setState(() {
        if (refresh) {
          transactions = newTransactions;
        } else {
          transactions.addAll(newTransactions);
        }
        
        final pagination = response['data']['pagination'];
        hasMoreData = currentPage < pagination['last_page'];
        
        isLoading = false;
        isLoadingMore = false;
      });
    } catch (e) {
      setState(() {
        error = e.toString();
        isLoading = false;
        isLoadingMore = false;
      });
    }
  }

  Future<void> _loadMoreTransactions() async {
    if (isLoadingMore || !hasMoreData) return;

    setState(() {
      isLoadingMore = true;
      currentPage++;
    });

    await _loadTransactions();
  }

  void _onFilterChanged(String? type) {
    setState(() {
      selectedType = type;
    });
    _loadTransactions(refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: const Text('Historique des transactions'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _loadTransactions(refresh: true),
          ),
        ],
      ),
      body: Column(
        children: [
          _buildFilterChips(),
          Expanded(
            child: isLoading
                ? const Center(child: CircularProgressIndicator())
                : error != null
                    ? _buildErrorWidget()
                    : transactions.isEmpty
                        ? _buildEmptyWidget()
                        : _buildTransactionsList(),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChips() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            FilterChip(
              label: const Text('Toutes'),
              selected: selectedType == null,
              onSelected: (_) => _onFilterChanged(null),
              backgroundColor: Colors.white,
              selectedColor: const Color(0xFF6366F1).withOpacity(0.2),
            ),
            const SizedBox(width: 8),
            ...transactionTypes.entries.map((entry) => Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                label: Text(entry.value),
                selected: selectedType == entry.key,
                onSelected: (_) => _onFilterChanged(entry.key),
                backgroundColor: Colors.white,
                selectedColor: const Color(0xFF6366F1).withOpacity(0.2),
              ),
            )),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorWidget() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
          const SizedBox(height: 16),
          Text('Erreur: $error'),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => _loadTransactions(refresh: true),
            child: const Text('Réessayer'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyWidget() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.receipt_long_outlined, size: 64, color: Colors.grey[400]),
          const SizedBox(height: 16),
          Text(
            selectedType == null 
                ? 'Aucune transaction trouvée'
                : 'Aucune transaction de ce type',
            style: TextStyle(
              fontSize: 18,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Commencez à regarder des publicités pour gagner des points!',
            style: TextStyle(
              color: Colors.grey[500],
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildTransactionsList() {
    return RefreshIndicator(
      onRefresh: () => _loadTransactions(refresh: true),
      child: ListView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: transactions.length + (isLoadingMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == transactions.length) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            );
          }

          final transaction = transactions[index];
          return _buildTransactionCard(transaction);
        },
      ),
    );
  }

  Widget _buildTransactionCard(Transaction transaction) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 5,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _buildTransactionIcon(transaction.type),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      transaction.typeDisplay,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    if (transaction.description.isNotEmpty)
                      Text(
                        transaction.description,
                        style: TextStyle(
                          color: Colors.grey[600],
                          fontSize: 12,
                        ),
                      ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    transaction.formattedAmount,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: _getAmountColor(transaction),
                    ),
                  ),
                  _buildStatusChip(transaction.status),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _formatDate(transaction.createdAt),
                style: TextStyle(
                  color: Colors.grey[500],
                  fontSize: 12,
                ),
              ),
              if (transaction.pointsToEuroRate != null)
                Text(
                  'Taux: 1€ = ${transaction.pointsToEuroRate!.toInt()} pts',
                  style: TextStyle(
                    color: Colors.grey[500],
                    fontSize: 12,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTransactionIcon(String type) {
    IconData icon;
    Color color;

    switch (type) {
      case 'points_earned':
        icon = Icons.stars;
        color = const Color(0xFF6366F1);
        break;
      case 'points_converted':
        icon = Icons.currency_exchange;
        color = const Color(0xFF10B981);
        break;
      case 'withdrawal':
        icon = Icons.account_balance;
        color = const Color(0xFFF59E0B);
        break;
      case 'referral_bonus':
        icon = Icons.group;
        color = const Color(0xFF8B5CF6);
        break;
      default:
        icon = Icons.receipt;
        color = Colors.grey;
    }

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, color: color, size: 20),
    );
  }

  Widget _buildStatusChip(String status) {
    Color color;
    Color backgroundColor;

    switch (status) {
      case 'completed':
        color = Colors.green[600]!;
        backgroundColor = Colors.green[50]!;
        break;
      case 'pending':
        color = Colors.orange[600]!;
        backgroundColor = Colors.orange[50]!;
        break;
      case 'processing':
        color = Colors.blue[600]!;
        backgroundColor = Colors.blue[50]!;
        break;
      case 'failed':
      case 'cancelled':
        color = Colors.red[600]!;
        backgroundColor = Colors.red[50]!;
        break;
      default:
        color = Colors.grey[600]!;
        backgroundColor = Colors.grey[50]!;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        _getStatusDisplayName(status),
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Color _getAmountColor(Transaction transaction) {
    if (transaction.type == 'points_earned' || transaction.type == 'referral_bonus') {
      return Colors.green[600]!;
    } else if (transaction.type == 'points_converted') {
      return Colors.blue[600]!;
    } else if (transaction.type == 'withdrawal') {
      return Colors.red[600]!;
    }
    return Colors.grey[600]!;
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays == 0) {
      return 'Aujourd\'hui ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
    } else if (difference.inDays == 1) {
      return 'Hier ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
    } else if (difference.inDays < 7) {
      return '${difference.inDays} jours';
    } else {
      return '${date.day}/${date.month}/${date.year}';
    }
  }

  String _getStatusDisplayName(String status) {
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