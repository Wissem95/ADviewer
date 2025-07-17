# 🎬 AdViewer - Watch Ads, Earn Rewards

AdViewer est une application mobile de type TikTok où les utilisateurs regardent des publicités vidéo et gagnent des points en répondant correctement à des quiz. Les points peuvent être convertis en argent réel.

## 🌟 Fonctionnalités

### Pour les Utilisateurs

- **Feed Vidéo Style TikTok** : Défilement vertical infini avec publicités vidéo
- **Système de Quiz** : Questions interactives après chaque publicité
- **Points & Récompenses** : Gagnez des points pour regarder des pubs et réussir les quiz
- **Conversion Monétaire** : Convertissez vos points en euros
- **Système de Parrainage** : Invitez des amis et gagnez des bonus
- **Leaderboard** : Classements quotidiens, hebdomadaires et mensuels
- **Wallet Intégré** : Gérez vos gains et retraits
- **Profil Personnalisé** : Statistiques, badges et achievements

### Fonctionnalités Avancées

- **Algorithme de Recommandation Intelligent** : Publicités personnalisées
- **Système Anti-Fraude** : Détection multi-comptes, VPN, émulateurs
- **Mode Hors-ligne** : Cache de vidéos pour visionnage offline
- **Notifications Push** : Alertes pour nouvelles pubs et promotions
- **Thème Sombre/Clair** : Interface adaptative
- **Multi-langues** : Support de 7 langues

## 🏗️ Architecture

### Backend - Laravel (PHP)

```
backend/
├── app/
│   ├── Http/Controllers/API/
│   │   ├── AuthController.php
│   │   ├── AdController.php
│   │   ├── QuizController.php
│   │   ├── WalletController.php
│   │   └── LeaderboardController.php
│   ├── Models/
│   │   ├── User.php
│   │   ├── Ad.php
│   │   ├── Quiz.php
│   │   ├── UserAdView.php
│   │   ├── Transaction.php
│   │   └── UserSession.php
│   └── Middleware/
├── database/migrations/
├── routes/api.php
└── config/
```

### Frontend - Flutter (Dart)

```
frontend/
├── lib/
│   ├── config/
│   │   ├── app_config.dart
│   │   ├── theme.dart
│   │   └── routes.dart
│   ├── models/
│   ├── providers/
│   ├── services/
│   ├── screens/
│   │   ├── home/
│   │   ├── wallet/
│   │   ├── profile/
│   │   └── auth/
│   ├── widgets/
│   └── utils/
└── assets/
```

## 📊 Base de Données

### Tables Principales

- **users** : Gestion des utilisateurs avec système de parrainage
- **ads** : Publicités avec ciblage et budget
- **quizzes** : Questions liées aux publicités
- **user_ad_views** : Tracking des vues et interactions
- **transactions** : Historique des points et retraits
- **user_sessions** : Sessions pour anti-fraude

## 🚀 Installation

### Prérequis

- PHP 8.1+
- Composer
- MySQL 8.0+
- Node.js 18+
- Flutter 3.0+
- Redis (optionnel mais recommandé)

### Backend Laravel

1. **Cloner le repository**

```bash
git clone https://github.com/username/adviewer.git
cd adviewer/backend
```

2. **Installer les dépendances**

```bash
composer install
```

3. **Configuration environnement**

```bash
cp .env.example .env
php artisan key:generate
```

4. **Configurer la base de données**

```env
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=adviewer
DB_USERNAME=root
DB_PASSWORD=your_password
```

5. **Exécuter les migrations**

```bash
php artisan migrate
php artisan db:seed
```

6. **Configurer le storage**

```bash
php artisan storage:link
```

7. **Lancer le serveur**

```bash
php artisan serve
```

### Frontend Flutter

1. **Naviguer vers le dossier frontend**

```bash
cd ../frontend
```

2. **Installer les dépendances**

```bash
flutter pub get
```

