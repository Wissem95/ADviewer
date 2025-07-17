import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/wallet.dart';
import '../../services/api_service.dart';

class ConversionScreen extends ConsumerStatefulWidget {
  final WalletBalance walletBalance;

  const ConversionScreen({
    super.key,
    required this.walletBalance,
  });

  @override
  ConsumerState<ConversionScreen> createState() => _ConversionScreenState();
}

class _ConversionScreenState extends ConsumerState<ConversionScreen> {
  final TextEditingController _pointsController = TextEditingController();
  bool isLoading = false;
  int pointsToConvert = 0;
  double estimatedEuros = 0.0;

  @override
  void initState() {
    super.initState();
    _pointsController.addListener(_updateEstimation);
  }

  @override
  void dispose() {
    _pointsController.dispose();
    super.dispose();
  }

  void _updateEstimation() {
    final points = int.tryParse(_pointsController.text) ?? 0;
    setState(() {
      pointsToConvert = points;
      estimatedEuros = points / widget.walletBalance.conversion.rate;
    });
  }

  void _setQuickAmount(int points) {
    _pointsController.text = points.toString();
  }

  Future<void> _convertPoints() async {
    if (pointsToConvert < widget.walletBalance.conversion.minimumConversion) {
      _showError('Minimum ${widget.walletBalance.conversion.minimumConversion} points requis');
      return;
    }

    if (pointsToConvert > widget.walletBalance.points.currentBalance) {
      _showError('Solde de points insuffisant');
      return;
    }

    // Show confirmation dialog
    final confirmed = await _showConfirmationDialog();
    if (!confirmed) return;

    setState(() {
      isLoading = true;
    });

    try {
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.convertPoints(pointsToConvert);
      final result = ConversionResult.fromJson(response);

      if (mounted) {
        _showSuccessDialog(result);
      }
    } catch (e) {
      _showError(e.toString());
    } finally {
      setState(() {
        isLoading = false;
      });
    }
  }

  Future<bool> _showConfirmationDialog() async {
    return await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirmer la conversion'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Vous êtes sur le point de convertir:'),
            const SizedBox(height: 8),
            Text(
              '$pointsToConvert points → €${estimatedEuros.toStringAsFixed(2)}',
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Cette action est irréversible.',
              style: TextStyle(
                color: Colors.orange[600],
                fontSize: 12,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Annuler'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    ) ?? false;
  }

  void _showSuccessDialog(ConversionResult result) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.check_circle, color: Colors.green[600]),
            const SizedBox(width: 8),
            const Text('Conversion réussie!'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.green[50],
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  Text(
                    '€${result.euroReceived.toStringAsFixed(2)}',
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.bold,
                      color: Colors.green[600],
                    ),
                  ),
                  const Text('ajoutés à votre portefeuille'),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Points convertis:'),
                Text('${result.pointsConverted}'),
              ],
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Nouveau solde points:'),
                Text('${result.newPointsBalance}'),
              ],
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Nouveau solde argent:'),
                Text('€${result.newMoneyBalance.toStringAsFixed(2)}'),
              ],
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).pop(true); // Return to wallet screen
            },
            child: const Text('Parfait!'),
          ),
        ],
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: const Text('Convertir Points'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildCurrentBalanceCard(),
            const SizedBox(height: 24),
            _buildConversionRateCard(),
            const SizedBox(height: 24),
            _buildConversionForm(),
            const SizedBox(height: 24),
            _buildQuickAmounts(),
            const SizedBox(height: 32),
            _buildConvertButton(),
          ],
        ),
      ),
    );
  }

  Widget _buildCurrentBalanceCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Solde actuel',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: Column(
                  children: [
                    const Icon(Icons.stars, color: Color(0xFF6366F1), size: 32),
                    const SizedBox(height: 8),
                    Text(
                      '${widget.walletBalance.points.currentBalance}',
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF6366F1),
                      ),
                    ),
                    const Text('Points'),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward, color: Colors.grey),
              Expanded(
                child: Column(
                  children: [
                    const Icon(Icons.euro, color: Color(0xFF10B981), size: 32),
                    const SizedBox(height: 8),
                    Text(
                      widget.walletBalance.money.formattedBalance,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF10B981),
                      ),
                    ),
                    const Text('Euros'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildConversionRateCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          const Icon(Icons.swap_horiz, color: Colors.white, size: 32),
          const SizedBox(height: 8),
          const Text(
            'Taux de conversion',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            widget.walletBalance.conversion.rateDisplay,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConversionForm() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Combien de points convertir?',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _pointsController,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: InputDecoration(
              labelText: 'Points à convertir',
              hintText: 'Min. ${widget.walletBalance.conversion.minimumConversion}',
              suffixText: 'points',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              prefixIcon: const Icon(Icons.stars),
            ),
          ),
          const SizedBox(height: 16),
          if (pointsToConvert > 0) ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.green[50],
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green[200]!),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Vous recevrez:',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                      Text(
                        '€${estimatedEuros.toStringAsFixed(2)}',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: Colors.green[600],
                        ),
                      ),
                    ],
                  ),
                  Icon(Icons.euro, color: Colors.green[600], size: 32),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildQuickAmounts() {
    final amounts = [50, 100, 250, 500, 1000];
    final availableAmounts = amounts
        .where((amount) => amount <= widget.walletBalance.points.currentBalance)
        .toList();

    if (availableAmounts.isEmpty) return const SizedBox();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Montants rapides',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: availableAmounts.map((amount) {
            final euros = amount / widget.walletBalance.conversion.rate;
            return OutlinedButton(
              onPressed: () => _setQuickAmount(amount),
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF6366F1),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
              child: Text('$amount pts (€${euros.toStringAsFixed(2)})'),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildConvertButton() {
    final canConvert = pointsToConvert >= widget.walletBalance.conversion.minimumConversion &&
        pointsToConvert <= widget.walletBalance.points.currentBalance;

    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: canConvert && !isLoading ? _convertPoints : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF10B981),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: isLoading
            ? const CircularProgressIndicator(color: Colors.white)
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.currency_exchange),
                  const SizedBox(width: 8),
                  Text(
                    pointsToConvert > 0
                        ? 'Convertir $pointsToConvert points en €${estimatedEuros.toStringAsFixed(2)}'
                        : 'Convertir les points',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
} 