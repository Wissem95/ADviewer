import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:go_router/go_router.dart';
import '../../models/ad.dart';
import '../../services/api_service.dart';

class VideoFeedScreen extends ConsumerStatefulWidget {
  const VideoFeedScreen({super.key});

  @override
  ConsumerState<VideoFeedScreen> createState() => _VideoFeedScreenState();
}

class _VideoFeedScreenState extends ConsumerState<VideoFeedScreen> {
  late PageController _pageController;
  List<Ad> ads = [];
  bool isLoading = true;
  int currentIndex = 0;
  Map<int, VideoPlayerController> videoControllers = {};

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _loadAds();
  }

  @override
  void dispose() {
    _pageController.dispose();
    for (var controller in videoControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _loadAds() async {
    try {
      setState(() => isLoading = true);
      
      // Pour l'instant, utilisons des données mock car l'API n'est peut-être pas encore prête
      ads = _getMockAds();
      
      // Précharger les 3 premières vidéos
      for (int i = 0; i < 3 && i < ads.length; i++) {
        await _initializeVideoController(i);
      }
      
      setState(() => isLoading = false);
      
      // Démarrer la première vidéo
      if (ads.isNotEmpty) {
        _playVideo(0);
      }
    } catch (e) {
      setState(() => isLoading = false);
      _showError('Erreur lors du chargement des publicités');
    }
  }

  List<Ad> _getMockAds() {
    return [
      Ad(
        id: 1,
        title: 'Nike Air Max Revolution',
        description: 'Découvrez la nouvelle collection Nike Air Max. Style, confort et performance réunis.',
        videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
        thumbnailUrl: 'https://via.placeholder.com/400x600/FF6B6B/FFFFFF?text=Nike',
        advertiserName: 'Nike',
        advertiserLogo: 'https://via.placeholder.com/50x50/000000/FFFFFF?text=N',
        duration: 30,
        pointsReward: 15,
        hasQuiz: true,
        category: 'Sport',
        createdAt: DateTime.now(),
      ),
      Ad(
        id: 2,
        title: 'McDonald\'s Big Mac',
        description: 'Le goût inimitable du Big Mac vous attend. Disponible en livraison !',
        videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
        thumbnailUrl: 'https://via.placeholder.com/400x600/FFD93D/000000?text=McDonald\'s',
        advertiserName: 'McDonald\'s',
        advertiserLogo: 'https://via.placeholder.com/50x50/FFD93D/FF0000?text=M',
        duration: 25,
        pointsReward: 12,
        hasQuiz: true,
        category: 'Food',
        createdAt: DateTime.now(),
      ),
      Ad(
        id: 3,
        title: 'Samsung Galaxy S24',
        description: 'L\'innovation Galaxy S24. Photographiez, créez, partagez comme jamais.',
        videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
        thumbnailUrl: 'https://via.placeholder.com/400x600/4285F4/FFFFFF?text=Samsung',
        advertiserName: 'Samsung',
        advertiserLogo: 'https://via.placeholder.com/50x50/4285F4/FFFFFF?text=S',
        duration: 35,
        pointsReward: 18,
        hasQuiz: true,
        category: 'Tech',
        createdAt: DateTime.now(),
      ),
    ];
  }

  Future<void> _initializeVideoController(int index) async {
    if (index >= ads.length || videoControllers.containsKey(index)) return;

    final controller = VideoPlayerController.networkUrl(Uri.parse(ads[index].videoUrl));
    
    try {
      await controller.initialize();
      controller.setLooping(true);
      videoControllers[index] = controller;
    } catch (e) {
      debugPrint('Erreur initialisation vidéo $index: $e');
    }
  }

  void _playVideo(int index) {
    // Pause all other videos
    for (var entry in videoControllers.entries) {
      if (entry.key != index) {
        entry.value.pause();
      }
    }

    // Play current video
    if (videoControllers.containsKey(index)) {
      videoControllers[index]!.play();
    }
  }

  void _onPageChanged(int index) {
    setState(() => currentIndex = index);
    _playVideo(index);
    
    // Précharger la vidéo suivante
    if (index + 1 < ads.length) {
      _initializeVideoController(index + 1);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  Future<void> _completeAd(Ad ad) async {
    try {
      // Marquer la pub comme vue
      // await ref.read(apiServiceProvider).markAdAsViewed(ad.id);
      
      // Afficher les points gagnés
      _showPointsEarned(ad.pointsReward);
      
      // Si il y a un quiz, l'afficher
      if (ad.hasQuiz) {
        _showQuiz(ad);
      }
    } catch (e) {
      _showError('Erreur lors de la completion de la publicité');
    }
  }

  void _showPointsEarned(int points) {
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.stars, color: Colors.amber, size: 50),
            const SizedBox(height: 16),
            Text(
              '+$points points',
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.amber,
              ),
            ),
            const SizedBox(height: 8),
            const Text('Félicitations !'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Continuer'),
          ),
        ],
      ),
    );
  }

  void _showQuiz(Ad ad) {
    // TODO: Naviguer vers l'écran de quiz
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('Quiz disponible !'),
        content: Text('Répondez au quiz pour ${ad.title} et gagnez des points bonus !'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Passer'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              // TODO: Naviguer vers le quiz
            },
            child: const Text('Commencer'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: CircularProgressIndicator(color: Colors.white),
        ),
      );
    }

    if (ads.isEmpty) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.video_library_outlined, size: 64, color: Colors.white),
              const SizedBox(height: 16),
              const Text(
                'Aucune publicité disponible',
                style: TextStyle(color: Colors.white, fontSize: 18),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _loadAds,
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          PageView.builder(
            controller: _pageController,
            scrollDirection: Axis.vertical,
            itemCount: ads.length,
            onPageChanged: _onPageChanged,
            itemBuilder: (context, index) {
              return _buildVideoPage(ads[index], index);
            },
          ),
          _buildTopBar(),
        ],
      ),
    );
  }

  Widget _buildVideoPage(Ad ad, int index) {
    final videoController = videoControllers[index];
    
    return Stack(
      fit: StackFit.expand,
      children: [
        if (videoController != null && videoController.value.isInitialized)
          VideoPlayer(videoController)
        else
          Container(
            color: Colors.grey[900],
            child: const Center(
              child: CircularProgressIndicator(color: Colors.white),
            ),
          ),
        
        _buildVideoOverlay(ad),
      ],
    );
  }

  Widget _buildTopBar() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'AdViewer',
              style: TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            Row(
              children: [
                IconButton(
                  onPressed: () => context.go('/wallet'),
                  icon: const Icon(Icons.account_balance_wallet, color: Colors.white),
                ),
                IconButton(
                  onPressed: () => context.go('/profile'),
                  icon: const Icon(Icons.person, color: Colors.white),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVideoOverlay(Ad ad) {
    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.bottomCenter,
            end: Alignment.topCenter,
            colors: [
              Colors.black.withOpacity(0.8),
              Colors.transparent,
            ],
          ),
        ),
        padding: const EdgeInsets.all(20),
        child: SafeArea(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Advertiser info
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 16,
                          backgroundImage: NetworkImage(ad.advertiserLogo),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          ad.advertiserName,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    
                    // Ad title
                    Text(
                      ad.title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    
                    // Ad description
                    Text(
                      ad.description,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 14,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 8),
                    
                    // Points reward
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.amber,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.stars, size: 16),
                          const SizedBox(width: 4),
                          Text(
                            '+${ad.pointsReward} points',
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              
              // Action buttons
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildActionButton(
                    icon: Icons.thumb_up,
                    label: 'J\'aime',
                    onTap: () {},
                  ),
                  const SizedBox(height: 16),
                  _buildActionButton(
                    icon: Icons.share,
                    label: 'Partager',
                    onTap: () {},
                  ),
                  const SizedBox(height: 16),
                  _buildActionButton(
                    icon: Icons.check_circle,
                    label: 'Terminé',
                    onTap: () => _completeAd(ad),
                    color: Colors.green,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    Color color = Colors.white,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              color: color.withOpacity(0.2),
              shape: BoxShape.circle,
              border: Border.all(color: color, width: 2),
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
} 