3. **Générer les fichiers**

```bash
flutter packages pub run build_runner build
```

4. **Lancer l'application**

```bash
flutter run
```

## 🔧 Configuration

### Variables d'Environnement Backend

```env
# Application
APP_NAME=AdViewer
APP_ENV=production
APP_DEBUG=false
APP_URL=https://your-domain.com

# Database
DB_CONNECTION=mysql
DB_HOST=your-db-host
DB_DATABASE=adviewer
DB_USERNAME=your-username
DB_PASSWORD=your-password

# Cloudinary (Stockage vidéo)
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
CLOUDINARY_UPLOAD_PRESET=your_preset

# Points & Wallet
POINTS_TO_EURO_RATE=100
MIN_WITHDRAWAL_AMOUNT=5.00
REFERRAL_BONUS_POINTS=50
DAILY_VIEWING_LIMIT=50

# Payment
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret

# Anti-Fraud
MAX_ACCOUNTS_PER_IP=3
VPN_DETECTION_API_KEY=your_api_key
```

### Configuration Flutter

Modifiez `lib/config/app_config.dart` :

```dart
static const String baseUrl = 'https://your-api-domain.com/api';
```

## 🚢 Déploiement

### Backend sur Railway.app

1. **Créer un compte Railway**
2. **Connecter votre repository GitHub**
3. **Configurer les variables d'environnement**
4. **Script de déploiement automatique**

```bash
# railway.toml
[build]
  builder = "nixpacks"

[deploy]
  healthcheckPath = "/api/health"
  restartPolicyType = "always"
```

### Base de Données avec PlanetScale

1. **Créer une base de données PlanetScale**
2. **Obtenir la chaîne de connexion**
3. **Configurer les variables d'environnement**

### Frontend sur App Store / Play Store

1. **Build de production**

```bash
# Android
flutter build apk --release --obfuscate --split-debug-info=debug_info

# iOS
flutter build ios --release --obfuscate --split-debug-info=debug_info
```

2. **Upload sur les stores**

## 🔒 Sécurité

### Anti-Fraude

- Limitation de comptes par IP
- Détection VPN/Proxy
- Analyse comportementale
- Vérification device fingerprint
- Rate limiting API

### Protection des Données

- Chiffrement des données sensibles
- Authentification JWT/Sanctum
- Validation stricte côté serveur
- HTTPS obligatoire
- Logs d'audit complets

## 📈 Monitoring & Analytics

### Métriques Clés

- DAU/MAU (Daily/Monthly Active Users)
- Taux de rétention
- Revenue per User (RPU)
- Taux de completion des publicités
- Taux de réussite aux quiz
- Fraude rate

### Outils Intégrés

- Firebase Analytics
- Crashlytics
- Performance Monitoring
- Custom Events Tracking

## 🎯 Scalabilité

### Architecture Scalable

- API REST avec rate limiting
- Cache Redis pour performances
- CDN pour les vidéos (Cloudinary)
- Queue system pour tâches lourdes
- Database indexing optimisé

### Optimisations

- Pagination sur toutes les listes
- Lazy loading des images/vidéos
- Background sync
- Compression des données
- Cache stratégique

## 🤝 Contribution

1. Fork le project
2. Créer une feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branch (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 License

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 📞 Support

- Email: support@adviewer.com
- Documentation: https://docs.adviewer.com
- FAQ: https://adviewer.com/faq

## 🗺️ Roadmap

### Version 1.1

- [ ] Achievements & Badges
- [ ] Réalité Augmentée dans les pubs
- [ ] Chat communautaire

### Version 1.2

- [ ] Mode Tournament
- [ ] NFT Rewards
- [ ] Crypto Payments

### Version 2.0

- [ ] IA Personalization
- [ ] Live Streaming Ads
- [ ] Social Commerce

---

**Fait avec ❤️ pour révolutionner la publicité mobile**
